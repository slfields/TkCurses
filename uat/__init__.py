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

"""Acceptance scenarios: what a person has to look at to judge.

The pytest suite asserts on an emulated terminal, which settles whether the
right characters reach the right cells. It cannot tell you that a window looks
wrong, that a resize leaves the display confused, or that Ctrl-C hands back a
terminal you can still type in. These scenarios are for those questions.

From the repository root, ``python3 -m uat`` lists them and
``python3 -m uat <number>`` runs one. From anywhere else, give the path:
``python3 /path/to/TkCurses/uat``. uat/ is a development tool rather than
part of the installed package, which is why the root has to be findable.

docs/UAT_BASE_WIDGETS.md says what each scenario is asking you to look at.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The scenarios accept this checkout's library, not whichever is installed.
# Nothing else puts src/ on sys.path: a pip install of an older tkcurses in
# site-packages won, and scenario 52 failed to import tkcurses.treemap - a
# module only the checkout had - while every older scenario quietly ran
# against the installed copy. tests/conftest.py makes the same fix for the
# suite. Here, in the package, it covers each way a scenario starts:
# python3 -m uat, python3 -m uat.scenario_NN, and the path form.
_SRC = str(Path(__file__).resolve().parent.parent / "src")
if sys.path[:1] != [_SRC]:
    if _SRC in sys.path:
        sys.path.remove(_SRC)
    sys.path.insert(0, _SRC)
