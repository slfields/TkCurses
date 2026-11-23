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

"""Run the acceptance scenarios.

``python3 -m uat`` lists them; ``python3 -m uat 3`` runs the third. Both need
the repository root as the working directory, since uat/ lives there and is
not part of the installed package. Giving the path instead works from
anywhere: ``python3 /path/to/TkCurses/uat``.

Each scenario also runs on its own - ``python3 -m uat.scenario_03_stacking`` -
which is what the list prints, so one can be pointed at from a bug report.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

# Run by path rather than with -m, this file's own directory is what lands on
# sys.path, not the repository root, so the package it belongs to cannot be
# imported. Putting the root on the path first is what makes the
# run-from-anywhere form work.
if __package__ in (None, ""):  # pragma: no cover - only when run by path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uat  # placed here deliberately: it needs the sys.path fix above


def scenarios() -> list[str]:
    """Every scenario module, in order."""
    return sorted(
        module.name
        for module in pkgutil.iter_modules(uat.__path__)
        if module.name.startswith("scenario_")
    )


def summary(name: str) -> str:
    """The first line of a scenario's docstring."""
    module = importlib.import_module(f"uat.{name}")
    return (module.__doc__ or "").strip().splitlines()[0]


def show() -> int:
    """Print the list of scenarios."""
    print("Acceptance scenarios. Run one with: python3 -m uat <number>\n")
    for index, name in enumerate(scenarios(), start=1):
        print(f"  {index:>2}. {summary(name)}")
        print(f"      python3 -m uat.{name}")
    print("\nWhat to look for: docs/UAT_BASE_WIDGETS.md (1-9),")
    print("                 docs/UAT_GEOMETRY.md (10-14),")
    print("                 docs/UAT_INTERACTIVE.md (15-19),")
    print("                 docs/UAT_VALUES.md (20-22),")
    print("                 docs/UAT_CONTENT.md (23-26),")
    print("                 docs/UAT_INPUT.md (27),")
    print("                 docs/UAT_GEOMETRY.md again (28),")
    print("                 docs/UAT_DIALOGS.md (29-30),")
    print("                 docs/UAT_COLOUR.md (31),")
    print("                 docs/UAT_CURSES.md (32),")
    print("                 docs/UAT_TTK.md (33-34),")
    print("                 docs/UAT_IMAGES.md (35-37),")
    print("                 docs/UAT_TEXT_EDITING.md (38),")
    print("                 docs/UAT_TABS_AND_INDENTATION.md (39),")
    print("                 docs/UAT_TTK_CORE_WIDGETS.md (40),")
    print("                 docs/UAT_ENTRY_VALIDATION.md (41),")
    print("                 docs/UAT_VIEWS_AND_SELECTIONS.md (42),")
    print("                 docs/UAT_CLIPBOARD.md (43),")
    print("                 docs/UAT_MOUSE_SELECTION.md (44),")
    print("                 docs/UAT_KEY_SEQUENCES.md (45),")
    print("                 docs/UAT_MENU_COLUMNS_SHORTCUTS.md (46),")
    print("                 docs/UAT_TREEVIEW_FROZEN_TITLES.md (47),")
    print("                 docs/UAT_CLASSIC_LOOKS.md (48),")
    print("                 docs/UAT_CLASSIC_BEHAVIOUR.md (49),")
    print("                 docs/UAT_MENU_IMAGES_TEAROFFS.md (50),")
    print("                 docs/UAT_BARGRAPH.md (51),")
    print("                 docs/UAT_TREEMAP.md (52),")
    print("                 docs/UAT_XYCHART.md (53)")
    return 0


def main(argv: list[str]) -> int:
    """List the scenarios, or run the one named by a number."""
    if not argv:
        return show()
    names = scenarios()
    try:
        chosen = names[int(argv[0]) - 1]
        if int(argv[0]) < 1:
            raise IndexError
    except (ValueError, IndexError):
        print(f"no such scenario: {argv[0]!r}", file=sys.stderr)
        return show() or 2
    module = importlib.import_module(f"uat.{chosen}")
    if hasattr(module, "run"):
        # A scenario that is not a tkinter one runs itself. The curses
        # scenario is the case: it has no root and no widgets to lay out,
        # and _support.run would give it both.
        return int(module.run())
    return int(module._support.run(module.TITLE, module.build))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
