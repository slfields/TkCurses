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

"""What ``tkcurses-cfg`` trusts: the paths it writes, the files it reads,
and the text it shows.

``tkcurses-cfg`` runs as a person on their own files and, through ``sudo``,
as root on the system-wide one - and a root that follows a path someone
else controls can be steered into any file on the machine. So:

- :func:`trusted_target` walks a path one component at a time before
  anything is written, and refuses a directory, a symbolic link or a file
  that someone other than the runner (or root) could change. The rule is
  the one ``sudoedit`` and OpenSSH's ``StrictModes`` use. Nothing on an
  accepted path can be changed by anyone else, so nothing can be swapped
  between the check and the write.
- :func:`read_regular` reads only a regular file, and only a small one: a
  FIFO given as ``--file`` would hang the command, a device exhaust it.
- :func:`printable` escapes control characters in anything shown, because
  a configuration file is text from somewhere else, and an escape sequence
  in it would otherwise drive the person's terminal.
"""

from __future__ import annotations

import os
import pwd
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from tkcurses._cfg.errors import FileSyntaxError, UnsafePath

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The largest file read as a configuration. A real one is a few hundred
#: bytes; this is room for every comment anyone would write.
MAX_SIZE = 1 << 20

#: How many symbolic links one path may pass through, as Linux allows.
MAX_LINKS = 40

_CONTROLS = [*range(0x20), 0x7F, *range(0x80, 0xA0)]
#: Bidirectional controls, which reorder what is shown around them.
_BIDI = [0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)]
_ESCAPED = {c: f"\\x{c:02x}" for c in _CONTROLS if c not in (0x09, 0x0A)}
_ESCAPED.update({c: f"\\u{c:04x}" for c in _BIDI})


def printable(text: str) -> str:
    """``text`` with every control character written out as an escape, so
    showing it cannot move the cursor, set a title, write the clipboard or
    reorder the line. A newline and a tab are kept."""
    return text.translate(_ESCAPED)


