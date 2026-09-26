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

"""Find tty tests that assert on a cell they never waited for.

This is the shape behind most of TkCurses-txk: a test waits for one thing to
appear and then asserts on a different cell, which is only safe if the whole
update arrived together. Nothing promises that - curses writes to the pty and
the harness drains it in chunks - so a sample can land mid-frame. It shows up
as a different test failing on a different Python version each run, never
reproducibly.

It exists as a script rather than a test because the judgement cannot be
automated: waiting for "hello" and then asserting on the row holding "hello"
is fine, and only a person can say which of the flagged tests are that shape.
An earlier cycle audited this by hand, found three, and missed
test_frame_tty.py - which then failed in CI months later. Running this is how
the next audit does not undercount:

    python3 tests/support/audit_waits.py

Every flagged test wants the same question asked of it: does the wait cover
every cell the assertions read? If not, widen the wait - `wait_for_cell`, or
one `wait_for` whose predicate names all of them.
"""

from __future__ import annotations

import ast
import pathlib
import sys

#: Waiting methods on TerminalHarness.
WAITS = frozenset(
    {
        "wait_for",
        "wait_for_text",
        "wait_for_cell",
        "wait_for_idle",
        "wait_for_exit",
        "wait_for_rows",
    }
)

#: Waits that already settle the screen or already name a cell, so a test
#: using one is not making this mistake.
SAFE = frozenset({"wait_for_idle", "wait_for_cell"})


def waits_in(fn: ast.FunctionDef) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in WAITS
    }


def asserts_on_a_cell(fn: ast.FunctionDef) -> bool:
    """Whether an ``assert`` in this test indexes ``.display``."""
    return any(
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "display"
        for statement in ast.walk(fn)
        if isinstance(statement, ast.Assert)
        for node in ast.walk(statement)
    )


def a_wait_looks_at_cells(fn: ast.FunctionDef) -> bool:
    """Whether any wait's own predicate indexes ``.display``.

    This is the signal that the author thought about which cells had
    arrived. A wait written as ``wait_for_text("hello")`` has not: it is
    satisfied by text anywhere on the screen, so an assertion on a
    particular cell underneath it is the shape this script looks for.

    It is a heuristic, deliberately. The alternative - matching row numbers
    between the wait and the assertions - cannot see through the ``row - 1``
    and ``row + 1`` arithmetic these tests are full of, and reported tests
    that had just been fixed. A wrong answer from an audit tool is worse
    than no tool, because it trains people to ignore it.
    """
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in WAITS
        ):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr == "display":
                    return True
    return False


def flagged(root: pathlib.Path) -> list[tuple[str, int, str, list[str]]]:
    out = []
    for path in sorted((root / "tests").glob("*_tty.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test_"):
                continue
            names = waits_in(fn)
            if not names or names & SAFE:
                continue
            if not asserts_on_a_cell(fn) or a_wait_looks_at_cells(fn):
                continue
            out.append((path.name, fn.lineno, fn.name, sorted(names)))
    return out


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    rows = flagged(root)
    print(f"{len(rows)} tty tests index .display without settling or naming a cell\n")
    for name, line, test, names in rows:
        print(f"  {name}:{line}  {test}\n      waits: {', '.join(names)}")
    print(
        "\nNot all of these are wrong. Ask of each: does the wait cover every\n"
        "cell the assertions read? See this module's docstring."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
