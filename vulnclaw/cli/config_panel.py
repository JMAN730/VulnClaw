"""Pure state model for the classic-REPL configuration panel.

This module deliberately imports no UI library and performs no I/O, so the
whole panel's behavior can be tested without a terminal.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
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


class _Keep:
    """Sentinel: blank input leaves the current value alone."""


_KEEP = _Keep()


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


class ConfigPanelModel:
    """Draft-editing state machine behind the classic-REPL config panel."""

    def __init__(self, config: VulnClawConfig) -> None:
        self.draft = copy.deepcopy(config)
        self._expanded: set[str] = set()
        self._focus_key = "llm"
        self._edit: dict[str, Any] | None = None
        self._reveal = False
        self.row_error = ""

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
