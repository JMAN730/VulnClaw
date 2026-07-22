"""Execution-boundary implementations for active tools."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from vulnclaw.config.domain_models import EvidenceRef
from vulnclaw.run_context import RunContext
from vulnclaw.targets import Target

from .docker_client import DockerCLIClient, DockerError, DockerUnavailableError
from .evidence import DEFAULT_MAX_FILE_BYTES, EvidenceBundleStore, _now_iso

logger = logging.getLogger(__name__)


class SandboxError(RuntimeError):
    """Execution could not be completed within the configured boundary."""


@dataclass(frozen=True)
class ExecResult:
    returncode: int
    stdout: str
    stderr: str
    bundle_ref: EvidenceRef | None
    timed_out: bool = False


@runtime_checkable
class ExecutionBoundary(Protocol):
    mode: str
    python_executable: str

    def run(
        self,
        argv: list[str],
        *,
        timeout: int,
        label: str,
        stdin_text: str | None = None,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> ExecResult: ...

    def close(self) -> None: ...


class LocalBoundary:
    """Explicit trusted-host execution preserving the legacy behavior."""

    mode = "trusted-local"
    python_executable = sys.executable or "python"

    def run(
        self,
        argv: list[str],
        *,
        timeout: int,
        label: str,
        stdin_text: str | None = None,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> ExecResult:
        del label
        run_env = None if env is None else {**os.environ, **env}
        try:
            result = subprocess.run(
                argv,
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=cwd,
                env=run_env,
            )
            return ExecResult(result.returncode, result.stdout, result.stderr, None)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            return ExecResult(124, stdout, stderr, None, timed_out=True)

    def close(self) -> None:
        return None


class DockerBoundary:
    mode = "docker"
    python_executable = "/usr/bin/python3"

    def __init__(
        self,
        *,
        run_context: RunContext,
        target: Target,
        image: str,
        network: str,
        client: DockerCLIClient | None = None,
        max_evidence_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        self._run_context = run_context
        self._target = target
        self._image = image
        self._network = network
        self._client = client or DockerCLIClient()
        self._evidence = EvidenceBundleStore(
            run_context, max_file_bytes=max_evidence_file_bytes
        )
        self._container: str | None = None
        self._lock = threading.RLock()

    @property
    def ingress_mode(self) -> str:
        return self._target.ingress_mode if self._target.kind == "local_repo" else "none"

    def run(
        self,
        argv: list[str],
        *,
        timeout: int,
        label: str,
        stdin_text: str | None = None,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> ExecResult:
        del cwd  # Docker commands always execute against the isolated /workspace.
        with self._lock:
            container = self._ensure_container()
            bundle_id, bundle_dir, bundle_ref = self._evidence.allocate(label)
            artifact_dir = f"/vulnclaw-artifacts/{bundle_id}"
            execution_env = {
                "PYTHONIOENCODING": "utf-8",
                "VULNCLAW_ARTIFACTS_DIR": artifact_dir,
                **dict(env or {}),
            }
            started_at = _now_iso()
            error = ""
            try:
                outcome = self._client.execute(
                    container,
                    argv,
                    timeout=timeout,
                    stdin_text=stdin_text,
                    env=execution_env,
                )
                try:
                    self._client.copy_artifacts(
                        container, artifact_dir, bundle_dir / "artifacts"
                    )
                except DockerError as exc:
                    error = str(exc)
                result = ExecResult(
                    outcome.returncode,
                    outcome.stdout,
                    outcome.stderr,
                    bundle_ref,
                    timed_out=outcome.timed_out,
                )
            except Exception as exc:
                error = str(exc)
                self._evidence.write(
                    bundle_dir,
                    label=label,
                    argv=argv,
                    ingress_mode=self.ingress_mode,
                    returncode=125,
                    stdout="",
                    stderr="",
                    timeout_hit=False,
                    started_at=started_at,
                    error=error,
                )
                raise SandboxError(f"Sandbox command failed: {exc}") from exc

            self._evidence.write(
                bundle_dir,
                label=label,
                argv=argv,
                ingress_mode=self.ingress_mode,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                timeout_hit=result.timed_out,
                started_at=started_at,
                error=error,
            )
            if result.timed_out:
                self._remove_container()
            return result

    def close(self) -> None:
        with self._lock:
            self._remove_container()

    def _ensure_container(self) -> str:
        if self._container:
            return self._container
        self._client.require_available()
        self._client.ensure_image(self._image)
        workspace = self._workspace()
        container = self._client.create_container(
            name=self._container_name(),
            image=self._image,
            network=self._network,
            workspace=workspace,
            ingress_mode=self._target.ingress_mode,
        )
        try:
            if workspace is not None and self._target.ingress_mode == "copy":
                self._client.copy_workspace(container, workspace)
        except Exception:
            try:
                self._client.remove_container(container)
            finally:
                raise
        self._container = container
        return container

    def _workspace(self) -> Path | None:
        if self._target.kind != "local_repo":
            return None
        workspace = Path(self._target.canonical).resolve()
        if not workspace.is_dir():
            raise SandboxError(f"Local target workspace does not exist: {workspace}")
        return workspace

    def _container_name(self) -> str:
        stem = re.sub(r"[^a-z0-9_.-]+", "-", self._run_context.run_name.lower()).strip("-.")
        digest = hashlib.sha256(self._target.target_id.encode("utf-8")).hexdigest()[:8]
        return f"vulnclaw-sandbox-{stem[:32]}-{digest}"[:63]

    def _remove_container(self) -> None:
        container = self._container
        if not container:
            return
        self._container = None
        try:
            self._client.remove_container(container)
        except Exception as exc:  # cleanup is best effort but never silent
            logger.warning("Failed to remove sandbox container %s: %s", container, exc)


__all__ = [
    "DockerBoundary",
    "DockerUnavailableError",
    "ExecResult",
    "ExecutionBoundary",
    "LocalBoundary",
    "SandboxError",
]
