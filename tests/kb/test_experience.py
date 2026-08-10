"""Regression tests for human-gated cross-run lessons."""

from datetime import datetime, timedelta, timezone

import pytest

from vulnclaw.kb.experience import (
    CONFIDENCE_HALF_LIFE_ENV,
    DEFAULT_CONFIDENCE_HALF_LIFE_DAYS,
    EvidenceRefs,
    ExperienceStore,
    Lesson,
    LessonScope,
    LessonSignal,
    LessonStatus,
    LessonTags,
    default_confidence_half_life_days,
)


def make_lesson(lesson_id: str, *, confidence: float = 0.5, run_id: str = "run-1") -> Lesson:
    return Lesson(
        id=lesson_id,
        scope=LessonScope.TECHNIQUE,
        signal=LessonSignal.SUCCESS,
        tags=LessonTags(tech=["sqli"], vuln_type="sql-injection", service="http"),
        context="An HTTP form parameter produces a SQL syntax error.",
        lesson="Prioritize parameterized-query verification before payload variation.",
        evidence_refs=EvidenceRefs(run_id=run_id, finding_id="finding-1", path="/login"),
        confidence=confidence,
    )


def test_create_approve_list_lifecycle_is_durable(tmp_path):
    store = ExperienceStore(tmp_path)
    pending = store.add(make_lesson("lesson-1"))

    assert pending.status is LessonStatus.PENDING
    assert store.list_by_status("pending") == [pending]
    assert store.list_by_status("approved") == []

    approved = store.approve(pending.id)
    assert approved is not None and approved.status is LessonStatus.APPROVED
    assert [lesson.id for lesson in store.list_by_status(LessonStatus.APPROVED)] == [pending.id]
    assert ExperienceStore(tmp_path).get(pending.id) == approved


def test_rejected_lessons_never_surface_as_approved(tmp_path):
    store = ExperienceStore(tmp_path)
    pending = store.add(make_lesson("lesson-2"))

    rejected = store.reject(pending.id)
    assert rejected is not None and rejected.status is LessonStatus.REJECTED
    assert store.list_by_status("approved") == []
    assert store.list_by_status("rejected") == [rejected]


def test_merge_reinforces_existing_lesson_without_second_entry(tmp_path):
    store = ExperienceStore(tmp_path)
    existing = store.add(make_lesson("lesson-3", confidence=0.5, run_id="run-1"))
    duplicate = make_lesson("candidate-3", confidence=0.5, run_id="run-2")

    merged = store.merge(existing.id, duplicate)

    assert merged is not None
    assert merged.id == existing.id
    assert merged.confidence > existing.confidence
    assert merged.source_runs == ["run-1", "run-2"]
    assert sorted(path.stem for path in (tmp_path / "experience").glob("*.json")) == [existing.id]


def test_add_forces_pending_and_target_scope_requires_target_key(tmp_path):
    store = ExperienceStore(tmp_path)
    approved = make_lesson("lesson-4").model_copy(update={"status": LessonStatus.APPROVED})

    assert store.add(approved).status is LessonStatus.PENDING


def test_confidence_decays_without_deleting_and_merge_refreshes_it(tmp_path):
    store = ExperienceStore(tmp_path, confidence_half_life_days=10)
    stale = make_lesson("lesson-decay", confidence=0.8, run_id="run-1").model_copy(
        update={"reinforced_at": datetime.now(timezone.utc) - timedelta(days=10)}
    )
    store.add(stale)

    assert store.get(stale.id) is not None
    assert 0.39 < store.effective_confidence(stale) < 0.41

    refreshed = store.merge(stale.id, make_lesson("candidate-decay", run_id="run-2"))

    assert refreshed is not None
    assert refreshed.reinforced_at > stale.reinforced_at
    assert store.effective_confidence(refreshed) > store.effective_confidence(stale)


def test_decay_reweights_without_mutating_or_deleting_stored_lessons(tmp_path):
    store = ExperienceStore(tmp_path, confidence_half_life_days=10)
    reference = datetime(2026, 1, 31, tzinfo=timezone.utc)
    lesson = make_lesson("lesson-immutable", confidence=0.8).model_copy(
        update={"reinforced_at": reference - timedelta(days=30)}
    )
    store.add(lesson)

    # Three half-lives at an injected reference time: 0.8 -> 0.1.
    assert store.effective_confidence(lesson, now=reference) == pytest.approx(0.1)
    # A reference time before the anchor never inflates the weight.
    assert store.effective_confidence(lesson, now=reference - timedelta(days=60)) == 0.8

    stored = store.get(lesson.id)
    assert stored is not None
    assert stored.confidence == 0.8
    assert stored.status is LessonStatus.PENDING
    assert store.list_by_status("pending") == [stored]


def test_confidence_half_life_is_environment_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv(CONFIDENCE_HALF_LIFE_ENV, "5")
    assert default_confidence_half_life_days() == 5.0
    assert ExperienceStore(tmp_path).confidence_half_life_days == 5.0

    for invalid in ("nonsense", "0", "-3", "   "):
        monkeypatch.setenv(CONFIDENCE_HALF_LIFE_ENV, invalid)
        assert default_confidence_half_life_days() == DEFAULT_CONFIDENCE_HALF_LIFE_DAYS

    monkeypatch.delenv(CONFIDENCE_HALF_LIFE_ENV)
    assert ExperienceStore(tmp_path).confidence_half_life_days == DEFAULT_CONFIDENCE_HALF_LIFE_DAYS

    with pytest.raises(ValueError):
        ExperienceStore(tmp_path, confidence_half_life_days=0)


def test_merge_threshold_respects_boundary_cases(tmp_path):
    store = ExperienceStore(tmp_path)
    existing = Lesson(
        id="threshold-existing",
        scope=LessonScope.TECHNIQUE,
        signal=LessonSignal.SUCCESS,
        tags=LessonTags(),
        context="alpha beta",
        lesson="gamma delta",
        evidence_refs=EvidenceRefs(run_id="run-1"),
        confidence=0.5,
    )
    candidate = existing.model_copy(
        update={
            "id": "threshold-candidate",
            "lesson": "gamma epsilon",
            "evidence_refs": EvidenceRefs(run_id="run-2"),
        }
    )
    store.add(existing)

    # Token overlap here is exactly 0.6 (3 shared of 5 distinct terms).
    assert store.find_near_duplicate(candidate, threshold=0.59) is not None
    assert store.find_near_duplicate(candidate, threshold=0.60) is not None
    assert store.find_near_duplicate(candidate, threshold=0.61) is None


def test_only_pending_lessons_are_eligible_for_candidate_merges(tmp_path):
    store = ExperienceStore(tmp_path)
    candidate = make_lesson("candidate", run_id="run-2")
    approved = store.add(make_lesson("approved", run_id="run-1"))
    store.approve(approved.id)
    rejected = store.add(make_lesson("rejected", run_id="run-3"))
    store.reject(rejected.id)

    assert store.find_near_duplicate(candidate, threshold=0.8) is None
