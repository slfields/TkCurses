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

"""Saving a configuration file: whole or not at all, one save at a time."""

from __future__ import annotations

import errno
import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path

import pytest

from tkcurses._cfg import store
from tkcurses._cfg.errors import BlockedByProblems, CfgError
from tkcurses._cfg.inifile import IniFile

SRC = Path(__file__).resolve().parents[1] / "src"
ORIGINAL = b"; mine\n[input]\nescape_delay = 40\n"
IS_ROOT = os.geteuid() == 0


def setting(name: str, raw: str):
    return lambda ini: ini.set(name, raw)


def snapshot(directory: Path) -> dict[str, bytes]:
    """Every file there but the lock, which stays by design."""
    return {
        p.name: p.read_bytes()
        for p in directory.iterdir()
        if p.is_file() and not p.name.endswith(".lock")
    }


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "tkcurses.ini"
    path.write_bytes(ORIGINAL)
    return path


# -------------------------------------------------------------- a good save


def test_a_save_writes_the_edit_and_keeps_the_previous_version(config):
    saved = store.edit(config, setting("input.escape_delay", "60"))
    assert saved.changed
    assert config.read_bytes() == ORIGINAL.replace(b"40", b"60")
    assert saved.backup == config.with_name("tkcurses.ini.bak")
    assert saved.backup.read_bytes() == ORIGINAL
    assert saved.warnings == []
    assert set(snapshot(config.parent)) == {"tkcurses.ini", "tkcurses.ini.bak"}


def test_a_second_save_keeps_the_version_before_it(config):
    store.edit(config, setting("input.escape_delay", "60"))
    store.edit(config, setting("input.escape_delay", "70"))
    assert b"= 60" in config.with_name("tkcurses.ini.bak").read_bytes()


def test_an_edit_that_changes_nothing_writes_nothing(config):
    inode = config.stat().st_ino
    saved = store.edit(config, setting("input.escape_delay", "40"))
    assert not saved.changed
    assert config.stat().st_ino == inode
    assert not config.with_name("tkcurses.ini.bak").exists()


def test_a_new_file_and_its_directories_are_made(tmp_path):
    path = tmp_path / "a" / "b" / "tkcurses.ini"
    old = os.umask(0o022)
    try:
        saved = store.edit(path, setting("mouse.enabled", "off"))
    finally:
        os.umask(old)
    assert path.read_text() == "[mouse]\nenabled = false\n"
    assert saved.backup is None
    assert path.stat().st_mode & 0o777 == 0o644  # programs of every user read it


def test_the_files_permissions_are_kept(config):
    config.chmod(0o640)
    store.edit(config, setting("input.escape_delay", "60"))
    assert config.stat().st_mode & 0o777 == 0o640


def test_a_symbolic_link_is_written_through_and_stays_a_link(tmp_path):
    real = tmp_path / "dotfiles" / "tkcurses.ini"
    real.parent.mkdir()
    real.write_bytes(ORIGINAL)
    link = tmp_path / "tkcurses.ini"
    link.symlink_to(real)
    store.edit(link, setting("input.escape_delay", "60"))
    assert link.is_symlink()
    assert b"= 60" in real.read_bytes()
    assert real.with_name("tkcurses.ini.bak").exists()


def test_the_change_sees_the_file_as_it_is_under_the_lock(config):
    seen = []

    def change(ini: IniFile) -> IniFile:
        seen.append(ini.text)
        return ini

    config.write_bytes(b"[mouse]\nenabled = true\n")
    store.edit(config, change)
    assert seen == ["[mouse]\nenabled = true\n"]


def test_a_refused_edit_writes_nothing(config):
    config.write_bytes(b"[input]\nescape_delay = 5000\n[mouse]\nenabled = 1\n")
    before = snapshot(config.parent)
    with pytest.raises(BlockedByProblems):
        store.edit(config, setting("mouse.enabled", "0"))
    assert snapshot(config.parent) == before


# ------------------------------------------------- failures before the swap


def failing(name: str, error: BaseException, *, after: int = 0):
    """A stand-in for ``os.<name>`` that fails on call ``after + 1``."""
    real = getattr(os, name)
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        if len(calls) > after:
            raise error
        return real(*args, **kwargs)

    return fake


