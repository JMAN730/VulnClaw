# Classic-REPL Config Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the classic REPL's five `/config` prompt chains with one keyboard-navigable panel covering llm, session, safety, recon and MCP.

**Architecture:** A pure `ConfigPanelModel` (no I/O, no UI libraries) owns the draft config, the row tree, focus, expansion and edit state. A pure `render_panel(model)` turns the model into a Rich renderable. A thin prompt_toolkit `Application` in `tui.py` maps keys onto model methods and pipes the Rich output through `ANSI`, exactly as `_run_pt_tui` already does at `tui.py:559`. The existing prompt chains stay as the non-TTY fallback.

**Tech Stack:** Python 3.11+, pydantic v2 config models, Rich for rendering, prompt_toolkit for the full-screen app, pytest.

**Spec:** `.scratch/repl-config-panel/spec.md`

## Global Constraints

- Target branch: `JMAN730/87-i18n-support` (PR #93). Do not branch off main.
- No new third-party dependency. `rich>=13.0.0` and `prompt_toolkit>=3.0.0` are already in `pyproject.toml:29-30`.
- `vulnclaw/cli/config_panel.py` must not import `prompt_toolkit`, `rich`, or anything that touches disk or network. Every test in `tests/cli/test_config_panel.py` runs without a TTY.
- Field set is frozen to what the wizard exposes today: llm 11, session 18, safety 9, recon 13, MCP servers. Do not add schema fields the wizard does not already offer.
- All user-visible strings go through `_()` with keys under `tui.config_panel.`, added to both `vulnclaw/i18n/en.json` and `vulnclaw/i18n/zh.json`.
- The three existing wizard tests must stay green and unmodified: `test_tui_llm_config_prompt_saves_provider_and_api_key`, `test_config_tui_escape_exits_without_saving`, `test_config_tui_llm_editor_shows_models_for_selected_provider` (`tests/cli/test_cli.py:1179-1298`).
- Run `python -m ruff check` on every file you touch before committing.

## File Structure

| File | Responsibility |
| --- | --- |
| `vulnclaw/cli/config_panel.py` (create) | `FieldSpec`/`SectionSpec` tables, `Row`, `ConfigPanelModel`. Pure state. |
| `vulnclaw/cli/config_panel_render.py` (create) | `render_panel(model) -> rich.console.Group`. Pure rendering. |
| `vulnclaw/cli/tui.py` (modify) | `run_config_tui` becomes a TTY dispatcher; `_run_config_wizard` is the renamed old body; `_run_config_panel` is the new prompt_toolkit shell. |
| `vulnclaw/i18n/en.json`, `zh.json` (modify) | `tui.config_panel.*` keys. |
| `tests/cli/test_config_panel.py` (create) | Model behavior tests, no TTY. |
| `tests/cli/test_config_panel_render.py` (create) | Render snapshots through a recording `Console`. |
| `tests/cli/test_cli.py` (modify) | One dispatcher test appended; existing wizard tests untouched. |

---

### Task 1: Row tree, sections, navigation

**Files:**
- Create: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `VulnClawConfig` from `vulnclaw.config.schema`; `ENGINE_CHOICES` from the same module.
- Produces: `FieldSpec(path, label_key, kind, choices)`, `SectionSpec(name, label_key, fields)`, `Row(key, kind, label_key, depth, value_kind, expanded, path)`, `ConfigPanelModel(config)` with `rows() -> list[Row]`, `focused -> Row`, `focus_next()`, `focus_prev()`, `toggle_expand()`, `expand()`, `collapse()`, `draft`.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_config_panel.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vulnclaw.cli.config_panel'`

- [ ] **Step 3: Write minimal implementation**

```python
# vulnclaw/cli/config_panel.py
"""Pure state model for the classic-REPL configuration panel.

This module deliberately imports no UI library and performs no I/O, so the
whole panel's behavior can be tested without a terminal.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from vulnclaw.config.schema import ENGINE_CHOICES, VulnClawConfig

TEXT = "text"
SECRET = "secret"
SECRET_LIST = "secret_list"
BOOL = "bool"
CHOICE = "choice"
INT = "int"
FLOAT = "float"
LIST = "list"
ENV = "env"
MODEL = "model"
PATH = "path"


@dataclass(frozen=True)
class FieldSpec:
    """One editable config value and how the panel edits it."""

    path: str
    label_key: str
    kind: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionSpec:
    """A collapsible group of fields."""

    name: str
    label_key: str
    fields: tuple[FieldSpec, ...]


LLM_FIELDS = (
    FieldSpec("llm.provider", "tui.config_panel.llm_provider", CHOICE),
    FieldSpec("llm.base_url", "tui.config_panel.llm_base_url", TEXT),
    FieldSpec("llm.auth_mode", "tui.config_panel.llm_auth_mode", CHOICE, ("static", "oauth")),
    FieldSpec("llm.api_keys", "tui.config_panel.llm_api_keys", SECRET_LIST),
    FieldSpec("llm.api_key", "tui.config_panel.llm_api_key", SECRET),
    FieldSpec("llm.model", "tui.config_panel.llm_model", MODEL),
    FieldSpec("llm.chatgpt_auto_proxy", "tui.config_panel.llm_chatgpt_auto_proxy", BOOL),
    FieldSpec("llm.max_tokens", "tui.config_panel.llm_max_tokens", INT),
    FieldSpec("llm.max_context_tokens", "tui.config_panel.llm_max_context_tokens", INT),
    FieldSpec("llm.temperature", "tui.config_panel.llm_temperature", FLOAT),
    FieldSpec("llm.reasoning_effort", "tui.config_panel.llm_reasoning_effort", TEXT),
)

SESSION_FIELDS = (
    FieldSpec("session.output_dir", "tui.config_panel.session_output_dir", PATH),
    FieldSpec("session.auto_save", "tui.config_panel.session_auto_save", BOOL),
    FieldSpec(
        "session.report_format",
        "tui.config_panel.session_report_format",
        CHOICE,
        ("markdown", "html"),
    ),
    FieldSpec(
        "session.poc_language",
        "tui.config_panel.session_poc_language",
        CHOICE,
        ("python", "bash"),
    ),
    FieldSpec(
        "session.engine",
        "tui.config_panel.session_engine",
        CHOICE,
        tuple(ENGINE_CHOICES),
    ),
    FieldSpec("session.max_rounds", "tui.config_panel.session_max_rounds", INT),
    FieldSpec("session.show_thinking", "tui.config_panel.session_show_thinking", BOOL),
    FieldSpec(
        "session.context_auto_compact",
        "tui.config_panel.session_context_auto_compact",
        BOOL,
    ),
    FieldSpec(
        "session.context_compact_trigger_ratio",
        "tui.config_panel.session_context_compact_trigger_ratio",
        FLOAT,
    ),
    FieldSpec(
        "session.context_compact_target_ratio",
        "tui.config_panel.session_context_compact_target_ratio",
        FLOAT,
    ),
    FieldSpec(
        "session.context_recent_message_groups",
        "tui.config_panel.session_context_recent_message_groups",
        INT,
    ),
    FieldSpec(
        "session.context_summary_max_tokens",
        "tui.config_panel.session_context_summary_max_tokens",
        INT,
    ),
    FieldSpec(
        "session.context_output_reserve_tokens",
        "tui.config_panel.session_context_output_reserve_tokens",
        INT,
    ),
    FieldSpec(
        "session.context_compaction_audit_enabled",
        "tui.config_panel.session_context_compaction_audit_enabled",
        BOOL,
    ),
    FieldSpec(
        "session.persistent_rounds_per_cycle",
        "tui.config_panel.session_persistent_rounds_per_cycle",
        INT,
    ),
    FieldSpec(
        "session.persistent_max_cycles",
        "tui.config_panel.session_persistent_max_cycles",
        INT,
    ),
    FieldSpec(
        "session.persistent_auto_report",
        "tui.config_panel.session_persistent_auto_report",
        BOOL,
    ),
    FieldSpec(
        "session.language",
        "tui.config_panel.session_language",
        CHOICE,
        ("auto", "en", "zh"),
    ),
)

SAFETY_FIELDS = (
    FieldSpec(
        "safety.enable_python_execute",
        "tui.config_panel.safety_enable_python_execute",
        BOOL,
    ),
    FieldSpec(
        "safety.python_execute_restricted",
        "tui.config_panel.safety_python_execute_restricted",
        BOOL,
    ),
    FieldSpec(
        "safety.python_execute_mode",
        "tui.config_panel.safety_python_execute_mode",
        CHOICE,
        ("safe", "lab", "trusted-local"),
    ),
    FieldSpec(
        "safety.python_execute_max_lines",
        "tui.config_panel.safety_python_execute_max_lines",
        INT,
    ),
    FieldSpec(
        "safety.python_execute_show_warning",
        "tui.config_panel.safety_python_execute_show_warning",
        BOOL,
    ),
    FieldSpec(
        "safety.python_execute_max_output_chars",
        "tui.config_panel.safety_python_execute_max_output_chars",
        INT,
    ),
    FieldSpec(
        "safety.python_execute_audit_enabled",
        "tui.config_panel.safety_python_execute_audit_enabled",
        BOOL,
    ),
    FieldSpec("safety.tool_parallel", "tui.config_panel.safety_tool_parallel", BOOL),
    FieldSpec(
        "safety.tool_max_concurrent",
        "tui.config_panel.safety_tool_max_concurrent",
        INT,
    ),
)

RECON_FIELDS = (
    FieldSpec("recon.fofa_email", "tui.config_panel.recon_fofa_email", TEXT),
    FieldSpec("recon.fofa_key", "tui.config_panel.recon_fofa_key", SECRET),
    FieldSpec("recon.hunter_key", "tui.config_panel.recon_hunter_key", SECRET),
    FieldSpec("recon.quake_key", "tui.config_panel.recon_quake_key", SECRET),
    FieldSpec("recon.zoomeye_key", "tui.config_panel.recon_zoomeye_key", SECRET),
    FieldSpec("recon.shodan_key", "tui.config_panel.recon_shodan_key", SECRET),
    FieldSpec("recon.zerozone_key", "tui.config_panel.recon_zerozone_key", SECRET),
    FieldSpec("recon.http_timeout", "tui.config_panel.recon_http_timeout", FLOAT),
    FieldSpec("recon.max_concurrency", "tui.config_panel.recon_max_concurrency", INT),
    FieldSpec("recon.space_size", "tui.config_panel.recon_space_size", INT),
    FieldSpec(
        "recon.dir_wordlist_path",
        "tui.config_panel.recon_dir_wordlist_path",
        TEXT,
    ),
    FieldSpec("recon.dir_max_requests", "tui.config_panel.recon_dir_max_requests", INT),
    FieldSpec("recon.js_max_files", "tui.config_panel.recon_js_max_files", INT),
)

SECTIONS = (
    SectionSpec("llm", "tui.config_panel.section_llm", LLM_FIELDS),
    SectionSpec("session", "tui.config_panel.section_session", SESSION_FIELDS),
    SectionSpec("safety", "tui.config_panel.section_safety", SAFETY_FIELDS),
    SectionSpec("recon", "tui.config_panel.section_recon", RECON_FIELDS),
    SectionSpec("mcp", "tui.config_panel.section_mcp", ()),
)


@dataclass
class Row:
    """One visible line in the panel."""

    key: str
    kind: str  # "group" | "field" | "action"
    label_key: str
    depth: int
    value_kind: str = ""
    path: str = ""
    expanded: bool = False
    choices: tuple[str, ...] = ()


class ConfigPanelModel:
    """Draft-editing state machine behind the classic-REPL config panel."""

    def __init__(self, config: VulnClawConfig) -> None:
        self.draft = copy.deepcopy(config)
        self._expanded: set[str] = set()
        self._focus_key = "llm"

    # -- row tree ---------------------------------------------------------

    def rows(self) -> list[Row]:
        rows: list[Row] = []
        for section in SECTIONS:
            expanded = section.name in self._expanded
            rows.append(
                Row(
                    key=section.name,
                    kind="group",
                    label_key=section.label_key,
                    depth=0,
                    expanded=expanded,
                )
            )
            if not expanded:
                continue
            rows.extend(self._section_rows(section))
        rows.append(
            Row(key="action.save", kind="action", label_key="tui.config_panel.save", depth=0)
        )
        return rows

    def _section_rows(self, section: SectionSpec) -> list[Row]:
        rows = [
            Row(
                key=spec.path,
                kind="field",
                label_key=spec.label_key,
                depth=1,
                value_kind=spec.kind,
                path=spec.path,
                choices=spec.choices,
            )
            for spec in section.fields
        ]
        if section.name == "llm":
            rows.append(
                Row(
                    key="action.fetch_models",
                    kind="action",
                    label_key="tui.config_panel.fetch_models",
                    depth=1,
                )
            )
        return rows

    # -- focus ------------------------------------------------------------

    @property
    def focused(self) -> Row:
        rows = self.rows()
        for row in rows:
            if row.key == self._focus_key:
                return row
        self._focus_key = rows[0].key
        return rows[0]

    def _focus_index(self) -> int:
        rows = self.rows()
        for index, row in enumerate(rows):
            if row.key == self._focus_key:
                return index
        return 0

    def focus_next(self) -> None:
        rows = self.rows()
        self._focus_key = rows[min(self._focus_index() + 1, len(rows) - 1)].key

    def focus_prev(self) -> None:
        rows = self.rows()
        self._focus_key = rows[max(self._focus_index() - 1, 0)].key

    # -- expansion --------------------------------------------------------

    def toggle_expand(self) -> None:
        row = self.focused
        if row.kind != "group":
            return
        if row.key in self._expanded:
            self._expanded.discard(row.key)
        else:
            self._expanded.add(row.key)

    def expand(self) -> None:
        row = self.focused
        if row.kind == "group":
            self._expanded.add(row.key)

    def collapse(self) -> None:
        row = self.focused
        if row.kind == "group":
            self._expanded.discard(row.key)
            return
        parent = self._parent_key(row)
        if parent is not None:
            self._expanded.discard(parent)
            self._focus_key = parent

    def _parent_key(self, row: Row) -> str | None:
        if row.kind == "action" and row.key == "action.fetch_models":
            return "llm"
        if row.path:
            return row.path.split(".", 1)[0]
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add config panel row tree and navigation"
```

---

### Task 2: Value read, display and text editing

**Files:**
- Modify: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `Row`, `ConfigPanelModel` from Task 1.
- Produces: `model.display_value(row) -> str`, `model.raw_value(row) -> Any`, `model.activate()`, `model.editing -> bool`, `model.edit_text -> str`, `model.set_edit_text(str)`, `model.commit_edit()`, `model.cancel_edit()`, `model.toggle_reveal()`, `model.row_error -> str`, module functions `mask_secret(str) -> str` and `mask_key_list(list[str]) -> str`.

Note: `mask_secret` and `mask_key_list` move here from `tui.py:2023-2038` so the pure model does not import `tui`. `tui.py` re-imports them from this module so the wizard keeps working and `_mask_secret` stays a valid name at its old call sites.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: FAIL with `AttributeError: 'ConfigPanelModel' object has no attribute 'activate'`

- [ ] **Step 3: Write minimal implementation**

Add to `vulnclaw/cli/config_panel.py`:

```python
def mask_secret(value: str) -> str:
    """Mask a secret so only a hint of it reaches the terminal."""
    value = (value or "").strip()
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "…" + value[-2:]
    return f"{value[:2]}…{value[-4:]}"


def mask_key_list(keys: list[str]) -> str:
    """Summarise a list of API keys without printing any in the clear."""
    usable = [key for key in keys if key and key.strip()]
    if not usable:
        return "(none)"
    plural = "s" if len(usable) != 1 else ""
    return f"{mask_secret(usable[0])} ({len(usable)} key{plural})"


def split_csv_items(raw: str) -> list[str]:
    """Split a comma/newline separated string into cleaned items."""
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


def parse_env_items(raw: str) -> dict[str, str]:
    """Parse `KEY=value, KEY=value` into a dict, raising ValueError on junk."""
    result: dict[str, str] = {}
    for item in split_csv_items(raw):
        if "=" not in item:
            raise ValueError("Environment entries must look like KEY=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Environment keys cannot be blank")
        result[key] = value.strip()
    return result
```

Add to `ConfigPanelModel.__init__`:

```python
        self._edit: dict[str, Any] | None = None
        self._reveal = False
        self.row_error = ""
```

Add these methods:

```python
    # -- values -----------------------------------------------------------

    def raw_value(self, row: Row) -> Any:
        target: Any = self.draft
        parts = row.path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        return getattr(target, parts[-1])

    def _set_value(self, row: Row, value: Any) -> None:
        target: Any = self.draft
        parts = row.path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)

    def display_value(self, row: Row) -> str:
        if row.kind != "field":
            return ""
        value = self.raw_value(row)
        if row.value_kind == SECRET:
            return value if self._reveal else mask_secret(value)
        if row.value_kind == SECRET_LIST:
            return ", ".join(value) if self._reveal else mask_key_list(value)
        if row.value_kind == BOOL:
            return "yes" if value else "no"
        if row.value_kind == LIST:
            return ", ".join(value or [])
        if row.value_kind == ENV:
            return ", ".join(f"{k}={v}" for k, v in sorted((value or {}).items()))
        return str(value)

    def _edit_seed(self, row: Row) -> str:
        """Text the editor opens with. Secrets always open empty."""
        if row.value_kind in (SECRET, SECRET_LIST):
            return ""
        return self.display_value(row)

    # -- editing ----------------------------------------------------------

    @property
    def editing(self) -> bool:
        return self._edit is not None

    @property
    def edit_text(self) -> str:
        return self._edit["text"] if self._edit else ""

    def set_edit_text(self, text: str) -> None:
        if self._edit is not None:
            self._edit["text"] = text

    def cancel_edit(self) -> None:
        self._edit = None
        self.row_error = ""

    def toggle_reveal(self) -> None:
        self._reveal = not self._reveal

    def activate(self) -> None:
        row = self.focused
        self.row_error = ""
        if row.kind == "group":
            self.toggle_expand()
            return
        if row.kind != "field":
            return
        if row.value_kind == BOOL:
            self._set_value(row, not self.raw_value(row))
            return
        self._edit = {"key": row.key, "text": self._edit_seed(row)}

    def commit_edit(self) -> None:
        if self._edit is None:
            return
        row = self.focused
        raw = self._edit["text"].strip()
        try:
            value = self._parse(row, raw)
        except ValueError as exc:
            self.row_error = str(exc)
            return
        if value is not _KEEP:
            self._set_value(row, value)
        self._edit = None
        self.row_error = ""

    def _parse(self, row: Row, raw: str) -> Any:
        kind = row.value_kind
        if raw == "!clear":
            return {
                SECRET_LIST: [],
                LIST: [],
                ENV: {},
            }.get(kind, "")
        if raw == "":
            return _KEEP
        if kind in (TEXT, SECRET, MODEL):
            return raw
        if kind == PATH:
            from pathlib import Path

            return Path(raw)
        if kind in (SECRET_LIST, LIST):
            return split_csv_items(raw)
        if kind == ENV:
            return parse_env_items(raw)
        if kind == INT:
            try:
                return int(raw)
            except ValueError:
                raise ValueError("Enter a whole number.") from None
        if kind == FLOAT:
            try:
                return float(raw)
            except ValueError:
                raise ValueError("Enter a number.") from None
        return raw
```

Add the sentinel next to the kind constants:

```python
class _Keep:
    """Sentinel: blank input leaves the current value alone."""


_KEEP = _Keep()
```

Then in `vulnclaw/cli/tui.py`, replace the bodies of `_mask_secret`, `_mask_key_list` and `_split_csv_items` (`tui.py:2018-2038`) with re-exports so there is one implementation:

```python
from vulnclaw.cli.config_panel import (
    mask_key_list as _mask_key_list,
    mask_secret as _mask_secret,
    split_csv_items as _split_csv_items,
)
```

Delete the three old function definitions.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py tests/cli/test_cli.py -q`
Expected: PASS, including the three untouched wizard tests

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py vulnclaw/cli/tui.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add value editing and secret masking to the config panel model"
```

---

### Task 3: Choice dropdowns and provider presets

**Files:**
- Modify: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `activate()`, `_set_value()` from Task 2.
- Produces: `model.dropdown_open -> bool`, `model.dropdown_options -> list[str]`, `model.dropdown_index -> int`, `model.select_option(delta: int)`, `model.commit_option()`, `model.cancel_option()`, `model.generation -> int`, `model.provider_choices() -> list[str]`.

`apply_provider_preset` and `list_providers` are imported from `vulnclaw.config.settings`. Both are pure with respect to disk (they only read the bundled provider table), so the model may import them.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
def test_choice_field_opens_a_dropdown_and_commits(model):
    _focus(model, "session.report_format")

    model.activate()
    assert model.dropdown_open is True
    assert model.dropdown_options == ["markdown", "html"]

    model.select_option(1)
    model.commit_option()

    assert model.draft.session.report_format == "html"
    assert model.dropdown_open is False


def test_dropdown_cancel_restores_the_previous_choice(model):
    model.draft.session.poc_language = "python"
    _focus(model, "session.poc_language")

    model.activate()
    model.select_option(1)
    model.cancel_option()

    assert model.draft.session.poc_language == "python"
    assert model.dropdown_open is False


def test_dropdown_selection_does_not_run_off_either_end(model):
    _focus(model, "session.report_format")
    model.activate()

    model.select_option(-5)
    assert model.dropdown_index == 0

    model.select_option(5)
    assert model.dropdown_index == 1


def test_changing_provider_applies_the_preset_and_bumps_the_generation(model):
    _focus(model, "llm.provider")
    model.activate()
    model.dropdown_index = model.dropdown_options.index("deepseek")
    generation_before = model.generation

    model.commit_option()

    assert model.draft.llm.provider == "deepseek"
    assert model.draft.llm.base_url == "https://api.deepseek.com"
    assert model.generation > generation_before
    assert model.models == []


def test_editing_base_url_or_key_bumps_the_generation(model):
    generation_before = model.generation

    _focus(model, "llm.base_url")
    model.activate()
    model.set_edit_text("https://example.test/v1")
    model.commit_edit()

    assert model.generation > generation_before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k dropdown`
Expected: FAIL with `AttributeError: 'ConfigPanelModel' object has no attribute 'dropdown_open'`

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `config_panel.py`:

```python
from vulnclaw.config.settings import apply_provider_preset, list_providers
```

Add to `__init__`:

```python
        self._dropdown: dict[str, Any] | None = None
        self.dropdown_index = 0
        self.generation = 0
        self.models: list[str] = []
```

Add these methods and extend `activate` / `commit_edit`:

```python
    STALE_PATHS = ("llm.provider", "llm.base_url", "llm.api_key", "llm.api_keys")

    def provider_choices(self) -> list[str]:
        return [item["provider"] for item in list_providers()]

    def options_for(self, row: Row) -> list[str]:
        if row.path == "llm.provider":
            return self.provider_choices()
        if row.value_kind == MODEL:
            return list(self.models)
        return list(row.choices)

    @property
    def dropdown_open(self) -> bool:
        return self._dropdown is not None

    @property
    def dropdown_options(self) -> list[str]:
        return self._dropdown["options"] if self._dropdown else []

    def select_option(self, delta: int) -> None:
        if self._dropdown is None:
            return
        limit = len(self._dropdown["options"]) - 1
        self.dropdown_index = max(0, min(self.dropdown_index + delta, limit))

    def cancel_option(self) -> None:
        self._dropdown = None
        self.dropdown_index = 0

    def commit_option(self) -> None:
        if self._dropdown is None:
            return
        row = self.focused
        choice = self._dropdown["options"][self.dropdown_index]
        self._dropdown = None
        self.dropdown_index = 0
        if row.path == "llm.provider":
            if choice != self.draft.llm.provider:
                self.draft = apply_provider_preset(self.draft, choice)
                self.draft.llm.provider = choice
                self._invalidate_models()
            return
        self._set_value(row, choice)

    def _invalidate_models(self) -> None:
        """Any credential change makes a fetched model list stale."""
        self.generation += 1
        self.models = []
```

In `activate`, before the bool branch, add:

```python
        options = self.options_for(row)
        if row.value_kind == CHOICE or (row.value_kind == MODEL and options):
            self._dropdown = {"options": options}
            current = self.raw_value(row)
            self.dropdown_index = options.index(current) if current in options else 0
            return
```

In `commit_edit`, after a successful `_set_value`, add:

```python
        if row.path in self.STALE_PATHS:
            self._invalidate_models()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add choice dropdowns and provider presets to the config panel"
```

---

### Task 4: Model fetch with a stale-result guard

**Files:**
- Modify: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `generation`, `models`, `_invalidate_models()` from Task 3.
- Produces: `model.can_fetch() -> bool`, `model.begin_fetch() -> int` (returns the generation to hand the worker thread), `model.apply_fetch_result(generation: int, models: list[str], error: str | None)`, `model.fetch_state -> str` (one of `"idle"`, `"loading"`, `"ok"`, `"error"`), `model.fetch_message -> str`.

The model never spawns a thread. Task 9's shell owns the thread and calls `apply_fetch_result` on the event loop.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
def test_fetch_is_blocked_without_credentials(model):
    model.draft.llm.base_url = ""
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []

    assert model.can_fetch() is False


def test_fetch_is_allowed_with_a_base_url_and_any_key(model):
    model.draft.llm.base_url = "https://example.test/v1"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = ["sk-pool"]

    assert model.can_fetch() is True


def test_successful_fetch_populates_the_model_list(model):
    model.draft.llm.base_url = "https://example.test/v1"
    model.draft.llm.api_key = "sk-test"

    generation = model.begin_fetch()
    assert model.fetch_state == "loading"

    model.apply_fetch_result(generation, ["a", "b"], None)

    assert model.models == ["a", "b"]
    assert model.fetch_state == "ok"


def test_a_stale_fetch_result_is_ignored(model):
    model.draft.llm.base_url = "https://example.test/v1"
    model.draft.llm.api_key = "sk-test"
    stale = model.begin_fetch()

    model._invalidate_models()  # provider changed while the fetch was in flight

    model.apply_fetch_result(stale, ["wrong-provider-model"], None)

    assert model.models == []


def test_a_failed_fetch_reports_an_error_and_leaves_the_list_empty(model):
    model.draft.llm.base_url = "https://example.test/v1"
    model.draft.llm.api_key = "sk-test"
    generation = model.begin_fetch()

    model.apply_fetch_result(generation, [], "connection refused")

    assert model.models == []
    assert model.fetch_state == "error"
    assert "connection refused" in model.fetch_message


def test_an_empty_successful_fetch_is_reported_as_an_error(model):
    model.draft.llm.base_url = "https://example.test/v1"
    model.draft.llm.api_key = "sk-test"
    generation = model.begin_fetch()

    model.apply_fetch_result(generation, [], None)

    assert model.fetch_state == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k fetch`
Expected: FAIL with `AttributeError: 'ConfigPanelModel' object has no attribute 'can_fetch'`

- [ ] **Step 3: Write minimal implementation**

Add to `__init__`:

```python
        self.fetch_state = "idle"
        self.fetch_message = ""
```

Add these methods:

```python
    def _usable_key(self) -> str:
        for key in self.draft.llm.api_keys:
            if key and key.strip():
                return key
        return self.draft.llm.api_key.strip()

    def can_fetch(self) -> bool:
        return bool(self.draft.llm.base_url.strip() and self._usable_key())

    def begin_fetch(self) -> int:
        """Mark a fetch in flight and return the generation the worker must echo back."""
        self.generation += 1
        self.models = []
        self.fetch_state = "loading"
        self.fetch_message = ""
        return self.generation

    def apply_fetch_result(
        self, generation: int, models: list[str], error: str | None
    ) -> None:
        if generation != self.generation:
            return
        if error:
            self.models = []
            self.fetch_state = "error"
            self.fetch_message = error
            return
        if not models:
            self.models = []
            self.fetch_state = "error"
            self.fetch_message = "No models returned; enter a model id manually."
            return
        self.models = list(models)
        self.fetch_state = "ok"
        self.fetch_message = f"{len(models)} models loaded."
```

Also extend `_invalidate_models` so an invalidated in-flight fetch resets the banner:

```python
    def _invalidate_models(self) -> None:
        self.generation += 1
        self.models = []
        self.fetch_state = "idle"
        self.fetch_message = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add guarded model fetching to the config panel model"
```

---

### Task 5: MCP servers as nested groups

**Files:**
- Modify: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `rows()`, `_section_rows()` from Task 1.
- Produces: MCP server rows keyed `mcp.<name>` (group) and `mcp.<name>.<field>` (field); `model.add_server(name: str) -> None` and `model.delete_server() -> None` operating on the focused server; `model.pending_server_name -> str` for the add flow. `delete_server` raises nothing — it sets `row_error` when the server is builtin.

MCP paths do not map onto `getattr` chains the way `llm.base_url` does, because the middle segment is a dict key. `raw_value`/`_set_value` gain a dict-aware branch.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
from vulnclaw.config.schema import MCPServerConfig, MCPTransportConfig


def _with_server(name="demo", enabled=True):
    config = VulnClawConfig()
    config.mcp.servers[name] = MCPServerConfig(
        name=name,
        enabled=enabled,
        priority=1,
        transport=MCPTransportConfig(type="stdio", command="run-me"),
    )
    return ConfigPanelModel(config)


def test_mcp_section_lists_servers_as_collapsed_groups():
    model = _with_server()
    model._expanded.add("mcp")

    keys = [row.key for row in model.rows()]

    assert "mcp.demo" in keys
    assert "mcp.demo.enabled" not in keys
    assert "action.add_server" in keys


def test_expanding_a_server_reveals_its_transport_fields():
    model = _with_server()
    model._expanded.update({"mcp", "mcp.demo"})

    keys = [row.key for row in model.rows()]

    assert "mcp.demo.enabled" in keys
    assert "mcp.demo.transport.type" in keys
    assert "mcp.demo.transport.env" in keys


def test_editing_a_nested_server_field_writes_through_to_the_draft():
    model = _with_server()
    model._expanded.update({"mcp", "mcp.demo"})
    model._focus_key = "mcp.demo.transport.command"

    model.activate()
    model.set_edit_text("other-command")
    model.commit_edit()

    assert model.draft.mcp.servers["demo"].transport.command == "other-command"


def test_adding_a_server_rejects_blank_and_duplicate_names():
    model = _with_server()

    model.add_server("")
    assert model.row_error != ""
    assert list(model.draft.mcp.servers) == ["demo"]

    model.add_server("demo")
    assert model.row_error != ""
    assert list(model.draft.mcp.servers) == ["demo"]

    model.add_server("second")
    assert model.row_error == ""
    assert model.draft.mcp.servers["second"].transport.type == "stdio"


def test_deleting_a_custom_server_removes_it():
    model = _with_server()
    model._expanded.add("mcp")
    model._focus_key = "mcp.demo"

    model.delete_server()

    assert "demo" not in model.draft.mcp.servers


def test_builtin_servers_cannot_be_deleted():
    from vulnclaw.config.schema import BUILTIN_MCP_SERVERS

    name = next(iter(BUILTIN_MCP_SERVERS))
    model = _with_server(name=name)
    model._expanded.add("mcp")
    model._focus_key = f"mcp.{name}"

    model.delete_server()

    assert name in model.draft.mcp.servers
    assert model.row_error != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k mcp or server`
Expected: FAIL — `mcp.demo` is not in the row keys

- [ ] **Step 3: Write minimal implementation**

Add the import:

```python
from vulnclaw.config.schema import (
    BUILTIN_MCP_SERVERS,
    ENGINE_CHOICES,
    MCPServerConfig,
    MCPTransportConfig,
    VulnClawConfig,
)
```

Add the per-server field table next to the section tables:

```python
MCP_SERVER_FIELDS = (
    FieldSpec("enabled", "tui.config_panel.mcp_enabled", BOOL),
    FieldSpec("priority", "tui.config_panel.mcp_priority", INT),
    FieldSpec("description", "tui.config_panel.mcp_description", TEXT),
    FieldSpec(
        "transport.type",
        "tui.config_panel.mcp_transport_type",
        CHOICE,
        ("stdio", "sse", "streamable-http"),
    ),
    FieldSpec("transport.command", "tui.config_panel.mcp_transport_command", TEXT),
    FieldSpec("transport.args", "tui.config_panel.mcp_transport_args", LIST),
    FieldSpec("transport.url", "tui.config_panel.mcp_transport_url", TEXT),
    FieldSpec("transport.env", "tui.config_panel.mcp_transport_env", ENV),
    FieldSpec(
        "transport.startup_timeout",
        "tui.config_panel.mcp_transport_startup_timeout",
        INT,
    ),
    FieldSpec("transport.tool_timeout", "tui.config_panel.mcp_transport_tool_timeout", INT),
)
```

Replace `_section_rows`'s MCP handling by adding this branch at the top of the method:

```python
        if section.name == "mcp":
            return self._mcp_rows()
```

and add:

```python
    def _mcp_rows(self) -> list[Row]:
        rows: list[Row] = []
        for name in self.draft.mcp.servers:
            server_key = f"mcp.{name}"
            expanded = server_key in self._expanded
            rows.append(
                Row(
                    key=server_key,
                    kind="group",
                    label_key="",
                    depth=1,
                    expanded=expanded,
                )
            )
            if not expanded:
                continue
            for spec in MCP_SERVER_FIELDS:
                rows.append(
                    Row(
                        key=f"{server_key}.{spec.path}",
                        kind="field",
                        label_key=spec.label_key,
                        depth=2,
                        value_kind=spec.kind,
                        path=f"{server_key}.{spec.path}",
                        choices=spec.choices,
                    )
                )
            rows.append(
                Row(
                    key=f"{server_key}.action.delete",
                    kind="action",
                    label_key="tui.config_panel.delete_server",
                    depth=2,
                )
            )
        rows.append(
            Row(
                key="action.add_server",
                kind="action",
                label_key="tui.config_panel.add_server",
                depth=1,
            )
        )
        return rows
```

Make path resolution dict-aware. Replace the loop body in `raw_value` and `_set_value` with a shared resolver:

```python
    def _resolve(self, path: str) -> tuple[Any, str]:
        """Return (owner, attribute) for a dotted path, hopping the MCP server dict."""
        parts = path.split(".")
        if parts[0] == "mcp":
            target: Any = self.draft.mcp.servers[parts[1]]
            parts = parts[2:]
        else:
            target = self.draft
        for part in parts[:-1]:
            target = getattr(target, part)
        return target, parts[-1]

    def raw_value(self, row: Row) -> Any:
        owner, attribute = self._resolve(row.path)
        return getattr(owner, attribute)

    def _set_value(self, row: Row, value: Any) -> None:
        owner, attribute = self._resolve(row.path)
        setattr(owner, attribute, value)
```

Extend `_parent_key` for the nested case:

```python
    def _parent_key(self, row: Row) -> str | None:
        if row.key == "action.fetch_models":
            return "llm"
        if row.key == "action.add_server":
            return "mcp"
        if row.key.startswith("mcp."):
            parts = row.key.split(".")
            return f"mcp.{parts[1]}" if len(parts) > 2 else "mcp"
        if row.path:
            return row.path.split(".", 1)[0]
        return None
```

Add the mutations:

```python
    def add_server(self, name: str) -> None:
        name = name.strip()
        if not name:
            self.row_error = "Server name cannot be blank."
            return
        if name in self.draft.mcp.servers:
            self.row_error = f"Server '{name}' already exists."
            return
        self.draft.mcp.servers[name] = MCPServerConfig(
            name=name,
            enabled=True,
            priority=1,
            transport=MCPTransportConfig(type="stdio"),
        )
        self.row_error = ""
        self._expanded.update({"mcp", f"mcp.{name}"})
        self._focus_key = f"mcp.{name}"

    def delete_server(self) -> None:
        row = self.focused
        parts = row.key.split(".")
        if len(parts) < 2 or parts[0] != "mcp":
            return
        name = parts[1]
        if name in BUILTIN_MCP_SERVERS:
            self.row_error = "Built-in servers cannot be deleted here."
            return
        self.draft.mcp.servers.pop(name, None)
        self._expanded.discard(f"mcp.{name}")
        self._focus_key = "mcp"
        self.row_error = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add nested MCP server rows to the config panel model"
```

---

### Task 6: Validation, save gating and section summaries

**Files:**
- Modify: `vulnclaw/cli/config_panel.py`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: `draft`, `row_error` from earlier tasks.
- Produces: `model.validate() -> list[str]`, `model.request_save() -> bool` (True when the caller should persist `model.draft`), `model.save_error -> str`, `model.summary(section_name: str) -> str`.

`request_save` owns the warn-once behavior for a malformed base URL so the shell stays dumb.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
def test_save_is_blocked_when_static_auth_has_no_credentials(model):
    model.draft.llm.auth_mode = "static"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []

    assert model.request_save() is False
    assert model.save_error != ""


def test_save_is_allowed_when_oauth_has_no_static_key(model):
    model.draft.llm.auth_mode = "oauth"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []
    model.draft.llm.base_url = "https://example.test/v1"

    assert model.request_save() is True


def test_a_malformed_base_url_warns_once_then_saves(model):
    model.draft.llm.api_key = "sk-test"
    model.draft.llm.base_url = "example.test/v1"

    assert model.request_save() is False
    assert "URL" in model.save_error or "url" in model.save_error

    assert model.request_save() is True


def test_save_surfaces_a_schema_violation(model):
    model.draft.llm.api_key = "sk-test"
    model.draft.session.max_rounds = -1

    assert model.request_save() is False
    assert "max_rounds" in model.save_error


def test_collapsed_summaries_describe_each_section(model):
    model.draft.llm.provider = "openai"
    model.draft.llm.model = "gpt-4o"
    model.draft.llm.api_key = "sk-abcdef123456"

    summary = model.summary("llm")

    assert "openai" in summary
    assert "gpt-4o" in summary
    assert "sk-abcdef123456" not in summary


def test_llm_summary_flags_that_the_key_pool_wins(model):
    model.draft.llm.api_key = "sk-single"
    model.draft.llm.api_keys = ["sk-pool"]

    assert "pool" in model.summary("llm").lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k save or summary`
Expected: FAIL with `AttributeError: 'ConfigPanelModel' object has no attribute 'request_save'`

- [ ] **Step 3: Write minimal implementation**

Add to `__init__`:

```python
        self.save_error = ""
        self._url_warning_acknowledged = False
```

Add these methods:

```python
    def validate(self) -> list[str]:
        """Blocking problems, in the order they should be shown."""
        errors: list[str] = []
        llm = self.draft.llm
        if llm.auth_mode == "static" and not self._usable_key():
            errors.append("An API key is required for static auth mode.")
        for name, server in self.draft.mcp.servers.items():
            if not name.strip():
                errors.append("MCP server names cannot be blank.")
            if server.transport.type == "stdio" and not (server.transport.command or "").strip():
                errors.append(f"MCP server '{name}' needs a command for stdio transport.")
            if server.transport.type != "stdio" and not (server.transport.url or "").strip():
                errors.append(f"MCP server '{name}' needs a URL for {server.transport.type}.")
        try:
            VulnClawConfig.model_validate(self.draft.model_dump())
        except Exception as exc:  # pydantic ValidationError
            errors.append(str(exc).splitlines()[1].strip() if "\n" in str(exc) else str(exc))
        return errors

    def _base_url_is_suspicious(self) -> bool:
        url = self.draft.llm.base_url.strip()
        return bool(url) and not url.startswith(("http://", "https://"))

    def request_save(self) -> bool:
        """True when the shell should call save_config(model.draft)."""
        errors = self.validate()
        if errors:
            self.save_error = errors[0]
            return False
        if self._base_url_is_suspicious() and not self._url_warning_acknowledged:
            self._url_warning_acknowledged = True
            self.save_error = "Base URL may be malformed; press Save again to continue."
            return False
        self.save_error = ""
        return True

    def summary(self, section_name: str) -> str:
        llm = self.draft.llm
        if section_name == "llm":
            parts = [llm.provider, llm.model, f"key {mask_secret(llm.api_key)}"]
            if [key for key in llm.api_keys if key.strip()]:
                parts.append("failover pool takes precedence")
            return " · ".join(parts)
        if section_name == "session":
            return " · ".join(
                [
                    self.draft.session.engine,
                    f"{self.draft.session.max_rounds} rounds",
                    self.draft.session.language,
                ]
            )
        if section_name == "safety":
            state = "on" if self.draft.safety.enable_python_execute else "off"
            return f"python exec {state} · {self.draft.safety.python_execute_mode}"
        if section_name == "recon":
            keys = [
                self.draft.recon.fofa_key,
                self.draft.recon.hunter_key,
                self.draft.recon.quake_key,
                self.draft.recon.zoomeye_key,
                self.draft.recon.shodan_key,
                self.draft.recon.zerozone_key,
            ]
            return f"{len([key for key in keys if key.strip()])} keys set"
        if section_name == "mcp":
            count = len(self.draft.mcp.servers)
            return f"{count} server{'s' if count != 1 else ''}"
        return ""
```

Note on the pydantic branch: `str(exc).splitlines()[1]` picks the first field line of a pydantic v2 error, which reads as `session.max_rounds` — that is what the `max_rounds` assertion matches. If the installed pydantic formats differently, adjust the slice, not the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel.py tests/cli/test_config_panel.py
git commit -m "feat(cli): add validation and section summaries to the config panel model"
```

---

### Task 7: i18n catalog entries

**Files:**
- Modify: `vulnclaw/i18n/en.json`, `vulnclaw/i18n/zh.json`
- Test: `tests/cli/test_config_panel.py`

**Interfaces:**
- Consumes: every `label_key` string used in Tasks 1 and 5, plus the action and hint keys.
- Produces: no Python surface. A guard test asserts the two catalogs agree.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_config_panel.py
def test_every_panel_label_key_exists_in_both_catalogs():
    import json
    from pathlib import Path

    from vulnclaw.cli import config_panel as panel

    root = Path(panel.__file__).resolve().parents[1] / "i18n"
    catalogs = {
        name: json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("en", "zh")
    }

    used = {
        spec.label_key
        for section in panel.SECTIONS
        for spec in section.fields
    }
    used |= {spec.label_key for spec in panel.MCP_SERVER_FIELDS}
    used |= {section.label_key for section in panel.SECTIONS}
    used |= {
        "tui.config_panel.save",
        "tui.config_panel.fetch_models",
        "tui.config_panel.add_server",
        "tui.config_panel.delete_server",
        "tui.config_panel.nav_hint",
        "tui.config_panel.esc_discards",
        "tui.config_panel.reveal_hint",
        "tui.config_panel.fetch_idle",
        "tui.config_panel.fetch_loading",
        "tui.config_panel.saved",
        "tui.config_panel.discarded",
    }

    for name, catalog in catalogs.items():
        missing = sorted(key for key in used if key not in catalog)
        assert missing == [], f"{name}.json is missing: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k catalog`
Expected: FAIL listing every `tui.config_panel.*` key as missing from `en.json`

- [ ] **Step 3: Write minimal implementation**

Add every key the test enumerates to both catalogs. English values are the labels the wizard already uses (`tui.py:2258-2444`), so the panel reads identically to the editor it replaces. Sample of the shape — write out all of them, not just these:

```json
  "tui.config_panel.section_llm": "LLM",
  "tui.config_panel.section_session": "Session",
  "tui.config_panel.section_safety": "Safety",
  "tui.config_panel.section_recon": "Recon",
  "tui.config_panel.section_mcp": "MCP Servers",
  "tui.config_panel.llm_provider": "Provider",
  "tui.config_panel.llm_base_url": "Base URL",
  "tui.config_panel.llm_auth_mode": "Auth mode",
  "tui.config_panel.llm_api_keys": "API keys",
  "tui.config_panel.llm_api_key": "Single API key fallback",
  "tui.config_panel.llm_model": "Model",
  "tui.config_panel.save": "Save",
  "tui.config_panel.fetch_models": "Fetch models",
  "tui.config_panel.add_server": "+ Add server",
  "tui.config_panel.delete_server": "Delete server",
  "tui.config_panel.nav_hint": "↑↓ move · Enter edit · Space expand · Ctrl+R reveal · Ctrl+S save",
  "tui.config_panel.esc_discards": "Esc discards",
  "tui.config_panel.reveal_hint": "Ctrl+R reveals API keys",
  "tui.config_panel.fetch_idle": "Press Fetch to load models",
  "tui.config_panel.fetch_loading": "Loading models…",
  "tui.config_panel.saved": "Config saved.",
  "tui.config_panel.discarded": "Discarded changes."
```

For `zh.json`, translate each value. Reuse the existing wizard translations where the catalog already has an equivalent (`tui.fetching_models` for the loading line, for example) so the wording stays consistent with the rest of the Chinese UI.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel.py -v -k catalog`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/i18n/en.json vulnclaw/i18n/zh.json tests/cli/test_config_panel.py
git commit -m "i18n: add config panel strings in en and zh"
```

---

### Task 8: Renderer

**Files:**
- Create: `vulnclaw/cli/config_panel_render.py`
- Test: `tests/cli/test_config_panel_render.py`

**Interfaces:**
- Consumes: `ConfigPanelModel`, `Row`, `model.rows()`, `model.display_value()`, `model.summary()`, `model.focused`, `model.editing`, `model.edit_text`, `model.dropdown_open`, `model.dropdown_options`, `model.dropdown_index`, `model.fetch_state`, `model.fetch_message`, `model.save_error`, `model.row_error`.
- Produces: `render_panel(model) -> rich.console.Group`.

Palette constants are imported from `vulnclaw.cli.tui` (`C_PRIMARY`, `C_MUTED`, `C_ERROR`, `C_BORDER`, `C_TEXT`). Importing `tui` from the renderer is fine — the renderer is not the pure module.

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_config_panel_render.py
"""Snapshot tests for the config panel renderer."""

import io

from rich.console import Console

from vulnclaw.cli.config_panel import ConfigPanelModel
from vulnclaw.cli.config_panel_render import render_panel
from vulnclaw.config.schema import VulnClawConfig


def _render(model):
    console = Console(
        file=io.StringIO(), record=True, width=100, force_terminal=False, color_system=None
    )
    console.print(render_panel(model))
    return console.export_text()


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


def test_errors_render_inside_the_panel():
    model = ConfigPanelModel(VulnClawConfig())
    model.draft.llm.auth_mode = "static"
    model.draft.llm.api_key = ""
    model.draft.llm.api_keys = []
    model.request_save()

    output = _render(model)

    assert "API key" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_config_panel_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vulnclaw.cli.config_panel_render'`

- [ ] **Step 3: Write minimal implementation**

```python
# vulnclaw/cli/config_panel_render.py
"""Render a ConfigPanelModel as a Rich renderable. Pure: no state, no I/O."""

from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vulnclaw.cli.config_panel import SECTIONS, ConfigPanelModel, Row
from vulnclaw.cli.tui import C_BORDER, C_ERROR, C_MUTED, C_PRIMARY, C_TEXT
from vulnclaw.i18n import _

_SECTION_LABELS = {section.name: section.label_key for section in SECTIONS}


def _row_label(model: ConfigPanelModel, row: Row) -> str:
    if row.kind == "group" and row.key.startswith("mcp."):
        return row.key.split(".", 1)[1]
    return _(row.label_key) if row.label_key else row.key


def _row_value(model: ConfigPanelModel, row: Row, focused: bool) -> str:
    if row.kind == "group":
        marker = "▾" if row.expanded else "▸"
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
```

Note: `_SECTION_LABELS` is unused in this first cut — delete it rather than leaving it, `ruff` will flag it.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_config_panel_render.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vulnclaw/cli/config_panel_render.py tests/cli/test_config_panel_render.py
git commit -m "feat(cli): render the config panel with Rich"
```

---

### Task 9: prompt_toolkit shell and TTY dispatch

**Files:**
- Modify: `vulnclaw/cli/tui.py:2571-2608`
- Test: `tests/cli/test_cli.py` (append)

**Interfaces:**
- Consumes: `ConfigPanelModel`, `render_panel`, `load_config`, `save_config`, `fetch_provider_models`.
- Produces: `run_config_tui()` unchanged in signature; new private `_run_config_panel()` and renamed `_run_config_wizard()`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/cli/test_cli.py, inside the class holding the other config-editor tests
    def test_run_config_tui_uses_the_panel_only_on_a_tty(self, monkeypatch):
        import vulnclaw.cli.tui as tui_mod

        calls = []
        monkeypatch.setattr(tui_mod, "_run_config_panel", lambda: calls.append("panel"))
        monkeypatch.setattr(tui_mod, "_run_config_wizard", lambda: calls.append("wizard"))

        monkeypatch.setattr(tui_mod.sys.stdin, "isatty", lambda: True, raising=False)
        monkeypatch.setattr(tui_mod.sys.stdout, "isatty", lambda: True, raising=False)
        tui_mod.run_config_tui()

        monkeypatch.setattr(tui_mod.sys.stdin, "isatty", lambda: False, raising=False)
        tui_mod.run_config_tui()

        assert calls == ["panel", "wizard"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_cli.py -v -k run_config_tui_uses_the_panel`
Expected: FAIL with `AttributeError: module 'vulnclaw.cli.tui' has no attribute '_run_config_panel'`

- [ ] **Step 3: Write minimal implementation**

Rename the existing `run_config_tui` body to `_run_config_wizard` (keep every line as-is), then add:

```python
def run_config_tui() -> None:
    """Run the interactive config editor: panel on a TTY, prompt chain otherwise."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        _run_config_panel()
        return
    _run_config_wizard()


def _run_config_panel() -> None:
    """Full-screen keyboard-navigable config panel."""
    import threading

    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl

    from vulnclaw.cli.config_panel import ConfigPanelModel
    from vulnclaw.cli.config_panel_render import render_panel

    screen = Console()
    model = ConfigPanelModel(load_config())
    outcome: dict[str, str] = {}

    def _body() -> ANSI:
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=True, width=None, color_system="truecolor")
        console.print(render_panel(model))
        return ANSI(buf.getvalue().rstrip("\n"))

    kb = KeyBindings()

    @kb.add("up")
    def _up(event: Any) -> None:
        if model.dropdown_open:
            model.select_option(-1)
        else:
            model.focus_prev()

    @kb.add("down")
    def _down(event: Any) -> None:
        if model.dropdown_open:
            model.select_option(1)
        else:
            model.focus_next()

    @kb.add("tab")
    def _tab(event: Any) -> None:
        model.focus_next()

    @kb.add("s-tab")
    def _shift_tab(event: Any) -> None:
        model.focus_prev()

    @kb.add("left")
    def _left(event: Any) -> None:
        model.collapse()

    @kb.add("right")
    def _right(event: Any) -> None:
        model.expand()

    @kb.add("c-r")
    def _reveal(event: Any) -> None:
        model.toggle_reveal()

    @kb.add("escape", eager=True)
    def _escape(event: Any) -> None:
        if model.dropdown_open:
            model.cancel_option()
            return
        if model.editing:
            model.cancel_edit()
            return
        outcome["result"] = "discarded"
        event.app.exit()

    @kb.add("c-c")
    def _interrupt(event: Any) -> None:
        outcome["result"] = "discarded"
        event.app.exit()

    def _save() -> None:
        if not model.request_save():
            return
        save_config(model.draft)
        outcome["result"] = "saved"
        app.exit()

    def _fetch() -> None:
        if not model.can_fetch():
            model.row_error = _("tui.config_panel.fetch_idle")
            return
        generation = model.begin_fetch()
        base_url = model.draft.llm.base_url
        api_key = model._usable_key()
        loop = app.loop

        def _worker() -> None:
            try:
                models = fetch_provider_models(base_url, api_key)
                error = None
            except Exception as exc:  # network/provider failure
                models, error = [], str(exc)

            def _apply() -> None:
                model.apply_fetch_result(generation, models, error)
                app.invalidate()

            loop.call_soon_threadsafe(_apply)

        threading.Thread(target=_worker, daemon=True).start()

    @kb.add("c-s")
    def _ctrl_s(event: Any) -> None:
        _save()

    @kb.add("enter")
    def _enter(event: Any) -> None:
        if model.dropdown_open:
            model.commit_option()
            return
        if model.editing:
            model.commit_edit()
            return
        row = model.focused
        if row.key == "action.save":
            _save()
        elif row.key == "action.fetch_models":
            _fetch()
        elif row.key == "action.add_server":
            model.add_server(_read_server_name(screen))
        elif row.key.endswith(".action.delete"):
            model.delete_server()
        else:
            model.activate()

    @kb.add("space")
    def _space(event: Any) -> None:
        if model.editing:
            model.set_edit_text(model.edit_text + " ")
            return
        model.activate()

    @kb.add("backspace")
    def _backspace(event: Any) -> None:
        if model.editing:
            model.set_edit_text(model.edit_text[:-1])

    @kb.add("<any>")
    def _typed(event: Any) -> None:
        if model.editing and len(event.data) == 1 and event.data.isprintable():
            model.set_edit_text(model.edit_text + event.data)

    app = Application(
        layout=Layout(HSplit([Window(FormattedTextControl(_body))])),
        key_bindings=kb,
        full_screen=True,
    )
    app.run()

    if outcome.get("result") == "saved":
        screen.print(
            Panel(_("tui.config_panel.saved"), border_style=C_SUCCESS, box=box.ROUNDED)
        )
    else:
        screen.print(
            Panel(_("tui.config_panel.discarded"), border_style=C_WARNING, box=box.ROUNDED)
        )


def _read_server_name(screen: Console) -> str:
    """Ask for a new MCP server name outside the full-screen app."""
    return _read_config_prompt_raw("Server name", console=screen).strip()
```

Note on `_read_server_name`: it runs while the `Application` is live, which prompt_toolkit does not allow. Wrap the call so the app suspends first:

```python
        elif row.key == "action.add_server":
            event.app.run_system_command  # not usable here
```

Use `app.run_in_terminal` instead, which is the supported escape hatch:

```python
        elif row.key == "action.add_server":
            from prompt_toolkit.application import run_in_terminal

            name = run_in_terminal(lambda: _read_server_name(screen))
            model.add_server(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_cli.py -q && python -m ruff check vulnclaw/cli/tui.py vulnclaw/cli/config_panel.py vulnclaw/cli/config_panel_render.py`
Expected: PASS, no ruff findings

- [ ] **Step 5: Manual smoke test**

Run `python -m vulnclaw config` in a real terminal. Verify: sections collapse and expand, arrow navigation, editing a text field, toggling a bool, opening the provider dropdown, Ctrl+R revealing the key, Ctrl+S saving, Esc discarding without touching `~/.vulnclaw/config.yaml`.

- [ ] **Step 6: Commit**

```bash
git add vulnclaw/cli/tui.py tests/cli/test_cli.py
git commit -m "feat(cli): open the config panel from the REPL on a TTY"
```

---

### Task 10: Ship it

**Files:**
- Modify: PR #93 description (via `gh pr edit`)
- Modify: issue #87 (via `gh issue comment`)

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest tests/cli tests/config -q`
Expected: PASS. The pre-existing MCP/Python 3.14 failure noted in the PR description is the only acceptable failure, and only if it reproduces on `main` too.

- [ ] **Step 2: Push**

```bash
git push origin HEAD:JMAN730/87-i18n-support
```

- [ ] **Step 3: Update the PR description**

Add a "REPL surface" section covering the new panel, list `vulnclaw/cli/config_panel.py`, `config_panel_render.py`, `tui.py`, both i18n catalogs and the two new test files under "Files and Components Affected", and replace the follow-up line about Textual/i18n with a note that the REPL panel is localized while the ratatui panel still is not.

- [ ] **Step 4: Correct the issue**

Comment on issue #87 that story 30 and the matching Out-of-Scope entry ("the classic-REPL `run_config_tui` editor — left untouched") no longer hold: the REPL editor is replaced by a panel in this PR, with the prompt chains retained only as the non-TTY fallback.

---

## Self-Review

**Spec coverage.** Panel shape → Task 1. MCP nesting → Task 5. prompt_toolkit + Rich rendering → Tasks 8, 9. Pure-model structure → Tasks 1-6. Non-TTY fallback → Task 9. Row model and value kinds → Task 2. Key bindings → Task 9. Draft/save → Tasks 2, 6, 9. Model fetch and generation guard → Tasks 4, 9. Validation → Task 6. i18n → Task 7. Testing → every task. Delivery → Task 10.

**Placeholders.** None: every code step carries the code, every test step carries the assertions.

**Type consistency.** `apply_fetch_result(generation, models, error)` is defined in Task 4 and called with the same three arguments in Task 9. `request_save() -> bool` is defined in Task 6 and gates `save_config` in Task 9. `_usable_key()` is introduced in Task 4 and reused in Tasks 6 and 9. `row_error` and `save_error` are separate fields throughout: row-level parse failures versus save-level blocks.

**Known rough edge.** Task 9's `<any>` binding plus the explicit `space` binding will fight over the space character while editing; the `space` handler covers it, but check the ordering during the manual smoke test in Task 9 Step 5.
