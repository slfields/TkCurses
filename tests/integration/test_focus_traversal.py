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


"""Tab order across a tree of containers.

Focus order is a property of the whole tree, not of any widget in it: it is
the order widgets were created within their toplevel, flattened through
however many frames they sit in. One widget cannot have an order, so none of
this could be a unit test.

Two rules are doing the work, and Tk states them separately:

- **Creation order, not layout order.** Repacking a widget does not move it
  in the tab order, which is why a form can be rearranged on screen without
  the keyboard following.
- **Who is eligible.** ``takefocus`` decides explicitly; left unset, a widget
  is eligible only while it is viewable and not disabled.
"""

from __future__ import annotations

import pytest

import tkcurses


@pytest.fixture
def form(app):
    """A window, a frame, a frame inside that, and five widgets among them.

    Created in the order a, b, c, d, e but scattered across three levels, so
    that a traversal following the tree and one following any single
    container would give different answers.
    """
    top = tkcurses.Toplevel(app, width=40, height=14)
    outer = tkcurses.Frame(top, name="outer")
    first = tkcurses.Entry(outer, name="a")
    second = tkcurses.Button(outer, name="b", text="B")
    inner = tkcurses.Frame(outer, name="inner")
    third = tkcurses.Entry(inner, name="c")
    caption = tkcurses.Label(inner, name="caption", text="not focusable")
    last = tkcurses.Checkbutton(top, name="e")
    for widget in (first, second, inner, third, caption):
        widget.pack()
    outer.pack()
    last.pack()
    app.update_layout()
    return {
        "top": top,
        "outer": outer,
        "inner": inner,
        "a": first,
        "b": second,
        "c": third,
        "caption": caption,
        "e": last,
    }


def walk(start, steps=5, back=False):
    """The names visited by tabbing ``steps`` times from ``start``."""
    seen, current = [], start
    for _ in range(steps):
        seen.append(current.winfo_name())
        current = current.tk_focusPrev() if back else current.tk_focusNext()
    return seen


# ----------------------------------------------------------------- the order


def test_tab_order_follows_the_tree_across_containers(form):
    """a and b in one frame, c in a frame inside it, e in the window itself -
    and tabbing goes straight through all three levels in creation order.
    """
    assert walk(form["a"], 4) == ["a", "b", "c", "e"]


def test_tab_order_wraps_around(form):
    assert walk(form["a"], 5) == ["a", "b", "c", "e", "a"]


def test_shift_tab_walks_the_same_order_backwards(form):
    assert walk(form["a"], 4, back=True) == ["a", "e", "c", "b"]


def test_containers_are_not_in_the_order(form):
    """Frames hold widgets; they are not stops on the way through them."""
    assert form["outer"].winfo_name() not in walk(form["a"], 6)
    assert form["inner"].winfo_name() not in walk(form["a"], 6)


def test_a_label_is_not_in_the_order(form):
    assert "caption" not in walk(form["a"], 6)


def test_relaying_out_a_widget_does_not_move_it_in_the_order(form):
    """Creation order, not layout order. Rearranging a form on screen must
    not rearrange the keyboard, or every cosmetic change becomes a usability
    change.
    """
    before = walk(form["a"], 4)

    form["b"].pack_forget()
    form["b"].pack()

    assert walk(form["a"], 4) == before


# ------------------------------------------- from a widget that is no stop


@pytest.mark.parametrize("make", ["classic", "ttk", "label"])
def test_tab_from_a_widget_tab_skips_moves_on_from_where_it_is(app, make):
    """A clicked scrollbar has the focus without being a Tab stop. Measured
    on Tk 9.0.2 with a Listbox, Entry a, a Scrollbar and Entry b: from the
    scrollbar, Tab goes to b and Shift-Tab to a - tk::FocusNext walks the
    tree from the widget itself. TkCurses went to the Listbox and b, the
    first and last stops in the window."""
    from tkcurses import ttk

    top = tkcurses.Toplevel(app)
    tkcurses.Listbox(top, name="list")
    tkcurses.Entry(top, name="a")
    skipped = {
        "classic": lambda: tkcurses.Scrollbar(top),
        "ttk": lambda: ttk.Scrollbar(top),
        "label": lambda: tkcurses.Label(top, text="no stop"),
    }[make]()
    tkcurses.Entry(top, name="b")
    assert not skipped._focus_ok()
    skipped.focus_set()
    assert skipped.tk_focusNext().winfo_name() == "b"
    assert skipped.tk_focusPrev().winfo_name() == "a"


