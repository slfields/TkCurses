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

"""The file dialogs against a real terminal, on a real directory."""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.tty

#: The answer is reported by its last component, not in full. pytest's
#: tmp_path is long enough that a whole path runs off a terminal this size,
#: and an assertion that cannot see the part it cares about is no assertion.
PROGRAM = """
import os
import tkcurses
from tkcurses import filedialog

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
buffer.write(0, 0, "ready")
root.tk.screen.refresh()

WORK = {work!r}


def ask(event):
    answer = {call}
    if answer is None:
        shown = "None"
    elif answer == "":
        shown = "empty"
    else:
        shown = os.path.basename(answer.rstrip(os.sep)) or answer
    buffer.write(1, 0, "chosen=%s{pad}" % (shown,))
    root.tk.screen.refresh()


root.bind("<Key-a>", ask)
root.after(10000, root.quit)
root.mainloop()
"""


@pytest.fixture
def tree(tmp_path):
    """Two matching files, one that does not match, and a subdirectory."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    (tmp_path / "gamma.log").write_text("g")
    return tmp_path


def browse(term, tmp_path, tree, call):
    term.run_source(
        PROGRAM.format(work=str(tree), call=call, pad=" " * 20),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("alpha.txt")


def click_text(term, text, offset=0):
    """Click on ``text``, once it is actually on the screen.

    It used to assume it already was, and next() with no default raised
    StopIteration - a bare "E StopIteration" with no clue which text was
    missing. The dialog's listing arrives before its buttons do, so a test
    that waited for a filename and then clicked Cancel was racing the
    button's first paint. Seen on CI, on one Python version out of five.

    **It matches the text standing alone**, not inside a longer word or a
    path. The dialog's own entries hold paths, and pytest names the temporary
    directory after the test: on CI ``test_a_subdirectory_can_be_opened``
    runs in ``.../test_a_subdirectory_can_be_ope0/``, so a plain search for
    ``subdir`` clicked the filter entry instead of the listing. It used to
    be hidden because the entry showed the END of its path; since
    TkCurses-i8s it shows the start, as Tk's does.
    """
    pattern = re.compile(rf"(?<![\w./-]){re.escape(text)}(?![\w./-])")

    def found(t):
        return next(
            (
                (match.start(), row)
                for row, line in enumerate(t.display)
                for match in [pattern.search(line)]
                if match
            ),
            None,
        )

    term.wait_for(lambda t: found(t) is not None, message=repr(text))
    column, row = found(term)
    term.click(column + offset, row)


PLAIN = 'filedialog.FileDialog(root).go(WORK, "*.txt")'


# ------------------------------------------------------------ the listing


def test_the_browser_shows_the_directories_and_the_matching_files(
    terminal, tmp_path, tree
):
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, PLAIN)
    screen = "\n".join(term.display)
    assert "subdir" in screen
    assert "beta.txt" in screen
    assert "gamma.log" not in screen, "the pattern should have excluded it"
    assert ".." in screen, "there must always be a way up"
    term.send_keys("<Escape>")


def test_clicking_a_file_puts_it_in_the_selection(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, PLAIN)
    click_text(term, "beta.txt")
    term.wait_for(
        lambda t: t.contains("beta.txt"), message="the name in the selection box"
    )
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=beta.txt")


def test_cancelling_gives_nothing(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, PLAIN)
    click_text(term, "Cancel", 1)
    term.wait_for_text("chosen=None")


def test_escape_cancels_too(terminal, tmp_path, tree):
    """A terminal has no window manager close button for the protocol
    handler to answer, so the key stands in for it."""
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, PLAIN)
    term.send_keys("<Escape>")
    term.wait_for_text("chosen=None")


def test_a_subdirectory_can_be_opened(terminal, tmp_path, tree):
    """Click to move the filter there, Filter to list it."""
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, PLAIN)
    click_text(term, "subdir")
    click_text(term, "Filter", 1)
    term.wait_for(
        lambda t: not t.contains("alpha.txt"),
        message="the subdirectory's own listing",
    )
    assert term.contains(".."), "and still a way back up"
    term.send_keys("<Escape>")


# ------------------------------------------------------------- the checks


def test_a_load_dialog_refuses_a_file_that_is_not_there(terminal, tmp_path, tree):
    """It is the only difference between it and the plain dialog, and the
    refusal has to be silent-but-firm rather than an answer."""
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        'filedialog.LoadFileDialog(root).go(WORK, "*.txt")',
    )
    term.send(b"nosuchfile")
    term.send(b"\r")
    term.wait_for_idle()
    assert not term.contains("chosen="), (
        f"a load dialog answered with a file that is not there:\n{term.describe()}"
    )
    term.send_keys("<Escape>")
    term.wait_for_text("chosen=None")


def test_a_load_dialog_accepts_one_that_is(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        'filedialog.LoadFileDialog(root).go(WORK, "*.txt")',
    )
    click_text(term, "alpha.txt")
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=alpha.txt")


def test_a_save_dialog_asks_before_overwriting(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        'filedialog.SaveFileDialog(root).go(WORK, "*.txt")',
    )
    click_text(term, "alpha.txt")
    click_text(term, "OK", 1)
    term.wait_for_text("Overwrite existing file")
    assert not term.contains("chosen="), "nothing is answered until it is allowed"
    # The question's default is Cancel, so Return declines and the browser
    # is still there.
    term.send(b"\r")
    term.wait_for(lambda t: t.contains("beta.txt"), message="the browser, still up")
    term.send_keys("<Escape>")
    term.wait_for_text("chosen=None")


def test_a_save_dialog_takes_a_new_name_without_asking(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        'filedialog.SaveFileDialog(root).go(WORK, "*.txt")',
    )
    term.send(b"delta.txt")
    term.send(b"\r")
    term.wait_for_text("chosen=delta.txt")


# ------------------------------------------------- the convenience wrappers


def test_askopenfilename_shows_the_browser_and_returns_a_path(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        "filedialog.askopenfilename(parent=root, initialdir=WORK)",
    )
    click_text(term, "alpha.txt")
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=alpha.txt")


def test_a_cancelled_askopenfilename_is_the_empty_string(terminal, tmp_path, tree):
    """tkinter's wrappers return "" rather than None, and code tests it for
    truth - so the difference matters even though both are falsy."""
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        "filedialog.askopenfilename(parent=root, initialdir=WORK)",
    )
    term.send_keys("<Escape>")
    term.wait_for_text("chosen=empty")


def test_askdirectory_answers_with_a_directory(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(
        term,
        tmp_path,
        tree,
        "filedialog.askdirectory(parent=root, initialdir=WORK)",
    )
    click_text(term, "subdir")
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=subdir")


def test_the_filetypes_option_sets_the_starting_pattern(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    term.run_source(
        PROGRAM.format(
            work=str(tree),
            call=(
                "filedialog.askopenfilename(parent=root, initialdir=WORK,"
                ' filetypes=[("Logs", "*.log")])'
            ),
            pad=" " * 20,
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send(b"a")
    term.wait_for_text("gamma.log")
    assert not term.contains("alpha.txt"), (
        f"the *.log pattern should have excluded it:\n{term.describe()}"
    )
    term.send_keys("<Escape>")


MANY = (
    '",".join(os.path.basename(path) for path in '
    "filedialog.askopenfilenames(parent=root, initialdir=WORK))"
)


def test_askopenfilenames_chooses_several_files(terminal, tmp_path, tree):
    """The list takes an extended selection, as tk_getOpenFile's does with
    -multiple: a click, then Shift-Down, chooses two, and OK gives both."""
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, MANY)
    click_text(term, "alpha.txt")
    term.send(b"\x1b[1;2B")
    term.wait_for(
        lambda t: t.contains('"alpha.txt" "beta.txt"'),
        message="both names in the selection box",
    )
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=alpha.txt,beta.txt")


def test_askopenfilenames_still_takes_one(terminal, tmp_path, tree):
    term = terminal(cols=70, rows=22)
    browse(term, tmp_path, tree, MANY)
    click_text(term, "beta.txt")
    click_text(term, "OK", 1)
    term.wait_for_text("chosen=beta.txt")
