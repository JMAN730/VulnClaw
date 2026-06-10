"""/help command — list all available slash commands."""

from __future__ import annotations

from vulnclaw.cli.textui.commands.registry import CommandRegistry


class HelpCommand:
    """Display usage information for slash commands."""

    def __init__(self, registry: CommandRegistry) -> None:
        self._registry = registry

    async def run(self, args: str, **context) -> None:
        """Show /help output."""
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        commands = self._registry.list_commands()

        lines = [
            "[bold]可用命令:[/]",
            "",
        ]
        for cmd in commands:
            lines.append(f"  [cyan]{cmd['name']}[/]  — {cmd['description']}")
        lines.append("")
        lines.append("[dim]提示: 在输入框中输入 / 可以自动补全命令[/]")

        chat_pane.add_system_message("\n".join(lines))
