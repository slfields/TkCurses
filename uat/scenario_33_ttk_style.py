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

"""The style engine: one place to change, and everything follows.

What to do: press `r` and watch three progress bars you never touched
individually change colour together. That is the whole claim of ttk, and
everything else here is a variation on it.

Then `t` to cycle the six themes, `d` and `a` to drive one bar through its
states, `s` to give the middle bar a style of its own, and `g` to start the
indeterminate bar sweeping.

What to look for: the sample box changes character set with the theme -
corners, rails and junctions - and the separators change with it. `r`
reaches every bar at once because it names the *class*, TProgressbar. `d`
reaches only the bar that is disabled, because that came from a map rather
than a configure. And the bar given `Danger.TProgressbar` keeps the class's
trough while taking only its own colour, which is what a dotted style name
inheriting looks like.

Also `w`, which opens a window with a grip in its corner. **Drag that grip
and the window resizes.** The grip on the main screen cannot do that,
because it sits on the root, whose size is the terminal's - but a Toplevel
is the library's own window and its corner is a real handle.

Keys: `r` restyle the class, `t` next theme, `d`/`a` disable/activate the
middle bar, `s` give it its own style, `g` start or stop the sweep,
`w` open or close a resizable window, `z` put everything back, Escape quits.
"""

from __future__ import annotations

import tkcurses
from tkcurses import ttk
from uat import _support

TITLE = "33 - ttk: the style engine"


def _where(window):
    """A window's position, or a dash when there is no such window."""
    if window is None or not window.winfo_exists():
        return "-"
    return f"+{window.winfo_x()}+{window.winfo_y()}"


