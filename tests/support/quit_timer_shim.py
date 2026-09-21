# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""Make a tty program live as long as the harness is willing to wait.

Copied into a child's working directory as ``sitecustomize.py``, which
Python imports at startup - so this needs no cooperation from the program
under test and shifts none of its line numbers.

**Why it exists.** Every tty program schedules its own exit,
``root.after(4000, root.quit)`` and its like, sixty-eight of them, so that a
wedged one cannot hang the suite. Those numbers are constants. The harness's
own waiting budget is not: CI multiplies it by ``TKCURSES_TEST_TIMEOUT_SCALE``
- four, at the time of writing. So on a runner four times slower the harness
waits twenty seconds for a program that killed itself after four, then
reports a timeout waiting for text nothing was ever going to print again.

That is TkCurses-txk, and it explains its signature exactly: a different
test each run, whichever one happened to be slowest to reach its checkpoint.

Only the exit timers are scaled, recognised by the callback being a
``quit``. Scaling every ``after`` would slow the animations these tests are
watching and change what they measure.
"""

from __future__ import annotations

import os
from typing import Any

_SCALE = float(os.environ.get("TKCURSES_TEST_TIMEOUT_SCALE", "1"))


def _install() -> None:
    """Patch ``Misc.after`` so a quit timer is scaled like the harness's waits."""
    if _SCALE <= 1:
        return
    try:
        import tkcurses
    except ImportError:  # pragma: no cover - a child that is not a tkcurses app
        return

    original = tkcurses.Misc.after

    def after(self: Any, ms: int, func: Any = None, *args: Any) -> Any:
        if func is not None and getattr(func, "__name__", "") == "quit":
            ms = int(ms * _SCALE)
        return original(self, ms, func, *args)

    tkcurses.Misc.after = after  # type: ignore[method-assign]


_install()
