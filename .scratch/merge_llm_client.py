"""Merge OpenRouter helpers from eb8b05b onto upstream HEAD llm_client.py."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
head = (ROOT / ".scratch" / "llm_head.py").read_text(encoding="utf-8")
helpers = (ROOT / ".scratch" / "openrouter_helpers.py").read_text(encoding="utf-8").rstrip() + "\n\n"

# --- imports ---
# HEAD has: asyncio, inspect, json, logging, SimpleNamespace, typing...
# Need: re, sys, datetime, email.utils for OpenRouter helpers
if "import logging" not in head:
    raise SystemExit("unexpected HEAD imports")
head = head.replace(
    "import json\nimport logging\nfrom types import SimpleNamespace\n",
    "import json\nimport logging\nimport re\nimport sys\n"
    "from datetime import datetime, timezone\n"
    "from email.utils import parsedate_to_datetime\n"
    "from types import SimpleNamespace\n",
    1,
)

# --- insert helpers after _DEFAULT_AUTO_TOOL_ROUNDS ---
marker = "_DEFAULT_AUTO_TOOL_ROUNDS = 6\n"
if marker not in head:
    raise SystemExit("missing _DEFAULT_AUTO_TOOL_ROUNDS marker")
head = head.replace(marker, marker + "\n" + helpers, 1)

# --- patch _call_with_persistent_retries to route OpenRouter ---
old_call = '''async def _call_with_persistent_retries(
    agent: AgentContext, request_fn, stage_label: str, max_retries: int = 20
) -> tuple[Any, int]:
    """Keep retrying retriable LLM calls until success, max retries, or manual interruption.

    Args:
        max_retries: Maximum number of retry attempts before raising RuntimeError.
                     Default is 20 (at 5s intervals = ~100s total wait).

    Returns:
        (response, retry_attempts)

    Raises:
        RuntimeError: If max_retries is exceeded.
    """
    loop = asyncio.get_running_loop()
'''

new_call = '''async def _call_with_persistent_retries(
    agent: AgentContext, request_fn, stage_label: str, max_retries: int = 20
) -> tuple[Any, int]:
    """Keep retrying retriable LLM calls until success, max retries, or manual interruption.

    Args:
        max_retries: Maximum number of retry attempts before raising RuntimeError.
                     Default is 20 (at 5s intervals = ~100s total wait).

    Returns:
        (response, retry_attempts)

    Raises:
        RuntimeError: If max_retries is exceeded.
    """
    if _provider_name(agent) == "openrouter":
        return await _call_openrouter_with_bounded_retries(
            agent,
            request_fn,
            stage_label,
        )

    loop = asyncio.get_running_loop()
'''
if old_call not in head:
    raise SystemExit("could not find _call_with_persistent_retries preamble")
head = head.replace(old_call, new_call, 1)

# --- patch _stream_chat_completion_message to use OpenRouter stream create + validate ---
old_stream = '''async def _stream_chat_completion_message(
    agent: AgentContext,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    stream_sink: "StreamSink",
) -> Any:
    """Run one streaming Chat Completions request and return a message-like object."""

    kwargs = build_chat_completion_kwargs(agent, messages, tools)
    stream_sink.on_status("Thinking...")
    response = agent._get_client().chat.completions.create(**kwargs, stream=True)

    full_text = ""
    reasoning_buffer = ""
    tool_calls_chunks: list[dict] = []
    stream = _ensure_async_iter(response)
    if stream is None:
        raise ValueError("LLM response is not a valid stream object")

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
'''

new_stream = '''async def _stream_chat_completion_message(
    agent: AgentContext,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    stream_sink: "StreamSink",
) -> Any:
    """Run one streaming Chat Completions request and return a message-like object."""

    kwargs = build_chat_completion_kwargs(agent, messages, tools)
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
if old_stream not in head:
    raise SystemExit("could not find _stream_chat_completion_message preamble")
head = head.replace(old_stream, new_stream, 1)

# --- re-raise OpenRouterResponseError in call_llm_auto exception handler ---
# Find the autonomous loop except Exception and prepend OpenRouter re-raise
old_auto_exc = '''        except Exception as exc:
            if last_tool_results is not None:
                fallback = _format_tool_results_fallback(
                    last_tool_results,
                    last_skipped_info,
                    assistant_text=last_assistant_text,
                )
                return _prepend_retry_notice(
                    f"{fallback}\\n[llm follow-up failed] {exc}",
                    retry_attempts_total,
                )
            raise
        retry_attempts_total += retry_attempts
'''
new_auto_exc = '''        except OpenRouterResponseError:
            raise
        except Exception as exc:
            if last_tool_results is not None:
                fallback = _format_tool_results_fallback(
                    last_tool_results,
                    last_skipped_info,
                    assistant_text=last_assistant_text,
                )
                return _prepend_retry_notice(
                    f"{fallback}\\n[llm follow-up failed] {exc}",
                    retry_attempts_total,
                )
            raise
        retry_attempts_total += retry_attempts
'''
if old_auto_exc not in head:
    raise SystemExit("could not find call_llm_auto exception block")
head = head.replace(old_auto_exc, new_auto_exc, 1)

# --- call_llm_auto_stream: re-raise OpenRouter in outer except ---
# HEAD has: except (NotImplementedError, ValueError, Exception) as e:
# Add OpenRouter before that by catching it specifically earlier... actually OpenRouter
# is a subclass of RuntimeError/Exception so it would be swallowed. Need to re-raise.
old_stream_exc = '''    except (NotImplementedError, ValueError, Exception) as e:
        error_text = str(e).lower()
        if last_tool_results is not None:
'''
new_stream_exc = '''    except OpenRouterResponseError:
        raise
    except (NotImplementedError, ValueError, Exception) as e:
        error_text = str(e).lower()
        if last_tool_results is not None:
'''
count = head.count(old_stream_exc)
if count != 1:
    raise SystemExit(f"call_llm_auto_stream except count={count}")
head = head.replace(old_stream_exc, new_stream_exc, 1)

# sanity
for marker in ("<<<<<<<", "=======", ">>>>>>>"):
    if marker in head:
        raise SystemExit(f"conflict marker remains: {marker}")
for needed in (
    "OpenRouterResponseError",
    "_call_openrouter_with_bounded_retries",
    "_create_stream_with_retries",
    "_validate_provider_response",
    "_DEFAULT_AUTO_TOOL_ROUNDS",
    "_resolve_auto_tool_rounds",
    "_stream_chat_completion_message",
):
    if needed not in head:
        raise SystemExit(f"missing symbol: {needed}")

out = ROOT / "vulnclaw" / "agent" / "llm_client.py"
out.write_text(head, encoding="utf-8")
print(f"wrote {out} ({len(head.splitlines())} lines)")
