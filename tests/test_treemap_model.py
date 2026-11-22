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

"""The treemap's items: Treeview's API, two levels, sizes and order."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.treemap._model import Model, checked_value


@pytest.fixture
def model():
    return Model()


def test_identifiers_are_generated_as_treeviews_are(model):
    assert model.insert("", "end") == "I001"
    assert model.insert("", "end", "mine") == "mine"
    assert model.insert("", "end") == "I002"


def test_a_generated_identifier_skips_one_in_use(model):
    model.insert("", "end", "I001")
    assert model.insert("", "end") == "I002"


def test_errors_use_treeviews_words(model):
    model.insert("", "end", "web")
    with pytest.raises(ValueError, match=r"^Item web already exists$"):
        model.insert("", "end", "web")
    with pytest.raises(ValueError, match=r"^Item nosuch not found$"):
        model.insert("nosuch", "end")
    with pytest.raises(ValueError, match=r"^Item nosuch not found$"):
        model.item("nosuch")


def test_a_third_level_is_refused(model):
    web = model.insert("", "end", text="web")
    nginx = model.insert(web, "end", text="nginx")
    with pytest.raises(
        ValueError, match=f"^a treemap has two levels: {nginx} is already a child$"
    ):
        model.insert(nginx, "end")


def test_a_group_cannot_be_moved_under_another_item(model):
    web = model.insert("", "end")
    model.insert(web, "end")
    db = model.insert("", "end")
    with pytest.raises(ValueError, match="two levels"):
        model.move(web, db, "end")
    with pytest.raises(ValueError, match="two levels"):
        model.move(db, model.get_children(web)[0], "end")


def test_an_item_cannot_go_under_itself(model):
    web = model.insert("", "end")
    with pytest.raises(ValueError, match=f"Cannot insert {web} as descendant"):
        model.move(web, web, 0)


def test_move_reparents_and_places(model):
    web = model.insert("", "end")
    db = model.insert("", "end")
    cache = model.insert("", "end")
    model.move(cache, web, 0)
    assert model.parent(cache) == web
    assert model.get_children() == (web, db)
    model.move(cache, "", 0)
    assert model.get_children() == (cache, web, db)
    assert model.index(cache) == 0


@pytest.mark.parametrize("value", [-1, "-0.5", math.nan, math.inf, "x", None, True])
def test_a_value_must_be_a_finite_number_not_negative(value):
    with pytest.raises(ValueError):
        checked_value(value)


def test_zero_and_strings_of_numbers_are_values():
    assert checked_value(0) == 0
    assert checked_value("2.5") == 2.5


def test_a_group_is_the_sum_of_its_children(model):
    web = model.insert("", "end", value=999)
    model.insert(web, "end", value=330)
    model.insert(web, "end", value=170)
    assert model.size(web) == 500
    assert model.item(web).value == 999


def test_deleting_the_last_child_brings_a_groups_own_value_back(model):
    web = model.insert("", "end", value=999)
    nginx = model.insert(web, "end", value=330)
    model.delete(nginx)
    assert model.size(web) == 999


def test_deleting_a_group_deletes_its_children(model):
    web = model.insert("", "end")
    nginx = model.insert(web, "end")
    model.focus = nginx
    model.selected = web
    model.delete(web)
    assert not model.exists(nginx)
    assert (model.focus, model.selected) == ("", "")


def test_a_bad_name_in_delete_removes_nothing(model):
    web = model.insert("", "end")
    with pytest.raises(ValueError, match="Item nosuch not found"):
        model.delete(web, "nosuch")
    assert model.exists(web)


def test_a_group_and_its_child_can_be_deleted_together(model):
    web = model.insert("", "end")
    nginx = model.insert(web, "end")
    model.delete(web, nginx)
    assert model.get_children() == ()


def test_layout_order_is_largest_first_ties_in_sibling_order(model):
    a = model.insert("", "end", value=1)
    b = model.insert("", "end", value=5)
    c = model.insert("", "end", value=1)
    d = model.insert("", 0, value=1)
    assert model.ordered() == [b, d, a, c]
    assert model.get_children() == (d, a, b, c)


def test_index_takes_numbers_and_end_and_clamps(model):
    a = model.insert("", "end")
    b = model.insert("", -5)
    c = model.insert("", "99")
    assert model.get_children() == (b, a, c)
    with pytest.raises(ValueError, match='bad index "middle"'):
        model.insert("", "middle")


def test_every_change_moves_the_version_on(model):
    seen = [model.version]
    web = model.insert("", "end")
    seen.append(model.version)
    model.configure(web, value=3)
    seen.append(model.version)
    model.delete(web)
    seen.append(model.version)
    assert seen == sorted(set(seen))


def test_a_refused_change_leaves_the_item_as_it_was(model):
    web = model.insert("", "end", text="web", value=3)
    with pytest.raises(ValueError):
        model.configure(web, text="new", value=-1)
    assert (model.item(web).text, model.item(web).value) == ("web", 3)


def test_path(model):
    web = model.insert("", "end")
    nginx = model.insert(web, "end")
    assert model.path(nginx) == (web, nginx)
    assert model.path(web) == (web,)


# A tree as a list of (value, [child values]).
trees = st.lists(
    st.tuples(
        st.integers(0, 1000),
        st.lists(st.integers(0, 1000), max_size=5),
    ),
    max_size=8,
)


@given(trees)
def test_the_total_is_the_sum_of_what_takes_room(tree):
    """A group counts its children, never its own value besides."""
    model = Model()
    for own, children in tree:
        group = model.insert("", "end", value=own)
        for value in children:
            model.insert(group, "end", value=value)
    expected = sum(sum(children) if children else own for own, children in tree)
    assert model.total() == expected
    sizes = [model.size(iid) for iid in model.ordered()]
    assert sizes == sorted(sizes, reverse=True)
