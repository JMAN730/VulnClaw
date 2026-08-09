"""Self-learning loop spine — distilled lessons, gated behind human approval."""

from vulnclaw.agent.experience.retrieval import (
    TargetContext,
    build_experience_context,
    target_context_from_agent,
)
from vulnclaw.agent.experience.schema import (
    Lesson,
    LessonEvidenceRefs,
    LessonScope,
    LessonSignal,
    LessonStatus,
    LessonTags,
)
from vulnclaw.agent.experience.store import ExperienceStore

__all__ = [
    "ExperienceStore",
    "Lesson",
    "LessonEvidenceRefs",
    "LessonScope",
    "LessonSignal",
    "LessonStatus",
    "LessonTags",
    "TargetContext",
    "build_experience_context",
    "target_context_from_agent",
]
