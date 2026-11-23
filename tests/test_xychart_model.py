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

"""An XY chart's series: points kept sorted, one kind of x, Treeview's
error words, and nothing changed by a refused call."""

import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.xychart._model import Model, checked_x, checked_y


def test_points_are_kept_sorted_by_x():
    model = Model()
    model.add("cpu", [(3, 30), (1, 10), (2, 20)])
    assert model.get("cpu").points() == [(1, 10), (2, 20), (3, 30)]


def test_an_x_given_twice_keeps_the_later_y():
    model = Model()
    model.add("cpu", [(1, 10), (1, 11)])
    model.append("cpu", (1, 12))
    assert model.get("cpu").points() == [(1, 12)]


@given(st.lists(st.tuples(st.integers(-50, 50), st.integers(-9, 9)), max_size=40))
def test_any_points_end_sorted_each_x_once_with_its_last_y(points):
    model = Model()
    model.add("s")
    for point in points:
        model.append("s", point)
    expected = dict(points)
    assert model.get("s").points() == sorted(expected.items())


def test_series_keep_the_order_they_were_added():
    model = Model()
    for name in ("b", "a", "c"):
        model.add(name)
    assert model.names() == ["b", "a", "c"]


def test_a_missing_value_is_none():
    model = Model()
    model.add("cpu", [(1, 10), (2, None)])
    assert model.get("cpu").ys == [10, None]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "x", True, [1]])
def test_a_bad_y_is_refused(bad):
    with pytest.raises(ValueError, match="y"):
        checked_y(bad)


@pytest.mark.parametrize("bad", [float("nan"), float("-inf"), "x", False, None])
def test_a_bad_x_is_refused(bad):
    with pytest.raises(ValueError, match="x"):
        checked_x(bad)


def test_a_time_is_epoch_seconds():
    aware = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.UTC)
    assert checked_x(aware) == (aware.timestamp(), "time")
    naive = dt.datetime(2026, 11, 23, 12, 0)
    assert checked_x(naive) == (naive.timestamp(), "time")  # local time
    day = dt.date(2026, 11, 23)
    assert checked_x(day) == (dt.datetime(2026, 11, 23).timestamp(), "time")


def test_every_x_in_a_chart_is_the_same_kind():
    model = Model()
    model.add("a", [(dt.datetime(2026, 1, 1), 1)])
    with pytest.raises(ValueError, match="x is a time in this chart, not a number"):
        model.add("b", [(5, 1)])
    with pytest.raises(ValueError, match="not a number"):
        model.append("a", (5, 1))
    assert not model.exists("b")


def test_a_points_kinds_cannot_mix_within_one_call():
    model = Model()
    with pytest.raises(ValueError, match="not a time"):
        model.add("a", [(1, 1), (dt.date(2026, 1, 1), 2)])
    assert not model.exists("a")
    assert model.xkind is None


def test_the_kind_is_free_again_once_no_series_has_points():
    model = Model()
    model.add("a", [(1, 1)])
    assert model.xkind == "number"
    model.set("a", [(dt.date(2026, 1, 1), 1)])  # its own points do not count
    assert model.xkind == "time"
    model.delete("a")
    model.add("b", [(1, 1)])
    assert model.xkind == "number"


def test_a_refused_set_or_append_changes_nothing():
    model = Model()
    model.add("a", [(1, 1), (2, 2)])
    before = model.version
    with pytest.raises(ValueError):
        model.set("a", [(3, 3), (4, "x")])
    with pytest.raises(ValueError):
        model.append("a", (5, 5), (6, float("nan")))
    assert model.get("a").points() == [(1, 1), (2, 2)]
    assert model.version == before


def test_a_point_must_be_a_pair():
    model = Model()
    with pytest.raises(ValueError, match=r"expected a point \(x, y\)"):
        model.add("a", [(1, 2, 3)])


def test_treeviews_words():
    model = Model()
    model.add("a")
    with pytest.raises(ValueError, match="Series a already exists"):
        model.add("a")
    with pytest.raises(ValueError, match="Series z not found"):
        model.get("z")


def test_delete_checks_every_name_first():
    model = Model()
    model.add("a")
    model.add("b")
    with pytest.raises(ValueError, match="Series z not found"):
        model.delete("a", "z")
    assert model.names() == ["a", "b"]
    model.delete("a", "b")
    assert model.names() == []


def test_configure_changes_only_what_it_is_given():
    model = Model()
    model.add("a", kind="area", text="CPU", color="red", description="all cores")
    model.configure("a", text="cpu")
    series = model.get("a")
    assert (series.kind, series.text, series.color, series.description) == (
        "area",
        "cpu",
        "red",
        "all cores",
    )
    with pytest.raises(ValueError, match='bad kind "bar": must be line or area'):
        model.configure("a", kind="bar")
    assert model.get("a").kind == "area"


def test_the_label_is_the_name_without_text():
    model = Model()
    model.add("cpu")
    assert model.get("cpu").label == "cpu"
    model.configure("cpu", text="CPU %")
    assert model.get("cpu").label == "CPU %"


def test_hidden_series_leave_the_shown_and_their_xs():
    model = Model()
    model.add("a", [(1, 1), (3, 3)])
    model.add("b", [(2, 2), (3, 3)])
    assert model.xs() == [1, 2, 3]
    model.configure("b", hidden=True)
    assert [s.name for s in model.shown()] == ["a"]
    assert model.xs() == [1, 3]


def test_every_change_moves_the_version():
    model = Model()
    versions = [model.version]
    for change in (
        lambda: model.add("a"),
        lambda: model.append("a", (1, 1)),
        lambda: model.set("a", [(2, 2)]),
        lambda: model.configure("a", color="red"),
        lambda: model.delete("a"),
    ):
        change()
        versions.append(model.version)
    assert versions == sorted(set(versions))
