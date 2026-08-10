"""Regression tests for distillation, retrieval, feedback, and decay."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from vulnclaw.agent.experience import (
    ExperienceStore,
    Lesson,
    LessonEvidenceRefs,
    LessonScope,
    LessonSignal,
    LessonStatus,
    LessonTags,
    TargetContext,
    build_experience_context,
)
from vulnclaw.agent.experience.distiller import RunArtifacts, distill_run, token_similarity
from vulnclaw.agent.experience.feedback import save_feedback
from vulnclaw.agent.kb_context import build_prompt_kb_and_experience_context
from vulnclaw.kb.store import KnowledgeStore
from vulnclaw.run_context import create_run_context
from vulnclaw.targets import build_targets


def _lesson(**overrides):
    values = dict(
        scope=LessonScope.TECHNIQUE,
        signal=LessonSignal.SUCCESS,
        tags=LessonTags(tech=["nginx"], vuln_type="sqli", service="http"),
        context="nginx http target with SQL injection",
        lesson="Use the verified parameter and preserve the encoded delimiter.",
        evidence_refs=LessonEvidenceRefs(run_id="run-1", finding_id="f-1", path="/login"),
        confidence=0.8,
        source_runs=["run-1"],
    )
    values.update(overrides)
    return Lesson(**values)


class _FakeLLM:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def generate_lessons(self, payload):
        self.calls.append(payload)
        return self.candidates


def test_distiller_makes_one_call_and_drops_unbacked_candidates(tmp_path):
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    llm = _FakeLLM([
        {
            "scope": "technique",
            "signal": "success",
            "context": "nginx SQL injection",
            "lesson": "Keep the verified parameter stable.",
            "tags": {"tech": ["nginx"], "vuln_type": "sqli", "service": "http"},
            "confidence": 0.7,
            "evidence": {"finding_id": "f-1"},
        },
        {
            "scope": "technique",
            "signal": "success",
            "context": "invented",
            "lesson": "This has no run evidence.",
            "evidence": {"finding_id": "not-from-run"},
        },
    ])
    artifacts = RunArtifacts(
        run_id="run-1",
        target="https://example.com",
        verified_findings=[{"id": "f-1", "endpoint": "/login", "vuln_type": "sqli"}],
    )

    written = distill_run(artifacts, llm, store=store)

    assert len(llm.calls) == 1
    assert len(written) == 1
    assert written[0].status == LessonStatus.PENDING
    assert written[0].evidence_refs.finding_id == "f-1"
    assert len(store.list_by_status(LessonStatus.PENDING)) == 1


def test_distiller_consumes_feedback_and_merges_duplicate(tmp_path):
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    existing = _lesson()
    store.add(existing)
    llm = _FakeLLM([
        {
            "scope": "technique",
            "signal": "success",
            "context": existing.context,
            "lesson": existing.lesson,
            "tags": existing.tags.model_dump(),
            "confidence": 0.5,
            "evidence": {"finding_id": "f-1"},
        }
    ])
    artifacts = RunArtifacts(
        run_id="run-2",
        verified_findings=[{"id": "f-1", "endpoint": "/login"}],
        operator_feedback={"rating": 5, "notes": "The tactic was correct."},
    )

    written = distill_run(artifacts, llm, store=store, similarity_threshold=0.99)

    assert llm.calls[0]["operator_feedback"]["rating"] == 5
    assert written[0].id == existing.id
    assert "run-2" in written[0].source_runs
    assert written[0].last_reinforced_at
    assert len(store.list_by_status(LessonStatus.PENDING)) == 1


def test_merge_threshold_boundary_is_configurable(tmp_path):
    left = _lesson()
    right = _lesson(lesson="Use another verified parameter and preserve the delimiter.")
    score = token_similarity(left, right)
    assert 0.0 < score < 1.0

    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    store.add(left)
    artifacts = RunArtifacts(run_id="run-2", verified_findings=[{"id": "f-1"}])
    candidate = {
        "scope": "technique", "signal": "success", "context": right.context,
        "lesson": right.lesson, "tags": right.tags.model_dump(), "confidence": 0.5,
        "evidence": {"finding_id": "f-1"},
    }

    assert len(distill_run(artifacts, _FakeLLM([candidate]), store=store, similarity_threshold=score - 0.01)) == 1
    assert len(distill_run(RunArtifacts(run_id="run-3", verified_findings=[{"id": "f-1"}]), _FakeLLM([candidate]), store=store, similarity_threshold=1.0)) == 1


def test_effective_confidence_decays_and_merge_reinforces(tmp_path):
    old = _lesson(created_at=(datetime.now(timezone.utc) - timedelta(days=30)).isoformat())
    assert 0.39 < old.effective_confidence() < 0.41
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    store.add(old)
    merged = store.merge(_lesson(source_runs=["run-2"]), into_id=old.id)
    assert merged.last_reinforced_at
    assert merged.effective_confidence() > 0.8


def test_retrieval_only_injects_matching_approved_lessons(tmp_path):
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    pending = _lesson(lesson="pending secret")
    rejected = _lesson(lesson="rejected secret")
    approved = _lesson(lesson="approved SQL injection guidance")
    store.add(pending)
    store.add(rejected)
    store.add(approved)
    store.reject(rejected.id)
    store.approve(approved.id)

    context = build_experience_context(
        TargetContext(services=["http/80"], tech=["nginx"], vuln_types=["sqli"]),
        store,
    )

    assert "## Prior Experience / Lessons" in context
    assert "approved SQL injection guidance" in context
    assert "pending secret" not in context
    assert "rejected secret" not in context


def test_experience_path_is_not_suppressed_by_english_kb_gate(tmp_path, monkeypatch):
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    lesson = _lesson()
    store.add(lesson)
    store.approve(lesson.id)
    state = SimpleNamespace(
        recon_data={"services": ["http/80"], "technologies": ["nginx"], "waf": ""},
        findings=[],
        target="https://example.com",
    )
    agent = SimpleNamespace(context=SimpleNamespace(state=state), _experience_store=store)
    monkeypatch.setattr("vulnclaw.agent.kb_context.current_lang", lambda: "en")

    context = build_prompt_kb_and_experience_context(agent, "sqli")

    assert "approved" not in context  # lesson text in this fixture is different
    assert "Use the verified parameter" in context


def test_feedback_upserts_run_record(tmp_path):
    context = create_run_context(
        command="run", targets=build_targets("https://example.com"), runs_dir=tmp_path, run_name="feedback-run"
    )
    first = save_feedback(context, rating=2, notes="needs work")
    second = save_feedback(context, rating=5, notes="now verified")

    assert first["rating"] == 2
    assert second["rating"] == 5
    assert (context.run_dir / "feedback.json").exists()


def test_run_artifacts_fall_back_to_verified_checkpoint_findings(tmp_path):
    run_dir = tmp_path / "run-with-checkpoint-findings"
    state_dir = run_dir / "targets" / "target-1" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "current.json").write_text(
        json.dumps(
            {
                "target": "https://example.com",
                "findings": [
                    {
                        "finding_id": "f-1",
                        "verification_status": "verified",
                        "verified": True,
                    },
                    {
                        "finding_id": "f-2",
                        "verification_status": "pending",
                        "verified": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    artifacts = RunArtifacts.from_run_dir(run_dir)

    assert artifacts.verified_findings == [
        {
            "finding_id": "f-1",
            "verification_status": "verified",
            "verified": True,
        }
    ]
