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

"""Reaching the system clipboard: through the terminal, or the desktop.

:class:`~tkcurses._core.clipboard.Selections` keeps the clipboard in the
process. This is how a copy leaves it, and how a paste brings in what another
application copied. There are two routes, and neither works everywhere:

**OSC 52**, ``ESC ] 52 ; c ; <base64> BEL``, asks the *terminal* to set the
clipboard. It works over SSH, which is its point, but only where the terminal
implements it - kitty, foot, WezTerm, a configured xterm, tmux - and a terminal
that does not ignores it silently. VTE, behind GNOME Terminal and Ptyxis, does
not and will not, on security grounds. So it is not sent on hope: the terminal
is **asked** first, with XTGETTCAP for ``Ms``, the terminfo capability tmux
uses to make the same decision. Measured in the author's VTE terminal
(``VTE_VERSION=8401``): ``Ms`` answered ``ESC P 0 + r ESC \\`` - an explicit
"not mine" - and an OSC 52 set was ignored. TkCurses-hpr.

**The desktop's own tool** - ``wl-copy``/``wl-paste`` on Wayland, ``xclip`` or
``xsel`` on X11 - works in any terminal, VTE included, and can read as well as
write. It only means anything on the machine the desktop is on: over SSH it
would fill the *remote* machine's clipboard, so it is not used there.

Reading through OSC 52 is not attempted. Terminals restrict it, or prompt,
for the reason VTE refused the sequence altogether: a program reading what
was copied elsewhere.

**What another application copied is not trusted.** The tool is found once,
on ``PATH``, and run by the absolute path found then: a ``PATH`` with a
relative entry such as ``.`` would otherwise run whatever ``wl-copy`` the
current directory holds, so a tool found only there is not used. A paste
asks for text, not whatever type the copier offered first, and reads at most
:data:`MAX_PASTE` bytes of it; more than that, and the paste is of nothing
from outside.
"""

from __future__ import annotations

import base64
import contextlib
import os
import select
import shutil
import subprocess
import termios
import time
import tty
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = [
    "CommandClipboard",
    "CommandPush",
    "Osc52Clipboard",
    "Route",
    "ask_terminal_for_osc52",
    "choose_route",
    "parse_osc52_answer",
]

#: XTGETTCAP for ``Ms``, then DA1 as a fence: every terminal answers DA1, so
#: its reply arriving means the first query was answered or ignored - there is
#: no need to wait out a timeout to know.
_QUERY = b"\x1bP+q" + b"Ms".hex().encode() + b"\x1b\\" + b"\x1b[c"

#: How long to wait for the fence before deciding the terminal is silent.
QUERY_TIMEOUT = 0.5


class Osc52Clipboard:
    """Copy by asking the terminal to set the clipboard. Cannot paste.

    ``target`` is OSC 52's selection letter: ``c`` for the clipboard, ``p``
    for the primary selection, which a middle click pastes.
    """

    name = "osc52"

    def __init__(
        self, write: Callable[[bytes], object] | None = None, target: str = "c"
    ) -> None:
        self._write = write or _write_to_terminal
        self._target = target.encode("ascii")

    def copy(self, text: str) -> bool:
        """Send the text to the terminal's clipboard."""
        payload = base64.b64encode(text.encode("utf-8"))
        self._write(b"\x1b]52;" + self._target + b";" + payload + b"\x07")
        return True

    def paste(self) -> str | None:
        """Never: see the module docstring."""
        return None

    def close(self) -> None:
        """Nothing is left running."""


class CommandPush:
    """Hand text to a desktop tool without waiting for it to finish.

    For the primary selection, which changes whenever a selection does: a
    copy may wait up to two seconds for its tool, which is fine for Ctrl-C
    and not for every selection. The tool is given the text and left to
    it. ``wl-copy`` and ``xclip`` read it and leave a process of their own
    serving the selection, so the one started here ends at once - unless
    the desktop keeps it waiting, as GNOME keeps ``wl-copy`` waiting for
    keyboard focus. A newer push then ends the one still waiting, since its
    text is out of date anyway.
    """

    #: The longest a push waits for its tool to take the text.
    TIMEOUT = 0.2

    def __init__(
        self,
        name: str,
        command: list[str],
        popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    ) -> None:
        self.name = name
        self._command = command
        self._popen = popen
        self._running: subprocess.Popen[bytes] | None = None

    def copy(self, text: str) -> bool:
        """Start the tool with ``text``. False if it could not be started."""
        self.close()
        try:
            process = self._popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return False
        self._running = process
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            process.communicate(text.encode("utf-8"), timeout=self.TIMEOUT)
        return True

    def close(self) -> None:
        """End a push still waiting on its tool."""
        process, self._running = self._running, None
        if process is not None and process.poll() is None:
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                process.wait(timeout=self.TIMEOUT)


