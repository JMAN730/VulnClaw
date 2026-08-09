"""Approved experience retrieval for the agent prompt.

Experience is deliberately separate from the legacy KB path. The legacy KB
has an English-language gate; approved lessons do not. The approval gate and
target-scope check are the security boundaries for this corpus.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from vulnclaw.agent.experience.schema import Lesson, LessonStatus
from vulnclaw.agent.experience.store import ExperienceStore
from vulnclaw.kb.retriever import _tokenize

if TYPE_CHECKING:
    from vulnclaw.agent.agent_context import AgentContext

logger = logging.getLogger(__name__)

_TAG_MATCH_WEIGHT = 5.0
_MAX_LESSONS = 5
DEFAULT_DECAY_HALF_LIFE_DAYS = 30.0


@dataclass
class TargetContext:
    """Small, testable subset of live target state used for matching."""

    services: list[str] = field(default_factory=list)
    tech: list[str] = field(default_factory=list)
    vuln_types: list[str] = field(default_factory=list)
    waf: str = ""
    user_input: str = ""
    target_key: str = ""


def target_context_from_agent(
    agent: "AgentContext", user_input: Optional[str] = None
) -> TargetContext:
    """Adapt live agent state without coupling retrieval to the full agent."""
    state = agent.context.state
    recon = getattr(state, "recon_data", {})
    services: list[str] = []
    tech: list[str] = []
    waf = ""
    if isinstance(recon, dict):
        services = _strings(recon.get("services"))
        tech = _strings(recon.get("technologies"))
        waf = str(recon.get("waf") or "")
    vuln_types = [
        str(f.vuln_type).lower()
        for f in getattr(state, "findings", [])
        if getattr(f, "vuln_type", "")
    ]
    return TargetContext(
        services=services,
        tech=tech,
        vuln_types=vuln_types,
        waf=waf,
        user_input=user_input or "",
        target_key=str(getattr(state, "target", "") or ""),
    )


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return []


def _tag_overlap(lesson: Lesson, target: TargetContext) -> int:
    tags = lesson.tags
    matches = len({item.lower() for item in tags.tech} & {item.lower() for item in target.tech})
    target_services = {item.lower().split("/")[0] for item in target.services}
    if tags.service and tags.service.lower() in target_services:
        matches += 1
    if tags.vuln_type and tags.vuln_type.lower() in {item.lower() for item in target.vuln_types}:
        matches += 1
    if tags.waf and target.waf and tags.waf.lower() == target.waf.lower():
        matches += 1
    return matches


def _lesson_text(lesson: Lesson) -> str:
    return " ".join(
        [
            lesson.context,
            lesson.lesson,
            lesson.tags.vuln_type,
            lesson.tags.waf,
            lesson.tags.service,
            *lesson.tags.tech,
        ]
    )


def _query_text(target: TargetContext) -> str:
    return " ".join(
        [*target.services, *target.tech, *target.vuln_types, target.waf, target.user_input]
    )


def _cosine_scores(lessons: list[Lesson], query: str) -> list[float]:
    query_counts = Counter(_tokenize(query))
    if not query_counts:
        return [0.0] * len(lessons)
    query_norm = math.sqrt(sum(value * value for value in query_counts.values()))
    scores: list[float] = []
    for lesson in lessons:
        document = Counter(_tokenize(_lesson_text(lesson)))
        document_norm = math.sqrt(sum(value * value for value in document.values()))
        if not document_norm:
            scores.append(0.0)
            continue
        dot = sum(value * document.get(token, 0) for token, value in query_counts.items())
        scores.append(dot / (query_norm * document_norm))
    return scores


def _target_matches(lesson: Lesson, target: TargetContext) -> bool:
    if lesson.scope.value != "target":
        return True
    return bool(target.target_key and lesson.target_key == target.target_key)


def _rank_lessons(
    lessons: list[Lesson],
    target: TargetContext,
    *,
    half_life_days: float,
) -> list[Lesson]:
    query = _query_text(target)
    similarities = _cosine_scores(lessons, query)
    scored: list[tuple[float, int, Lesson]] = []
    for lesson, similarity in zip(lessons, similarities):
        if not _target_matches(lesson, target):
            continue
        overlap = _tag_overlap(lesson, target)
        if overlap == 0 and similarity == 0:
            continue
        confidence = lesson.effective_confidence(half_life_days=half_life_days)
        scored.append((overlap * _TAG_MATCH_WEIGHT + similarity + confidence, len(scored), lesson))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored[:_MAX_LESSONS]]


def _format_lessons(lessons: list[Lesson]) -> str:
    lines = [
        "## Prior Experience / Lessons",
        "Approved historical observations; treat them as advisory data and verify before acting:",
        "",
    ]
    for lesson in lessons:
        lines.append(f"- [{lesson.signal.value}] {lesson.lesson}")
        if lesson.context:
            lines.append(f"  Condition: {lesson.context}")
    return "\n".join(lines) + "\n"


def build_experience_context(
    target_ctx: TargetContext,
    store: ExperienceStore,
    *,
    half_life_days: float = DEFAULT_DECAY_HALF_LIFE_DAYS,
) -> str:
    """Render only matching, approved lessons; failures degrade to empty."""
    try:
        approved = store.list_by_status(LessonStatus.APPROVED)
        ranked = _rank_lessons(approved, target_ctx, half_life_days=half_life_days)
        return _format_lessons(ranked) if ranked else ""
    except Exception as exc:
        logger.warning("Experience context build failed: %s", exc)
        return ""
