"""/save command — force-save the current chat history."""

from __future__ import annotations


class SaveCommand:
    """Force-save the current chat history to disk."""

    async def run(self, args: str, **context) -> None:
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        chat_pane._save_current_history()
        chat_pane.add_system_message("[green]✓ 聊天记录已保存[/]")
