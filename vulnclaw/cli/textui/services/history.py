"""Chat history persistence — save/load chat messages per target.

Each target's chat history is stored as a JSON file under
``~/.vulnclaw/history/<sanitized_target>.json``.

Only text messages (user + assistant) are persisted — tool
call details and system messages are excluded.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ChatMessageData:
    """Serialisable chat message record."""

    type: str  # "user" | "assistant"
    content: str
    timestamp: str = ""
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")


class ChatHistoryStore:
    """Persistent chat history storage keyed by target."""

    def __init__(self, store_dir: Path | None = None) -> None:
        if store_dir is None:
            store_dir = Path.home() / ".vulnclaw" / "history"
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────

    def save(self, target: str, messages: list[ChatMessageData]) -> None:
        """Save chat messages for *target*."""
        file_path = self._path_for(target)
        data = {
            "target": target,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "messages": [asdict(m) for m in messages],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, target: str) -> list[ChatMessageData]:
        """Load chat messages for *target* (returns empty list if none)."""
        file_path = self._path_for(target)
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ChatMessageData(**m) for m in data.get("messages", [])]

    def delete(self, target: str) -> None:
        """Delete chat history for *target*."""
        self._path_for(target).unlink(missing_ok=True)

    def list_targets(self) -> list[tuple[str, str]]:
        """List (target, iso_timestamp) for all saved histories, newest first."""
        entries: list[tuple[str, str]] = []
        for file_path in self._dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ts = data.get("timestamp", "")
                target = data.get("target", file_path.stem)
                entries.append((target, ts))
            except (json.JSONDecodeError, OSError):
                continue
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries

    # ── Internal ──────────────────────────────────────────────────

    def _path_for(self, target: str) -> Path:
        return self._dir / f"{self._sanitize_filename(target)}.json"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:120]


# ── Global singleton accessors ─────────────────────────────────────

_STORE: ChatHistoryStore | None = None


def get_history_store() -> ChatHistoryStore:
    global _STORE
    if _STORE is None:
        _STORE = ChatHistoryStore()
    return _STORE


def set_history_store(store: ChatHistoryStore) -> None:
    global _STORE
    _STORE = store
