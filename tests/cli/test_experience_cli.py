from typer.testing import CliRunner

from vulnclaw.agent.experience import (
    ExperienceStore,
    Lesson,
    LessonEvidenceRefs,
    LessonScope,
    LessonSignal,
    LessonStatus,
)
from vulnclaw.kb.store import KnowledgeStore


def _lesson():
    return Lesson(
        scope=LessonScope.TECHNIQUE,
        signal=LessonSignal.SUCCESS,
        context="nginx target",
        lesson="Preserve the verified delimiter",
        evidence_refs=LessonEvidenceRefs(run_id="run-1", finding_id="f-1", path="/login"),
        source_runs=["run-1"],
    )


def test_experience_review_gate_commands(tmp_path):
    from vulnclaw.cli.main import app

    runner = CliRunner()
    store = ExperienceStore(store=KnowledgeStore(store_dir=tmp_path))
    lesson = _lesson()
    store.add(lesson)

    result = runner.invoke(app, ["experience", "list", "--store-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert lesson.id in result.output

    result = runner.invoke(app, ["experience", "show", lesson.id, "--store-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "run-1" in result.output
    assert "/login" in result.output

    result = runner.invoke(
        app,
        ["experience", "edit", lesson.id, "--lesson", "Updated guidance", "--store-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert ExperienceStore(store=KnowledgeStore(store_dir=tmp_path)).get(lesson.id).lesson == "Updated guidance"

    result = runner.invoke(app, ["experience", "approve", lesson.id, "--store-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert ExperienceStore(store=KnowledgeStore(store_dir=tmp_path)).get(lesson.id).status == LessonStatus.APPROVED

    result = runner.invoke(app, ["experience", "reject", "missing", "--store-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "missing" in result.output
