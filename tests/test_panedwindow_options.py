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

"""A classic PanedWindow's sash, handle and proxy options. TkCurses-gm66.9.

Each rule was measured on Tk 9.0.2 and is cited where it is asserted. Tk's
distances are pixels and these are cells.
"""

from __future__ import annotations

import curses
from types import SimpleNamespace

import pytest

from tkcurses import Frame, Misc, PanedWindow, TclError, ttk
from tkcurses._core.events import MouseEvent
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack


class Window:
    """A curses window that keeps every cell written, with its attribute."""

    def __init__(self, rect):
        self.rect = rect
        self.cells = {}

    def getmaxyx(self):
        return (self.rect.height, self.rect.width)

    def bkgd(self, *args):
        pass

    def erase(self):
        self.cells = {}

    def addstr(self, row, column, text, attribute=0):
        for offset, character in enumerate(text):
            self.cells[(row, column + offset)] = (character, attribute)

    insstr = addstr


@pytest.fixture
def stack():
    return PanelStack(window_factory=Window, panel_factory=None)


@pytest.fixture
def root(stack):
    root = Misc()
    root.tk.panels = stack
    root.tk.screen = SimpleNamespace(
        started=True, size=SimpleNamespace(width=60, height=20)
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    return root


def make(root, cols=41, rows=6, **kw):
    """A paned window ``cols`` by ``rows`` with two ten-cell panes."""
    widget = PanedWindow(root, name="p", **kw)
    widget._allocate(Rect(0, 0, cols, rows))
    widget._map()
    for name in ("a", "b"):
        widget.add(Frame(widget, name=name, width=10, height=3))
    widget.update_layout()
    return widget


def pane(widget, index):
    return widget._paned.slaves()[index]


def cell(widget, row, column):
    return widget._panel.window.cells.get((row, column), (" ", 0))


def column_of(widget, glyph):
    return sorted(
        {x for (_, x), (c, _) in widget._panel.window.cells.items() if c == glyph}
    )


def rows_of(widget, glyph):
    return sorted(
        {y for (y, _), (c, _) in widget._panel.window.cells.items() if c == glyph}
    )


# ------------------------------------------------------------------ options

DEFAULTS = {
    "handlepad": 1,
    "handlesize": 1,
    "height": "",
    "proxybackground": "",
    "proxyborderwidth": 2,
    "proxyrelief": "flat",
    "sashcursor": "",
    "sashpad": 0,
    "sashrelief": "flat",
    "width": "",
}


@pytest.mark.parametrize(("name", "value"), DEFAULTS.items())
def test_the_defaults(root, name, value):
    assert PanedWindow(root).cget(name) == value


def test_opaqueresize_is_on_by_default(root):
    assert PanedWindow(root).cget("opaqueresize")


@pytest.mark.parametrize(
    "name",
    [
        "handlepad",
        "handlesize",
        "sashpad",
        "proxyborderwidth",
        "sashwidth",
        "width",
        "height",
    ],
)
def test_a_negative_distance_is_kept_as_given(root, name):
    """Measured: every one of these reads back -3 after -3."""
    assert PanedWindow(root, **{name: -3}).cget(name) == -3


@pytest.mark.parametrize(
    "name", ["handlepad", "handlesize", "sashpad", "proxyborderwidth", "sashwidth"]
)
def test_a_distance_must_be_one(root, name):
    with pytest.raises(TclError, match='expected screen distance but got "x"'):
        PanedWindow(root, **{name: "x"})


@pytest.mark.parametrize("name", ["width", "height"])
def test_width_and_height_name_the_empty_string_too(root, name):
    with pytest.raises(TclError, match='expected screen distance or "" but got "x"'):
        PanedWindow(root, **{name: "x"})


@pytest.mark.parametrize("name", ["width", "height"])
def test_width_and_height_go_back_to_empty(root, name):
    widget = PanedWindow(root, **{name: 30})
    widget.configure(**{name: ""})
    assert widget.cget(name) == ""


def test_opaqueresize_is_a_boolean(root):
    with pytest.raises(TclError, match='expected boolean value but got "maybe"'):
        PanedWindow(root, opaqueresize="maybe")
    assert PanedWindow(root, opaqueresize="no").cget("opaqueresize") == 0


def test_sashrelief_is_a_relief_and_not_empty(root):
    with pytest.raises(TclError, match='bad relief "bogus"'):
        PanedWindow(root, sashrelief="bogus")
    with pytest.raises(TclError, match='ambiguous relief ""'):
        PanedWindow(root, sashrelief="")


def test_proxyrelief_may_be_empty(root):
    assert PanedWindow(root, proxyrelief="").cget("proxyrelief") == ""
    with pytest.raises(TclError, match='ambiguous relief "s"'):
        PanedWindow(root, proxyrelief="s")


def test_proxybackground_is_a_colour(root):
    with pytest.raises(TclError, match='unknown color name "nocolour"'):
        PanedWindow(root, proxybackground="nocolour")
    assert PanedWindow(root, proxybackground="red").cget("proxybackground") == "red"


def test_sashcursor_is_kept_for_the_program(root):
    assert PanedWindow(root, sashcursor="sb_h_double_arrow").cget("sashcursor") == (
        "sb_h_double_arrow"
    )


# ------------------------------------------------------------- the sash span


def test_one_cell_between_panes_by_default(root):
    widget = make(root)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 1


def test_sashpad_goes_either_side(root):
    """Measured: sashpad 5 put the second pane 18 past the first where it had
    been 8 - five each side."""
    widget = make(root, sashpad=2)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 5


def test_the_padding_answers_as_the_sash(root):
    """Measured: every pixel from one pane's edge to the next is the sash."""
    widget = make(root, sashpad=2)
    first = pane(widget, 0).winfo_width()
    for x in range(first, first + 5):
        assert widget.identify(x, 1) == (0, "sash"), x
    assert widget.identify(first + 5, 1) == ()
    assert widget.identify(first - 1, 1) == ()


def test_sashwidth_widens_the_sash(root):
    widget = make(root, sashwidth=3)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 3


def test_a_wider_handle_widens_the_sash(root):
    """Measured: sashwidth 4 under handlesize 8 left 8 between the panes."""
    widget = make(root, handlesize=3)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 3


def test_a_hidden_handle_does_not(root):
    widget = make(root, handlesize=3, showhandle=False)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 1


def test_a_narrower_handle_does_not(root):
    widget = make(root, sashwidth=3, handlesize=1)
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 3


@pytest.mark.parametrize(("option", "value"), [("sashpad", -3), ("sashwidth", 0)])
def test_the_sash_is_never_less_than_one_cell(root, option, value):
    widget = make(root, **{option: value})
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 1


def test_changing_the_span_relays_the_panes_out(root):
    widget = make(root)
    widget.configure(sashpad=1)
    widget.update_layout()
    assert pane(widget, 1).winfo_x() - pane(widget, 0).winfo_width() == 3


def test_sash_coord_names_the_line_not_the_padding(root):
    """Measured: a 4-pixel sash under an 8-pixel handle after a 100-pixel
    pane is at 102, and with sashpad 5 at 107."""
    widget = make(root, sashpad=2)
    assert widget.sash_coord(0)[0] == pane(widget, 0).winfo_width() + 2
    widget = make(root, sashwidth=1, handlesize=3)
    assert widget.sash_coord(0)[0] == pane(widget, 0).winfo_width() + 1


@pytest.mark.parametrize("kw", [{}, {"sashpad": 2}, {"handlesize": 3}])
def test_sash_place_reads_back_from_sash_coord(root, kw):
    """Measured: sash_place at 150 answered 150, padded or not."""
    widget = make(root, **kw)
    widget.sash_place(0, 12, 0)
    assert widget.sash_coord(0)[0] == 12


def test_a_vertical_window_pads_rows(root):
    widget = PanedWindow(root, name="v", orient="vertical", sashpad=1)
    widget._allocate(Rect(0, 0, 10, 21))
    widget._map()
    for name in ("a", "b"):
        widget.add(Frame(widget, name=name, width=5, height=5))
    widget.update_layout()
    first, second = widget._paned.slaves()
    assert second.winfo_y() - first.winfo_height() == 3


def three(root, **kw):
    widget = PanedWindow(root, name="p3", **kw)
    widget._allocate(Rect(0, 0, 50, 6))
    widget._map()
    for name in ("a", "b", "c"):
        widget.add(Frame(widget, name=name, width=10, height=3))
    widget.update_layout()
    return widget


def test_every_sash_takes_its_span(root):
    widget = three(root, sashpad=1)
    a, b, c = widget._paned.slaves()
    assert b.winfo_x() == a.winfo_width() + 3
    assert c.winfo_x() == b.winfo_x() + b.winfo_width() + 3
    assert widget.sash_coord(1)[0] == b.winfo_x() + b.winfo_width() + 1


def test_the_panes_share_what_the_sashes_leave(root):
    widget = three(root, sashpad=1)
    assert sum(child.winfo_width() for child in widget._paned.slaves()) == 50 - 2 * 3


def test_placing_a_later_sash_counts_the_spans_before_it(root):
    widget = three(root, sashpad=1)
    widget.sash_place(1, 30, 0)
    assert widget.sash_coord(1)[0] == 30
    a, b, _ = widget._paned.slaves()
    assert a.winfo_width() + 3 + b.winfo_width() + 1 == 30


def test_the_span_is_in_the_request(root):
    widget = make(root, sashpad=2)
    assert widget.winfo_reqwidth() == 10 + 5 + 10


# ------------------------------------------------------- width and height


def test_width_and_height_fix_the_request(root):
    """Measured: width 300 over two 100-pixel panes asked for 300."""
    widget = make(root, width=30, height=4)
    assert (widget.winfo_reqwidth(), widget.winfo_reqheight()) == (30, 4)


def test_either_alone(root):
    widget = make(root, width=30)
    assert widget.winfo_reqwidth() == 30
    assert widget.winfo_reqheight() == 3, "the panes' own height"


def test_empty_gives_the_panes_size_back(root):
    """Measured: "" gave the panes' 218 back."""
    widget = make(root, width=30)
    widget.configure(width="")
    widget.update_layout()
    assert widget.winfo_reqwidth() == 21


def test_ttk_still_sizes_to_its_panes(root):
    widget = ttk.Panedwindow(root, name="t")
    for name in ("a", "b"):
        widget.add(Frame(widget, name=name, width=10, height=3))
    widget.update_layout()
    assert widget.winfo_reqwidth() == 21


# ------------------------------------------------------------------ drawing


def test_the_handle_is_handlepad_cells_down_the_sash(root):
    """Tk's handle is at -handlepad from the sash's start, not its middle."""
    widget = make(root)
    assert rows_of(widget, "┃") == [1]
    assert column_of(widget, "┃") == [widget.sash_coord(0)[0]]


def test_handlepad_moves_it(root):
    widget = make(root, handlepad=3)
    assert rows_of(widget, "┃") == [3]


def test_handlesize_is_its_length_and_its_width(root):
    widget = make(root, handlesize=2)
    start = pane(widget, 0).winfo_width()
    assert rows_of(widget, "┃") == [1, 2]
    assert column_of(widget, "┃") == [start, start + 1]


def test_the_line_fills_sashwidth_in_the_middle_of_the_span(root):
    widget = make(root, sashwidth=1, handlesize=3, showhandle=True)
    start = pane(widget, 0).winfo_width()
    assert column_of(widget, "│") == [start + 1]
    assert column_of(widget, "┃") == [start, start + 1, start + 2]


def test_the_handle_is_inside_the_padding(root):
    widget = make(root, sashpad=1)
    assert column_of(widget, "┃") == [widget.sash_coord(0)[0]]


def test_nothing_is_drawn_in_the_padding(root):
    widget = make(root, sashpad=1)
    start = pane(widget, 0).winfo_width()
    assert column_of(widget, "│") == [start + 1]
    assert cell(widget, 3, start)[0] == " "


def test_no_handle_when_showhandle_is_off(root):
    widget = make(root, showhandle=False)
    assert rows_of(widget, "┃") == []


def test_a_vertical_handle_is_handlepad_cells_along(root):
    widget = PanedWindow(root, name="v", orient="vertical", handlepad=2)
    widget._allocate(Rect(0, 0, 10, 13))
    widget._map()
    for name in ("a", "b"):
        widget.add(Frame(widget, name=name, width=5, height=3))
    widget.update_layout()
    cells = widget._panel.window.cells
    assert sorted(x for (_, x), (c, _) in cells.items() if c == "━") == [2]


def test_a_sunken_sash_is_dim(root):
    widget = make(root, sashrelief="sunken")
    x = widget.sash_coord(0)[0]
    assert cell(widget, 3, x)[1] & curses.A_DIM


def test_a_raised_sash_is_not(root):
    widget = make(root, sashrelief="raised")
    x = widget.sash_coord(0)[0]
    assert not cell(widget, 3, x)[1] & curses.A_DIM


# -------------------------------------------------------------------- proxy


def drag(widget, to, *, release=True):
    x, y = widget.sash_coord(0)
    widget._handle(MouseEvent(button=1, state="pressed", x=x, y=y))
    widget._handle(MouseEvent(button=0, state="drag", x=to, y=y))
    if release:
        widget._handle(MouseEvent(button=1, state="released", x=to, y=y))


def test_an_opaque_drag_moves_the_panes_with_the_pointer(root):
    widget = make(root)
    drag(widget, 6, release=False)
    assert pane(widget, 0).winfo_width() == 6
    assert widget._proxy_panel is None


def test_without_opaqueresize_the_panes_wait(root):
    """tk::panedwindow::DragSash places the proxy, not the sash."""
    widget = make(root, opaqueresize=False)
    before = pane(widget, 0).winfo_width()
    drag(widget, 6, release=False)
    assert pane(widget, 0).winfo_width() == before
    assert widget._proxy_panel is not None
    assert widget._proxy_panel.rect.x == 6


def test_the_proxy_is_the_length_of_the_division(root):
    widget = make(root, opaqueresize=False)
    drag(widget, 6, release=False)
    rect = widget._proxy_panel.rect
    assert (rect.y, rect.width, rect.height) == (0, 1, 6)


def test_the_proxy_follows_the_pointer(root):
    widget = make(root, opaqueresize=False)
    drag(widget, 6, release=False)
    panel = widget._proxy_panel
    widget._handle(MouseEvent(button=0, state="drag", x=9, y=1))
    assert widget._proxy_panel is panel, "moved, not made again"
    assert panel.rect.x == 9


def test_the_release_moves_the_sash_to_the_proxy(root, stack):
    """tk::panedwindow::ReleaseSash: proxy coord, proxy forget, sash place."""
    widget = make(root, opaqueresize=False)
    drag(widget, 6)
    assert pane(widget, 0).winfo_width() == 6
    assert widget._proxy_panel is None
    assert [panel for panel in stack if panel.userptr() is widget] == [widget._panel]


def test_the_proxy_stays_inside_the_window(root):
    widget = make(root, opaqueresize=False)
    drag(widget, 90, release=False)
    assert widget._proxy_panel.rect.x == 40


def test_the_proxy_is_drawn_as_the_sash(root):
    widget = make(root, opaqueresize=False, proxyrelief="sunken")
    drag(widget, 6, release=False)
    cells = widget._proxy_panel.window.cells
    assert {c for c, _ in cells.values()} == {"│"}
    assert len(cells) == 6
    assert all(attribute & curses.A_DIM for _, attribute in cells.values())


def test_destroying_the_window_takes_the_proxy_down(root, stack):
    widget = make(root, opaqueresize=False)
    drag(widget, 6, release=False)
    panel = widget._proxy_panel
    widget.destroy()
    assert panel not in stack
