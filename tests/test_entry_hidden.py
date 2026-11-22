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

"""A hidden entry - ``show`` set - keeps its contents out of Python strings."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from tkcurses import Entry, Misc, StringVar, ttk
from tkcurses._core import wipeable
from tkcurses._core.events import MOD_CTRL, MOD_SHIFT, KeyEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack
from tkcurses._core.wipeable import SecretBuffer

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def root():
    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def placed(widget):
    widget._allocate(Rect(0, 0, 22, 3))
    widget._map()
    widget.focus_set()
    return widget


def press(widget, keysym, state=0, char=""):
    widget._handle(KeyEvent(keysym=keysym, char=char, modifiers=state))


def type_text(widget, text):
    for char in text:
        press(widget, char, char=char)


@pytest.fixture
def no_strings(monkeypatch):
    """Fail the test if a hidden field's contents become a str."""

    def refuse(self):
        raise AssertionError("a hidden field's contents were made into a str")

    monkeypatch.setattr(SecretBuffer, "to_str", refuse)


MAKERS = {
    "Entry": lambda root, **kw: Entry(root, **kw),
    "ttk.Entry": lambda root, **kw: ttk.Entry(root, **kw),
    "ttk.Combobox": lambda root, **kw: ttk.Combobox(root, **kw),
}


@pytest.mark.parametrize("make", MAKERS.values(), ids=MAKERS.keys())
def test_typing_and_editing_make_no_string(root, no_strings, make):
    widget = placed(make(root, name="pw", show="*"))
    type_text(widget, "correct horse")
    press(widget, "BackSpace")
    press(widget, "Home")
    press(widget, "Delete")
    press(widget, "Right", MOD_CTRL)
    press(widget, "Left", MOD_CTRL)
    press(widget, "End", MOD_SHIFT)
    press(widget, "Insert", MOD_CTRL)  # <<Copy>>: the mask, not the text
    press(widget, "End")
    widget.insert("end", "!")
    widget.delete(0)
    widget._redraw()
    assert widget._field.length == len("rrect hors!")


def test_the_contents_are_held_in_wipeable_memory(root):
    widget = placed(Entry(root, name="pw", show="*"))
    type_text(widget, "hunter2")
    assert widget._field.hidden
    assert widget.get() == "hunter2"


def test_secret_gives_the_utf8_and_wipes_it(root):
    widget = placed(Entry(root, name="pw", show="•"))
    type_text(widget, "pässwörd")
    with widget.secret() as view:
        assert bytes(view) == "pässwörd".encode()
        digest = hashlib.sha256(view).digest()
    assert digest == hashlib.sha256("pässwörd".encode()).digest()
    with pytest.raises(ValueError):
        bytes(view)


def test_secret_works_on_a_plain_entry_too(root):
    widget = placed(Entry(root, name="plain"))
    widget.insert(0, "visible")
    with widget.secret() as view:
        assert bytes(view) == b"visible"


def test_turning_show_off_and_on_keeps_the_contents(root):
    widget = placed(Entry(root, name="pw", show="*"))
    type_text(widget, "abc")
    widget.configure(show="")
    assert not widget._field.hidden
    assert widget.get() == "abc"
    widget.configure(show="*")
    assert widget._field.hidden
    assert widget.get() == "abc"


def test_destroying_a_hidden_entry_wipes_it(root, monkeypatch):
    closed = []
    original = SecretBuffer.close

    def spying(self):
        closed.append(self._codes is not None)
        original(self)

    monkeypatch.setattr(SecretBuffer, "close", spying)
    widget = placed(Entry(root, name="pw", show="*"))
    type_text(widget, "hunter2")
    widget.destroy()
    assert True in closed
    assert not widget._field.hidden
    assert widget._field.length == 0


def test_get_a_variable_and_a_validator_still_see_the_text(root):
    """The tkinter API hands out str; that stays, and is documented."""
    seen = []
    variable = StringVar(root)
    widget = placed(
        Entry(
            root,
            name="pw",
            show="*",
            textvariable=variable,
            validate="key",
            validatecommand=lambda proposed: seen.append(proposed) or True,
        )
    )
    type_text(widget, "ab")
    assert widget.get() == "ab"
    assert variable.get() == "ab"
    assert seen[-2:] == ["a", "ab"]  # after the variable's own, forced


