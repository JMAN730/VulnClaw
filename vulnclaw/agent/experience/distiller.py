"""Turn finished-run evidence into human-gated experience lessons."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from vulnclaw.agent.experience.schema import (
    Lesson,
    LessonEvidenceRefs,
    LessonScope,
    LessonSignal,
    LessonTags,
)
from vulnclaw.agent.experience.store import ExperienceStore
from vulnclaw.agent.reflexion import ReflexionEngine, ReflexionState
from vulnclaw.i18n import current_lang
from vulnclaw.kb.retriever import _tokenize

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.6


@dataclass
class RunArtifacts:
    """Machine-readable inputs collected from one completed run."""

    run_id: str
    verified_findings: list[dict[str, Any]] = field(default_factory=list)
    reflexion_snapshot: dict[str, Any] = field(default_factory=dict)
    reasoning_path_statuses: list[dict[str, Any]] = field(default_factory=list)
    step_summary: str = ""
    target: str = ""
    operator_feedback: Optional[dict[str, Any]] = None

    def reflexion_experience(self) -> dict[str, Any]:
        if not self.reflexion_snapshot:
            return {}
        try:
            return ReflexionEngine(
                state=ReflexionState.model_validate(self.reflexion_snapshot)
            ).extract_experience() or {}
        except Exception:
            logger.warning("run %s: invalid reflexion snapshot", self.run_id)
            return {}

    def failed_paths(self) -> set[str]:
        paths = set(self.reflexion_experience().get("failed_paths", []) or [])
        for item in self.reasoning_path_statuses:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or item.get("state") or "").lower()
            path = str(item.get("path") or item.get("name") or "").strip()
            if path and status in {"failed", "deadend", "dead_end", "blocked"}:
                paths.add(path)
        return paths

    def has_evidence(self) -> bool:
        return bool(self.verified_findings or self.failed_paths())

    @classmethod
    def from_run_dir(
        cls, run_dir: Path | str, *, run_id: str | None = None
    ) -> "RunArtifacts":
        run_dir = Path(run_dir)
        resolved_id = run_id or run_dir.name
        verified: list[dict[str, Any]] = []
        findings_path = run_dir / "findings" / "findings.json"
        try:
            document = json.loads(findings_path.read_text(encoding="utf-8"))
            verified = list(document.get("verified", []) or [])
        except (OSError, TypeError, ValueError):
            pass

        snapshot: dict[str, Any] = {}
        paths: list[dict[str, Any]] = []
        target = ""
        state_paths = sorted((run_dir / "targets").glob("*/state/current.json"))
        if state_paths:
            try:
                raw = json.loads(state_paths[0].read_text(encoding="utf-8"))
                if not verified:
                    verified = [
                        item
                        for item in (raw.get("findings") or [])
                        if isinstance(item, dict)
                        and (
                            item.get("verified") is True
                            or item.get("verification_status") == "verified"
                        )
                    ]
                snapshot = dict(raw.get("reflexion_snapshot") or {})
                paths = list(raw.get("reasoning_path_statuses") or raw.get("path_statuses") or [])
                records = list(raw.get("step_records") or [])
                target = str(raw.get("target") or "")
                summary = "; ".join(
                    str(item.get("summary") or item.get("action") or "")
                    for item in records[-10:]
                    if isinstance(item, dict)
                ).strip("; ")
            except (OSError, TypeError, ValueError):
                summary = ""
        else:
            summary = ""

        feedback: Optional[dict[str, Any]] = None
        feedback_path = run_dir / "feedback.json"
        try:
            raw_feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
            if isinstance(raw_feedback, dict):
                feedback = raw_feedback
        except (OSError, TypeError, ValueError):
            pass
        return cls(
            run_id=resolved_id,
            verified_findings=verified,
            reflexion_snapshot=snapshot,
            reasoning_path_statuses=paths,
            step_summary=summary,
            target=target,
            operator_feedback=feedback,
        )


class DistillerLLM(Protocol):
    """One-call structured-output boundary used by ``distill_run``."""

    def generate_lessons(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...


class AgentDistillerLLM:
    """Adapter for the existing synchronous structured LLM call."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    def generate_lessons(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        from vulnclaw.agent.solver import structured_call

        prompt = (
            "Return JSON only in the shape {\"lessons\":[...]}. Distill only lessons "
            "supported by the supplied verified findings or failed paths. Each lesson "
            "must contain scope, signal, context, lesson, tags, confidence, and evidence. "
            "Evidence must be {\"finding_id\": id} or {\"failed_path\": path} copied "
            "exactly from the payload.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        response = asyncio.run(structured_call(self.agent, prompt, max_tokens=1400))
        return _parse_candidates(response)


def distill_run(
    artifacts: RunArtifacts,
    llm: DistillerLLM,
    *,
    store: Optional[ExperienceStore] = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[Lesson]:
    """Make one LLM call and persist only evidence-backed pending lessons."""
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0 and 1")
    if not artifacts.has_evidence():
        return []
    store = store or ExperienceStore()
    experience = artifacts.reflexion_experience()
    payload = _build_payload(artifacts, experience)
    try:
        candidates = llm.generate_lessons(payload) or []
    except Exception:
        logger.exception("run %s: distiller LLM call failed", artifacts.run_id)
        return []

    verified_by_id = {
        str(item.get("finding_id") or item.get("id") or ""): item
        for item in artifacts.verified_findings
        if isinstance(item, dict)
    }
    written: list[Lesson] = []
    for raw in candidates:
        lesson = _build_lesson(raw, artifacts, verified_by_id, artifacts.failed_paths())
        if lesson is None:
            continue
        duplicate = _find_near_duplicate(lesson, store, similarity_threshold)
        if duplicate is not None:
            merged = store.merge(lesson, into_id=duplicate.id)
            if merged is not None:
                written.append(merged)
            continue
        store.add(lesson)
        written.append(lesson)
    return written


def schedule_run_distillation(run_context: Any, agent: Any) -> threading.Thread:
    """Start best-effort completion distillation in a managed worker thread.

    The caller owns the returned thread and must join it before shutting down
    a short-lived process, such as the CLI.
    """
    def worker() -> None:
        try:
            artifacts = RunArtifacts.from_run_dir(
                run_context.run_dir,
                run_id=str(run_context.manifest.get("run_id") or run_context.run_name),
            )
            lessons = distill_run(artifacts, AgentDistillerLLM(agent))
            run_context.append_event("distillation_completed", {"lessons": len(lessons)})
        except Exception as exc:
            logger.exception("run %s: async distillation failed", run_context.run_name)
            try:
                run_context.append_event("distillation_failed", {"error": str(exc)[:300]})
            except Exception:
                pass

    thread = threading.Thread(
        target=worker,
        name=f"vulnclaw-distill-{run_context.run_name}",
        daemon=True,
    )
    thread.start()
    return thread


def _build_payload(artifacts: RunArtifacts, experience: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": artifacts.run_id,
        "target": artifacts.target,
        "language": current_lang(),
        "verified_findings": artifacts.verified_findings,
        "reflexion_experience": experience,
        "failed_paths": sorted(artifacts.failed_paths()),
        "reasoning_path_statuses": artifacts.reasoning_path_statuses,
        "step_summary": artifacts.step_summary,
        "operator_feedback": artifacts.operator_feedback,
    }


def _build_lesson(
    raw: Any,
    artifacts: RunArtifacts,
    verified_by_id: dict[str, dict[str, Any]],
    failed_paths: set[str],
) -> Optional[Lesson]:
    if not isinstance(raw, dict):
        return None
    evidence = raw.get("evidence") or raw.get("evidence_refs") or {}
    if not isinstance(evidence, dict):
        return None
    finding_id = str(evidence.get("finding_id") or "")
    failed_path = str(evidence.get("failed_path") or evidence.get("path") or "")
    finding = verified_by_id.get(finding_id)
    if finding is None and failed_path not in failed_paths:
        logger.warning("run %s: dropping unbacked lesson", artifacts.run_id)
        return None

    try:
        scope = LessonScope(str(raw.get("scope") or LessonScope.TECHNIQUE.value))
    except ValueError:
        scope = LessonScope.TECHNIQUE
    try:
        signal = LessonSignal(str(raw.get("signal") or (
            LessonSignal.SUCCESS.value if finding is not None else LessonSignal.DEADEND.value
        )))
    except ValueError:
        signal = LessonSignal.SUCCESS if finding is not None else LessonSignal.DEADEND
    raw_tags = raw.get("tags")
    tags_raw: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
    tags = LessonTags(
        tech=[str(item) for item in tags_raw.get("tech", []) if item],
        vuln_type=str(tags_raw.get("vuln_type") or ""),
        waf=str(tags_raw.get("waf") or ""),
        service=str(tags_raw.get("service") or ""),
    )
    lesson_text = str(raw.get("lesson") or "").strip()
    if not lesson_text:
        return None
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    feedback: dict[str, Any] = artifacts.operator_feedback or {}
    try:
        rating = int(feedback.get("rating"))
    except (TypeError, ValueError):
        rating = 3
    confidence = max(0.0, min(1.0, confidence * (0.7 + 0.1 * rating)))
    target_key = str(raw.get("target_key") or artifacts.target or "") if scope == LessonScope.TARGET else None
    if scope == LessonScope.TARGET and not target_key:
        return None
    return Lesson(
        scope=scope,
        signal=signal,
        tags=tags,
        context=str(raw.get("context") or "").strip(),
        lesson=lesson_text,
        evidence_refs=LessonEvidenceRefs(
            run_id=artifacts.run_id,
            finding_id=finding_id or None,
            path=(str(finding.get("endpoint") or "") if finding else "") or failed_path or None,
        ),
        confidence=confidence,
        source_runs=[artifacts.run_id],
        target_key=target_key,
    )


def _lesson_tokens(lesson: Lesson) -> Counter[str]:
    return Counter(_tokenize(" ".join([
        lesson.context, lesson.lesson, lesson.tags.vuln_type,
        lesson.tags.waf, lesson.tags.service, *lesson.tags.tech,
    ])))


def token_similarity(a: Lesson, b: Lesson) -> float:
    """Cosine similarity used by deduplication."""
    left, right = _lesson_tokens(a), _lesson_tokens(b)
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(token, 0) for token, value in left.items())
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return dot / denominator if denominator else 0.0


def _find_near_duplicate(
    candidate: Lesson, store: ExperienceStore, threshold: float
) -> Optional[Lesson]:
    from vulnclaw.agent.experience.schema import LessonStatus

    candidates = store.list_by_status(LessonStatus.PENDING) + store.list_by_status(LessonStatus.APPROVED)
    best: Optional[Lesson] = None
    best_score = threshold
    for existing in candidates:
        if existing.scope != candidate.scope or existing.target_key != candidate.target_key:
            continue
        score = token_similarity(candidate, existing)
        if score > best_score:
            best_score = score
            best = existing
    return best


def _parse_candidates(response: str) -> list[dict[str, Any]]:
    """Parse the single structured response defensively."""
    cleaned = (response or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    try:
        value = json.loads(cleaned)
    except (TypeError, ValueError):
        return []
    if isinstance(value, dict):
        value = value.get("lessons", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
