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


"""An application to test against, rather than a widget on a bare root.

Every other test in this repo starts from one widget and nothing else. That
is the right shape for asking whether a Listbox scrolls, and the wrong one
for asking whether a Listbox and the Scrollbar beside it agree - which is
where this project's hand-found bugs have actually been.

So the fixtures here build a small application: a root with a real panel
stack, containers inside it, widgets inside those. The helpers below are the
things every module in this package would otherwise repeat - who is under a
cell, what order the panels are in, what a widget's window covers.

``stub_window``/``stack``/``root`` were already copied into at least three
test modules by hand. They live here now.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import tkcurses
from tkcurses import Misc
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

#: The screen every headless fixture pretends to have.
SCREEN = (80, 24)


def stub_window(rect: Rect) -> SimpleNamespace:
    """A window that is only its rectangle. Enough to stack and to measure."""
    return SimpleNamespace(rect=rect)


@pytest.fixture
def stack() -> PanelStack:
    """A panel stack with no curses under it."""
    return PanelStack(window_factory=stub_window, panel_factory=None)


@pytest.fixture
def app(stack, monkeypatch):
    """A root that behaves like a mapped application, without a terminal.

    Mapped and sized, because an unmapped root gives its children no windows
    and every stacking question then has the same empty answer.
    """
    root = Misc()
    root.tk.panels = stack
    root._rect = Rect(0, 0, *SCREEN)
    root._mapped = True
    monkeypatch.setattr(type(root), "_screen_size", lambda self: SCREEN)
    return root


# ------------------------------------------------------------------ helpers


def widget_at(app, x: int, y: int):
    """Who receives a click on this cell.

    The same two steps ``Tk._widget_at`` takes: the panel stack answers first
    because it is the only thing that knows the z-order, and the widget tree's
    geometry answers when there is no panel there. Mirrored rather than called
    because the headless root is a Misc, and ``_widget_at`` is Tk's.

    Keeping this beside the tests is deliberate: when the two disagree, that
    is the bug, and a test that called the implementation could not see it.
    """
    panel = app.tk.panels.panel_at(x, y)
    if panel is not None:
        widget = panel.userptr()
        if isinstance(widget, Misc) and widget.winfo_exists():
            return widget
    return app.winfo_containing(x, y) or app


def through_grab(app, target):
    """Where an event actually lands, once a grab is taken into account.

    ``Tk._through_grab``'s rule, mirrored for the same reason ``widget_at``
    is: the headless root is a Misc, and when routing and the grab disagree
    that *is* the bug, so a test that called the implementation could not
    see it.
    """
    grab = app.tk.grab
    if grab is None or not grab.winfo_exists():
        return target
    if any(widget is grab for widget in target._ancestry()):
        return target
    return grab


def z_order(app) -> list:
    """Every widget with a window, back to front."""
    by_panel = {
        widget._panel: widget
        for widget in app._subtree()
        if getattr(widget, "_panel", None) is not None
    }
    return [by_panel[panel] for panel in app.tk.panels._order if panel in by_panel]


def covers(widget) -> Rect:
    """The screen cells a widget's window actually occupies."""
    return Rect(
        widget.winfo_rootx(),
        widget.winfo_rooty(),
        widget._rect.width,
        widget._rect.height,
    )


def build(app, spec: dict):
    """Make a tree of Frames and Labels from ``{name: {...} | None}``.

    Saves every module below writing the same twenty lines of place() calls.
    A value of None is a leaf Label; a dict is a Frame with those children.
    """
    made = {}

    def add(parent, name, children, x, y, width, height):
        if children is None:
            widget = tkcurses.Label(parent, name=name, text=name)
        else:
            widget = tkcurses.Frame(parent, name=name)
        widget.place(x=x, y=y, width=width, height=height)
        made[name] = widget
        if children:
            for index, (child, grandchildren) in enumerate(children.items()):
                # Narrower than the parent by more than a border, so that
                # "the cell beside the child" is unambiguously the parent's.
                add(widget, child, grandchildren, 1, 1 + index, width - 4, 1)

    for index, (name, children) in enumerate(spec.items()):
        add(app, name, children, 0, index * 8, 30, 7)
    app.update_layout()
    return made
