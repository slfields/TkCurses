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

"""``tkcurses-cfg``'s command line, run in-process against scratch files."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tkcurses._cfg import cli, store
from tkcurses._core.config import REMOVED, SETTINGS

SRC = Path(__file__).resolve().parents[1] / "src"
IS_ROOT = os.geteuid() == 0


class Run:
    """``tkcurses-cfg`` with its two files in a scratch directory."""

    def __init__(self, tmp_path: Path, monkeypatch, capsys) -> None:
        self.home = tmp_path / "home"
        self.system = tmp_path / "etc" / "tkcurses" / "tkcurses.ini"
        self.user = self.home / ".config" / "tkcurses" / "tkcurses.ini"
        self.home.mkdir()
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        for name in list(os.environ):
            if name.startswith("TKCURSES_"):
                monkeypatch.delenv(name)
        monkeypatch.setattr(cli, "config_paths", lambda: (self.system, self.user))
        self.capsys = capsys
        self.monkeypatch = monkeypatch

    def __call__(self, *argv: str) -> tuple[int, str, str]:
        status = cli.main(list(argv))
        out, err = self.capsys.readouterr()
        return status, out, err

    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


@pytest.fixture
def run(tmp_path, monkeypatch, capsys) -> Run:
    return Run(tmp_path, monkeypatch, capsys)


# --------------------------------------------------------------------- list


def test_list_shows_every_setting_its_value_and_source(run):
    run.write(run.system, "[mouse]\nenabled = off\n")
    run.write(run.user, "[input]\nescape_delay = 40\n")
    status, out, err = run("list")
    assert status == 0 and err == ""
    lines = out.splitlines()
    assert lines[0].split() == ["SETTING", "VALUE", "SOURCE"]
    assert len([line for line in lines if "." in line.split(" ")[0]]) == len(SETTINGS)
    assert ["mouse.enabled", "false", "system"] in [line.split() for line in lines]
    assert ["input.escape_delay", "40", "ms", "user"] in [
        line.split() for line in lines
    ]
    assert ["clipboard.system", "auto", "default"] in [line.split() for line in lines]
    assert "system:  /" in out
    assert "user:    ~/.config/tkcurses/tkcurses.ini" in out


def test_list_changed_shows_only_settings_not_at_their_default(run):
    run.write(run.user, "[input]\nescape_delay = 40\n")
    _, out, _ = run("list", "--changed")
    assert [line.split()[0] for line in out.splitlines()[1:2]] == ["input.escape_delay"]
    run.user.unlink()
    assert run("list", "--changed")[1] == "Every setting is at its default.\n"


def test_an_environment_override_is_flagged_and_explained(run):
    run.write(run.user, "[input]\nescape_delay = 40\n")
    run.monkeypatch.setenv("TKCURSES_INPUT_ESCAPE_DELAY", "7")
    _, out, _ = run("list", "--changed")
    assert ["input.escape_delay", "7", "ms", "environment", "*"] in [
        line.split() for line in out.splitlines()
    ]
    assert "* Set in this shell's environment ($TKCURSES_INPUT_ESCAPE_DELAY)" in out
    assert "overrides both files" in out


def test_list_sources_marks_the_winner_and_what_was_refused(run):
    run.write(run.system, "[input]\nescape_delay = 50\n")
    run.write(run.user, "[input]\nescape_delay = soon\n")
    run.monkeypatch.setenv("TKCURSES_INPUT_ESCAPE_DELAY", "5000")
    _, out, err = run("list", "--sources", "--changed")
    block = out.split("input.escape_delay = 1000 ms\n")[1]
    rows = [line.split()[:4] for line in block.splitlines() if line.strip()][:4]
    assert rows == [
        ["default", "25", "ms"],
        ["system", "50", "ms", str(run.system)],
        ["x", "user", "soon", "~/.config/tkcurses/tkcurses.ini"],
        [">", "environment", "1000", "ms"],
    ]
    assert "(5000 is outside 0-1000)" in block
    assert "('soon' is not a number)" in block
    assert err == ""  # each refusal is on its row; a warning would repeat it


def test_plain_list_warns_of_an_unusable_value_after_the_table(run):
    run.write(run.user, "[input]\nescape_delay = soon\n")
    run.monkeypatch.setattr(
        cli, "_warn_all", lambda w: print(*(f"warning: {x}" for x in w))
    )
    _, out, _ = run("list", "--changed")
    assert out.splitlines()[0] == "Every setting is at its default."
    assert out.splitlines()[1].startswith("warning: [input] escape_delay in ")
    assert "'soon' is not a number, using 25" in out


def test_list_defaults_says_what_each_setting_takes(run):
    _, out, _ = run("list", "--defaults")
    assert out.splitlines()[0].split() == ["SETTING", "DEFAULT", "TAKES", "VARIABLE"]
    row = next(line for line in out.splitlines() if line.startswith("input.escape"))
    assert "25 ms" in row and "of milliseconds from 0 to 1000" in row
    assert row.endswith("TKCURSES_INPUT_ESCAPE_DELAY")


def test_list_json_is_typed_and_complete(run):
    run.write(run.user, "[mouse]\nclick_interval = 300\n")
    run.monkeypatch.setenv("TKCURSES_MOUSE_ENABLED", "no")
    _, out, _ = run("list", "--json")
    data = json.loads(out)
    by_name = {s["name"]: s for s in data["settings"]}
    assert set(by_name) == {s.name for s in SETTINGS}
    assert by_name["mouse.click_interval"]["value"] == 300
    assert by_name["mouse.click_interval"]["unit"] == "milliseconds"
    assert by_name["mouse.enabled"]["unit"] is None
    assert by_name["mouse.click_interval"]["source"] == "user"
    assert by_name["mouse.click_interval"]["location"] == str(run.user)
    assert by_name["mouse.enabled"]["value"] is False
    assert by_name["mouse.enabled"]["environment_override"] is True
    assert [o["source"] for o in by_name["mouse.enabled"]["chain"]] == [
        "default",
        "environment",
    ]
    assert data["warnings"] == []


def test_defaults_and_sources_together_is_a_usage_error(run):
    with pytest.raises(SystemExit) as caught:
        run("list", "--defaults", "--sources")
    assert caught.value.code == 2


# ---------------------------------------------------------------------- get


def test_a_value_shown_to_a_person_carries_its_unit_and_one_for_a_script_not(run):
    run.write(run.user, "[mouse]\nclick_interval = 300\n")
    table = [line.split() for line in run("list")[1].splitlines()]
    assert ["mouse.click_interval", "300", "ms", "user"] in table
    assert ["mouse.enabled", "true", "default"] in table  # no unit to show
    assert run("get", "mouse.click_interval")[1] == "300\n"
    _, out, _ = run("set", "mouse.click_interval", "350")
    assert out.startswith("mouse.click_interval = 350 ms in ")


def test_set_reports_a_boolean_as_what_it_now_is(run):
    """The message reads the file's text back; ``false`` is a non-empty
    string, so showing it unparsed said ``true``."""
    assert run("set", "mouse.enabled", "off")[1].startswith("mouse.enabled = false ")
    assert "is already false" in run("set", "mouse.enabled", "no")[1]


def test_get_prints_only_the_value(run):
    run.write(run.user, "[display]\ncolor_mode = TrueColor\n")
    assert run("get", "display.color_mode") == (0, "truecolor\n", "")
    assert run("get", "mouse.enabled") == (0, "true\n", "")


def test_get_says_on_stderr_when_the_environment_decides(run):
    run.monkeypatch.setenv("TKCURSES_DISPLAY_COLOR_MODE", "8")
    status, out, err = run("get", "display.color_mode")
    assert (status, out) == (0, "8\n")
    assert "$TKCURSES_DISPLAY_COLOR_MODE sets this" in err


def test_get_json_carries_the_chain(run):
    run.write(run.user, "[input]\nescape_delay = 40\n")
    data = json.loads(run("get", "input.escape_delay", "--json")[1])
    assert (data["value"], data["source"]) == (40, "user")
    assert data["chain"][0] == {
        "source": "default",
        "location": "built-in",
        "raw": None,
        "value": 25,
        "applied": True,
        "problem": None,
    }


@pytest.mark.parametrize(
    ("name", "words"),
    [
        ("input.escape_dely", "did you mean input.escape_delay?"),
        ("escape_delay", "section.key"),
        ("debug.enabled", "no longer exists"),
        (".x", "section.key"),
    ],
)
def test_get_an_unknown_setting_is_status_3(run, name, words):
    status, out, err = run("get", name)
    assert (status, out) == (3, "")
    assert words in err
    assert err.startswith("tkcurses-cfg: ")


# ---------------------------------------------------------------------- set


def test_set_writes_your_file_and_says_so(run):
    status, out, err = run("set", "input.escape_delay", "50")
    assert (status, err) == (0, "")
    assert out == "input.escape_delay = 50 ms in ~/.config/tkcurses/tkcurses.ini\n"
    assert run.user.read_text() == "[input]\nescape_delay = 50\n"
    assert run("get", "input.escape_delay")[1] == "50\n"


def test_set_the_same_value_changes_nothing(run):
    run.write(run.user, "[mouse]\nenabled = false\n")
    _, out, _ = run("set", "mouse.enabled", "OFF")
    assert out.endswith(
        "is already false in ~/.config/tkcurses/tkcurses.ini; nothing changed\n"
    )
    assert not run.user.with_name("tkcurses.ini.bak").exists()


def test_set_a_value_the_setting_does_not_take_is_status_4(run):
    run.write(run.user, "[input]\nescape_delay = 40\n")
    status, out, err = run("set", "input.escape_delay", "-5")
    assert (status, out) == (4, "")
    assert "-5 is outside 0-1000; it takes a whole number of milliseconds" in err
    assert run.user.read_text() == "[input]\nescape_delay = 40\n"


def test_set_in_a_file_with_a_bad_value_is_refused_unless_it_fixes_it(run):
    run.write(run.user, "[mouse]\nclick_interval: 5000\n")
    status, _, err = run("set", "mouse.enabled", "off")
    assert status == 4 and "line 2: mouse.click_interval" in err
    assert run("set", "mouse.click_interval", "300")[0] == 0
    assert run("set", "mouse.enabled", "off")[0] == 0


def test_set_in_a_file_that_cannot_be_read_is_status_5(run):
    run.write(run.user, "[mouse]\nenabled = 1\nenabled = 0\n")
    status, _, err = run("set", "mouse.enabled", "on")
    assert status == 5 and "line 3" in err


def test_set_warns_when_the_environment_will_win(run):
    run.monkeypatch.setenv("TKCURSES_MOUSE_ENABLED", "1")
    _, _, err = run("set", "mouse.enabled", "off")
    assert "$TKCURSES_MOUSE_ENABLED=1 is set in this shell's environment" in err


def test_set_global_writes_the_system_file_and_warns_of_a_user_file(run):
    run.write(run.user, "[mouse]\nenabled = true\n")
    status, out, err = run("set", "--global", "mouse.enabled", "off")
    assert status == 0
    assert out == f"mouse.enabled = false in {run.system}\n"
    assert "overrides the system-wide file for that user" in err


@pytest.mark.skipif(IS_ROOT, reason="root writes anywhere")
def test_set_global_without_permission_says_how_and_is_status_6(run):
    run.system.parent.mkdir(parents=True)
    run.system.parent.chmod(0o555)
    try:
        status, _, err = run("set", "--global", "mouse.enabled", "off")
    finally:
        run.system.parent.chmod(0o755)
    assert status == 6
    assert "Nothing was changed." in err
    assert "sudo tkcurses-cfg set --global mouse.enabled off" in err


def test_set_waits_for_the_lock_then_is_status_7(run):
    run.write(run.user, "[mouse]\nenabled = true\n")
    fd = os.open(store.lock_path(run.user), os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        status, _, err = run("set", "--lock-timeout", "0.2", "mouse.enabled", "off")
    finally:
        os.close(fd)
    assert status == 7 and "--lock-timeout" in err


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "soon", "3601"])
def test_a_lock_timeout_out_of_bounds_is_a_usage_error(run, value):
    with pytest.raises(SystemExit) as caught:
        run("set", "--lock-timeout", value, "mouse.enabled", "off")
    assert caught.value.code == 2
    assert "--lock-timeout" in run.capsys.readouterr().err


def test_global_and_file_together_is_a_usage_error(run, tmp_path):
    with pytest.raises(SystemExit) as caught:
        run("set", "--global", "--file", str(tmp_path / "x.ini"), "mouse.enabled", "1")
    assert caught.value.code == 2


def test_a_directory_is_not_a_file(run, tmp_path):
    with pytest.raises(SystemExit) as caught:
        run("set", "--file", str(tmp_path), "mouse.enabled", "1")
    assert caught.value.code == 2
    assert "is a directory" in run.capsys.readouterr().err


def test_file_stands_in_for_your_own(run, tmp_path):
    other = tmp_path / "other.ini"
    assert run("set", "--file", str(other), "input.escape_delay", "60")[0] == 0
    assert other.read_text() == "[input]\nescape_delay = 60\n"
    assert not run.user.exists()
    _, out, _ = run("list", "--changed", "--file", str(other))
    assert ["input.escape_delay", "60", "ms", "file"] in [
        line.split() for line in out.splitlines()
    ]


# -------------------------------------------------------------------- unset


def test_unset_removes_the_line_and_says_what_wins_now(run):
    run.write(run.system, "[input]\nescape_delay = 50\n")
    run.write(run.user, "; keep me\n[input]\nescape_delay = 40\n")
    status, out, err = run("unset", "input.escape_delay")
    assert status == 0
    assert out == "input.escape_delay removed from ~/.config/tkcurses/tkcurses.ini\n"
    assert f"now 50 ms, from system ({run.system})" in err
    assert run.user.read_text() == "; keep me\n[input]\n"


def test_unset_what_the_file_does_not_set_changes_nothing(run):
    _, out, _ = run("unset", "input.escape_delay")
    assert (
        out
        == "~/.config/tkcurses/tkcurses.ini does not set input.escape_delay; nothing changed\n"
    )


def test_unset_cleans_out_a_removed_setting(run):
    run.write(run.user, "[debug]\nenabled = 1\n")
    status, _, err = run("unset", "debug.enabled")
    assert (status, err) == (0, "")
    assert run.user.read_text() == "[debug]\n"


def test_unset_an_unknown_name_not_in_the_file_is_status_3(run):
    assert run("unset", "mouse.nope")[0] == 3


# -------------------------------------------------------------------- check


def test_check_with_no_files_is_clean(run):
    status, out, _ = run("check")
    assert status == 0
    assert (
        out
        == "0 errors, 0 warnings (no configuration files exist; and this shell's environment)\n"
    )


def test_check_reports_every_problem_with_its_line(run):
    run.write(
        run.user,
        "[mouse]\nclick_interval = 5000\nclik = 1\n[debug]\nenabled = 1\n[colours]\n",
    )
    status, out, _ = run("check")
    assert status == 4
    lines = out.splitlines()
    assert lines[0].startswith(f"error: {run.user}, line 2: mouse.click_interval: ")
    assert lines[1].startswith(f"warning: {run.user}, line 3: mouse.clik: ")
    assert lines[2].startswith(f"warning: {run.user}, line 5: debug.enabled: ")
    assert lines[3].startswith(f"warning: {run.user}, line 6: colours: ")
    assert lines[4].startswith("1 error, 3 warnings (")


def test_check_warnings_alone_are_status_0(run):
    run.write(run.user, "[mouse]\nclik = 1\n")
    assert run("check")[0] == 0


def test_check_a_syntax_error_is_status_5(run):
    run.write(run.system, "[mouse]\nenabled = 1\n  continued\n")
    status, out, _ = run("check")
    assert status == 5
    assert f"error: {run.system}, line 3: is indented further" in out


def test_check_reads_the_environment_too(run):
    run.monkeypatch.setenv("TKCURSES_DISPLAY_COLOR_MODE", "24bit")
    run.monkeypatch.setenv(REMOVED[0].variable, "1")
    status, out, _ = run("check")
    assert status == 4
    assert "error: $TKCURSES_DISPLAY_COLOR_MODE: '24bit' is not one of" in out
    assert f"warning: ${REMOVED[0].variable} no longer has any effect" in out


@pytest.mark.skipif(IS_ROOT, reason="root reads anything")
def test_check_a_file_that_cannot_be_read_is_status_6(run):
    run.write(run.user, "[mouse]\n")
    run.user.chmod(0)
    try:
        status, out, _ = run("check")
    finally:
        run.user.chmod(0o644)
    assert status == 6 and "cannot be read: Permission denied" in out


# --------------------------------------------------------------- path, init


def test_path_prints_the_file_an_edit_would_go_to(run, tmp_path):
    assert run("path")[1] == f"{run.user}\n"
    assert run("path", "--global")[1] == f"{run.system}\n"
    assert run("path", "--file", "~/x.ini")[1] == f"{run.home / 'x.ini'}\n"


def test_init_writes_the_starter_file(run):
    status, out, _ = run("init")
    assert status == 0
    assert out.startswith("wrote ~/.config/tkcurses/tkcurses.ini")
    text = run.user.read_text()
    assert ";escape_delay = 25" in text
    assert run("check")[0] == 0
    assert run("list", "--changed")[1] == "Every setting is at its default.\n"


def test_init_will_not_replace_a_file_without_force(run):
    run.write(run.user, "[mouse]\nenabled = 0\n")
    status, _, err = run("init")
    assert status == 9 and "--force" in err
    assert run.user.read_text() == "[mouse]\nenabled = 0\n"


def test_init_force_replaces_even_a_broken_file_and_keeps_it(run):
    run.write(run.user, "[mouse]\n[mouse]\n")
    status, _, err = run("init", "--force")
    assert status == 0
    assert "kept as ~/.config/tkcurses/tkcurses.ini.bak" in err
    assert run.user.with_name("tkcurses.ini.bak").read_text() == "[mouse]\n[mouse]\n"


# ------------------------------------------------------------ the rest


def test_no_command_prints_help_and_is_a_usage_error(run):
    status, out, err = run()
    assert (status, out) == (2, "")
    assert "usage: tkcurses-cfg" in err


def test_help_lists_every_exit_status(run):
    with pytest.raises(SystemExit):
        run("--help")
    out = run.capsys.readouterr().out
    for status in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "130"):
        assert f"\n  {status} " in out


def test_an_unexpected_error_is_status_1_and_asks_for_debug(run, monkeypatch):
    def boom(args):
        raise RuntimeError("bad")

    monkeypatch.setattr(cli, "cmd_path", boom)
    status, _, err = run("path")
    assert status == 1 and "Rerun with --debug" in err
    status, _, err = run("path", "--debug")
    assert status == 1 and "Traceback" in err and "RuntimeError: bad" in err


def test_the_command_is_installed_as_tkcurses_cfg():
    """Read as text: tomllib is not in Python 3.10."""
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    scripts = text.split("[project.scripts]\n")[1].split("\n\n")[0]
    assert 'tkcurses-cfg = "tkcurses._cfg.cli:main"' in scripts.splitlines()


def test_it_runs_as_a_program(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("TKCURSES_")} | {
        "PYTHONPATH": str(SRC),
        "XDG_CONFIG_HOME": str(tmp_path),
    }
    script = "import sys; from tkcurses._cfg.cli import main; sys.exit(main())"
    done = subprocess.run(
        [sys.executable, "-c", script, "set", "mouse.enabled", "maybe"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 4
    assert "'maybe' is not a boolean" in done.stderr
