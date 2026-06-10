"""/clear command — clear the chat message area."""

from __future__ import annotations


class ClearCommand:
    """Clear all messages from the chat pane."""

    async def run(self, args: str, **context) -> None:
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        chat_pane.clear_messages()
