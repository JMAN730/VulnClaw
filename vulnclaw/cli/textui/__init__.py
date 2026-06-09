"""Textual-powered TUI for VulnClaw.

Conditional import — falls back gracefully when textual is not installed.
Use VULNCLAW_TUI_LEGACY=1 environment variable to force the old Rich TUI.
"""

from __future__ import annotations

import os

TEXTUAL_AVAILABLE: bool = False
VULNCLAW_TUI_LEGACY = os.environ.get("VULNCLAW_TUI_LEGACY", "0") == "1"

try:
    from textual.app import App as _TextualApp  # noqa: F401

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
