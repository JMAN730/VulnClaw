"""Per-run boundary construction and agent lookup helpers."""

from __future__ import annotations

from typing import Any

from vulnclaw.run_context import RunContext
from vulnclaw.targets import Target

from .boundary import DockerBoundary, ExecutionBoundary, LocalBoundary, SandboxError


def create_execution_boundary(
    *,
    config: Any,
    run_context: RunContext | None,
    target: Target,
    trusted_local: bool = False,
) -> ExecutionBoundary:
    safety = getattr(config, "safety", None)
    configured_mode = str(getattr(safety, "sandbox_mode", "docker"))
    mode = "trusted-local" if trusted_local else configured_mode
    if mode == "trusted-local":
        return LocalBoundary()
    if mode != "docker":
        raise SandboxError(f"Unsupported sandbox mode: {mode!r}")
    if run_context is None:
        raise SandboxError(
            "Docker sandbox execution requires a run directory for evidence; "
            "use --trusted-local only for an explicitly trusted host run"
        )
    return DockerBoundary(
        run_context=run_context,
        target=target,
        image=str(getattr(safety, "sandbox_image", "vulnclaw/sandbox:0.3.3")),
        network=str(getattr(safety, "sandbox_network", "none")),
        max_evidence_file_bytes=int(
            getattr(safety, "sandbox_max_evidence_file_bytes", 10 * 1024 * 1024)
        ),
    )


def require_agent_boundary(agent: Any) -> ExecutionBoundary:
    boundary = getattr(agent, "execution_boundary", None)
    if boundary is not None:
        return boundary
    mode = str(getattr(getattr(agent.config, "safety", None), "sandbox_mode", "docker"))
    if mode == "trusted-local":
        # Direct helper calls outside the orchestrator remain possible only when
        # the host boundary was explicitly selected in configuration.
        return LocalBoundary()
    raise SandboxError(
        "Docker sandbox boundary is not initialized. Run active tools through "
        "the orchestrator, or explicitly select --trusted-local for host execution."
    )


__all__ = ["create_execution_boundary", "require_agent_boundary"]
