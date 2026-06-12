"""Tool implementations for the TUI Agent loop.

Each tool wraps an external capability (bash, file read, etc.)
following the BaseTool interface for use in the Agent ReAct loop.
"""

from vulnclaw.cli.textui.tools.base import BaseTool, ToolResult, ToolStatus
from vulnclaw.cli.textui.tools.registry import ToolRegistry

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "ToolStatus",
]
