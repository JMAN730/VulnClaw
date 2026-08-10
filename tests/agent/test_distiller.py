from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vulnclaw.agent.distiller import (
    _LESSON_SCHEMA,
    RunArtifacts,
    distill_run,
    persist_distilled_lessons,
    schedule_run_distillation,
)
from vulnclaw.agent.reasoning_state import AttackPath, PathStatus, ReasoningState
from vulnclaw.kb.experience import ExperienceStore, LessonStatus


def _artifacts(run_id: str = "run-1") -> RunArtifacts:
    return RunArtifacts(
        run_id=run_id,
        target_key="target-123",
        language="en",
        verified_findings=[{"finding_id": "finding-1", "vuln_type": "sqli"}],
        reflexion_snapshot={"failed_paths": ["sqli-union"]},
        reasoning_paths=[{"path": "sqli-union", "status": "failed"}],
        step_summary=[{"action": "probe", "status": "success"}],
    )


def _candidate(payload: dict) -> dict:
    assert payload["run_id"]
    return {
        "lessons": [
            {
                "scope": "technique",
                "signal": "success",
                "tags": {"tech": ["mysql"], "vuln_type": "sqli"},
                "context": "A MySQL error-based SQL injection is verified.",
                "lesson": "Validate the error condition before escalating extraction.",
                "confidence": 0.7,
                "evidence_refs": {"finding_id": "finding-1"},
            },
            {
                "scope": "technique",
                "signal": "success",
                "tags": {},
                "context": "unverified assertion",
                "lesson": "This must never be persisted.",
                "evidence_refs": {},
            },
        ]
    }


def test_distill_run_accepts_only_candidates_with_recorded_provenance():
    lessons = distill_run(_artifacts(), _candidate)

    assert len(lessons) == 1
    assert lessons[0].status is LessonStatus.PENDING
    assert lessons[0].evidence_refs.run_id == "run-1"
    assert lessons[0].evidence_refs.finding_id == "finding-1"
    assert lessons[0].id.startswith("lesson-")


def test_distill_run_accepts_a_recorded_failed_path_as_provenance():
    lessons = distill_run(
        _artifacts(),
        lambda _payload: {
            "lessons": [
                {
                    "scope": "target",
                    "signal": "deadend",
                    "tags": {"waf": "example-waf"},
                    "context": "The target blocks the UNION probe.",
                    "lesson": "Switch attack surfaces after this WAF block.",
                    "evidence_refs": {"path": "sqli-union"},
                }
            ]
        },
    )

    assert len(lessons) == 1
    assert lessons[0].target_key == "target-123"
    assert lessons[0].evidence_refs.path == "sqli-union"


def test_distill_run_accepts_a_failed_structured_reasoning_path_as_provenance():
    session = SimpleNamespace(
        findings=[],
        step_records=[],
        reasoning=ReasoningState(
            paths=[AttackPath(name="blocked-login-sqli", status=PathStatus.FAILED)]
        ),
        reflexion_snapshot={},
    )
    artifacts = RunArtifacts.from_session("run-1", session, target_key="target-123")

    lessons = distill_run(
        artifacts,
        lambda _payload: {
            "lessons": [
                {
                    "scope": "target",
                    "signal": "deadend",
                    "tags": {"waf": "example-waf"},
                    "context": "The login SQL injection path was blocked.",
                    "lesson": "Use a different attack surface after the block.",
                    "confidence": 0.6,
                    "evidence_refs": {"path": "blocked-login-sqli"},
                }
            ]
        },
    )

    assert artifacts.failed_paths() == {"blocked-login-sqli"}
    assert len(lessons) == 1
    assert lessons[0].evidence_refs.path == "blocked-login-sqli"


def test_persist_distilled_lessons_merges_near_duplicates(tmp_path: Path):
    store = ExperienceStore(tmp_path)
    first = persist_distilled_lessons(_artifacts("run-1"), _candidate, store, merge_threshold=0.6)
    second = persist_distilled_lessons(_artifacts("run-2"), _candidate, store, merge_threshold=0.6)

    assert len(first) == len(second) == 1
    pending = store.list_by_status("pending")
    assert len(pending) == 1
    assert pending[0].source_runs == ["run-1", "run-2"]
    assert pending[0].confidence > 0.7


def test_background_distillation_logs_and_swallows_errors(tmp_path: Path):
    class RunContext:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []
            self.status = "completed"

        def append_event(self, kind: str, payload: dict) -> None:
            self.events.append((kind, payload))

    context = RunContext()
    thread = schedule_run_distillation(
        artifacts=_artifacts(),
        llm=lambda _payload: (_ for _ in ()).throw(RuntimeError("unavailable")),
        store=ExperienceStore(tmp_path),
        run_context=context,
    )
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert thread.daemon is False
    assert context.status == "completed"
    assert context.events == [("distillation_failed", {"error": "RuntimeError"})]


def test_openai_strict_schema_requires_every_object_property():
    candidate = _LESSON_SCHEMA["properties"]["lessons"]["items"]

    assert set(candidate["properties"]) == set(candidate["required"])
    assert set(candidate["properties"]["tags"]["properties"]) == set(
        candidate["properties"]["tags"]["required"]
    )
    assert set(candidate["properties"]["evidence_refs"]["properties"]) == set(
        candidate["properties"]["evidence_refs"]["required"]
    )