def test_from_the_window_itself_tab_starts_at_either_end(form):
    assert form["top"].tk_focusNext().winfo_name() == "a"
    assert form["top"].tk_focusPrev().winfo_name() == "e"


def test_a_window_with_no_stops_has_no_next(app):
    top = tkcurses.Toplevel(app)
    label = tkcurses.Label(top, text="nothing to focus")
    assert label.tk_focusNext() is None
    assert top.tk_focusPrev() is None


# ------------------------------------------------------------- eligibility


def test_takefocus_false_takes_a_widget_out_of_the_order(form):
    form["c"].configure(takefocus=False)

    assert walk(form["a"], 4) == ["a", "b", "e", "a"]


def test_takefocus_true_puts_one_back_in(form):
    form["caption"].configure(takefocus=True)

    assert "caption" in walk(form["a"], 6)


def test_a_disabled_widget_is_skipped(form):
    """Measured on Tk 9.0.2: with b disabled, tabbing from a gives
    ['a', 'c', 'a', 'c'] - b is gone from the order, and ::tk::FocusOK
    answers 0 for it.

    Here it stays in, so the keyboard lands on a widget that cannot be typed
    into and gives no sign of why. The next Tab moves on, so it reads as a
    dead stop rather than a skipped stop.
    """
    form["b"].configure(state="disabled")

    assert walk(form["a"], 3) == ["a", "c", "e"]


def test_re_enabling_a_widget_leaves_it_in_the_order(form):
    """Not an xfail, and it was one until the suite reported it xpassing.

    While TkCurses-s6g stands, disabling never removed the widget, so
    disabling and re-enabling cannot change anything and the test cannot
    fail either way. It stays because it must still hold *after* the fix -
    that is the half of the round trip the fix could plausibly get wrong -
    but it proves nothing today, and marking it xfail claimed otherwise.
    """
    form["b"].configure(state="disabled")
    form["b"].configure(state="normal")

    assert walk(form["a"], 4) == ["a", "b", "c", "e"]


def test_an_explicit_takefocus_still_wins_over_the_state(form):
    """The rule underneath the bug, and the reason the fix is three rules
    rather than one: Tk consults -takefocus first, and only falls back to the
    state check when it is unset. takefocus=True on a disabled widget still
    takes focus.
    """
    form["b"].configure(state="disabled", takefocus=True)

    assert "b" in walk(form["a"], 4)


# ------------------------------------------------------- focus and the screen


def test_focus_set_puts_the_focus_on_the_widget(form):
    form["c"].focus_set()
    assert form["c"].focus_get() is form["c"]


def test_focus_survives_the_window_being_raised(form):
    """Raising is a stacking change, not a focus change - and it now moves a
    whole subtree of panels, so this is worth asserting rather than assuming.
    """
    form["c"].focus_set()

    form["top"].tkraise()

    assert form["c"].focus_get() is form["c"]


def test_focus_survives_the_window_being_moved(form):
    form["c"].focus_set()

    form["top"].geometry("40x14+10+4")

    assert form["c"].focus_get() is form["c"]


def test_destroying_the_focused_widget_does_not_leave_focus_on_it(form):
    """Whatever happens next, the focus must not still name something that
    no longer exists - every key would go to a destroyed widget.
    """
    form["c"].focus_set()

    form["c"].destroy()

    assert form["a"].focus_get() is not form["c"]


def test_the_order_closes_up_after_a_widget_is_destroyed(form):
    form["b"].destroy()

    assert walk(form["a"], 3) == ["a", "c", "e"]
