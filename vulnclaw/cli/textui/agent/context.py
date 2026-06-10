"""Context builder — assemble message arrays for the LLM from chat history."""

from __future__ import annotations

from typing import Any


class ContextBuilder:
    """Build OpenAI-compatible message arrays from chat history.

    Only user and assistant text messages are included in the
    context — tool results and system messages are excluded to
    keep token usage low.
    """

    def __init__(self, system_prompt: str | None = None) -> None:
        self._system_prompt = system_prompt or (
            "你是 VulnClaw，一个 AI 驱动的渗透测试辅助工具。\n"
            "你可以帮助用户进行安全分析、漏洞检测和渗透测试。\n"
            "请用中文回答用户的问题。"
        )

    def build(
        self,
        history: list[dict[str, str]],
        user_text: str,
    ) -> list[dict[str, Any]]:
        """Build the full messages list for the LLM API call.

        Parameters
        ----------
        history:
            List of ``{"role": "user"|"assistant", "content": str}`` dicts.
        user_text:
            The current user input to append.

        Returns
        -------
        OpenAI-format messages list with system prompt + history + user message.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    def from_message_data(
        self,
        message_data: list,
        user_text: str,
    ) -> list[dict[str, Any]]:
        """Build context from ChatMessageData objects (services.history)."""
        history: list[dict[str, str]] = []
        for msg in message_data:
            if msg.type in ("user", "assistant"):
                history.append({"role": msg.type, "content": msg.content})
        return self.build(history, user_text)
