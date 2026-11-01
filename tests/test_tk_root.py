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

"""The root's methods that need no terminal: loadtk and readprofile.

``Tk(useTk=False)`` builds a root without starting curses, so both can be
asked about here; what ``loadtk`` does to a real terminal is in
``test_tk_tty.py``.
"""

from __future__ import annotations

import pytest

import tkcurses


@pytest.fixture
def root():
    root = tkcurses.Tk(useTk=False)
    yield root
    root.destroy()


def test_use_tk_false_leaves_the_terminal_alone(root):
    assert root._started is False


def test_loadtk_on_a_destroyed_root_starts_nothing():
    root = tkcurses.Tk(useTk=False)
    root.destroy()
    root.loadtk()
    assert root._started is False


def test_readprofile_runs_the_class_profile_then_the_base_one(
    root, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".Tk.py").write_text("self.ran = ['Tk']\n")
    (tmp_path / ".demo.py").write_text("self.ran.append('demo')\n")
    root.readprofile("demo", "Tk")
    assert root.ran == ["Tk", "demo"]


def test_a_profile_sees_the_library_as_tkinters_sees_tkinter(
    root, tmp_path, monkeypatch
):
    """tkinter runs a profile after ``from tkinter import *``; ours, tkcurses."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".demo.py").write_text("self.found = Label, END\n")
    root.readprofile("demo", "Tk")
    assert root.found == (tkcurses.Label, "end")


def test_readprofile_skips_the_tcl_files_and_missing_ones(root, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".Tk.tcl").write_text("this is not python\n")
    root.readprofile("absent", "Tk")


def test_the_root_never_reads_a_profile_by_itself(tmp_path, monkeypatch):
    """tkinter's constructor would run this; ours does not - the author's call."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".Tk.py").write_text("raise SystemExit('profile ran')\n")
    tkcurses.Tk(useTk=False).destroy()
