"""Log panel widget with RichLog for streaming output."""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class LogPanel(Static):
    """Panel wrapping a RichLog for streaming LLM output display."""

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
        margin: 0 1;
    }
    """

    content: reactive[str] = reactive("", init=False)

    def __init__(self, title: str = "输出日志", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._lines: list[str] = []

    def on_mount(self) -> None:
        self._refresh()

    def write(self, text: str) -> None:
        """Append text to the log."""
        self._lines.append(text)
        self.content = "".join(self._lines[-200:])  # keep last 200 lines worth

    def clear(self) -> None:
        """Clear all log content."""
        self._lines.clear()
        self.content = ""
        self._refresh()

    def watch_content(self, value: str) -> None:
        self._refresh()

    def _refresh(self) -> None:
        display = self.content[-5000:] if len(self.content) > 5000 else self.content
        panel = Panel(
            Text(display or "等待输出...", style="dim" if not display else "default"),
            title=self._title,
            border_style="green",
            highlight=True,
        )
        self.update(panel)
