"""Standalone SC configuration screen for the child popup window.

This is a small Textual App that runs in a separate terminal window,
communicating with the main process via file IPC (PopupIPC).
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from vulnclaw.cli.textui.popup.ipc import PopupIPC
from vulnclaw.i18n import _
from vulnclaw.cli.tui import MODES


class PopupSCApp(App):
    """Textual App for the independent SC configuration popup.

    Parameters
    ----------
    session_dir:
        Path to the IPC session directory.
    """

    BINDINGS = [
        ("escape", "action_close", _("tui.popup.sc_screen.close")),
        ("ctrl+s", "action_save", _("tui.popup.sc_screen.save")),
        ("ctrl+e", "action_execute", _("tui.popup.sc_screen.execute")),
    ]

    AUTO_FOCUS = "#sc-target"

    TITLE = _("tui.popup.sc_screen.title")

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

    .section > Input {
        margin: 0 0 1 0;
        width: 1fr;
    }

    #sc-mode {
        height: auto;
        margin: 0 0 1 0;
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
            yield Static(_("tui.popup.sc_screen.sc_config_title"), id="title")
            with Vertical(id="body"):
                # ── Target ──
                with Vertical(classes="section"):
                    yield Static("目标设置", classes="section-title")
                    yield Input(
                        value=self._data.get("target", ""),
                        placeholder="目标地址 (IP/域名/URL)",
                        id="sc-target",
                    )

                # ── Boundary constraints ──
                with Vertical(classes="section"):
                    yield Static(_("tui.popup.sc_screen.boundary_constraints"),
                                 classes="section-title")
                    for input_id, placeholder in (
                        ("sc-only-host", _("tui.popup.sc_screen.only_host_placeholder")),
                        ("sc-only-port", _("tui.popup.sc_screen.only_port_placeholder")),
                        ("sc-only-path", _("tui.popup.sc_screen.only_path_placeholder")),
                        ("sc-blocked-host", _("tui.popup.sc_screen.blocked_host_placeholder")),
                        ("sc-blocked-path", _("tui.popup.sc_screen.blocked_path_placeholder")),
                    ):
                        key = input_id.replace("sc-", "").replace("-", "_")
                        yield Input(
                            value=str(self._data.get(key, "")),
                            placeholder=placeholder,
                            id=input_id,
                        )

                # ── Actions ──
                with Vertical(classes="section"):
                    yield Static("操作限制", classes="section-title")
                    yield Input(
                        value=self._data.get("allow_actions", ""),
                        placeholder="允许操作 (逗号分隔, 例如 recon,scan)",
                        id="sc-allow-actions",
                    )
                    yield Input(
                        value=self._data.get("block_actions", ""),
                        placeholder="禁止操作 (逗号分隔, 例如 exploit)",
                        id="sc-block-actions",
                    )

                # ── Mode ──
                with Vertical(classes="section"):
                    yield Static("检查模式", classes="section-title")
                    current_mode = self._data.get("mode", "standard")
                    yield RadioSet(
                        *[
                            RadioButton(
                                f"{m.label} - {m.description}",
                                value=k == current_mode,
                            )
                            for k, m in MODES.items()
                        ],
                        id="sc-mode",
                    )

            # ── Buttons ──
            with Horizontal(id="actions"):
                yield Button(_("tui.popup.sc_screen.btn_execute"),
                             id="btn-execute", variant="primary")
                yield Button(_("tui.popup.sc_screen.btn_save"),
                             id="btn-save")
                yield Button(_("tui.popup.sc_screen.btn_close"),
                             id="btn-close")

    def on_mount(self) -> None:
        """Load initial data from IPC and start polling."""
        payload = self._ipc.read()
        if payload:
            self._data = payload.get("data", {})
            self._refresh_form()

        self.set_interval(1.0, self._poll_main)

    def _refresh_form(self) -> None:
        """Refresh form fields from the current data."""
        # Update Input widgets
        for field_id in (
            "sc-target", "sc-only-host", "sc-only-port", "sc-only-path",
            "sc-blocked-host", "sc-blocked-path",
            "sc-allow-actions", "sc-block-actions",
        ):
            key = field_id.replace("sc-", "").replace("-", "_")
            value = self._data.get(key, "")
            try:
                self.query_one(f"#{field_id}", Input).value = str(value)
            except Exception:
                pass

        # Restore mode
        current_mode = self._data.get("mode", "standard")
        try:
            mode_set = self.query_one("#sc-mode", RadioSet)
            for i, btn in enumerate(mode_set.children):
                if isinstance(btn, RadioButton):
                    label = str(btn.label).split(" - ")[0]
                    for key, m in MODES.items():
                        if m.label == label and key == current_mode:
                            mode_set.pressed_index = i
                            break
        except Exception:
            pass

    async def _poll_main(self) -> None:
        """Poll for updates from the main process."""
        payload = self._ipc.read()
        if payload:
            self._data = payload.get("data", {})
            self._refresh_form()

    # ── Button handlers ─────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id
        data = self._collect()

        if btn_id == "btn-save":
            self._ipc.write(data, action="save")
            self.notify(_("tui.popup.sc_screen.synced_to_main"), timeout=2)
            return  # stay open, independent window

        if btn_id == "btn-execute":
            self._ipc.write(data, action="execute")
            self.notify(_("tui.popup.sc_screen.config_saved_executing"), timeout=2)
            self.exit()
            return

        if btn_id == "btn-close":
            self._ipc.write(data, action="close")
            self.exit()
            return

    # ── Key bindings ────────────────────────────────────────────

    def action_save(self) -> None:
        """Ctrl+S — sync to main, keep popup open."""
        data = self._collect()
        self._ipc.write(data, action="save")
        self.notify(_("tui.popup.sc_screen.synced_to_main"), timeout=2)

    def action_execute(self) -> None:
        """Ctrl+E — sync and execute, then close."""
        self._ipc.write(self._collect(), action="execute")
        self.notify(_("tui.popup.sc_screen.config_saved_executing"), timeout=2)
        self.exit()

    def action_close(self) -> None:
        """ESC — sync data and close."""
        self._ipc.write(self._collect(), action="close")
        self.exit()

    # ── Helpers ─────────────────────────────────────────────────

    def _collect(self) -> dict[str, Any]:
        """Read all form values."""
        mode = "standard"
        try:
            mode_set = self.query_one("#sc-mode", RadioSet)
            pressed = mode_set.pressed_index
            for i, btn in enumerate(mode_set.children):
                if isinstance(btn, RadioButton) and i == pressed:
                    label = str(btn.label).split(" - ")[0]
                    for key, m in MODES.items():
                        if m.label == label:
                            mode = key
                            break
        except Exception:
            pass

        return {
            "target": self._input_val("sc-target"),
            "only_host": self._input_val("sc-only-host"),
            "only_port": self._input_val("sc-only-port"),
            "only_path": self._input_val("sc-only-path"),
            "blocked_host": self._input_val("sc-blocked-host"),
            "blocked_path": self._input_val("sc-blocked-path"),
            "allow_actions": self._input_val("sc-allow-actions"),
            "block_actions": self._input_val("sc-block-actions"),
            "mode": mode,
        }

    def _input_val(self, input_id: str) -> str:
        try:
            return self.query_one(f"#{input_id}", Input).value.strip()
        except Exception:
            return ""
