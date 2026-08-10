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

    assert "LLM" in output
    assert "openai" in output
    assert "Session" in output
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


def test_expanded_llm_section_shows_the_idle_fetch_hint():
    model = ConfigPanelModel(VulnClawConfig())
    model.toggle_expand()  # focus starts on the llm group

    output = _render(model)

    assert "Press Fetch to load models" in output


def test_the_idle_hint_gives_way_to_the_fetch_outcome():
    model = ConfigPanelModel(VulnClawConfig())
    model.toggle_expand()
    generation = model.begin_fetch()
    model.apply_fetch_result(generation, ["a", "b"], None)

    output = _render(model)

    assert "Press Fetch to load models" not in output
    assert "2 models loaded." in output


def test_errors_render_inside_the_panel():
    model = ConfigPanelModel(VulnClawConfig())
    model.draft.llm.auth_mode = "static"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []
    model.request_save()

    output = _render(model)

    assert "API key" in output
