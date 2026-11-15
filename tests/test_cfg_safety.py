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

"""What tkcurses-cfg trusts: the paths it writes through, the files it
reads and the text it shows.

Each attack here was carried out against the command before the fix -
a save through a planted link replaced the file it pointed at, a planted
lock link made a save create a file, a FIFO hung ``check``, a value's
escape sequence reached the terminal - and each test fails without it.
Root is tested through ``euid``: an ordinary user cannot be root, and
the rule is a pure function of who is asking and who owns what.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

import pytest

from tkcurses._cfg import cli, store
from tkcurses._cfg.errors import FileSyntaxError, UnsafePath
from tkcurses._cfg.safety import MAX_SIZE, printable, read_regular, trusted_target
from tkcurses._cfg.session import Session

ME = os.geteuid()
SOMEONE_ELSE = ME + 4242

pytestmark = pytest.mark.skipif(
    ME == 0, reason="these are written for a user that is not root"
)

CONFIG = "[mouse]\nenabled = no\n"


@pytest.fixture
def home(tmp_path):
    """A directory that is the runner's own, not writable by anyone else."""
    tmp_path.chmod(0o755)
    return tmp_path


def shared(directory: Path, mode: int) -> Path:
    directory.mkdir()
    directory.chmod(mode)
    return directory


# ------------------------------------------------------------- the path


def test_a_file_of_ones_own_is_its_own_target(home):
    (home / "a.ini").write_text(CONFIG)
    assert trusted_target(home / "a.ini") == home / "a.ini"


def test_ones_own_link_is_followed_to_its_target(home):
    real = home / "dotfiles" / "tkcurses.ini"
    real.parent.mkdir()
    real.write_text(CONFIG)
    (home / "link.ini").symlink_to(real)
    assert trusted_target(home / "link.ini") == real


def test_a_directory_anyone_can_change_is_refused(home):
    planted = shared(home / "open", 0o777) / "cfg.ini"
    planted.symlink_to(home / "victim.txt")
    with pytest.raises(UnsafePath, match="anyone can change"):
        trusted_target(planted)


def test_a_sticky_directory_is_allowed_for_ones_own_file(home):
    mine = shared(home / "sticky", 0o1777) / "mine.ini"
    mine.write_text(CONFIG)
    assert trusted_target(mine) == mine


def test_a_group_writable_directory_is_allowed_for_a_user_not_for_root(home):
    group = shared(home / "group", 0o775)
    assert trusted_target(group / "x.ini") == group / "x.ini"
    with pytest.raises(UnsafePath):
        trusted_target(group / "x.ini", euid=0)


def test_a_link_belonging_to_someone_else_is_not_followed():
    """In /tmp - sticky, root's - a link made by this user is someone
    else's to a runner with another id."""
    with tempfile.TemporaryDirectory(dir="/tmp") as scratch:
        target = Path(scratch) / "victim.txt"
        target.write_text("precious")
        link = Path(tempfile.mktemp(dir="/tmp", suffix=".ini"))
        link.symlink_to(target)
        try:
            with pytest.raises(
                UnsafePath, match="is a symbolic link belonging to user"
            ):
                trusted_target(link, euid=SOMEONE_ELSE)
        finally:
            link.unlink()


def test_a_directory_belonging_to_someone_else_is_refused(home):
    with pytest.raises(UnsafePath, match="belongs to user"):
        trusted_target(home / "a.ini", euid=SOMEONE_ELSE)


def test_root_refuses_a_users_directory_and_says_how_to_change_it(home):
    with pytest.raises(UnsafePath) as caught:
        trusted_target(home / "a.ini", euid=0)
    # Refused at the first step root does not own alone: /tmp, or a
    # directory of the user's, depending on where the test runs.
    assert "belongs to user" in str(caught.value) or "other than root" in str(
        caught.value
    )
    assert "sudo -u USER tkcurses-cfg" in str(caught.value)


def test_root_refuses_tmp():
    with pytest.raises(UnsafePath, match="users other than root can change /tmp"):
        trusted_target(Path("/tmp/tkcurses.ini"), euid=0)


