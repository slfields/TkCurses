"""Tests for tkcurses._core.attributes."""

from __future__ import annotations

import curses

import pytest

from tkcurses._core.attributes import (
    ATTRIBUTES,
    BorderStyle,
    attribute_names,
    for_state,
    from_font,
    parse_attributes,
    style_for_relief,
    without,
)
from tkcurses.constants import FLAT, GROOVE, RAISED, RIDGE, SOLID, SUNKEN

# ------------------------------------------------------------------ parsing


def test_parse_single_name():
    assert parse_attributes("bold") == curses.A_BOLD


def test_parse_several_names():
    mask = parse_attributes("bold underline")
    assert mask & curses.A_BOLD
    assert mask & curses.A_UNDERLINE


def test_parse_accepts_a_sequence():
    assert parse_attributes(["bold", "reverse"]) == parse_attributes("bold reverse")


def test_parse_passes_a_mask_through():
    assert parse_attributes(curses.A_BOLD | curses.A_DIM) == (
        curses.A_BOLD | curses.A_DIM
    )


def test_parse_is_case_insensitive_and_ignores_padding():
    assert parse_attributes("  BOLD   Underline ") == parse_attributes("bold underline")


def test_parse_empty_is_normal():
    assert parse_attributes("") == curses.A_NORMAL
    assert parse_attributes([]) == curses.A_NORMAL


def test_parse_skips_blank_entries():
    """A sequence assembled from optional parts may contain empty strings."""
    assert parse_attributes(["bold", "", "  ", "underline"]) == parse_attributes(
        "bold underline"
    )


def test_parse_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown text attribute"):
        parse_attributes("sparkly")


@pytest.mark.parametrize("name", sorted(ATTRIBUTES))
def test_every_documented_attribute_parses(name):
    parse_attributes(name)


def test_attribute_names_round_trip():
    mask = parse_attributes("bold underline")
    names = attribute_names(mask)
    assert "bold" in names
    assert "underline" in names
    assert "dim" not in names


def test_attribute_names_of_normal_is_empty():
    """A_NORMAL is zero, so it names nothing that is set."""
    assert attribute_names(curses.A_NORMAL) == ()


def test_without_clears_attributes():
    mask = parse_attributes("bold underline dim")
    cleared = without(mask, curses.A_BOLD, curses.A_DIM)
    assert not cleared & curses.A_BOLD
    assert not cleared & curses.A_DIM
    assert cleared & curses.A_UNDERLINE


def test_without_is_harmless_when_the_attribute_is_absent():
    assert without(curses.A_BOLD, curses.A_BLINK) == curses.A_BOLD


# ------------------------------------------------------------------- states


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("normal", curses.A_NORMAL),
        ("active", curses.A_REVERSE),
        ("disabled", curses.A_DIM),
    ],
)
def test_state_attributes(state, expected):
    assert for_state(state) == expected


def test_state_keeps_the_base_attributes():
    assert for_state("disabled", curses.A_UNDERLINE) == (
        curses.A_UNDERLINE | curses.A_DIM
    )


def test_unknown_state_is_rejected():
    with pytest.raises(ValueError, match="unknown widget state"):
        for_state("hovering")


# -------------------------------------------------------------------- fonts


def test_font_styling():
    assert from_font() == curses.A_NORMAL
    assert from_font(bold=True) == curses.A_BOLD
    assert from_font(italic=True) == curses.A_ITALIC
    assert from_font(underline=True) == curses.A_UNDERLINE
    combined = from_font(bold=True, italic=True, underline=True)
    for flag in (curses.A_BOLD, curses.A_ITALIC, curses.A_UNDERLINE):
        assert combined & flag


# ------------------------------------------------------------------ borders


@pytest.mark.parametrize("relief", [FLAT, RAISED, SUNKEN, SOLID, RIDGE, GROOVE])
def test_every_tkinter_relief_has_a_style(relief):
    assert isinstance(style_for_relief(relief), BorderStyle)


def test_relief_is_case_insensitive():
    assert style_for_relief("RAISED") == style_for_relief("raised")


def test_unknown_relief_is_rejected():
    with pytest.raises(ValueError, match="unknown relief"):
        style_for_relief("embossed")


def test_solid_border_edges():
    style = style_for_relief(SOLID)
    assert style.top(6) == "┌────┐"
    assert style.bottom(6) == "└────┘"


def test_ridge_uses_doubled_lines():
    """Reliefs are told apart by line style, since a terminal cannot shade."""
    assert style_for_relief(RIDGE).top(5) == "╔═══╗"


def test_flat_relief_draws_nothing_visible():
    style = style_for_relief(FLAT)
    assert style.top(5).strip() == ""
    assert style.vertical == " "


def test_raised_and_sunken_differ_by_attribute():
    raised = style_for_relief(RAISED)
    sunken = style_for_relief(SUNKEN)
    assert raised.horizontal == sunken.horizontal, "same glyphs"
    assert raised.attr != sunken.attr, "told apart by weight"
    assert raised.attr == curses.A_BOLD
    assert sunken.attr == curses.A_DIM


@pytest.mark.parametrize("width", [0, 1, 2, 3, 10])
def test_edges_are_exactly_the_requested_width(width):
    """A border one cell too long would overwrite its neighbour."""
    style = style_for_relief(SOLID)
    assert len(style.top(width)) == max(0, width)
    assert len(style.bottom(width)) == max(0, width)


def test_degenerate_widths():
    style = style_for_relief(SOLID)
    assert style.top(0) == ""
    assert style.top(1) == "┌"
    assert style.top(2) == "┌┐"