#: The most a paste reads from the desktop's tool, in bytes: 16 MiB. A
#: clipboard holding more is read as holding nothing this program can use.
MAX_PASTE = 16 << 20


def _run_bounded(
    argv: list[str], *, timeout: float, limit: int = MAX_PASTE, **_: object
) -> subprocess.CompletedProcess[bytes]:
    """``subprocess.run`` for a paste, reading no more than ``limit + 1``
    bytes of what the tool writes before it is killed.

    Takes ``subprocess.run``'s keywords and ignores the others: standard
    input and error are always closed, and output is always captured.

    Raises:
        OSError: If the tool cannot be started.
        subprocess.TimeoutExpired: If it has not finished in ``timeout``.
    """
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert process.stdout is not None
    out = bytearray()
    deadline = time.monotonic() + timeout
    try:
        fd = process.stdout.fileno()
        while len(out) <= limit:
            remaining = deadline - time.monotonic()
            ready = select.select([fd], [], [], max(remaining, 0))[0]
            if not ready:
                raise subprocess.TimeoutExpired(argv, timeout)
            chunk = os.read(fd, min(1 << 16, limit + 1 - len(out)))
            if not chunk:
                break
            out += chunk
    finally:
        process.stdout.close()
        if process.poll() is None and len(out) > limit:
            with contextlib.suppress(OSError):
                process.kill()
        try:
            process.wait(timeout=max(deadline - time.monotonic(), 0.1))
        except subprocess.TimeoutExpired:
            with contextlib.suppress(OSError):
                process.kill()
            process.wait()
            raise
    return subprocess.CompletedProcess(argv, process.returncode, bytes(out), b"")


