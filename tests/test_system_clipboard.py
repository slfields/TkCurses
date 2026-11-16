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

"""Reaching the system clipboard: OSC 52, the desktop's tool, or neither.

The terminal replies below are the bytes measured in the author's VTE
terminal (VTE_VERSION=8401) with a raw probe, and the form XTGETTCAP gives
for a capability a terminal has. TkCurses-hpr.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import threading
import time

import pytest

from tkcurses._core.clipboard import CLIPBOARD, PRIMARY, PRIMARY_SETTLE, Selections
from tkcurses._core.errors import TclError
from tkcurses._core.system_clipboard import (
    MAX_PASTE,
    CommandClipboard,
    CommandPush,
    Osc52Clipboard,
    Route,
    _run_bounded,
    ask_terminal_for_osc52,
    choose_route,
    parse_osc52_answer,
)

#: The author's terminal, measured: "not a capability I have", then DA1.
VTE_REPLY = b"\x1bP0+r\x1b\\\x1b[?61;1;21;22;28c"
#: What a terminal with Ms answers: the capability's value, hex-encoded.
HAS_MS = b"\x1bP1+r4d73=" + b"\x1b]52;%p1%s;%p2%s\x07".hex().encode() + b"\x1b\\"


# ------------------------------------------------------------- the answer


def test_vtes_answer_says_no():
    assert parse_osc52_answer(VTE_REPLY) is False


def test_a_terminal_with_ms_says_yes_in_either_case_of_hex():
    assert parse_osc52_answer(HAS_MS + b"\x1b[?62c") is True
    assert parse_osc52_answer(HAS_MS.replace(b"4d73", b"4D73")) is True


def test_a_terminal_that_ignores_the_query_says_nothing():
    assert parse_osc52_answer(b"\x1b[?62;22c") is None


# -------------------------------------------------------------- the route


def tools(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


WAYLAND = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}


def test_off_uses_nothing_and_never_asks_the_terminal():
    asked = []
    route = choose_route(
        "off",
        WAYLAND,
        ask_terminal=lambda: asked.append(1),
        which=tools("wl-copy", "wl-paste"),
    )
    assert (route.writer, route.reader, asked) == (None, None, [])
    assert "turned off" in route.reason


def test_a_terminal_with_osc52_writes_and_the_desktop_tool_still_reads():
    route = choose_route(
        "auto", WAYLAND, ask_terminal=lambda: True, which=tools("wl-copy", "wl-paste")
    )
    assert isinstance(route.writer, Osc52Clipboard)
    assert isinstance(route.reader, CommandClipboard)
    assert route.reader.name == "wl-copy"


def test_vte_with_wl_clipboard_uses_the_desktop_tool():
    """The author's setup, once wl-clipboard is installed."""
    route = choose_route(
        "auto", WAYLAND, ask_terminal=lambda: False, which=tools("wl-copy", "wl-paste")
    )
    assert isinstance(route.writer, CommandClipboard)
    assert route.writer is route.reader
    assert route.writer.name == "wl-copy"


def test_vte_without_a_tool_says_what_to_install():
    """The author's setup as measured: VTE, Wayland, no wl-clipboard."""
    route = choose_route("auto", WAYLAND, ask_terminal=lambda: False, which=tools())
    assert (route.writer, route.reader) == (None, None)
    assert "no OSC 52" in route.reason
    assert "wl-clipboard" in route.reason


def test_x11_falls_back_to_xclip_then_xsel():
    x11 = {"DISPLAY": ":0"}
    xclip = choose_route("auto", x11, ask_terminal=lambda: None, which=tools("xclip"))
    xsel = choose_route("auto", x11, ask_terminal=lambda: None, which=tools("xsel"))
    assert (xclip.writer.name, xsel.writer.name) == ("xclip", "xsel")


