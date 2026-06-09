"""Execution pane — embeddable streaming execution view."""

from __future__ import annotations

import asyncio

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from vulnclaw.agent.core import AgentCore
from vulnclaw.cli.textui.widgets.log_panel import LogPanel
from vulnclaw.cli.textui.widgets.tool_panel import ToolPanel
from vulnclaw.cli.tui import TuiTaskDraft
from vulnclaw.config.schema import VulnClawConfig


class ExecutionPane(Static):
    """Embeddable streaming execution view — lives inside ContentSwitcher."""

    DEFAULT_CSS = """
    ExecutionPane {
        height: 1fr;
    }

    #exec-header {
        height: auto;
        margin: 0 1;
    }

    #exec-content {
        height: 1fr;
    }

    #exec-log {
        width: 2fr;
        height: 1fr;
    }

    #exec-tools {
        width: 1fr;
        height: 1fr;
    }

    #findings-badge {
        height: auto;
        margin: 0 1;
    }
    """

    class Completed(Message):
        """Posted when execution finishes."""

    class Interrupted(Message):
        """Posted when execution is interrupted."""

    def __init__(self, draft: TuiTaskDraft, config: VulnClawConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self._draft = draft
        self._config = config
        self._interrupted = False
        self._completed = False
        self._task: asyncio.Task | None = None
        self._agent: AgentCore | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._render_header(), id="exec-header")
        with Horizontal(id="exec-content"):
            with Static(id="exec-log"):
                yield LogPanel(title="")
            with Static(id="exec-tools"):
                yield ToolPanel()
        yield Static(self._render_findings_badge(), id="findings-badge")

    def on_mount(self) -> None:
        """Start execution."""
        self._task = asyncio.create_task(self._run_execution())

    def _render_header(self) -> Panel:
        return Panel(
            f"目标: [bold cyan]{self._draft.target}[/]  |  "
            f"模式: [bold green]{self._draft.command}[/]  |  轮次: [bold yellow]0[/]",
            title="执行中",
            border_style="green",
        )

    def _render_findings_badge(self) -> Panel:
        return Panel(
            Text("发现: 0  已验证: 0  待验证: 0", style="bold"),
            title="发现统计",
            border_style="magenta",
        )

    async def _run_execution(self) -> None:
        mcp_manager = getattr(self._config, "mcp_manager", None)
        self._agent = AgentCore(self._config, mcp_manager=mcp_manager)

        log_panel = self.query_one(LogPanel)
        tool_panel = self.query_one(ToolPanel)
        header = self.query_one("#exec-header", Static)
        findings_badge = self.query_one("#findings-badge", Static)

        def on_token(token: str) -> None:
            log_panel.write(token)

        def on_tool_call(tool_info: dict) -> None:
            tool_panel.add_pending(tool_info)

        def on_tool_result(result: dict) -> None:
            tool_panel.update_status(result)

        def on_step(round_num: int, result) -> None:
            findings_count = len(self._agent.context.state.findings) if self._agent else 0
            verified_count = sum(
                1 for f in self._agent.context.state.findings if getattr(f, "verified", False)
            ) if self._agent else 0
            pending_count = findings_count - verified_count

            header.update(Panel(
                f"目标: [bold cyan]{self._draft.target}[/]  |  "
                f"模式: [bold green]{self._draft.command}[/]  |  "
                f"轮次: [bold yellow]{round_num}[/]  |  "
                f"阶段: [bold]{result.phase}[/]",
                title="执行中",
                border_style="green",
            ))
            findings_badge.update(Panel(
                Text(f"发现: {findings_count}  已验证: {verified_count}  待验证: {pending_count}",
                     style="bold"),
                title="发现统计",
                border_style="magenta",
            ))
            if not result.should_continue:
                self._completed = True

        try:
            from vulnclaw.agent.loop_controller import auto_pentest

            results = await auto_pentest(
                self._agent,
                self._draft.target,
                target=self._draft.target,
                max_rounds=15,
                on_step=on_step,
                on_token=on_token,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )

            self._completed = True
            log_panel.write(f"\n[完成] 自动渗透测试结束，共执行 {len(results)} 轮")
            header.update(Panel(
                f"目标: [bold cyan]{self._draft.target}[/]  |  状态: [bold green]已完成[/]",
                title="执行完成",
                border_style="green",
            ))
            self.post_message(self.Completed())

        except asyncio.CancelledError:
            self._interrupted = True
            log_panel.write("\n[中断] 用户中断任务")
            header.update(Panel(
                f"目标: [bold cyan]{self._draft.target}[/]  |  状态: [bold red]已中断[/]",
                title="执行中断",
                border_style="red",
            ))
            self.post_message(self.Interrupted())

        except Exception as exc:
            log_panel.write(f"\n[错误] {exc}")
            import traceback
            log_panel.write(traceback.format_exc())
            header.update(Panel(
                f"目标: [bold cyan]{self._draft.target}[/]  |  状态: [bold red]出错[/]",
                title="执行错误",
                border_style="red",
            ))

    def interrupt(self) -> None:
        """Interrupt execution."""
        if self._task and not self._task.done():
            self._task.cancel()
            self._interrupted = True
