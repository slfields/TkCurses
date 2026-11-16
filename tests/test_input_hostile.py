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

"""Input from outside the program - the environment, the configuration
files, a person typing - that once stopped a program or drove its
terminal. Each test fails without its fix (security review TkCurses-tcbj).
"""

from __future__ import annotations

import io
import pathlib
import sys
from types import SimpleNamespace

import pytest

import tkcurses
from tkcurses import Misc
from tkcurses._cfg import cli
from tkcurses._core.config import TkCursesConfig, config_paths
from tkcurses.colorchooser import Chooser

HUGE = "9" * 5000


# ------------------------------------------- a number too long to convert


@pytest.mark.parametrize("raw", [HUGE, "-" + HUGE])
def test_a_number_too_long_to_convert_is_a_bad_value_not_a_crash(raw):
    config = TkCursesConfig.load(paths=(), env={"TKCURSES_MOUSE_CLICK_INTERVAL": raw})
    assert config.mouse.click_interval == TkCursesConfig().mouse.click_interval
    assert any(
        "5000 digits" in warning or "5001 digits" in warning
        for warning in config.warnings
    )


def test_the_same_number_in_a_file_is_a_bad_value_too(tmp_path):
    ini = tmp_path / "tkcurses.ini"
    ini.write_text(f"[mouse]\nclick_interval = {HUGE}\n")
    config = TkCursesConfig.load(paths=(ini,), env={})
    assert config.mouse.click_interval == TkCursesConfig().mouse.click_interval


def test_tkcurses_cfg_checks_such_a_file_without_crashing(tmp_path, capsys):
    ini = tmp_path / "tkcurses.ini"
    ini.write_text(f"[mouse]\nclick_interval = {HUGE}\n")
    assert cli.main(["check", "--file", str(ini)]) == 4
    assert "5000 digits" in capsys.readouterr().out


# ------------------------------------------------------ no home directory


@pytest.fixture
def homeless(monkeypatch):
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    def nowhere(cls=None):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(pathlib.Path, "home", classmethod(nowhere))


def test_with_no_home_directory_the_rest_of_the_configuration_is_read(homeless):
    with pytest.raises(RuntimeError):
        config_paths()
    config = TkCursesConfig.load(env={"TKCURSES_MOUSE_ENABLED": "0"})
    assert config.mouse.enabled is False
    assert "no home directory" in " ".join(config.warnings)


def test_tkcurses_cfg_with_no_home_directory_says_what_to_do(homeless, capsys):
    assert cli.main(["list"]) == 1
    assert (
        "set HOME or XDG_CONFIG_HOME, or name a file with --file"
        in capsys.readouterr().err
    )


# -------------------------------------------------------- colour chooser


@pytest.mark.parametrize("typed", ["inf", "-inf", "1e999", "nan"])
def test_a_channel_given_infinity_becomes_zero_as_tk_does(typed, monkeypatch):
    picker = Chooser(Misc())
    picker._fixoptions()
    picker._entries = {"Red": SimpleNamespace(get=lambda: typed)}
    seen = []
    monkeypatch.setattr(
        picker, "set_channel", lambda channel, value: seen.append(value)
    )
    picker._on_channel("Red")(None)
    assert seen == [0]


# ------------------------------------------------------ reports at exit


def test_a_report_on_the_way_out_cannot_drive_the_terminal(monkeypatch):
    """A locale name or a path under XDG_CONFIG_HOME is quoted in what is
    printed when the screen is given back; an escape sequence in either
    used to reach the terminal raw."""
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured)
    report = tkcurses._not_utf8_report({"LC_ALL": "xx\x1b]0;PWNED\x07\x1b[2J"})
    tkcurses._write_to_stderr(report)
    written = captured.getvalue()
    assert "\x1b" not in written and "\x07" not in written
    assert "LC_ALL=xx\\x1b]0;PWNED\\x07\\x1b[2J" in written
    assert written.endswith("\n")