@pytest.mark.parametrize("variable", ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"])
def test_over_ssh_the_desktop_tool_is_not_used(variable):
    """It would fill the remote machine's clipboard, not the person's."""
    remote = {**WAYLAND, variable: "1.2.3.4 5 6.7.8.9 22"}
    route = choose_route(
        "auto", remote, ask_terminal=lambda: False, which=tools("wl-copy", "wl-paste")
    )
    assert route.writer is None
    assert "SSH" in route.reason
    over_osc52 = choose_route(
        "auto", remote, ask_terminal=lambda: True, which=tools("wl-copy", "wl-paste")
    )
    assert isinstance(over_osc52.writer, Osc52Clipboard)
    assert over_osc52.reader is None


def test_forcing_a_route_skips_the_question():
    asked = []
    forced = choose_route(
        "osc52", {}, ask_terminal=lambda: asked.append(1), which=tools()
    )
    assert isinstance(forced.writer, Osc52Clipboard) and asked == []
    command = choose_route(
        "command", {}, ask_terminal=lambda: asked.append(1), which=tools()
    )
    assert command.writer is None and asked == []


# -------------------------------------------------------------- transports


def test_osc52_sends_the_text_base64_encoded_to_the_clipboard():
    sent = []
    Osc52Clipboard(sent.append).copy("héllo")
    assert sent == [b"\x1b]52;c;" + base64.b64encode("héllo".encode()) + b"\x07"]
    assert Osc52Clipboard(sent.append).paste() is None


def fake_run(returncode=0, stdout=b"", raises=None):
    calls = []

    def run(argv, **kw):
        calls.append((argv, kw))
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(argv, returncode, stdout, b"")

    run.calls = calls
    return run


def test_the_desktop_tool_is_handed_the_text():
    run = fake_run()
    tool = CommandClipboard("wl-copy", ["wl-copy"], ["wl-paste", "--no-newline"], run)
    assert tool.copy("héllo") is True
    argv, kw = run.calls[0]
    assert argv == ["wl-copy"] and kw["input"] == "héllo".encode()


def test_the_desktop_tool_is_read_from():
    run = fake_run(stdout=b"from firefox")
    tool = CommandClipboard("wl-copy", ["wl-copy"], ["wl-paste", "--no-newline"], run)
    assert tool.paste() == "from firefox"


@pytest.mark.parametrize(
    "run",
    [
        fake_run(returncode=1),
        fake_run(raises=OSError("gone")),
        fake_run(raises=subprocess.TimeoutExpired("wl-paste", 2)),
    ],
    ids=["fails", "missing", "hangs"],
)
def test_a_tool_that_cannot_answer_reads_as_nothing(run):
    tool = CommandClipboard("wl-copy", ["wl-copy"], ["wl-paste"], run)
    assert tool.paste() is None
    assert tool.copy("x") is False


# -------------------------------------------------------- the selections


class Recorder:
    name = "recorder"

    def __init__(self, ok=True, holds=None):
        self.sent, self.ok, self.holds = [], ok, holds

    def copy(self, text):
        self.sent.append(text)
        return self.ok

    def paste(self):
        return self.holds


def test_a_copy_is_sent_whole_after_every_append():
    selections = Selections()
    writer = Recorder()
    selections.route = Route(writer, None, "test")
    selections.clear(CLIPBOARD)
    selections.append("hel", CLIPBOARD)
    selections.append("lo", CLIPBOARD)
    assert writer.sent == ["hel", "hello"]
    assert not selections.kept_inside


def test_primary_is_not_sent():
    selections = Selections()
    writer = Recorder()
    selections.route = Route(writer, None, "test")
    selections.set("chosen", PRIMARY)
    assert writer.sent == []


def test_a_paste_reads_another_applications_copy():
    selections = Selections()
    selections.route = Route(None, Recorder(holds="from firefox"), "test")
    selections.set("ours", CLIPBOARD)
    assert selections.get(CLIPBOARD) == "from firefox"
    assert selections.held(CLIPBOARD) == "ours"


def test_an_unreadable_system_clipboard_falls_back_to_ours():
    selections = Selections()
    selections.route = Route(None, Recorder(holds=None), "test")
    with pytest.raises(TclError):
        selections.get(CLIPBOARD)
    selections.set("ours", CLIPBOARD)
    assert selections.get(CLIPBOARD) == "ours"


@pytest.mark.parametrize(
    "writer", [None, Recorder(ok=False)], ids=["no route", "failed"]
)
def test_a_copy_that_cannot_leave_is_noted(writer):
    selections = Selections()
    selections.route = Route(writer, None, "test")
    selections.set("kept", CLIPBOARD)
    assert selections.kept_inside


def test_without_a_route_nothing_is_noted():
    """No screen, as in every unit test: the question was never asked."""
    selections = Selections()
    selections.set("kept", CLIPBOARD)
    assert not selections.kept_inside


# ---------------------------------------------- asking a real terminal


def answering(reply):
    """A pseudo-terminal whose far end answers the query with ``reply``."""
    master, slave = os.openpty()

    def respond():
        try:
            asked = os.read(master, 1024)
        except OSError:
            return
        if reply is not None and b"\x1b[c" in asked:
            os.write(master, reply)

    thread = threading.Thread(target=respond, daemon=True)
    thread.start()
    return master, slave, thread


def test_asking_vte_hears_no():
    master, slave, thread = answering(VTE_REPLY)
    try:
        assert ask_terminal_for_osc52(slave, timeout=2.0) is False
    finally:
        thread.join(1)
        os.close(master)
        os.close(slave)


def test_asking_a_terminal_with_ms_hears_yes():
    master, slave, thread = answering(HAS_MS + b"\x1b[?62;22c")
    try:
        assert ask_terminal_for_osc52(slave, timeout=2.0) is True
    finally:
        thread.join(1)
        os.close(master)
        os.close(slave)


def test_a_silent_terminal_costs_the_timeout_and_no_more():
    master, slave, thread = answering(None)
    try:
        started = time.monotonic()
        assert ask_terminal_for_osc52(slave, timeout=0.3) is None
        assert time.monotonic() - started < 1.5
    finally:
        thread.join(1)
        os.close(master)
        os.close(slave)


def test_the_fence_ends_the_wait_without_the_timeout():
    """A terminal that answers costs a round trip, not the whole timeout."""
    master, slave, thread = answering(VTE_REPLY)
    try:
        started = time.monotonic()
        ask_terminal_for_osc52(slave, timeout=5.0)
        assert time.monotonic() - started < 2.0
    finally:
        thread.join(1)
        os.close(master)
        os.close(slave)


def test_not_a_terminal_is_not_asked():
    read, write = os.pipe()
    try:
        assert ask_terminal_for_osc52(read, timeout=0.2) is None
    finally:
        os.close(read)
        os.close(write)


def test_turned_off_on_purpose_is_not_reported():
    """Someone who chose off does not need telling that it is off."""
    selections = Selections()
    selections.route = choose_route("off", {}, ask_terminal=lambda: None)
    selections.set("kept", CLIPBOARD)
    assert not selections.kept_inside


#: Room for the reason on UAT 43's readout line, at its 90 columns.
READOUT_ROOM = 90 - len(" focus: target     system: ")


@pytest.mark.parametrize("setting", ["auto", "osc52", "command", "off"])
@pytest.mark.parametrize(
    "environ",
    [WAYLAND, {"DISPLAY": ":0"}, {}, {**WAYLAND, "SSH_CONNECTION": "x"}],
    ids=["wayland", "x11", "none", "ssh"],
)
@pytest.mark.parametrize("terminal_says", [True, False, None])
@pytest.mark.parametrize("installed", [(), ("wl-copy", "wl-paste"), ("xclip",)])
def test_every_reason_fits_the_readout(setting, environ, terminal_says, installed):
    route = choose_route(
        setting, environ, ask_terminal=lambda: terminal_says, which=tools(*installed)
    )
    assert len(route.reason) <= READOUT_ROOM, route.reason


# ------------------------------------------------------------- PRIMARY


def test_osc52_sets_the_primary_selection_with_its_p_target():
    sent = []
    Osc52Clipboard(write=sent.append, target="p").copy("hi")
    assert sent == [b"\x1b]52;p;" + base64.b64encode(b"hi") + b"\x07"]


@pytest.mark.parametrize(
    ("environ", "installed", "command"),
    [
        (WAYLAND, ("wl-copy", "wl-paste"), ["wl-copy", "--primary"]),
        ({"DISPLAY": ":0"}, ("xclip",), ["xclip", "-selection", "primary", "-in"]),
        ({"DISPLAY": ":0"}, ("xsel",), ["xsel", "--primary", "--input"]),
    ],
)
def test_the_desktop_tool_sets_primary_too(environ, installed, command):
    route = choose_route(
        "auto", environ, ask_terminal=lambda: False, which=tools(*installed)
    )
    assert isinstance(route.primary, CommandPush)
    # By the path found, not the name: TkCurses-tcbj.15.
    assert route.primary._command == [f"/usr/bin/{command[0]}", *command[1:]]


@pytest.mark.parametrize("setting", ["auto", "osc52"])
def test_an_osc52_route_sets_primary_by_osc52(setting):
    route = choose_route(setting, {}, ask_terminal=lambda: True, which=tools())
    sent = []
    route.primary._write = sent.append
    route.primary.copy("x")
    assert sent[0].startswith(b"\x1b]52;p;")


def test_no_route_sets_no_primary():
    for setting in ("off", "auto"):
        route = choose_route(setting, {}, ask_terminal=lambda: False, which=tools())
        assert route.primary is None


class FakeProcess:
    def __init__(self, *, stuck=False):
        self.stuck, self.given, self.killed = stuck, None, False

    def communicate(self, data, timeout):
        self.given = data
        if self.stuck:
            raise subprocess.TimeoutExpired("tool", timeout)

    def poll(self):
        return None if self.stuck and not self.killed else 0

    def kill(self):
        self.killed = True

    def wait(self, timeout):
        return 0


def started(processes):
    def popen(command, **kwargs):
        assert kwargs["start_new_session"], "never in the terminal's job"
        processes.append(FakeProcess(stuck=bool(len(processes) == 0)))
        return processes[-1]

    return popen


def test_a_push_hands_over_the_text_and_does_not_wait_on_a_stuck_tool():
    """GNOME keeps wl-copy waiting for focus: the push gives up waiting
    after a moment, and the next push ends the one still stuck."""
    processes = []
    push = CommandPush("wl-copy", ["wl-copy", "--primary"], popen=started(processes))
    began = time.monotonic()
    assert push.copy("first") is True
    assert time.monotonic() - began < 1
    assert processes[0].given == b"first"
    assert push.copy("second") is True
    assert processes[0].killed
    assert processes[1].given == b"second"
    push.close()
    assert not processes[1].killed, "a tool that finished is left alone"


def test_a_push_that_cannot_start_says_so():
    def missing(command, **kwargs):
        raise FileNotFoundError(command[0])

    assert CommandPush("xclip", ["xclip"], popen=missing).copy("x") is False


class Owner:
    def __init__(self, text):
        self.text = text

    def __call__(self, first, last):
        if self.text is None:
            raise TclError("PRIMARY selection doesn't exist")
        return self.text


def primary_with(text):
    selections = Selections()
    writer = Recorder()
    selections.route = Route(None, None, "test", primary=writer)
    owner = Owner(text)
    selections.own(owner, PRIMARY)
    selections.handle(owner, owner, PRIMARY)
    return selections, writer, owner


def test_primary_is_sent_once_it_holds_still():
    selections, writer, _ = primary_with("chosen")
    selections.push_primary(0.0)
    assert writer.sent == [], "seen once: it may still be moving"
    selections.push_primary(PRIMARY_SETTLE)
    assert writer.sent == ["chosen"]
    selections.push_primary(PRIMARY_SETTLE * 2)
    assert writer.sent == ["chosen"], "not sent again unchanged"


def test_a_selection_being_dragged_out_is_not_sent():
    selections, writer, owner = primary_with("a")
    for step, text in enumerate(["ab", "abc", "abcd"], start=1):
        owner.text = text
        selections.push_primary(step * PRIMARY_SETTLE)
    assert writer.sent == []
    selections.push_primary(4 * PRIMARY_SETTLE)
    assert writer.sent == ["abcd"]


def test_primary_is_looked_at_only_every_settle_interval():
    selections, writer, _ = primary_with("x")
    selections.push_primary(0.0)
    selections.push_primary(PRIMARY_SETTLE / 2)
    assert writer.sent == []
    selections.push_primary(PRIMARY_SETTLE)
    assert writer.sent == ["x"]


@pytest.mark.parametrize("text", [None, ""], ids=["nothing selected", "empty"])
def test_nothing_to_send_sends_nothing(text):
    selections, writer, _ = primary_with(text)
    for step in range(3):
        selections.push_primary(step * PRIMARY_SETTLE)
    assert writer.sent == []


def test_without_an_owner_or_a_route_primary_is_not_looked_at():
    selections = Selections()
    selections.route = Route(None, None, "test", primary=Recorder())
    selections.set("held", PRIMARY)
    for step in range(3):
        selections.push_primary(step * PRIMARY_SETTLE)
    assert selections.route.primary.sent == []
    selections, writer, _ = primary_with("x")
    selections.route.primary = None
    for step in range(3):
        selections.push_primary(step * PRIMARY_SETTLE)
    assert writer.sent == []


# ------------------------------------------- what is not trusted, TkCurses-tcbj


@pytest.mark.parametrize("found", ["wl-copy", "./wl-copy", "bin/wl-copy"])
def test_a_tool_found_by_a_relative_path_is_not_run(found):
    """``PATH=.:...`` finds a ``wl-copy`` planted in the current directory;
    shutil.which then answers with a relative path, and it is refused."""
    route = choose_route(
        "command",
        {"WAYLAND_DISPLAY": "wayland-0"},
        ask_terminal=lambda: False,
        which=lambda name: found if name == "wl-copy" else f"/usr/bin/{name}",
    )
    assert route.writer is None and route.reader is None


def test_the_tool_runs_by_the_path_found_at_the_start():
    route = choose_route(
        "command",
        WAYLAND,
        ask_terminal=lambda: False,
        which=tools("wl-copy", "wl-paste"),
    )
    assert route.writer._copy == ["/usr/bin/wl-copy"]
    assert route.reader._paste[0] == "/usr/bin/wl-paste"


def test_wl_paste_is_asked_for_text_not_whatever_was_offered_first():
    route = choose_route(
        "command",
        WAYLAND,
        ask_terminal=lambda: False,
        which=tools("wl-copy", "wl-paste"),
    )
    assert route.reader._paste[-2:] == ["--type", "text"]


def test_a_paste_larger_than_the_limit_is_nothing():
    run = fake_run(stdout=b"x" * (MAX_PASTE + 1))
    tool = CommandClipboard("wl-copy", ["wl-copy"], ["wl-paste"], run)
    assert tool.paste() is None
    assert CommandClipboard(
        "w", ["c"], ["p"], fake_run(stdout=b"x" * MAX_PASTE)
    ).paste()


def _python(code):
    return [sys.executable, "-I", "-c", code]


def test_the_bounded_reader_stops_a_tool_that_never_stops_writing():
    endless = _python("import sys\nwhile True: sys.stdout.buffer.write(b'x' * 65536)")
    start = time.monotonic()
    done = _run_bounded(endless, timeout=10, limit=100_000)
    assert len(done.stdout) == 100_001
    assert done.returncode != 0
    assert time.monotonic() - start < 5


def test_the_bounded_reader_returns_what_a_tool_wrote():
    done = _run_bounded(_python("print('héllo', end='')"), timeout=10)
    assert (done.returncode, done.stdout) == (0, "héllo".encode())


def test_the_bounded_reader_gives_up_on_a_tool_that_hangs():
    with pytest.raises(subprocess.TimeoutExpired):
        _run_bounded(_python("import time; time.sleep(30)"), timeout=0.5)


def test_a_real_tool_is_read_through_the_bounded_reader():
    tool = CommandClipboard("py", ["true"], _python("print('copied', end='')"))
    assert tool.paste() == "copied"


def test_the_bounded_reader_kills_a_tool_that_outlives_its_pipe():
    """Closing the pipe ends an ordinary writer; one that ignores SIGPIPE
    and carries on would keep the paste waiting, so it is killed."""
    stubborn = _python(
        "import signal, sys, time\n"
        "signal.signal(signal.SIGPIPE, signal.SIG_IGN)\n"
        "try:\n"
        "    while True: sys.stdout.buffer.write(b'x' * 65536); sys.stdout.flush()\n"
        "except OSError:\n"
        "    time.sleep(30)"
    )
    start = time.monotonic()
    done = _run_bounded(stubborn, timeout=10, limit=100_000)
    assert len(done.stdout) == 100_001
    assert time.monotonic() - start < 5