def test_root_accepts_the_system_wide_place():
    etc = Path("/etc")
    if etc.stat().st_uid != 0 or etc.stat().st_mode & 0o022:
        pytest.skip("this machine's /etc is not root's alone")
    path = Path("/etc/tkcurses-not-here/tkcurses.ini")
    assert trusted_target(path, euid=0) == path


@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_only_a_regular_file_is_written(home, kind):
    path = home / "thing"
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    with pytest.raises(UnsafePath, match=r"is not a regular file|is a directory"):
        trusted_target(path)


def test_dot_dot_is_walked_where_the_link_leads(home):
    """`a/link/..` is the parent of the link's target, as the kernel has it,
    not `a`, as reading the string would."""
    (home / "b" / "sub").mkdir(parents=True)
    (home / "a").mkdir()
    (home / "a" / "link").symlink_to(home / "b" / "sub")
    assert trusted_target(home / "a" / "link" / ".." / "x.ini") == home / "b" / "x.ini"


def test_directories_to_be_made_are_fine_but_not_dot_dot_after_them(home):
    assert (
        trusted_target(home / "new" / "deeper" / "x.ini")
        == home / "new" / "deeper" / "x.ini"
    )
    with pytest.raises(UnsafePath, match=r"does not exist, and \.\. follows it"):
        trusted_target(home / "new" / ".." / "x.ini")


def test_a_link_loop_is_refused(home):
    (home / "one").symlink_to(home / "two")
    (home / "two").symlink_to(home / "one")
    with pytest.raises(UnsafePath, match="more than 40 symbolic links"):
        trusted_target(home / "one")


def test_a_file_in_the_middle_of_the_path_is_refused(home):
    (home / "file").write_text("x")
    with pytest.raises(UnsafePath, match="is not a directory"):
        trusted_target(home / "file" / "x.ini")


def test_a_relative_path_is_walked_from_where_it_is_run(home, monkeypatch):
    monkeypatch.chdir(home)
    (home / "a.ini").write_text(CONFIG)
    assert trusted_target(Path("a.ini")) == home / "a.ini"


# ------------------------------------------------------------- saving


def test_a_save_through_a_planted_link_changes_nothing(home, capsys):
    victim = home / "victim.txt"
    victim.write_text("precious")
    planted = shared(home / "open", 0o777) / "cfg.ini"
    planted.symlink_to(victim)
    assert cli.main(["init", "--force", "--file", str(planted)]) == 6
    assert victim.read_text() == "precious"
    assert "will not write through it. Nothing was changed." in capsys.readouterr().err


def test_a_planted_lock_link_creates_nothing(home):
    config = home / "a.ini"
    config.write_text(CONFIG)
    elsewhere = home / "created-by-the-lock"
    (home / "a.ini.lock").symlink_to(elsewhere)
    with pytest.raises(UnsafePath, match="will not use it as a lock"):
        store.edit(config, lambda ini: ini.set("mouse.enabled", "on"))
    assert not elsewhere.exists()
    assert config.read_text() == CONFIG


def test_a_lock_is_its_owners_alone(home):
    config = home / "a.ini"
    store.edit(config, lambda ini: ini.set("mouse.enabled", "on"))
    lock = home / "a.ini.lock"
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600
    lock.chmod(0o644)  # as an earlier version left it
    store.edit(config, lambda ini: ini.set("mouse.enabled", "off"))
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


def test_nothing_new_is_writable_by_everyone_whatever_the_umask(home):
    old = os.umask(0)
    try:
        store.edit(
            home / "new" / "sub" / "a.ini", lambda ini: ini.set("mouse.enabled", "on")
        )
    finally:
        os.umask(old)
    for path, mode in (("new", 0o775), ("new/sub", 0o775), ("new/sub/a.ini", 0o664)):
        assert stat.S_IMODE((home / path).stat().st_mode) == mode, path


def test_a_saved_file_loses_set_id_bits(home):
    config = home / "a.ini"
    config.write_text(CONFIG)
    config.chmod(0o6750)
    store.edit(config, lambda ini: ini.set("mouse.enabled", "on"))
    assert stat.S_IMODE(config.stat().st_mode) == 0o750


