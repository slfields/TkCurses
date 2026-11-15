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

"""Saving a configuration file so that it is never half-written.

Two things read and write these files at once: ``tkcurses-cfg`` itself, more
than one of which may run, and every TkCurses program, which reads the file
when it starts and takes no lock to do so. So a save is built for both:

1. **Lock** - ``flock`` on ``<file>.lock`` beside the file, waited for up to
   a timeout, so two saves are one after the other and neither loses the
   other's change. The lock is held for the save alone, never while a person
   is looking at a screen.
2. **Read again and check**, under the lock: the edit is applied to the file
   as it is now, not as it was when the command started.
3. **Write a new file beside it** - same directory, so the rename below is
   on one file system and atomic - all of it, then ``fsync``, then the old
   file's permissions (and owner, when root).
4. **Keep the old one** as ``<file>.bak``: a hard link to it, made now and
   given its name only after the swap, so a failure leaves the old backup
   alone too.
5. **Swap**, with ``os.replace``, then ``fsync`` the directory.

A program starting at any moment reads the old file or the new one, whole.
Any failure before the swap - an exception, a full disk, Ctrl-C, SIGTERM or
SIGHUP - removes what was written and leaves the file and its backup exactly
as they were, and the error says so. A symbolic link is written through, at
its target, so a dotfile manager's link stays a link.
"""

from __future__ import annotations

import errno
import fcntl
import os
import signal
import tempfile
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tkcurses._cfg.errors import CfgError
from tkcurses._cfg.inifile import IniFile

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

#: How often a waiting save tries the lock again, in seconds.
_POLL = 0.05

#: What ``link`` fails with on a file system that has no hard links, or no
#: more for this file. Anything else - a full disk, say - is a failure of
#: the save, not a reason to copy instead.
_NO_HARD_LINKS = frozenset({errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK})

#: The longest a save may be told to wait for the lock, in seconds; the
#: command checks its ``--lock-timeout`` against it.
MAX_LOCK_TIMEOUT = 3600.0


class PermissionDenied(CfgError):
    """The file, its directory or its lock cannot be written."""

    exit_code = 6


class LockTimeout(CfgError):
    """Another save held the lock for longer than the timeout."""

    exit_code = 7


class StorageError(CfgError):
    """The disk is full, over quota, or failed."""

    exit_code = 8


class Interrupted(CfgError):
    """Ctrl-C, SIGTERM or SIGHUP during a save."""

    exit_code = 130


class _Terminated(BaseException):
    """SIGTERM or SIGHUP, raised where the save is so it can back out."""


@dataclass
class Saved:
    """What a save did."""

    #: The file as it now is.
    ini: IniFile
    #: Whether anything was written: an edit that changes nothing does not
    #: touch the file.
    changed: bool
    #: Where the previous version was kept, if anything was written.
    backup: Path | None = None
    #: Things that went wrong after the new file was in place, which did
    #: not undo it.
    warnings: list[str] = field(default_factory=list)


def target_of(path: Path) -> Path:
    """The file a save of ``path`` writes: a symbolic link's target."""
    return path.resolve() if path.is_symlink() else path


def lock_path(path: Path) -> Path:
    target = target_of(path)
    return target.with_name(target.name + ".lock")


def backup_path(path: Path) -> Path:
    target = target_of(path)
    return target.with_name(target.name + ".bak")


def edit(
    path: Path,
    change: Callable[[IniFile], IniFile],
    *,
    timeout: float = 10.0,
    admin_hint: str | None = None,
) -> Saved:
    """Apply ``change`` to the file at ``path`` and save the result.

    Args:
        change: Given the file as it is under the lock, returns it edited.
            Anything it raises - a refused value, say - ends the save
            before anything is written.
        timeout: Seconds to wait for another save to finish.
        admin_hint: Added to a permission error, such as how to run the
            command as root for the system-wide file.

    Raises:
        CfgError: what went wrong, carrying the command's exit status.
    """
    if not 0 <= timeout <= MAX_LOCK_TIMEOUT:
        raise ValueError(f"timeout {timeout} is outside 0-{MAX_LOCK_TIMEOUT}")
    target = target_of(path)
    with _signals_raise(), _explained(target, admin_hint):
        target.parent.mkdir(parents=True, exist_ok=True)
        with _locked(lock_path(target), timeout):
            before = IniFile.read(target)
            after = change(before)
            if after.text == before.text:
                return Saved(before, changed=False)
            if target.exists() and not os.access(target, os.W_OK):
                raise PermissionError(errno.EACCES, "not writable", str(target))
            data = after.text.encode("utf-8")
            backup, warnings = _replace(target, data)
            return Saved(after, changed=True, backup=backup, warnings=warnings)


