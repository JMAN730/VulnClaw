"""Tab completion rule table — parser and loader.

Usage::

    from vulnclaw.cli.textui.commands.completion_rules import load_rules

    rules = load_rules()
    # rules == {"config": [("popup-mode", "<desc>"), ("popup-mode embed", "<desc>"), ...],
    #           "sc":     [("show", "<desc>"), ("run", "<desc>")],
    #           ...}

Then pass ``rules.get("config", [])`` to ``registry.register(completions=...)``.
"""

from __future__ import annotations

import os
from typing import Optional

from vulnclaw.i18n import _


_RULES_PATH = os.path.join(os.path.dirname(__file__), "completion_rules.txt")


def load_rules(path: Optional[str] = None) -> dict[str, list[tuple[str, str]]]:
    """Parse the completion rule table and return grouped completions.

    Each line in the rule file has the format::

        base_command | suffix_path | i18n_key

    Blank lines and lines starting with ``#`` are ignored.
    The *suffix_path* may contain spaces for multi-level completion
    (e.g. ``popup-mode embed`` is two levels deep).

    Returns a dict mapping ``base_command → [(suffix_path, localized_desc), …]``.
    The returned structure is ready to be passed to
    ``CommandRegistry.register(completions=…)``.
    """
    path = path or _RULES_PATH
    result: dict[str, list[tuple[str, str]]] = {}

    try:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 3:
                    continue
                base_cmd, suffix, i18n_key = parts
                if not base_cmd or not suffix or not i18n_key:
                    continue
                desc = _(i18n_key)
                result.setdefault(base_cmd, []).append((suffix, desc))
    except FileNotFoundError:
        pass  # no rules → empty result

    return result
