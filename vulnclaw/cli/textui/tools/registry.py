"""Tool registry — central lookup of available tools.

Mirrors the Claude Code ``assembleToolPool()`` pattern, allowing
the AgentLoop and commands to discover tools by name.
"""

from __future__ import annotations

from typing import Any

from vulnclaw.cli.textui.tools.base import BaseTool


class ToolRegistry:
    """Registry of all tools available to the Agent loop.

    Tools are registered by name and can be looked up by the
    AgentLoop when the LLM requests a tool call.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Build OpenAI-compatible tool definitions from all tools."""
        defs: list[dict[str, Any]] = []
        for tool in self._tools.values():
            defs.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            })
        return defs
