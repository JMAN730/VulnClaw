"""Settings panel — graphical configuration modal.

Opened via ``/settings``.  Shows all configurable fields grouped by
category.  Saves to the YAML config file on confirmation.
"""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch

from vulnclaw.config.settings import load_config, save_config, list_providers
from vulnclaw.i18n import _

logger = logging.getLogger(__name__)

# ── Dropdown option tuples ─────────────────────────────────────

LANGUAGE_OPTIONS = [
    (_("tui.component.settings_screen.lang_auto"), "auto"),
    (_("tui.component.settings_screen.lang_zh"), "zh"),
    (_("tui.component.settings_screen.lang_en"), "en"),
]

RENDER_OPTIONS = [
    (_("tui.component.settings_screen.render_markdown"), "markdown"),
    (_("tui.component.settings_screen.render_plain"), "plain"),
]

POPUP_MODE_OPTIONS = [
    (_("tui.component.settings_screen.popup_embed"), "embed"),
    (_("tui.component.settings_screen.popup_separate"), "separate"),
]


def _provider_options() -> list[tuple[str, str]]:
    """Return provider dropdown options from presets + custom."""
    options = []
    for p in list_providers():
        options.append((f"{p['label']}  ({p['provider']})", p["provider"]))
    options.append(("Custom (custom)", "custom"))
    return options


