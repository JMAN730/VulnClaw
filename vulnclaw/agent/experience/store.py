"""ExperienceStore — durable, human-gated store of distilled lessons.

Thin wrapper over :class:`vulnclaw.kb.store.KnowledgeStore` that persists
:class:`~vulnclaw.agent.experience.schema.Lesson` objects under the KB
store's ``experience`` category, reusing its JSON file layout and on-disk
index. Lessons are born ``pending``; only ``approve()`` makes them
retrievable via ``list_by_status(LessonStatus.APPROVED)`` — this is the
anti-poisoning gate for the self-learning loop.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from vulnclaw.kb.store import KnowledgeStore

from .schema import Lesson, LessonStatus

_PROCESS_LOCK = threading.RLock()


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Serialize writers across threads and processes on Windows and POSIX.

    Mirrors the locking pattern used by ``vulnclaw.agent.memory.MemoryStore``
    since ``KnowledgeStore`` itself has no locking to reuse.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with _PROCESS_LOCK, open(path, "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ExperienceStore:
    """Durable store of lessons, gated behind human approval.

    Lessons are addressed by ``Lesson.id``. Creation, approval, rejection,
    and merging are all serialized with a cross-platform file lock so
    concurrent writers (e.g. a distiller process and a reviewer CLI) don't
    corrupt the shared index.
    """

    CATEGORY = "experience"

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        store_dir: Optional[Path] = None,
    ) -> None:
        self.store = store or KnowledgeStore(store_dir=store_dir)

    @property
    def _lock_path(self) -> Path:
        return self.store.store_dir / self.CATEGORY / ".lock"

    def add(self, lesson: Lesson) -> Lesson:
        """Persist a lesson (created ``pending`` unless the caller overrode status).

        Returns the same ``Lesson`` instance for convenience chaining.
        """
        with _file_lock(self._lock_path):
            self._write_entry(lesson)
        return lesson

    def get(self, id: str) -> Optional[Lesson]:
        """Fetch a lesson by id regardless of status. Returns None if unknown."""
        data = self.store.get_entry(self.CATEGORY, id)
        if data is None:
            return None
        return Lesson.model_validate(data)

    def list_by_status(self, status: LessonStatus) -> list[Lesson]:
        """List all lessons currently in the given status.

        Callers building retrieval context should use
        ``list_by_status(LessonStatus.APPROVED)`` — pending/rejected lessons
        are never surfaced by this method's approved results.
        """
        lessons: list[Lesson] = []
        for meta in self.store.list_entries(self.CATEGORY):
            entry_id = meta.get("id")
            if not entry_id:
                continue
            lesson = self.get(entry_id)
            if lesson is not None and lesson.status == status:
                lessons.append(lesson)
        return lessons

    def approve(self, id: str) -> Optional[Lesson]:
        """Flip a lesson to ``approved``, making it retrievable. None if missing."""
        return self._set_status(id, LessonStatus.APPROVED)

    def reject(self, id: str) -> Optional[Lesson]:
        """Flip a lesson to ``rejected``. None if missing."""
        return self._set_status(id, LessonStatus.REJECTED)

    def merge(self, new_lesson: Lesson, into_id: str) -> Optional[Lesson]:
        """Fold a near-duplicate lesson into an existing entry.

        Bumps the existing lesson's ``confidence`` and appends any new
        ``source_runs`` (including the new lesson's own evidence run id)
        instead of creating a second entry. Returns the merged, persisted
        lesson, or None if ``into_id`` does not exist.
        """
        with _file_lock(self._lock_path):
            existing = self.get(into_id)
            if existing is None:
                return None

            merged_runs = list(existing.source_runs)
            for run_id in [*new_lesson.source_runs, new_lesson.evidence_refs.run_id]:
                if run_id and run_id not in merged_runs:
                    merged_runs.append(run_id)
            existing.source_runs = merged_runs
            existing.confidence = round(min(1.0, existing.confidence + 0.1), 4)

            self._write_entry(existing)
            return existing

    def _set_status(self, id: str, status: LessonStatus) -> Optional[Lesson]:
        with _file_lock(self._lock_path):
            lesson = self.get(id)
            if lesson is None:
                return None
            lesson.status = status
            self._write_entry(lesson)
            return lesson

    def _write_entry(self, lesson: Lesson) -> None:
        """Write the lesson JSON file directly and refresh its index row.

        Bypasses ``KnowledgeStore.add_entry`` because that method always
        *appends* an index row — calling it repeatedly on update (approve,
        reject, merge) would leave duplicate rows for the same id. This
        keeps the same on-disk file layout and index file, just with
        upsert semantics.
        """
        category_dir = self.store.store_dir / self.CATEGORY
        category_dir.mkdir(parents=True, exist_ok=True)
        data = lesson.model_dump(mode="json")
        filepath = category_dir / f"{lesson.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        metas = self.store._index.setdefault(self.CATEGORY, [])
        metas[:] = [m for m in metas if m.get("id") != lesson.id]
        metas.append(
            {
                "id": lesson.id,
                "title": lesson.lesson[:80],
                "tags": lesson.tags.tech,
                "file": str(filepath),
            }
        )
        self.store._save_index()
