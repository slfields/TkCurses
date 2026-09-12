"""Module entry point for ``python -m tkcurses`` and the tkcurses-demo script.

The demo currently reports the installed version. It is replaced by a real
widget/dialog showcase once the widget set lands.
"""

from __future__ import annotations

import sys

from tkcurses import __version__


def main() -> int:
    """Run the TkCurses demo. Returns a process exit code."""
    print(f"TkCurses {__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