@pytest.mark.parametrize(
    ("name", "error", "status", "words"),
    [
        ("write", OSError(errno.ENOSPC, "No space left"), 8, "is full"),
        ("write", OSError(errno.EDQUOT, "Quota exceeded"), 8, "quota"),
        ("fsync", OSError(errno.EIO, "Input/output error"), 8, "Input/output"),
        ("fchmod", OSError(errno.EPERM, "Not permitted"), 6, "permission denied"),
        ("link", OSError(errno.ENOSPC, "No space left"), 8, "is full"),
        ("replace", OSError(errno.EACCES, "Denied"), 6, "permission denied"),
        ("replace", OSError(errno.EROFS, "Read-only"), 6, "read-only"),
        ("replace", OSError(errno.EXDEV, "Cross-device link"), 8, "Cross-device"),
        ("replace", KeyboardInterrupt(), 130, "interrupted"),
    ],
)
def test_a_failure_before_the_swap_changes_nothing(
    config, monkeypatch, name, error, status, words
):
    store.edit(config, setting("input.escape_delay", "50"))  # a backup to keep
    before = snapshot(config.parent)
    monkeypatch.setattr(os, name, failing(name, error))
    with pytest.raises(CfgError) as caught:
        store.edit(config, setting("input.escape_delay", "60"))
    monkeypatch.undo()
    assert caught.value.exit_code == status
    assert words in str(caught.value)
    assert "Nothing was changed." in str(caught.value)
    assert snapshot(config.parent) == before


def test_a_backup_where_hard_links_are_not_allowed_is_copied(config, monkeypatch):
    monkeypatch.setattr(os, "link", failing("link", OSError(errno.EPERM, "no")))
    saved = store.edit(config, setting("input.escape_delay", "60"))
    assert saved.backup.read_bytes() == ORIGINAL


def test_failing_to_keep_the_backup_after_the_swap_is_only_a_warning(
    config, monkeypatch
):
    # The first replace is the swap; the second names the backup.
    monkeypatch.setattr(
        os, "replace", failing("replace", OSError(errno.EIO, "I/O"), after=1)
    )
    saved = store.edit(config, setting("input.escape_delay", "60"))
    monkeypatch.undo()
    assert saved.changed and saved.backup is None
    assert saved.warnings == ["the previous version was not kept: I/O"]
    assert b"= 60" in config.read_bytes()
    assert set(snapshot(config.parent)) == {"tkcurses.ini"}


