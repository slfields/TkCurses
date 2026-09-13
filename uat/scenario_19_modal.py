"""A modal dialog: does the grab really hold the keyboard?

What to do: press F2 to open the dialog. Try typing into the field behind it,
and try Tab. Press y or n in the dialog, or Escape to close it through its
WM_DELETE_WINDOW handler.
What to look for: while the dialog is open, nothing you type reaches the field
behind it - that is what grab_set is for, and a dialog that leaks keystrokes to
the window underneath is worse than no dialog. The count of what the background
field received must not move while the dialog is up. After the dialog closes,
the field answers the keyboard again.

Escape is bound to the WM_DELETE_WINDOW protocol rather than to destroy()
directly: nothing in a terminal raises that protocol on its own, so this is
what shows the handler is wired up at all.

F2 rather than a letter, because a focused entry consumes every printable key
and stops it reaching an application-wide binding - which is correct, and
exactly what the grab below is being asked to do on a larger scale.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "19 - a modal dialog and its grab"


def build(root, screen):
    area = _support.content_area(root)
    state = {"answer": "none", "dialog": None}

    tkcurses.Label(
        area,
        text="Type here, then press F2 and try typing again.",
        anchor="w",
    ).pack(side="top", fill="x")
    background = tkcurses.Entry(area, width=30)
    background.pack(side="top", pady=1)
    background.focus_set()

    def report():
        screen.line(0, f" {TITLE} ")
        screen.line(
            1,
            f"  background field holds {background.get()!r}  "
            f"last answer: {state['answer']}   F2 opens the dialog",
        )
        screen.footer(" Escape quits, or closes the dialog ")
        screen.refresh()

    def close(answer):
        state["answer"] = answer
        dialog = state["dialog"]
        if dialog is not None:
            dialog.grab_release()
            dialog.destroy()
            state["dialog"] = None
            background.focus_set()
        root.update_layout()
        report()

    def open_dialog(event):
        if state["dialog"] is not None:
            return "break"
        # Tall enough for the label and the button row: a dialog sized to its
        # text leaves the buttons nowhere to go, and they simply vanish.
        dialog = tkcurses.Toplevel(root, width=36, height=10)
        dialog.title("Really?")
        dialog.transient(root)
        dialog.grab_set()
        state["dialog"] = dialog
        tkcurses.Label(dialog, text="Answer y or n.\nEscape closes it.").pack(
            side="top", pady=1
        )
        buttons = tkcurses.Frame(dialog)
        buttons.pack(side="top")
        tkcurses.Button(buttons, text="Yes", command=lambda: close("yes")).pack(
            side="left", padx=1
        )
        tkcurses.Button(buttons, text="No", command=lambda: close("no")).pack(
            side="left", padx=1
        )
        dialog.protocol("WM_DELETE_WINDOW", lambda: close("closed"))
        dialog.bind("<Key-y>", lambda event: close("yes"))
        dialog.bind("<Key-n>", lambda event: close("no"))
        dialog.bind(
            "<Key-Escape>", lambda event: dialog._invoke_protocol("WM_DELETE_WINDOW")
        )
        dialog.focus_set()
        root.update_layout()
        report()
        return "break"

    root.bind_all("<Key-F2>", open_dialog)
    # On the entry rather than on "all": its class binding consumes printable
    # keys, so an application-wide one would never see them. Deferred to idle
    # so the report runs after the character has actually been inserted.
    background.bind("<Any-Key>", lambda event: root.after_idle(report))
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
