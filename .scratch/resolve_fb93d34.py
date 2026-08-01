"""Resolve fb93d34 cherry-pick conflicts."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- test_provider_models.py ---
tp = ROOT / "tests" / "test_provider_models.py"
text = tp.read_text(encoding="utf-8")
old = '''<<<<<<< HEAD
    ) == ["a-model", "z-model"]

def test_provider_discovery_catalogs_have_matching_keys_and_placeholders():
    """OpenRouter/model-discovery i18n keys stay in sync across en/zh."""
    from pathlib import Path
    from string import Formatter

    def _catalog(lang: str) -> dict[str, str]:
        path = Path(__file__).resolve().parents[1] / "vulnclaw" / "i18n" / f"{lang}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _placeholders(value: str) -> set[str]:
        return {name for _, name, _, _ in Formatter().parse(value) if name}

    prefixes = ("tui.model_discovery_", "tui.openrouter_warning")
    english = {
        key: value for key, value in _catalog("en").items() if key.startswith(prefixes)
    }
    chinese = {
        key: value for key, value in _catalog("zh").items() if key.startswith(prefixes)
    }

    assert english.keys() == chinese.keys()
    assert {
        key: (_placeholders(english[key]), _placeholders(chinese[key]))
        for key in english
        if _placeholders(english[key]) != _placeholders(chinese[key])
    } == {}

=======
    ) == ["a-model", "a-model", "z-model"]
>>>>>>> fb93d34 (fix: close openrouter review gaps)
'''
new = '''    ) == ["a-model", "a-model", "z-model"]


def test_provider_discovery_catalogs_have_matching_keys_and_placeholders():
    """OpenRouter/model-discovery i18n keys stay in sync across en/zh."""
    from pathlib import Path
    from string import Formatter

    def _catalog(lang: str) -> dict[str, str]:
        path = Path(__file__).resolve().parents[1] / "vulnclaw" / "i18n" / f"{lang}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _placeholders(value: str) -> set[str]:
        return {name for _, name, _, _ in Formatter().parse(value) if name}

    prefixes = ("tui.model_discovery_", "tui.openrouter_warning")
    english = {
        key: value for key, value in _catalog("en").items() if key.startswith(prefixes)
    }
    chinese = {
        key: value for key, value in _catalog("zh").items() if key.startswith(prefixes)
    }

    assert english.keys() == chinese.keys()
    assert {
        key: (_placeholders(english[key]), _placeholders(chinese[key]))
        for key in english
        if _placeholders(english[key]) != _placeholders(chinese[key])
    } == {}
'''
if old not in text:
    raise SystemExit("test_provider_models conflict block not found")
tp.write_text(text.replace(old, new, 1), encoding="utf-8")
print("test_provider_models fixed")

# --- zh.json ---
zh_path = ROOT / "vulnclaw" / "i18n" / "zh.json"
zh = zh_path.read_text(encoding="utf-8")
zh_pat = re.compile(
    r"<<<<<<< HEAD\n"
    r'  "tui\.openrouter_warning": "[^"]*"\n'
    r"=======\n"
    r".*?"
    r">>>>>>> fb93d34 \(fix: close openrouter review gaps\)\n?",
    re.S,
)
zh_rep = (
    '  "tui.model_discovery_selected_incompatible": '
    '"警告：当前 Model ID 不在兼容目录中。自主运行前请选择列表中的模型；'
    '仅在接受运行时失败关闭拒绝时保留该 ID。",\n'
    '  "tui.model_manual_entry": "手动输入 Model ID…",\n'
    '  "tui.openrouter_warning": '
    '"OpenRouter 可能在多个上游提供商之间路由请求。'
    '发送敏感的授权目标数据前，请核验账户隐私与 ZDR 偏好。"\n'
)
zh_new, n = zh_pat.subn(zh_rep, zh, count=1)
if n != 1:
    raise SystemExit(f"zh.json replace count={n}")
json.loads(zh_new)
zh_path.write_text(zh_new, encoding="utf-8")
print("zh.json fixed")

# --- llm_client.py ---
llm_path = ROOT / "vulnclaw" / "agent" / "llm_client.py"
llm = llm_path.read_text(encoding="utf-8")

# conflict 1: imports
llm = llm.replace(
    "<<<<<<< HEAD\nimport logging\n=======\nimport math\n"
    ">>>>>>> fb93d34 (fix: close openrouter review gaps)\n",
    "import logging\nimport math\n",
    1,
)

# conflict 2+3 in call_llm_stream: take theirs iter helper
llm = llm.replace(
    "<<<<<<< HEAD\n"
    "        response = client.chat.completions.create(**kwargs, stream=True)\n"
    "=======\n"
    ">>>>>>> fb93d34 (fix: close openrouter review gaps)\n",
    "",
    1,
)
llm = llm.replace(
    "<<<<<<< HEAD\n"
    "        # 自动适配 sync/async Stream（sync Stream 用 _AsyncIterWrapper 包装）\n"
    "        _stream = _ensure_async_iter(response)\n"
    "        if _stream is None:\n"
    "            raise ValueError(\"LLM response is not a valid stream object\")\n"
    "        async for chunk in _stream:\n"
    "=======\n"
    "        async for chunk in _iter_stream_chunks_with_retries(\n"
    "            agent,\n"
    "            kwargs,\n"
    "            \"stream\",\n"
    "        ):\n"
    ">>>>>>> fb93d34 (fix: close openrouter review gaps)\n",
    "        async for chunk in _iter_stream_chunks_with_retries(\n"
    "            agent,\n"
    "            kwargs,\n"
    "            \"stream\",\n"
    "        ):\n",
    1,
)

# conflicts in call_llm_auto_stream: keep HEAD structure (ours), drop theirs old streaming body
# Conflict A
llm = llm.replace(
    "<<<<<<< HEAD\n"
    "        for _tool_round in range(_resolve_auto_tool_rounds(agent, max_tool_rounds) + 1):\n"
    "            messages = _fit_context_window(agent, messages)\n"
    "            message = await _stream_chat_completion_message(agent, messages, tools, stream_sink)\n"
    "            tool_calls = list(getattr(message, \"tool_calls\", None) or [])\n"
    "            if not tool_calls:\n"
    "                return extract_response(message)\n"
    "=======\n"
    "        # First LLM call with streaming\n"
    "        stream_sink.on_status(\"Thinking...\")\n"
    ">>>>>>> fb93d34 (fix: close openrouter review gaps)\n",
    "        for _tool_round in range(_resolve_auto_tool_rounds(agent, max_tool_rounds) + 1):\n"
    "            messages = _fit_context_window(agent, messages)\n"
    "            message = await _stream_chat_completion_message(agent, messages, tools, stream_sink)\n"
    "            tool_calls = list(getattr(message, \"tool_calls\", None) or [])\n"
    "            if not tool_calls:\n"
    "                return extract_response(message)\n",
    1,
)

# Conflict B
llm = llm.replace(
    "<<<<<<< HEAD\n"
    "            tool_results, skipped_info = await handle_tool_calls_with_results(agent, message)\n"
    "            last_tool_results = tool_results\n"
    "            last_skipped_info = skipped_info\n"
    "            last_assistant_text = message.content or \"\"\n"
    "            for item in tool_results:\n"
    "                if isinstance(item, dict) and \"content\" in item:\n"
    "                    stream_sink.on_tool_result(item[\"content\"])\n"
    "=======\n"
    "        async for chunk in _iter_stream_chunks_with_retries(\n"
    "            agent,\n"
    "            kwargs,\n"
    "            \"auto stream\",\n"
    "        ):\n"
    "            if chunk.choices and len(chunk.choices) > 0:\n"
    "                delta = chunk.choices[0].delta\n"
    ">>>>>>> fb93d34 (fix: close openrouter review gaps)\n",
    "            tool_results, skipped_info = await handle_tool_calls_with_results(agent, message)\n"
    "            last_tool_results = tool_results\n"
    "            last_skipped_info = skipped_info\n"
    "            last_assistant_text = message.content or \"\"\n"
    "            for item in tool_results:\n"
    "                if isinstance(item, dict) and \"content\" in item:\n"
    "                    stream_sink.on_tool_result(item[\"content\"])\n",
    1,
)

# Conflict C: keep ours, drop large theirs block
pat_c = re.compile(
    r"<<<<<<< HEAD\n"
    r"            assistant_message = _assistant_tool_message\(extract_response\(message\), executed_tool_calls\)\n"
    r"            tool_messages = _tool_result_messages\(tool_results\)\n"
    r"            messages\.append\(assistant_message\)\n"
    r"            messages\.extend\(tool_messages\)\n"
    r"            if include_history:\n"
    r"                _append_context_message\(agent, assistant_message\)\n"
    r"                for tool_message in tool_messages:\n"
    r"                    _append_context_message\(agent, tool_message\)\n"
    r"=======\n"
    r".*?"
    r">>>>>>> fb93d34 \(fix: close openrouter review gaps\)\n",
    re.S,
)
rep_c = (
    "            assistant_message = _assistant_tool_message(extract_response(message), executed_tool_calls)\n"
    "            tool_messages = _tool_result_messages(tool_results)\n"
    "            messages.append(assistant_message)\n"
    "            messages.extend(tool_messages)\n"
    "            if include_history:\n"
    "                _append_context_message(agent, assistant_message)\n"
    "                for tool_message in tool_messages:\n"
    "                    _append_context_message(agent, tool_message)\n"
)
llm2, n = pat_c.subn(rep_c, llm, count=1)
if n != 1:
    raise SystemExit(f"llm conflict C replace count={n}")
llm = llm2

# Update _stream_chat_completion_message to use iter helper (fb93d34 intent)
old_stream = '''    kwargs = build_chat_completion_kwargs(agent, messages, tools)
    stream_sink.on_status("Thinking...")
    response = await _create_stream_with_retries(agent, kwargs, "auto stream")

    full_text = ""
    reasoning_buffer = ""
    tool_calls_chunks: list[dict] = []
    stream = _ensure_async_iter(response)
    if stream is None:
        raise ValueError("LLM response is not a valid stream object")

    async for chunk in stream:
        _validate_provider_response(
            agent,
            chunk,
            partial_text=full_text,
            require_choices=False,
        )
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
'''
new_stream = '''    kwargs = build_chat_completion_kwargs(agent, messages, tools)
    stream_sink.on_status("Thinking...")

    full_text = ""
    reasoning_buffer = ""
    tool_calls_chunks: list[dict] = []

    async for chunk in _iter_stream_chunks_with_retries(
        agent,
        kwargs,
        "auto stream",
    ):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
'''
if old_stream not in llm:
    raise SystemExit("_stream_chat_completion_message block not found for upgrade")
llm = llm.replace(old_stream, new_stream, 1)

# Remove unused client var warning in call_llm_stream if client only used for removed create
# Keep client if still used later in fallback path — check
# Actually call_llm_stream often has fallback using client - leave it.

for marker in ("<<<<<<<", "=======", ">>>>>>>"):
    if marker in llm:
        raise SystemExit(f"llm still has {marker}")

llm_path.write_text(llm, encoding="utf-8")
print("llm_client fixed")

# compile check
import py_compile
py_compile.compile(str(llm_path), doraise=True)
print("py_compile ok")