def build(root, screen):
    style = ttk.Style(root)
    themes = list(style.theme_names())
    state = {"theme": 0, "sweeping": False, "window": None, "bare": None}

    screen.line(0, f" {TITLE} ")
    screen.footer(
        " r restyle  t theme  d/a state  s own style  g sweep"
        "  w window  b borderless  z reset  Escape quits "
    )

    area = _support.content_area(root, top=3, bottom=2)

    # Three bars of the same class. Nothing is ever done to them one at a
    # time except by the keys that are meant to.
    bars = []
    for index in range(3):
        bar = ttk.Progressbar(
            area, name=f"bar{index}", length=24, value=30 + index * 25
        )
        bar.place(x=14, y=index)
        bars.append(bar)
    sweep = ttk.Progressbar(
        area, name="sweep", length=24, mode="indeterminate", value=0
    )
    sweep.place(x=14, y=4)

    for index, label in enumerate(("bar one", "bar two", "bar three")):
        tkcurses.Label(area, text=label, anchor="w").place(x=1, y=index, width=12)
    tkcurses.Label(area, text="sweeping", anchor="w").place(x=1, y=4, width=12)

    # The sample box, as labels inside the area rather than text written to
    # the screen behind it: the area's panel is opaque and would cover it.
    sample = [tkcurses.Label(area, name=f"sample{row}", anchor="w") for row in range(3)]
    for row, label in enumerate(sample):
        label.place(x=6, y=7 + row, width=14)

    ttk.Separator(area, name="rule1").place(x=1, y=6, width=37)
    ttk.Separator(area, name="rule2").place(x=1, y=11, width=37)
    ttk.Sizegrip(area, name="grip").place(x=38, y=12)

    def report():
        """Say what the database currently holds, so the screen is readable."""
        screen.line(
            1,
            f"  theme={themes[state['theme']]}"
            f"   TProgressbar foreground={style.lookup('TProgressbar', 'foreground')!r}"
            f"   bar two state={bars[1].state()}",
        )
        screen.line(
            2,
            f"  bar two style={bars[1].cget('style') or '(its class)'}"
            f"   sweeping={state['sweeping']}"
            f"   window={_where(state['window'])}"
            f"   borderless={_where(state['bare'])}",
        )

    def draw_sample():
        """A box in the theme's own characters, corners and junctions and all.

        Three labels rather than widgets that draw boxes, because the widgets
        that will - Notebook, Treeview - are the next cycle's work. This is
        the character set they will use.
        """
        glyphs = style.glyphs()
        rule = glyphs.horizontal * 5
        sample[0].configure(
            text=glyphs.top_left + rule + glyphs.tee_down + rule + glyphs.top_right
        )
        sample[1].configure(
            text=glyphs.vertical + " " * 5 + glyphs.vertical + " " * 5 + glyphs.vertical
        )
        sample[2].configure(
            text=glyphs.bottom_left + rule + glyphs.tee_up + rule + glyphs.bottom_right
        )

    def restyle(event=None):
        del event
        style.configure("TProgressbar", foreground="green")
        style.map(
            "TProgressbar",
            foreground=[("disabled", "red"), ("active", "yellow")],
        )
        report()
        screen.refresh()
        return "break"

    def next_theme(event=None):
        del event
        state["theme"] = (state["theme"] + 1) % len(themes)
        style.theme_use(themes[state["theme"]])
        draw_sample()
        report()
        screen.refresh()
        return "break"

    def set_state(flags):
        def handler(event=None):
            del event
            bars[1].state(flags)
            bars[1]._redraw()
            report()
            screen.refresh()
            return "break"

        return handler

    def own_style(event=None):
        del event
        style.configure("Danger.TProgressbar", foreground="magenta")
        bars[1].configure(style="Danger.TProgressbar")
        report()
        screen.refresh()
        return "break"

    def toggle_sweep(event=None):
        del event
        if state["sweeping"]:
            sweep.stop()
        else:
            sweep.start(120)
        state["sweeping"] = not state["sweeping"]
        report()
        screen.refresh()
        return "break"

    def open_window(event=None):
        """A resizable Toplevel with a grip in its corner, to drag.

        The grip on the main screen sits on the root, whose size is the
        terminal's - nothing an application draws can change that. This one
        is on a window the library owns, where the grip is a handle rather
        than a mark.
        """
        del event
        if state.get("window") is not None and state["window"].winfo_exists():
            state["window"].destroy()
            state["window"] = None
            report()
            screen.refresh()
            return "break"
        window = tkcurses.Toplevel(root)
        window.title(" drag my title ")
        window.geometry("26x8+18+5")
        tkcurses.Label(window, text="drag my title row", anchor="w").place(x=2, y=1)
        tkcurses.Label(window, text="drag the ◢ to resize", anchor="w").place(x=2, y=2)
        tkcurses.Label(window, text="w closes it again", anchor="w").place(x=2, y=3)
        ttk.Sizegrip(window, name="wgrip").place(relx=1.0, x=-1, rely=1.0, y=-1)
        # After the class binding, not before it: a widget binding runs first,
        # so reporting here directly would print where the window still is.
        window.bind("<B1-Motion>", lambda event: root.after(0, _after_drag), add="+")
        state["window"] = window
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def _after_drag():
        """Put the screen right after a window has moved over it."""
        report()
        screen.refresh()

    def open_borderless(event=None):
        """A borderless window the *application* drags, not the library.

        This is the other half of ARCHITECTURE.md's "Window Management":
        overrideredirect(True) leaves no decoration to grab, so moving it is
        the program's job - and the code below is the textbook tkinter
        recipe, unchanged. It is here so the two halves can be compared side
        by side: press this one anywhere and it moves, because the
        application said so; press the ordinary window's body and it does
        not, because only its title row is a handle.
        """
        del event
        if state.get("bare") is not None and state["bare"].winfo_exists():
            state["bare"].destroy()
            state["bare"] = None
            _after_drag()
            return "break"
        bare = tkcurses.Toplevel(root)
        bare.overrideredirect(True)
        bare.geometry("22x3+40+14")
        tkcurses.Label(bare, text="no border - press", anchor="w").place(x=0, y=0)
        tkcurses.Label(bare, text="anywhere to drag", anchor="w").place(x=0, y=1)
        tkcurses.Label(bare, text="b closes it again", anchor="w").place(x=0, y=2)

        grab = {}

        def press(event):
            grab["x"] = event.x_root - bare.winfo_x()
            grab["y"] = event.y_root - bare.winfo_y()

        def motion(event):
            bare.geometry(
                f"22x3+{event.x_root - grab.get('x', 0)}"
                f"+{event.y_root - grab.get('y', 0)}"
            )
            root.update_layout()
            _after_drag()

        bare.bind("<Button-1>", press)
        bare.bind("<B1-Motion>", motion)
        state["bare"] = bare
        root.update_layout()
        _after_drag()
        return "break"

    def reset(event=None):
        del event
        if state.get("bare") is not None and state["bare"].winfo_exists():
            state["bare"].destroy()
        state["bare"] = None
        style.theme_use("default")
        state["theme"] = 0
        style.configure("TProgressbar", foreground="")
        style.map("TProgressbar", foreground=[])
        bars[1].state(["!disabled", "!active"])
        bars[1].configure(style="")
        if state["sweeping"]:
            toggle_sweep()
        draw_sample()
        report()
        screen.refresh()
        return "break"

    root.bind("<Key-r>", restyle)
    root.bind("<Key-t>", next_theme)
    # Exclusive on purpose. Setting `active` while `disabled` is still on
    # changes nothing visible, because the map lists disabled first and the
    # first matching entry wins - which is correct, and baffling to watch.
    root.bind("<Key-d>", set_state(["disabled", "!active"]))
    root.bind("<Key-a>", set_state(["!disabled", "active"]))
    root.bind("<Key-s>", own_style)
    root.bind("<Key-g>", toggle_sweep)
    root.bind("<Key-w>", open_window)
    root.bind("<Key-b>", open_borderless)
    root.bind("<Key-z>", reset)

    root.update_layout()
    draw_sample()
    report()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
