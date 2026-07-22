"""Durable, bounded evidence bundles for sandbox executions."""

from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from vulnclaw.config.domain_models import EvidenceRef
from vulnclaw.run_context import RunContext, atomic_write_json, atomic_write_text

DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_label(label: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
    return (value or "command")[:48]


def _truncate_text(text: str, limit: int) -> tuple[str, bool]:
    raw = text.encode("utf-8", "replace")
    if len(raw) <= limit:
        return text, False
    clipped = raw[:limit].decode("utf-8", "ignore")
    return clipped, True


class EvidenceBundleStore:
    """Allocate deterministic bundle ids and persist execution results."""

    def __init__(self, run_context: RunContext, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES):
        self._run_context = run_context
        self._max_file_bytes = max(1, int(max_file_bytes))
        self._counter = 0
        self._lock = threading.Lock()

    def allocate(self, label: str) -> tuple[str, Path, EvidenceRef]:
        with self._lock:
            self._counter += 1
            bundle_id = f"{_safe_label(label)}-{self._counter:04d}"
            bundle_dir = self._run_context.evidence_dir("sandbox", bundle_id)
        (bundle_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        return (
            bundle_id,
            bundle_dir,
            EvidenceRef(kind="sandbox_output", path=f"sandbox/{bundle_id}"),
        )

    def write(
        self,
        bundle_dir: Path,
        *,
        label: str,
        argv: list[str],
        ingress_mode: str,
        returncode: int,
        stdout: str,
        stderr: str,
        timeout_hit: bool,
        started_at: str,
        error: str = "",
    ) -> None:
        stdout_value, stdout_truncated = _truncate_text(stdout, self._max_file_bytes)
        stderr_value, stderr_truncated = _truncate_text(stderr, self._max_file_bytes)
        artifact_truncations = self._bound_artifacts(bundle_dir / "artifacts")
        atomic_write_text(bundle_dir / "stdout.txt", stdout_value)
        atomic_write_text(bundle_dir / "stderr.txt", stderr_value)
        atomic_write_json(
            bundle_dir / "meta.json",
            {
                "label": label,
                "argv": argv,
                "ingress_mode": ingress_mode,
                "exit_code": returncode,
                "started_at": started_at,
                "ended_at": _now_iso(),
                "timeout_hit": timeout_hit,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "artifact_truncations": artifact_truncations,
                "error": error,
            },
        )

    def _bound_artifacts(self, root: Path) -> list[str]:
        truncated: list[str] = []
        if not root.exists():
            return truncated
        for current_root, dirs, files in os.walk(root, followlinks=False):
            current = Path(current_root)
            for name in list(dirs):
                path = current / name
                if path.is_symlink():
                    path.unlink(missing_ok=True)
                    dirs.remove(name)
            for name in files:
                path = current / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    path.unlink(missing_ok=True)
                    truncated.append(f"{relative}:symlink-removed")
                    continue
                if path.stat().st_size > self._max_file_bytes:
                    with path.open("r+b") as handle:
                        handle.truncate(self._max_file_bytes)
                    truncated.append(relative)
        return truncated


__all__ = ["DEFAULT_MAX_FILE_BYTES", "EvidenceBundleStore", "_now_iso"]
