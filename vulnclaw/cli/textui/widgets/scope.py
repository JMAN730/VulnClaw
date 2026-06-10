"""Scope / boundary constraints panel."""

from __future__ import annotations

from rich.table import Table
from textual.widgets import Static


class ScopePanel(Static):
    """Panel showing boundary constraints configuration."""

    DEFAULT_CSS = """
    ScopePanel {
        height: auto;
        margin: 0 0;
        background: $panel;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        only_host: str = "",
        only_port: str = "",
        only_path: str = "",
        blocked_host: str = "",
        blocked_path: str = "",
        allow_actions: str = "",
        block_actions: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._only_host = only_host
        self._only_port = only_port
        self._only_path = only_path
        self._blocked_host = blocked_host
        self._blocked_path = blocked_path
        self._allow_actions = allow_actions
        self._block_actions = block_actions

    def update_scope(
        self,
        only_host: str = "",
        only_port: str = "",
        only_path: str = "",
        blocked_host: str = "",
        blocked_path: str = "",
        allow_actions: str = "",
        block_actions: str = "",
    ) -> None:
        self._only_host = only_host
        self._only_port = only_port
        self._only_path = only_path
        self._blocked_host = blocked_host
        self._blocked_path = blocked_path
        self._allow_actions = allow_actions
        self._block_actions = block_actions
        self._refresh()

    def on_mount(self) -> None:
        self._refresh()

    def _val(self, v: str) -> str:
        return v if v else "—"

    def _refresh(self) -> None:
        table = Table.grid(expand=True)
        table.add_column("约束", ratio=1)
        table.add_column("值", ratio=3)

        table.add_row("仅允许主机", self._val(self._only_host))
        table.add_row("仅允许端口", self._val(self._only_port))
        table.add_row("仅允许路径", self._val(self._only_path))
        table.add_row("禁止主机", self._val(self._blocked_host))
        table.add_row("禁止路径", self._val(self._blocked_path))
        table.add_row("允许操作", self._val(self._allow_actions))
        table.add_row("禁止操作", self._val(self._block_actions))

        self.update(table)
