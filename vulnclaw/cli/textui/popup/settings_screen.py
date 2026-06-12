"""Standalone settings configuration screen for the child popup window.

This is a small Textual App that runs in a separate terminal window,
communicating with the main process via file IPC (PopupIPC).
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static, Switch

from vulnclaw.cli.textui.popup.ipc import PopupIPC
from vulnclaw.i18n import _

# ── Dropdown options ───────────────────────────────────────────

LANGUAGE_OPTIONS = [
    (_("tui.popup.settings_screen.lang_auto"), "auto"),
    (_("tui.popup.settings_screen.lang_zh"), "zh"),
    (_("tui.popup.settings_screen.lang_en"), "en"),
]

RENDER_OPTIONS = [
    (_("tui.popup.settings_screen.render_markdown"), "markdown"),
    (_("tui.popup.settings_screen.render_plain"), "plain"),
]

POPUP_MODE_OPTIONS = [
    (_("tui.popup.settings_screen.popup_embed"), "embed"),
    (_("tui.popup.settings_screen.popup_separate"), "separate"),
]


class PopupSettingsApp(App):
    """Textual App for the independent settings popup.

    Parameters
    ----------
    session_dir:
        Path to the IPC session directory.
    """

    BINDINGS = [
        ("escape", "action_close", _("tui.popup.settings_screen.close")),
        ("ctrl+s", "action_save", _("tui.popup.settings_screen.save")),
    ]

    TITLE = _("tui.popup.settings_screen.title")

    DEFAULT_CSS = """
    Screen {
        align: center middle;
    }

    #root {
        width: 90%;
        height: 90%;
        border: thick $secondary;
        background: $surface;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }

    #body {
        height: auto;
        max-height: 70vh;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 0 1;
        scrollbar-gutter: stable;
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

    #actions {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    #actions > Button {
        margin: 0 1;
    }
    """

    def __init__(self, session_dir: str) -> None:
        super().__init__()
        self._ipc = PopupIPC(session_dir, side="child")
        self._data: dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="root"):
            yield Static(_("tui.popup.settings_screen.popup_title"), id="title")
            with Vertical(id="body"):
                # ── LLM Provider ──
                with Vertical(classes="section"):
                    yield Static(_("tui.popup.settings_screen.section_llm_provider"),
                                 classes="section-title")
                    yield self._field_input("tui.popup.settings_screen.provider",
                                            "provider", self._data.get("llm_provider", ""))
                    yield self._field_input("tui.popup.settings_screen.api_key",
                                            "api_key", self._data.get("llm_api_key", ""),
                                            password=True)
                    yield self._field_input("tui.popup.settings_screen.base_url",
                                            "base_url", self._data.get("llm_base_url", ""))
                    yield self._field_input("tui.popup.settings_screen.model",
                                            "model", self._data.get("llm_model", ""))

                # ── LLM Parameters ──
                with Vertical(classes="section"):
                    yield Static(_("tui.popup.settings_screen.section_llm_params"),
                                 classes="section-title")
                    yield self._field_input("tui.popup.settings_screen.max_tokens",
                                            "max_tokens",
                                            str(self._data.get("llm_max_tokens", "4096")))
                    yield self._field_input("tui.popup.settings_screen.temperature",
                                            "temperature",
                                            str(self._data.get("llm_temperature", "0.1")))

                # ── Display ──
                with Vertical(classes="section"):
                    yield Static(_("tui.popup.settings_screen.section_display"),
                                 classes="section-title")
                    yield self._field_select("tui.popup.settings_screen.render_mode",
                                             "render_mode",
                                             RENDER_OPTIONS,
                                             self._data.get("session_render_mode", "plain"))
                    yield self._field_switch("tui.popup.settings_screen.show_thinking",
                                             "show_thinking",
                                             bool(self._data.get("session_show_thinking", False)))

                # ── Session ──
                with Vertical(classes="section"):
                    yield Static(_("tui.popup.settings_screen.section_session"),
                                 classes="section-title")
                    yield self._field_switch("tui.popup.settings_screen.auto_save",
                                             "auto_save",
                                             bool(self._data.get("session_auto_save", True)))
                    yield self._field_input("tui.popup.settings_screen.max_rounds",
                                            "max_rounds",
                                            str(self._data.get("session_max_rounds", "15")))
                    yield self._field_select("tui.popup.settings_screen.language",
                                             "language",
                                             LANGUAGE_OPTIONS,
                                             self._data.get("session_language", "auto"))
                    yield self._field_select("tui.popup.settings_screen.popup_mode",
                                             "popup_mode",
                                             POPUP_MODE_OPTIONS,
                                             self._data.get("session_popup_mode", "embed"))

            # ── Buttons ──
            with Horizontal(id="actions"):
                yield Button(_("tui.popup.settings_screen.btn_save"),
                             id="btn-save", variant="primary")
                yield Button(_("tui.popup.settings_screen.btn_close"),
                             id="btn-close")

    # ── Field helpers ───────────────────────────────────────────

    @staticmethod
    def _field_input(label_key: str, field_id: str, value: str,
                     *, password: bool = False) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Input(value=value, id=f"setting-{field_id}",
                  password=password, classes="field-input"),
            classes="field-row",
        )

    @staticmethod
    def _field_select(label_key: str, field_id: str,
                      options: list[tuple[str, str]], selected: str) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Select(options, value=selected, id=f"setting-{field_id}",
                   classes="field-select"),
            classes="field-row",
        )

    @staticmethod
    def _field_switch(label_key: str, field_id: str, value: bool) -> Vertical:
        return Vertical(
            Static(_(label_key), classes="field-label"),
            Switch(value=value, id=f"setting-{field_id}", classes="field-switch"),
            classes="field-row",
        )

    # ── Lifecycle ───────────────────────────────────────────────

    def on_mount(self) -> None:
        """Load initial data from IPC."""
        self._try_read_ipc(retries=10)

    def _try_read_ipc(self, retries: int = 10) -> None:
        """Attempt to read IPC data; retry with delay if file not ready."""
        payload = self._ipc.read()
        if payload is not None:
            self._data = payload.get("data", {})
            self._refresh_form()
        elif retries > 0:
            self.set_timer(0.1, lambda: self._try_read_ipc(retries - 1))

    def _refresh_form(self) -> None:
        """Push current data into form widgets."""
        for field_id, key in (
            ("setting-provider",     "llm_provider"),
            ("setting-api_key",      "llm_api_key"),
            ("setting-base_url",     "llm_base_url"),
            ("setting-model",        "llm_model"),
            ("setting-max_tokens",   "llm_max_tokens"),
            ("setting-temperature",  "llm_temperature"),
            ("setting-render_mode",  "session_render_mode"),
            ("setting-show_thinking","session_show_thinking"),
            ("setting-auto_save",    "session_auto_save"),
            ("setting-max_rounds",   "session_max_rounds"),
            ("setting-language",     "session_language"),
            ("setting-popup_mode",   "session_popup_mode"),
        ):
            val = self._data.get(key, "")
            try:
                self.query_one(f"#{field_id}", Input).value = str(val)
            except Exception:
                pass

        for field_id, key in ("setting-show_thinking", "session_show_thinking"), \
                              ("setting-auto_save", "session_auto_save"):
            try:
                self.query_one(f"#{field_id}", Switch).value = bool(self._data.get(key, False))
            except Exception:
                pass

        for field_id, key, opts in (
            ("setting-render_mode", "session_render_mode", RENDER_OPTIONS),
            ("setting-language",    "session_language",    LANGUAGE_OPTIONS),
            ("setting-popup_mode",  "session_popup_mode",  POPUP_MODE_OPTIONS),
        ):
            val = self._data.get(key, "")
            for display, opt_val in opts:
                if opt_val == val:
                    try:
                        self.query_one(f"#{field_id}", Select).value = val
                    except Exception:
                        pass
                    break

    # ── Button handlers ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-save":
            self._do_save()
            return  # keep open, independent window

        if btn_id == "btn-close":
            self._do_close()
            return

    # ── Key bindings ────────────────────────────────────────────

    def action_save(self) -> None:
        """Ctrl+S — sync to main, keep popup open."""
        self._do_save()

    def action_close(self) -> None:
        """ESC — sync data and close."""
        self._do_close()

    # ── Save / Close helpers ────────────────────────────────────

    def _do_save(self) -> None:
        """Sync data to main, apply language change locally."""
        old_lang = self._data.get("session_language", "auto")
        data = self._collect()
        new_lang = data.get("session_language", "auto")

        self._ipc.write(data, action="save")
        self.notify(_("tui.popup.settings_screen.saved"), timeout=2)

        if new_lang != old_lang:
            from vulnclaw.i18n import set_language
            set_language(new_lang)
            self.recompose()

    def _do_close(self) -> None:
        """Sync data and close."""
        old_lang = self._data.get("session_language", "auto")
        data = self._collect()
        new_lang = data.get("session_language", "auto")

        self._ipc.write(data, action="close")

        if new_lang != old_lang:
            from vulnclaw.i18n import set_language
            set_language(new_lang)

        self.exit()

    # ── Collect ─────────────────────────────────────────────────

    def _collect(self) -> dict[str, Any]:
        data = {
            "llm_provider":       self._input_val("setting-provider"),
            "llm_api_key":        self._input_val("setting-api_key"),
            "llm_base_url":       self._input_val("setting-base_url"),
            "llm_model":          self._input_val("setting-model"),
            "llm_max_tokens":     self._int_val("setting-max_tokens", 4096),
            "llm_temperature":    self._float_val("setting-temperature", 0.1),
            "session_render_mode":  self._select_val("setting-render_mode"),
            "session_show_thinking": self._switch_val("setting-show_thinking"),
            "session_auto_save":   self._switch_val("setting-auto_save"),
            "session_max_rounds":  self._int_val("setting-max_rounds", 15),
            "session_language":    self._select_val("setting-language"),
            "session_popup_mode":  self._select_val("setting-popup_mode"),
        }
        return data

    # ── Widget readers ──────────────────────────────────────────

    def _input_val(self, widget_id: str) -> str:
        try:
            return self.query_one(f"#{widget_id}", Input).value.strip()
        except Exception:
            return ""

    def _int_val(self, widget_id: str, default: int) -> int:
        try:
            return int(self._input_val(widget_id))
        except (ValueError, TypeError):
            return default

    def _float_val(self, widget_id: str, default: float) -> float:
        try:
            return float(self._input_val(widget_id))
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
            return self.query_one(f"#{widget_id}", Switch).value
        except Exception:
            return False
