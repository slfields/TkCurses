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

"""The file browser's arithmetic, which needs no terminal.

Reading the filter box, writing it back, and turning a directory into two
lists is all path handling, and it is where a file dialog is wrong in ways
nobody notices until they cannot get out of a directory.
"""

from __future__ import annotations

import os

import pytest

from tkcurses import Misc
from tkcurses.filedialog import (
    _Browser,
    _first_pattern,
    _with_extension,
    dialogstates,
)


@pytest.fixture
def tree(tmp_path):
    """A directory with two matching files, one that does not, and a subdir."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    (tmp_path / "gamma.log").write_text("g")
    return tmp_path


@pytest.fixture
def browser():
    return _Browser(Misc())


# ------------------------------------------------------------- the filter


def test_the_filter_splits_into_a_directory_and_a_pattern(browser, tree):
    browser.set_filter(str(tree), "*.txt")
    assert browser.get_filter() == (str(tree), "*.txt")


def test_a_directory_with_no_pattern_gets_a_star(browser, tree):
    """Typing a directory into the filter box means everything in it."""
    browser.filter.delete(0, "end")
    browser.filter.insert("end", str(tree))
    assert browser.get_filter() == (str(tree), "*")


def test_a_trailing_separator_also_means_everything(browser, tree):
    browser.filter.delete(0, "end")
    browser.filter.insert("end", str(tree) + os.sep)
    assert browser.get_filter() == (str(tree), "*")


def test_a_relative_directory_is_made_absolute(browser):
    """So that what the box says is where the listing came from."""
    browser.set_filter(os.curdir, "*")
    directory, _ = browser.get_filter()
    assert os.path.isabs(directory)


def test_an_empty_directory_and_pattern_fall_back(browser, monkeypatch):
    monkeypatch.chdir(os.sep)
    browser.set_filter("", "")
    assert browser.get_filter()[1] == "*"


# ---------------------------------------------------------------- listing


def test_the_directory_list_starts_with_the_way_up(browser, tree):
    """Always, so a directory whose name cannot be typed is not a trap."""
    browser.set_filter(str(tree), "*")
    assert browser.refresh() is True
    assert browser.dirs.get(0) == os.pardir


def test_subdirectories_are_listed_after_it(browser, tree):
    browser.set_filter(str(tree), "*")
    browser.refresh()
    assert list(browser.dirs.get(0, "end")) == [os.pardir, "subdir"]


def test_only_the_files_matching_the_pattern_are_listed(browser, tree):
    browser.set_filter(str(tree), "*.txt")
    browser.refresh()
    assert list(browser.files.get(0, "end")) == ["alpha.txt", "beta.txt"]


def test_a_wider_pattern_lists_more(browser, tree):
    browser.set_filter(str(tree), "*")
    browser.refresh()
    assert list(browser.files.get(0, "end")) == [
        "alpha.txt",
        "beta.txt",
        "gamma.log",
    ]


def test_directories_are_never_filtered_out_by_the_pattern(browser, tree):
    """The pattern is about files; a directory is how you get anywhere."""
    browser.set_filter(str(tree), "*.txt")
    browser.refresh()
    assert "subdir" in list(browser.dirs.get(0, "end"))


def test_a_directory_that_cannot_be_read_changes_nothing(browser, tree):
    """Rather than emptying the lists and losing the place somebody had."""
    browser.set_filter(str(tree), "*")
    browser.refresh()
    before = list(browser.dirs.get(0, "end")), list(browser.files.get(0, "end"))

    browser.set_filter(str(tree / "nowhere"), "*")
    assert browser.refresh() is False
    assert (
        list(browser.dirs.get(0, "end")),
        list(browser.files.get(0, "end")),
    ) == before


# -------------------------------------------------------------- selection


def test_the_selection_is_a_name_under_the_current_directory(browser, tree):
    browser.set_filter(str(tree), "*")
    browser.refresh()
    browser.set_selection("alpha.txt")
    assert browser.get_selection() == str(tree / "alpha.txt")


def test_refreshing_keeps_the_chosen_name(browser, tree):
    """Changing the pattern must not throw away what was already chosen."""
    browser.set_filter(str(tree), "*")
    browser.refresh()
    browser.set_selection("alpha.txt")
    browser.set_filter(str(tree), "*.txt")
    browser.refresh()
    assert browser.get_selection().endswith("alpha.txt")


def test_entering_a_subdirectory_moves_the_filter(browser, tree):
    browser.set_filter(str(tree), "*.txt")
    browser.refresh()
    browser.enter_directory("subdir")
    directory, pattern = browser.get_filter()
    assert directory == str(tree / "subdir")
    assert pattern == "*.txt", "the pattern should survive the move"


def test_the_way_up_goes_up(browser, tree):
    browser.set_filter(str(tree), "*")
    browser.refresh()
    browser.enter_directory(os.pardir)
    assert browser.get_filter()[0] == str(tree.parent)


# ---------------------------------------------------------------- options


@pytest.mark.parametrize(
    ("filetypes", "pattern"),
    [
        (None, "*"),
        ((), "*"),
        ((("Text", "*.txt"),), "*.txt"),
        ([["Logs", "*.log"], ["All", "*"]], "*.log"),
        (("badly formed",), "*"),
    ],
)
def test_the_first_filetype_sets_the_starting_pattern(filetypes, pattern):
    assert _first_pattern(filetypes) == pattern


@pytest.mark.parametrize(
    ("path", "extension", "expected"),
    [
        ("/tmp/notes", ".txt", "/tmp/notes.txt"),
        # One it already has is left alone, even a different one.
        ("/tmp/notes.log", ".txt", "/tmp/notes.log"),
        ("/tmp/notes", None, "/tmp/notes"),
        ("/tmp/notes", "", "/tmp/notes"),
    ],
)
def test_the_default_extension_is_added_only_when_there_is_none(
    path, extension, expected
):
    assert _with_extension(path, extension) == expected


def test_the_remembered_states_are_shared_across_dialogs():
    """tkinter keeps them in a module-level dictionary, and so does this."""
    assert isinstance(dialogstates, dict)
