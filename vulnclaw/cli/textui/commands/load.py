"""/load command — load chat history for a target."""

from __future__ import annotations


class LoadCommand:
    """Load chat history for a specific target."""

    async def run(self, args: str, **context) -> None:
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        target = args.strip()
        if not target:
            # Show available targets
            from vulnclaw.cli.textui.services.history import get_history_store
            store = get_history_store()
            targets = store.list_targets()

            if not targets:
                chat_pane.add_system_message("[dim]没有找到保存的历史记录[/]")
                return

            lines = [
                "[bold]可用的历史记录:[/]",
                "",
            ]
            for t, ts in targets:
                lines.append(f"  [cyan]{t}[/]  — {ts}")
            lines.append("")
            lines.append("[dim]使用 /load <目标> 加载对应的聊天记录[/]")
            chat_pane.add_system_message("\n".join(lines))
        else:
            chat_pane._load_history(target)
