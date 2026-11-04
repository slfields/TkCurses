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


"""Record Tk 9's word procedures over many strings, as test data.

Run with a display and the system tkinter, from the repository root::

    DISPLAY=:0 /usr/bin/python3 tests/support/record_word_boundaries.py

It writes ``word_boundaries.json`` beside itself: for each string, what
``tk::endOfWord``, ``tk::startOfNextWord`` and ``tk::startOfPreviousWord``
answer from every index, ``null`` for Tk's ``""``. ``tests/test_words.py``
holds ``tkcurses._core.words`` to it. Tk 9.0.2 makes the three in C over
ICU; tk.tcl's Tcl versions, over word.tcl, do not load. TkCurses-wmaq.

With them ``tk::wordBreakBefore`` and ``tk::wordBreakAfter``, which a
double-click selects words by, from one before the start to one past the
end and from ``end``, which ``tk::TextPrevPos`` passes. Those two ARE
tk.tcl's, over word.tcl's runs of ``\\w`` and ``\\W``: Tk 9.0.2 defines no
C ones. ``tests/test_words.py`` holds ``_core/editing.py``'s ``run_start``
and ``run_end`` to them. TkCurses-asfo.
"""

from __future__ import annotations

import json
import random
import tkinter
from pathlib import Path

PROCEDURES = ("endOfWord", "startOfNextWord", "startOfPreviousWord")
BREAKS = ("wordBreakBefore", "wordBreakAfter")
#: Characters and pieces the rules treat differently: letters, digits, the
#: connector, each joining mark, spaces, tabs, newlines, other punctuation
#: and a combining mark.
ALPHABET = [
    *"abcxyzAB019_ .,'-:;\n\t()\u00e9",
    "\u0301", "  ", "it's", "3.14", "1,000", "a.b", "foo_bar",
]  # fmt: skip
FIXED = [
    "hello world  foo_bar-baz, 42 x", "a-b", "ab--cd", "x  ,  y", " lead",
    "end. ", "it's 3.14 a.b", "ab12 _x", "abc  \n  def", "ab\n\ncd", "a \t b",
    "x\ny", "a:b c;d 1,000 1;2", "q (r) [s]", "", "a", " ",
]  # fmt: skip


def record(count: int = 400, seed: int = 20261104) -> list[dict[str, object]]:
    root = tkinter.Tk()
    proc = root.tk.eval("info procs ::tk::wordBreakBefore")
    assert proc, "Tk has a C wordBreakBefore; the fixture's note is wrong"
    rng = random.Random(seed)
    strings = FIXED + [
        "".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 14)))
        for _ in range(count)
    ]

    def call(procedure: str, text: str, index: int | str) -> int | None:
        answer = root.tk.call(f"::tk::{procedure}", text, index)
        # tkinter hands an empty answer back as "" or as ().
        return None if answer in ("", ()) else int(answer)

    cases = [
        {"s": text}
        | {p: [call(p, text, i) for i in range(len(text) + 1)] for p in PROCEDURES}
        | {
            p: [call(p, text, i) for i in range(-1, len(text) + 2)]
            + [call(p, text, "end")]
            for p in BREAKS
        }
        for text in strings
    ]
    root.destroy()
    return cases


if __name__ == "__main__":
    out = Path(__file__).with_name("word_boundaries.json")
    data = {"measured": "tkinter on Python 3.14 over Tk 9.0.2", "cases": record()}
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(len(data["cases"]), "strings ->", out)
