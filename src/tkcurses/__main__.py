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

"""Module entry point for ``python -m tkcurses`` and the tkcurses-demo script.

The demo currently reports the installed version. It is replaced by a real
widget/dialog showcase once the widget set lands.
"""

from __future__ import annotations

import sys

from tkcurses import NOTICE


def main() -> int:
    """Run the TkCurses demo. Returns a process exit code.

    The notice comes first because the GNU GPL asks an interactive program
    to show one when it starts: the version, who holds the copyright, that
    there is no warranty, and where to read the terms.
    """
    print(NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
