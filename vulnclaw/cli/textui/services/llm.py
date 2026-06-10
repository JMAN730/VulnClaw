"""LLM service — streaming chat completion via OpenAI API.

Wraps the core agent logic for use by the ChatPane / AgentLoop.
"""

from __future__ import annotations

import json
import platform
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI, APIError

from vulnclaw.cli.tui import MODES
from vulnclaw.config.settings import load_config


class LlmService:
    """Lightweight LLM client for the Textual TUI chat.

    Provides streaming completion with basic tool-use detection,
    delegating actual tool execution to the caller via a callback.
    """

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self._model: str = ""
        self._system_prompt: str = ""
        self._tools_supported: bool | None = None
        self._os_info = self._detect_os()

    # ── Public API ─────────────────────────────────────────────────

    async def check_tool_support(self) -> bool:
        """Proactively test whether the LLM API supports tool/function calling.

        Sends a **streaming** request with the actual tool definitions and
        immediately breaks after the first chunk.  This exercises the same
        code path as production so that any thinking-mode / tool conflict
        is triggered reliably.

        The result is cached after the first call.
        """
        if self._tools_supported is not None:
            return self._tools_supported

        client = self._get_client()
        model = self._get_model()

        test_messages: list[dict[str, Any]] = [
            {"role": "user", "content": "测试"}
        ]
        test_tools = self._build_tool_defs()

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=test_messages,
                tools=test_tools,
                stream=True,
            )
            # Consume one chunk to force the API to fully validate the request.
            # If tools conflict with thinking mode, the 400 error is raised at
            # create() time — before we even iterate.
            async for _ in stream:
                break
            self._tools_supported = True
        except APIError as exc:
            if exc.status_code == 400 and any(
                kw in str(exc).lower()
                for kw in ["reasoning_content", "thinking", "reasoning"]
            ):
                self._tools_supported = False
            else:
                # Other API errors (auth, rate-limit, etc.) — assume tools
                # supported so the user gets a clear error at chat time.
                self._tools_supported = True
        except Exception:
            # Transient errors should not block startup
            self._tools_supported = True

        return self._tools_supported

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        on_text: callable,
        on_tool_call: callable | None = None,
        on_reasoning: callable | None = None,
        tools: list[dict[str, Any]] | None = None,
        _is_retry: bool = False,
    ) -> None:
        """Stream a chat completion, yielding text chunks and tool calls.

        Parameters
        ----------
        messages:
            OpenAI-format message list (system, user, assistant, tool).
        on_text:
            Async callable ``on_text(chunk: str)`` for each text delta.
        on_tool_call:
            Optional async callable ``on_tool_call(tool_name, args)``
            when the model requests a tool use.
        on_reasoning:
            Optional async callable ``on_reasoning(chunk: str)`` for
            each reasoning_content delta (thinking mode models).
            Not sent to ``on_text`` — callers control display.
        tools:
            Optional custom tool definitions. If not provided, uses
            the built-in default tool set (bash, read_file, web_fetch).
        _is_retry:
            Internal flag — set to True when retrying without tools after
            a 400 error (thinking mode / reasoning_content conflict).
        """
        client = self._get_client()
        model = self._get_model()

        kwargs = dict(
            model=model,
            messages=messages,
            stream=True,
        )

        # Add tool definitions if callback is provided
        if on_tool_call:
            kwargs["tools"] = tools if tools is not None else self._build_tool_defs()
            kwargs["tool_choice"] = "auto"

        try:
            stream = await client.chat.completions.create(**kwargs)
        except APIError as exc:
            # Graceful fallback: if the API rejects tool calls (thinking mode /
            # reasoning models that don't support function calling), retry without
            # tools so the user can still get a text-only response.
            if (
                not _is_retry
                and on_tool_call
                and exc.status_code == 400
                and any(
                    kw in str(exc).lower()
                    for kw in ["reasoning_content", "thinking", "reasoning"]
                )
            ):
                await on_text(
                    "[dim]当前模型不支持工具调用（可能启用了思考模式），"
                    "已降级为纯文本模式...[/]\n\n"
                )
                return await self.stream_chat(
                    messages=messages,
                    on_text=on_text,
                    on_tool_call=None,  # disable tools
                    tools=None,
                    _is_retry=True,
                )
            await on_text(f"\n\n[red]LLM API 错误: {exc}[/]")
            return

        current_tool_name = ""
        current_tool_args = ""
        accumulated_content = ""
        accumulated_reasoning = ""

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            # Reasoning content (DeepSeek R1, o1, etc. — emitted before content)
            # Reasoning is NOT sent to on_text by default; the caller can
            # subscribe via on_reasoning if they want to display it.
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                accumulated_reasoning += reasoning
                if on_reasoning:
                    await on_reasoning(reasoning)

            # Text content
            if delta.content:
                accumulated_content += delta.content
                await on_text(delta.content)

            # Tool call(s)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.function and tc.function.name:
                        current_tool_name = tc.function.name
                        current_tool_args = tc.function.arguments or ""
                    elif tc.function and tc.function.arguments:
                        current_tool_args += tc.function.arguments

            # Check finish reason
            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish == "tool_calls" and on_tool_call and current_tool_name:
                parsed_args = {}
                try:
                    parsed_args = json.loads(current_tool_args) if current_tool_args else {}
                except json.JSONDecodeError:
                    parsed_args = {"raw": current_tool_args}
                await on_tool_call(
                    current_tool_name,
                    parsed_args,
                    accumulated_content,
                    accumulated_reasoning,
                )
                current_tool_name = ""
                current_tool_args = ""

    def build_messages(
        self,
        user_text: str,
        history: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the full messages array with system prompt."""
        system_prompt = self._build_system_prompt()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Append history
        if history:
            messages.extend(history)

        # Append current user message
        messages.append({"role": "user", "content": user_text})
        return messages

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _detect_os() -> dict[str, str]:
        """Detect the host operating system and return shell hints."""
        system = platform.system().lower()
        if system == "windows":
            return {
                "name": "Windows",
                "shell": "PowerShell",
                "syntax_hint": "不要使用 uname、$(...) 等 Linux/bash 专属命令。",
            }
        if system == "linux":
            return {
                "name": "Linux",
                "shell": "bash",
                "syntax_hint": "",
            }
        if system == "darwin":
            return {
                "name": "macOS",
                "shell": "zsh/bash",
                "syntax_hint": "",
            }
        return {
            "name": system,
            "shell": "shell",
            "syntax_hint": "",
        }

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            config = load_config()
            llm_cfg = config.llm
            self._client = AsyncOpenAI(
                api_key=llm_cfg.api_key or "",
                base_url=llm_cfg.base_url or None,
            )
            self._model = llm_cfg.model or "gpt-4o"
        return self._client

    def _get_model(self) -> str:
        self._get_client()  # ensure loaded
        return self._model

    def _build_system_prompt(self) -> str:
        """Build the system prompt used for every chat turn."""
        os_info = self._os_info
        return (
            "你是 VulnClaw，一个 AI 驱动的渗透测试辅助工具。"
            "你可以帮助用户进行安全分析、漏洞检测和渗透测试。"
            "你可以使用各种工具来执行任务。"
            f"注意：当前系统为 {os_info['name']}，执行命令时请使用 "
            f"{os_info['shell']} 语法。{os_info['syntax_hint']}"
            "请用中文回答用户的问题。"
        )

    def _build_tool_defs(self) -> list[dict[str, Any]]:
        """Build OpenAI tool definitions for function calling."""
        os_info = self._os_info
        return [
            {
                "type": "function",
                "function": {
                    "name": "bash",
                    "description": f"在 {os_info['name']} 上执行 {os_info['shell']} 命令",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "要执行的 shell 命令",
                            },
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取文件的内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "文件路径",
                            },
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "从 URL 获取内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "要获取的 URL",
                            },
                        },
                        "required": ["url"],
                    },
                },
            },
        ]
