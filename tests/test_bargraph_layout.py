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

"""Where the bars, labels, axis, readout, baseline and title go."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses.bargraph._layout import (
    LayoutSpec,
    Rect,
    compute_layout,
    length_cells_for,
    natural_size,
    place_text,
    track_sizes,
)

# ------------------------------------------------------------------ spec ----


@pytest.mark.parametrize(
    "options",
    [
        {"orient": "diagonal"},
        {"segments": 0},
        {"thickness": 0},
        {"gap": -1},
        {"borderwidth": -1},
        {"labelanchor": "center"},
        {"orient": "vertical", "readout_width": 3},
    ],
)
def test_spec_rejects(options):
    with pytest.raises(ValueError):
        LayoutSpec(**options)


def test_label_column_is_the_longest_label_capped():
    assert LayoutSpec(labels=("a", "abcd")).label_column_width == 4
    assert LayoutSpec(labels=("x" * 30,), labelwidth=12).label_column_width == 12
    assert LayoutSpec(labels=("", "")).label_column_width == 0


# ------------------------------------------------------------ thickness ----


def test_absolute_thickness_is_fixed():
    spec = LayoutSpec(segments=3, thickness=2, relative=False)
    assert track_sizes(100, spec) == [2, 2, 2]


def test_relative_thickness_shares_the_space_evenly():
    # 20 cells, 3 segments, 2 gaps of 1: 18 to share -> 6 each.
    assert track_sizes(20, LayoutSpec(segments=3)) == [6, 6, 6]
    # 21 cells: 19 to share -> 7, 6, 6 (leftover to the leading bars).
    assert track_sizes(21, LayoutSpec(segments=3)) == [7, 6, 6]


def test_relative_thickness_never_below_the_minimum():
    spec = LayoutSpec(segments=4, thickness=3)
    assert track_sizes(10, spec) == [3, 3, 3, 3]


# ------------------------------------------------------------- vertical ----


def test_vertical_bare():
    layout = compute_layout(5, 4, LayoutSpec(segments=3, thickness=1, relative=False))
    assert layout.bars == Rect(0, 0, 5, 4)
    assert layout.tracks == (Rect(0, 0, 1, 4), Rect(2, 0, 1, 4), Rect(4, 0, 1, 4))
    assert layout.length_cells == 4
    assert (layout.title, layout.axis, layout.baseline, layout.readout) == (None,) * 4
    assert layout.labels == ()


def test_vertical_everything():
    spec = LayoutSpec(
        segments=2,
        thickness=2,
        relative=False,
        borderwidth=1,
        title="CPU",
        labels=("a", "b"),
        axis=True,
        axis_label_width=3,
        baseline=True,
    )
    layout = compute_layout(12, 10, spec)
    # Box: inner area is (1, 1, 10, 8). Title sits in the top edge.
    assert layout.title == Rect(2, 0, 8, 1)
    # Axis: 3 label columns + 1 ruler column on the left.
    assert layout.axis == Rect(1, 1, 4, 6)
    assert layout.bars == Rect(5, 1, 6, 6)
    assert layout.baseline == Rect(5, 7, 6, 1)
    assert layout.labels == (Rect(5, 8, 2, 1), Rect(8, 8, 2, 1))
    assert layout.tracks == (Rect(5, 1, 2, 6), Rect(8, 1, 2, 6))


def test_title_without_a_box_takes_a_row():
    top = compute_layout(10, 5, LayoutSpec(title="T"))
    assert top.title == Rect(0, 0, 10, 1)
    assert top.bars == Rect(0, 1, 10, 4)
    bottom = compute_layout(10, 5, LayoutSpec(title="T", labelanchor="se"))
    assert bottom.title == Rect(0, 4, 10, 1)
    assert bottom.bars == Rect(0, 0, 10, 4)


def test_title_in_the_bottom_edge():
    layout = compute_layout(
        10, 5, LayoutSpec(title="T", labelanchor="s", borderwidth=1)
    )
    assert layout.title == Rect(2, 4, 6, 1)
    assert layout.bars == Rect(1, 1, 8, 3)


def test_segments_that_do_not_fit_are_clipped():
    layout = compute_layout(4, 2, LayoutSpec(segments=3, thickness=2, relative=False))
    assert layout.tracks == (Rect(0, 0, 2, 2), Rect(3, 0, 1, 2), Rect(4, 0, 0, 2))
    assert layout.tracks[2].empty


# ----------------------------------------------------------- horizontal ----


def test_horizontal_everything():
    spec = LayoutSpec(
        orient="horizontal",
        segments=2,
        relative=False,
        labels=("cpu0", "cpu1"),
        baseline=True,
        readout_width=3,
        axis=True,
    )
    layout = compute_layout(20, 5, spec)
    # Labels 4 + space, baseline 1, readout space + 3, axis 2 rows.
    assert layout.labels == (Rect(0, 0, 4, 1), Rect(0, 2, 4, 1))
    assert layout.baseline == Rect(5, 0, 1, 3)
    assert layout.bars == Rect(6, 0, 10, 3)
    assert layout.readout == Rect(17, 0, 3, 3)
    assert layout.axis == Rect(6, 3, 10, 2)
    assert layout.tracks == (Rect(6, 0, 10, 1), Rect(6, 2, 10, 1))
    assert layout.length_cells == 10


# ---------------------------------------------------------- natural size ----


def test_natural_size_fits_the_whole_title():
    boxed = LayoutSpec(relative=False, borderwidth=1, title="CPU load")
    width, _ = natural_size(boxed, 1)
    # "┌─ CPU load ─┐": corner and line either side, a space either side.
    assert width == len("CPU load") + 2 + 4
    plain = LayoutSpec(relative=False, title="CPU load")
    assert natural_size(plain, 1) == (8, 2)


def test_length_cells_for_points():
    assert length_cells_for(8) == 1
    assert length_cells_for(20) == 3
    assert length_cells_for(64) == 8


SPECS = st.builds(
    LayoutSpec,
    orient=st.sampled_from(["vertical", "horizontal"]),
    segments=st.integers(1, 6),
    thickness=st.integers(1, 3),
    gap=st.integers(0, 2),
    relative=st.booleans(),
    borderwidth=st.integers(0, 2),
    title=st.sampled_from(["", "Load"]),
    labelanchor=st.sampled_from(["n", "nw", "ne", "s", "sw", "se"]),
    labels=st.sampled_from([(), ("a", "bb"), ("long label",)]),
    axis=st.booleans(),
    axis_label_width=st.integers(0, 4),
    baseline=st.booleans(),
)


@given(SPECS, st.integers(1, 20))
def test_natural_size_fits_everything(spec, length):
    width, height = natural_size(spec, length)
    layout = compute_layout(width, height, spec)
    if spec.title:
        # The graph is widened so the whole title shows; on a horizontal
        # graph that width lands along the bars, as empty track past the
        # peak.
        assert layout.length_cells >= length
    else:
        assert layout.length_cells == length
    assert all(not track.empty for track in layout.tracks)


def _cells(rect: Rect) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x in range(rect.x, rect.x + max(0, rect.width))
        for y in range(rect.y, rect.y + max(0, rect.height))
    }


@given(SPECS, st.integers(0, 40), st.integers(0, 20))
def test_regions_stay_inside_and_do_not_overlap(spec, width, height):
    layout = compute_layout(width, height, spec)
    window = _cells(Rect(0, 0, width, height))
    inner = _cells(Rect(0, 0, width, height).inset(spec.borderwidth))
    regions = [layout.bars, layout.axis, layout.baseline, layout.readout]
    regions += [layout.title] if spec.borderwidth == 0 else []
    regions += list(layout.labels)
    seen: set[tuple[int, int]] = set()
    for region in regions:
        if region is None:
            continue
        cells = _cells(region)
        assert cells <= inner
        assert not cells & seen
        seen |= cells
    for rect in (*layout.tracks, *layout.labels):
        assert _cells(rect) <= inner
    if layout.title is not None:
        assert _cells(layout.title) <= window


# ------------------------------------------------------------ place_text ----


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [("nw", (0, "abc")), ("ne", (7, "abc")), ("n", (3, "abc")), ("s", (3, "abc"))],
)
def test_place_text(anchor, expected):
    assert place_text(Rect(0, 0, 10, 1), "abc", anchor) == expected


def test_place_text_truncates_with_an_ellipsis():
    assert place_text(Rect(2, 0, 4, 1), "abcdef", "n") == (2, "abc…")
    assert place_text(Rect(2, 0, 1, 1), "abcdef", "n") == (2, "…")
    assert place_text(Rect(2, 0, 0, 1), "abcdef", "n") == (2, "")


# ------------------------------------------------------------ axis title


def _titled(**kwargs):
    base = {"axis": True, "borderwidth": 1, "axis_title": "Load (ms)"}
    return LayoutSpec(**(base | kwargs))


def test_axis_title_goes_left_in_the_edge_at_the_axis_end():
    vertical = compute_layout(30, 10, _titled())
    assert vertical.axis_title == Rect(2, 0, 11, 1)
    horizontal = compute_layout(30, 10, _titled(orient="horizontal"))
    assert horizontal.axis_title == Rect(2, 9, 11, 1)


def test_the_graph_label_keeps_its_place_and_the_axis_title_moves_right():
    layout = compute_layout(30, 10, _titled(title="CPU", labelanchor="nw"))
    assert layout.title is not None
    assert layout.axis_title == Rect(30 - 2 - 11, 0, 11, 1)


def test_a_label_on_the_other_edge_is_no_obstacle():
    layout = compute_layout(30, 10, _titled(title="CPU", labelanchor="sw"))
    assert layout.axis_title == Rect(2, 0, 11, 1)


def test_no_axis_title_where_it_does_not_fit():
    assert compute_layout(14, 10, _titled()).axis_title is None
    # Both ends taken by a long centred label.
    long = "A label as long as the edge"
    assert compute_layout(30, 10, _titled(title=long)).axis_title is None


def test_no_axis_title_without_a_box_or_an_axis():
    assert compute_layout(30, 10, _titled(borderwidth=0)).axis_title is None
    assert compute_layout(30, 10, _titled(axis=False)).axis_title is None


def test_natural_size_makes_room_for_the_axis_title():
    spec = _titled(segments=1, thickness=1, axis_label_width=2)
    width, _ = natural_size(spec, 4)
    assert width >= len(" Load (ms) ") + 4
    beside = _titled(segments=1, axis_label_width=2, title="CPU", labelanchor="nw")
    width, _ = natural_size(beside, 4)
    layout = compute_layout(width, 8, beside)
    assert layout.axis_title is not None and layout.title is not None
