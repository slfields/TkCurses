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
