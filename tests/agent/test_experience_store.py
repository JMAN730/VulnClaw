"""Tests for the experience/lesson self-learning loop spine (ExperienceStore + Lesson)."""

from __future__ import annotations


def _make_lesson(**overrides):
    from vulnclaw.agent.experience import (
        Lesson,
        LessonEvidenceRefs,
        LessonScope,
        LessonSignal,
    )

    defaults = dict(
        scope=LessonScope.TECHNIQUE,
        signal=LessonSignal.SUCCESS,
        context="target runs nginx + php-fpm behind a WAF",
        lesson="URL-encode the payload twice to bypass the WAF's regex filter",
        evidence_refs=LessonEvidenceRefs(run_id="run-001", finding_id="find-1", path="/login"),
        confidence=0.5,
        source_runs=["run-001"],
    )
    defaults.update(overrides)
    return Lesson(**defaults)


class TestLessonSchema:
    def test_defaults(self):
        from vulnclaw.agent.experience import (
            Lesson,
            LessonEvidenceRefs,
            LessonScope,
            LessonSignal,
            LessonStatus,
        )

        lesson = Lesson(
            scope=LessonScope.TARGET,
            signal=LessonSignal.DEADEND,
            context="ctx",
            lesson="instruction",
            evidence_refs=LessonEvidenceRefs(run_id="run-1"),
        )
        assert lesson.id.startswith("exp-")
        assert lesson.status == LessonStatus.PENDING
        assert lesson.confidence == 0.0
        assert lesson.source_runs == []
        assert lesson.tags.tech == []
        assert lesson.tags.vuln_type == ""
        assert lesson.created_at

    def test_target_scope_allows_target_key(self):
        from vulnclaw.agent.experience import Lesson, LessonEvidenceRefs, LessonScope, LessonSignal

        lesson = Lesson(
            scope=LessonScope.TARGET,
            signal=LessonSignal.SUCCESS,
            context="ctx",
            lesson="instruction",
            evidence_refs=LessonEvidenceRefs(run_id="run-1"),
            target_key="acme-corp",
        )
        assert lesson.target_key == "acme-corp"

    def test_evidence_refs_provenance(self):
        lesson = _make_lesson()
        assert lesson.evidence_refs.run_id == "run-001"
        assert lesson.evidence_refs.finding_id == "find-1"
        assert lesson.evidence_refs.path == "/login"


class TestExperienceStoreLifecycle:
    def _make_store(self, tmp_path):
        from vulnclaw.agent.experience import ExperienceStore
        from vulnclaw.kb.store import KnowledgeStore

        return ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))

    def test_experience_category_dir_created(self, tmp_path):
        self._make_store(tmp_path)
        assert (tmp_path / "experience").exists()

    def test_add_creates_pending_lesson(self, tmp_path):
        from vulnclaw.agent.experience import LessonStatus

        store = self._make_store(tmp_path)
        lesson = _make_lesson()
        store.add(lesson)

        fetched = store.get(lesson.id)
        assert fetched is not None
        assert fetched.status == LessonStatus.PENDING

    def test_pending_not_in_approved_list(self, tmp_path):
        from vulnclaw.agent.experience import LessonStatus

        store = self._make_store(tmp_path)
        lesson = _make_lesson()
        store.add(lesson)

        assert store.list_by_status(LessonStatus.APPROVED) == []
        assert len(store.list_by_status(LessonStatus.PENDING)) == 1

    def test_approve_makes_lesson_retrievable_via_list(self, tmp_path):
        from vulnclaw.agent.experience import LessonStatus

        store = self._make_store(tmp_path)
        lesson = _make_lesson()
        store.add(lesson)

        approved = store.approve(lesson.id)
        assert approved is not None
        assert approved.status == LessonStatus.APPROVED

        approved_list = store.list_by_status(LessonStatus.APPROVED)
        assert len(approved_list) == 1
        assert approved_list[0].id == lesson.id

    def test_list_by_status_only_matching(self, tmp_path):
        from vulnclaw.agent.experience import LessonStatus

        store = self._make_store(tmp_path)
        l1 = _make_lesson()
        l2 = _make_lesson()
        l3 = _make_lesson()
        store.add(l1)
        store.add(l2)
        store.add(l3)

        store.approve(l1.id)
        store.reject(l2.id)
        # l3 stays pending

        approved = store.list_by_status(LessonStatus.APPROVED)
        rejected = store.list_by_status(LessonStatus.REJECTED)
        pending = store.list_by_status(LessonStatus.PENDING)

        assert [lesson.id for lesson in approved] == [l1.id]
        assert [lesson.id for lesson in rejected] == [l2.id]
        assert [lesson.id for lesson in pending] == [l3.id]

    def test_rejected_never_surfaces_as_approved(self, tmp_path):
        from vulnclaw.agent.experience import LessonStatus

        store = self._make_store(tmp_path)
        lesson = _make_lesson()
        store.add(lesson)
        store.reject(lesson.id)

        assert store.list_by_status(LessonStatus.APPROVED) == []
        fetched = store.get(lesson.id)
        assert fetched.status == LessonStatus.REJECTED

    def test_approve_reject_persist_across_reload(self, tmp_path):
        from vulnclaw.agent.experience import ExperienceStore, LessonStatus
        from vulnclaw.kb.store import KnowledgeStore

        store1 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        lesson = _make_lesson()
        store1.add(lesson)
        store1.approve(lesson.id)

        # Reload from disk with a brand new KnowledgeStore/ExperienceStore.
        store2 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        reloaded = store2.get(lesson.id)
        assert reloaded is not None
        assert reloaded.status == LessonStatus.APPROVED
        assert [approved_lesson.id for approved_lesson in store2.list_by_status(LessonStatus.APPROVED)] == [lesson.id]

    def test_get_nonexistent_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.get("exp-does-not-exist") is None

    def test_approve_nonexistent_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.approve("exp-does-not-exist") is None

    def test_reject_nonexistent_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.reject("exp-does-not-exist") is None

    def test_add_reloads_index_after_another_store_writes(self, tmp_path):
        from vulnclaw.agent.experience import ExperienceStore, LessonStatus
        from vulnclaw.kb.store import KnowledgeStore

        store1 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        store2 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        lesson1 = _make_lesson()
        lesson2 = _make_lesson()

        store1.add(lesson1)
        store2.add(lesson2)

        pending_ids = {lesson.id for lesson in store2.list_by_status(LessonStatus.PENDING)}
        assert pending_ids == {lesson1.id, lesson2.id}


