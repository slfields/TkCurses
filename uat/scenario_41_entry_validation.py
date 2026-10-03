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

"""Entry validation, and whether a refusal is something you can see.

What to do: type in each entry on the left. Press the buttons beside them,
which edit the entries from code rather than from the keyboard. Move the focus
away from the third entry with Tab, F6 or a click. Then press Ctrl-R to put
everything back and do it again.

What to look for: **the mode column under the title.** It reads back
``cget("validate")`` for every entry on screen, after every event. An entry
whose mode silently becomes ``none`` has stopped validating and will accept
anything from then on, with nothing on screen to say so unless you are looking
at that column. That is the failure this scenario exists to make visible, and
it is not hypothetical - it is what Tk does, deliberately, in three separate
circumstances:

* a validator that raises
* a validator that edits the entry it is being asked about
* a ``textvariable`` written with a value the validator refuses

The first two are Tk's recursion guard: a validator calling ``insert`` on its
own entry would call itself forever, so Tk cuts the loop by switching
validation off and leaves it off. The third is Tk admitting it cannot refuse
what the variable already holds. All three were measured against Tcl/Tk 9.0.2
rather than assumed, and all three leave an application quietly unvalidated.

Why this scenario exists at all: validation had 4,694 automated tests agreeing
with real Tk scenario for scenario, and no acceptance coverage whatsoever - the
word "valid" appeared in none of the forty scenarios here and none of the
fourteen checklists. Tests can say the behaviour matches. They cannot say that
a person can tell what happened, which for a feature whose whole job is to
refuse things is most of the question. TkCurses-wkd.

The three conditions, and what each does with a refusal:

=========  ====================================  ==========================
condition  fires when                            a refusal means
=========  ====================================  ==========================
edit       a keystroke, insert(), delete()       the edit is discarded
focus      the focus arrives or leaves           nothing is undone
forced     the textvariable is written           nothing can be undone;
                                                 validation is switched off
=========  ====================================  ==========================

So the third entry is the surprising one on purpose: tab away from it with
letters in it, watch it complain, and watch the letters stay. A focus
validator is advisory. If it reverted the text, that would be the bug.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "41 - Entry validation: edit, focus and forced"

#: Row in the content area, label, and the mode each entry is built with.
#
#: Three rows apart, not two. A bordered widget is three rows tall, so two
#: rows apart means each one's bottom border is painted over by the next one's
#: top. That is written down as a finding from UAT 40
#: (docs/UAT_TTK_CORE_WIDGETS.md) and it happened again here anyway - caught by
#: driving this scenario in a pty rather than by its smoke test, which only
#: checks that the title appears.
FIELDS = (
    ("digits", 0, "digits only (key)", "key"),
    ("locked", 3, "readonly", "key"),
    ("onfocus", 6, "focusout", "focusout"),
    ("broken", 9, "validator raises", "key"),
    ("forced", 12, "forced (variable)", "key"),
)


def build(root, screen):
    entries = {}
    last = {"text": "nothing yet"}

    screen.line(0, f" {TITLE} ")
    screen.footer(" ^R reset every entry   Tab / F6 move focus   Escape quits ")

    # Fifteen rows of entries, one for the title, three for the readout and one
    # for the footer: this scenario wants a terminal at least 20 rows tall.
    area = _support.content_area(root, top=4, bottom=1)

    def note(message):
        """Record what just happened, and redraw the readout once it has.

        Deferred, not immediate, and the difference matters. Most of these
        messages come from inside a validation callback, and the mode this
        scenario exists to display is changed by the machinery *after* that
        callback returns - a validator that raises is still looking at
        ``validate="key"`` at the moment it raises. Drawing from inside the
        callback showed the mode as it was a moment ago and never corrected
        it, so the one case worth seeing - validation switching itself off -
        was invisible in the very column built to show it.

        Found by driving this scenario in a pty. Its smoke test passed
        throughout, because a smoke test checks that the title appears.
        """
        last["text"] = message
        root.after_idle(describe)

    def describe():
        """Show every entry's mode and contents, which is the whole point.

        Written straight to the screen rather than into a Label because it has
        to sit outside the content area: a widget's panel is opaque and would
        cover it.
        """
        # Fixed rows under the title, NOT measured down from the bottom. The
        # readout used to live at height - 4, and a resize left it off the
        # screen for good: the support screen replays each line at the row it
        # was written at, so a line placed relative to the old height goes back
        # to a row that no longer exists. Measured by resizing a pty from 28
        # rows to 24 and watching the whole column disappear.
        row = 1
        modes = []
        for name, _y, _label, _mode in FIELDS:
            mode = str(entries[name].cget("validate"))
            # Shouted, because this is the thing a person has to notice and
            # the whole reason the column is here.
            modes.append(f"{name}={'NONE!' if mode == 'none' else mode}")
        screen.line(row, " modes  " + "  ".join(modes[:3]))
        screen.line(row + 1, "        " + "  ".join(modes[3:]))
        screen.line(row + 2, f" last: {last['text']}")
        screen.refresh()

    def digits_only(name):
        """A validator that allows digits, and says what it decided."""

        def validate(proposed):
            allowed = proposed.isdigit() or proposed == ""
            note(
                f"{name}: validator saw {proposed!r} -> "
                f"{'allowed' if allowed else 'refused'}"
            )
            return allowed

        return validate

    def complain(name):
        """An invalidcommand that takes the refused text, which Tk's can too."""

        def refused(proposed):
            note(f"{name}: REFUSED {proposed!r} (invalidcommand ran)")

        return refused

    # --------------------------------------------------------------- the entries
    for name, y, label, _mode in FIELDS:
        tkcurses.Label(area, name=f"l{name}", text=label, anchor="w").place(
            x=2, y=y, width=18
        )
        entry = tkcurses.Entry(area, name=name)
        entry.place(x=21, y=y, width=18)
        entries[name] = entry

    def reset(event=None):
        """Put every entry back, so the whole scenario can be replayed.

        Needed because most of what this demonstrates is one-way: an entry that
        has switched its own validation off stays that way, which is exactly
        the behaviour being shown.
        """
        del event
        for name, _y, _label, _mode in FIELDS:
            entry = entries[name]
            entry.configure(validate="none", state="normal")
            entry.delete(0, "end")
            entry.configure(
                validatecommand=digits_only(name), invalidcommand=complain(name)
            )
        entries["locked"].configure(state="readonly")
        entries["broken"].configure(validatecommand=explode)
        entries["forced"].configure(textvariable=held)
        for name, _y, _label, mode in FIELDS:
            entries[name].configure(validate=mode)
        last["text"] = "reset: every entry validating again"
        describe()
        return "break"

    def explode(proposed):
        """A validator that fails, which is one of the three ways Tk gives up."""
        note(f"broken: validator raised on {proposed!r}")
        raise RuntimeError("this validator is broken")

    held = tkcurses.StringVar(root, "")

    # ------------------------------------------------- the edits made from code
    def code_edit(name, text, at="end"):
        """A button that edits an entry, so insert() is seen as well as typing."""

        def pressed():
            entries[name].insert(at, text)
            note(
                f"{name}: insert({at!r}, {text!r}) returned, contents now "
                f"{entries[name].get()!r}"
            )

        return pressed

    tkcurses.Button(
        area, name="bx", text="insert 'x'", command=code_edit("digits", "x")
    ).place(x=42, y=0, width=14)
    tkcurses.Button(
        area, name="b7", text="insert '7'", command=code_edit("digits", "7")
    ).place(x=58, y=0, width=14)
    tkcurses.Button(
        area, name="bl", text="insert '9'", command=code_edit("locked", "9")
    ).place(x=42, y=3, width=14)

    def write_variable():
        """The forced condition: the value lands whatever the validator says."""
        held.set("xyz")
        note("forced: variable set to 'xyz' - the value lands either way")

    tkcurses.Button(area, name="bv", text="set variable", command=write_variable).place(
        x=42, y=12, width=14
    )

    root.bind("<Control-r>", reset)
    reset()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
