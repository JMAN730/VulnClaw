"""/sc command — scan configuration (floating modal or quick args).

When invoked without arguments, opens a ScanConfigScreen modal.
When invoked with ``--key value`` arguments, updates config directly.
"""

from __future__ import annotations

import shlex


class ScanConfigCommand:
    """Manage scan configuration via modal or quick args."""

    async def run(self, args: str, **context) -> None:
        """Route the command: modal vs quick args."""
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        if not args.strip():
            # No args → open modal
            await self._open_modal(chat_pane)
            return

        # Has args → parse quick params
        self._handle_quick_args(args, chat_pane)

    @staticmethod
    async def _open_modal(chat_pane) -> None:
        """Push the ScanConfigScreen modal."""
        from vulnclaw.cli.textui.components.scan_config_screen import ScanConfigScreen
        screen = ScanConfigScreen(chat_pane._state.to_dict())
        chat_pane.add_system_message("[dim]打开扫描配置面板...[/]")
        result = await chat_pane.app.push_screen_wait(screen)
        if result:
            chat_pane._apply_sc_config(result)
            if result.get("_execute"):
                chat_pane.add_system_message("[green]✓ 配置已保存并启动任务[/]")
            else:
                chat_pane.add_system_message("[green]✓ 配置已保存[/]")
        # Re-focus input after modal is dismissed
        chat_pane._focus_input()

    @staticmethod
    def _handle_quick_args(args: str, chat_pane) -> None:
        """Parse --key value pairs and apply directly."""
        try:
            tokens = shlex.split(args)
        except ValueError:
            chat_pane.add_system_message(f"[red]参数解析错误: {args}[/]")
            return

        config: dict[str, str] = {}
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("--"):
                key = token[2:].replace("-", "_")
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    config[key] = tokens[i + 1]
                    i += 2
                else:
                    config[key] = ""
                    i += 1
            else:
                i += 1

        if not config:
            chat_pane.add_system_message(f"[red]无效参数: {args}[/]")
            chat_pane.add_system_message("[dim]用法: /sc --target <目标> --port <端口>[/]")
            return

        chat_pane._state.update_from_dict(config)
        chat_pane.add_system_message("[green]✓ 配置已更新[/]")
