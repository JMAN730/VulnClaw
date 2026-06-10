"""Target history overview panel."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.widgets import Static


class OverviewPanel(Static):
    """Panel showing target history summary."""

    DEFAULT_CSS = """
    OverviewPanel {
        height: auto;
        margin: 0 0;
        background: $panel;
        padding: 0 1;
    }
    """

    def __init__(self, target: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._target = target

    def update_target(self, target: str) -> None:
        self._target = target
        self._refresh()

    def on_mount(self) -> None:
        self._refresh()

    def _empty_table(self, text: str) -> Table:
        table = Table.grid(expand=True)
        table.add_column("", ratio=1)
        table.add_column("", ratio=2)
        table.add_row(Text(text, style="dim"), "")
        return table

    def _refresh(self) -> None:
        if not self._target:
            self.update(self._empty_table("尚未设置目标"))
            return

        from vulnclaw.target_state.store import get_target_state_preview, list_target_snapshots

        try:
            preview = get_target_state_preview(self._target)
            snapshots = list_target_snapshots(self._target)
        except Exception:
            self.update(self._empty_table("读取目标历史失败"))
            return

        if preview is None:
            self.update(self._empty_table("无历史记录"))
            return

        table = Table.grid(expand=True)
        table.add_column("指标", ratio=1)
        table.add_column("值", ratio=2)

        table.add_row("阶段", str(preview.get("phase", "unknown")))
        table.add_row("快照数", str(len(snapshots)))
        table.add_row("发现数", str(preview.get("findings_count", 0)))
        table.add_row("已验证", str(preview.get("verified_count", 0)))
        table.add_row("待验证", str(preview.get("pending_count", 0)))

        violations = preview.get("constraint_violations", [])
        if not isinstance(violations, list):
            violations = []
        table.add_row("违规数", str(len(violations)))

        self.update(table)
