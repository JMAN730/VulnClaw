"""Widgets (legacy package) — re-exports for backward compatibility.

New code should import from the canonical locations:

- ``vulnclaw.cli.textui.components`` — UI components
- ``vulnclaw.cli.textui.commands`` — slash commands
- ``vulnclaw.cli.textui.services`` — services
- ``vulnclaw.cli.textui.tools`` — tool implementations
- ``vulnclaw.cli.textui.agent`` — agent loop
- ``vulnclaw.cli.textui.utils`` — utilities

This module keeps old import paths working during migration.
"""

# Re-export components from new locations
from vulnclaw.cli.textui.components.chat_pane import ChatPane
from vulnclaw.cli.textui.components.chat_input import ChatInput
from vulnclaw.cli.textui.components.message_widgets import (
    UserMessage,
    AssistantText,
    ToolCallMessage,
    FormOperation,
    SystemMessage,
)
from vulnclaw.cli.textui.components.scan_config_screen import ScanConfigScreen

# Re-export legacy widgets that remain in widgets/
from vulnclaw.cli.textui.widgets.input_bar import InputBar
from vulnclaw.cli.textui.widgets.log_panel import LogPanel
from vulnclaw.cli.textui.widgets.overview import OverviewPanel
from vulnclaw.cli.textui.widgets.scope import ScopePanel
from vulnclaw.cli.textui.widgets.status_bar import StatusBar
from vulnclaw.cli.textui.widgets.tool_panel import ToolPanel

__all__ = [
    "AssistantText",
    "ChatInput",
    "ChatPane",
    "FormOperation",
    "InputBar",
    "LogPanel",
    "OverviewPanel",
    "ScanConfigScreen",
    "ScopePanel",
    "StatusBar",
    "SystemMessage",
    "ToolCallMessage",
    "ToolPanel",
    "UserMessage",
]
