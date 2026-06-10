"""/exit and /quit commands — exit the application."""

from __future__ import annotations


class ExitCommand:
    """Exit the TUI application."""

    async def run(self, args: str, **context) -> None:
        app = context.get("app")
        if app is not None:
            app.exit()
