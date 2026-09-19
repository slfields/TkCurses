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


"""Containers inside containers, and the size that has to survive the trip.

**A container asks its parent for what its children need plus what it spends
on itself.** Its children are laid out in its *content* area - the rect less
border, padding and menubar - so a container that passes the raw manager
request upward is short by exactly what it spends, and clips its own
contents by exactly that.

That is TkCurses-2dz, found by a person noticing a dialog panel came out one
row tall. It cannot fail with one widget: it needs a container, a child
inside it, and a parent above it to ask.

The other thing only nesting shows is that the arithmetic has to hold at
every level at once. One frame getting its border right proves nothing about
three of them.
"""

from __future__ import annotations

import tkcurses

#: What a border costs on each axis: one cell each side.
EDGE = 2


def stack_of(app, depth: int, text: str = "12345"):
    """``depth`` bordered frames inside each other, with a label at the bottom.

    The outermost is placed, because something has to say where the stack
    goes. Every level below alternates pack and grid, because the request
    has to travel up through whichever of them is there and a bug in one
    would otherwise hide behind the other.

    Not place, below the top. A placed child does not contribute to its
    parent's requested size - measured against Tk 9.0.2, where a parent
    holding one placed child asks for 1x1 - so a placed level would collapse
    the stack above it, correctly, and prove nothing about borders. That
    rule gets its own test below.
    """
    managers = ["place", "pack", "grid", "pack", "grid"]
    parent = app
    frames = []
    for level in range(depth):
        frame = tkcurses.Frame(parent, name=f"f{level}", relief="solid")
        frames.append(frame)
        parent = frame
    # Three rows rather than one. A single-row leaf makes the whole stack
    # degenerate uniformly when the arithmetic is wrong - every frame ends up
    # the leaf's size, too short to draw a border at all, and containment
    # then holds trivially. Three rows keep the frames tall enough that a
    # border is really drawn, which is what clips.
    leaf = tkcurses.Frame(parent, name="leaf", relief="flat")
    for index in range(3):
        tkcurses.Label(leaf, name=f"row{index}", text=text).pack()
    leaf.pack()
    for level in reversed(range(depth)):
        frame = frames[level]
        manager = managers[min(level, len(managers) - 1)]
        if manager == "place":
            frame.place(x=0, y=0)
        elif manager == "pack":
            frame.pack()
        else:
            frame.grid(row=0, column=0)
    app.update_layout()
    return frames, leaf


# ------------------------------------------------------------------- one level


def test_a_bordered_container_asks_for_room_for_its_own_border(app):
    """Regression, TkCurses-2dz.

    Three stacked 9x1 rows need 9x3 of content. A bordered frame holding
    them must ask for 11x5, not 9x3 - which is what it used to ask for, and
    why it drew a border over the first and last of the three rows and showed
    one.
    """
    frame = tkcurses.Frame(app, name="f", relief="solid")
    rows = [tkcurses.Label(frame, name=f"r{i}", text="123456789") for i in range(3)]
    for row in rows:
        row.pack()
    frame.place(x=0, y=0)
    app.update_layout()

    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (9 + EDGE, 3 + EDGE)


def test_the_children_of_a_bordered_container_are_not_clipped_by_it(app):
    """The half a size assertion misses: the rows must actually be there."""
    frame = tkcurses.Frame(app, name="f", relief="solid")
    rows = [tkcurses.Label(frame, name=f"r{i}", text="123456789") for i in range(3)]
    for row in rows:
        row.pack()
    frame.place(x=0, y=0)
    app.update_layout()

    assert [(r._rect.width, r._rect.height) for r in rows] == [(9, 1)] * 3


def test_a_borderless_container_asks_for_exactly_what_its_children_need(app):
    """The control. Without it, an over-generous fudge would pass the test
    above and nobody would know.
    """
    frame = tkcurses.Frame(app, name="f", relief="flat")
    for index in range(3):
        tkcurses.Label(frame, name=f"r{index}", text="123456789").pack()
    frame.place(x=0, y=0)
    app.update_layout()

    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (9, 3)


def test_padding_is_asked_for_as_well_as_the_border(app):
    frame = tkcurses.Frame(app, name="f", relief="solid", padx=2, pady=1)
    tkcurses.Label(frame, name="l", text="123456789").pack()
    frame.place(x=0, y=0)
    app.update_layout()

    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (
        9 + EDGE + 4,
        1 + EDGE + 2,
    )


def test_a_labelframe_leaves_room_for_its_own_border_too(app):
    """Every container type that can hold children gets this case. A
    LabelFrame's title sits in its top border, as a Toplevel's does, so it
    costs a border and not a row more.
    """
    frame = tkcurses.LabelFrame(app, name="lf", text="Box")
    tkcurses.Label(frame, name="l", text="123456789").pack()
    frame.place(x=0, y=0)
    app.update_layout()

    assert (frame.winfo_reqwidth(), frame.winfo_reqheight()) == (9 + EDGE, 1 + EDGE)
    assert frame._content_rect().width == 9


# ---------------------------------------------------------------- many levels


