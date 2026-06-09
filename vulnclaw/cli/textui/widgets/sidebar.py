"""Sidebar navigation widget — fixed vertical menu with active highlight."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class SidebarItem(Static):
    """A single clickable item in the sidebar."""

    DEFAULT_CSS = """
    SidebarItem {
        height: 2;
        padding: 0 1;
        content-align: left middle;
    }
    SidebarItem:hover {
        background: $accent 15%;
    }
    SidebarItem.-active {
        background: $accent 30%;
    }
    """

    class Selected(Message):
        """Posted when this item is selected."""

        def __init__(self, item_id: str) -> None:
            super().__init__()
            self.item_id = item_id

    def __init__(self, item_id: str, label: str) -> None:
        super().__init__(id=f"sidebar-{item_id}")
        self._item_id = item_id
        self._label = label

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self.update(Text(f"  {self._label}"))

    def on_click(self) -> None:
        self.post_message(self.Selected(self._item_id))


class Sidebar(Vertical):
    """Fixed left-side navigation menu."""

    DEFAULT_CSS = """
    Sidebar {
        width: 16;
        height: 1fr;
        background: $panel;
        overflow-y: auto;
        padding: 0 0;
    }
    """

    active_id: reactive[str] = reactive("dashboard")

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, SidebarItem] = {}

    def compose(self) -> ComposeResult:
        menu_items = [
            ("dashboard", "仪表盘"),
            ("target",    "设置目标"),
            ("mode",      "选择模式"),
            ("scope",     "设置范围"),
            ("execution", "执行任务"),
            ("history",   "历史记录"),
            ("report",    "生成报告"),
            ("diagnostic","诊断信息"),
            ("config",    "LLM 配置"),
        ]
        for item_id, label in menu_items:
            item = SidebarItem(item_id, label)
            self._items[item_id] = item
            yield item

    def on_mount(self) -> None:
        self._update_highlight()

    def watch_active_id(self) -> None:
        self._update_highlight()

    def _update_highlight(self) -> None:
        for item_id, item in self._items.items():
            item.set_class(item_id == self.active_id, "-active")

    def on_sidebar_item_selected(self, event: SidebarItem.Selected) -> None:
        """Handle sidebar item selection."""
        self.active_id = event.item_id
        self.post_message(self.Navigate(event.item_id))

    class Navigate(Message):
        """Posted when the user selects a different sidebar item."""

        def __init__(self, item_id: str) -> None:
            super().__init__()
            self.item_id = item_id
