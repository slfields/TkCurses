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

"""Tests for the Tk root window, driven through a real pseudo-terminal.

Tk owns curses, so almost nothing about it can be checked without a terminal:
the interesting behaviour is what it does to one, and whether it gives it back.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str, *, after: str = "") -> str:
    """A root that writes to the screen, runs ``body``, then loops."""
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
{after}
"""


def test_a_root_starts_curses_and_paints(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(program('buffer.write(0, 0, "root is up")'), workdir=tmp_path)
    term.wait_for_text("root is up")


def test_the_root_knows_the_terminal_size(terminal, tmp_path):
    term = terminal(cols=52, rows=14)
    term.run_source(
        program(
            'buffer.write(0, 0, "%sx%s" % (root.winfo_width(), root.winfo_height()))'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("52x14")


def test_the_root_is_mapped_and_is_its_own_toplevel(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            'buffer.write(0, 0, "mapped=%s top=%s" % ('
            "root.winfo_ismapped(), root.winfo_toplevel() is root))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("mapped=True top=True")


def test_a_widget_defaults_to_the_root_as_its_master(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "w = tkcurses.Widget()\n"
            'buffer.write(0, 0, "master=%s" % (w.master is root))'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("master=True")


# ---------------------------------------------------------------- teardown


def test_destroying_the_root_restores_the_terminal(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
root.destroy()
print("terminal restored")
""",
        workdir=tmp_path,
    )
    term.wait_for_text("terminal restored")


def test_a_failure_while_the_root_is_live_still_restores_the_terminal(
    terminal, tmp_path
):
    """The terminal must come back even when the program dies holding it."""
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import sys
import tkcurses

root = tkcurses.Tk()
try:
    raise RuntimeError("boom")
finally:
    root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "boom" in t.stderr, message="the traceback")


def test_the_root_can_be_used_as_a_context_manager(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

with tkcurses.Tk() as root:
    root.tk.screen.buffer.write(0, 0, "inside")
    root.tk.screen.refresh()
    root.after(50, root.quit)
    root.mainloop()
print("left cleanly")
""",
        workdir=tmp_path,
    )
    term.wait_for_text("left cleanly")


def test_a_second_root_is_refused_while_one_is_live(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
try:
    tkcurses.Tk()
    outcome = "allowed"
except tkcurses.TclError:
    outcome = "refused"
finally:
    root.destroy()
print("second root:", outcome)
""",
        workdir=tmp_path,
    )
    term.wait_for_text("second root: refused")


def test_a_root_can_be_created_again_after_the_first_is_destroyed(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

tkcurses.Tk().destroy()
second = tkcurses.Tk()
second.destroy()
print("both roots ran")
""",
        workdir=tmp_path,
    )
    term.wait_for_text("both roots ran")


# -------------------------------------------------------------- event loop


def test_after_callbacks_run_in_the_loop(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def tick():\n"
            '    buffer.write(1, 0, "timer fired")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(10, tick)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("timer fired")


def test_quit_leaves_the_loop_without_destroying_the_root(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
root.after(10, root.quit)
root.mainloop()
alive = root.winfo_exists()
root.destroy()
print("after quit, alive:", alive)
""",
        workdir=tmp_path,
    )
    term.wait_for_text("after quit, alive: True")


def test_the_loop_can_be_entered_again_after_quit(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
runs = []
def stop():
    runs.append(1)
    root.quit()
for _ in range(2):
    root.after(10, stop)
    root.mainloop()
root.destroy()
print("loops run:", len(runs))
""",
        workdir=tmp_path,
    )
    term.wait_for_text("loops run: 2")


def test_mainloop_honours_a_pass_limit(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
root.mainloop(1)
root.destroy()
print("one pass done")
""",
        workdir=tmp_path,
    )
    term.wait_for_text("one pass done")


# ------------------------------------------------------------------- input


def test_a_key_reaches_a_binding_on_the_root(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def typed(event):\n"
            '    buffer.write(1, 0, "got %s" % event.keysym)\n'
            "    root.tk.screen.refresh()\n"
            'root.bind("<Key-a>", typed)\n'
            'buffer.write(0, 0, "ready")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("got a")


def test_a_key_reaches_the_focused_widget(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "child = tkcurses.Widget(root, name='child')\n"
            "def typed(event):\n"
            '    buffer.write(1, 0, "child got %s" % event.keysym)\n'
            "    root.tk.screen.refresh()\n"
            'child.bind("<Key-b>", typed)\n'
            "child.focus_set()\n"
            'buffer.write(0, 0, "ready")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"b")
    term.wait_for_text("child got b")


def test_a_terminal_resize_reaches_the_root(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def resized(event):\n"
            '    buffer.write(1, 0, "resized %sx%s" % (event.width, event.height))\n'
            "    root.tk.screen.refresh()\n"
            'root.bind("<Configure>", resized)\n'
            'buffer.write(0, 0, "ready")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.resize(56, 16)
    term.wait_for_text("resized 56x16")


def test_the_root_tracks_its_new_size_after_a_resize(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def resized(event):\n"
            '    buffer.write(2, 0, "now %sx%s" % ('
            "root.winfo_width(), root.winfo_height()))\n"
            "    root.tk.screen.refresh()\n"
            'root.bind("<Configure>", resized)\n'
            'buffer.write(0, 0, "ready")'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.resize(48, 12)
    term.wait_for_text("now 48x12")


def test_shrinking_hard_and_growing_back_leaves_no_fragment(terminal, tmp_path):
    """The whole tree, panels included, through a violent resize.

    A terminal shrunk this far scrolls the layout up its own scrollback, and
    what was a border two thirds of the way down the screen lands on top of
    the header. Nothing in the widget tree is wrong at that point - the frame
    is off screen and knows it - so the check has to be what the terminal is
    actually showing.
    """
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            'tkcurses.Label(root, text="HEADER").place(x=0, y=0)\n'
            "frame = tkcurses.Frame(\n"
            '    root, relief="solid", borderwidth=1, width=14, height=4\n'
            ")\n"
            "frame.place(x=2, y=9)\n"
            "root.update_layout()"
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "\u2500" in t.display[9], message="the frame's top edge")

    term.resize(12, 5)
    term.wait_for(lambda t: t.row(0) == "HEADER", message="the header, repainted")
    fragments = [
        row for row in term.display if set(row) & set("\u2500\u2502\u250c\u2514")
    ]
    assert not fragments, f"border left on a screen the frame is off: {fragments}"

    term.resize(40, 14)
    term.wait_for(lambda t: "\u2500" in t.display[9], message="the frame, back again")
    assert term.row(0) == "HEADER"


def test_a_toplevel_clipped_by_a_small_terminal_comes_back_whole(terminal, tmp_path):
    """Growing the terminal again has to undo the clipping it caused.

    A window is clipped to the screen rather than allowed off the edge,
    because curses refuses a panel that runs past one. Nothing lays a
    toplevel out - it is not packed, gridded or placed, so no geometry
    manager ever looks at it again - and unless the resize goes looking for
    it itself, it keeps whatever window the narrowest terminal it ever saw
    left it with, and never fills out again.
    """
    term = terminal(cols=44, rows=12)
    term.run_source(
        program(
            "for row in range(2, 10):\n"
            '    buffer.write(row, 0, "background " * 4)\n'
            "window = tkcurses.Toplevel(root, width=30, height=8)\n"
            'window.title("Wide")\n'
            'window.geometry("30x8+8+2")\n'
            "root.update_layout()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Wide")
    term.wait_for(
        lambda t: t.text_at(2, 37, 1) == "\u2510", message="the window's far corner"
    )

    term.resize(20, 12)
    # Waited out rather than watched for: the harness narrows its own screen
    # the moment it asks for the resize, so every assertion about a narrow
    # terminal is true before the application has even been told.
    term.wait_for_idle(quiet=0.4, timeout=8)

    term.resize(44, 12)
    term.wait_for(
        lambda t: t.text_at(2, 37, 1) == "\u2510",
        message="the window's far corner, back again",
    )
    assert term.text_at(3, 8, 30) == "\u2502" + " " * 28 + "\u2502", (
        f"the window is not whole again:\n{term.describe()}"
    )


def test_a_widget_cut_off_by_an_edge_is_clipped_not_wrapped(terminal, tmp_path):
    """Curses wraps a write that runs past the right edge; we must not.

    A widget the screen edge cuts in half gets a window holding only the part
    that fits, because curses will not make one that runs off the screen.
    Drawing the whole widget into it wrapped the overflow onto the next row -
    a border that ran on into the line below - instead of losing it.
    """
    term = terminal(cols=12, rows=8)
    term.run_source(
        program(
            "wide = tkcurses.Frame(root, width=30, height=3, relief='solid')\n"
            "wide.place(x=0, y=1)\n"
            "tall = tkcurses.Frame(root, width=8, height=30, relief='solid')\n"
            "tall.place(x=0, y=5)\n"
            "root.update_layout()"
        ),
        workdir=tmp_path,
    )
    # Two frames are being drawn and both are asserted on, so wait for the
    # second one's corner as well: a wait on row 1 alone returns while the
    # tall frame at row 5 may still be arriving, and the assertions below
    # about rows 5 and 6+ would then be reading an unfinished screen -
    # TkCurses-txk.
    term.wait_for(
        lambda t: "\u250c" in t.display[1] and "\u250c" in t.display[5],
        message="both frames",
    )

    # Cut off at the right: a top edge across the screen and no corner, since
    # the corner is off it. Row 2 is the frame's own middle row, which holds
    # its two vertical edges - and the right one is off screen too.
    assert term.row(1) == "\u250c" + "\u2500" * 11, term.describe()
    assert term.row(2) == "\u2502", term.describe()

    # Cut off at the bottom: the top edge and then sides all the way down,
    # and no bottom edge, because it belongs 25 rows below the screen.
    assert term.row(5) == "\u250c" + "\u2500" * 6 + "\u2510", term.describe()
    below = "\n".join(term.display[6:])
    assert "\u2514" not in below, (
        f"a bottom edge was drawn for a frame whose bottom is off screen:"
        f"\n{term.describe()}"
    )
    assert below.count("\u2502") == 4, (
        f"the sides should run to the bottom of the screen:\n{term.describe()}"
    )


def test_a_widget_resized_inside_an_unchanged_window_is_redrawn(terminal, tmp_path):
    """The window can stay the same while the widget changes size.

    A widget clipped by the screen edge has a window the size of the visible
    part, and shrinking the widget to that same size leaves the window
    untouched - so nothing looked as though it had changed, and the border
    stayed drawn for the size the widget used to be. On screen that is a box
    with no right-hand edge, which is what a widget running off the screen is
    supposed to look like, on one that now fits perfectly.
    """
    term = terminal(cols=12, rows=8)
    term.run_source(
        program(
            "box = tkcurses.Frame(root, width=30, height=3, relief='solid')\n"
            "box.place(x=0, y=1)\n"
            "root.update_layout()\n"
            "def shrink(event):\n"
            "    box.place(width=12)\n"
            "    root.update_layout()\n"
            '    buffer.write(0, 0, "narrow")\n'
            "    root.tk.screen.refresh()\n"
            'root.bind("<Key-n>", shrink)'
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "\u250c" in t.display[1], message="the frame")
    assert term.row(1) == "\u250c" + "\u2500" * 11, "it starts off screen"

    term.send(b"n")
    term.wait_for_text("narrow")
    term.wait_for(
        lambda t: t.row(1) == "\u250c" + "\u2500" * 10 + "\u2510",
        message="the frame drawn at the size it now is",
    )


def test_a_container_going_off_screen_takes_its_children_with_it(terminal, tmp_path):
    """A window dropped for being off screen must drop its children's too.

    Nothing lays the children out again: their rects are offsets from the
    container's and did not change, and the container itself is not laid out
    at all once it is off screen. Only the curses windows are wrong, so this
    is visible on the terminal and nowhere else - the child stays drawn where
    it was, on top of whatever is in that place now.

    Found in uat/scenario_11_grid at 34x9, where the fifth box is off the
    bottom and its label was drawn over the third box's, hiding it.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "keep = tkcurses.Frame(root, width=12, height=4, relief='solid')\n"
            "tkcurses.Label(keep, text='K').place(x=1, y=1)\n"
            "keep.place(x=0, y=2)\n"
            "gone = tkcurses.Frame(root, width=12, height=4)\n"
            "tkcurses.Label(gone, text='G').place(x=1, y=1)\n"
            "gone.place(x=0, y=6)\n"
            "root.update_layout()\n"
            "def banish(event):\n"
            "    gone.place(y=40)\n"
            "    root.update_layout()\n"
            '    buffer.write(0, 0, "moved")\n'
            "    root.tk.screen.refresh()\n"
            'root.bind("<Key-b>", banish)'
        ),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: t.contains("G"), message="the label to start with")
    term.send(b"b")
    term.wait_for_text("moved")
    term.wait_for(
        lambda t: not t.contains("G"), message="the label of the banished frame to go"
    )
    assert term.contains("K"), (
        f"the frame that stayed put lost its label too:\n{term.describe()}"
    )


def test_a_container_coming_back_brings_its_children_with_it(terminal, tmp_path):
    """The other direction: a window made again has to make its children's."""
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "box = tkcurses.Frame(root, width=12, height=4, relief='solid')\n"
            "tkcurses.Label(box, text='G').place(x=1, y=1)\n"
            "box.place(x=0, y=40)\n"
            "root.update_layout()\n"
            "def bring_back(event):\n"
            "    box.place(y=3)\n"
            "    root.update_layout()\n"
            '    buffer.write(0, 0, "moved")\n'
            "    root.tk.screen.refresh()\n"
            'buffer.write(0, 0, "ready")\n'
            'root.bind("<Key-b>", bring_back)'
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    assert not term.contains("G"), "the frame starts off screen"
    term.send(b"b")
    term.wait_for_text("moved")
    term.wait_for(lambda t: t.contains("G"), message="the label to come back")


def test_moving_a_container_takes_its_children_with_it(terminal, tmp_path):
    """A container that moves without resizing must relocate its children.

    Nothing in the widget tree is wrong when this fails: the child's geometry
    is an offset from its master and the master moved, so the offset still
    holds and the container's layout has no reason to run again. Only the
    curses window is left behind, which makes this visible on the terminal
    and nowhere else - the child stays drawn where its container used to be.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "frame = tkcurses.Frame(root, width=10, height=3)\n"
            "frame.pack_propagate(False)\n"
            'tkcurses.Label(frame, text="Z").pack()\n'
            "frame.place(x=0, y=2)\n"
            "root.update_layout()\n"
            "def shift():\n"
            "    frame.place(x=20, y=2)\n"
            "    root.update_layout()\n"
            '    buffer.write(0, 0, "moved")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(60, shift)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("moved")
    term.wait_for(
        lambda t: t.find_text("Z") is not None and t.find_text("Z")[1] >= 20,
        message="the label at its new column",
    )
    assert sum(row.count("Z") for row in term.display) == 1, (
        f"the label is drawn twice over:\n{term.describe()}"
    )


# ------------------------------------------------------ callback exceptions


def test_an_exception_in_a_callback_does_not_stop_the_loop(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def boom():\n"
            '    raise RuntimeError("callback failed")\n'
            "def survived():\n"
            '    buffer.write(1, 0, "still running")\n'
            "    root.tk.screen.refresh()\n"
            "root.after(10, boom)\n"
            "root.after(40, survived)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("still running")


def test_a_callback_exception_is_reported(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program("root.after(10, lambda: 1 / 0)"),
        workdir=tmp_path,
    )
    term.wait_for(
        lambda t: "ZeroDivisionError" in t.stderr, message="the reported exception"
    )


def test_report_callback_exception_can_be_overridden(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "def report(exc, val, tb):\n"
            '    buffer.write(1, 0, "reported %s" % exc.__name__)\n'
            "    root.tk.screen.refresh()\n"
            "root.report_callback_exception = report\n"
            "root.after(10, lambda: 1 / 0)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("reported ZeroDivisionError")


def test_a_reported_traceback_is_not_staircased(terminal, tmp_path):
    """curses clears ONLCR, so a bare newline does not return to column 0.

    Without the translation each line of a traceback starts where the last
    one ended and the report walks off the right edge. stderr is pointed at
    the terminal here because that is where a person running the application
    sees it; the harness otherwise keeps it on a separate pipe.
    """
    term = terminal(cols=100, rows=30)
    term.run_source(
        """
import sys
import tkcurses

root = tkcurses.Tk()
sys.stderr = sys.stdout
root.after(10, lambda: 1 / 0)
root.after(400, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ZeroDivisionError")
    lines = [line for line in term.display if line.strip()]
    # A traceback indents its source lines by four and its File lines by two.
    # Anything further right is the staircase, each line resuming where the
    # previous one stopped.
    for line in lines:
        indent = len(line) - len(line.lstrip())
        assert indent <= 4, f"staircased: {line!r}"
    assert any(line.startswith("ZeroDivisionError") for line in lines)
    assert any(line.startswith('  File "') for line in lines)


def test_a_widget_placed_off_screen_does_not_take_the_application_down(
    terminal, tmp_path
):
    """Curses refuses to move a panel past an edge, and says so with ERR.

    place() lets a widget sit partly or wholly outside its container, and Tk
    clips the result. A curses window cannot, so the panel has to cover the
    visible part only - otherwise the refusal comes back as an exception from
    inside the layout and the whole application goes down.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
box = tkcurses.Widget(root, name="box")
box._requested = tkcurses._core.geometry.Size(10, 3)
for x, y in ((-20, -20), (38, 11), (-5, 4), (200, 200), (2, 2)):
    box.place(x=x, y=y)
    root.update_layout()
buffer.write(0, 0, "survived")
root.tk.screen.refresh()
root.after(50, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("survived")
    assert "Traceback" not in term.stderr


def test_a_terminal_resize_lays_the_tree_out_again(terminal, tmp_path):
    """The root's size is set directly, so its layout must be told separately.

    Without that, anything sized against the terminal keeps the size the
    terminal used to be.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
box = tkcurses.Widget(root, name="box")
box._requested = tkcurses._core.geometry.Size(4, 1)
# Placed on the lower half: a widget's panel is opaque, and one
# covering row 0 would hide the line being asserted on.
box.place(relx=0.0, rely=0.5, relwidth=1.0, relheight=0.5)

def show(event=None):
    # <Configure> is delivered before the loop lays the tree out again, as in
    # Tk where layout happens at idle time, so a handler that wants fresh
    # child geometry has to ask for it.
    root.update_layout()
    buffer.write(0, 0, "box %s in %sx%s    " % (
        box.winfo_geometry(), root.winfo_width(), root.winfo_height()))
    root.tk.screen.refresh()

root.bind("<Configure>", show)
root.update_layout()
show()
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("box 40x6+0+6 in 40x12")
    term.resize(60, 20)
    term.wait_for_text("box 60x10+0+10 in 60x20")


def test_a_layout_recovers_from_a_terminal_too_small_to_hold_it(terminal, tmp_path):
    """Shrink until the widget has nowhere to be, then grow back.

    On the way down the widget loses its window entirely; on the way back up
    it has to get one again, at the right place. Reported from UAT scenario
    12, where a relatively placed box came back in the wrong position after a
    shrink and restore.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
box = tkcurses.Widget(root, name="box")
box._requested = tkcurses._core.geometry.Size(4, 1)
box.place(x=2, y=6, relwidth=1.0, width=-4, height=3)

def show(event=None):
    root.update_layout()
    # Two short lines rather than one long one: the screen gets narrow
    # enough in this test that a single line would be truncated away.
    buffer.write(0, 0, "%sx%s        " % (root.winfo_width(), root.winfo_height()))
    buffer.write(1, 0, "%s            " % box.winfo_geometry())
    root.tk.screen.refresh()

root.bind("<Configure>", show)
root.update_layout()
show()
root.after(8000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("36x3+2+6")
    # Too short for the widget's row to exist at all.
    term.resize(12, 4)
    term.wait_for_text("12x4")
    # And back: the geometry must be what it was, not a remembered position
    # from some intermediate size.
    term.resize(40, 12)
    term.wait_for(
        lambda t: "36x3+2+6" in t.row(1) and "40x12" in t.row(0),
        message="the restored geometry",
    )
    assert "Traceback" not in term.stderr


def test_tab_moves_the_focus_between_widgets(terminal, tmp_path):
    """Focus traversal is the application's business, not any widget's.

    tk_focusNext has existed since the base widget system; nothing bound a
    key to it until the interactive UAT went looking, so Tab did nothing at
    all in a running application.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
first = tkcurses.Button(root, text='one', name='one')
first.place(x=1, y=1)
second = tkcurses.Button(root, text='two', name='two')
second.place(x=1, y=5)

def report(event=None):
    focused = root.focus_get()
    buffer.write(10, 0, 'focus %s   ' % (focused.winfo_name() if focused else '-'))
    root.tk.screen.refresh()

root.bind_all('<FocusIn>', report)
first.focus_set()
report()
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("focus one")
    term.send_keys("<Tab>")
    term.wait_for_text("focus two")
    term.send_keys("<Tab>")
    term.wait_for_text("focus one")


def test_a_lone_escape_arrives_promptly(terminal, tmp_path):
    """ncurses waits ESCDELAY before deciding a bare Escape was meant.

    Its default is a full second, which makes the key that cancels things
    feel broken. Tk shortens it at startup; this checks the key arrives
    inside a time a person would call immediate.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
def pressed(event):
    buffer.write(0, 0, 'escaped')
    root.tk.screen.refresh()
root.bind_all('<Key-Escape>', pressed)
buffer.write(5, 0, 'ready')
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_keys("<Escape>")
    term.wait_for_text("escaped", timeout=0.6)


def test_a_modal_grab_keeps_keys_from_what_is_behind_it(terminal, tmp_path):
    """A dialog that leaks keystrokes to the window underneath is worse than none."""
    term = terminal(cols=40, rows=14)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
behind = tkcurses.Entry(root, width=20, name='behind')
behind.place(x=1, y=1)
behind.focus_set()

def report():
    buffer.write(12, 0, 'behind=%r      ' % behind.get())
    root.tk.screen.refresh()

def open_dialog(event):
    dialog = tkcurses.Toplevel(root, width=20, height=5)
    dialog.grab_set()
    dialog.focus_set()
    buffer.write(11, 0, 'dialog up')
    report()
    root.tk.screen.refresh()

root.bind_all('<Key-F2>', open_dialog)
behind.bind('<Any-Key>', lambda event: root.after_idle(report))
report()
root.after(4000, root.quit)
root.mainloop()
root.destroy()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("behind=''")
    term.send(b"ab")
    term.wait_for_text("behind='ab'")
    term.send_keys("<F2>")
    term.wait_for_text("dialog up")
    term.send(b"cd")
    term.wait_for_idle()
    # The grab holds: nothing typed since reached the field behind it.
    assert "behind='ab'" in "\n".join(term.display)


F6_TRAVERSAL = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
text = tkcurses.Text(root, name='editor', width=24, height=3)
text.place(x=0, y=1, width=24, height=3)
entry = tkcurses.Entry(root, name='field', width=20)
entry.place(x=0, y=5, width=20)

# An editor that wants Tab for indentation, which is the whole reason F6 exists.
text.bind('<Key-Tab>', lambda event: (text.insert('insert', '\\t'), 'break')[1])
text.focus_set()

def poll():
    focused = root.focus_get()
    name = focused.winfo_name() if focused else '-'
    buffer.write(9, 0, ('focus=%s text=%r' % (name, text.get('1.0', 'end-1c')))[:70].ljust(70))
    buffer.write(11, 0, 'ready')
    root.tk.screen.refresh()
    root.after(60, poll)

poll()
root.after(5000, root.quit)
root.mainloop()
"""


def test_f6_moves_the_focus_when_tab_is_spoken_for(terminal, tmp_path):
    """A Text can keep Tab for indentation and still be escapable by keyboard.

    TkCurses-87e. tkinter's Text takes Tab to insert one and gives traversal to
    Control-Tab instead. That split cannot be had in a terminal: Tab, Control-I
    and Control-Tab are all the byte 0x09, and the modern CSI encodings of
    Control-Tab are not parsed - measured, CSI 27;5;9~ arrives as ';' '9' '~',
    so pressing it in a Text would type into the document.

    So the escape is F6, with Shift-F6 to go back. Alt-arrows were considered and
    rejected: i3 and sway bind Mod1+Left/Right to window focus by default and the
    window manager would consume them. GNOME reserves Alt-F6 and Shift-Alt-F6,
    which is why the pair is plain F6 and Shift-F6.

    Driven with the escape sequences a terminal really sends - this terminal's
    terminfo gives kf6=\\E[17~ and kf18=\\E[17;2~ - rather than with a key name,
    because the point is what survives the journey.
    """
    term = terminal(cols=40, rows=13)
    term.run_source(F6_TRAVERSAL, workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for(
        lambda t: "focus=editor" in t.row(9), message="the editor to take focus"
    )

    term.send(b"\x09")  # Tab: the editor's own binding wins
    term.wait_for(
        lambda t: "\\t" in t.row(9),
        message="Tab to indent rather than traverse",
    )
    assert "focus=editor" in term.row(9), "Tab moved the focus despite the binding"

    term.send(b"\x1b[17~")  # F6
    term.wait_for(
        lambda t: "focus=field" in t.row(9), message="F6 to move the focus on"
    )

    term.send(b"\x1b[17;2~")  # Shift-F6, which arrives as the key named F18
    term.wait_for(
        lambda t: "focus=editor" in t.row(9), message="Shift-F6 to move it back"
    )

    assert "Traceback" not in term.stderr


def test_loadtk_starts_a_root_made_without_the_terminal(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk(useTk=False)
assert root.tk.screen is None
root.loadtk()
root.loadtk()
root.tk.screen.buffer.write(0, 0, "loaded late")
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("loaded late")


def _blue(cell):
    return cell.bg == "blue"


def test_a_root_given_a_background_paints_every_cell_behind_the_widgets(
    terminal, tmp_path
):
    # Tk paints a toplevel's background behind its children; the root here is
    # the whole terminal, so that is every cell no widget covers.
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'root.configure(background="blue")\n'
        'tk.Label(root, text="on top", bg="red").pack()\n'
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    for row, column in ((0, 0), (0, 39), (5, 20), (9, 0), (9, 39)):
        term.wait_for_cell(row, column, _blue, message=f"blue at {row},{column}")
    term.wait_for_cell(0, 17, lambda cell: cell.data == "o" and cell.bg == "red")


def test_the_root_background_can_be_taken_away(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'root.configure(bg="blue")\n'
        'root.after(300, lambda: root.configure(bg=""))\n'
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_cell(5, 20, _blue, message="the blue background")
    term.wait_for_cell(5, 20, lambda cell: cell.bg == "black", message="black")
    term.wait_for_cell(9, 39, lambda cell: cell.bg == "black", message="black")


def test_the_root_background_reaches_the_cells_a_resize_adds(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'root.configure(bg="blue")\n'
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_cell(9, 39, _blue, message="the blue background")
    term.resize(50, 14)
    term.wait_for_cell(13, 49, _blue, message="blue in the new corner")


def test_a_background_set_before_loadtk_is_painted_when_curses_starts(
    terminal, tmp_path
):
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk(useTk=False)\n"
        'root.configure(bg="blue")\n'
        "root.loadtk()\n"
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_cell(5, 20, _blue, message="the blue background")


def test_the_root_pads_its_children_with_its_background(terminal, tmp_path):
    # Tk 9.0.2: a root with padx=10, pady=5 puts a label packed fill="both"
    # at 10,5, and paints the padding with its background.
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'root.configure(padx=3, pady=2, bg="blue")\n'
        'tk.Label(root, text="inside", bg="red").pack(fill="both", expand=True)\n'
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_cell(2, 3, lambda cell: cell.bg == "red", message="red at 2,3")
    term.wait_for_cell(7, 36, lambda cell: cell.bg == "red", message="red at 7,36")
    for row, column in ((1, 3), (2, 2), (8, 36), (7, 37)):
        term.wait_for_cell(row, column, _blue, message=f"blue at {row},{column}")


def test_padding_set_on_a_running_root_moves_its_children(terminal, tmp_path):
    # Set after the first layout, it did nothing until the terminal resized.
    term = terminal(cols=40, rows=10)
    term.run_source(
        "import tkcurses as tk\n"
        "root = tk.Tk()\n"
        'tk.Label(root, text="inside", bg="red").pack(fill="both", expand=True)\n'
        "root.after(300, lambda: root.configure(padx=3, pady=2))\n"
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_cell(0, 0, lambda cell: cell.bg == "red", message="red at 0,0")
    term.wait_for_cell(0, 0, lambda cell: cell.bg != "red", message="0,0 cleared")
    term.wait_for_cell(2, 3, lambda cell: cell.bg == "red", message="red at 2,3")


@pytest.mark.parametrize("call", ["root.update_idletasks()", "button.update()"])
def test_update_idletasks_lays_widgets_out(terminal, tmp_path, call):
    """Measured on Tk 9.0.2: a packed Button reads winfo_width() 1 before
    update_idletasks and its real width after, from the root or from a
    child; tkinter's idiom for centring a window or sizing to content
    depends on it. ``update`` from a widget does the same here."""
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "button = tkcurses.Button(root, text='Hello')\n"
            "button.pack()\n"
            f"{call}\n"
            "early = button.winfo_width()\n"
            "root.after(200, lambda: buffer.write(9, 0, "
            "f'early={early} late={button.winfo_width()}'))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("late=")
    early, late = term.display[9].split()
    assert early.split("=")[1] == late.split("=")[1] != "0"


def test_update_idletasks_shows_a_change_before_a_long_computation(terminal, tmp_path):
    """The other idiom: say "working", update_idletasks, then block. The
    screen must say it while the program is busy, not after."""
    term = terminal(cols=40, rows=10)
    term.run_source(
        program(
            "import time\n"
            "label = tkcurses.Label(root, text='idle')\n"
            "label.pack()\n"
            "def work():\n"
            "    label.configure(text='working')\n"
            "    root.update_idletasks()\n"
            "    time.sleep(3)\n"
            "    label.configure(text='finished')\n"
            "root.after(100, work)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("working", timeout=2.5)
    assert "finished" not in "\n".join(term.display)
