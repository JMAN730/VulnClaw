"""Secure execution-boundary public API."""

from .boundary import (
    DockerBoundary,
    ExecResult,
    ExecutionBoundary,
    LocalBoundary,
    SandboxError,
)
from .docker_client import DockerError, DockerImageError, DockerUnavailableError
from .runtime import create_execution_boundary, require_agent_boundary

__all__ = [
    "DockerBoundary",
    "DockerError",
    "DockerImageError",
    "DockerUnavailableError",
    "ExecResult",
    "ExecutionBoundary",
    "LocalBoundary",
    "SandboxError",
    "create_execution_boundary",
    "require_agent_boundary",
]
