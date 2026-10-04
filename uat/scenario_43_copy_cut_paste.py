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

"""Copy, cut and paste - and Ctrl-C, which copies or closes.

What to do: select text with Shift and the arrows, then cut, copy and paste
between the fields. Try the masked field and the read-only one. Try Ctrl-C
with something selected, and again with nothing selected.

What to look for: **the readout under the title**, which shows what the
clipboard holds and what the PRIMARY selection holds after every event. The
clipboard is this program's own - nothing copied here reaches another
application yet (TkCurses-hpr) - so the readout is the only place a copy can
be seen before it is pasted.

The keys, as measured in the author's terminal (TkCurses-lw2):

=================  =========================================================
cut                Ctrl-X, Ctrl-W, Shift-Delete
copy               **Ctrl-C with a selection** - with none, Ctrl-C closes;
                   Ctrl-Insert too, where the terminal passes it on
paste              Ctrl-V, Ctrl-Y (Shift-Insert is usually the terminal's)
select all         Ctrl-/
paste PRIMARY      the middle button, where it is released
=================  =========================================================

The clipboard had no acceptance before this: it came with the base class in
TkCurses-lrc.1, and nothing a person could do reached it.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "43 - Copy, cut and paste"

#: Row in the content area, name, label, and what the field starts holding.
#: Three rows apart: everything bordered is three tall (UAT 40's finding).
FIELDS = (
    (0, "source", "source", "hello world"),
    (3, "target", "target", ""),
    (6, "masked", "masked (show=*)", "secret"),
    (9, "locked", "read-only", "copy me, not cut"),
)


def build(root, screen):
    screen.line(0, f" {TITLE} ")
    screen.footer(
        " ^X cut  ^C copy (with a selection; else quits)  ^V paste  ^/ all  Esc quits "
    )
    area = _support.content_area(root, top=4, bottom=1)
    entries = {}
    last = {"text": "nothing yet"}

    for y, name, label, _text in FIELDS:
        tkcurses.Label(area, name=f"l{name}", text=label, anchor="w").place(
            x=2, y=y + 1, width=17
        )
        entry = tkcurses.Entry(area, name=name)
        entry.place(x=20, y=y, width=30)
        entries[name] = entry
    entries["masked"].configure(show="*")
    text = tkcurses.Text(area, name="text", width=40, height=3, wrap="none")
    text.place(x=20, y=12, width=42, height=5)
    tkcurses.Label(area, name="ltext", text="text", anchor="w").place(
        x=2, y=13, width=17
    )

    def held(getter):
        try:
            return repr(getter())[:30]
        except tkcurses.TclError:
            return "(empty)"

    def describe():
        """The clipboard and PRIMARY, which are the whole point.

        Polled rather than redrawn from each handler, because the handlers
        are the library's own class bindings - the thing under test - and
        this must not depend on them to report what they did.
        """
        focus = root.focus_get()
        screen.line(
            1,
            f" clipboard: {held(root.clipboard_get):<32}"
            f"  PRIMARY: {held(root.selection_get)}",
        )
        screen.line(
            2, f" focus: {focus.winfo_name() if focus is not None else '-':<10}"
        )
        screen.line(3, f" last: {last['text']}")
        screen.refresh()
        root.after(100, describe)

    def reset(event=None):
        del event
        for _y, name, _label, start in FIELDS:
            entry = entries[name]
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, start)
            entry.icursor(0)
        entries["locked"].configure(state="readonly")
        text.delete("1.0", "end")
        text.insert("1.0", "line one\nline two")
        root.clipboard_clear()
        entries["source"].focus_set()
        last["text"] = "reset: clipboard empty, focus on source"
        return "break"

    root.bind("<Control-r>", reset)
    reset()
    describe()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