class _Printable:
    """A text stream that escapes control characters on the way through."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def write(self, text: str) -> int:
        self._stream.write(printable(text))
        return len(text)

    def __getattr__(self, name: str) -> Any:  # flush, fileno, isatty, ...
        return getattr(self._stream, name)


@contextmanager
def printable_output() -> Iterator[None]:
    """Standard output and error escape control characters until the end.

    One place for it, rather than at each of the dozens of messages that
    quote a file: a value, a section name, a path or a parser's own error
    text can each carry an escape sequence, and the one that is missed is
    the one that matters.
    """
    saved = sys.stdout, sys.stderr
    sys.stdout = _Printable(sys.stdout)
    sys.stderr = _Printable(sys.stderr)
    try:
        yield
    finally:
        sys.stdout, sys.stderr = saved


def read_regular(path: Path) -> bytes | None:
    """The contents of the regular file at ``path``; ``None`` if there is
    no file.

    Raises:
        FileSyntaxError: it is not a regular file, or larger than
            :data:`MAX_SIZE`. Nothing that is not a regular file is
            opened: opening some devices does something.
        OSError: it cannot be read.
    """
    try:
        before = path.stat()
    except FileNotFoundError:
        return None
    _regular(path, before)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC)
    try:
        _regular(path, os.fstat(fd))  # what was opened, if it was swapped
        chunks: list[bytes] = []
        size = 0
        while chunk := os.read(fd, 65536):
            size += len(chunk)
            if size > MAX_SIZE:
                raise _too_large(path)
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def trusted_target(path: Path, *, euid: int | None = None) -> Path:
    """The file a save of ``path`` writes, once every step to it is safe.

    Each directory from ``/`` down must belong to the runner or root and
    not be writable by everyone else - a sticky directory such as ``/tmp``
    excepted, where others cannot rename what is not theirs. Each symbolic
    link must belong to the runner or root, and the file, if there is one,
    must be a regular file belonging to either. Run as root, every
    directory must belong to root and be writable only by root.

    Directories that do not exist yet are fine: they will be made in the
    last one that does, which has been checked.

    Args:
        euid: Whose save this is; the process's effective user by default.

    Raises:
        UnsafePath: why not, with nothing changed.
    """
    euid = os.geteuid() if euid is None else euid
    asked = Path.cwd() / path  # joined, not normalised: .. is walked
    pending = list(asked.parts[1:])
    current = Path("/")
    _check_directory(asked, current, current.stat(), euid)
    links = 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent  # current is real: its parent is too
            continue
        candidate = current / part
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            if ".." in pending:
                raise _refused(
                    asked, f"{candidate} does not exist, and .. follows it", euid
                ) from None
            return current.joinpath(part, *pending)
        except NotADirectoryError:
            raise _refused(asked, f"{current} is not a directory", euid) from None
        if stat.S_ISLNK(info.st_mode):
            links += 1
            if links > MAX_LINKS:
                raise _refused(
                    asked,
                    f"it passes through more than {MAX_LINKS} symbolic links",
                    euid,
                )
            if info.st_uid not in (euid, 0):
                raise _refused(
                    asked,
                    f"{candidate} is a symbolic link belonging to {_who(info.st_uid)}",
                    euid,
                )
            target = candidate.readlink()
            if target.is_absolute():
                current = Path("/")
            pending = [*target.parts[1 if target.is_absolute() else 0 :], *pending]
            continue
        if not pending:
            if stat.S_ISDIR(info.st_mode):
                raise _refused(asked, f"{candidate} is a directory", euid)
            if not stat.S_ISREG(info.st_mode):
                raise _refused(asked, f"{candidate} is not a regular file", euid)
            if info.st_uid not in (euid, 0):
                raise _refused(
                    asked, f"{candidate} belongs to {_who(info.st_uid)}", euid
                )
            return candidate
        if not stat.S_ISDIR(info.st_mode):
            raise _refused(asked, f"{candidate} is not a directory", euid)
        _check_directory(asked, candidate, info, euid)
        current = candidate
    raise _refused(asked, f"{current} is a directory", euid)  # it ended in ..


def _check_directory(
    asked: Path, directory: Path, info: os.stat_result, euid: int
) -> None:
    if info.st_uid not in (euid, 0):
        raise _refused(asked, f"{directory} belongs to {_who(info.st_uid)}", euid)
    mode = info.st_mode
    if euid == 0:
        if mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise _refused(asked, f"users other than root can change {directory}", euid)
    elif mode & stat.S_IWOTH and not mode & stat.S_ISVTX:
        raise _refused(asked, f"anyone can change {directory}", euid)


def _refused(asked: Path, why: str, euid: int) -> UnsafePath:
    advice = ""
    if euid == 0:
        advice = (
            " As root, tkcurses-cfg changes only files that only root can "
            "change; to change a user's file, run it as that user: "
            "sudo -u USER tkcurses-cfg ..."
        )
    return UnsafePath(
        f"{asked}: {why}, so tkcurses-cfg will not write through it. "
        f"Nothing was changed.{advice}",
        why,
    )


def _who(uid: int) -> str:
    try:
        return f"user {pwd.getpwuid(uid).pw_name}"
    except KeyError:
        return f"user {uid}"


def _regular(path: Path, info: os.stat_result) -> None:
    if stat.S_ISREG(info.st_mode):
        if info.st_size > MAX_SIZE:
            raise _too_large(path)
        return
    kind = "a directory" if stat.S_ISDIR(info.st_mode) else "not a regular file"
    raise FileSyntaxError(
        str(path), None, f"is {kind}; a configuration file is an ordinary text file"
    )


def _too_large(path: Path) -> FileSyntaxError:
    return FileSyntaxError(
        str(path),
        None,
        f"is larger than {MAX_SIZE // 1024} KiB; a configuration file is a few "
        "hundred bytes",
    )
