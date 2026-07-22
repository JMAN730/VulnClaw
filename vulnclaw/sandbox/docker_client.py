"""Small, injection-friendly adapter around the Docker CLI."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class DockerError(RuntimeError):
    """Base Docker boundary failure."""


class DockerUnavailableError(DockerError):
    """Docker CLI or daemon is unavailable."""


class DockerImageError(DockerError):
    """The configured sandbox image could not be resolved or built."""


@dataclass(frozen=True)
class DockerExecResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class DockerCLIClient:
    def __init__(self, *, dockerfile: Path | None = None) -> None:
        self._dockerfile = dockerfile or Path(__file__).with_name("Dockerfile")

    def require_available(self) -> None:
        try:
            result = self._run(
                ["docker", "version", "--format", "{{.Server.Version}}"], timeout=15
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DockerUnavailableError(self._unavailable_message()) from exc
        if result.returncode != 0:
            raise DockerUnavailableError(self._unavailable_message(result.stderr))

    def ensure_image(self, image: str) -> None:
        inspected = self._run(["docker", "image", "inspect", image], timeout=30)
        if inspected.returncode == 0:
            return
        if "@sha256:" in image:
            raise DockerImageError(
                f"Sandbox image {image!r} is unavailable. Pull the pinned image before running."
            )
        built = self._run(
            [
                "docker",
                "build",
                "--tag",
                image,
                "--file",
                str(self._dockerfile),
                str(self._dockerfile.parent),
            ],
            timeout=600,
        )
        if built.returncode != 0:
            raise DockerImageError(
                f"Failed to build sandbox image {image!r}: {built.stderr.strip()[:1000]}"
            )

    def create_container(
        self,
        *,
        name: str,
        image: str,
        network: str,
        workspace: Path | None,
        ingress_mode: str,
    ) -> str:
        command = [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--network",
            network,
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=256",
            "--memory=512m",
            "--cpus=1",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--tmpfs",
            "/vulnclaw-artifacts:rw,nosuid,nodev,noexec,size=64m,mode=1777",
        ]
        if workspace is not None and ingress_mode == "mount":
            command.extend(
                ["--mount", f"type=bind,src={workspace},dst=/workspace,readonly"]
            )
        else:
            command.extend(
                ["--tmpfs", "/workspace:rw,nosuid,nodev,noexec,size=512m,mode=1777"]
            )
        command.append(image)
        result = self._run(command, timeout=120)
        if result.returncode != 0:
            raise DockerError(f"Failed to create sandbox container: {result.stderr.strip()[:1000]}")
        return result.stdout.strip()

    def copy_workspace(self, container: str, workspace: Path) -> None:
        source = str(workspace) + os.sep + "."
        result = self._run(["docker", "cp", source, f"{container}:/workspace"], timeout=300)
        if result.returncode != 0:
            raise DockerError(f"Failed to copy target into /workspace: {result.stderr.strip()[:1000]}")

    def execute(
        self,
        container: str,
        argv: list[str],
        *,
        timeout: int,
        stdin_text: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> DockerExecResult:
        command = ["docker", "exec", "--interactive", "--workdir", "/workspace"]
        for key, value in (env or {}).items():
            command.extend(["--env", f"{key}={value}"])
        command.extend([container, *argv])
        try:
            result = self._run(command, timeout=timeout, input_text=stdin_text)
            return DockerExecResult(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as exc:
            return DockerExecResult(
                124,
                self._decode_timeout_value(exc.stdout),
                self._decode_timeout_value(exc.stderr),
                timed_out=True,
            )

    def copy_artifacts(self, container: str, source: str, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        result = self._run(
            ["docker", "cp", f"{container}:{source}/.", str(destination)], timeout=120
        )
        # docker cp returns non-zero when a command produced no artifact directory.
        if result.returncode != 0 and "does not exist" not in result.stderr.lower():
            raise DockerError(f"Failed to copy sandbox artifacts: {result.stderr.strip()[:1000]}")

    def remove_container(self, container: str) -> None:
        result = self._run(["docker", "rm", "--force", container], timeout=30)
        if result.returncode != 0 and "no such container" not in result.stderr.lower():
            raise DockerError(f"Failed to remove sandbox container: {result.stderr.strip()[:1000]}")

    @staticmethod
    def _decode_timeout_value(value: str | bytes | None) -> str:
        if value is None:
            return ""
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else value

    @staticmethod
    def _unavailable_message(detail: str = "") -> str:
        suffix = f" ({detail.strip()[:500]})" if detail.strip() else ""
        return (
            "Docker is required for the sandbox execution boundary but is unavailable. "
            "Start Docker, or explicitly re-run with --trusted-local to execute on the host."
            f"{suffix}"
        )

    @staticmethod
    def _run(
        command: list[str],
        *,
        timeout: int,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **kwargs,
        )


__all__ = [
    "DockerCLIClient",
    "DockerError",
    "DockerExecResult",
    "DockerImageError",
    "DockerUnavailableError",
]
