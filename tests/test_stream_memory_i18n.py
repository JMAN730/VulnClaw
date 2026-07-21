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


def test_memory_retrieve_preserves_falsey_value(i18n_language):
    i18n_language("en")
    from vulnclaw.mcp.lifecycle import MCPLifecycleManager

    mgr = MCPLifecycleManager(MagicMock())
    with patch("vulnclaw.agent.memory.MemoryStore") as store_cls:
        store_cls.return_value.retrieve.return_value = 0
        result = asyncio.run(mgr._call_memory("retrieve", {"key": "count"}))
    assert result == "0"
    assert "Not found" not in result


def test_transcript_fallback_localized_english(i18n_language):
    from vulnclaw.agent.llm_client import _format_tool_results_fallback

    i18n_language("en")
    out = _format_tool_results_fallback(
        [{"content": "[tool:fetch] Status: 200"}],
        ["duplicate tool call"],
    )
    assert "Provider is incompatible with standard tool-summary format" in out
    assert "Skipped this round: duplicate tool call" in out
    assert "已降级" not in out


def test_transcript_fallback_localized_chinese(i18n_language):
    from vulnclaw.agent.llm_client import _format_tool_results_fallback

    i18n_language("zh")
    out = _format_tool_results_fallback(
        [{"content": "[tool:fetch] Status: 200"}],
        [],
    )
    assert "[工具结果已处理]" in out
    assert "已降级为纯文本结果摘要" in out
    assert "[tool results processed]" not in out


def test_compress_messages_keeps_english_transcript_markers():
    from vulnclaw.agent.context import ContextManager

    summary = ContextManager._compress_messages(
        [
            {
                "role": "assistant",
                "content": "Calling tool: traffic_list({})\nTool result: [traffic] No matching captures.",
            }
        ]
    )
    assert "Calling tool: traffic_list" in summary
    assert "Tool result: [traffic]" in summary
