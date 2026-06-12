"""VulnClaw Textual application entry point."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.screen import Screen

from vulnclaw import __version__


class VulnClawApp(App):
    """Main Textual application for VulnClaw TUI."""

    TITLE = f"VulnClaw v{__version__}"
    SUB_TITLE = "AI-powered penetration testing CLI"

    SCREENS: dict[str, Screen] = {}

    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出", priority=True),
        Binding("ctrl+c", "request_shutdown", "强制退出", priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._initial_target: str = ""
        self._initial_mode: str = "standard"
        self._initial_state: dict = {}

    def set_initial_state(
        self,
        target: str = "",
        mode: str = "standard",
        **extra,
    ) -> None:
        """Store CLI-provided initial state for use after mount."""
        self._initial_target = target
        self._initial_mode = mode
        self._initial_state = extra

    def on_mount(self) -> None:
        """Initialize the app and push the main screen."""
        from vulnclaw.cli.textui.screens.main import MainScreen

        self.push_screen(MainScreen())


def run_textual_app(
    target: str = "",
    mode: str = "standard",
    **extra,
) -> None:
    """Run the Textual TUI application."""
    app = VulnClawApp()
    app.set_initial_state(target=target, mode=mode, **extra)
    app.run()
