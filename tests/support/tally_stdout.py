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

"""Count what a child writes to stdout, and say so on the way out.

Copied into a directory that goes on the child's ``PYTHONPATH`` as
``sitecustomize.py``, which Python imports at startup. That is the point:
it instruments the command under test **without changing the command**.

TkCurses-9q7 is a listing that arrives truncated on one Python version while
the child exits 0. Separating "the child stopped writing" from "the pty lost
it" needs the child's own count, and the first attempt at that got the answer
by running a DIFFERENT child - a wrapper module - and comparing. Both children
passed through the same harness in the same CI job, so the comparison looked
sound, and it is not: they ran at different moments under different load, and
the thing being investigated is timing-dependent. A wrapper can only ever
report on itself.

This reports on ``python3 -m uat`` itself. The report goes to fd 2 with
``os.write``, which is the pipe the harness reads as ``term.stderr`` - a
separate channel from the pty, so the answer is not subject to whatever is
eating stdout, and no buffering of our own stands between the number and the
pipe.

``LAST`` is the other half of the answer. If the child stopped writing, the
last thing it managed to write says where: the listing prints a line per
scenario and imports the next scenario between them, so the last line names
the import it did not come back from.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import sys
from typing import Any


class _Tally:
    """A stdout that counts, and remembers the last thing through it."""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self.count = 0
        self.writes = 0
        self.last = ""

    def write(self, text: str) -> int:
        self.count += len(text.encode("utf-8", "replace"))
        self.writes += 1
        if text.strip():
            self.last = text.strip()[-60:]
        return int(self._stream.write(text))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _install() -> None:
    if sys.stdout is None:  # pragma: no cover - a child with no stdout
        return
    tally = _Tally(sys.stdout)
    sys.stdout = tally  # type: ignore[assignment]

    def report() -> None:
        # os.write, not print: at interpreter shutdown sys.stderr may already
        # be closed, and a buffered write would be the one thing lost from a
        # report about things being lost.
        with contextlib.suppress(Exception):  # a stdout already torn down
            sys.stdout.flush()
        message = (
            f"BYTES-WRITTEN {tally.count} WRITES {tally.writes} LAST {tally.last!r}\n"
        )
        with contextlib.suppress(OSError):  # fd 2 gone
            os.write(2, message.encode("utf-8", "replace"))

    atexit.register(report)


_install()