def test_every_level_of_nesting_costs_exactly_its_own_border(app):
    """Three frames, three managers, and the arithmetic holds at each step.

    5x1 of text, and each bordered level adds one cell on every side: 7x3,
    9x5, 11x7. A level that forgot, or one that counted twice, breaks the
    sequence rather than only the total.
    """
    frames, leaf = stack_of(app, 3)

    sizes = [(f._rect.width, f._rect.height) for f in frames]
    assert sizes == [(11, 9), (9, 7), (7, 5)]
    assert (leaf._rect.width, leaf._rect.height) == (5, 3)


def test_nesting_offsets_each_level_by_its_own_border(app):
    """Position, not just size: each content area starts one cell in."""
    frames, leaf = stack_of(app, 3)

    positions = [(f.winfo_rootx(), f.winfo_rooty()) for f in frames]
    assert positions == [(0, 0), (1, 1), (2, 2)]
    assert (leaf.winfo_rootx(), leaf.winfo_rooty()) == (3, 3)


def test_every_child_fits_inside_the_container_that_holds_it(app):
    """The point of the whole module, and the assertion that took two goes.

    Asserting the leaf's *size* proves nothing: under the 2dz bug the leaf
    still measured 5x1, because it got what it asked for and the frames
    around it collapsed to 5x1 as well - no room for a border, so the border
    was drawn straight over the label. The size was right and the screen was
    wrong.

    What has to hold is containment: every child sits wholly within its
    parent's content area, at every level. That is false the moment a
    container forgets to ask for its own border.
    """
    frames, leaf = stack_of(app, 5)

    for parent, child in zip([app, *frames], [*frames, leaf], strict=True):
        inside = parent._content_rect()
        left, top = child.winfo_rootx(), child.winfo_rooty()
        assert left >= inside.x, (child._name, left, inside)
        assert top >= inside.y, (child._name, top, inside)
        assert left + child._rect.width <= inside.x + inside.width, child._name
        assert top + child._rect.height <= inside.y + inside.height, child._name


# ------------------------------------------------------- when there is no room


def test_a_squeezed_container_gives_its_child_the_content_area(app):
    """A container forced smaller than it asked for passes on what is left
    *inside* it, not its whole rect - otherwise the child draws over the
    border it is supposed to sit within.
    """
    frame = tkcurses.Frame(app, name="f", relief="solid")
    child = tkcurses.Label(frame, name="big", text="x" * 20)
    child.pack()
    frame.place(x=0, y=0, width=8, height=3)
    app.update_layout()

    assert (frame._rect.width, frame._rect.height) == (8, 3)
    assert (child._rect.width, child._rect.height) == (8 - EDGE, 1)


def test_a_container_with_no_room_at_all_does_not_go_negative(app):
    """Two cells of frame is exactly its border and nothing else. The child
    gets zero, not minus two.
    """
    frame = tkcurses.Frame(app, name="f", relief="solid")
    child = tkcurses.Label(frame, name="c", text="xxxx")
    child.pack()
    frame.place(x=0, y=0, width=2, height=2)
    app.update_layout()

    assert frame._content_rect().width >= 0
    assert child._rect.width >= 0


# ------------------------------------------------------------ change and relay


def test_resizing_the_outermost_container_travels_all_the_way_down(app):
    """A resize is not a fresh layout: the levels in between have to pass it
    on. Measured by giving the child something to fill with.
    """
    outer = tkcurses.Frame(app, name="outer", relief="solid")
    inner = tkcurses.Frame(outer, name="inner", relief="solid")
    child = tkcurses.Label(app.nametowidget(str(inner)), name="c", text="x")
    child.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    inner.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    outer.place(x=0, y=0, width=20, height=10)
    app.update_layout()
    assert (child._rect.width, child._rect.height) == (20 - 2 * EDGE, 10 - 2 * EDGE)

    outer.place_configure(width=30, height=14)
    app.update_layout()

    assert (child._rect.width, child._rect.height) == (30 - 2 * EDGE, 14 - 2 * EDGE)


# ------------------------------------------------------- which manager asks


def test_a_placed_child_does_not_size_its_parent(app):
    """Measured against Tk 9.0.2: a parent holding one placed child asks for
    1x1, where the same child packed or gridded makes it ask for the child's
    size.

    Place means "put it exactly here", and a manager that honours an exact
    position cannot also be negotiating for room. Worth a test because it is
    the one case where a container legitimately ignores what is inside it,
    and it looks identical to the 2dz bug from the outside.
    """
    outer = tkcurses.Frame(app, name="outer", relief="flat")
    inner = tkcurses.Label(outer, name="inner", text="12345")
    inner.place(x=0, y=0)
    outer.pack()
    app.update_layout()

    assert (outer.winfo_reqwidth(), outer.winfo_reqheight()) == (0, 0)


def test_a_packed_or_gridded_child_does_size_its_parent(app):
    """The other half, so the test above cannot pass by everything being 0."""
    for name, manager in (("p", "pack"), ("g", "grid")):
        outer = tkcurses.Frame(app, name=f"outer{name}", relief="flat")
        inner = tkcurses.Label(outer, name="inner", text="12345")
        getattr(inner, manager)()
        outer.place(x=0, y=0)
        app.update_layout()
        assert (outer.winfo_reqwidth(), outer.winfo_reqheight()) == (5, 1), manager
