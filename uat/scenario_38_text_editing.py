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

"""Undo, search, and where a character actually is.

What to do: type in the box. Press Ctrl-Z to undo and Ctrl-Y to redo. Press
Ctrl-T to turn autoseparators off and on. Press Ctrl-F to reach the search
field, type something and press Return to find it again - Return repeatedly
walks through every match and round to the start. Press Ctrl-R to load a
paragraph long enough to wrap and to scroll. Tab types a tab, as it does in
tkinter; see ``insert_tab`` for why that has to be said out loud here.
What to look for: **undo takes back what you would call one action**, not one
letter; and the cell the status line reports is the cell the cursor is in.

These three are exactly the kind of thing automated tests pass while a person
finds the widget unusable, which is why they are here rather than left to the
suite.

An undo stack that groups wrongly is correct edit by edit: every character
goes on and comes off in the right order, and no test of a single edit can
tell. It is only maddening to *use* - undo becomes backspace with extra
steps, and taking back a sentence means holding Ctrl-Z down and watching it
crawl. So the thing to judge is the grouping, not the mechanism: type a whole
word and undo once.

Grouping is invisible from outside, which is why the status line counts the
groups rather than leaving them to be inferred, and why Ctrl-T is here. With
-autoseparators ON, the count goes up when you change what you are doing -
move the cursor, switch from typing to deleting. With it OFF, Tk puts in no
separators at all and everything since the last explicit edit_separator() is
one group, so the count stops rising and Ctrl-Z takes the lot. Watching that
number stop moving is the clearest way to see what the option is for.

A search that wraps looks like a bug when you are not expecting it, and Tk
wraps: with no stopindex a forward search runs off the end and round to the
beginning. The status line says which match you are on and how many there
are, so going round is visible as going round rather than as the search
having lost its place.

The geometry line is the part that would otherwise have to be taken on
trust. dlineinfo and bbox say where the widget thinks the insert cursor is;
the cursor is drawn where the widget thinks it should go. If those two ever
disagree, clicking a character would select a different one - so this shows
both numbers next to the thing they describe and lets a person check them by
eye, including on a wrapped line and after scrolling sideways.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "38 - text editing: undo, search and geometry"

#: Loaded by Ctrl-R. Long enough to wrap, and long enough to scroll.
PARAGRAPH = (
    "The quick brown fox jumps over the lazy dog, and having jumped it "
    "goes back again to see whether the dog has noticed. It has not.\n"
    "\n"
    "A second paragraph, so that Up and Down have somewhere to go and "
    "the search has more than one line to find things on.\n"
)


def build(root, screen):
    screen.line(2, "Type. Ctrl-Z undo, Ctrl-Y redo, Ctrl-R load a paragraph.")
    screen.line(3, "Ctrl-T toggles autoseparators. Ctrl-F to Find, Return finds next.")

    editor = tkcurses.Text(
        root,
        name="editor",
        width=60,
        height=10,
        wrap="char",
        undo=True,
        autoseparators=True,
    )
    editor.place(x=2, y=5, relwidth=1.0, width=-4, height=10)

    screen.line(17, "Find:")
    finder = tkcurses.Entry(root, name="finder", width=30)
    # Rows 16, 17 and 18: an Entry draws a border above and below its one
    # row of text, and anything placed on 18 lands on that bottom edge.
    finder.place(x=8, y=16, width=30)

    status = tkcurses.Label(root, name="status", anchor="w")
    status.place(x=2, y=20, relwidth=1.0, width=-4)
    found = tkcurses.Label(root, name="found", anchor="w")
    found.place(x=2, y=21, relwidth=1.0, width=-4)

    def report(event=None):
        """Say where the cursor is, by both accounts, and what undo holds.

        ``groups`` is the number of separate things Ctrl-Z would take back,
        and it is the point of the autoseparators half of this scenario:
        grouping is invisible from outside, so without it a person can only
        infer it by pressing Ctrl-Z and counting what comes back.
        """
        where = editor.index("insert")
        box = editor.bbox("insert")
        line = editor.dlineinfo("insert")
        cell = "off screen" if box is None else f"cell x={box[0]} y={box[1]}"
        row = "-" if line is None else f"row y={line[1]} width={line[2]}"
        autosep = "on" if editor.cget("autoseparators") else "OFF"
        status.configure(
            text=f"insert {where}   {cell}   dlineinfo {row}"
            f"   modified={editor.edit_modified()}"
            f"   autosep={autosep}   undo groups={editor._buffer.undo_depth}"
        )
        root.after(100, report)

    def undo(event=None):
        try:
            editor.edit_undo()
        except tkcurses.TclError as error:
            found.configure(text=str(error))
        return "break"

    def redo(event=None):
        try:
            editor.edit_redo()
        except tkcurses.TclError as error:
            found.configure(text=str(error))
        return "break"

    def load(event=None):
        editor.edit_separator()
        editor.insert("end-1c", PARAGRAPH)
        return "break"

    def search(event=None):
        """Find the next match from just past the cursor, and count them all.

        Starting at ``insert +1c`` rather than at ``insert`` is what makes
        Return walk forwards: a search from the cursor would find the match
        the cursor is already sitting on, for ever.
        """
        pattern = finder.get()
        if not pattern:
            found.configure(text="nothing to find")
            return "break"
        counter = tkcurses.IntVar()
        at = editor.search(pattern, "insert +1c", count=counter)
        if not at:
            found.configure(text=f"{pattern!r} is not in the text")
            return "break"
        editor.mark_set("insert", at)
        editor.see(at)
        editor.focus_set()
        total = _count(editor, pattern)
        found.configure(
            text=f"{pattern!r} at {at}, {counter.get()} characters,"
            f" {total} in the text altogether"
        )
        return "break"

    def insert_tab(event=None):
        """Tab types a tab here, as it does in tkinter.

        Tk binds <Tab> in a Text to insert one and keep the focus, and puts
        traversal on <Control-Tab>. TkCurses leaves Tab alone at the widget
        level so that focus traversal - which lives on the ``all`` tag - can
        have it, because a terminal cannot reliably send Control-Tab and a
        keyboard-only user would otherwise be stuck in the first Text they
        reached.

        That is a sensible default for a terminal and the wrong one for an
        EDITOR, which is what this scenario is pretending to be. So the
        scenario takes Tab back the way the architecture intends - bind it
        and return "break" - and gives the Find box Ctrl-F instead. Relying
        on the default here made the scenario quietly disagree with tkinter
        about what Tab does in a text editor.
        """
        editor._type("\t")
        return "break"

    def to_find(event=None):
        finder.focus_set()
        return "break"

    def toggle_separators(event=None):
        """Flip -autoseparators so the difference can be seen, not taken on trust.

        With it off, Tk puts in no separators at all: everything typed since
        the last explicit edit_separator() is ONE group, so Ctrl-Z takes the
        lot. That is the behaviour to compare against, and the reason the
        option exists.
        """
        now = not editor.cget("autoseparators")
        editor.configure(autoseparators=now)
        found.configure(
            text=f"autoseparators {'on' if now else 'off'} - "
            + (
                "typing is grouped by what you are doing"
                if now
                else "everything from here is one undo group"
            )
        )
        return "break"

    editor.bind("<Tab>", insert_tab)
    editor.bind("<Control-f>", to_find)
    editor.bind("<Control-t>", toggle_separators)
    editor.bind("<Control-z>", undo)
    editor.bind("<Control-y>", redo)
    editor.bind("<Control-r>", load)
    finder.bind("<Return>", search)
    editor.focus_set()
    root.after(100, report)


def _count(editor, pattern):
    """How many matches there are, by walking round once.

    Uses the wrap deliberately: start at 1.0, take each match in turn, and
    stop when it comes back to one already seen. A count done any other way
    would not exercise the thing the checklist asks about.
    """
    seen = []
    at = editor.search(pattern, "1.0")
    while at and at not in seen:
        seen.append(at)
        at = editor.search(pattern, f"{at} +1c")
    return len(seen)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
