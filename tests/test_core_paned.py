"""Tests for how a paned window divides its room."""

from __future__ import annotations

import pytest

from tkcurses._core.paned import SASH_WIDTH, distribute, place_sash

# ------------------------------------------------------------- distribution


def test_panes_that_fit_are_left_alone():
    assert distribute([10, 10, 10], [0, 0, 0], 30) == [10, 10, 10]


def test_surplus_is_spread_rather_than_given_to_one():
    """Growing a window should widen every pane, not stretch the last."""
    sizes = distribute([5, 5, 5], [0, 0, 0], 20)
    assert sum(sizes) == 20
    assert max(sizes) - min(sizes) <= 1


def test_shortfall_is_spread_too():
    sizes = distribute([10, 10, 10], [0, 0, 0], 15)
    assert sum(sizes) == 15
    assert max(sizes) - min(sizes) <= 1


def test_a_minimum_is_respected_before_a_wish():
    sizes = distribute([10, 10, 10], [8, 0, 0], 12)
    assert sizes[0] == 8
    assert sum(sizes) == 12


def test_a_pane_below_its_minimum_is_brought_up_to_it():
    assert distribute([2], [6], 10) == [10]


def test_panes_that_cannot_fit_come_back_as_they_are():
    """Every pane at its minimum and still too many: the honest answer.

    The container clips them. Pretending otherwise would mean returning
    sizes that do not add up, which whoever draws them has to discover.
    """
    sizes = distribute([5, 5, 5], [5, 5, 5], 6)
    assert sizes == [5, 5, 5]


def test_no_panes_is_no_sizes():
    assert distribute([], [], 40) == []


@pytest.mark.parametrize("available", [0, 1, 7, 40, 400])
def test_the_sizes_never_go_below_one(available):
    for size in distribute([10, 10], [0, 0], available):
        assert size >= 1


# -------------------------------------------------------------- moving a sash


def test_a_sash_moves_the_boundary_between_two_panes():
    assert place_sash([10, 10], 0, 4, [0, 0]) == [4, 16]


def test_moving_a_sash_keeps_the_total():
    """A drag must not ripple through the rest of the window."""
    for position in range(0, 30):
        assert sum(place_sash([10, 10, 10], 1, position, [2, 2, 2])) == 30


def test_a_sash_stops_at_its_neighbours_minimum():
    assert place_sash([10, 10], 0, 25, [0, 3]) == [17, 3]


def test_a_sash_stops_at_its_own_minimum():
    assert place_sash([10, 10], 0, 0, [4, 0]) == [4, 16]


def test_a_middle_sash_leaves_the_other_panes_alone():
    sizes = place_sash([10, 10, 10], 1, 18, [0, 0, 0])
    assert sizes[0] == 10


def test_a_sash_that_does_not_exist_changes_nothing():
    assert place_sash([10, 10], 5, 4, [0, 0]) == [10, 10]
    assert place_sash([10], 0, 4, [0]) == [10]


def test_the_sash_position_counts_the_sashes_before_it():
    """Pane 0 is 10 wide, so sash 1 starts at 10 plus one for sash 0."""
    sizes = place_sash([10, 10, 10], 1, 10 + SASH_WIDTH + 4, [0, 0, 0])
    assert sizes[1] == 4
