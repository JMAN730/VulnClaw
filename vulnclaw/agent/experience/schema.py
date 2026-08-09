"""Lesson schema — distilled, human-approved experience for the self-learning loop.

A ``Lesson`` is the unit of durable knowledge produced by distilling a run's
transcript into a transferable instruction. Lessons are born ``pending`` and
only become retrievable for reuse once a human flips them to ``approved`` —
this is the anti-poisoning gate that keeps a compromised or hallucinating
distillation pass from injecting bad guidance into future runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


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
    confidence: float = 0.0
    source_runs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    target_key: str | None = None
