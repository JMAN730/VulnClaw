"""File read tool — read file contents from the local filesystem."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from vulnclaw.cli.textui.tools.base import BaseTool, ToolResult, ToolStatus


class FileReadTool(BaseTool):
    """Read a file from the local filesystem."""

    name = "read_file"
    description = "读取本地文件的内容"
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径",
            },
        },
        "required": ["path"],
    }

    async def run(self, inputs: dict[str, Any]) -> ToolResult:
        path_str = inputs.get("path", "")
        if not path_str:
            return ToolResult(status=ToolStatus.ERROR, error="未提供文件路径")

        start = time.monotonic()
        try:
            file_path = Path(path_str).expanduser().resolve()
            if not file_path.exists():
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"文件不存在: {path_str}",
                    duration_s=round(time.monotonic() - start, 2),
                )
            if not file_path.is_file():
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"不是文件: {path_str}",
                    duration_s=round(time.monotonic() - start, 2),
                )

            content = file_path.read_text("utf-8", errors="replace")
            return ToolResult(
                status=ToolStatus.DONE,
                output=content[:10000],
                duration_s=round(time.monotonic() - start, 2),
            )
        except Exception as exc:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )


# Singleton
file_read_tool = FileReadTool()
