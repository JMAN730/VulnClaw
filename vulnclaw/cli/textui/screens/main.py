"""Main screen — single chat interface with command dispatch.

Architecture (Claude Code inspired)::

    MainScreen (Screen)
    └── ChatPane (Vertical)
        ├── #chat-messages (VerticalScroll)
        │   ├── UserMessage | AssistantText | ToolCallMessage | SystemMessage
        │   └── ...
        └── ChatInput (docked bottom)
            ├── #chat-input-field (Input)
            └── #chat-completions (ListView, shown on /)
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from vulnclaw.cli.textui.components.chat_pane import ChatPane
from vulnclaw.cli.textui.components.chat_input import ChatInput
from vulnclaw.cli.textui.commands.registry import CommandRegistry
from vulnclaw.cli.textui.commands.help import HelpCommand
from vulnclaw.cli.textui.commands.sc import ScanConfigCommand
from vulnclaw.cli.textui.commands.config import ConfigCommand
from vulnclaw.cli.textui.commands.clear import ClearCommand
from vulnclaw.cli.textui.commands.load import LoadCommand
from vulnclaw.cli.textui.commands.save import SaveCommand
from vulnclaw.cli.textui.commands.exit_cmd import ExitCommand
from vulnclaw.cli.textui.utils.state import TuiStateWrapper
from vulnclaw.cli.textui.services.history import get_history_store


class MainScreen(Screen):
    """Main screen — single chat interface with command dispatch."""

    BINDINGS = [
        Binding("ctrl+c", "interrupt_or_quit", "中断/退出", priority=True),
        Binding("q", "quit", "退出"),
        Binding("ctrl+l", "focus_input", "聚焦输入"),
    ]

    DEFAULT_CSS = """
    MainScreen {
        background: $surface;
    }

    #main-container {
        height: 1fr;
    }

    #hint-bar {
        height: 1;
        padding: 0 1;
        text-align: left;
        color: $text-muted;
        dock: bottom;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._state = TuiStateWrapper()
        self._cmd_registry = CommandRegistry()
        self._chat_pane: ChatPane | None = None
        self._last_ctrl_c: float = 0.0  # for double-press-to-quit detection

        # Register all slash commands
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all slash commands in the registry."""
        help_cmd = HelpCommand(self._cmd_registry)
        sc_cmd = ScanConfigCommand()
        config_cmd = ConfigCommand()
        clear_cmd = ClearCommand()
        load_cmd = LoadCommand()
        save_cmd = SaveCommand()
        exit_cmd = ExitCommand()

        self._cmd_registry.register("help", "显示帮助信息", help_cmd.run)
        self._cmd_registry.register("sc", "打开扫描配置面板", sc_cmd.run)
        self._cmd_registry.register("config", "查看当前配置", config_cmd.run)
        self._cmd_registry.register("clear", "清除聊天记录", clear_cmd.run)
        self._cmd_registry.register("load", "加载聊天记录", load_cmd.run)
        self._cmd_registry.register("save", "保存聊天记录", save_cmd.run)
        self._cmd_registry.register("exit", "退出程序", exit_cmd.run)
        self._cmd_registry.register("quit", "退出程序", exit_cmd.run)

    def compose(self) -> ComposeResult:
        """Compose the main screen."""
        with Vertical(id="main-container"):
            yield ChatPane(
                self._state,
                self._cmd_registry,
                id="chat-pane",
            )
        yield Static(
            "  [dim]输入 / 查看命令  |  Tab 补全  |  Ctrl+C 退出  |  /help 查看帮助[/]",
            id="hint-bar",
        )

    def on_mount(self) -> None:
        """Focus chat input and load history on mount."""
        self._chat_pane = self.query_one("#chat-pane", ChatPane)

        # Focus input
        chat_input = self.query_one("#chat-input", ChatInput)
        chat_input.focus_input()

        # Show welcome message
        self._chat_pane.add_system_message(
            "[dim]欢迎使用 VulnClaw! 输入 /help 查看可用命令[/]"
        )

        # Load history for current target if set
        if self._state.target:
            self._chat_pane._load_history(self._state.target)

    def action_interrupt_or_quit(self) -> None:
        """Ctrl+C: interrupt if busy, otherwise double-press to quit."""
        try:
            chat_pane = self.query_one("#chat-pane", ChatPane)
        except Exception:
            chat_pane = None

        if chat_pane is not None and chat_pane.is_busy:
            chat_pane.cancel_current()
            self.notify("操作已中断", timeout=2)
            return

        # Idle — require double Ctrl+C within 3 seconds
        now = time.monotonic()
        if now - self._last_ctrl_c < 3.0:
            self.app.exit()
        else:
            self._last_ctrl_c = now
            self.notify("再按一次 Ctrl+C 退出程序", timeout=3)

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_focus_input(self) -> None:
        """Focus the chat input (Ctrl+L)."""
        try:
            inp = self.query_one("#chat-input", ChatInput)
            inp.focus_input()
        except Exception:
            pass

    def on_chat_pane_execute_request(self, event: ChatPane.ExecuteRequest) -> None:
        """Handle execution request from chat pane."""
        self._state.update_from_dict(event.config)
        self._chat_pane.add_system_message("[green]✓ 任务已启动[/]")
        self.app.notify("任务已启动", timeout=3)

    def on_chat_pane_load_history_request(self, event: ChatPane.LoadHistoryRequest) -> None:
        """Handle history load request."""
        if self._chat_pane:
            self._chat_pane._load_history(event.target)
