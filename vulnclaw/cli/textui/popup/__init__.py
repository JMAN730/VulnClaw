"""Popup child process — runs ``python -m vulnclaw.cli.textui.popup``.

Launched by the main TUI when ``popup_mode == "separate"`` to display
scan configuration in an independent terminal window, communicating
via file IPC.

Any unhandled exception is printed to stderr **and** saved to
``<session-dir>/error.log`` so the error can be inspected even if the
window closes unexpectedly.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="VulnClaw popup child process")
    parser.add_argument(
        "--session-dir", required=True,
        help="IPC session directory path",
    )
    parser.add_argument(
        "--type", default="sc",
        choices=["sc", "settings"],
        help="Popup type: sc (scan config) or settings",
    )
    args, _ = parser.parse_known_args()

    try:
        if args.type == "sc":
            from vulnclaw.cli.textui.popup.sc_screen import PopupSCApp

            app = PopupSCApp(args.session_dir)
            app.run()
        elif args.type == "settings":
            from vulnclaw.cli.textui.popup.settings_screen import PopupSettingsApp

            app = PopupSettingsApp(args.session_dir)
            app.run()
        else:
            print(f"Unknown popup type: {args.type}", file=sys.stderr)
            sys.exit(1)
    except Exception:
        error_msg = traceback.format_exc()

        # Write to console
        print(error_msg, file=sys.stderr)
        print(
            "\n--- VulnClaw Popup encountered an error."
            " Press Enter to close this window. ---"
        )

        # Also save to a file so it's not lost
        try:
            log_file = Path(args.session_dir) / "error.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(error_msg, encoding="utf-8")
        except Exception:
            pass

        input()
        sys.exit(1)
