"""``python -m vulnclaw.cli.textui.popup`` entry point.

Delegates to :func:`vulnclaw.cli.textui.popup.main` so the entry logic
lives in a single place (``__init__.py``).
"""

from vulnclaw.cli.textui.popup import main

main()
