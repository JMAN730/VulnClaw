"""Snapshot tests for the config panel renderer."""

import io

from rich.console import Console

from vulnclaw.cli.config_panel import ConfigPanelModel
from vulnclaw.cli.config_panel_render import render_panel
from vulnclaw.config.schema import VulnClawConfig
from vulnclaw.i18n import init_i18n


def _render(model):
    init_i18n("en")
    console = Console(
        file=io.StringIO(),
        record=True,
        width=120,
        height=40,
        force_terminal=True,
        color_system=None,
    )
    console.print(render_panel(model))
    return console.export_text(styles=False)


def test_collapsed_view_shows_one_line_per_section():
    config = VulnClawConfig()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4o"
    model = ConfigPanelModel(config)

    output = _render(model)
    from pathlib import Path
    Path("_fail_render.txt").write_text(output, encoding="utf-8")
    Path("_fail_rows.txt").write_text("\n".join(r.key for r in model.rows()), encoding="utf-8")

    assert "LLM" in output
    assert "openai" in output
    assert "Session" in output, f"keys={output!r}"
    assert "Base URL" not in output


def test_expanded_view_shows_fields_and_masks_the_key():
    config = VulnClawConfig()
    config.llm.api_key = "sk-abcdef123456"
    model = ConfigPanelModel(config)
    model.toggle_expand()

    output = _render(model)

    assert "Base URL" in output
    assert "sk-abcdef123456" not in output


def test_open_dropdown_lists_its_options():
    model = ConfigPanelModel(VulnClawConfig())
    model._expanded.add("session")
    model._focus_key = "session.report_format"
    model.activate()

    output = _render(model)

    assert "markdown" in output
    assert "html" in output


def test_errors_render_inside_the_panel():
    model = ConfigPanelModel(VulnClawConfig())
    model.draft.llm.auth_mode = "static"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []
    model.request_save()

    output = _render(model)

    assert "API key" in output
