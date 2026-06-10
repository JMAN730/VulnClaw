"""Bash tool — execute shell commands on the host system."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from vulnclaw.cli.textui.tools.base import BaseTool, ToolResult, ToolStatus


class BashTool(BaseTool):
    """Execute a shell command and capture its output."""

    name = "bash"
    description = "在 Windows 上执行 PowerShell 命令并获取输出（注意：系统为 Windows，使用 PowerShell 语法，不支持 uname、$(...) 等 Linux/bash 命令）"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
        },
        "required": ["command"],
    }

    async def run(self, inputs: dict[str, Any]) -> ToolResult:
        command = inputs.get("command", "")
        if not command:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="未提供命令",
            )

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            duration = time.monotonic() - start

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                error_out = stderr.decode("utf-8", errors="replace")
                if error_out.strip():
                    output += f"\n[stderr]\n{error_out}"

            if proc.returncode != 0:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    output=output[:10000],
                    error=f"退出码 {proc.returncode}",
                    duration_s=round(duration, 2),
                )

            return ToolResult(
                status=ToolStatus.DONE,
                output=output[:10000],
                duration_s=round(duration, 2),
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="命令执行超时 (300s)",
                duration_s=round(time.monotonic() - start, 2),
            )
        except Exception as exc:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )


# Singleton
bash_tool = BashTool()
