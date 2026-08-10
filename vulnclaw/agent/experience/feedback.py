"""Operator feedback persistence for completed run directories."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vulnclaw.run_context import RunContext, atomic_write_json


def save_feedback(context: RunContext, *, rating: int, notes: str) -> dict[str, Any]:
    """Upsert one validated feedback record and emit an audit event."""
    if rating not in range(1, 6):
        raise ValueError("rating must be an integer from 1 to 5")
    if "\x00" in notes:
        raise ValueError("notes cannot contain NUL characters")
    record = {
        "rating": rating,
        "notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(context.run_dir / "feedback.json", record)
    context.append_event("operator_feedback", {"rating": rating, "has_notes": bool(notes)})
    return record


def load_feedback(run_dir: Path | str) -> dict[str, Any] | None:
    """Load feedback without raising on a missing or malformed optional file."""
    import json

    path = Path(run_dir) / "feedback.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    return value
