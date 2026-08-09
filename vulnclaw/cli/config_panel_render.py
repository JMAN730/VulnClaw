"""Render a ConfigPanelModel as a Rich renderable. Pure: no state, no I/O."""

from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vulnclaw.cli.config_panel import ConfigPanelModel, Row
from vulnclaw.cli.tui import C_BORDER, C_ERROR, C_MUTED, C_PRIMARY, C_TEXT
from vulnclaw.i18n import _


def _row_label(model: ConfigPanelModel, row: Row) -> str:
    if row.kind == "group" and row.key.startswith("mcp."):
        return row.key.split(".", 1)[1]
    return _(row.label_key) if row.label_key else row.key


def _row_value(model: ConfigPanelModel, row: Row, focused: bool) -> str:
    if row.kind == "group":
        marker = "▾" if row.expanded else "▸"
        # MCP nested groups use the full key as section; summary() only knows top-level names.
        summary = "" if row.expanded else model.summary(row.key)
        return f"{marker} {summary}".rstrip()
    if focused and model.editing:
        return f"{model.edit_text}▏"
    return model.display_value(row)


def render_panel(model: ConfigPanelModel) -> Group:
    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("label", style=C_TEXT, no_wrap=True)
    table.add_column("value", style=C_TEXT)

    focused_key = model.focused.key
    for row in model.rows():
        focused = row.key == focused_key
        indent = "  " * row.depth
        label = Text(f"{indent}{_row_label(model, row)}")
        if row.kind == "group":
            label.stylize(f"bold {C_PRIMARY}")
        if focused:
            label.stylize("reverse")
        table.add_row(label, _row_value(model, row, focused))
        if focused and model.dropdown_open:
            for index, option in enumerate(model.dropdown_options):
                marker = "›" if index == model.dropdown_index else " "
                table.add_row(Text(f"{indent}  {marker} {option}", style=C_MUTED), "")

    body: list[object] = [table]
    if model.fetch_state == "loading":
        body.append(Text(_("tui.config_panel.fetch_loading"), style=C_MUTED))
    elif model.fetch_message:
        style = C_ERROR if model.fetch_state == "error" else C_MUTED
        body.append(Text(model.fetch_message, style=style))
    for message in (model.row_error, model.save_error):
        if message:
            body.append(Text(message, style=C_ERROR))
    body.append(
        Text(
            f"{_('tui.config_panel.nav_hint')}  ·  {_('tui.config_panel.esc_discards')}",
            style=C_MUTED,
        )
    )

    return Group(
        Panel(
            Group(*body),
            title="VulnClaw Config",
            border_style=C_BORDER,
            box=box.ROUNDED,
        )
    )
