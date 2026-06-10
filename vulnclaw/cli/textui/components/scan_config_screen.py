"""Scan configuration modal screen — launched by /sc.

Provides a floating modal panel for configuring scan targets,
boundary constraints, mode, and action filters.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from vulnclaw.cli.tui import MODES


class ScanConfigScreen(ModalScreen[dict[str, Any] | None]):
    """Floating modal for scan configuration.

    Returns a dict of config values when the user clicks
    "执行任务" or "保存配置", or ``None`` when cancelled.
    """

    BINDINGS = [
        ("escape", "dismiss_modal", "关闭"),
    ]

    def action_dismiss_modal(self) -> None:
        """Close the config modal."""
        self.dismiss(None)

    DEFAULT_CSS = """
    ScanConfigScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #sc-panel {
        width: 70;
        height: auto;
        max-height: 90%;
        border: thick $secondary;
        background: $surface;
        padding: 1 2;
    }

    #sc-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 0 0 1 0;
    }

    #sc-body {
        height: auto;
        overflow-y: auto;
        padding: 0 1;
    }

    .sc-section {
        height: auto;
        margin: 1 0;
    }

    .sc-section-title {
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }

    .sc-section > Input {
        margin: 0 0 0 0;
    }

    #sc-mode {
        height: auto;
        margin: 0 0 1 0;
    }

    #sc-actions {
        height: auto;
        margin-top: 1;
        align: center middle;
        padding: 0 1;
    }

    #sc-actions > Button {
        margin: 0 1;
    }
    """

    def __init__(self, initial: dict[str, Any] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._initial = initial or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="sc-panel"):
            yield Static("安全扫描配置", id="sc-title")

            with Vertical(id="sc-body"):
                # ── Target ──
                with Vertical(classes="sc-section"):
                    yield Static("目标设置", classes="sc-section-title")
                    yield Input(
                        value=self._initial.get("target", ""),
                        placeholder="目标地址 (IP/域名/URL)",
                        id="sc-target",
                    )

                # ── Boundary constraints ──
                with Vertical(classes="sc-section"):
                    yield Static("边界约束", classes="sc-section-title")
                    yield Input(
                        value=self._initial.get("only_host", ""),
                        placeholder="仅允许主机 (例如 192.168.1.0/24)",
                        id="sc-only-host",
                    )
                    yield Input(
                        value=self._initial.get("only_port", ""),
                        placeholder="仅允许端口 (例如 80,443)",
                        id="sc-only-port",
                    )
                    yield Input(
                        value=self._initial.get("only_path", ""),
                        placeholder="仅允许路径 (例如 /api,/admin)",
                        id="sc-only-path",
                    )
                    yield Input(
                        value=self._initial.get("blocked_host", ""),
                        placeholder="禁止主机 (例如 10.0.0.0/8)",
                        id="sc-blocked-host",
                    )
                    yield Input(
                        value=self._initial.get("blocked_path", ""),
                        placeholder="禁止路径 (例如 /logout,/private)",
                        id="sc-blocked-path",
                    )

                # ── Actions ──
                with Vertical(classes="sc-section"):
                    yield Static("操作限制", classes="sc-section-title")
                    yield Input(
                        value=self._initial.get("allow_actions", ""),
                        placeholder="允许操作 (逗号分隔, 例如 recon,scan)",
                        id="sc-allow-actions",
                    )
                    yield Input(
                        value=self._initial.get("block_actions", ""),
                        placeholder="禁止操作 (逗号分隔, 例如 exploit)",
                        id="sc-block-actions",
                    )

                # ── Mode ──
                with Vertical(classes="sc-section"):
                    yield Static("检查模式", classes="sc-section-title")
                    current_mode = self._initial.get("mode", "standard")
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
            with Horizontal(id="sc-actions"):
                yield Button("执行任务", id="sc-execute", variant="primary")
                yield Button("保存配置", id="sc-save")
                yield Button("关闭", id="sc-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id

        if btn_id == "sc-close":
            self.dismiss(None)
            return

        try:
            config = self._collect_config()
        except Exception as exc:
            self.dismiss(None)
            return

        if btn_id == "sc-execute":
            config["_execute"] = True
            self.dismiss(config)
        elif btn_id == "sc-save":
            self.dismiss(config)

    def _collect_config(self) -> dict[str, Any]:
        """Read all form values into a dict."""
        return {
            "target": self._get_input("sc-target"),
            "only_host": self._get_input("sc-only-host"),
            "only_port": self._get_input("sc-only-port"),
            "only_path": self._get_input("sc-only-path"),
            "blocked_host": self._get_input("sc-blocked-host"),
            "blocked_path": self._get_input("sc-blocked-path"),
            "allow_actions": self._get_input("sc-allow-actions"),
            "block_actions": self._get_input("sc-block-actions"),
            "mode": self._get_mode(),
        }

    def _get_input(self, input_id: str) -> str:
        try:
            return self.query_one(f"#{input_id}", Input).value.strip()
        except Exception:
            return ""

    def _get_mode(self) -> str:
        try:
            mode_set = self.query_one("#sc-mode", RadioSet)
            pressed = mode_set.pressed_index
            for i, btn in enumerate(mode_set.children):
                if isinstance(btn, RadioButton) and i == pressed:
                    label = str(btn.label).split(" - ")[0]
                    for key, m in MODES.items():
                        if m.label == label:
                            return key
        except Exception:
            pass
        return self._initial.get("mode", "standard")
