"""TuiState wrapper — central state management for the Textual TUI.

Bridges the legacy TuiState from cli.tui with a clean API
that the new component/command/agent layers can depend on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vulnclaw.cli.tui import TuiState
from vulnclaw.config.settings import load_config
from vulnclaw.config.schema import VulnClawConfig


@dataclass
class TuiStateWrapper:
    """Convenience wrapper around the core TuiState.

    Provides property access, change tracking,
    and a single source of truth for the whole TUI.
    """

    target: str = ""
    mode: str = "standard"
    only_host: str = ""
    only_port: str = ""
    only_path: str = ""
    blocked_host: str = ""
    blocked_path: str = ""
    allow_actions: list[str] = field(default_factory=list)
    block_actions: list[str] = field(default_factory=list)
    resume: bool = True

    _config: VulnClawConfig | None = None

    @classmethod
    def from_core(cls, state: TuiState) -> TuiStateWrapper:
        """Create from core TuiState."""
        return cls(
            target=state.target,
            mode=state.mode,
            only_host=state.only_host,
            only_port=state.only_port,
            only_path=state.only_path,
            blocked_host=state.blocked_host,
            blocked_path=state.blocked_path,
            allow_actions=list(state.allow_actions) if state.allow_actions else [],
            block_actions=list(state.block_actions) if state.block_actions else [],
            resume=state.resume,
        )

    def to_core(self) -> TuiState:
        """Convert back to core TuiState."""
        return TuiState(
            target=self.target,
            mode=self.mode,
            only_host=self.only_host,
            only_port=self.only_port,
            only_path=self.only_path,
            blocked_host=self.blocked_host,
            blocked_path=self.blocked_path,
            allow_actions=list(self.allow_actions),
            block_actions=list(self.block_actions),
            resume=self.resume,
        )

    @property
    def config(self) -> VulnClawConfig:
        """Lazy-loaded app configuration."""
        if self._config is None:
            self._config = load_config()
        return self._config

    def reload_config(self) -> None:
        """Force config reload from file on next access.

        Call this after any external config file change
        (e.g. after /config popup-mode save).
        """
        self._config = None

    def to_dict(self) -> dict[str, Any]:
        """Export as flat dict (for screen config, history metadata, etc.)."""
        return {
            "target": self.target,
            "mode": self.mode,
            "only_host": self.only_host,
            "only_port": self.only_port,
            "only_path": self.only_path,
            "blocked_host": self.blocked_host,
            "blocked_path": self.blocked_path,
            "allow_actions": ",".join(self.allow_actions),
            "block_actions": ",".join(self.block_actions),
            "resume": self.resume,
        }

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Apply values from a dict (e.g. scan config screen result)."""
        for key, value in data.items():
            if hasattr(self, key) and key != "_config":
                if key in ("allow_actions", "block_actions") and isinstance(value, str):
                    value = [a.strip() for a in value.split(",") if a.strip()]
                setattr(self, key, value)
