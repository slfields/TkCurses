"""InputHandler against a real terminal.

Keyboard translation, the select-based wait, and resize handling all need a
genuine pty, so they are driven through the harness.
"""

from __future__ import annotations

import re
import time

import pytest

pytestmark = pytest.mark.tty

LOOP = """
import curses, sys
from tkcurses._core.input import InputHandler
from tkcurses._core.screen import CursesScreen

screen = CursesScreen()
buffer = screen.start()
try:
    handler = InputHandler(screen.stdscr)
    buffer.write(0, 0, "ready")
    screen.refresh()
    row = 1
    while row < buffer.height:
        events = handler.poll()
        if not events:
            handler.wait_for_input(50)
            continue
        for event in events:
            {BODY}
        screen.refresh()
finally:
    screen.stop()
"""


def run(term, tmp_path, body):
    term.run_source(LOOP.replace("{BODY}", body), workdir=tmp_path)
    term.wait_for_text("ready")


def test_printable_keys_become_key_events(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    run(
        term,
        tmp_path,
        'buffer.write(row, 0, "sym=%s char=%s" % (event.keysym, event.char)); row += 1',
    )
    term.send_keys("A")
    term.wait_for_text("sym=A char=A")
    term.send_keys("z")
    term.wait_for_text("sym=z char=z")


def test_named_keys_translate_to_keysyms(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    run(term, tmp_path, 'buffer.write(row, 0, "sym=%s" % event.keysym); row += 1')
    term.send_keys("<Up>")
    term.wait_for_text("sym=Up")
    term.send_keys("<Left>")
    term.wait_for_text("sym=Left")
    term.send_keys("<Home>")
    term.wait_for_text("sym=Home")


def test_tab_and_escape(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    run(term, tmp_path, 'buffer.write(row, 0, "sym=%s" % event.keysym); row += 1')
    term.send_keys("<Tab>")
    term.wait_for_text("sym=Tab")


def test_control_keys_carry_the_control_modifier(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    run(
        term,
        tmp_path,
        'buffer.write(row, 0, "sym=%s mods=%d" % (event.keysym, event.modifiers));'
        " row += 1",
    )
    term.send_keys("<Control-a>")
    # MOD_CTRL is 0x02; the keysym is the base letter.
    term.wait_for_text("sym=a mods=2")


def test_return_is_not_treated_as_a_control_key(terminal, tmp_path):
    """Return arrives in the control range but is a key in its own right."""
    term = terminal(cols=40, rows=8)
    run(
        term,
        tmp_path,
        'buffer.write(row, 0, "sym=%s mods=%d" % (event.keysym, event.modifiers));'
        " row += 1",
    )
    term.send_keys("<Return>")
    term.wait_for_text("sym=Return mods=0")


def test_resize_produces_a_resize_event(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    run(
        term,
        tmp_path,
        'buffer.write(row, 0, "%s %sx%s" % (event.type, getattr(event, "width", 0),'
        ' getattr(event, "height", 0))); row += 1',
    )
    term.resize(52, 12)
    term.wait_for_text("resize 52x12")


def test_wait_for_input_returns_false_when_idle(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        import time
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            start = time.monotonic()
            got = handler.wait_for_input(120)
            elapsed = (time.monotonic() - start) * 1000
            buffer.write(0, 0, "idle=%s waited=%s" % (got, elapsed >= 100))
            screen.refresh()
            screen.stdscr.nodelay(False)
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("idle=")
    # It must report no input, and must actually have waited rather than spun.
    assert term.row(0) == "idle=False waited=True"
    term.send_keys("q")


def test_wait_for_input_returns_true_when_a_key_is_pending(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            buffer.write(0, 0, "ready")
            screen.refresh()
            got = handler.wait_for_input(5000)
            events = handler.poll()
            buffer.write(1, 0, "got=%s events=%d" % (got, len(events)))
            screen.refresh()
            screen.stdscr.nodelay(False)
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_keys("k")
    term.wait_for_text("got=True events=1")
    term.send_keys("q")


def test_mouse_support_is_reported(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            buffer.write(0, 0, "mouse=%s interval=%d" % (
                handler.mouse_available, handler.click_interval))
            screen.refresh()
            screen.stdscr.nodelay(False)
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("mouse=")
    assert "interval=200" in term.row(0)
    term.send_keys("q")


def test_click_interval_can_be_changed(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            handler.click_interval = 350
            buffer.write(0, 0, "interval=%d" % handler.click_interval)
            try:
                handler.click_interval = -1
            except ValueError as exc:
                buffer.write(1, 0, "rejected")
            screen.refresh()
            screen.stdscr.nodelay(False)
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("interval=350")
    assert term.row(1) == "rejected"
    term.send_keys("q")


def test_negative_timeout_is_rejected(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        import sys
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            try:
                handler.wait_for_input(-5)
            except ValueError as exc:
                print("rejected: %s" % exc, file=sys.stderr, flush=True)
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "rejected:" in t.stderr, message="the rejection")
    assert "must not be negative" in term.stderr


def test_several_keys_are_drained_in_one_poll(terminal, tmp_path):
    """poll() returns everything pending, not one event per call."""
    term = terminal(cols=40, rows=8)
    term.run_source(
        """
        import time
        from tkcurses._core.input import InputHandler
        from tkcurses._core.screen import CursesScreen

        screen = CursesScreen()
        buffer = screen.start()
        try:
            handler = InputHandler(screen.stdscr)
            buffer.write(0, 0, "ready")
            screen.refresh()
            handler.wait_for_input(5000)
            time.sleep(0.2)          # let the whole burst arrive
            events = handler.poll()
            buffer.write(1, 0, "drained=%d" % len(events))
            screen.refresh()
            screen.stdscr.nodelay(False)
            screen.stdscr.getch()
        finally:
            screen.stop()
        """,
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_keys("abcde")
    term.wait_for_text("drained=5")
    term.send_keys("q")


# -------------------------------------------------------------------- mouse

MOUSE_LOOP = """
import curses
from tkcurses._core.input import InputHandler
from tkcurses._core.screen import CursesScreen

screen = CursesScreen()
buffer = screen.start()
try:
    handler = InputHandler(screen.stdscr)
    buffer.write(0, 0, "ready")
    screen.refresh()
    row = 1
    while row < buffer.height:
        events = handler.poll()
        if not events:
            handler.wait_for_input(50)
            continue
        for event in events:
            if event.type != "mouse":
                continue
            buffer.write(row, 0, "%s b%d @%d,%d%s" % (
                event.state, event.button, event.x, event.y,
                "" if event.drag_end is None else " end=%d,%d" % event.drag_end,
            ))
            row += 1
        screen.refresh()
finally:
    screen.stop()
"""


def test_a_click_is_reported_at_the_right_cell(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(MOUSE_LOOP, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send_mouse(10, 5, action="press")
    term.wait_for_text("pressed b1 @10,5")


def test_a_click_arrives_as_a_press_and_a_release(terminal, tmp_path):
    """Both halves, always - the library does its own click counting.

    ncurses would rather report one CLICKED for a quick press and release in
    the same cell, and nothing at all for the release if the pointer moved a
    cell in between. InputHandler therefore holds it at mouseinterval(0) and
    MouseDecoder counts repeats itself, so a widget always hears both halves
    of a click wherever the pointer ended up.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(MOUSE_LOOP, workdir=tmp_path)
    term.wait_for_text("ready")
    term.click(7, 3)
    term.wait_for_text("pressed b1 @7,3")
    term.wait_for_text("released b1 @7,3")


def test_a_slow_press_and_release_are_reported_separately(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(MOUSE_LOOP, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send_mouse(7, 3, action="press")
    term.wait_for_text("pressed b1 @7,3")
    # This test is about timing: the release has to fall outside the 200ms
    # multi-click window, or ncurses reports one CLICKED instead of two events.
    time.sleep(0.3)
    term.send_mouse(7, 3, action="release")
    term.wait_for_text("released b1 @7,3")


def test_right_button_is_distinguished(terminal, tmp_path):
    term = terminal(cols=40, rows=10)
    term.run_source(MOUSE_LOOP, workdir=tmp_path)
    term.wait_for_text("ready")
    term.send_mouse(4, 2, button=3, action="press")
    term.wait_for_text("pressed b3 @4,2")


def test_a_drag_reports_both_ends(terminal, tmp_path):
    """The drag inference runs against real curses reports, not a stub."""
    term = terminal(cols=40, rows=12)
    term.run_source(MOUSE_LOOP, workdir=tmp_path)
    term.wait_for_text("ready")
    # One step at a time, each acknowledged on screen before the next is sent.
    # Written as one burst the three sequences reach ncurses in a single read,
    # and its parser merges them into a different set of events - which ones
    # depends on the build. On the CI runners the press disappeared and the
    # motion arrived with no button held; with mouseinterval(0) the release
    # disappeared instead. None of that is what this test is about, so the
    # steps are separated rather than timed around.
    term.send_mouse(2, 1, action="press")
    term.wait_for_text("pressed b1 @2,1")
    term.send_mouse(8, 4, action="move")
    term.wait_for_text("drag b1 @8,4")
    term.send_mouse(15, 6, action="release")
    term.wait_for_text("released b1 @15,6 end=15,6")


def test_the_terminal_is_asked_to_report_drags(terminal, tmp_path):
    """ncurses will not ask for it, whatever mousemask says.

    mousemask accepts REPORT_MOUSE_POSITION and reports it granted, but the
    only thing ncurses sends the terminal is normal tracking - press and
    release. Nothing caught this because the harness sends motion whether
    the application asked for it or not; a real terminal does not.
    """
    term = terminal(cols=30, rows=6)
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(1500, root.quit)\n"
        "root.mainloop()\n"
        "root.destroy()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("up")
    assert b"\x1b[?1002h" in term.received


def test_hover_reporting_is_off_unless_it_is_asked_for(terminal, tmp_path):
    """1003 sends an event for every cell the pointer crosses."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(1500, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("up")
    assert b"\x1b[?1003h" not in term.received


def test_hover_reporting_can_be_turned_on(terminal, tmp_path):
    term = terminal(cols=30, rows=6, env={"TKCURSES_MOUSE_REPORT_HOVER": "1"})
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(1500, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("up")
    assert b"\x1b[?1003h" in term.received


def test_motion_reporting_can_be_turned_off(terminal, tmp_path):
    term = terminal(cols=30, rows=6, env={"TKCURSES_MOUSE_REPORT_MOTION": "0"})
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(1500, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("up")
    assert b"\x1b[?1002h" not in term.received


def test_the_terminal_is_put_back_on_the_way_out(terminal, tmp_path):
    """A terminal left reporting the mouse sends garbage to whatever runs next."""
    term = terminal(cols=30, rows=6)
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(300, root.quit)\n"
        "root.mainloop()\n"
        "root.destroy()\n",
        workdir=tmp_path,
    )
    term.wait_for_exit(timeout=10)
    assert b"\x1b[?1002l" in term.received


def test_the_motion_mode_is_written_after_the_screen_is_up(terminal, tmp_path):
    """Once at setup and once from the loop, so nothing can overtake it.

    ncurses writes its own mouse mode through its output buffer. A mode that
    goes into that buffer is at the mercy of when it is flushed and of
    whatever ncurses writes afterwards, so this one goes straight to the
    terminal, last.
    """
    term = terminal(cols=30, rows=6)
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "root.tk.screen.buffer.write(0, 0, 'up')\n"
        "root.tk.screen.refresh()\n"
        "root.after(600, root.quit)\n"
        "root.mainloop()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("up")
    term.wait_for_exit(timeout=10)
    received = term.received
    assert received.count(b"\x1b[?1002h") >= 2
    # And it is the last mouse mode set, so nothing overrides it.
    modes = re.findall(rb"\x1b\[\?([0-9;]*100[0-9][0-9;]*)h", received)
    assert modes[-1] == b"1002"


def _key_reporter() -> str:
    return (
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "buffer = root.tk.screen.buffer\n"
        "def show(event):\n"
        "    buffer.write(1, 0, 'key=%s state=%d   ' % (event.keysym, event.state))\n"
        "    root.tk.screen.refresh()\n"
        "root.bind_all('<Any-Key>', show)\n"
        "buffer.write(0, 0, 'ready')\n"
        "root.tk.screen.refresh()\n"
        "root.after(4000, root.quit)\n"
        "root.mainloop()\n"
        "root.destroy()\n"
    )


@pytest.mark.parametrize(
    ("byte", "keysym"),
    [(b"\x0e", "n"), (b"\x0f", "o"), (b"\x11", "q"), (b"\x13", "s")],
)
def test_control_keys_reach_the_application(terminal, tmp_path, byte, keysym):
    """Control-Q and Control-S are XON and XOFF to the line discipline.

    It uses them to pause and resume output and passes neither on, so an
    application that binds Control-Q - as a menu with a Ctrl+Q accelerator
    invites - never saw the key at all.
    """
    term = terminal(cols=40, rows=6)
    term.run_source(_key_reporter(), workdir=tmp_path)
    term.wait_for_text("ready")
    term.send(byte)
    term.wait_for_text(f"key={keysym} state=2")


def test_control_c_still_interrupts(terminal, tmp_path):
    """Flow control is cleared by hand rather than with raw(), which would
    also stop Control-C raising an interrupt - too much to give up."""
    term = terminal(cols=40, rows=6)
    term.run_source(
        "import tkcurses\n"
        "root = tkcurses.Tk()\n"
        "buffer = root.tk.screen.buffer\n"
        "buffer.write(0, 0, 'ready')\n"
        "root.tk.screen.refresh()\n"
        "try:\n"
        "    root.after(4000, root.quit)\n"
        "    root.mainloop()\n"
        "except KeyboardInterrupt:\n"
        "    root.destroy()\n"
        "    raise SystemExit(7)\n"
        "root.destroy()\n",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"\x03")
    assert term.wait_for_exit(timeout=10) == 7


def test_the_terminal_flow_control_is_put_back(terminal, tmp_path):
    """A tty left without XON/XOFF is a tty whose next program cannot be paused."""
    term = terminal(cols=40, rows=6)
    term.run_source(
        "import sys, termios, tkcurses\n"
        "before = termios.tcgetattr(sys.__stdin__.fileno())[0]\n"
        "root = tkcurses.Tk()\n"
        "during = termios.tcgetattr(sys.__stdin__.fileno())[0]\n"
        "root.after(200, root.quit)\n"
        "root.mainloop()\n"
        "root.destroy()\n"
        "after = termios.tcgetattr(sys.__stdin__.fileno())[0]\n"
        "ok = (before & termios.IXON) and not (during & termios.IXON)\n"
        "raise SystemExit(0 if ok and before == after else 1)\n",
        workdir=tmp_path,
    )
    assert term.wait_for_exit(timeout=10) == 0, term.stderr
