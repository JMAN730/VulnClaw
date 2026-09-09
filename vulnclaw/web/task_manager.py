"""In-memory task manager for the Web UI backend."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from vulnclaw.config.settings import WEB_TASKS_FILE, ensure_dirs
from vulnclaw.web.schemas import TaskCreateRequest, TaskEvent, TaskRecord, TaskSummary


class WebTaskManager:
    """Manage background task state and event streams."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._history: dict[str, deque[TaskEvent]] = {}
        self._queues: dict[str, asyncio.Queue[TaskEvent]] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._storage_path = WEB_TASKS_FILE
        self._load_state()

    def create_task(self, request: TaskCreateRequest) -> TaskRecord:
        task_id = f"task_{uuid4().hex[:12]}"
        record = TaskRecord(
            task_id=task_id,
            command=request.command,
            target=request.target,
            status="pending",
            resume=request.resume,
            snapshot_id=request.snapshot_id,
            options=request.options,
        )
        self._tasks[task_id] = record
        self._history[task_id] = deque(maxlen=500)
        self._queues[task_id] = asyncio.Queue()
        self.publish(
            task_id, "task_created", {"command": request.command, "target": request.target}
        )
        self._save_state()
        return record

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self._tasks.values())

    def publish(self, task_id: str, event: str, payload: dict) -> None:
        evt = TaskEvent(event=event, task_id=task_id, payload=payload)
        self._history.setdefault(task_id, deque(maxlen=500)).append(evt)
        queue = self._queues.get(task_id)
        if queue is not None:
            queue.put_nowait(evt)
        self._save_state()

    def set_restoring(self, task_id: str, *, snapshot_id: str | None = None) -> None:
        record = self._tasks[task_id]
        record.status = "restoring"
        self.publish(
            task_id,
            "task_restoring",
            {"status": record.status, "snapshot_id": snapshot_id or record.snapshot_id or ""},
        )

    def set_running(self, task_id: str) -> None:
        record = self._tasks[task_id]
        record.status = "running"
        record.started_at = datetime.now().isoformat()
        self.publish(task_id, "task_started", {"status": record.status})

    def set_completed(
        self,
        task_id: str,
        latest_message: str | None = None,
        summary: dict | TaskSummary | None = None,
    ) -> None:
        record = self._tasks[task_id]
        record.status = "completed"
        record.completed_at = datetime.now().isoformat()
        record.latest_message = latest_message
        if summary is not None:
            record.summary = summary if isinstance(summary, TaskSummary) else TaskSummary(**summary)
        payload = {"status": record.status, "message": latest_message or ""}
        if record.summary is not None:
            payload["summary"] = record.summary.model_dump(mode="json")
        self.publish(task_id, "task_completed", payload)

    def set_failed(self, task_id: str, error: str) -> None:
        record = self._tasks[task_id]
        record.status = "failed"
        record.completed_at = datetime.now().isoformat()
        record.error = error
        record.latest_message = error
        self.publish(task_id, "task_failed", {"status": record.status, "error": error})

    def set_stopped(self, task_id: str) -> None:
        record = self._tasks[task_id]
        record.status = "stopped"
        record.completed_at = datetime.now().isoformat()
        self.publish(task_id, "task_stopped", {"status": record.status})

    def update_progress(
        self, task_id: str, *, phase: str | None = None, message: str | None = None
    ) -> None:
        record = self._tasks[task_id]
        if phase:
            record.latest_phase = phase
        if message:
            record.latest_message = message
        self._save_state()

    async def stream_events(self, task_id: str):
        queue = self._queues[task_id]
        history = list(self._history.get(task_id, []))
        for item in history:
            yield item

        while True:
            record = self._tasks.get(task_id)
            if record and record.status in {"completed", "failed", "stopped"} and queue.empty():
                break
            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield item
            except (asyncio.TimeoutError, TimeoutError):
                # Python 3.10 下 asyncio.wait_for 抛 asyncio.TimeoutError（3.11 起才与
                # 内置 TimeoutError 合并），两者都捕获以保证流式循环跨版本不中断
                continue

    def bind_runtime_task(self, task_id: str, task: asyncio.Task) -> None:
        self._running[task_id] = task

    def release_runtime_task(self, task_id: str) -> None:
        """Drop the completed runtime task without changing its persisted record."""
        self._running.pop(task_id, None)

    async def stop_task(self, task_id: str) -> bool:
        task = self._running.get(task_id)
        if task is None:
            return False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # _run_task records cancellation before completing. Retain this guard
        # for callers that bind a task which exits without updating the record.
        record = self._tasks.get(task_id)
        if record is not None and record.status != "stopped":
            self.set_stopped(task_id)
        self.release_runtime_task(task_id)
        return True

    def _save_state(self) -> None:
        ensure_dirs()
        payload = {
            "tasks": [task.model_dump(mode="json") for task in self._tasks.values()],
            "history": {
                task_id: [event.model_dump(mode="json") for event in history]
                for task_id, history in self._history.items()
            },
        }
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._storage_path.parent,
                prefix=".web-tasks-",
                suffix=".json",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                json.dump(payload, temporary, ensure_ascii=False, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self._storage_path)
        finally:
            if temporary_path is not None:
                with contextlib.suppress(FileNotFoundError, OSError):
                    temporary_path.unlink()

    def _load_state(self) -> None:
        ensure_dirs()
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, dict):
            return

        task_items = raw.get("tasks", [])
        if not isinstance(task_items, list):
            task_items = []
        for item in task_items:
            if not isinstance(item, dict):
                continue
            try:
                record = TaskRecord(**item)
            except (TypeError, ValueError):
                continue
            self._tasks[record.task_id] = record
            self._history[record.task_id] = deque(maxlen=500)
            self._queues[record.task_id] = asyncio.Queue()

        history_by_task = raw.get("history", {})
        if not isinstance(history_by_task, dict):
            return
        for task_id, items in history_by_task.items():
            if not isinstance(task_id, str) or task_id not in self._tasks or not isinstance(items, list):
                continue
            events: deque[TaskEvent] = deque(maxlen=500)
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    event = TaskEvent(**item)
                except (TypeError, ValueError):
                    continue
                if event.task_id == task_id:
                    events.append(event)
            self._history[task_id] = events