def _replace(target: Path, data: bytes) -> tuple[Path | None, list[str]]:
    """Put ``data`` at ``target`` in one step; see the module's numbered list."""
    directory = target.parent
    old = target.stat() if target.exists() else None
    temp: str | None = None
    backup_temp: str | None = None
    try:
        fd, temp = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=directory
        )
        try:
            _write_all(fd, data)
            os.fsync(fd)
            if old is not None:
                os.fchmod(fd, old.st_mode & 0o7777)
                if os.geteuid() == 0 and (old.st_uid, old.st_gid) != (0, 0):
                    os.fchown(fd, old.st_uid, old.st_gid)
            else:
                os.fchmod(fd, 0o666 & ~_umask())
        finally:
            os.close(fd)
        if old is not None:
            backup_temp = _hold_backup(target)
        Path(temp).replace(target)
        temp = None
    except BaseException:
        for leftover in (temp, backup_temp):
            if leftover is not None:
                with suppress(OSError):
                    Path(leftover).unlink()
        raise
    # The new file is in place: nothing from here undoes it, so a failure
    # is a warning, not an error.
    warnings: list[str] = []
    backup: Path | None = None
    if backup_temp is not None:
        backup = target.with_name(target.name + ".bak")
        try:
            Path(backup_temp).replace(backup)
        except OSError as exc:
            warnings.append(f"the previous version was not kept: {exc.strerror}")
            backup = None
            with suppress(OSError):
                Path(backup_temp).unlink()
    try:
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        # Some file systems cannot sync a directory; the rename has
        # happened either way.
        pass
    return backup, warnings


def _hold_backup(target: Path) -> str:
    """The current file under a temporary name, to become the backup."""
    fd, held = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".bak.tmp", dir=target.parent
    )
    os.close(fd)
    Path(held).unlink()
    try:
        os.link(target, held)
    except OSError as exc:
        if exc.errno not in _NO_HARD_LINKS:
            raise
        # No hard links here (some network and FAT file systems): copy.
        fd = os.open(held, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(fd, target.read_bytes())
            os.fsync(fd)
            os.fchmod(fd, target.stat().st_mode & 0o7777)
        finally:
            os.close(fd)
    return held


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


@contextmanager
def _locked(path: Path, timeout: float) -> Iterator[None]:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"{path} is held by another tkcurses-cfg; waited "
                        f"{timeout:g}s. Nothing was changed. Try again, or "
                        "give a longer --lock-timeout."
                    ) from None
                time.sleep(_POLL)
        yield
    finally:
        os.close(fd)  # releases the lock


@contextmanager
def _signals_raise() -> Iterator[None]:
    """SIGTERM and SIGHUP raise, for the duration, so a save backs out
    rather than dying with a temporary file on disk."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def raise_terminated(signum: int, _frame: Any) -> None:
        raise _Terminated(signum)

    previous = {
        sig: signal.signal(sig, raise_terminated)
        for sig in (signal.SIGTERM, signal.SIGHUP)
    }
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextmanager
def _explained(target: Path, admin_hint: str | None) -> Iterator[None]:
    """Every way a save can fail, as a :class:`CfgError` for its user."""
    unchanged = "Nothing was changed."
    try:
        yield
    except CfgError:
        raise
    except (KeyboardInterrupt, _Terminated):
        raise Interrupted(f"{target}: interrupted. {unchanged}") from None
    except OSError as exc:
        where = exc.filename or target
        reason = exc.strerror or str(exc)
        if exc.errno in (errno.EACCES, errno.EPERM):
            hint = f" {admin_hint}" if admin_hint else ""
            raise PermissionDenied(
                f"{where}: permission denied. {unchanged}{hint}"
            ) from None
        if exc.errno == errno.EROFS:
            raise PermissionDenied(
                f"{where}: the file system is read-only. {unchanged}"
            ) from None
        if exc.errno == errno.ENOSPC:
            raise StorageError(
                f"{where}: the file system is full. {unchanged}"
            ) from None
        if exc.errno == errno.EDQUOT:
            raise StorageError(f"{where}: over the disk quota. {unchanged}") from None
        raise StorageError(f"{where}: {reason}. {unchanged}") from None