def test_as_root_a_users_file_is_refused_before_anything_is_touched(home, monkeypatch):
    config = home / "a.ini"
    config.write_text(CONFIG)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(UnsafePath, match="sudo -u USER"):
        store.edit(config, lambda ini: ini.set("mouse.enabled", "on"))
    assert config.read_text() == CONFIG
    assert not (home / "a.ini.lock").exists()


def test_the_path_is_checked_again_after_making_its_directories(home, monkeypatch):
    """A link put where a directory was about to be made - in a sticky
    directory anyone may create names in - is caught."""
    elsewhere = home / "elsewhere"
    elsewhere.mkdir()
    real = store._make_directories

    def race(directory):
        directory.symlink_to(elsewhere)  # someone else got there first
        real(directory)

    monkeypatch.setattr(store, "_make_directories", race)
    with pytest.raises(UnsafePath, match="changed while"):
        store.edit(home / "new" / "a.ini", lambda ini: ini.set("mouse.enabled", "on"))
    assert list(elsewhere.iterdir()) == []


# ------------------------------------------------------------- reading


def test_reading_takes_only_a_small_regular_file(home):
    assert read_regular(home / "none.ini") is None
    (home / "a.ini").write_text(CONFIG)
    assert read_regular(home / "a.ini") == CONFIG.encode()
    os.mkfifo(home / "fifo.ini")
    with pytest.raises(FileSyntaxError, match="is not a regular file"):
        read_regular(home / "fifo.ini")
    with pytest.raises(FileSyntaxError, match="is not a regular file"):
        read_regular(Path("/dev/zero"))
    big = home / "big.ini"
    with big.open("wb") as f:
        f.truncate(MAX_SIZE + 1)
    with pytest.raises(FileSyntaxError, match="larger than 1024 KiB"):
        read_regular(big)


def test_check_on_a_fifo_answers_at_once(home, capsys):
    os.mkfifo(home / "fifo.ini")
    assert cli.main(["check", "--file", str(home / "fifo.ini")]) == 5
    assert "is not a regular file" in capsys.readouterr().out


def test_the_screen_shows_a_fifo_as_unreadable_and_does_not_hang(home):
    os.mkfifo(home / "user.ini")
    s = Session(home / "etc.ini", home / "user.ini", env={})
    assert s.edited["user"] is None
    assert "is not a regular file" in s.why_read_only()
    assert s.changed_on_disk() == []


def test_the_screen_says_why_it_will_not_write_a_file(home):
    planted = shared(home / "open", 0o777) / "user.ini"
    planted.write_text(CONFIG)
    s = Session(home / "etc.ini", planted, env={})
    assert (
        s.why_read_only()
        == f"Anyone can change {home / 'open'}, so it is not written through."
    )


# ------------------------------------------------------------- showing


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("\x1b[2J", "\\x1b[2J"),
        ("\x1b]52;c;aGk=\x07", "\\x1b]52;c;aGk=\\x07"),
        ("\x9b2J", "\\x9b2J"),
        ("\x7f", "\\x7f"),
        ("abc‮def", "abc\\u202edef"),
        ("tab\tand\nnewline", "tab\tand\nnewline"),
        ("café ─ 200 ms", "café ─ 200 ms"),
    ],
)
def test_control_characters_are_shown_not_obeyed(raw, shown):
    assert printable(raw) == shown


def test_no_escape_from_a_file_reaches_the_terminal(home, capfd):
    config = home / "a.ini"
    config.write_text("[mouse]\nenabled = \x1b[2Jno\n[\x1bcx]\nk = 1\n")
    for argv in (["list", "--sources"], ["check"], ["get", "mouse.enabled", "--json"]):
        cli.main([*argv, "--file", str(config)])
        out, err = capfd.readouterr()
        assert "\x1b" not in out + err, argv
    cli.main(["list", "--sources", "--file", str(config)])
    assert "\\x1b[2Jno" in capfd.readouterr().out


def test_standard_output_is_given_back_after_the_command(capsys):
    import sys

    before = sys.stdout, sys.stderr
    cli.main(["path"])
    assert (sys.stdout, sys.stderr) == before
