"""Lesson schema — distilled, human-approved experience for the self-learning loop.

A ``Lesson`` is the unit of durable knowledge produced by distilling a run's
transcript into a transferable instruction. Lessons are born ``pending`` and
only become retrievable for reuse once a human flips them to ``approved`` —
this is the anti-poisoning gate that keeps a compromised or hallucinating
distillation pass from injecting bad guidance into future runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class LessonScope(str, Enum):
    """Whether a lesson applies to a specific target or is target-agnostic."""

    TARGET = "target"
    TECHNIQUE = "technique"


class LessonStatus(str, Enum):
    """Human review state. Only APPROVED lessons are retrievable."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LessonSignal(str, Enum):
    """Whether the lesson captures a success to repeat or a dead end to avoid."""

    SUCCESS = "success"
    DEADEND = "deadend"


class LessonTags(BaseModel):
    """Structured tags used for retrieval matching."""

    tech: list[str] = Field(default_factory=list)
    vuln_type: str = ""
    waf: str = ""
    service: str = ""


class LessonEvidenceRefs(BaseModel):
    """Provenance pointers back to the run that produced the lesson."""

    run_id: str
    finding_id: str | None = None
    path: str | None = None


class Lesson(BaseModel):
    """A single distilled, retrievable lesson.

    Created ``pending``; must be approved by a human reviewer before it can
    be surfaced by retrieval (see ``ExperienceStore.list_by_status``).
    """

    id: str = Field(default_factory=lambda: f"exp-{uuid.uuid4()}")
    scope: LessonScope
    status: LessonStatus = LessonStatus.PENDING
    signal: LessonSignal
    tags: LessonTags = Field(default_factory=LessonTags)
    context: str
    lesson: str
    evidence_refs: LessonEvidenceRefs
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_runs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target_key: str | None = None
    last_reinforced_at: str | None = None

    @model_validator(mode="after")
    def validate_scope_key(self) -> "Lesson":
        if self.scope == LessonScope.TECHNIQUE and self.target_key is not None:
            raise ValueError("technique-scoped lessons cannot carry target_key")
        return self

    def effective_confidence(
        self,
        *,
        now: datetime | None = None,
        half_life_days: float = 30.0,
    ) -> float:
        """Return confidence reweighted by age without mutating the lesson."""
        if half_life_days <= 0:
            return self.confidence
        anchor = self.last_reinforced_at or self.created_at
        try:
            created = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
            current = now or datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            age = max(0.0, (current - created).total_seconds())
        except (AttributeError, TypeError, ValueError):
            return self.confidence
        decay = 0.5 ** (age / timedelta(days=half_life_days).total_seconds())
        return round(self.confidence * decay, 6)
