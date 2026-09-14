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

"""Message boxes and prompts, and exactly what each one answers with.

What to do: press each key in turn and answer the dialog that appears -
sometimes by pressing a button, sometimes with Escape, sometimes with Return.
Watch the line at the top, which reports what the call returned.
What to look for: the answer matches the button you pressed; Escape gives the
one the dialog's kind stands for rather than nothing; a prompt refuses a bad
value and stays up; and the background comes back exactly as it was.

The background is printed across the screen on purpose. A dialog that leaves
anything behind is easier to see against text than against blank space, and
what is behind a dialog is the thing most likely to be damaged by one.

The answers are worth reading closely, because the eight message box
functions do not agree on a return type and are not supposed to. Three give a
string, four a boolean, and one a boolean *or* None - so ``showinfo`` answers
``'ok'`` while ``askyesno`` answers ``True``, and code written as
``if askyesno(...)`` depends on the difference.
"""

from __future__ import annotations

from tkcurses import messagebox, simpledialog
from uat import _support

TITLE = "29 - dialogs: what each one answers with"

#: One key per dialog, with what to call and a word on what to expect.
DIALOGS: list[tuple[str, str, str]] = [
    ("1", "showinfo", "a string, 'ok'"),
    ("2", "showwarning", "a string, 'ok'"),
    ("3", "showerror", "a string, 'ok'"),
    ("4", "askquestion", "'yes' or 'no'"),
    ("5", "askyesno", "True or False"),
    ("6", "askokcancel", "True or False"),
    ("7", "askretrycancel", "True or False"),
    ("8", "askyesnocancel", "True, False or None"),
    ("s", "askstring", "text, or None if cancelled"),
    ("i", "askinteger", "a whole number 1-10, or None"),
    ("f", "askfloat", "a number, or None"),
]


def build(root, screen):
    for row in range(4, screen.height - 1):
        screen.line(row, "background " * (screen.width // 11 + 1))

    def report(name, value):
        screen.line(1, f"  {name} returned {value!r}   ({type(value).__name__})")
        screen.refresh()

    def ask(name, call):
        def handler(event):
            report(name, call())
            return "break"

        return handler

    calls = {
        "showinfo": lambda: messagebox.showinfo("Done", "All finished.", parent=root),
        "showwarning": lambda: messagebox.showwarning(
            "Careful", "That was close.", parent=root
        ),
        "showerror": lambda: messagebox.showerror("Oh dear", "It broke.", parent=root),
        "askquestion": lambda: messagebox.askquestion(
            "Question", "Carry on?", parent=root
        ),
        "askyesno": lambda: messagebox.askyesno("Question", "Really?", parent=root),
        "askokcancel": lambda: messagebox.askokcancel(
            "Question", "Proceed?", parent=root
        ),
        "askretrycancel": lambda: messagebox.askretrycancel(
            "Question", "Try again?", parent=root
        ),
        "askyesnocancel": lambda: messagebox.askyesnocancel(
            "Question", "Save before leaving?", parent=root
        ),
        "askstring": lambda: simpledialog.askstring(
            "Name", "What shall I call it?", parent=root
        ),
        "askinteger": lambda: simpledialog.askinteger(
            "Count", "How many? (1 to 10)", parent=root, minvalue=1, maxvalue=10
        ),
        "askfloat": lambda: simpledialog.askfloat("Weight", "How heavy?", parent=root),
    }

    for key, name, _ in DIALOGS:
        root.bind(f"<Key-{key}>", ask(name, calls[name]))

    def nested(event):
        """A dialog opened from inside another, which is what a save prompt is."""
        answer = messagebox.askyesnocancel(
            "Unsaved", "Save before closing?", parent=root
        )
        if answer:
            where = simpledialog.askstring("Save as", "File name:", parent=root)
            report("save-then-name", where)
        else:
            report("askyesnocancel", answer)
        return "break"

    root.bind("<Key-n>", nested)

    screen.line(0, f" {TITLE} ")
    screen.line(1, "  press a key")
    screen.line(2, "  " + "  ".join(f"{key} {name}" for key, name, _ in DIALOGS[:8]))
    screen.line(
        3,
        "  "
        + "  ".join(f"{key} {name}" for key, name, _ in DIALOGS[8:])
        + "   n save-then-name",
    )
    screen.footer(" Escape quits ")


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