class SettingsScreen(ModalScreen[bool | None]):
    """Graphical configuration panel.

    Returns
    -------
    ``True`` if the user saved, ``None`` if cancelled.
    """

    BINDINGS = [
        ("escape", "save_and_close", _("tui.component.settings_screen.save_and_close")),
    ]

    DEFAULT_CSS = """
    Screen {
        align: center middle;
    }

    #settings-panel {
        width: 80%;
        height: auto;
        max-height: 90%;
        border: thick $secondary;
        background: $surface;
        padding: 1 2;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }

    #settings-body {
        height: auto;
        max-height: 65vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 0 1;
    }

    .section {
        height: auto;
        margin: 1 0;
    }

    .section-title {
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }

    .field-row {
        height: auto;
        margin: 0 0 1 0;
        align: left middle;
    }

    .field-label {
        width: 18;
        text-align: right;
        padding: 0 1 0 0;
        color: $text;
    }

    .field-input {
        width: 1fr;
    }

    .field-select {
        width: 1fr;
    }

    .field-switch {
        width: auto;
    }

    #settings-actions {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    #settings-actions > Button {
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._config = load_config()
        self._providers = _provider_options()

    # ── Compose ─────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel"):
            yield Static(_("tui.component.settings_screen.title"), id="settings-title")
            with Vertical(id="settings-body"):
                # ── LLM Provider ──
                with Vertical(classes="section"):
                    yield Static(_("tui.component.settings_screen.section_llm_provider"),
                                 classes="section-title")
                    yield self._field_select(
                        "tui.component.settings_screen.provider",
                        "provider",
                        self._providers,
                        self._config.llm.provider,
                    )
                    yield self._field_input(
                        "tui.component.settings_screen.api_key",
                        "api_key",
                        self._config.llm.api_key,
                        password=True,
                    )
                    yield self._field_input(
                        "tui.component.settings_screen.base_url",
                        "base_url",
                        self._config.llm.base_url,
                    )
                    yield self._field_input(
                        "tui.component.settings_screen.model",
                        "model",
                        self._config.llm.model,
                    )

                # ── LLM Parameters ──
                with Vertical(classes="section"):
                    yield Static(_("tui.component.settings_screen.section_llm_params"),
                                 classes="section-title")
                    yield self._field_input(
                        "tui.component.settings_screen.max_tokens",
                        "max_tokens",
                        str(self._config.llm.max_tokens),
                    )
                    yield self._field_input(
                        "tui.component.settings_screen.temperature",
                        "temperature",
                        str(self._config.llm.temperature),
                    )

                # ── Display ──
                with Vertical(classes="section"):
                    yield Static(_("tui.component.settings_screen.section_display"),
                                 classes="section-title")
                    yield self._field_select(
                        "tui.component.settings_screen.render_mode",
                        "render_mode",
                        RENDER_OPTIONS,
                        self._config.session.render_mode,
                    )
                    yield self._field_switch(
                        "tui.component.settings_screen.show_thinking",
                        "show_thinking",
                        self._config.session.show_thinking,
                    )

                # ── Session ──
                with Vertical(classes="section"):
                    yield Static(_("tui.component.settings_screen.section_session"),
                                 classes="section-title")
                    yield self._field_switch(
                        "tui.component.settings_screen.auto_save",
                        "auto_save",
                        self._config.session.auto_save,
                    )
                    yield self._field_input(
                        "tui.component.settings_screen.max_rounds",
                        "max_rounds",
                        str(self._config.session.max_rounds),
                    )
                    yield self._field_select(
                        "tui.component.settings_screen.language",
                        "language",
                        LANGUAGE_OPTIONS,
                        self._config.session.language,
                    )
                    yield self._field_select(
                        "tui.component.settings_screen.popup_mode",
                        "popup_mode",
                        POPUP_MODE_OPTIONS,
                        self._config.session.popup_mode,
                    )

            # ── Actions ──
            with Horizontal(id="settings-actions"):
                yield Button(_("tui.component.settings_screen.btn_save"),
                             id="btn-save-save", variant="primary")
                yield Button(_("tui.component.settings_screen.btn_cancel"),
                             id="btn-save-cancel")

    # ── Field helpers ───────────────────────────────────────────

    @staticmethod
    def _field_input(
        label_key: str,
        field_id: str,
        value: str,
        *,
        password: bool = False,
    ) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Input(
                value=value,
                id=f"setting-{field_id}",
                password=password,
                classes="field-input",
            ),
            classes="field-row",
        )

    @staticmethod
    def _field_select(
        label_key: str,
        field_id: str,
        options: list[tuple[str, str]],
        selected: str,
    ) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Select(
                options,
                value=selected,
                id=f"setting-{field_id}",
                classes="field-select",
            ),
            classes="field-row",
        )

    @staticmethod
    def _field_switch(
        label_key: str,
        field_id: str,
        value: bool,
    ) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Switch(value=value, id=f"setting-{field_id}", classes="field-switch"),
            classes="field-row",
        )

    # ── Button press ────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-save-save":
            self._save_and_close()
        elif btn_id == "btn-save-cancel":
            self.dismiss(None)

    # ── Key binding ─────────────────────────────────────────────

    def action_save_and_close(self) -> None:
        """ESC also saves (double-guarantee)."""
        self._save_and_close()

    # ── Save ────────────────────────────────────────────────────

    def _save_and_close(self) -> None:
        """Read form, persist to YAML, dismiss with ``True``."""
        old_lang = self._config.session.language
        self._read_form_into_config()
        new_lang = self._config.session.language

        try:
            save_config(self._config)
            self.notify(_("tui.component.settings_screen.saved"), timeout=3)
        except Exception as exc:
            logger.exception("Failed to save config")
            self.notify(f"Save failed: {exc}", severity="error", timeout=5)
            return

        # If language changed, re-init the global translator now
        if new_lang != old_lang:
            from vulnclaw.i18n import set_language
            set_language(new_lang)

        self.dismiss(True)

    def _read_form_into_config(self) -> None:
        """Copy form values back to the config object."""

        # LLM provider
        self._config.llm.provider = self._select_val("setting-provider")
        self._config.llm.api_key = self._input_val("setting-api_key")
        self._config.llm.base_url = self._input_val("setting-base_url")
        self._config.llm.model = self._input_val("setting-model")

        # LLM params
        self._config.llm.max_tokens = self._int_val("setting-max_tokens", 4096)
        self._config.llm.temperature = self._float_val("setting-temperature", 0.1)

        # Display
        self._config.session.render_mode = self._select_val("setting-render_mode")
        self._config.session.show_thinking = self._switch_val("setting-show_thinking")

        # Session
        self._config.session.auto_save = self._switch_val("setting-auto_save")
        self._config.session.max_rounds = self._int_val("setting-max_rounds", 15)
        self._config.session.language = self._select_val("setting-language")
        self._config.session.popup_mode = self._select_val("setting-popup_mode")

    # ── Widget readers ──────────────────────────────────────────

    def _input_val(self, widget_id: str) -> str:
        try:
            return self.query_one(f"#{widget_id}", Input).value.strip()
        except Exception:
            return ""

    def _int_val(self, widget_id: str, default: int) -> int:
        raw = self._input_val(widget_id)
        try:
            return int(raw)
        except (ValueError, TypeError):
            return default

    def _float_val(self, widget_id: str, default: float) -> float:
        raw = self._input_val(widget_id)
        try:
            return float(raw)
        except (ValueError, TypeError):
            return default

    def _select_val(self, widget_id: str) -> str:
        try:
            sel = self.query_one(f"#{widget_id}", Select)
            return sel.value if sel.value is not None else ""
        except Exception:
            return ""

    def _switch_val(self, widget_id: str) -> bool:
        try:
            sw = self.query_one(f"#{widget_id}", Switch)
            return sw.value
        except Exception:
            return False
