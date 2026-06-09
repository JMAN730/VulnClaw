"""Dashboard main screen — sidebar + ContentSwitcher layout."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    ContentSwitcher,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

from vulnclaw import __version__
from vulnclaw.cli.textui.widgets.exec_pane import ExecutionPane
from vulnclaw.cli.textui.widgets.input_bar import InputBar
from vulnclaw.cli.textui.widgets.overview import OverviewPanel
from vulnclaw.cli.textui.widgets.scope import ScopePanel
from vulnclaw.cli.textui.widgets.sidebar import Sidebar
from vulnclaw.cli.textui.widgets.status_bar import StatusBar
from vulnclaw.cli.tui import MODES, TuiState, build_runtime_diagnostic, build_task_draft
from vulnclaw.config.settings import load_config


class MainScreen(Screen):
    """Dashboard main screen with sidebar navigation and content panes."""

    BINDINGS = [
        Binding("tab", "next_pane", "切换", priority=True),
        Binding("shift+tab", "prev_pane", "切换", priority=True),
        Binding("ctrl+c", "quit_or_interrupt", "退出", priority=True),
        Binding("q", "quit_app", "退出"),
    ]

    MENU_ORDER = ["dashboard", "target", "mode", "scope", "execution",
                  "history", "report", "diagnostic", "config"]

    DEFAULT_CSS = """
    MainScreen {
        background: $surface;
    }

    #main-layout {
        height: 1fr;
    }

    #content-area {
        height: 1fr;
        padding: 0 1;
    }

    /* Dashboard pane */
    #dashboard-pane {
        height: 1fr;
        padding: 0 1;
    }

    /* Form panes */
    .form-pane {
        height: 1fr;
        padding: 0 2;
    }

    .form-pane > Label {
        height: 1;
        text-style: bold;
        color: cyan;
        margin: 0 0;
    }

    .form-pane > Input {
        margin: 0 0;
    }

    /* Info panes */
    .info-pane {
        height: 1fr;
        padding: 0 2;
    }

    #hint-bar {
        height: 1;
        padding: 0 1;
        dock: bottom;
        text-align: left;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.state = TuiState()
        self.config = load_config()
        self._exec_pane: ExecutionPane | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            yield Sidebar()
            with ContentSwitcher(id="content-area", initial="dashboard"):
                yield self._build_dashboard_pane()
                yield self._build_target_pane()
                yield self._build_mode_pane()
                yield self._build_scope_pane()
                yield Static("请先设置目标后查看历史记录",
                             id="history-pane", classes="info-pane")
                yield Static("请先执行任务后生成报告",
                             id="report-pane", classes="info-pane")
                yield self._build_diagnostic_pane()
                yield Static(
                    "LLM 配置\n\n请在终端使用 `vulnclaw config` 命令配置 LLM",
                    id="config-pane", classes="info-pane")
        yield InputBar()
        yield Static(f"[dim]v{__version__}  ·  Tab 切换  ·  q 退出[/]", id="hint-bar")

    def _build_dashboard_pane(self) -> Vertical:
        return Vertical(
            StatusBar(
                target=self.state.target,
                mode=self.state.mode,
                model=getattr(self.config.llm, "model", "unknown"),
                provider=getattr(self.config.llm, "provider", "unknown"),
                id="dashboard-status",
            ),
            Horizontal(
                Vertical(
                    OverviewPanel(target=self.state.target, id="dashboard-overview"),
                    id="dashboard-overview-col",
                ),
                Vertical(
                    ScopePanel(
                        only_host=self.state.only_host,
                        only_port=self.state.only_port,
                        only_path=self.state.only_path,
                        blocked_host=self.state.blocked_host,
                        blocked_path=self.state.blocked_path,
                        allow_actions=", ".join(self.state.allow_actions),
                        block_actions=", ".join(self.state.block_actions),
                        id="dashboard-scope",
                    ),
                    id="dashboard-scope-col",
                ),
                id="dashboard-content",
            ),
            id="dashboard-pane",
        )

    def _build_target_pane(self) -> Vertical:
        return Vertical(
            Label("设置目标地址 (IP/域名):"),
            Input(placeholder="例如 192.168.1.1 或 example.com", id="target-input"),
            id="target-pane", classes="form-pane",
        )

    def _build_mode_pane(self) -> Vertical:
        return Vertical(
            Label("选择检查模式:"),
            RadioSet(*[
                RadioButton(f"{m.label} - {m.description}",
                            value=k == "standard")
                for k, m in MODES.items()
            ], id="mode-radioset"),
            id="mode-pane", classes="form-pane",
        )

    def _build_scope_pane(self) -> Vertical:
        return Vertical(
            Label("边界约束设置 (留空 = 不限制):"),
            Input(placeholder="仅允许主机 (IP/域名)", id="scope-only-host"),
            Input(placeholder="仅允许端口", id="scope-only-port"),
            Input(placeholder="仅允许路径", id="scope-only-path"),
            Input(placeholder="禁止主机", id="scope-blocked-host"),
            Input(placeholder="禁止路径", id="scope-blocked-path"),
            id="scope-pane", classes="form-pane",
        )

    def _build_diagnostic_pane(self) -> Vertical:
        diagnostic = build_runtime_diagnostic(self.config)
        lines = [
            f"Python: {diagnostic.python_version}",
            f"Node.js: {diagnostic.node_version}",
            f"npx: {diagnostic.npx_status}",
            f"uvx: {diagnostic.uvx_status}",
            f"nmap: {diagnostic.nmap_status}",
            f"Provider: {diagnostic.provider}",
            f"Model: {diagnostic.model}",
            f"API Key: {'已配置' if diagnostic.api_key_configured else '未配置'}",
            f"MCP: {diagnostic.mcp_total_services} total / {diagnostic.mcp_running_services} running",
        ]
        text = "\n".join(f"• {line}" for line in lines)
        return Vertical(
            Label("运行时诊断信息"),
            Static(text),
            id="diagnostic-pane", classes="info-pane",
        )

    # ── Navigation ─────────────────────────────────────────────────────

    def action_next_pane(self) -> None:
        """Tab: cycle to next sidebar item."""
        sb = self.query_one(Sidebar)
        idx = self.MENU_ORDER.index(sb.active_id)
        next_id = self.MENU_ORDER[(idx + 1) % len(self.MENU_ORDER)]
        self._navigate(next_id)

    def action_prev_pane(self) -> None:
        """Shift+Tab: cycle to previous sidebar item."""
        sb = self.query_one(Sidebar)
        idx = self.MENU_ORDER.index(sb.active_id)
        prev_id = self.MENU_ORDER[(idx - 1) % len(self.MENU_ORDER)]
        self._navigate(prev_id)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_quit_or_interrupt(self) -> None:
        """Ctrl+C: interrupt execution if running, otherwise quit."""
        sw = self.query_one(ContentSwitcher)
        if sw.current == "execution-pane" and self._exec_pane:
            self._exec_pane.interrupt()
        else:
            self.app.exit()

    def _navigate(self, pane_id: str) -> None:
        """Switch to a content pane and update sidebar highlight."""
        sw = self.query_one(ContentSwitcher)
        target = "execution-pane" if pane_id == "execution" else f"{pane_id}-pane"
        if pane_id == "execution" and not self._exec_pane:
            return  # execution not started yet
        sw.current = target
        sb = self.query_one(Sidebar)
        sb.active_id = pane_id
        if pane_id == "dashboard":
            self._refresh_dashboard()

    def _launch_execution(self) -> None:
        """Create and navigate to execution pane."""
        draft = build_task_draft(self.state)
        exec_pane = ExecutionPane(draft, self.config, id="execution-pane")
        self._exec_pane = exec_pane

        sw = self.query_one(ContentSwitcher)
        # Remove old execution pane if exists
        for old in sw.query("#execution-pane"):
            old.remove()
        sw.mount(exec_pane)
        sw.current = "execution-pane"

        sb = self.query_one(Sidebar)
        sb.active_id = "execution"

    # ── Sidebar navigation handler ────────────────────────────────────

    def on_sidebar_navigate(self, event: Sidebar.Navigate) -> None:
        """Handle sidebar navigation events."""
        item_id = event.item_id
        if item_id == "execution":
            if not self.state.target.strip():
                self._notify("请先设置目标")
                return
            self._launch_execution()
        else:
            self._navigate(item_id)

    # ── Form handlers ──────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle form input submissions."""
        input_id = event.input.id

        if input_id == "target-input":
            value = event.value.strip()
            if value:
                self.state.target = value
                self._navigate("dashboard")
                self._notify(f"目标已设置: {value}")

        elif input_id in ("scope-only-host", "scope-only-port", "scope-only-path",
                          "scope-blocked-host", "scope-blocked-path"):
            self.state.only_host = self.query_one("#scope-only-host", Input).value.strip()
            self.state.only_port = self.query_one("#scope-only-port", Input).value.strip()
            self.state.only_path = self.query_one("#scope-only-path", Input).value.strip()
            self.state.blocked_host = self.query_one("#scope-blocked-host", Input).value.strip()
            self.state.blocked_path = self.query_one("#scope-blocked-path", Input).value.strip()
            self._notify("范围已保存")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle mode selection."""
        if event.radio_set.id == "mode-radioset":
            label = str(event.pressed.label).split(" - ")[0]
            for key, mode in MODES.items():
                if mode.label == label:
                    self.state.mode = key  # type: ignore[assignment]
                    self._navigate("dashboard")
                    self._notify(f"模式已选择: {mode.label}")
                    break

    # ── Execution completion handlers ──────────────────────────────────

    def on_execution_pane_completed(self) -> None:
        """Handle execution completion."""
        self._notify("任务执行完成", timeout=5)

    def on_execution_pane_interrupted(self) -> None:
        """Handle execution interruption."""
        self._notify("任务已中断", timeout=5)

    # ── Input bar ──────────────────────────────────────────────────────

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Handle natural language input."""
        self._notify(f"处理指令: {event.text}")

    # ── Helpers ────────────────────────────────────────────────────────

    def _refresh_dashboard(self) -> None:
        """Refresh dashboard content after state changes."""
        status_bar = self.query_one("#dashboard-status", StatusBar)
        status_bar.update_target(self.state.target)
        status_bar.update_mode(self.state.mode)

        overview = self.query_one("#dashboard-overview", OverviewPanel)
        overview.update_target(self.state.target)

        scope = self.query_one("#dashboard-scope", ScopePanel)
        scope.update_scope(
            only_host=self.state.only_host,
            only_port=self.state.only_port,
            only_path=self.state.only_path,
            blocked_host=self.state.blocked_host,
            blocked_path=self.state.blocked_path,
            allow_actions=", ".join(self.state.allow_actions),
            block_actions=", ".join(self.state.block_actions),
        )

    def _notify(self, message: str, timeout: int = 5) -> None:
        self.app.notify(message, timeout=timeout)
