"""Tests for LLM error formatting in the classic REPL."""

from types import SimpleNamespace

from vulnclaw.cli._helpers import format_llm_user_error


def test_format_llm_user_error_prefers_openrouter_metadata_raw():
    exc = SimpleNamespace(
        body={
            "message": "Provider returned error",
            "code": 429,
            "metadata": {
                "raw": "google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream.",
                "remedy_hint": "Retry shortly or switch models.",
            },
        }
    )
    exc.__str__ = lambda self: "Error code: 429 - {...}"  # type: ignore[method-assign]
    # BaseException-like: format_llm_user_error calls str(exc) only as fallback.
    class _E(Exception):
        def __init__(self):
            super().__init__("Error code: 429 - blob")
            self.body = exc.body

    msg = format_llm_user_error(_E())
    assert "rate-limited upstream" in msg
    assert "Retry shortly" in msg
    assert "Provider returned error" not in msg or "rate-limited" in msg


def test_format_llm_user_error_falls_back_to_str():
    assert format_llm_user_error(RuntimeError("boom")) == "boom"