class TestExperienceStoreMerge:
    def _make_store(self, tmp_path):
        from vulnclaw.agent.experience import ExperienceStore
        from vulnclaw.kb.store import KnowledgeStore

        return ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))

    def test_merge_folds_duplicate_no_second_entry(self, tmp_path):
        store = self._make_store(tmp_path)
        original = _make_lesson(confidence=0.5, source_runs=["run-001"])
        store.add(original)

        duplicate = _make_lesson(
            confidence=0.6,
            source_runs=["run-002"],
        )
        duplicate.evidence_refs.run_id = "run-002"

        merged = store.merge(duplicate, into_id=original.id)

        assert merged is not None
        assert merged.id == original.id
        # No second entry was created.
        assert store.get(duplicate.id) is None

    def test_merge_bumps_confidence(self, tmp_path):
        store = self._make_store(tmp_path)
        original = _make_lesson(confidence=0.5, source_runs=["run-001"])
        store.add(original)

        duplicate = _make_lesson(confidence=0.6, source_runs=["run-002"])
        merged = store.merge(duplicate, into_id=original.id)

        assert merged.confidence > 0.5

    def test_merge_appends_source_runs(self, tmp_path):
        store = self._make_store(tmp_path)
        original = _make_lesson(confidence=0.5, source_runs=["run-001"])
        store.add(original)

        duplicate = _make_lesson(confidence=0.6, source_runs=["run-002", "run-003"])
        duplicate.evidence_refs.run_id = "run-002"

        merged = store.merge(duplicate, into_id=original.id)

        assert "run-001" in merged.source_runs
        assert "run-002" in merged.source_runs
        assert "run-003" in merged.source_runs

    def test_merge_persists_to_disk(self, tmp_path):
        from vulnclaw.agent.experience import ExperienceStore
        from vulnclaw.kb.store import KnowledgeStore

        store1 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        original = _make_lesson(confidence=0.5, source_runs=["run-001"])
        store1.add(original)

        duplicate = _make_lesson(confidence=0.6, source_runs=["run-002"])
        store1.merge(duplicate, into_id=original.id)

        store2 = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
        reloaded = store2.get(original.id)
        assert reloaded.confidence > 0.5
        assert "run-002" in reloaded.source_runs

    def test_merge_into_nonexistent_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        duplicate = _make_lesson()
        assert store.merge(duplicate, into_id="exp-does-not-exist") is None
