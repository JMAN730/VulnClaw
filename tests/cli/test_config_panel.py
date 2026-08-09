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


def _focus(model, key):
    """Move focus to a row by key, expanding whatever is needed to reach it."""
    for section in ("llm", "session", "safety", "recon", "mcp"):
        model._expanded.add(section)
    model._focus_key = key


def test_bool_field_toggles_without_opening_an_editor(model):
    _focus(model, "session.auto_save")
    before = model.draft.session.auto_save

    model.activate()

    assert model.draft.session.auto_save is not before
    assert model.editing is False


def test_text_edit_commits_on_enter(model):
    _focus(model, "llm.base_url")

    model.activate()
    model.set_edit_text("https://example.test/v1")
    model.commit_edit()

    assert model.draft.llm.base_url == "https://example.test/v1"
    assert model.editing is False


def test_text_edit_cancel_restores_previous_value(model):
    model.draft.llm.reasoning_effort = "medium"
    _focus(model, "llm.reasoning_effort")

    model.activate()
    model.set_edit_text("high")
    model.cancel_edit()

    assert model.draft.llm.reasoning_effort == "medium"


def test_blank_text_keeps_current_value_and_clear_sentinel_empties_it(model):
    model.draft.recon.fofa_email = "a@b.test"
    _focus(model, "recon.fofa_email")

    model.activate()
    model.set_edit_text("")
    model.commit_edit()
    assert model.draft.recon.fofa_email == "a@b.test"

    model.activate()
    model.set_edit_text("!clear")
    model.commit_edit()
    assert model.draft.recon.fofa_email == ""


def test_int_field_rejects_unparseable_input_and_keeps_the_editor_open(model):
    _focus(model, "llm.max_tokens")

    model.activate()
    model.set_edit_text("many")
    model.commit_edit()

    assert model.editing is True
    assert model.row_error != ""
    assert model.draft.llm.max_tokens == 4096


def test_float_and_list_and_env_fields_parse(model):
    _focus(model, "recon.http_timeout")
    model.activate()
    model.set_edit_text("2.5")
    model.commit_edit()
    assert model.draft.recon.http_timeout == 2.5


def test_secret_is_masked_until_revealed(model):
    model.draft.llm.api_key = "sk-abcdef123456"
    _focus(model, "llm.api_key")
    row = model.focused

    assert "sk-abcdef123456" not in model.display_value(row)

    model.toggle_reveal()

    assert model.display_value(row) == "sk-abcdef123456"


def test_secret_list_shows_a_count_not_the_keys(model):
    model.draft.llm.api_keys = ["sk-one", "sk-two"]
    _focus(model, "llm.api_keys")
    row = model.focused

    display = model.display_value(row)

    assert "sk-one" not in display
    assert "2" in display


def test_path_field_round_trips_as_a_path(model):
    from pathlib import Path

    _focus(model, "session.output_dir")

    model.activate()
    model.set_edit_text("./somewhere")
    model.commit_edit()

    assert model.draft.session.output_dir == Path("./somewhere")
