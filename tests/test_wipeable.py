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

"""Tests for tkcurses._core.wipeable: wipeable memory for hidden fields."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._core import wipeable
from tkcurses._core.editing import TextField
from tkcurses._core.wipeable import MmapAllocator, SecretBuffer, SodiumAllocator

PAGE_CHARS = wipeable._PAGE // wipeable.CHAR_BYTES


class SpyRegion:
    """A real mmap region that records what it held when it was freed."""

    def __init__(self, spy: SpyAllocator, size: int) -> None:
        self._inner = wipeable._MmapRegion(size)
        self.address = self._inner.address
        self.size = self._inner.size
        self.locked = self._inner.locked
        self.lock_error = self._inner.lock_error
        self.view = self._inner.view
        self._spy = spy

    def wipe(self) -> None:
        self._inner.wipe()

    def free(self) -> None:
        if self._inner._map is not None:
            self._inner.wipe()
            self._spy.freed.append(bytes(self.view))  # what free() leaves
        self._inner.free()


class SpyAllocator:
    name = "spy"

    def __init__(self) -> None:
        self.freed: list[bytes] = []
        self.allocated = 0

    def allocate(self, size: int) -> SpyRegion:
        self.allocated += 1
        return SpyRegion(self, size)


@pytest.fixture
def spy(monkeypatch):
    allocator = SpyAllocator()
    monkeypatch.setattr(wipeable, "_chosen", allocator)
    return allocator


@pytest.fixture(params=["mmap", "sodium"])
def each_allocator(request, monkeypatch):
    if request.param == "mmap":
        chosen = MmapAllocator()
    else:
        chosen = SodiumAllocator.load()
        if chosen is None:
            pytest.skip("libsodium is not installed")
    monkeypatch.setattr(wipeable, "_chosen", chosen)
    return chosen


def wiped(data: bytes) -> bool:
    return not any(data)


# ------------------------------------------------------------- contents


def test_it_holds_what_it_was_given(each_allocator):
    buffer = SecretBuffer("pässwörd")
    assert len(buffer) == 8
    assert buffer.to_str() == "pässwörd"
    assert buffer[1] == "ä"
    assert buffer[-1] == "d"
    buffer.close()


def test_an_index_past_the_end_is_an_index_error(each_allocator):
    buffer = SecretBuffer("ab")
    with pytest.raises(IndexError):
        buffer[2]
    buffer.close()


@given(
    st.lists(
        st.one_of(
            st.tuples(st.just("insert"), st.integers(0, 40), st.text(max_size=8)),
            st.tuples(st.just("delete"), st.integers(0, 40), st.integers(0, 40)),
        ),
        max_size=30,
    )
)
def test_edits_match_the_same_edits_on_a_str(operations):
    buffer = SecretBuffer()
    model = ""
    for kind, a, b in operations:
        if kind == "insert":
            at = min(a, len(model))
            buffer.insert(at, b)
            model = model[:at] + b + model[at:]
        else:
            first, last = sorted((min(a, len(model)), min(b, len(model))))
            buffer.delete(first, last)
            model = model[:first] + model[last:]
        assert len(buffer) == len(model)
    assert buffer.to_str() == model
    buffer.close()


def test_it_grows_past_a_page(each_allocator):
    buffer = SecretBuffer("ab")
    buffer.insert(1, "x" * (3 * PAGE_CHARS))
    assert len(buffer) == 3 * PAGE_CHARS + 2
    assert buffer[0] == "a"
    assert buffer[-1] == "b"
    buffer.close()


# ---------------------------------------------------------------- UTF-8


@pytest.mark.parametrize("text", ["", "abc", "ñandú", "日本語", "🙂 ok", "á"])
def test_utf8_is_what_encode_gives(each_allocator, text):
    buffer = SecretBuffer(text)
    with buffer.utf8() as view:
        assert bytes(view) == text.encode("utf-8")
        assert view.readonly
    buffer.close()


def test_a_utf8_view_cannot_be_used_after_the_block(spy):
    buffer = SecretBuffer("secret")
    with buffer.utf8() as view:
        pass
    with pytest.raises(ValueError):
        bytes(view)
    buffer.close()


def test_a_lone_surrogate_is_refused_rather_than_mis_encoded(spy):
    buffer = SecretBuffer("a\ud800")
    with pytest.raises(ValueError), buffer.utf8():
        pass
    buffer.close()


# ---------------------------------------------------------------- wiping


def test_utf8_memory_is_wiped_when_the_block_ends(spy):
    buffer = SecretBuffer("secret")
    with buffer.utf8():
        pass
    assert len(spy.freed) == 1
    assert wiped(spy.freed[0])
    buffer.close()


def test_utf8_memory_is_wiped_when_the_block_raises(spy):
    buffer = SecretBuffer("secret")
    with pytest.raises(RuntimeError), buffer.utf8():
        raise RuntimeError
    assert wiped(spy.freed[0])
    buffer.close()


def test_growing_wipes_the_memory_it_leaves(spy):
    buffer = SecretBuffer("secret")
    buffer.insert(0, "x" * PAGE_CHARS)
    assert len(spy.freed) == 1
    assert wiped(spy.freed[0])
    buffer.close()


def test_closing_wipes_the_memory(spy):
    buffer = SecretBuffer("secret")
    buffer.close()
    buffer.close()  # harmless twice
    assert len(spy.freed) == 1
    assert wiped(spy.freed[0])


def test_a_deleted_tail_leaves_zeros_behind(spy):
    buffer = SecretBuffer("abcdef")
    buffer.delete(1, 3)
    raw = bytes(buffer._region.view[: 6 * wipeable.CHAR_BYTES])
    assert buffer.to_str() == "adef"
    assert raw[4 * wipeable.CHAR_BYTES :] == bytes(2 * wipeable.CHAR_BYTES)
    buffer.close()


def test_clear_zeroes_everything(spy):
    buffer = SecretBuffer("secret")
    buffer.clear()
    assert len(buffer) == 0
    assert wiped(bytes(buffer._region.view))
    buffer.close()


def test_a_closed_buffer_refuses_to_be_read(spy):
    buffer = SecretBuffer("secret")
    buffer.close()
    with pytest.raises(ValueError):
        buffer.to_str()


# ---------------------------------------------------------------- locking


def test_the_memory_is_locked_where_the_system_allows(each_allocator):
    buffer = SecretBuffer("x")
    region = buffer._region
    assert region.locked or region.lock_error
    buffer.close()


def test_a_lock_that_fails_is_remembered_once(monkeypatch):
    class Unlockable(MmapAllocator):
        def allocate(self, size):
            region = super().allocate(size)
            region.locked, region.lock_error = False, "Cannot allocate memory"
            return region

    monkeypatch.setattr(wipeable, "_chosen", Unlockable())
    monkeypatch.setattr(wipeable, "_lock_failure", "")
    buffer = SecretBuffer("still works")
    assert buffer.to_str() == "still works"
    assert wipeable.lock_failure() == "Cannot allocate memory"
    wipeable.forget_lock_failure()
    assert wipeable.lock_failure() == ""
    buffer.close()


def test_an_allocator_is_chosen_once(monkeypatch):
    monkeypatch.setattr(wipeable, "_chosen", None)
    first = wipeable.allocator()
    assert wipeable.allocator() is first
    assert first.name in ("libsodium", "mmap with mlock")


# ----------------------------------------------------- a hidden TextField


@given(
    st.lists(
        st.one_of(
            st.tuples(
                st.just("insert"), st.integers(0, 30), st.text("ab c", max_size=6)
            ),
            st.tuples(st.just("delete"), st.integers(0, 30), st.integers(0, 30)),
            st.tuples(st.just("move"), st.integers(0, 30), st.booleans()),
            st.tuples(st.just("view"), st.integers(0, 30), st.integers(1, 12)),
        ),
        max_size=25,
    )
)
def test_a_hidden_field_edits_as_a_plain_one_does(operations):
    """Every character here is one cell wide, so a mask measures the same."""
    plain, hidden = TextField(), TextField()
    hidden.hide()
    for kind, a, b in operations:
        for field in (plain, hidden):
            if kind == "insert":
                field.insert(a, b)
            elif kind == "delete":
                field.delete(a, b)
            elif kind == "move":
                field.move_to(a, extend=b)
            else:
                field.set_view(a, b)
                field.scroll_into_view(b)
        assert hidden.text == plain.text
        assert (hidden.cursor, hidden.selection, hidden.view) == (
            plain.cursor,
            plain.selection,
            plain.view,
        )
        assert hidden.column_of(a) == plain.column_of(a)
        assert hidden.index_at(a) == plain.index_at(a)
    hidden.close()


def test_hiding_and_revealing_keep_the_contents(spy):
    field = TextField("hunter2")
    field.hide()
    assert field.hidden
    assert field.text == "hunter2"
    field.reveal()
    assert not field.hidden
    assert field.text == "hunter2"
    assert wiped(spy.freed[-1])


def test_a_hidden_field_measures_by_its_mask(spy):
    field = TextField()
    field.hide(cells_each=2)
    field.insert(0, "abc")
    assert field.cell_of(3) == 6
    field.close()


def test_closing_a_hidden_field_empties_it(spy):
    field = TextField()
    field.hide()
    field.insert(0, "hunter2")
    field.close()
    assert field.text == ""
    assert not field.hidden
    assert wiped(spy.freed[-1])
