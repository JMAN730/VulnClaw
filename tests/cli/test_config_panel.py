"""Behavior tests for the classic-REPL config panel model (no TTY required)."""

import pytest

from vulnclaw.cli.config_panel import ConfigPanelModel
from vulnclaw.config.schema import VulnClawConfig


@pytest.fixture
def model():
    return ConfigPanelModel(VulnClawConfig())


def test_starts_with_every_section_collapsed(model):
    keys = [row.key for row in model.rows()]

    assert keys == [
        "llm",
        "session",
        "safety",
        "recon",
        "mcp",
        "action.save",
    ]


def test_expanding_a_section_reveals_its_fields(model):
    model.toggle_expand()  # focus starts on the llm group

    keys = [row.key for row in model.rows()]

    assert keys[0] == "llm"
    assert "llm.provider" in keys
    assert "llm.reasoning_effort" in keys
    assert "action.fetch_models" in keys
    assert keys.index("llm.provider") < keys.index("session")


def test_navigation_skips_rows_inside_collapsed_groups(model):
    model.focus_next()

    assert model.focused.key == "session"


def test_navigation_walks_into_an_expanded_group(model):
    model.toggle_expand()
    model.focus_next()

    assert model.focused.key == "llm.provider"


def test_collapse_from_a_field_jumps_to_the_parent_group(model):
    model.toggle_expand()
    model.focus_next()

    model.collapse()

    assert model.focused.key == "llm"
    assert [row.key for row in model.rows()].count("llm.provider") == 0


def test_focus_does_not_run_off_either_end(model):
    model.focus_prev()
    assert model.focused.key == "llm"

    for _ in range(20):
        model.focus_next()
    assert model.focused.key == "action.save"


def test_draft_is_a_copy_of_the_supplied_config():
    config = VulnClawConfig()
    model = ConfigPanelModel(config)

    model.draft.llm.model = "changed"

    assert config.llm.model != "changed"
