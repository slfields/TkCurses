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