class CommandClipboard:
    """Copy and paste through the desktop's clipboard tool.

    ``run`` starts the copy, ``paste_run`` the paste; tests replace them.
    """

    def __init__(
        self,
        name: str,
        copy_command: list[str],
        paste_command: list[str],
        run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
        primary_command: list[str] | None = None,
        paste_run: Callable[..., subprocess.CompletedProcess[bytes]] | None = None,
    ) -> None:
        self.name = name
        self._copy = copy_command
        self._paste = paste_command
        self._run = run
        # A test's fake ``run`` answers pastes too, unless it names its own.
        self._paste_run = paste_run or (
            run if run is not subprocess.run else _run_bounded
        )
        #: Sets the primary selection, when the tool can.
        self.primary = (
            CommandPush(name, primary_command) if primary_command is not None else None
        )

    def copy(self, text: str) -> bool:
        """Hand the text to the tool. False if it could not be run."""
        try:
            done = self._run(
                self._copy,
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return done.returncode == 0

    def paste(self) -> str | None:
        """What the desktop's clipboard holds, or None if it cannot say.

        None covers an empty clipboard too - wl-paste fails on one - which
        the caller treats as "nothing to add to what this program has".
        """
        try:
            done = self._paste_run(
                self._paste,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if done.returncode != 0 or len(done.stdout) > MAX_PASTE:
            return None
        return done.stdout.decode("utf-8", errors="replace")


#: The desktop tools, in the order they are tried for each kind of session:
#: name, copy, paste, and setting the primary selection.
_WAYLAND_TOOLS = (
    (
        "wl-copy",
        ["wl-copy"],
        # Text only: with no type, wl-paste gives whatever the copier offered
        # first, which may be an image.
        ["wl-paste", "--no-newline", "--type", "text"],
        ["wl-copy", "--primary"],
    ),
)
_X11_TOOLS = (
    (
        "xclip",
        ["xclip", "-selection", "clipboard", "-in"],
        ["xclip", "-selection", "clipboard", "-out"],
        ["xclip", "-selection", "primary", "-in"],
    ),
    (
        "xsel",
        ["xsel", "--clipboard", "--input"],
        ["xsel", "--clipboard", "--output"],
        ["xsel", "--primary", "--input"],
    ),
)


@dataclass
class Route:
    """How copies leave, how pastes arrive, and why - for the notice."""

    #: Sends a copy out, or None if copies stay in the process.
    writer: Osc52Clipboard | CommandClipboard | None
    #: Brings another application's copy in, or None.
    reader: CommandClipboard | None
    #: One line saying what was chosen or why nothing was.
    reason: str
    #: Whether a copy that stays inside is worth telling the person about.
    #: Not when they turned the system clipboard off themselves.
    notify: bool = True
    #: Sets the system's primary selection - what a middle click pastes in
    #: other applications - or None.
    primary: Osc52Clipboard | CommandPush | None = None


def parse_osc52_answer(reply: bytes) -> bool | None:
    """What a terminal's reply to the XTGETTCAP query says about OSC 52.

    True for ``ESC P 1 + r 4d73=...`` (it has ``Ms``), False for
    ``ESC P 0 + r`` (it says it has not - VTE's answer, measured), and None
    when it did not answer the query at all.
    """
    # Lowered: the capability name comes back as hex, in either case.
    reply = reply.lower()
    if b"\x1bp1+r" + b"Ms".hex().encode() in reply:
        return True
    if b"\x1bp0+r" in reply:
        return False
    return None


def ask_terminal_for_osc52(fd: int = 0, timeout: float = QUERY_TIMEOUT) -> bool | None:
    """Ask the terminal on ``fd`` whether it supports OSC 52.

    Must run before curses starts, which would otherwise read the reply as
    keystrokes. Waits only until the DA1 fence comes back, so a terminal that
    answers costs a round trip, and one that never does costs ``timeout``.
    """
    try:
        if not os.isatty(fd):
            return None
        saved = termios.tcgetattr(fd)
    except (OSError, termios.error):
        return None
    reply = b""
    try:
        tty.setraw(fd)
        # To the terminal: standard output when that is it, as it is for
        # curses; the input side otherwise, which is the same device.
        os.write(1 if os.isatty(1) else fd, _QUERY)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], deadline - time.monotonic())
            if not ready:
                break
            reply += os.read(fd, 1024)
            if _fenced(reply):
                break
    except OSError:
        return None
    finally:
        with contextlib.suppress(OSError, termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    return parse_osc52_answer(reply)


def _fenced(reply: bytes) -> bool:
    """True once a DA1 reply - ``ESC [ ? ... c`` - has arrived."""
    start = reply.find(b"\x1b[?")
    return start >= 0 and reply.find(b"c", start) >= 0


def choose_route(
    setting: str,
    environ: Mapping[str, str],
    *,
    ask_terminal: Callable[[], bool | None],
    which: Callable[[str], str | None] = shutil.which,
) -> Route:
    """Decide how this run reaches the system clipboard.

    ``auto``: OSC 52 when the terminal says it has it, otherwise the desktop
    tool on a local session, otherwise neither. Whichever writes, the
    desktop tool also reads when there is one, so a paste brings in what
    another application copied. ``osc52`` and ``command`` force one route;
    ``off`` uses neither.
    """
    if setting == "off":
        return Route(None, None, "turned off (clipboard.system = off)", notify=False)
    tool = _desktop_tool(environ, which)
    if setting == "command":
        if tool is None:
            return Route(None, None, _no_tool_reason(environ))
        return Route(tool, tool, f"the desktop's {tool.name}", primary=tool.primary)
    if setting == "osc52":
        return Route(
            Osc52Clipboard(),
            tool,
            "OSC 52, as configured",
            primary=Osc52Clipboard(target="p"),
        )
    if ask_terminal():
        return Route(
            Osc52Clipboard(),
            tool,
            "OSC 52 - the terminal says it has it",
            primary=Osc52Clipboard(target="p"),
        )
    if tool is not None:
        return Route(tool, tool, f"the desktop's {tool.name}", primary=tool.primary)
    return Route(
        None,
        None,
        "no OSC 52, and " + _no_tool_reason(environ),
    )


def _remote(environ: Mapping[str, str]) -> bool:
    return any(
        environ.get(name) for name in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")
    )


def _desktop_tool(
    environ: Mapping[str, str], which: Callable[[str], str | None]
) -> CommandClipboard | None:
    """The clipboard tool for a local desktop session, if one is installed."""
    if _remote(environ):
        return None
    tools: tuple[tuple[str, list[str], list[str], list[str]], ...] = ()
    if environ.get("WAYLAND_DISPLAY"):
        tools += _WAYLAND_TOOLS
    if environ.get("DISPLAY"):
        tools += _X11_TOOLS
    for name, copy, paste, primary in tools:
        found = {program: which(program) for program in {copy[0], paste[0], primary[0]}}
        resolved = {
            program: path
            for program, path in found.items()
            if path and Path(path).is_absolute()
        }
        if len(resolved) == len(found):
            return CommandClipboard(
                name,
                _absolute(copy, resolved),
                _absolute(paste, resolved),
                primary_command=_absolute(primary, resolved),
            )
    return None


def _absolute(command: list[str], paths: Mapping[str, str]) -> list[str]:
    """``command`` with its program replaced by the absolute path found."""
    return [paths[command[0]], *command[1:]]


def _no_tool_reason(environ: Mapping[str, str]) -> str:
    # Short: UAT 43's readout shows this on one line of a 90-column screen.
    if _remote(environ):
        return "SSH: a desktop tool would reach the remote"
    if environ.get("WAYLAND_DISPLAY"):
        return "wl-copy not installed (wl-clipboard)"
    if environ.get("DISPLAY"):
        return "neither xclip nor xsel installed"
    return "no desktop session to reach"


def _write_to_terminal(data: bytes) -> None:
    """Write past curses, all of it, as the image overlay does."""
    written = 0
    while written < len(data):
        written += os.write(1, data[written:])
