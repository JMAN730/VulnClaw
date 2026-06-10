"""Command registry — register and dispatch slash commands.

Each slash command is a class implementing ``async run(args, context)``.
Registration mirrors the Claude Code pattern where each command
is a self-contained module.
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine


class CommandRegistry:
    """Central registry of slash commands.

    Usage::

        registry = CommandRegistry()
        registry.register("help", "显示帮助信息", help_cmd.run)

        # Later:
        await registry.dispatch("/help", chat_pane)
    """

    def __init__(self) -> None:
        self._commands: dict[str, _CommandEntry] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Register a slash command.

        Parameters
        ----------
        name:
            Command name without leading slash, e.g. ``"help"``.
        description:
            Short description shown in /help and autocomplete.
        handler:
            Async callable ``async def handler(args, chat_pane)``.
        """
        self._commands[name] = _CommandEntry(name, description, handler)

    async def dispatch(self, command_line: str, **context) -> str | None:
        """Parse and dispatch a slash command.

        Parameters
        ----------
        command_line:
            Full input including leading slash, e.g. ``"/help"`` or ``"/sc --target x"``.

        Returns
        -------
        The command name if found, None if unknown.
        """
        if not command_line.startswith("/"):
            return None

        parts = command_line[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        entry = self._commands.get(cmd_name)
        if entry is None:
            return None

        await entry.handler(args, **context)
        return cmd_name

    def list_commands(self) -> list[dict[str, str]]:
        """Return all registered commands (name + description)."""
        return [
            {"name": f"/{c.name}", "description": c.description}
            for c in self._commands.values()
        ]

    def complete(self, prefix: str) -> list[dict[str, str]]:
        """Return commands matching the given prefix (without leading slash)."""
        prefix_lower = prefix.lower()
        return [
            {"name": f"/{c.name}", "description": c.description}
            for c in self._commands.values()
            if c.name.startswith(prefix_lower)
        ]


class _CommandEntry:
    """Internal entry for a registered command."""

    __slots__ = ("name", "description", "handler")

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler
