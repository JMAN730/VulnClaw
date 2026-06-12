"""Base tool interface for the Agent loop.

Every tool (bash, file read, etc.) implements this interface
so the AgentLoop can discover, invoke, and render tool calls uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"


@dataclass
class ToolResult:
    """Result returned by a tool after execution."""

    status: ToolStatus
    output: str = ""
    error: str = ""
    duration_s: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract tool that the AgentLoop can invoke.

    Subclasses define:
    - name / description: displayed in UI tool calls
    - input_schema: Zod-like dict for parameter validation
    - run(inputs) -> ToolResult: actual execution
    """

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}

    @abstractmethod
    async def run(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given inputs."""

    def format_params(self, inputs: dict[str, Any]) -> str:
        """Format parameters for display in the ToolCallMessage header."""
        parts = []
        for key, value in inputs.items():
            parts.append(f"{key}={value}")
        return ", ".join(parts)
