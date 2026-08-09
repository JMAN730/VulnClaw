"""Pure state model for the classic-REPL configuration panel.

This module deliberately imports no UI library and performs no I/O, so the
whole panel's behavior can be tested without a terminal.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

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