def test_without_a_validator_no_proposed_text_is_built(root, no_strings):
    """validate="key" with no command asks nobody, so builds nothing."""
    widget = placed(Entry(root, name="pw", show="*", validate="key"))
    type_text(widget, "abc")
    assert widget._field.length == 3


def test_a_wide_mask_draws_two_cells_a_character(root):
    widget = placed(Entry(root, name="pw", show="界"))
    type_text(widget, "abc")
    assert widget._field.cell_of(3) == 6


# ------------------------------------------------------------- in memory

PROBE = textwrap.dedent(
    """
    import gc, re, sys
    from types import SimpleNamespace
    from tkcurses import Entry, Misc
    from tkcurses._core import wipeable
    from tkcurses._core.events import KeyEvent
    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    if sys.argv[2] == "mmap":
        wipeable._chosen = wipeable.MmapAllocator()
    # Never a literal, so only the widget can assemble it.
    codes = [ord(c) + 1 for c in 'Yp6"oV8wJm']

    narrow = bytes(codes)  # how a str of these characters holds them
    wide = b"".join(c.to_bytes(4, "little") for c in codes)  # the buffer's way

    def count(needle):
        found = 0
        with open("/proc/self/maps") as maps, open("/proc/self/mem", "rb", 0) as mem:
            for line in maps:
                m = re.match(r"([0-9a-f]+)-([0-9a-f]+) r", line)
                if not m or "[v" in line:
                    continue
                low, high = int(m[1], 16), int(m[2], 16)
                try:
                    mem.seek(low)
                    data = mem.read(high - low)
                except (OSError, ValueError, OverflowError):
                    continue
                found += data.count(needle)
        return found

    root = Misc()
    root.tk.panels = PanelStack(window_factory=lambda r: SimpleNamespace(rect=r), panel_factory=None)
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    entry = Entry(root, name="pw", show="*")
    entry._allocate(Rect(0, 0, 22, 3))
    entry._map()
    entry.focus_set()
    if sys.argv[1] == "typed":
        for code in codes:
            entry._handle(KeyEvent(keysym=chr(code), char=chr(code), modifiers=0))
        with entry.secret() as view:
            bytes(view[:0])
    held = count(narrow)
    entry.delete(0, "end")
    entry.destroy()
    del entry
    gc.collect()
    print(held, count(narrow), count(wide))
    """
)


@pytest.mark.skipif(not Path("/proc/self/mem").exists(), reason="needs /proc/self/mem")
@pytest.mark.parametrize("allocator", ["default", "mmap"])
def test_a_typed_password_is_gone_from_memory_once_the_entry_is(tmp_path, allocator):
    """Counted against a run that types nothing, whose only copies are the
    probe's own search strings.

    While the entry holds the password, no ``str`` of it exists: before
    hidden fields kept their contents out of one, this found one more copy
    than the control did, every run. Afterwards, the field's own memory
    holds nothing either. Freed strings are not counted after the entry
    is gone, because whether one survives depends on what the allocator
    happens to reuse.
    """
    script = tmp_path / "probe.py"
    script.write_text(PROBE)

    def run(mode):
        done = subprocess.run(
            [sys.executable, str(script), mode, allocator],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONPATH": str(SRC), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return done.stdout.split()

    assert run("typed") == run("control")


def test_the_exit_notice_names_why_memory_was_not_locked(monkeypatch, capsys):
    import tkcurses

    monkeypatch.setattr(wipeable, "_lock_failure", "Cannot allocate memory")
    written = []
    monkeypatch.setattr(tkcurses, "_write_to_stderr", written.append)
    tkcurses._report_secret_unlocked()
    tkcurses._report_secret_unlocked()  # said once
    assert len(written) == 1
    assert "could not be locked" in written[0]
    assert "Cannot allocate memory" in written[0]
    assert "still wiped" in written[0]