def test_a_directory_that_cannot_sync_is_not_a_failure(config, monkeypatch):
    real = os.fsync

    def fsync(fd):
        if _is_dir(fd):
            raise OSError(errno.EINVAL, "Invalid argument")
        return real(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    assert store.edit(config, setting("input.escape_delay", "60")).changed


def _is_dir(fd: int) -> bool:
    import stat

    return stat.S_ISDIR(os.fstat(fd).st_mode)


@pytest.mark.skipif(IS_ROOT, reason="root writes anywhere")
def test_a_directory_that_cannot_be_written_is_permission_denied(config):
    before = snapshot(config.parent)
    config.parent.chmod(0o555)
    try:
        with pytest.raises(store.PermissionDenied) as caught:
            store.edit(
                config,
                setting("input.escape_delay", "60"),
                admin_hint="Run it as root.",
            )
    finally:
        config.parent.chmod(0o755)
    assert caught.value.exit_code == 6
    assert str(caught.value).endswith("Nothing was changed. Run it as root.")
    assert snapshot(config.parent) == before


@pytest.mark.skipif(IS_ROOT, reason="root writes anywhere")
def test_a_file_that_is_not_writable_is_not_replaced(config):
    """The rename would succeed - it needs only the directory - but a file
    its owner made read-only is not one to rewrite behind their back."""
    config.chmod(0o444)
    with pytest.raises(store.PermissionDenied, match="permission denied"):
        store.edit(config, setting("input.escape_delay", "60"))
    assert config.read_bytes() == ORIGINAL


def test_a_file_that_cannot_be_read_as_a_configuration_is_not_touched(config):
    config.write_bytes(b"[mouse]\n[mouse]\n")
    before = snapshot(config.parent)
    with pytest.raises(CfgError) as caught:
        store.edit(config, setting("mouse.enabled", "on"))
    assert caught.value.exit_code == 5
    assert snapshot(config.parent) == before


# ------------------------------------------------------------------ locking


def test_a_held_lock_is_waited_for_then_given_up_on(config):
    fd = os.open(store.lock_path(config), os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        started = time.monotonic()
        with pytest.raises(store.LockTimeout) as caught:
            store.edit(config, setting("input.escape_delay", "60"), timeout=0.3)
        waited = time.monotonic() - started
    finally:
        os.close(fd)
    assert caught.value.exit_code == 7
    assert str(store.lock_path(config)) in str(caught.value)
    assert waited >= 0.3
    assert config.read_bytes() == ORIGINAL


def test_a_lock_released_while_waiting_is_taken(config):
    fd = os.open(store.lock_path(config), os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    threading.Timer(0.2, os.close, (fd,)).start()
    assert store.edit(config, setting("input.escape_delay", "60"), timeout=5).changed


@pytest.mark.parametrize("timeout", [-1, store.MAX_LOCK_TIMEOUT + 1])
def test_a_timeout_out_of_bounds_is_refused(config, timeout):
    with pytest.raises(ValueError, match="outside"):
        store.edit(config, setting("input.escape_delay", "60"), timeout=timeout)


INCREMENT = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from tkcurses._cfg import store

    def bump(ini):
        entry = ini.get("mouse.click_interval")
        return ini.set("mouse.click_interval", str(int(entry.value) + 1))

    for _ in range(int(sys.argv[2])):
        store.edit(Path(sys.argv[1]), bump, timeout=60)
    """
)


def test_saves_from_several_processes_at_once_all_land(tmp_path):
    """Each process adds one, many times; without the lock two read the
    same number and one addition is lost."""
    path = tmp_path / "tkcurses.ini"
    path.write_text("[mouse]\nclick_interval = 1\n")
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    workers = [
        subprocess.Popen([sys.executable, "-c", INCREMENT, str(path), "25"], env=env)
        for _ in range(4)
    ]
    assert [w.wait(timeout=120) for w in workers] == [0, 0, 0, 0]
    assert IniFile.read(path).get("mouse.click_interval").value == "101"


def test_a_reader_never_sees_a_part_written_file(config):
    """What a program starting mid-save sees: the old file or the new,
    never an empty or partial one."""
    padding = "; " + "x" * 4000 + "\n"
    config.write_text(padding * 8 + "[input]\nescape_delay = 1\n")
    done = threading.Event()

    def writer():
        for value in range(2, 202):
            store.edit(config, setting("input.escape_delay", str(value)))
        done.set()

    thread = threading.Thread(target=writer)
    thread.start()
    reads = 0
    while not done.is_set():
        ini = IniFile.parse(config.read_text())
        assert ini.get("input.escape_delay") is not None
        assert ini.text.startswith(padding * 8)
        reads += 1
    thread.join()
    assert reads > 10


# ------------------------------------------------------------------ signals

SLOW_SAVE = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    from tkcurses._cfg import store
    from tkcurses._cfg.errors import CfgError

    real = os.fsync
    def fsync(fd):
        Path(sys.argv[2]).write_text("writing")
        time.sleep(30)
        return real(fd)
    os.fsync = fsync
    try:
        store.edit(
            Path(sys.argv[1]),
            lambda ini: ini.set("input.escape_delay", "60"),
        )
    except CfgError as exc:
        print(exc, file=sys.stderr)
        sys.exit(exc.exit_code)
    """
)


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGHUP])
def test_a_signal_mid_save_backs_out(config, tmp_path, signum):
    marker = Path(tempfile.mkdtemp()) / "marker"
    before = snapshot(config.parent)
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    child = subprocess.Popen(
        [sys.executable, "-c", SLOW_SAVE, str(config), str(marker)],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 30
    while not marker.exists():
        assert child.poll() is None, child.stderr.read()
        assert time.monotonic() < deadline
        time.sleep(0.02)
    # The temporary file is on disk now: the save is half done.
    assert any(p.name.endswith(".tmp") for p in config.parent.iterdir())
    child.send_signal(signum)
    _, err = child.communicate(timeout=30)
    assert child.returncode == 130
    assert "interrupted. Nothing was changed." in err
    assert snapshot(config.parent) == before
