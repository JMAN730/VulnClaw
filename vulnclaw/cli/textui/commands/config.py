"""/config command — show current configuration."""

from __future__ import annotations


class ConfigCommand:
    """Display the current TUI configuration state."""

    async def run(self, args: str, **context) -> None:
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        state = context.get("state")
        if state is None:
            return

        lines = [
            "[bold]当前配置:[/]",
            "",
            f"  [cyan]目标:[/]     {state.target or '[dim]未设置[/]'}",
            f"  [cyan]模式:[/]     {state.mode}",
            f"  [cyan]仅允许主机:[/] {state.only_host or '—'}",
            f"  [cyan]仅允许端口:[/] {state.only_port or '—'}",
            f"  [cyan]仅允许路径:[/] {state.only_path or '—'}",
            f"  [cyan]禁止主机:[/]   {state.blocked_host or '—'}",
            f"  [cyan]禁止路径:[/]   {state.blocked_path or '—'}",
            f"  [cyan]允许操作:[/]   {', '.join(state.allow_actions) if state.allow_actions else '—'}",
            f"  [cyan]禁止操作:[/]   {', '.join(state.block_actions) if state.block_actions else '—'}",
        ]

        chat_pane.add_system_message("\n".join(lines))
