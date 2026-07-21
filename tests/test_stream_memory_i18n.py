"""i18n coverage for stream-sink labels and memory tool returns."""

from __future__ import annotations

import asyncio
import io
from unittest.mock import MagicMock, patch

from rich.console import Console

from vulnclaw.cli._helpers import TerminalStreamSink
from vulnclaw.i18n import _


def test_stream_sink_labels_english(i18n_language):
    i18n_language("en")
    output = io.StringIO()
    sink = TerminalStreamSink(Console(file=output, force_terminal=True))
    sink.on_tool_call("traffic_list", "{}")
    sink.on_tool_result("No matching captures.")
    text = output.getvalue()
    assert "Calling tool: traffic_list" in text
    assert "Tool result: No matching captures." in text
    assert "调用工具" not in text
    assert "工具结果" not in text


def test_stream_sink_labels_chinese(i18n_language):
    i18n_language("zh")
    output = io.StringIO()
    sink = TerminalStreamSink(Console(file=output, force_terminal=True))
    sink.on_tool_call("traffic_list", "{}")
    sink.on_tool_result("没有匹配的抓包记录。")
    text = output.getvalue()
    assert "调用工具: traffic_list" in text
    assert "工具结果: 没有匹配的抓包记录。" in text


def test_memory_retrieve_not_found_english(i18n_language):
    i18n_language("en")
    from vulnclaw.mcp.lifecycle import MCPLifecycleManager

    mgr = MCPLifecycleManager(MagicMock())
    with patch("vulnclaw.agent.memory.MemoryStore") as store_cls:
        store_cls.return_value.retrieve.return_value = None
        result = asyncio.run(mgr._call_memory("retrieve", {"key": "current_target"}))
    assert result == _("memory.retrieve.not_found")
    assert "Not found" in result
    assert "未找到" not in result


def test_memory_retrieve_not_found_chinese(i18n_language):
    i18n_language("zh")
    from vulnclaw.mcp.lifecycle import MCPLifecycleManager

    mgr = MCPLifecycleManager(MagicMock())
    with patch("vulnclaw.agent.memory.MemoryStore") as store_cls:
        store_cls.return_value.retrieve.return_value = None
        result = asyncio.run(mgr._call_memory("retrieve", {"key": "current_target"}))
    assert "未找到" in result
