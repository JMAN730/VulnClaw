"""Cross-platform terminal launcher.

Opens a new terminal window running a given command.
Supports Windows (cmd.exe / start) and Linux (common terminal emulators).

Usage::

    open_terminal([sys.executable, "-m", "my_module", "--flag", "value"])
"""

from __future__ import annotations

import shlex
import subprocess
import sys


def open_terminal(cmd_args: list[str]) -> None:
    """Open a new terminal window executing *cmd_args*.

    Parameters
    ----------
    cmd_args:
        Command and arguments as a list, e.g.
        ``[sys.executable, "-m", "vulnclaw.cli.textui.popup",
         "--session-dir", "/tmp/x"]``.
    """
    if sys.platform == "win32":
        _open_windows(cmd_args)
    else:
        _open_linux(cmd_args)


def _open_windows(cmd_args: list[str]) -> None:
    """Windows: new CMD window that closes when done.

    Uses ``cmd /c`` (close after execution). The child process handles
    its own error display and pause before exit.
    """
    cmd_line = subprocess.list2cmdline(cmd_args)
    full_cmd = f'start "" cmd /c {cmd_line}'
    subprocess.Popen(full_cmd, shell=True)


def _open_linux(cmd_args: list[str]) -> None:
    """Linux: try common terminal emulators in order."""
    command = shlex.join(cmd_args)
    terminals = [
        ("x-terminal-emulator", ("-e", command)),
        ("gnome-terminal", ("--", "sh", "-c", command)),
        ("xterm", ("-e", command)),
        ("konsole", ("--hold", "-e", "sh", "-c", command)),
        ("lxterminal", ("-e", command)),
        ("xfce4-terminal", ("-e", command)),
        ("mate-terminal", ("-e", command)),
    ]

    for term, args in terminals:
        try:
            subprocess.Popen([term, *args])
            return
        except FileNotFoundError:
            continue

    print(
        "Warning: could not open a new terminal window. "
        "Install x-terminal-emulator, gnome-terminal, or xterm.",
        file=sys.stderr,
    )
