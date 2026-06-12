"""/settings command — open graphical settings panel.

Usage::

    /settings      Open configuration settings (embed or separate window)
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import asyncio

from vulnclaw.config.settings import load_config, save_config
from vulnclaw.i18n import _


def _config_to_flat(config) -> dict[str, Any]:
    """Convert VulnClawConfig to flat dict for IPC."""
    return {
        "llm_provider":       config.llm.provider,
        "llm_api_key":        config.llm.api_key,
        "llm_base_url":       config.llm.base_url,
        "llm_model":          config.llm.model,
        "llm_max_tokens":     config.llm.max_tokens,
        "llm_temperature":    config.llm.temperature,
        "session_render_mode":   config.session.render_mode,
        "session_show_thinking": config.session.show_thinking,
        "session_auto_save":     config.session.auto_save,
        "session_max_rounds":    config.session.max_rounds,
        "session_language":      config.session.language,
        "session_popup_mode":    config.session.popup_mode,
    }


def _flat_to_config(data: dict[str, Any]) -> None:
    """Apply flat settings dict onto the current config and save."""
    cfg = load_config()

    # LLM provider
    cfg.llm.provider = str(data.get("llm_provider", cfg.llm.provider))
    cfg.llm.api_key = str(data.get("llm_api_key", cfg.llm.api_key))
    cfg.llm.base_url = str(data.get("llm_base_url", cfg.llm.base_url))
    cfg.llm.model = str(data.get("llm_model", cfg.llm.model))

    # LLM params
    try:
        cfg.llm.max_tokens = int(data.get("llm_max_tokens", cfg.llm.max_tokens))
    except (ValueError, TypeError):
        pass
    try:
        cfg.llm.temperature = float(data.get("llm_temperature", cfg.llm.temperature))
    except (ValueError, TypeError):
        pass

    # Display
    cfg.session.render_mode = str(data.get("session_render_mode", cfg.session.render_mode))
    cfg.session.show_thinking = bool(data.get("session_show_thinking", cfg.session.show_thinking))

    # Session
    cfg.session.auto_save = bool(data.get("session_auto_save", cfg.session.auto_save))
    try:
        cfg.session.max_rounds = int(data.get("session_max_rounds", cfg.session.max_rounds))
    except (ValueError, TypeError):
        pass
    cfg.session.language = str(data.get("session_language", cfg.session.language))
    cfg.session.popup_mode = str(data.get("session_popup_mode", cfg.session.popup_mode))

    save_config(cfg)


class SettingsCommand:
    """Open the graphical settings panel (embed or separate window)."""

    async def run(self, args: str, **context) -> None:
        """Route to embed or separate based on popup_mode."""
        chat_pane = context.get("chat_pane")
        if chat_pane is None:
            return

        # Read config directly from file — bypass TuiStateWrapper cache
        # to guarantee we see the latest popup_mode even if the user just
        # changed it via /config popup-mode.
        cfg = load_config()
        popup_mode = cfg.session.popup_mode
        if popup_mode == "separate":
            await self._open_separate(chat_pane)
        else:
            await self._open_embed(chat_pane)

    # ── Embed (in-terminal modal) ─────────────────────────────

    async def _open_embed(self, chat_pane) -> None:
        """Push the SettingsScreen modal in-terminal."""
        from vulnclaw.cli.textui.components.settings_screen import SettingsScreen

        screen = SettingsScreen()
        result = await chat_pane.app.push_screen_wait(screen)

        if result:
            chat_pane._state.reload_config()
            # Re-init LLM service so provider/api_key/base_url/model take effect
            chat_pane._llm.reconfigure()
            chat_pane.add_system_message(_("tui.command.settings.saved"))
            # Re-compose the whole UI so language/text changes take effect
            chat_pane.app.recompose()

        chat_pane._focus_input()

    # ── Separate (independent window) ─────────────────────────

    async def _open_separate(self, chat_pane) -> None:
        """Open settings in a new terminal window (file IPC)."""
        session_id = uuid.uuid4().hex[:12]
        session_dir = (Path(tempfile.gettempdir()) /
                       "vulnclaw_popup" / session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Write initial config — read fresh from file for consistency
        cfg = load_config()
        main_file = session_dir / "main_to_child.json"
        main_file.write_text(
            json.dumps({
                "version": 1,
                "data": _config_to_flat(cfg),
                "action": None,
            }),
            encoding="utf-8",
        )

        from vulnclaw.cli.textui.popup.launcher import open_terminal

        open_terminal([
            sys.executable, "-m", "vulnclaw.cli.textui.popup",
            "--type", "settings",
            "--session-dir", str(session_dir),
        ])

        chat_pane.add_system_message(
            _("tui.command.settings.opened_separate", session_id=session_id)
        )

        # Non-blocking background poller
        asyncio.create_task(
            self._poll_separate_background(session_dir, chat_pane)
        )

        chat_pane._focus_input()

    @staticmethod
    async def _poll_separate_background(
        session_dir: Path, chat_pane,
    ) -> None:
        """Background task: poll child IPC, save config on action."""
        from vulnclaw.i18n import set_language

        child_file = session_dir / "child_to_main.json"
        last_version = 0
        last_lang: str | None = None

        for _i in range(7200):  # 2 hours timeout
            await asyncio.sleep(1)
            try:
                raw = child_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                ver = data.get("version", 0)
                if ver > last_version:
                    last_version = ver
                    action = data.get("action")
                    if action == "save":
                        flat = data.get("data", {})
                        new_lang = flat.get("session_language", "auto")
                        if new_lang != last_lang:
                            set_language(new_lang)
                            last_lang = new_lang
                            chat_pane.app.recompose()
                        _flat_to_config(flat)
                        chat_pane._state.reload_config()
                        chat_pane._llm.reconfigure()
                    elif action == "close":
                        flat = data.get("data", {})
                        new_lang = flat.get("session_language", "auto")
                        if new_lang != last_lang:
                            set_language(new_lang)
                            chat_pane.app.recompose()
                        _flat_to_config(flat)
                        chat_pane._state.reload_config()
                        chat_pane._llm.reconfigure()
                        break
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        # Cleanup
        try:
            shutil.rmtree(session_dir)
        except Exception:
            pass
