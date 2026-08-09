"""Operator review commands for distilled lessons."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vulnclaw.agent.experience import ExperienceStore, Lesson, LessonStatus
from vulnclaw.cli._helpers import console, err_console

experience_app = typer.Typer(help="Review and gate distilled experience lessons")
_STORE_DIR = typer.Option(None, "--store-dir", help="Override the knowledge-base directory")


def _store(store_dir: Optional[Path]) -> ExperienceStore:
    return ExperienceStore(store_dir=store_dir)


def _required(store: ExperienceStore, lesson_id: str) -> Lesson:
    lesson = store.get(lesson_id)
    if lesson is None:
        err_console.print(f"[!] No lesson found with id: {lesson_id}")
        raise typer.Exit(1)
    return lesson


@experience_app.command("list")
def list_pending(store_dir: Optional[Path] = _STORE_DIR) -> None:
    """List pending lessons awaiting human review."""
    lessons = _store(store_dir).list_by_status(LessonStatus.PENDING)
    if not lessons:
        console.print("[yellow]No pending lessons.[/yellow]")
        return
    table = Table(title="Pending Lessons")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Scope")
    table.add_column("Signal")
    table.add_column("Lesson")
    table.add_column("Confidence", justify="right")
    for lesson in lessons:
        table.add_row(lesson.id, lesson.scope.value, lesson.signal.value, lesson.lesson[:100], f"{lesson.confidence:.2f}")
    console.print(table)


@experience_app.command("review")
def review(store_dir: Optional[Path] = _STORE_DIR) -> None:
    """Alias for ``experience list``."""
    list_pending(store_dir=store_dir)


@experience_app.command("show")
def show(
    lesson_id: str = typer.Argument(..., help="Lesson id"),
    store_dir: Optional[Path] = _STORE_DIR,
) -> None:
    """Show lesson text and provenance."""
    lesson = _required(_store(store_dir), lesson_id)
    body = Text()
    body.append(f"Status: {lesson.status.value}\n")
    body.append(f"Scope: {lesson.scope.value}\n")
    body.append(f"Signal: {lesson.signal.value}\n")
    body.append(f"Confidence: {lesson.confidence:.2f}\n")
    body.append(f"Created: {lesson.created_at}\n")
    body.append(f"Last reinforced: {lesson.last_reinforced_at or '(never)'}\n\n")
    body.append(f"Context:\n{lesson.context}\n\n")
    body.append(f"Lesson:\n{lesson.lesson}\n\n")
    body.append(
        "Tags: "
        + ", ".join(
            item for item in [
                f"tech={','.join(lesson.tags.tech)}" if lesson.tags.tech else "",
                f"vuln_type={lesson.tags.vuln_type}" if lesson.tags.vuln_type else "",
                f"waf={lesson.tags.waf}" if lesson.tags.waf else "",
                f"service={lesson.tags.service}" if lesson.tags.service else "",
            ]
            if item
        )
        + "\n\n",
    )
    evidence = lesson.evidence_refs
    body.append(
        f"Provenance:\n  run_id: {evidence.run_id}\n"
        f"  finding_id: {evidence.finding_id or '(none)'}\n"
        f"  path: {evidence.path or '(none)'}\n"
        f"  source_runs: {', '.join(lesson.source_runs) or '(none)'}\n"
    )
    console.print(Panel(body, title=f"Lesson {lesson.id}", expand=False))


@experience_app.command("approve")
def approve(lesson_id: str = typer.Argument(...), store_dir: Optional[Path] = _STORE_DIR) -> None:
    """Approve a lesson for future retrieval."""
    lesson = _required(_store(store_dir), lesson_id)
    ExperienceStore(store_dir=store_dir).approve(lesson.id)
    console.print(f"[+] Approved {lesson.id}")


@experience_app.command("reject")
def reject(lesson_id: str = typer.Argument(...), store_dir: Optional[Path] = _STORE_DIR) -> None:
    """Reject a lesson; rejected lessons remain auditable but inert."""
    lesson = _required(_store(store_dir), lesson_id)
    ExperienceStore(store_dir=store_dir).reject(lesson.id)
    console.print(f"[+] Rejected {lesson.id}")


@experience_app.command("edit")
def edit(
    lesson_id: str = typer.Argument(...),
    context: Optional[str] = typer.Option(None, "--context"),
    lesson_text: Optional[str] = typer.Option(None, "--lesson"),
    approve_after: bool = typer.Option(False, "--approve"),
    store_dir: Optional[Path] = _STORE_DIR,
) -> None:
    """Edit lesson text, optionally approving it in the same operation."""
    store = _store(store_dir)
    lesson = _required(store, lesson_id)
    if context is None and lesson_text is None:
        err_console.print("[!] Provide at least one of --context or --lesson")
        raise typer.Exit(1)
    if context is not None:
        lesson.context = context
    if lesson_text is not None:
        lesson.lesson = lesson_text
    store.add(lesson)
    if approve_after:
        store.approve(lesson.id)
    console.print(f"[+] Updated {lesson.id}")
