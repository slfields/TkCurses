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
#
# Portions follow logic in the Tcl and Tk library scripts, each named beside
# the code that follows it. Tcl and Tk are copyright the Regents of the
# University of California, Sun Microsystems, Inc., Scriptics Corporation,
# ActiveState Corporation, Apple Inc. and other parties, and are used under
# the Tcl/Tk licence; see THIRD_PARTY_NOTICES.md.

"""TkCurses - a tkinter-compatible API layer that renders to curses.

TkCurses mirrors tkinter's module structure and public names so that
tkinter-style application code can run in a terminal with no Tk, Tcl, or
graphical display present. Widget calls are translated into curses and
curses.panel operations against a character-cell screen.

This module is the counterpart to ``tkinter/__init__.py`` and holds the core
widget set (Tk, Toplevel, Frame, Label, Button, Entry, ...). Internal
machinery lives under :mod:`tkcurses._core`.

See ARCHITECTURE.md for the full specification.
"""

from __future__ import annotations

import contextlib

# Imported under a private name, and it matters. The compatibility module is
# tkcurses.curses, and importing it makes Python bind that submodule as the
# attribute `curses` on this package - which is this module's own global
# namespace. A plain `import curses` here would be silently replaced by the
# facade the moment anybody imported it, and every reference below would
# resolve against the wrong module. Measured, not theorised: it clobbers.
import curses as _curses
import functools
import inspect
import itertools
import math
import os
import re
import sys
import time
import traceback
import weakref
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from tkcurses._core.application import Application
from tkcurses._core.attributes import (
    BorderStyle,
    for_state,
    from_font,
    style_for_relief,
    with_colors,
)
from tkcurses._core.bindings import (
    EventPattern,
    PatternSequence,
    parse_sequence,
    pattern_for_event,
)
from tkcurses._core.canvas import (
    bbox_of,
    compose,
    filled_oval_pixels,
    filled_polygon_pixels,
    filled_rectangle_pixels,
    line_pixels,
    oval_pixels,
    polygon_pixels,
    rectangle_pixels,
)
from tkcurses._core.clipboard import CLIPBOARD, PRIMARY
from tkcurses._core.colors import (
    ColorDepth,
    ColorManager,
    palette_rgb,
    parse_color,
    rgb_for,
    rgb_of,
    truecolor_hinted,
)
from tkcurses._core.config import TkCursesConfig
from tkcurses._core.direct import DirectPainter
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.editing import TextField, run_end, run_start
from tkcurses._core.errors import TclError, TkCursesError
from tkcurses._core.events import (
    MOD_CTRL,
    MOD_SHIFT,
    KeyEvent,
    MouseEvent,
    ResizeEvent,
)
from tkcurses._core.events import Event as CoreEvent
from tkcurses._core.geometry import (
    BORDER_WIDTH,
    Insets,
    Rect,
    Size,
    clamp,
    clip_text,
    content_rect,
    parse_pad,
    parse_single_pad,
)
from tkcurses._core.grid import (
    GridLayout,
    GridOptions,
    LineConfig,
    parse_sticky,
)
from tkcurses._core.images import (
    ROWS_PER_CELL,
    BitmapImage,
    Image,
    PhotoImage,
)
from tkcurses._core.input import InputHandler
from tkcurses._core.menus import (
    # The GLYPH drawn for a submenu, not tkinter's CASCADE, which is the
    # string 'cascade' naming an entry TYPE. Two different things with one
    # name: importing tkinter's over this one would have drawn "File
    # cascade" where the arrow belongs.
    CASCADE as CASCADE_GLYPH,
)
from tkcurses._core.menus import (
    COLUMN_GAP,
    MenuEntry,
    Placed,
    accelerator_sequence,
    lay_out,
    measure_entries,
    place_popup,
    visible_window,
)
from tkcurses._core.option_names import WIDGET_CLASSES, database_names
from tkcurses._core.pack import FILLS, SIDES, PackLayout, PackOptions, parse_anchor
from tkcurses._core.paned import SASH_WIDTH, PanedLayout, PaneOptions
from tkcurses._core.panels import PanelStack
from tkcurses._core.place import BORDERMODES, PlaceLayout, PlaceOptions
from tkcurses._core.screen import (
    TERMINALS_OWN,
    CursesScreen,
    CursorStyle,
    TerminalCursor,
)
from tkcurses._core.system_clipboard import ask_terminal_for_osc52, choose_route
from tkcurses._core.text import align_offset, measure, wrap, wrap_spans
from tkcurses._core.textbuffer import Index, TextBuffer
from tkcurses._core.textlayout import (
    WORDPROCESSOR,
    TabStops,
    char_at,
    column_of,
    parse_tabs,
    render,
)

# Every constant tkinter's own module defines, re-exported so that a
# star-import puts the same names in scope. tkinter does this with
# ``from tkinter.constants import *``; the list is spelled out here because
# ``tkcurses.constants`` also carries curses names - A_BOLD, KEY_UP and
# friends - which tkinter has no equivalent for and which a star-import must
# therefore NOT bind. A program written against tkinter should not acquire
# names from us that tkinter would not have given it.
#
# A widget program stopped at import on `NameError: name 'RIGHT' is not
# defined` while every value behind those names already worked, which is
# TkCurses-bm8. Kept honest by a test that compares this against
# tkinter.constants itself rather than a copy of the list.
from tkcurses.constants import (
    ACTIVE,
    ALL,
    ANCHOR,
    ARC,
    BASELINE,
    BEVEL,
    BOTH,
    BOTTOM,
    BROWSE,
    BUTT,
    CASCADE,
    CENTER,
    CHAR,
    CHECKBUTTON,
    CHORD,
    COMMAND,
    CURRENT,
    DISABLED,
    DOTBOX,
    END,
    EW,
    EXTENDED,
    FALSE,
    FIRST,
    FLAT,
    GROOVE,
    HIDDEN,
    HORIZONTAL,
    INSERT,
    INSIDE,
    LAST,
    LEFT,
    MITER,
    MOVETO,
    MULTIPLE,
    NE,
    NO,
    NONE,
    NORMAL,
    NS,
    NSEW,
    NUMERIC,
    NW,
    OFF,
    ON,
    OUTSIDE,
    PAGES,
    PIESLICE,
    PROJECTING,
    RADIOBUTTON,
    RAISED,
    RIDGE,
    RIGHT,
    ROUND,
    SCROLL,
    SE,
    SEL,
    SEL_FIRST,
    SEL_LAST,
    SEPARATOR,
    SINGLE,
    SOLID,
    SUNKEN,
    SW,
    TOP,
    TRUE,
    UNDERLINE,
    UNITS,
    VERTICAL,
    WORD,
    YES,
    E,
    N,
    S,
    W,
    X,
    Y,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from tkcurses._core.layout import Layout
    from tkcurses._core.panels import Panel

__version__ = "0.1.0"
__author__ = "Scott L. Fields"
__copyright__ = "Copyright (C) 2026 Scott L. Fields"
__license__ = "GPL-3.0-only"

#: The notice the GNU GPL asks an interactive program to show. A library
#: cannot show it itself - it has no startup of its own and no business
#: writing over an application's screen - so it is offered here for a
#: program that wants to, which is what ``tkcurses-demo`` does.
NOTICE = f"""\
TkCurses {__version__}  {__copyright__}
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under the terms of the GNU General Public License version 3.
See <https://www.gnu.org/licenses/gpl-3.0.html> for the full terms."""

#: The constants come first, as one block, because they are a set rather
#: than a list of individual decisions - see the import above.
__all__ = [
    "ACTIVE",
    "ALL",
    "ANCHOR",
    "ARC",
    "BASELINE",
    "BEVEL",
    "BOTH",
    "BOTTOM",
    "BROWSE",
    "BUTT",
    "CASCADE",
    "CENTER",
    "CHAR",
    "CHECKBUTTON",
    "CHORD",
    "COMMAND",
    "CURRENT",
    "DISABLED",
    "DOTBOX",
    "END",
    "EW",
    "EXTENDED",
    "FALSE",
    "FIRST",
    "FLAT",
    "GROOVE",
    "HIDDEN",
    "HORIZONTAL",
    "INSERT",
    "INSIDE",
    "LAST",
    "LEFT",
    "MITER",
    "MOVETO",
    "MULTIPLE",
    "NE",
    "NO",
    "NONE",
    "NORMAL",
    "NOTICE",
    "NS",
    "NSEW",
    "NUMERIC",
    "NW",
    "OFF",
    "ON",
    "OUTSIDE",
    "PAGES",
    "PIESLICE",
    "PROJECTING",
    "RADIOBUTTON",
    "RAISED",
    "RIDGE",
    "RIGHT",
    "ROUND",
    "SCROLL",
    "SE",
    "SEL",
    "SEL_FIRST",
    "SEL_LAST",
    "SEPARATOR",
    "SINGLE",
    "SOLID",
    "SUNKEN",
    "SW",
    "TOP",
    "TRUE",
    "UNDERLINE",
    "UNITS",
    "VERTICAL",
    "WORD",
    "YES",
    "BaseWidget",
    "BitmapImage",
    "BooleanVar",
    "Button",
    "Canvas",
    "Checkbutton",
    "DoubleVar",
    "E",
    "Entry",
    "Event",
    "Frame",
    "Grid",
    "Image",
    "IntVar",
    "Label",
    "LabelFrame",
    "Listbox",
    "Menu",
    "Menubutton",
    "Message",
    "Misc",
    "N",
    "NoDefaultRoot",
    "OptionMenu",
    "Pack",
    "PanedWindow",
    "PhotoImage",
    "Place",
    "Radiobutton",
    "S",
    "Scale",
    "Scrollbar",
    "Spinbox",
    "StringVar",
    "TclError",
    "Text",
    "Tk",
    "TkCursesError",
    "Toplevel",
    "Variable",
    "W",
    "Widget",
    "Wm",
    "X",
    "XView",
    "Y",
    "YView",
    "__author__",
    "__copyright__",
    "__license__",
    "__version__",
]

#: Cells per inch, used by ``winfo_pixels`` to convert screen distances such
#: as ``"2i"``. A character cell is the closest thing a terminal has to a
#: pixel, and 10 columns by 6 rows to the inch is the classic teletype metric
#: that terminal emulators still approximate.
_CELLS_PER_INCH = 10.0

#: Suffixes tkinter accepts on a screen distance, in inches.
_DISTANCE_UNITS: dict[str, float] = {
    "i": 1.0,
    "c": 1 / 2.54,
    "m": 1 / 25.4,
    "p": 1 / 72.0,
}

#: Size a Toplevel takes when neither the application nor Wm has asked for
#: one. Tk's default is 200x200 pixels, which is about this many cells at
#: a usual font size, and small enough to fit an 80x24 terminal with room
#: to spare.
_DEFAULT_TOPLEVEL_SIZE = Size(30, 10)

#: Strings ``getboolean`` accepts, exactly as Tcl does.
_TRUE = frozenset({"1", "yes", "true", "on", "y", "t"})
_FALSE = frozenset({"0", "no", "false", "off", "n", "f"})


class Event:
    """An event delivered to a binding callback.

    tkinter passes one object with a fixed set of attributes, whatever kind of
    event it describes, and application code reads whichever of them apply.
    That shape is kept here so existing handlers work unchanged.

    Unset fields hold ``0`` or ``""`` rather than tkinter's ``"??"`` sentinel.
    Code that tests a field it should not have read gets a falsy value instead
    of a string that crashes arithmetic two lines later, and nothing that reads
    the right field for its event type can tell the difference.

    Attributes:
        widget: The widget the binding fired on.
        type: Event type name, such as ``Key`` or ``ButtonPress``.
        time: When it happened, in seconds since the epoch.
        num: Mouse button number.
        keycode: Raw key code from curses.
        keysym: Key name, such as ``Return`` or ``a``.
        keysym_num: Numeric form of the keysym, for printable keys.
        char: The character the key produced, empty if it produced none.
        state: Modifier flags, as the ``MOD_*`` values in
            :mod:`tkcurses._core.events`. tkinter reports X11's bitmask here;
            the meanings are the same but the bit positions are not.
        x, y: Position within the widget, in cells.
        x_root, y_root: Position on the screen, in cells.
        width, height: New size, for ``<Configure>``.
        delta: Scroll amount, positive for up.
    """

    __slots__ = (
        "char",
        "delta",
        "height",
        "keycode",
        "keysym",
        "keysym_num",
        "num",
        "state",
        "time",
        "type",
        "widget",
        "width",
        "x",
        "x_root",
        "y",
        "y_root",
    )

    def __init__(self, **fields: Any) -> None:
        """Create an event, defaulting every field the caller does not give."""
        self.widget: Any = None
        self.type: str = "??"
        self.time: float = time.time()
        self.num: int = 0
        self.keycode: int = 0
        self.keysym: str = ""
        self.keysym_num: int = 0
        self.char: str = ""
        self.state: int = 0
        self.x: int = 0
        self.y: int = 0
        self.x_root: int = 0
        self.y_root: int = 0
        self.width: int = 0
        self.height: int = 0
        self.delta: int = 0
        for name, value in fields.items():
            if name not in self.__slots__:
                raise TypeError(f"Event has no field {name!r}")
            setattr(self, name, value)

    def __repr__(self) -> str:
        """Show the fields that carry something, as tkinter's repr does."""
        shown = {
            name: getattr(self, name)
            for name in self.__slots__
            if name not in ("type", "time") and getattr(self, name)
        }
        fields = " ".join(f"{name}={value!r}" for name, value in shown.items())
        return f"<{self.type} event{' ' if fields else ''}{fields}>"

    @classmethod
    def _from_core(cls, core: CoreEvent, widget: Misc) -> Event:
        """Build the tkinter-facing event for one internal input event."""
        event = cls(widget=widget, time=core.time)
        if isinstance(core, KeyEvent):
            event.type = "Key"
            event.keycode = core.keycode
            event.keysym = core.keysym
            event.char = core.char
            event.state = core.modifiers
            event.keysym_num = ord(core.char) if len(core.char) == 1 else 0
            event.x_root, event.y_root = widget.tk.pointer
        elif isinstance(core, MouseEvent):
            event.type = _MOUSE_EVENT_TYPES[core.state]
            event.num = core.button
            event.state = core.modifiers
            event.x_root, event.y_root = core.x, core.y
            event.x = core.x - widget.winfo_rootx()
            event.y = core.y - widget.winfo_rooty()
            # Curses reports the wheel as buttons 4 and 5, as X11 does, so
            # delta is derived rather than reported.
            event.delta = {4: 1, 5: -1}.get(core.button, 0)
        elif isinstance(core, ResizeEvent):
            event.type = "Configure"
            event.width = core.width
            event.height = core.height
        return event


def _focus_next(event: Event) -> str:
    """Move the focus to the next widget that will take it."""
    _move_focus(event.widget, forwards=True)
    return "break"


def _focus_previous(event: Event) -> str:
    """Move the focus to the previous widget that will take it."""
    _move_focus(event.widget, forwards=False)
    return "break"


def _move_focus(widget: Misc, *, forwards: bool) -> None:
    """Hand the focus on, starting from wherever it currently is.

    From the widget the event reached rather than from the focus, because a
    key pressed with nothing focused still has to start somewhere.
    """
    current = widget.focus_get() or widget
    target = current.tk_focusNext() if forwards else current.tk_focusPrev()
    if target is not None:
        target.focus_set()


#: tkinter's event type names for each mouse state the input layer reports.
_MOUSE_EVENT_TYPES: dict[str, str] = {
    "pressed": "ButtonPress",
    "clicked": "ButtonPress",
    "double": "ButtonPress",
    "triple": "ButtonPress",
    "released": "ButtonRelease",
    "drag": "Motion",
    "motion": "Motion",
}


def _given(cnf: dict[str, Any] | None, kw: dict[str, Any]) -> dict[str, Any]:
    """Options as tkinter reads them: ``cnf``, then the keywords over it.

    **An option given as None is left out**, as if it had not been given -
    tkinter's ``Misc._options`` skips it, so ``configure(text=None)`` leaves
    the text alone rather than clearing it. Measured on Tk 9.0.2 for
    constructors, ``configure``, ``w[key] = None``, canvas items, menu
    entries, text tags, panes, tabs, the Treeview's methods, ``Style`` and
    all three geometry managers. Here None was stored, and ``cget`` answered
    it back (TkCurses-bx5b).
    """
    return {
        key: value for key, value in {**(cnf or {}), **kw}.items() if value is not None
    }


#: Tk's insertion-cursor options, on every widget with an insert point: Entry
#: and Spinbox, Text, and Canvas's text items. Tk 9.0.2's defaults, except the
#: colour, which is "" as every colour here is - the terminal's own. What they
#: do is ``BaseWidget._cursor_style``. TkCurses-gm66.2.
_INSERT_CURSOR_OPTIONS: dict[str, Any] = {
    "insertbackground": "",
    "insertborderwidth": 0,
    "insertofftime": 300,
    "insertontime": 600,
    "insertwidth": 2,
}

#: Tk draws its cursor this many pixels wide unless told otherwise. A width
#: left at it asks nothing of the terminal; see ``BaseWidget._cursor_style``.
_TK_INSERT_WIDTH = _INSERT_CURSOR_OPTIONS["insertwidth"]


class _TerminalsOwn(str):
    """The ``""`` a colour option starts at, told apart from a ``""`` given.

    It reads back, compares and prints as ``""``. Text's
    ``inactiveselectbackground`` needs the difference: Tk's default is a grey,
    so the selection stays visible without the focus, and a program that sets
    ``""`` is asking for it to vanish. Here the default is the terminal's own
    look, which is also ``""``. ``cget`` hands this object back, so
    ``configure(option=cget(option))`` keeps the default. TkCurses-gm66.3.
    """

    __slots__ = ()


#: Tk's selection options, on every widget that has a selection: Entry and
#: Spinbox, Listbox, Text, and Canvas's text items. Tk 9.0.2's defaults except
#: the colours, "" here: a selection nobody coloured is reversed, as it always
#: was. See ``BaseWidget._selection_attribute``. TkCurses-gm66.3.
_SELECTION_OPTIONS: dict[str, Any] = {
    "selectbackground": "",
    "selectborderwidth": 0,
    "selectforeground": "",
}

#: Text's select colours and its ``sel`` tag's are one setting: measured on Tk
#: 9.0.2, configuring either changes what the other reads back.
_SELECTION_TAG_OPTIONS = {
    "selectbackground": "background",
    "selectforeground": "foreground",
}
_SELECTION_WIDGET_OPTIONS = {
    tag: widget for widget, tag in _SELECTION_TAG_OPTIONS.items()
}

#: The colours Tk gives a label or button for its active and disabled states.
#: Tk 9.0.2's defaults are real colours; these are "", the look the states
#: had before: reversed and dimmed. See ``BaseWidget._in_state``.
#: TkCurses-gm66.4.
_STATE_COLOUR_OPTIONS: dict[str, Any] = {
    "activebackground": "",
    "activeforeground": "",
    "disabledforeground": "",
}

_TCL_INTEGER = re.compile(r"\s*[+-]?\d+\s*")


def _tcl_integer(widget: Any, value: Any) -> int:
    """An integer option, refused as Tk refuses it. Measured on Tk 9.0.2."""
    del widget
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str) and _TCL_INTEGER.fullmatch(value):
        return int(value)
    raise TclError(f'expected integer but got "{value}"')


def _as_int(value: Any, otherwise: int) -> int:
    """An integer option as stored, which the option database leaves a string."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return otherwise


def _screen_distance(widget: Any, value: Any) -> int:
    """A size that cannot go below zero: Tk stores -3 as 0, measured.

    Suffixed distances - ``2p``, ``1c`` - are refused, as everywhere here
    (TkCurses-2qo).
    """
    del widget
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        raise TclError(f'expected screen distance but got "{value}"') from None
    return max(0, number)


def _colour_or_terminals(widget: Any, value: Any) -> Any:
    """A colour, or "" for the terminal's own. Tk refuses "", and has no such
    thing as the terminal's colour to give it."""
    if value == "":
        return value
    try:
        widget.winfo_rgb(str(value))
    except (TclError, ValueError):
        raise TclError(f'unknown color name "{value}"') from None
    return value


def _tcl_boolean(widget: Any, value: Any) -> int:
    """A boolean option, answered as Tk answers it: ``yes`` reads back 1."""
    try:
        return int(widget.getboolean(value))
    except TclError:
        raise TclError(f'expected boolean value but got "{value}"') from None


def _insert_unfocussed(widget: Any, value: Any) -> str:
    """``hollow``, ``none`` or ``solid``, by any unique prefix, as Tk takes it."""
    del widget
    choices = ("hollow", "none", "solid")
    text = str(value)
    matches = [choice for choice in choices if text and choice.startswith(text)]
    if len(matches) != 1:
        raise TclError(f'bad insertunfocussed "{text}": must be hollow, none, or solid')
    return matches[0]


_RELIEFS = ("flat", "groove", "raised", "ridge", "solid", "sunken")


def _choose_relief(value: Any, choices: str) -> str:
    """A relief by its name or any unique prefix, as ``Tk_GetRelief`` takes it.

    Case matters and spaces are not stripped: Tk refuses ``RAISED`` and
    `` raised``, measured on 9.0.2.
    """
    text = str(value)
    if text in _RELIEFS:
        return text
    matches = [relief for relief in _RELIEFS if relief.startswith(text)]
    if len(matches) == 1 and text:
        return matches[0]
    problem = "bad" if not matches else "ambiguous"
    raise TclError(f'{problem} relief "{text}": must be {choices}')


def _relief(widget: Any, value: Any) -> str:
    """A relief, which may not be empty."""
    del widget
    return _choose_relief(value, "flat, groove, raised, ridge, solid, or sunken")


def _relief_or_none(widget: Any, value: Any) -> str:
    """A relief, or "" for none: ``overrelief``, whose "" means no change."""
    del widget
    if value == "":
        return ""
    return _choose_relief(value, 'flat, groove, raised, ridge, solid, sunken, or ""')


def _signed_distance(widget: Any, value: Any) -> int:
    """A size Tk keeps below zero as given: ``sliderlength`` and
    ``activeborderwidth`` read back -5 after -5, measured. What is drawn
    treats one as its smallest instead."""
    del widget
    try:
        return round(float(value))
    except (TypeError, ValueError):
        raise TclError(f'expected screen distance but got "{value}"') from None


def _element_borderwidth(widget: Any, value: Any) -> Any:
    """A size, or "" for the scrollbar's own ``borderwidth``. Tk reads any
    negative width back as "", measured."""
    if value == "":
        return ""
    distance = _signed_distance(widget, value)
    return "" if distance < 0 else distance


def _part_relief(relief: Any) -> int:
    """How a relief shows on a part one cell deep: a slider, an arrow, an entry.

    There are no edges to draw it with, so only the relief Tk's bindings put
    on a part while it is held, ``sunken``, is shown, and it is dim, as a
    sunken border is. The rest draw the part as it was. TkCurses-gm66.5.
    """
    return _curses.A_DIM if str(relief) == SUNKEN else _curses.A_NORMAL


#: Options whose values are checked, and stored as Tk would store them. Most
#: options here are not: a colour or a relief is taken as given and resolved
#: when drawn. These are checked because they reach the terminal itself.
_OPTION_VALUES: dict[str, Callable[[Any, Any], Any]] = {
    "activebackground": _colour_or_terminals,
    "activeborderwidth": _signed_distance,
    "activeforeground": _colour_or_terminals,
    "activerelief": _relief,
    "blockcursor": _tcl_boolean,
    "buttonbackground": _colour_or_terminals,
    "buttondownrelief": _relief,
    "buttonuprelief": _relief,
    "disabledbackground": _colour_or_terminals,
    "disabledforeground": _colour_or_terminals,
    "elementborderwidth": _element_borderwidth,
    "inactiveselectbackground": _colour_or_terminals,
    "insertbackground": _colour_or_terminals,
    "insertborderwidth": _screen_distance,
    "insertofftime": _tcl_integer,
    "insertontime": _tcl_integer,
    "insertunfocussed": _insert_unfocussed,
    "insertwidth": _screen_distance,
    "jump": _tcl_boolean,
    "maxundo": _tcl_integer,
    "offrelief": _relief,
    "overrelief": _relief_or_none,
    "readonlybackground": _colour_or_terminals,
    "repeatdelay": _tcl_integer,
    "repeatinterval": _tcl_integer,
    "selectbackground": _colour_or_terminals,
    "selectborderwidth": _screen_distance,
    "selectcolor": _colour_or_terminals,
    "selectforeground": _colour_or_terminals,
    "sliderlength": _signed_distance,
    "spacing1": _screen_distance,
    "spacing2": _screen_distance,
    "spacing3": _screen_distance,
    "sliderrelief": _relief,
    "troughcolor": _colour_or_terminals,
}


def _menubar_of(window: Any) -> Menu | None:
    """The Menu a window's ``menu`` option names, or None for no menubar.

    Tk takes the menu as a widget or as its path name, and ``""`` for none -
    which is also what ``cget("menu")`` answers by default, and how a program
    removes a menubar (TkCurses-un8i: it crashed here). Measured on Tk 9.0.2,
    the name is not checked when it is set: one that names nothing, or names a
    widget that is not a menu, is stored as given, and no bar is shown.
    """
    value = getattr(window, "_options", {}).get("menu")
    if isinstance(value, str):
        if not value:
            return None
        try:
            value = window.nametowidget(value)
        except KeyError:
            return None
    if isinstance(value, Menu) and value.winfo_exists():
        return value
    return None


def _answering_queries(method: Callable[..., Any]) -> Callable[..., Any]:
    """``method`` as a ``configure`` that also answers ``configure("name")``.

    See :meth:`Misc.__init_subclass__`, which applies it.
    """

    @functools.wraps(method)
    def configure(self: Misc, cnf: Any = None, **kw: Any) -> Any:
        if isinstance(cnf, str):
            return self._configure_query(cnf)
        if (cnf or kw) and not _given(cnf, kw):
            # Options given, every one None: tkinter drops them all and sets
            # nothing - it does not fall through to listing them, which is
            # what an empty call means. Measured, configure(text=None) is None.
            return None
        return method(self, cnf, **kw)

    configure._answers_queries = True  # type: ignore[attr-defined]
    return configure


class Misc:
    """Behaviour shared by every widget: bindings, focus, timers, queries.

    tkinter's ``Misc`` is a mixin over a Tcl interpreter handle. Here the
    equivalent shared state is an :class:`~tkcurses._core.application.Application`,
    reached through ``self.tk`` — the same attribute name, so tkinter code
    that pokes at it finds something there.

    Widget geometry is kept in ``_rect`` (position relative to the master) and
    ``_requested`` (the size the widget asked for). This class only reads
    them; the geometry managers and the window lifecycle set them, and until
    they do every ``winfo`` query reports zeroes rather than failing.

    ``_layout_manager`` is the manager laying out this widget's *children*,
    which is a different thing from the manager that placed the widget itself
    - that one is named by ``winfo_manager()``, and the container holding its
    options is ``_manager_container``. A widget can be packed into its parent
    while gridding its own children.
    """

    #: True for Tk and Toplevel. Bindings, focus history and coordinate
    #: origins all stop at a toplevel, so the widget layer marks them here.
    _is_toplevel = False

    #: State shared with every other widget in the same application.
    tk: Application

    #: The parent widget, None for the root of the tree.
    master: Misc | None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Let every ``configure`` a subclass defines answer a query.

        ``configure("relief")`` asks for one option rather than setting any,
        and Tk answers it on every widget. Nearly thirty classes here override
        ``configure`` to check or react to what is set, and every one began
        by merging ``cnf`` into a dict - so a string crashed them all with
        ``'str' object is not a mapping``, the root window included
        (TkCurses-kifn). Answering it here, once, means an override written
        later cannot forget to.
        """
        super().__init_subclass__(**kwargs)
        # What the class RESOLVES, not what it defines: the ttk widgets take
        # configure from ttk.Widget, a mixin that is no Misc and never comes
        # through here itself.
        for name in ("configure", "config"):
            method = getattr(cls, name)
            if not getattr(method, "_answers_queries", False):
                setattr(cls, name, _answering_queries(method))

    def __init__(self, master: Misc | None = None, name: str | None = None) -> None:
        """
        Args:
            master: Parent widget. None makes this the root of a new
                application with its own bindings, timers and clipboard;
                resolving a default root is the widget layer's job, not this
                one's.
            name: Path component for this widget. Generated from the class
                name when omitted, as tkinter does.

        Raises:
            ValueError: If the name contains a ``.``, which would make the
                widget path ambiguous.
        """
        self.master = master
        self.children: dict[str, Misc] = {}
        self.tk = Application() if master is None else master.tk

        if name is None:
            name = "." if master is None else self.tk.next_name(type(self).__name__)
        if master is not None and "." in name:
            raise ValueError(f"widget name {name!r} may not contain a '.'")
        self._name = name
        self._w = self._build_path(master, name)

        self._bindtags: tuple[str, ...] | None = None
        self._options: dict[str, Any] = {}
        self._rect = Rect(0, 0, 0, 0)
        self._requested = Size(0, 0)
        self._manager = ""
        #: The container whose geometry manager is laying this widget out.
        #: Usually the master, but ``in_`` allows another - and either way
        #: it is where the widget's own options live, which is what a later
        #: reconfigure has to merge into.
        self._manager_container: Misc | None = None
        #: The geometry manager laying out this widget's children, and
        #: whether this widget resizes itself to fit them.
        self._layout_manager: Layout | None = None
        self._layout_propagate = True
        #: The stacked window this widget draws into, once it has one.
        self._panel: Panel | None = None
        self._mapped = False
        self._takefocus = True
        self._takefocus_given = False
        self._destroyed = False

        self.tk.widgets.add(self._w, self)
        if master is not None:
            master.children[name] = self

    def __repr__(self) -> str:
        """Identify the widget by class and path, as tkinter does."""
        return f"<{type(self).__name__} object {self._w}>"

    def __str__(self) -> str:
        """The widget's path name.

        Tk identifies widgets by path in every API that takes one, so a widget
        used where a string is expected has to render as its path.
        """
        return self._w

    @staticmethod
    def _build_path(master: Misc | None, name: str) -> str:
        """Full path name for a widget under ``master``.

        The root is ``.`` and its children are ``.name`` rather than
        ``..name``, which is why this is not a plain join.
        """
        if master is None:
            return name
        return f"{master._w}{name}" if master._w == "." else f"{master._w}.{name}"

    # ==================================================================
    # Core
    # ==================================================================

    def destroy(self) -> None:
        """Destroy this widget and everything under it.

        Children go first, so a handler bound to ``<Destroy>`` on a child
        still sees an intact parent. Destroying twice is harmless, which
        matters because a parent's teardown may reach a child the application
        has already destroyed.
        """
        if self._destroyed:
            return
        for child in list(self.children.values()):
            child.destroy()
        self.event_generate("<Destroy>")

        self._destroyed = True
        self._mapped = False
        self.tk.bindings.unbind(self._w)
        # Pending callbacks go with it. Tk owns an after handle as a command
        # belonging to the widget, so destroying the widget drops it and the
        # callback never runs; here it used to run against a widget whose
        # window and panel were gone.
        self.tk.timers.cancel_for(self._w)
        self.tk.widgets.remove(self._w)
        self.tk.selections.disown(self)
        if self.tk.focus is self:
            self.tk.focus = None
        if self.tk.grab is self:
            self.grab_release()
        self.tk.focus_history.pop(id(self), None)
        if self.master is not None:
            self.master.children.pop(self._name, None)

    def deletecommand(self, name: str) -> None:
        """Remove a registered callback by the handle ``bind`` returned.

        tkinter deletes a Tcl command here; the only handles TkCurses hands
        out are binding ids, so that is what this removes.
        """
        self.tk.bindings.unbind(self._w, funcid=name)

    # ==================================================================
    # Binding
    # ==================================================================

    def bind(
        self,
        sequence: str | None = None,
        func: Callable[[Event], Any] | None = None,
        add: bool | str | None = None,
    ) -> Any:
        """Bind ``func`` to ``sequence`` on this widget.

        With a callback, returns a handle that :meth:`unbind` accepts. With a
        sequence but no callback, returns the callbacks bound to it — tkinter
        returns a Tcl script string there, which has no meaning without Tcl,
        so the callables themselves are returned instead. With neither,
        returns the sequences currently bound.

        ``add`` keeps existing callbacks instead of replacing them. tkinter
        spells it ``"+"``; a true value works too.
        """
        return self._bind_on(self._w, sequence, func, add)

    def unbind(self, sequence: str, funcid: str | None = None) -> None:
        """Remove bindings for ``sequence``, or just the one named by ``funcid``."""
        self.tk.bindings.unbind(self._w, parse_sequence(sequence), funcid)

    def bind_all(
        self,
        sequence: str | None = None,
        func: Callable[[Event], Any] | None = None,
        add: bool | str | None = None,
    ) -> Any:
        """Bind on the ``all`` tag, so every widget in the application sees it."""
        return self._bind_on("all", sequence, func, add)

    def unbind_all(self, sequence: str) -> None:
        """Remove an application-wide binding."""
        self.tk.bindings.unbind("all", parse_sequence(sequence))

    def bind_class(
        self,
        className: str,
        sequence: str | None = None,
        func: Callable[[Event], Any] | None = None,
        add: bool | str | None = None,
    ) -> Any:
        """Bind on a widget class, so every widget of that class sees it.

        This is how a widget's own behaviour is defined: ``Entry`` handles
        typing through a class binding, which an instance binding can then
        override or suppress with ``"break"``.
        """
        return self._bind_on(className, sequence, func, add)

    def unbind_class(self, className: str, sequence: str) -> None:
        """Remove a class binding."""
        self.tk.bindings.unbind(className, parse_sequence(sequence))

    def bindtags(self, tagList: Sequence[str] | None = None) -> tuple[str, ...]:
        """Get or set the tags consulted when an event reaches this widget.

        The default is the widget's own path, its class, its toplevel, and
        ``all``, in that order. Reordering them is the supported way to make
        an instance binding run before its class binding rather than after.
        """
        if tagList is None:
            return self._binding_tags()
        self._bindtags = tuple(str(tag) for tag in tagList)
        return self._bindtags

    def _binding_tags(self) -> tuple[str, ...]:
        """The tags to consult, honouring any set by :meth:`bindtags`."""
        if self._bindtags is not None:
            return self._bindtags
        toplevel = self.winfo_toplevel()
        tags = [self._w, self.winfo_class()]
        if toplevel is not self:
            tags.append(toplevel._w)
        tags.append("all")
        return tuple(tags)

    def _bind_on(
        self,
        tag: str,
        sequence: str | None,
        func: Callable[[Event], Any] | None,
        add: bool | str | None,
    ) -> Any:
        """Shared implementation of the four ``bind`` variants."""
        if sequence is None:
            return self.tk.bindings.sequences(tag)
        pattern = parse_sequence(sequence)
        if func is None:
            return tuple(
                binding.func for binding in self.tk.bindings.bindings(tag, pattern)
            )
        return self.tk.bindings.bind(tag, pattern, func, add=bool(add))

    # ==================================================================
    # Virtual events
    # ==================================================================

    def event_add(self, virtual: str, *sequences: str) -> None:
        """Make each of ``sequences`` raise the virtual event ``virtual``."""
        self.tk.virtual_events.add(
            virtual, *(parse_sequence(sequence) for sequence in sequences)
        )

    def event_delete(self, virtual: str, *sequences: str) -> None:
        """Stop ``sequences`` raising ``virtual``; with none given, remove it."""
        self.tk.virtual_events.delete(
            virtual, *(parse_sequence(sequence) for sequence in sequences)
        )

    def event_info(self, virtual: str | None = None) -> tuple[str, ...]:
        """Sequences bound to ``virtual``, or every virtual event's name."""
        if virtual is None:
            return tuple(self.tk.virtual_events.names())
        return tuple(str(pattern) for pattern in self.tk.virtual_events.info(virtual))

    def event_generate(self, sequence: str, **kw: Any) -> None:
        """Deliver a synthetic event to this widget's bindings.

        Keyword arguments set fields on the :class:`Event` the callbacks
        receive, so a test or a widget can raise ``<<Paste>>`` or replay a
        click without a terminal in the loop.
        """
        pattern = parse_sequence(sequence)
        if isinstance(pattern, PatternSequence):
            # Measured, Tk 9.0.2: event generate of a two-event sequence, or
            # of "ab", answers exactly this.
            raise TclError("only one event specification allowed")
        event = Event(widget=self, **kw)
        event.type = pattern.type
        if pattern.is_virtual:
            self._dispatch(event, [pattern])
            return
        if pattern.type == "Key" and not event.keysym:
            event.keysym = pattern.detail
        if pattern.type.startswith("Button") and not event.num:
            with contextlib.suppress(ValueError):
                event.num = int(pattern.detail)
        if not event.state:
            event.state = pattern.modifiers
        self._dispatch(event, [pattern])

    # ==================================================================
    # Event delivery
    # ==================================================================

    def _handle(self, core: CoreEvent) -> bool:
        """Deliver one input event to this widget, returning True on break.

        The entry point the main loop uses once it has decided which widget an
        event belongs to.
        """
        if isinstance(core, MouseEvent):
            # The only report of where the mouse is; winfo_pointerxy() has
            # nothing else to go on, since curses cannot be asked.
            self.tk.pointer = (core.x, core.y)
            if core.state == "clicked":
                # ncurses merges a quick press and release into one CLICKED
                # report. Tk has no such event: a widget waits for the
                # release to decide whether the press counted, so delivering
                # only a press leaves a button held down for ever and never
                # invoked. The pair is put back here, where the knowledge that
                # curses coalesced them belongs.
                broke = self._handle(replace(core, state="pressed"))
                return self._handle(replace(core, state="released")) or broke
        pattern = pattern_for_event(core)
        return self._dispatch(Event._from_core(core, self), [pattern])

    def _dispatch(self, event: Event, patterns: list[EventPattern]) -> bool:
        """Run the bindings matching ``patterns`` over this widget's tags.

        A physical event also raises whatever virtual events it is registered
        for, matching Tk: a widget with both ``<Control-v>`` and ``<<Paste>>``
        bound runs both.
        """
        if self._destroyed:
            return False
        all_patterns = list(patterns)
        for pattern in patterns:
            if not pattern.is_virtual:
                all_patterns.extend(self.tk.virtual_events.raised_by(pattern))
        return self.tk.bindings.dispatch(self._binding_tags(), event, all_patterns)

    # ==================================================================
    # Focus
    # ==================================================================

    def focus_set(self) -> None:
        """Give this widget the keyboard focus.

        The widget losing focus gets ``<FocusOut>`` and this one gets
        ``<FocusIn>``, in that order, which is the order Tk uses and the one
        an entry widget relies on to commit its value before the next one
        starts editing.
        """
        previous = self.tk.focus
        if previous is self:
            return
        self.tk.focus = self
        self.tk.focus_history[id(self.winfo_toplevel())] = self
        if previous is not None and previous.winfo_exists():
            previous.event_generate("<FocusOut>")
        self.event_generate("<FocusIn>")

    focus = focus_set

    def focus_force(self) -> None:
        """Take the focus.

        Identical to :meth:`focus_set`: the distinction in Tk is about wresting
        focus from another application's window, and a curses program owns the
        whole terminal already.
        """
        self.focus_set()

    def focus_get(self) -> Misc | None:
        """The widget with the keyboard focus, or None."""
        return self.tk.focus

    def focus_displayof(self) -> Misc | None:
        """The focused widget. There is one display, so this is :meth:`focus_get`."""
        return self.tk.focus

    def focus_lastfor(self) -> Misc:
        """The widget that last had focus in this widget's toplevel.

        Returns the toplevel itself if nothing in it has been focused, so the
        result is always something that can be focused.
        """
        toplevel = self.winfo_toplevel()
        last = self.tk.focus_history.get(id(toplevel))
        if last is None or not last.winfo_exists():
            return toplevel
        return last

    def tk_focusFollowsMouse(self) -> None:
        """Focus whichever widget the mouse is over.

        One-way, as in Tk: there is no call to turn it off again.
        """
        self.tk.focus_follows_mouse = True

    def tk_focusNext(self) -> Misc | None:
        """The next widget in tab order, or None if nothing can take focus."""
        return self._focus_step(1)

    def tk_focusPrev(self) -> Misc | None:
        """The previous widget in tab order."""
        return self._focus_step(-1)

    def _focus_step(self, direction: int) -> Misc | None:
        """Walk the focus order from this widget by one step, wrapping around.

        Tab order is the order widgets were created within the toplevel, which
        is the order they appear in each parent's children — the same rule Tk
        uses, and the reason reordering a layout does not reorder tabbing.
        """
        order = [
            widget
            for widget in self.winfo_toplevel()._subtree()
            if widget._focus_ok() and widget is not self.winfo_toplevel()
        ]
        if not order:
            return None
        try:
            index = order.index(self)
        except ValueError:
            return order[0 if direction > 0 else -1]
        return order[(index + direction) % len(order)]

    def _focus_ok(self) -> bool:
        """Whether tabbing may stop on this widget.

        Tk settles this in ``::tk::FocusOK``, and it is three rules rather
        than one:

        * ``takefocus`` set to false - never.
        * ``takefocus`` set to true - always, **disabled or not**. A caller
          who named it meant it.
        * ``takefocus`` left alone - only while the widget is not disabled.

        The third is the one that was missing, so tabbing stopped on widgets
        that could not be typed into and said nothing about why; the next Tab
        moved on, making it read as a dead stop rather than a skipped one.

        The distinction needs to know whether ``takefocus`` was *asked for* or
        merely defaulted, which a bool cannot hold - hence
        ``_takefocus_given``. Tk keeps the same distinction by defaulting the
        option to the empty string rather than to a truth value.
        """
        if not self._takefocus:
            return False
        if self._takefocus_given:
            return True
        return str(self._options.get("state", "normal")) != "disabled"

    def _subtree(self) -> Iterator[Misc]:
        """This widget and its descendants, parents before children."""
        yield self
        for child in list(self.children.values()):
            yield from child._subtree()

    # ==================================================================
    # Event scheduling
    # ==================================================================

    def after(
        self, ms: int, func: Callable[..., Any] | None = None, *args: Any
    ) -> str | None:
        """Run ``func`` after ``ms`` milliseconds; return a cancellable handle.

        Without ``func`` this sleeps, as tkinter's does. That blocks the event
        loop for the whole delay and the display stops responding, which is
        why the callback form is the one to reach for; the blocking form is
        kept only because tkinter has it.
        """
        if func is None:
            time.sleep(ms / 1000.0)
            return None
        return self.tk.timers.after(ms, func, *args, owner=self._w)

    def after_idle(self, func: Callable[..., Any], *args: Any) -> str:
        """Run ``func`` when the event loop next has nothing else to do."""
        return self.tk.timers.after_idle(func, *args, owner=self._w)

    def after_cancel(self, id: str) -> None:
        """Cancel a scheduled callback.

        Raises:
            ValueError: If ``id`` is None, as tkinter does. Cancelling a
                handle that has already fired is not an error.
        """
        if id is None:
            raise ValueError("id must be a valid identifier returned from after")
        self.tk.timers.cancel(id)

    def after_info(self, id: str | None = None) -> Any:
        """Handles still scheduled, or ``(func, args, kind)`` for one of them."""
        return self.tk.timers.info(id)

    # ==================================================================
    # Audio
    # ==================================================================

    def bell(self, displayof: int = 0) -> None:  # noqa: ARG002 - tkinter signature
        """Ring the terminal bell.

        Whether anything is heard is the terminal emulator's decision; many
        flash the screen instead, and some do nothing at all.
        """
        if self.tk.screen is not None and self.tk.screen.started:
            with contextlib.suppress(_curses.error):
                _curses.beep()
            return
        with contextlib.suppress(OSError, ValueError):
            sys.stdout.write("\a")
            sys.stdout.flush()

    # ==================================================================
    # Clipboard and selection
    # ==================================================================

    def _copy_on_interrupt(self) -> bool:
        """Copy instead of closing, if the focused widget has a selection.

        Ctrl-C is the close gesture here (TkCurses-7l6), and Tk's copy key.
        Measured in the author's terminal (TkCurses-lw2), no OTHER copy key
        of Tk's reaches a program: Ctrl-Insert and Ctrl-Shift-V arrive as
        nothing, Ctrl-Shift-C arrives as plain Ctrl-C, and Alt-W as Escape
        then w. So the decision, the author's: **Ctrl-C copies when the focused
        widget has something selected, and closes otherwise.** Close stays
        one keystroke away - press it again once the selection is gone - and
        an application that binds ``<Control-c>`` still takes the key
        entirely, as before.

        Returns True if it copied, in which case nothing closes.
        """
        focused = self.focus_get()
        if focused is None or not focused._has_copyable_selection():
            return False
        focused.event_generate("<<Copy>>")
        return True

    def _focused_cursor_style(self) -> CursorStyle:
        """What the focused widget asks of the terminal cursor's look."""
        focused = self.tk.focus
        return TERMINALS_OWN if focused is None else focused._cursor_style()

    def _cursor_style(self) -> CursorStyle:
        """Nothing, for anything with no insertion cursor of its own."""
        return TERMINALS_OWN

    def _focused_insert_cell(self) -> tuple[int, int] | None:
        """Where the terminal's cursor belongs: the focused widget's insert point.

        None when nothing has the focus, or what has it takes no typing.
        """
        focused = self.tk.focus
        return None if focused is None else focused._insert_cell()

    def _insert_cell(self) -> tuple[int, int] | None:
        """The screen cell, ``(row, column)``, where typing would go here.

        None for a widget that takes no typing; Entry and Text say otherwise.
        """
        return None

    def _has_copyable_selection(self) -> bool:
        """Whether this widget has a selection Ctrl-C should copy.

        False here; Entry and Text, which bind ``<<Copy>>``, say otherwise.
        See :meth:`_copy_on_interrupt`.
        """
        return False

    def clipboard_get(self, **kw: Any) -> str:
        """Return the clipboard contents.

        Raises:
            TclError: If nothing has been copied, as tkinter does when no
                application owns the selection.
        """
        return self.tk.selections.get(kw.get("selection", CLIPBOARD))

    def clipboard_clear(self, **kw: Any) -> None:
        """Empty the clipboard."""
        self.tk.selections.clear(kw.get("selection", CLIPBOARD))

    def clipboard_append(self, string: str, **kw: Any) -> None:
        """Add ``string`` to the clipboard, claiming it if it was empty."""
        selection = kw.get("selection", CLIPBOARD)
        self.tk.selections.append(string, selection)
        self.tk.selections.own(self, selection)

    def selection_get(self, **kw: Any) -> str:
        """Return the selection, asking its owner's handler if it has one."""
        return self.tk.selections.resolve(kw.get("selection", PRIMARY))

    def selection_clear(self, **kw: Any) -> None:
        """Release the selection."""
        selection = kw.get("selection", PRIMARY)
        self.tk.selections.clear(selection)
        if self.tk.selections.owner(selection) is self:
            self.tk.selections.disown(self)

    def selection_own(self, **kw: Any) -> None:
        """Claim the selection for this widget.

        ``command``, as in tkinter, is called when another widget takes it.
        """
        self.tk.selections.own(
            self, kw.get("selection", PRIMARY), lost=kw.get("command")
        )

    def image_names(self) -> tuple[str, ...]:
        """The names of every image this application still holds.

        "Still" is the operative word, and it is not a quirk of this
        implementation: an image nothing references is collected, so a name
        can leave this list without anything having deleted it. That is Tk's
        behaviour too, and the registry is weak in order to keep it.
        """
        return tuple(sorted(self.tk.images))

    def image_types(self) -> tuple[str, ...]:
        """The image types that can be created, as Tk reports them."""
        return ("bitmap", "photo")

    def selection_own_get(self, **kw: Any) -> Misc:
        """The widget owning the selection.

        Raises:
            TclError: If nothing owns it, matching tkinter.
        """
        selection = kw.get("selection", PRIMARY)
        owner: Misc | None = self.tk.selections.owner(selection)
        if owner is None:
            raise TclError(f"selection {selection} doesn't exist or form unknown")
        return owner

    def selection_handle(self, command: Callable[..., str], **kw: Any) -> None:
        """Supply the selection's contents from ``command`` when it is asked for."""
        self.tk.selections.handle(self, command, kw.get("selection", PRIMARY))

    # ==================================================================
    # Grab
    # ==================================================================

    def grab_set(self) -> None:
        """Direct events to this widget and its children only.

        How a modal dialog stays modal. The main loop honours it when deciding
        where an event goes.
        """
        self.tk.grab = self
        self.tk.grab_global = False

    def grab_set_global(self) -> None:
        """Grab globally.

        A curses application already owns the terminal, so this differs from
        :meth:`grab_set` only in what :meth:`grab_status` reports.
        """
        self.tk.grab = self
        self.tk.grab_global = True

    def grab_release(self) -> None:
        """Release the grab, if this widget holds it."""
        if self.tk.grab is self:
            self.tk.grab = None
            self.tk.grab_global = False

    def grab_current(self) -> Misc | None:
        """The widget holding the grab, or None."""
        return self.tk.grab

    def grab_status(self) -> str | None:
        """``"local"``, ``"global"``, or None if this widget has no grab."""
        if self.tk.grab is not self:
            return None
        return "global" if self.tk.grab_global else "local"

    # ==================================================================
    # Stacking
    # ==================================================================

    def tkraise(self, aboveThis: Misc | None = None) -> None:
        """Raise this widget above its siblings, or just above ``aboveThis``."""
        self._restack(aboveThis, above=True)

    lift = tkraise

    def lower(self, belowThis: Misc | None = None) -> None:
        """Lower this widget below its siblings, or just below ``belowThis``."""
        self._restack(belowThis, above=False)

    def _restack(self, other: Misc | None, above: bool) -> None:
        """Move this widget within its parent's child order.

        Sibling order *is* stacking order: the panel stack is rebuilt from it,
        so moving a widget here is what puts its window in front once one
        exists.
        """
        if self.master is None:
            return
        siblings = self.master.children
        if self._name not in siblings:
            return
        order = [name for name in siblings if name != self._name]
        if other is None:
            position = len(order) if above else 0
        else:
            try:
                index = order.index(other._name)
            except ValueError:
                return
            position = index + 1 if above else index
        order.insert(position, self._name)
        self.master.children = {name: siblings[name] for name in order}

    # ------------------------------------------------------ negotiation

    def _content_rect(self) -> Rect:
        """The region this container offers its children, in screen cells.

        The widget's own region less its border and padding, per
        ARCHITECTURE.md "Content Coordinate Rules": a bordered 30x8 window
        offers 28x6 starting one cell in.
        """
        rect = Rect(
            self.winfo_rootx(), self.winfo_rooty(), self._rect.width, self._rect.height
        )
        if _menubar_of(self) is not None:
            # A menubar sits inside the window's border and above everything
            # else in it, so the row it occupies is not the children's to
            # use. Taken off here rather than in each window class, because
            # this is the one place that decides what a container offers.
            rect = Rect(rect.x, rect.y + 1, rect.width, max(0, rect.height - 1))
        return content_rect(
            rect, bordered=self._border_drawn, padding=self._content_padding()
        )

    def _content_padding(self) -> Insets:
        """Space inside the border that this container keeps from its children.

        One method because TWO things need the same answer - :meth:`_content_rect`
        places the children and :meth:`_outer_size` asks the parent for room -
        and a container whose two halves disagree either clips its children or
        leaves a gap. The scrollbar that drew seven of its nine rows was two
        predicates disagreeing in exactly this way.

        Overridable so a themed widget can add ttk's ``-padding`` to it.
        """
        return Insets.symmetric(
            horizontal=int(self._options.get("padx", 0) or 0),
            vertical=int(self._options.get("pady", 0) or 0),
        )

    def _outer_size(self, content: Size) -> Size:
        """How big this widget must be to offer ``content`` cells inside it.

        The inverse of :meth:`_content_rect`, and the thing a container has
        to tell its parent: a geometry manager works out what the children
        need, which is a *content* size, and the container is bigger than
        that by its own border, padding and menubar. Without this a bordered
        container sized to its children clips them by exactly its border.

        ``_bordered`` rather than ``_border_drawn``, deliberately: whether a
        border is drawn depends on the size the widget already has, and
        asking that here would be circular - a frame one row tall draws no
        border, so it would ask for no room for one, so it would stay one
        row tall.
        """
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        padding = self._content_padding()
        menu = 1 if _menubar_of(self) is not None else 0
        return Size(
            content.width + edge + padding.width,
            content.height + edge + padding.height + menu,
        )

    @property
    def _bordered(self) -> bool:
        """True if this widget draws a border, costing a cell on each edge.

        overrideredirect asks for a window a window manager leaves alone,
        which here means one that draws no decoration of its own.
        """
        if getattr(self, "_overrideredirect", False):
            return False
        return bool(self._options.get("borderwidth")) or (
            self._options.get("relief", FLAT) != FLAT
        )

    @property
    def _border_drawn(self) -> bool:
        """True when there is a border *and* room on screen to draw it.

        A bordered widget too small for its own border draws none, so
        everything that measures the space left inside has to agree with the
        painting. It did not: an Entry squeezed to a single row subtracted
        an edge that was never drawn, came out with no content area at all,
        and rendered nothing - a blank rectangle indistinguishable from a
        widget that had failed to appear.
        """
        return self._bordered and self._rect.width >= 2 and self._rect.height >= 2

    def _restack_panels(self) -> None:
        """Put the panel stack back into tree order, parents behind children.

        ``_subtree`` yields a widget before its children, so raising each in
        turn leaves every child in front of its container and siblings in
        their own stacking order.
        """
        stack = self.tk.panels
        if stack is None:
            return
        for widget in self._subtree():
            panel = widget._panel
            if panel is not None and not panel.hidden:
                stack.raise_to_top(panel)

    def _redraw(self) -> None:
        """Repaint after this widget's window changed.

        Called whenever the window is created, replaced or moved - a resize
        builds a new curses window, so anything drawn into the old one is
        gone. Widgets that draw override this; the default does nothing,
        which is every widget until the widget set lands.
        """

    def _screen_rect(self) -> Rect:
        """Where this widget is on the screen, in absolute cells.

        ``_rect`` is an offset from the master; a curses panel is positioned
        absolutely. Confusing the two is invisible for a toplevel, whose
        master sits at the origin, and wrong for everything inside one.
        """
        x, y = self._root_offset()
        return Rect(x, y, self._rect.width, self._rect.height)

    def _visible_rect(self) -> Rect:
        """The part of this widget that is on the screen.

        A widget may be positioned partly or wholly outside the terminal -
        place() allows it and Tk clips the result - but a curses window may
        not: asking curses to move a panel past an edge fails outright, and
        the whole application goes down with it. The panel therefore covers
        the visible part only, while the widget's own geometry is left alone,
        so winfo_x() still reports where it was actually put.
        """
        width, height = self._screen_size()
        return self._screen_rect().intersection(Rect(0, 0, width, height))

    def _request_size(self, width: int, height: int) -> None:
        """Declare the size this widget would like to be.

        A widget calls this when its content changes - a label given longer
        text, a frame given another child. The request travels no further
        than it changes anything: the container is queued, and the run that
        follows stops at the first ancestor whose own size is unaffected.
        """
        requested = Size(max(0, width), max(0, height))
        if requested == self._requested:
            return
        self._requested = requested
        if self.master is not None:
            self.tk.layout.invalidate(self.master)

    def _invalidate_layout(self) -> None:
        """Ask for this container's children to be laid out again."""
        self.tk.layout.invalidate(self)

    def update_layout(self) -> int:
        """Lay out whatever is waiting, now. Returns containers laid out.

        The main loop does this before drawing, so an application rarely
        needs to. A test that wants to read geometry without running a loop
        does.
        """
        return self.tk.layout.run()

    def _propagate_flag(self, flag: bool | None) -> bool:
        """Shared implementation of pack_propagate and grid_propagate."""
        if flag is None:
            return self._layout_propagate
        self._layout_propagate = bool(flag)
        if self._layout_propagate:
            self._invalidate_layout()
        return self._layout_propagate

    def pack_slaves(self) -> list[Misc]:
        """The children this container is packing, in packing order."""
        manager = self._layout_manager
        if not isinstance(manager, PackLayout):
            return []
        # cast, with a reason: a geometry manager hands back exactly the
        # objects it was given, and in this library those are always widgets.
        # It describes them as Managed because that is all IT needs of them -
        # see _core.geometry.Managed - while the public contract here is
        # tkinter's, a list of widgets. The cast is the one place that
        # difference is stated rather than papered over with Any. TkCurses-d40.
        return cast("list[Misc]", list(manager.slaves(self)))

    slaves = pack_slaves

    def grid_slaves(
        self, row: int | None = None, column: int | None = None
    ) -> list[Misc]:
        """The children this container is gridding, optionally in one cell."""
        manager = self._layout_manager
        if not isinstance(manager, GridLayout):
            return []
        # cast, with a reason: a geometry manager hands back exactly the
        # objects it was given, and in this library those are always widgets.
        # It describes them as Managed because that is all IT needs of them -
        # see _core.geometry.Managed - while the public contract here is
        # tkinter's, a list of widgets. The cast is the one place that
        # difference is stated rather than papered over with Any. TkCurses-d40.
        return cast("list[Misc]", list(manager.slaves(self, row=row, column=column)))

    def grid_size(self) -> tuple[int, int]:
        """The grid's extent as ``(columns, rows)``."""
        manager = self._layout_manager
        return manager.size() if isinstance(manager, GridLayout) else (0, 0)

    def grid_bbox(
        self,
        column: int | None = None,
        row: int | None = None,
        col2: int | None = None,
        row2: int | None = None,
    ) -> tuple[int, int, int, int]:
        """The region a cell or range of cells covers, in screen cells."""
        manager = self._layout_manager
        if not isinstance(manager, GridLayout):
            return (0, 0, 0, 0)
        if column is None or row is None:
            columns, rows = manager.size()
            return manager.bbox(
                self._content_rect(), 0, 0, max(0, columns - 1), max(0, rows - 1)
            )
        return manager.bbox(
            self._content_rect(),
            column,
            row,
            col2 if col2 is not None else column,
            row2 if row2 is not None else row,
        )

    def grid_location(self, x: int, y: int) -> tuple[int, int]:
        """The cell at a screen position, or ``(-1, -1)`` outside the grid."""
        manager = self._layout_manager
        if not isinstance(manager, GridLayout):
            return (-1, -1)
        return manager.location(self._content_rect(), x, y)

    def grid_anchor(self, anchor: str | None = None) -> str:
        """Get or set where the grid sits when it is smaller than its container."""
        manager = _grid_layout_of(self)
        if anchor is not None:
            if anchor != "center":
                # Validate before storing, so a bad anchor fails here rather
                # than during the next layout.
                try:
                    parse_sticky(anchor)
                except ValueError as error:
                    raise TclError(str(error)) from None
            manager.anchor = anchor
            self.tk.layout.invalidate(self)
        return manager.anchor

    def grid_rowconfigure(
        self, index: int, cnf: dict[str, Any] | str | None = None, **kw: Any
    ) -> Any:
        """Get or set how one row behaves: weight, minsize, pad, uniform."""
        return self._line_configure("row", index, cnf, kw)

    def grid_columnconfigure(
        self, index: int, cnf: dict[str, Any] | str | None = None, **kw: Any
    ) -> Any:
        """Get or set how one column behaves."""
        return self._line_configure("column", index, cnf, kw)

    rowconfigure = grid_rowconfigure
    columnconfigure = grid_columnconfigure

    def _line_configure(
        self,
        axis: str,
        index: int,
        cnf: dict[str, Any] | str | None,
        kw: dict[str, Any],
    ) -> Any:
        """Shared implementation of grid_rowconfigure and grid_columnconfigure.

        Raises:
            TclError: If an option is not one Tk accepts for a grid line.
        """
        manager = _grid_layout_of(self)
        current = (
            manager.row_config(index) if axis == "row" else manager.column_config(index)
        )
        listing = {
            "weight": current.weight,
            "minsize": current.minsize,
            "pad": current.pad,
            "uniform": current.uniform,
        }
        if isinstance(cnf, str):
            # grid_columnconfigure(0, "weight") asks for one value. It crashed
            # here on "'str' object is not a mapping" - TkCurses-bx5b, found
            # beside the None handling; TkCurses-kifn was the same for
            # configure. Message measured on Tk 9.0.2.
            if cnf not in listing:
                raise TclError(
                    f'bad option "-{cnf}": must be -minsize, -pad, -uniform, or -weight'
                )
            return listing[cnf]
        # Measured: unlike configure, a call whose every option is None DOES
        # answer the listing in tkinter, since it checks after dropping them.
        given = _given(cnf, kw)
        if not given:
            return listing
        config = LineConfig(
            current.weight, current.minsize, current.pad, current.uniform
        )
        for name, value in given.items():
            if not hasattr(config, name):
                raise TclError(f'unknown option "-{name}"')
            if name == "uniform":
                config.uniform = str(value)
            else:
                try:
                    setattr(config, name, max(0, int(value)))
                except (TypeError, ValueError):
                    raise TclError(f'expected integer but got "{value}"') from None
        if axis == "row":
            manager.configure_row(index, config)
        else:
            manager.configure_column(index, config)
        self.tk.layout.invalidate(self)
        return None

    def place_slaves(self) -> list[Misc]:
        """The children this container is placing."""
        manager = self._layout_manager
        if not isinstance(manager, PlaceLayout):
            return []
        # cast, with a reason: a geometry manager hands back exactly the
        # objects it was given, and in this library those are always widgets.
        # It describes them as Managed because that is all IT needs of them -
        # see _core.geometry.Managed - while the public contract here is
        # tkinter's, a list of widgets. The cast is the one place that
        # difference is stated rather than papered over with Any. TkCurses-d40.
        return cast("list[Misc]", list(manager.slaves(self)))

    def pack_propagate(self, flag: bool | None = None) -> bool:
        """Get or set whether this container resizes to fit its children.

        Switched off, the container keeps whatever size it was given and its
        children are laid out inside that, however little room it leaves.
        Tk offers one flag per manager name; there is one container and one
        setting, so these are the same flag under three spellings, as they
        effectively are in Tk.
        """
        return self._propagate_flag(flag)

    grid_propagate = pack_propagate
    propagate = pack_propagate

    # ==================================================================
    # Window information
    # ==================================================================

    def winfo_children(self) -> list[Misc]:
        """This widget's children, in stacking order."""
        return list(self.children.values())

    def winfo_class(self) -> str:
        """The widget's class name, as bindings and the option database use it."""
        return type(self).__name__

    def winfo_name(self) -> str:
        """The widget's name within its parent."""
        return self._name

    def winfo_parent(self) -> str:
        """The parent's path name, empty for the root."""
        return "" if self.master is None else self.master._w

    def winfo_id(self) -> int:
        """A stable identifier for this widget.

        Tk returns an X window id. There are no windows to have ids, so the
        object's identity stands in: unique, stable for the widget's life, and
        meaningless to compare across runs, which is also true of the original.
        """
        return id(self)

    def winfo_exists(self) -> bool:
        """False once the widget has been destroyed."""
        return not self._destroyed

    def winfo_ismapped(self) -> bool:
        """True if a geometry manager has placed this widget."""
        return self._mapped

    def winfo_viewable(self) -> bool:
        """True if this widget and every ancestor are mapped.

        A mapped widget inside an unmapped frame is not on screen, which is
        the distinction this draws against :meth:`winfo_ismapped`. The root
        is exempt: nothing manages it, and the terminal is always there.
        """
        for widget in self._ancestry():
            if widget.master is not None and not widget._mapped:
                return False
        return True

    def _leave_layout(self, container: Misc) -> None:
        """Take this widget out of one container's layout.

        Called when a geometry call moves the widget somewhere else.
        Without it the container being left goes on laying the widget out:
        a widget moved with ``in_`` is then managed twice over, and drawn
        wherever the first of the two decides.
        """
        layout = container._layout_manager
        if layout is None:
            return
        layout.remove(self)
        container.tk.layout.invalidate(container)

    def _managed_layout(self, name: str) -> Layout | None:
        """The layout currently laying this widget out, if ``name`` is it.

        Tk merges every geometry reconfigure into the options the widget
        already has, and keeps doing so when it moves to a different
        container: ``place_configure(in_=other, x=5)`` leaves the anchor and
        the width alone. Only ``forget`` resets them - checked against Tk
        9.0.2, where a place after ``place_forget`` comes back with
        ``anchor=nw``. Those options live with the container doing the
        laying out, which ``in_`` allows to be something other than the
        master, so this is where a reconfigure goes looking for them.
        """
        if self._manager != name or self._manager_container is None:
            return None
        return self._manager_container._layout_manager

    def winfo_manager(self) -> str:
        """The geometry manager handling this widget, or an empty string."""
        return self._manager

    def winfo_toplevel(self) -> Misc:
        """The nearest enclosing toplevel window."""
        widget = self
        while widget.master is not None and not widget._is_toplevel:
            widget = widget.master
        return widget

    def winfo_x(self) -> int:
        """Column offset within the parent, in cells."""
        return self._rect.x

    def winfo_y(self) -> int:
        """Row offset within the parent, in cells."""
        return self._rect.y

    def winfo_width(self) -> int:
        """Width in cells."""
        return self._rect.width

    def winfo_height(self) -> int:
        """Height in cells."""
        return self._rect.height

    def winfo_reqwidth(self) -> int:
        """Width the widget asked for, which may exceed what it was given."""
        return self._requested.width

    def winfo_reqheight(self) -> int:
        """Height the widget asked for."""
        return self._requested.height

    def winfo_rootx(self) -> int:
        """Column on the screen, in cells."""
        return self._root_offset()[0]

    def winfo_rooty(self) -> int:
        """Row on the screen, in cells."""
        return self._root_offset()[1]

    def _root_offset(self) -> tuple[int, int]:
        """Screen position, summing offsets up to the enclosing toplevel.

        The walk stops there rather than continuing to the root, because a
        toplevel's position is where it sits on the screen, not an offset from
        the widget it happened to be created under. Summing past it would move
        every dialog by its owner's position.
        """
        x = y = 0
        for widget in self._ancestry():
            x += widget._rect.x
            y += widget._rect.y
            if widget._is_toplevel:
                break
        return x, y

    def winfo_geometry(self) -> str:
        """Size and position as ``WxH+X+Y``, in cells."""
        return (
            f"{self.winfo_width()}x{self.winfo_height()}+{self._rect.x}+{self._rect.y}"
        )

    def winfo_containing(self, rootX: int, rootY: int) -> Misc | None:
        """The topmost widget at a screen position, or None.

        Later siblings are on top, so the search runs back to front and takes
        the first hit, which is the widget a click at that cell would reach.
        """
        return self._root()._containing(rootX, rootY)

    def _containing(self, x: int, y: int) -> Misc | None:
        """Depth-first hit test, topmost child first."""
        for child in reversed(list(self.children.values())):
            hit = child._containing(x, y)
            if hit is not None:
                return hit
        if not self._mapped:
            return None
        left, top = self.winfo_rootx(), self.winfo_rooty()
        if (
            left <= x < left + self.winfo_width()
            and top <= y < top + self.winfo_height()
        ):
            return self
        return None

    def winfo_screenwidth(self) -> int:
        """Terminal width in cells."""
        return self._screen_size()[0]

    def winfo_screenheight(self) -> int:
        """Terminal height in cells."""
        return self._screen_size()[1]

    def winfo_vrootwidth(self) -> int:
        """Virtual root width. A terminal has no virtual desktop, so the screen."""
        return self.winfo_screenwidth()

    def winfo_vrootheight(self) -> int:
        """Virtual root height."""
        return self.winfo_screenheight()

    def winfo_cells(self) -> int:
        """Number of colours available, which is what Tk means by cells."""
        return _curses.COLORS if self.tk.screen is not None else 8

    def winfo_depth(self) -> int:
        """Bits per cell, derived from the colour count."""
        return max(1, self.winfo_cells().bit_length() - 1)

    def winfo_screendepth(self) -> int:
        """Bits per cell for the screen, which is the only display there is."""
        return self.winfo_depth()

    def winfo_rgb(self, color: str) -> tuple[int, int, int]:
        """A colour's channel values, 16 bits each, as tkinter reports them.

        For a name or a hex string the terminal cannot show exactly, this is
        what will actually be rendered rather than what was asked for:
        reporting the request back would hide the approximation, and how
        close it gets depends on how many colours the terminal has.
        """
        depth = self.winfo_colordepth()
        direct = rgb_for(color)
        rgb = (
            direct
            if direct is not None
            else palette_rgb(parse_color(color, depth), depth)
        )
        return (rgb[0] * 257, rgb[1] * 257, rgb[2] * 257)

    def winfo_colordepth(self) -> ColorDepth:
        """How many colours this terminal has.

        Not tkinter's - X has no equivalent question, because an X display
        answers ``winfo_screendepth`` in bits per pixel and has the full
        range either way. A terminal does not, and anything drawing a colour
        ramp has to know which of the four tiers it is drawing on.
        On a terminal with no colour at all this is :data:`ColorDepth.NONE`.
        Before there is a screen to ask, it is :data:`ColorDepth.BASIC` - the
        eight every colour terminal has, which is what colour resolution has
        always assumed when it had nothing better to go on.
        """
        colors = self.tk.colors
        return colors.depth if colors is not None else ColorDepth.BASIC

    def winfo_pixels(self, number: str | int | float) -> int:
        """Convert a screen distance to whole cells."""
        return round(self.winfo_fpixels(number))

    def winfo_fpixels(self, number: str | int | float) -> float:
        """Convert a screen distance to cells, keeping the fraction.

        tkinter accepts ``"2c"``, ``"1i"``, ``"10p"`` and ``"3m"`` as well as
        bare numbers. A cell is the unit here, at ten to the inch.

        Raises:
            TclError: If the distance cannot be parsed, as tkinter does.
        """
        if isinstance(number, (int, float)):
            return float(number)
        text = str(number).strip()
        factor = _DISTANCE_UNITS.get(text[-1:])
        try:
            value = float(text[:-1] if factor is not None else text)
        except ValueError:
            raise TclError(f"bad screen distance {number!r}") from None
        return value if factor is None else value * factor * _CELLS_PER_INCH

    def winfo_pointerx(self) -> int:
        """Column the mouse was last reported at."""
        return self.tk.pointer[0]

    def winfo_pointery(self) -> int:
        """Row the mouse was last reported at."""
        return self.tk.pointer[1]

    def winfo_pointerxy(self) -> tuple[int, int]:
        """Where the mouse was last reported, as ``(x, y)``."""
        return self.tk.pointer

    def _ancestry(self) -> Iterator[Misc]:
        """This widget and every ancestor, innermost first."""
        widget: Misc | None = self
        while widget is not None:
            yield widget
            widget = widget.master

    def _root(self) -> Misc:
        """The root widget of this application."""
        widget = self
        while widget.master is not None:
            widget = widget.master
        return widget

    def _screen_size(self) -> tuple[int, int]:
        """Terminal size in cells, from the screen if one is running.

        Before ``mainloop()`` there is no curses screen to ask, and the answer
        still has to be something usable, so the environment is consulted and
        a conventional 80x24 stands in when even that fails — output redirected
        to a file, most often.
        """
        screen = self.tk.screen
        if screen is not None and screen.started:
            size = screen.size
            return size.width, size.height
        try:
            terminal = os.get_terminal_size()
        except OSError:
            return 80, 24
        return terminal.columns, terminal.lines

    # ==================================================================
    # Event loop
    # ==================================================================

    def update_idletasks(self) -> None:
        """Run pending idle callbacks without touching input."""
        self.tk.timers.run_idle()

    def update(self) -> None:
        """Run pending callbacks.

        Idle work first, then anything whose timer has expired, which is the
        order the main loop uses. Input is not read here: draining the
        keyboard from inside a callback is what makes tkinter's ``update()``
        reentrant and dangerous, and the loop in Tk is the one place that does
        it.
        """
        self.tk.timers.run_idle()
        self.tk.timers.run_due()

    def wait_variable(self, name: Variable) -> None:
        """Run the event loop until ``name`` is written to.

        A modal wait: it returns when something sets the variable, and hangs
        if nothing ever does - which is Tk's behaviour too, and why the usual
        caller is a dialog that has already arranged for a button to set it.
        """
        written: list[bool] = []
        handle = name.trace_add("write", lambda *_: written.append(True))
        try:
            self._wait_until(lambda: bool(written))
        finally:
            name.trace_remove("write", handle)

    waitvar = wait_variable

    def wait_window(self, window: Misc | None = None) -> None:
        """Run the event loop until ``window`` is destroyed.

        Returns at once if it is already gone, so a caller need not race the
        window it is waiting for.
        """
        target = window if window is not None else self
        self._wait_until(lambda: not target.winfo_exists())

    def wait_visibility(self, window: Misc | None = None) -> None:
        """Run the event loop until ``window`` is on the screen."""
        target = window if window is not None else self
        self._wait_until(lambda: target.winfo_viewable())

    def _wait_until(self, ready: Callable[[], bool]) -> None:
        """Pump the event loop until ``ready`` holds.

        Stops early if the root is destroyed: without that, closing the
        application during a wait would leave the loop spinning on a tree
        that no longer exists.
        """
        root = self._root()
        while not ready():
            if not root.winfo_exists():
                return
            root.update()

    def quit(self) -> None:
        """Ask the main loop to stop.

        The loop notices on its next pass, so the calling callback runs to
        completion first.
        """
        self.tk.quit_requested = True

    def mainloop(self, n: int = 0) -> None:
        """Enter the event loop.

        Raises:
            TclError: Unless the root widget provides a loop. ``Tk()`` does;
                a bare ``Misc`` tree has nothing to run.
        """
        root = self._root()
        if root is self:
            raise TclError("no event loop is available; create a Tk() first")
        root.mainloop(n)

    # ==================================================================
    # Configuration
    # ==================================================================

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set widget options, or return them all when called with none.

        tkinter returns a five-tuple per option describing its resource name,
        class and default. Those come from Tcl's widget definitions, which do
        not exist here, so the current values are returned instead.

        Asked for one option by name, it does answer the five-tuple: see
        :meth:`_configure_query`.
        """
        options = _given(cnf, kw)
        if not options:
            return dict(self._options)
        for key, value in options.items():
            self._options[key] = value
        return None

    config = configure

    def _configure_query(self, key: str) -> tuple[Any, ...]:
        """``configure(key)``: Tk's five-tuple for one option.

        ``(name, database name, database class, default, value)``. A widget
        knows its defaults and its class, so :class:`BaseWidget` answers this
        properly; here there is only the value.
        """
        return (key, *database_names("", key), "", self.cget(key))

    def cget(self, key: str) -> Any:
        """The value of one option.

        Raises:
            TclError: If the widget has no such option.
        """
        try:
            return self._options[key]
        except KeyError:
            raise TclError(f'unknown option "-{key}"') from None

    def keys(self) -> list[str]:
        """The widget's option names, sorted."""
        return sorted(self._options)

    def __getitem__(self, key: str) -> Any:
        """``widget[key]`` reads an option, as in tkinter."""
        return self.cget(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """``widget[key] = value`` sets an option."""
        self.configure({key: value})

    # ==================================================================
    # Option database
    # ==================================================================

    def option_add(
        self, pattern: str, value: Any, priority: int | str | None = None
    ) -> None:
        """Register a default for options matching ``pattern``."""
        self.tk.options.add(pattern, value, priority)

    def option_clear(self) -> None:
        """Discard every registered option default."""
        self.tk.options.clear()

    def option_get(self, name: str, className: str) -> Any:
        """The registered default for ``name`` on this widget, or None."""
        return self.tk.options.get(self._w, className, name)

    def option_readfile(
        self,
        fileName: str,  # noqa: ARG002 - tkinter signature
        priority: int | str | None = None,  # noqa: ARG002 - tkinter signature
    ) -> None:
        """Not supported.

        Raises:
            TclError: Always. The file format is Tcl's resource syntax, and
                nothing here can read it.
        """
        raise TclError("option_readfile is not supported: no Tcl resource parser")

    # ==================================================================
    # Utility
    # ==================================================================

    def nametowidget(self, name: str | Misc) -> Misc:
        """The widget with the given path name.

        A name without a leading ``.`` is taken as relative to this widget,
        which is how Tk resolves the names it hands to callbacks.

        Raises:
            KeyError: If no such widget exists.
        """
        path = str(name)
        if not path.startswith("."):
            path = self._build_path(self, path)
        widget = self.tk.widgets.get(path)
        if widget is None:
            raise KeyError(f"no widget named {path!r}")
        return widget

    _nametowidget = nametowidget

    def getvar(self, name: str = "PY_VAR") -> Any:
        """Read an application variable."""
        return self.tk.variables.get(name)

    def setvar(self, name: str = "PY_VAR", value: Any = "1") -> None:
        """Write an application variable."""
        self.tk.variables[name] = value

    def getint(self, s: Any) -> int:
        """Parse an integer, accepting Tcl's ``0x``/``0o``/``0b`` prefixes."""
        if isinstance(s, int):
            return s
        return int(str(s), 0)

    def getdouble(self, s: Any) -> float:
        """Parse a float."""
        return float(s)

    def getboolean(self, s: Any) -> bool:
        """Parse a boolean the way Tcl does.

        Accepts ``1``/``0``, ``yes``/``no``, ``true``/``false``, ``on``/``off``
        in any case, as well as real booleans and numbers.

        Raises:
            TclError: If the value is not one of those, as tkinter does.
        """
        if isinstance(s, bool):
            return s
        if isinstance(s, (int, float)):
            return bool(s)
        text = str(s).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise TclError(f'expected boolean value but got "{s}"')


# ======================================================================
# Default root
# ======================================================================

#: The root created implicitly when a widget is made with no master, as
#: tkinter does. Set by ``Tk()``; nothing here creates one, because creating a
#: root means taking over the terminal and that should never be a side effect
#: of forgetting an argument.
_default_root: Misc | None = None

#: Whether an implicit root is allowed at all. ``NoDefaultRoot()`` clears it.
_support_default_root = True


def NoDefaultRoot() -> None:
    """Require every widget to name its master explicitly.

    Worth calling in a library: an implicit root is a process-wide singleton,
    and code that relies on it cannot be used twice in one program.
    """
    global _support_default_root, _default_root
    _support_default_root = False
    _default_root = None


def _get_default_root(what: str = "create a widget") -> Misc:
    """The implicit root, or an error explaining what to do instead.

    Raises:
        TclError: If there is no root yet, or default roots are switched off.
            tkinter creates one here; TkCurses refuses, because initialising
            curses reconfigures the terminal and must be something the
            application asked for.
    """
    if not _support_default_root:
        raise TclError(
            f"No master specified and tkcurses is configured to not "
            f"support default root; cannot {what}"
        )
    if _default_root is None:
        raise TclError(f"No root window; create a Tk() before trying to {what}")
    return _default_root


# ======================================================================
# Widget base classes
# ======================================================================

#: Short spellings tkinter accepts for the options whose names are long.
#: Tk's own short spellings for long option names. These are *Tcl* synonyms:
#: Tk defines them, they appear in a widget's own option list, and ``cget``
#: takes them. Python-keyword workarounds like ``from_`` are a different thing
#: entirely and are deliberately not here - see :func:`_keyword_option`.
_OPTION_ALIASES: dict[str, str] = {
    "bg": "background",
    "fg": "foreground",
    "bd": "borderwidth",
}


def _keyword_option(
    name: str, spec: dict[str, Any], synonyms: dict[str, str] | None = None
) -> str:
    """The option a keyword argument names, allowing for Python's keywords.

    Tk's ``-from`` cannot be written ``from=2`` in Python, so tkinter lets a
    keyword carry one trailing underscore and strips it:
    ``Misc._options`` does ``if k[-1] == '_': k = k[:-1]``. That is a rule
    about *keywords*, not an alias - which is the distinction this library had
    lost. ``from_`` was stored as the canonical name, so ``configure()``
    reported ``from_`` where tkinter reports ``from``, and
    ``w.configure()["from"]`` raised KeyError here while working in tkinter.

    Measured on Tcl/Tk 9.0.2, and the asymmetry is the whole point:

    =====================  ============  ===========
    asked for as            ``from``      ``from_``
    =====================  ============  ===========
    in ``configure()``      yes           no
    ``cget``                yes           TclError
    keyword argument        yes           yes
    =====================  ============  ===========

    So the underscore is stripped here, on the keyword path, and nowhere else.
    ``cget`` resolves :data:`_OPTION_ALIASES` only, which is why
    ``cget("from_")`` now raises as tkinter's does. TkCurses-y5q.
    """
    table = _OPTION_ALIASES if synonyms is None else synonyms
    option = table.get(name, name)
    if option not in spec and option.endswith("_") and option[:-1] in spec:
        return option[:-1]
    return option


#: Merged option specifications, keyed by class. Walking the MRO on every
#: ``configure`` call would be wasted work; the spec cannot change once the
#: class exists.
_SPEC_CACHE: dict[type, dict[str, Any]] = {}


class BaseWidget(Misc):
    """A widget: a named node in the tree with a set of options.

    Subclasses declare what they accept in ``_widget_options``, a mapping of
    option name to default. The sets are merged down the inheritance chain, so
    a widget lists only what it adds to the standard set below.

    An option not in the merged set is an error, at construction and at
    ``configure`` time alike. tkinter gets that from Tcl's widget definitions;
    without them the check has to be explicit, and it is worth having — a
    misspelled option that silently does nothing is a long afternoon.
    """

    #: Tk's short spellings for this class's options. A *class* attribute and
    #: not a module constant, because the synonyms are per widget: measured on
    #: Tcl/Tk 9.0.2, ``tk.Entry`` takes ``vcmd`` while ``ttk.Entry`` refuses it
    #: although both have ``validatecommand``, and no themed widget has a
    #: synonym at all - ``ttk.Label(bg="red")`` raises. A single global table
    #: got both directions wrong: it was missing ``vcmd`` on the classic
    #: widgets and offering ``bg`` on the themed ones. The most derived
    #: declaration wins, so ttk's mixin empties it. TkCurses-oe5.
    _option_synonyms: ClassVar[dict[str, str]] = _OPTION_ALIASES

    #: Options every widget accepts. The set is deliberately smaller than
    #: tkinter's: X11 options with no cell equivalent (screen distances in
    #: pixels) are left out rather than accepted and ignored, so that setting
    #: one fails loudly instead of quietly.
    #:
    #: **The focus highlight ring is the exception** (TkCurses-gm66.1). Its
    #: three options are accepted, stored and answered, and draw nothing:
    #: every widget that takes the focus already shows it with a cue sized to
    #: a cell - brackets on a Button, an underline on a Checkbutton or a
    #: Listbox row, a bold border on an Entry, a reversed sash - and that cue
    #: stays whatever these say. Refusing them stopped programs at the line,
    #: and they are among the most common options tkinter code sets: usually
    #: ``highlightthickness=0``, to hide X11's ring for looks. Honouring that
    #: by hiding the cue would leave a terminal user no sign of where the
    #: keyboard is. The thickness defaults to Tk's, 1 on the widgets that take
    #: the focus and 0 here; the colours to "", as every colour here does.
    _widget_options: ClassVar[dict[str, Any]] = {
        "background": "",
        "borderwidth": 0,
        "cursor": "",
        "foreground": "",
        "highlightbackground": "",
        "highlightcolor": "",
        "highlightthickness": 0,
        "padx": 0,
        "pady": 0,
        "relief": FLAT,
        # False, because a widget with nothing to do with the keyboard must
        # not be a place the focus can land: Tab stopping on a Frame or a
        # Label shows the user nothing and looks like the focus vanished.
        # Widgets that answer the keyboard turn it back on for themselves,
        # which is how tkinter's "decide by class" default behaves in
        # practice.
        "takefocus": False,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget. Defaults to the implicit root, which must
                already exist; see :func:`_get_default_root`.
            cnf: Options as a dictionary, for names that are not identifiers.
            name: Path component for this widget, generated when omitted.
            **kw: Options as keywords.

        Raises:
            TclError: If an option is not one this widget accepts, or if no
                master was given and there is no root window.
        """
        if master is None:
            master = _get_default_root(f"create a {type(self).__name__}")
        super().__init__(master, name)
        given = _given(cnf, kw)
        self._options = self._initial_options(given)
        self._takefocus = bool(self._options.get("takefocus", False))
        self._takefocus_given = "takefocus" in given

    # ------------------------------------------------------------ options

    @classmethod
    def _option_spec(cls) -> dict[str, Any]:
        """Every option this class accepts, with defaults, merged down the MRO."""
        cached = _SPEC_CACHE.get(cls)
        if cached is None:
            spec: dict[str, Any] = {}
            for klass in reversed(cls.__mro__):
                spec.update(vars(klass).get("_widget_options", {}))
            cached = _SPEC_CACHE[cls] = spec
        return cached

    def _initial_options(self, given: dict[str, Any]) -> dict[str, Any]:
        """Resolve this widget's starting options.

        Three sources, weakest first: the class's declared defaults, then the
        option database, then whatever the caller passed. That ordering is
        what makes ``option_add("*Button.relief", "raised")`` reach a button
        that did not ask for a relief while leaving alone one that did.
        """
        spec = self._option_spec()
        options = dict(spec)
        for name in spec:
            from_database = self.tk.options.get(self._w, self.winfo_class(), name)
            if from_database is not None:
                options[name] = from_database
        options.update(self._checked(given))
        return options

    def _configured_menubar(self, given: dict[str, Any]) -> None:
        """Attach a menubar when one is set through the ``menu`` option.

        Only Tk and Toplevel have that option, and only they have the method
        - so the check is for both rather than for the class, which keeps
        BaseWidget from having to know about windows.
        """
        if "menu" in given and hasattr(self, "_attach_menubar"):
            self._attach_menubar()

    def _checked(self, given: dict[str, Any]) -> dict[str, Any]:
        """Resolve aliases and reject anything this widget does not accept."""
        spec = self._option_spec()
        resolved: dict[str, Any] = {}
        for name, value in given.items():
            option = _keyword_option(name, spec, self._option_synonyms)
            if option not in spec:
                raise TclError(f'unknown option "-{name}"')
            check = _OPTION_VALUES.get(option)
            resolved[option] = value if check is None else check(self, value)
        return resolved

    def _cursor_style(self) -> CursorStyle:
        """What this widget asks of the terminal's cursor while it has the focus.

        Tk draws its own cursor and these options shape it. Here the cursor is
        the terminal's, as the person set it up (UAT 43, TkCurses-lw2), so an
        option left at Tk's default asks for nothing. One a program changed
        asks for the nearest thing a terminal has (TkCurses-gm66.2):

        - ``blockcursor`` on a Text: a block over the character, as Tk draws.
        - ``insertwidth`` at anything but Tk's 2: a bar, which is Tk's shape
          at every width. A terminal cell has no width to give it.
        - ``insertofftime`` of 0 or less: a cursor that does not blink, which
          is what Tk's manual says 0 means. Asked alone, it is a steady *bar*,
          because that is the cursor Tk would be drawing.
        - ``insertbackground``: the cursor's colour.

        ``insertontime``'s length and ``insertborderwidth``'s 3-D edge have no
        terminal request, nor has the blink's speed, and ``insertunfocussed``
        would need a second cursor; they are stored and answered only.
        """
        options = self._options
        if "insertwidth" not in options:
            return TERMINALS_OWN
        block = bool(options.get("blockcursor", 0))
        steady = _as_int(options["insertofftime"], 300) <= 0
        reshaped = _as_int(options["insertwidth"], _TK_INSERT_WIDTH) != _TK_INSERT_WIDTH
        shape = None
        if block or reshaped or steady:
            shape = (2 if steady else 1) if block else (6 if steady else 5)
        colour = None
        if options["insertbackground"]:
            red, green, blue = (
                channel // 257
                for channel in self.winfo_rgb(options["insertbackground"])
            )
            colour = f"#{red:02x}{green:02x}{blue:02x}"
        return CursorStyle(shape=shape, colour=colour)

    def _selection_attribute(
        self, attribute: int, foreground: Any = None, background: Any = None
    ) -> int:
        """How selected text is drawn: in the colours given, else reversed.

        ``foreground`` and ``background`` default to ``selectforeground`` and
        ``selectbackground``. With neither set, or no colour on the terminal,
        the selection is reversed, as it was before Tk's options were taken
        (TkCurses-gm66.3). One set alone keeps the widget's colour for the
        other, as a Text tag does.
        """
        options = self._options
        if foreground is None:
            foreground = options.get("selectforeground", "")
        if background is None:
            background = options.get("selectbackground", "")
        if self.tk.colors is None or not (foreground or background):
            return attribute | _curses.A_REVERSE
        return self._coloured(attribute, foreground, background)

    #: The options that colour each state, as ``(foreground, background)``
    #: option names, either of which may be None. See ``_in_state``.
    _STATE_COLOURS: ClassVar[dict[str, tuple[str | None, str | None]]] = {}

    def _coloured(self, attribute: int, foreground: Any, background: Any) -> int:
        """``attribute`` wearing these colours, the widget's own for a ``""``.

        Unchanged when neither is given or the terminal has no colour.
        """
        colors = self.tk.colors
        if colors is None or not (foreground or background):
            return attribute
        options = self._options
        return with_colors(
            attribute,
            colors.attribute_for(
                str(foreground or options.get("foreground") or "white"),
                str(background or options.get("background") or "black"),
            ),
        )

    def _state_colours(self, state: str) -> tuple[Any, Any] | None:
        """The colours a program gave ``state``, or None if it gave none.

        None too on a terminal with no colour, where they cannot be shown.
        """
        names = self._STATE_COLOURS.get(state)
        if names is None or self.tk.colors is None:
            return None
        foreground, background = (
            self._options.get(name, "") if name else "" for name in names
        )
        return (foreground, background) if foreground or background else None

    def _in_state(self, attribute: int, state: str | None = None) -> int:
        """``attribute`` as this widget looks in ``state``, its own by default.

        In the colours a program gave the state - ``activebackground``,
        ``disabledforeground`` and the rest - and otherwise reversed or dimmed
        as ``for_state`` has always drawn it. Tk's defaults for these are
        real colours; here they are ``""``, so a program that gives none
        looks as it did before they were taken (TkCurses-gm66.4).
        """
        if state is None:
            state = str(self._options.get("state", "normal"))
        colours = self._state_colours(state)
        if colours is not None:
            return self._coloured(attribute, *colours)
        with contextlib.suppress(ValueError):
            return for_state(state, attribute)
        return attribute

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, or return them all when called with none.

        Raises:
            TclError: If an option is not one this widget accepts.
        """
        given = _given(cnf, kw)
        if not given:
            return dict(self._options)
        self._options.update(self._checked(given))
        if "takefocus" in given:
            self._takefocus = bool(self._options["takefocus"])
            self._takefocus_given = True
        self._configured_menubar(given)
        return None

    config = configure

    def cget(self, key: str) -> Any:
        """The value of one option, accepting the short spellings.

        Raises:
            TclError: If this widget has no such option.
        """
        option = self._option_synonyms.get(key, key)
        try:
            return self._options[option]
        except KeyError:
            raise TclError(f'unknown option "-{key}"') from None

    def keys(self) -> list[str]:
        """The option names this widget accepts, sorted."""
        return sorted(self._option_spec())

    def _configure_query(self, key: str) -> tuple[Any, ...]:
        """``configure(key)``: Tk's five-tuple for one option.

        Measured on Tk 9.0.2, a short spelling answers the FULL entry under the
        full name - ``configure("bg")`` is ``("background", "background",
        "Background", ...)``, not the two-tuple ``configure()`` lists for
        ``bg`` - and the name is taken as it stands: ``configure("-text")`` is
        ``unknown option "--text"``, as ``cget`` already refuses it.

        The database name and class are Tk's, from
        :mod:`tkcurses._core.option_names`. The default is this library's own,
        which is not always Tk's: colours and sizes here are cells and curses
        colours, not pixels and X colours.
        """
        value = self.cget(key)
        option = self._option_synonyms.get(key, key)
        return (
            option,
            *database_names(self._database_class(), option),
            self._option_spec().get(option, ""),
            value,
        )

    @classmethod
    def _database_class(cls) -> str:
        """Which of Tk's widget classes this is, for its database names.

        The nearest along the MRO, so a program's own subclass of
        ``ttk.Entry`` answers as a ttk Entry. ``""`` when there is none.
        """
        for klass in cls.__mro__:
            prefix = "ttk" if klass.__module__ == "tkcurses.ttk" else "tk"
            name = f"{prefix}.{klass.__name__}"
            if name in WIDGET_CLASSES:
                return name
        return ""

    # ---------------------------------------------------------- lifecycle

    @property
    def _window(self) -> Any:
        """The curses window behind this widget, or None if it has no panel."""
        return None if self._panel is None else self._panel.window

    def _allocate(self, rect: Rect) -> None:
        """Give the widget the region a geometry manager decided on.

        Called by pack, grid and place, and by a resize that moves things
        around. The widget records the region whether or not there is a panel
        stack to build on: layout is decided before curses exists, and the
        window follows once it does.

        An empty region is how a manager says "no room for this" - it drops
        the window rather than asking curses for a zero-sized one, which
        curses refuses.
        """
        previous, self._rect = self._rect, rect
        if rect != previous:
            # tkinter raises <Configure> whenever a widget's size or position
            # changes, however it changed - geometry(), a manager, minsize, a
            # terminal resize. _allocate is the one place all of those meet,
            # so it is the one place this belongs.
            #
            # Only on a real change, which is what keeps a handler that calls
            # geometry() from recurring: its second call sets the same rect,
            # that is not a change, and nothing fires. Measured against Tk
            # 9.0.2, where such a handler produces two events and stops.
            self.event_generate(
                "<Configure>",
                width=rect.width,
                height=rect.height,
                x=rect.x,
                y=rect.y,
            )
        resized = (rect.width, rect.height) != (previous.width, previous.height)
        if resized:
            # How much of the content is visible is a function of the size, so
            # a scrollbar told before the widget had its final size was told a
            # fraction computed against the wrong height. Nothing corrected
            # it, and the ordinary idiom - create, fill, lay out - is the
            # broken order, so the common case was the wrong one.
            self._report_scroll_view()
        if resized and self._layout_manager is not None:
            # A container given a new size has to place its children again.
            # Propagation travels upward - what a widget needs - and this is
            # the other direction: what it was actually given. Without it a
            # container laid out before its own parent keeps children sized
            # against a region it no longer has.
            self.tk.layout.invalidate(self)
        if not self._sync_window():
            if resized and self._panel is not None:
                # The window did not change, because the screen edge was
                # already clipping it to the same few cells - but the widget
                # is a different size now and draws itself differently, so
                # the border it puts at its own right edge moves even though
                # nothing about the window did.
                self._redraw()
            return
        # The widget's window has changed and its descendants' have not:
        # their rects are offsets from this one and so did not change, which
        # is exactly why nothing above tells them anything. A container that
        # moves without changing size does not lay its children out again,
        # and one that goes off screen is not laid out at all - so without
        # this the children stay drawn where the container used to be.
        for widget in self._subtree():
            # A subtree is typed as Misc, and only a widget has a window; the
            # root is the one Misc that is not a widget, and it is nobody's
            # descendant.
            if widget is not self and isinstance(widget, BaseWidget):
                widget._sync_window()

    def _report_scroll_view(self) -> None:
        """Tell any scrollbar where the view is now. A no-op unless scrollable.

        Overridden by the widgets that have a view to report - Listbox, Text
        and Canvas - so that :meth:`_allocate` has one thing to call without
        knowing which widgets those are.
        """

    def _sync_window(self) -> bool:
        """Put this widget's curses window where its geometry now says.

        Returns:
            True if the window changed at all - made, dropped, moved or
            rebuilt - so that anything positioned relative to it has to be
            seen to as well. A widget that goes off screen counts: its own
            window is dropped, and the descendants whose windows are drawn
            over the same cells would otherwise stay exactly where they
            were, which is a label left behind on top of whatever is now in
            its place.
        """
        stack = self.tk.panels
        if stack is None:
            return False
        if not self._viewable:
            # Inside something that is not on screen. The widget keeps its
            # geometry and gets its window back when the ancestor returns -
            # the same treatment as one scrolled off the edge. Without this a
            # layout pass gives every hidden notebook page's contents a fresh
            # window, and two pages are drawn at once. TkCurses-mlw.
            return self._drop_window()
        if self._rect.is_empty:
            return self._drop_window()
        if self._panel is None:
            if self._mapped:
                self._create_window()
                return self._panel is not None
            return False
        # Compared against where the panel actually is, not against the
        # widget's previous rect: a rect is an offset from the master, so an
        # ancestor moving relocates the panel without changing it.
        target = self._visible_rect()
        if target.is_empty:
            # Entirely off screen. The widget keeps its geometry and gets its
            # window back when it comes into view again.
            return self._drop_window()
        current = self._panel.rect
        if (target.width, target.height) != (current.width, current.height):
            # Curses cannot resize a window in place, and replacing it is also
            # what keeps a shrink from leaving the vacated cells behind.
            stack.replace_window(self._panel, target)
            self._redraw()
            return True
        if (target.x, target.y) != (current.x, current.y):
            stack.move(self._panel, target.x, target.y)
            self._redraw()
            return True
        return False

    def _drop_window(self) -> bool:
        """Release this widget's window and say whether there was one."""
        had_one = self._panel is not None
        self._destroy_window()
        return had_one

    def _map(self) -> None:
        """Put the widget on screen, creating its window if it has none.

        Idempotent: a geometry manager may re-map a widget it has already
        placed, and mapping twice should not raise ``<Map>`` twice.
        """
        if self._mapped:
            return
        self._mapped = True
        self._create_window()
        self._show_subtree()
        if not self._viewable:
            # Mapped, but inside something that is not: the widget belongs on
            # screen and cannot be seen yet. Tk keeps these apart as *mapped*
            # and *viewable*, and without the distinction a layout pass puts
            # the contents of every hidden notebook page back on the screen -
            # which is exactly what it did.
            self._hide_subtree()
            if self._panel is not None:
                self.tk.panels.hide(self._panel)  # type: ignore[union-attr]
            return
        self.event_generate("<Map>")

    @property
    def _viewable(self) -> bool:
        """True when this widget and every ancestor of it is mapped.

        Tk's rule. ``_mapped`` says whether the widget wants to be on screen;
        this says whether it can be, which is a property of the whole chain
        above it.
        """
        widget: Misc | None = self.master
        while widget is not None:
            if isinstance(widget, BaseWidget) and not widget._mapped:
                return False
            widget = widget.master
        return True

    def _show_subtree(self) -> None:
        """Put the panels of everything inside this widget back on screen.

        The counterpart of :meth:`_hide_subtree`. A child that was unmapped
        in its own right stays away: its ``_mapped`` is false, and this only
        shows the ones whose absence was their ancestor's doing. That is Tk's
        distinction between *mapped* and *viewable* - a widget is viewable
        only when it and every ancestor is mapped.
        """
        stack = self.tk.panels
        if stack is None:
            return
        for widget in self._subtree():
            if widget is self or not isinstance(widget, BaseWidget):
                continue
            if not widget._mapped:
                continue
            if widget._panel is None:
                # It gave its window up while it could not be seen - a child
                # laid out before its container was mapped does exactly that -
                # so it needs building rather than merely unhiding.
                widget._sync_window()
            elif widget._panel is not None:
                stack.show(widget._panel)
        # And put them back above this widget's own panel, which was created
        # after theirs and would otherwise be drawn over its own contents -
        # the same rule _restack_descendants keeps for raising and lowering.
        self._restack_descendants(stack)

    def _hide_subtree(self) -> None:
        """Take the panels of everything inside this widget off screen.

        A child draws on its own panel, so hiding only this widget's leaves
        every label and field inside it exactly where it was - measured, a
        notebook showed two pages at once. TkCurses-mlw, and the third time
        this shape has bitten: see also ``_restack_descendants`` and the
        descendant loop in ``_allocate``.
        """
        stack = self.tk.panels
        if stack is None:
            return
        for widget in self._subtree():
            if widget is self or not isinstance(widget, BaseWidget):
                continue
            if widget._panel is not None:
                stack.hide(widget._panel)

    def _unmap(self) -> None:
        """Take the widget off screen, keeping its window for a later map.

        The window is hidden rather than destroyed, because an unmapped
        widget is usually on its way back - a notebook tab, a hidden frame -
        and rebuilding the window each time would throw away its contents.
        """
        # Before the guard, not after it. A container may itself never have
        # been mapped while the children inside it were - a notebook page
        # laid out once and then put away - and returning early left every
        # one of them on screen.
        self._hide_subtree()
        if not self._mapped:
            return
        self._mapped = False
        if self._panel is not None:
            self.tk.panels.hide(self._panel)  # type: ignore[union-attr]
        if self.tk.focus is self:
            # A widget that is no longer on screen must not keep the
            # keyboard. Left holding it, every key afterwards is delivered to
            # something nobody can see and every binding further out - the
            # Escape that closes the application, most of all - stops firing.
            self.tk.focus = None
        self.event_generate("<Unmap>")

    def _create_window(self) -> None:
        """Allocate this widget's panel, if it can have one yet.

        Silent when there is no stack or no region: both mean "not yet", and
        the widget will get its window when :meth:`_allocate` or :meth:`_map`
        next finds the other half in place.
        """
        stack = self.tk.panels
        if stack is None or self._rect.is_empty:
            return
        visible = self._visible_rect()
        if visible.is_empty:
            return
        if self._panel is None:
            self._panel = stack.new_panel(visible, userptr=self)
            # A panel goes on top of the stack when it is made, and windows
            # are made in layout order, which is not tree order: a container
            # laid out after its own children would sit in front of them and
            # hide them behind an empty window. Tree order is re-imposed each
            # time rather than relying on the order things happened to be
            # created in.
            self._root()._restack_panels()
        else:
            stack.show(self._panel)
        self._redraw()

    def _destroy_window(self) -> None:
        """Release this widget's panel.

        Safe to call on a widget that never had one, which is what makes
        destroy() able to call it unconditionally.
        """
        if self._panel is None:
            return
        stack = self.tk.panels
        if stack is not None:
            stack.destroy(self._panel)
        self._panel = None

    def _restack(self, other: Misc | None, above: bool) -> None:
        """Reorder among siblings, and move the window with it.

        Sibling order is the model; the panel stack is what the terminal
        shows. Changing one without the other leaves a widget that claims to
        be in front while drawing behind.
        """
        super()._restack(other, above)
        stack = self.tk.panels
        if stack is None or self._panel is None:
            return
        target = getattr(other, "_panel", None) if other is not None else None
        if target is None:
            if above:
                stack.raise_to_top(self._panel)
            else:
                stack.lower_to_bottom(self._panel)
        elif above:
            stack.raise_above(self._panel, target)
        else:
            stack.lower_below(self._panel, target)
        self._restack_descendants(stack)

    def _restack_descendants(self, stack: PanelStack) -> None:
        """Carry the children along, so the widget does not bury its own.

        A child draws on its own panel *above* its container's - that is what
        makes a label visible inside a frame at all. Moving only the
        container's panel therefore puts the container's own blank interior
        in front of everything it contains: measured, raising a Toplevel left
        a window with a border, a title, and nothing else. Every label, every
        grip, gone, and not left behind at the old position either - simply
        covered.

        Chaining rather than raising each to the top, and from the container
        upward: that keeps the subtree's own order intact and works for
        lowering as well, where the children have to come down and stay just
        above the parent rather than be left at the front.
        """
        previous = self._panel
        if previous is None:
            return
        for widget in self._subtree():
            if widget is self or not isinstance(widget, BaseWidget):
                continue
            panel = widget._panel
            if panel is None:
                continue
            stack.raise_above(panel, previous)
            previous = panel

    def destroy(self) -> None:
        """Destroy the widget, its children, and their windows.

        Children go first - Misc sees to that - so a panel is never left
        pointing at a destroyed parent, and this widget's own window is
        released last.
        """
        if self._destroyed:
            return
        super().destroy()
        self._destroy_window()


# ======================================================================
# Geometry managers
# ======================================================================


class Pack:
    """Packing: place a widget against one edge of what space is left.

    The mixin half of the pack manager. The arithmetic is in
    :mod:`tkcurses._core.pack`; what is here is the tkinter-shaped API and the
    checking that goes with it.
    """

    if TYPE_CHECKING:
        # Supplied by the widget this is mixed into, declared so the contract
        # is visible and the mixin still type-checks on its own.
        master: Misc | None

        # The rest of what a geometry manager needs of the widget this is
        # mixed into - see _core.geometry.Managed, which names exactly these
        # four. Only master was declared, so handing self to the manager
        # type-checked against nothing at all. TkCurses-d40.
        def winfo_reqwidth(self) -> int: ...
        def winfo_reqheight(self) -> int: ...
        def _allocate(self, rect: Rect) -> None: ...

        _manager: str
        _manager_container: Misc | None

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...
        def _managed_layout(self, name: str) -> Layout | None: ...
        def _leave_layout(self, container: Misc) -> None: ...

    def pack_configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Pack this widget into its container.

        Args:
            cnf: Options as a dictionary, merged with the keywords.
            **kw: ``side``, ``fill``, ``expand``, ``anchor``, ``padx``,
                ``pady``, ``ipadx``, ``ipady``, plus ``in_`` to pack into
                something other than the master, and ``before``/``after`` to
                place this widget in the packing order.

        Raises:
            TclError: If an option or its value is not one Tk accepts, or if
                the container is already managed by a different manager.
        """
        options = _given(cnf, kw)
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot pack the root window")
        before = options.pop("before", None)
        after = options.pop("after", None)

        layout = _pack_layout_of(container)
        current = self._managed_layout("pack")
        remembered = (
            current.options_for(self) if isinstance(current, PackLayout) else None
        )
        # A geometry call naming a different container is a move, and the
        # container being left has to stop laying this widget out.
        previous = self._manager_container
        if previous is not None and previous is not container:
            self._leave_layout(previous)
        layout.add(self, _pack_options(options, remembered), before=before, after=after)
        self._manager = "pack"
        self._manager_container = container
        self._map()
        container.tk.layout.invalidate(container)

    pack = pack_configure

    def pack_forget(self) -> None:
        """Stop packing this widget and take it off the screen.

        Its packing options are forgotten, which is what will separate this
        from ``grid_remove``: packing it again starts from the defaults.
        """
        container = self._manager_container or self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, PackLayout):
            manager.remove(self)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._manager_container = None
        self._unmap()

    forget = pack_forget

    def pack_info(self) -> dict[str, Any]:
        """How this widget is packed.

        Raises:
            TclError: If it is not packed. Tk reports that rather than
                returning defaults, which would read as though it were.
        """
        container = self._manager_container or self.master
        manager = container._layout_manager if container is not None else None
        options = manager.options_for(self) if isinstance(manager, PackLayout) else None
        if options is None:
            raise TclError(f'window "{self}" is not packed')
        return {
            "in": container,
            "side": options.side,
            "fill": options.fill,
            "expand": options.expand,
            "anchor": options.anchor,
            "padx": options.padx.value,
            "pady": options.pady.value,
            "ipadx": options.ipadx,
            "ipady": options.ipady,
        }

    info = pack_info


#: What each layout class is called in the error a mixed container raises.
_MANAGER_NAMES = {
    "PackLayout": "pack",
    "GridLayout": "grid",
    "PlaceLayout": "place",
    "PanedLayout": "paned",
}


def _pack_layout_of(container: Misc) -> PackLayout:
    """The container's pack manager, created on first use.

    Raises:
        TclError: If the container is already laid out by a different manager.
            Tk refuses the same mixture: two managers each deciding where the
            same children go is not a layout.
    """
    manager = container._layout_manager
    if manager is None:
        manager = PackLayout()
        container._layout_manager = manager
        return manager
    if not isinstance(manager, PackLayout):
        other = _MANAGER_NAMES.get(type(manager).__name__, type(manager).__name__)
        raise TclError(
            f"cannot use geometry manager pack inside {container} which already "
            f"has slaves managed by {other}"
        )
    return manager


def _pack_options(
    given: dict[str, Any], remembered: PackOptions | None = None
) -> PackOptions:
    """Build and check one widget's packing options.

    Args:
        given: The options named in this call.
        remembered: The options the widget already has, which everything not
            named keeps. None starts from the defaults, which is what a
            widget not currently packed gets.

    Raises:
        TclError: If an option is unknown or its value is not one Tk accepts.
            Checked here rather than left to produce a strange layout later: a
            misspelled ``fill`` is otherwise invisible.
    """
    options = (
        PackOptions(**vars(remembered)) if remembered is not None else PackOptions()
    )
    for name, value in given.items():
        if not hasattr(options, name):
            raise TclError(f'unknown option "-{name}"')
        setattr(options, name, value)

    if options.side not in SIDES:
        raise TclError(f'bad side "{options.side}": must be {", ".join(SIDES)}')
    if options.fill not in FILLS:
        raise TclError(f'bad fill style "{options.fill}": must be {", ".join(FILLS)}')
    try:
        parse_anchor(options.anchor)
    except ValueError as error:
        raise TclError(str(error)) from None
    options.expand = bool(options.expand)
    _check_pads(options, given)
    return options


def _check_pads(options: PackOptions | GridOptions, given: dict[str, Any]) -> None:
    """Parse the four pad options of whichever manager is being configured.

    ``padx``/``pady`` take a distance per side; ``ipadx``/``ipady`` take one
    distance only. The asymmetry is Tk's own, measured rather than assumed:
    Tcl/Tk 9.0.2 accepts ``padx=(2, 8)`` and rejects ``ipadx=(2, 8)`` with
    ``bad ipadx value "2 8": must be positive screen distance``.

    Only options named in this call are re-parsed. Ones the widget already had
    are already :class:`Pad` instances, and feeding a ``Pad`` back through
    :func:`parse_pad` would be a second, lossy conversion.

    Raises:
        TclError: With Tk's wording, for a value Tk would refuse.
    """
    for name in ("padx", "pady"):
        if name not in given:
            continue
        try:
            setattr(options, name, parse_pad(getattr(options, name)))
        except ValueError as error:
            raise TclError(str(error)) from None
    for name in ("ipadx", "ipady"):
        if name not in given:
            continue
        try:
            setattr(options, name, parse_single_pad(getattr(options, name), name))
        except ValueError as error:
            raise TclError(str(error)) from None


class Grid:
    """Gridding: place a widget in a row and a column.

    The mixin half of the grid manager; the sizing is in
    :mod:`tkcurses._core.grid`.
    """

    if TYPE_CHECKING:
        master: Misc | None

        # The rest of what a geometry manager needs of the widget this is
        # mixed into - see _core.geometry.Managed, which names exactly these
        # four. Only master was declared, so handing self to the manager
        # type-checked against nothing at all. TkCurses-d40.
        def winfo_reqwidth(self) -> int: ...
        def winfo_reqheight(self) -> int: ...
        def _allocate(self, rect: Rect) -> None: ...

        _manager: str
        _manager_container: Misc | None

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...
        def _managed_layout(self, name: str) -> Layout | None: ...
        def _leave_layout(self, container: Misc) -> None: ...

    def grid_configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Place this widget in its container's grid.

        Args:
            cnf: Options as a dictionary, merged with the keywords.
            **kw: ``row``, ``column``, ``rowspan``, ``columnspan``,
                ``sticky``, ``padx``, ``pady``, ``ipadx``, ``ipady``, plus
                ``in_`` to grid into something other than the master.

        A bare ``grid()`` on a widget that was hidden with
        :meth:`grid_remove` puts it back where it was.

        Raises:
            TclError: If an option or its value is not one Tk accepts, or the
                container is already managed by a different manager.
        """
        options = _given(cnf, kw)
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot grid the root window")
        layout = _grid_layout_of(container)
        # Two sources, and the live one wins: a widget being reconfigured
        # merges into the options it has now, while one that grid_remove()
        # hid merges into the ones that were kept for it.
        current = self._managed_layout("grid")
        held = current.options_for(self) if isinstance(current, GridLayout) else None
        remembered = held or layout.remembered(self)
        # A geometry call naming a different container is a move, and the
        # container being left has to stop laying this widget out.
        previous = self._manager_container
        if previous is not None and previous is not container:
            self._leave_layout(previous)
        if not options and remembered is not None:
            layout.add(self, remembered)
        else:
            layout.add(self, _grid_options(options, remembered))
        self._manager = "grid"
        self._manager_container = container
        self._map()
        container.tk.layout.invalidate(container)

    grid = grid_configure

    def grid_forget(self) -> None:
        """Take this widget out of the grid and forget where it was."""
        self._ungrid(keep=False)

    def grid_remove(self) -> None:
        """Take this widget out of the grid but remember where it was.

        A later bare ``grid()`` puts it back, which is what makes this the
        way to hide a widget temporarily.
        """
        self._ungrid(keep=True)

    def _ungrid(self, *, keep: bool) -> None:
        """Shared implementation of grid_forget and grid_remove."""
        container = self._manager_container or self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, GridLayout):
            manager.remove(self, keep=keep)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._manager_container = None
        self._unmap()

    def grid_info(self) -> dict[str, Any]:
        """Where this widget sits in the grid.

        Raises:
            TclError: If it is not gridded.
        """
        container = self._manager_container or self.master
        manager = container._layout_manager if container is not None else None
        options = manager.options_for(self) if isinstance(manager, GridLayout) else None
        if options is None:
            raise TclError(f'window "{self}" is not gridded')
        return {
            "in": container,
            "row": options.row,
            "column": options.column,
            "rowspan": options.rowspan,
            "columnspan": options.columnspan,
            "sticky": options.sticky,
            "padx": options.padx.value,
            "pady": options.pady.value,
            "ipadx": options.ipadx,
            "ipady": options.ipady,
        }


def _grid_layout_of(container: Misc) -> GridLayout:
    """The container's grid manager, created on first use.

    Raises:
        TclError: If the container is already laid out by a different manager.
    """
    manager = container._layout_manager
    if manager is None:
        manager = GridLayout()
        container._layout_manager = manager
        return manager
    if not isinstance(manager, GridLayout):
        other = _MANAGER_NAMES.get(type(manager).__name__, type(manager).__name__)
        raise TclError(
            f"cannot use geometry manager grid inside {container} which already "
            f"has slaves managed by {other}"
        )
    return manager


def _grid_options(
    given: dict[str, Any], remembered: GridOptions | None = None
) -> GridOptions:
    """Build and check one widget's grid options.

    Raises:
        TclError: If an option is unknown or its value is not one Tk accepts.
    """
    options = (
        GridOptions(**vars(remembered)) if remembered is not None else GridOptions()
    )
    for name, value in given.items():
        if not hasattr(options, name):
            raise TclError(f'unknown option "-{name}"')
        setattr(options, name, value)

    try:
        parse_sticky(options.sticky)
    except ValueError as error:
        raise TclError(str(error)) from None
    for name in ("row", "column"):
        value = getattr(options, name)
        try:
            setattr(options, name, max(0, int(value)))
        except (TypeError, ValueError):
            raise TclError(f'expected integer but got "{value}"') from None
    _check_pads(options, given)
    for name in ("rowspan", "columnspan"):
        value = getattr(options, name)
        try:
            setattr(options, name, max(1, int(value)))
        except (TypeError, ValueError):
            raise TclError(f'expected integer but got "{value}"') from None
    return options


class Place:
    """Placing: put a widget at a position you choose.

    The mixin half of the place manager; the arithmetic is in
    :mod:`tkcurses._core.place`.
    """

    if TYPE_CHECKING:
        master: Misc | None

        # The rest of what a geometry manager needs of the widget this is
        # mixed into - see _core.geometry.Managed, which names exactly these
        # four. Only master was declared, so handing self to the manager
        # type-checked against nothing at all. TkCurses-d40.
        def winfo_reqwidth(self) -> int: ...
        def winfo_reqheight(self) -> int: ...
        def _allocate(self, rect: Rect) -> None: ...

        _manager: str
        _manager_container: Misc | None

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...
        def _managed_layout(self, name: str) -> Layout | None: ...
        def _leave_layout(self, container: Misc) -> None: ...

    def place_configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Place this widget in its container.

        Args:
            cnf: Options as a dictionary, merged with the keywords.
            **kw: ``x``, ``y``, ``width``, ``height`` in cells; ``relx``,
                ``rely``, ``relwidth``, ``relheight`` as fractions of the
                container; ``anchor``; ``bordermode``; and ``in_`` to place
                into something other than the master.

        Raises:
            TclError: If an option or its value is not one Tk accepts, or the
                container is already managed by a different manager.
        """
        options = _given(cnf, kw)
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot place the root window")
        layout = _place_layout_of(container)
        current = self._managed_layout("place")
        remembered = (
            current.options_for(self) if isinstance(current, PlaceLayout) else None
        )
        # A geometry call naming a different container is a move, and the
        # container being left has to stop laying this widget out.
        previous = self._manager_container
        if previous is not None and previous is not container:
            self._leave_layout(previous)
        layout.add(self, _place_options(options, remembered))
        self._manager = "place"
        self._manager_container = container
        self._map()
        container.tk.layout.invalidate(container)

    place = place_configure

    def place_forget(self) -> None:
        """Stop placing this widget and take it off the screen."""
        container = self._manager_container or self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, PlaceLayout):
            manager.remove(self)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._manager_container = None
        self._unmap()

    def place_info(self) -> dict[str, Any]:
        """How this widget is placed.

        Raises:
            TclError: If it is not placed.
        """
        container = self._manager_container or self.master
        manager = container._layout_manager if container is not None else None
        options = (
            manager.options_for(self) if isinstance(manager, PlaceLayout) else None
        )
        if options is None:
            raise TclError(f'window "{self}" is not placed')
        return {"in": container, **vars(options)}


def _place_layout_of(container: Misc) -> PlaceLayout:
    """The container's place manager, created on first use.

    Raises:
        TclError: If the container is already laid out by a different manager.
    """
    manager = container._layout_manager
    if manager is None:
        manager = PlaceLayout()
        container._layout_manager = manager
        return manager
    if not isinstance(manager, PlaceLayout):
        other = _MANAGER_NAMES.get(type(manager).__name__, type(manager).__name__)
        raise TclError(
            f"cannot use geometry manager place inside {container} which already "
            f"has slaves managed by {other}"
        )
    return manager


def _place_options(
    given: dict[str, Any], remembered: PlaceOptions | None = None
) -> PlaceOptions:
    """Build and check one widget's placement options.

    Args:
        given: The options named in this call.
        remembered: The options the widget already has, which everything not
            named keeps. None starts from the defaults.

    Raises:
        TclError: If an option is unknown or its value is not one Tk accepts.
    """
    options = (
        PlaceOptions(**vars(remembered)) if remembered is not None else PlaceOptions()
    )
    for name, value in given.items():
        if not hasattr(options, name):
            raise TclError(f'unknown option "-{name}"')
        setattr(options, name, value)

    try:
        parse_anchor(options.anchor)
    except ValueError as error:
        raise TclError(str(error)) from None
    if options.bordermode not in BORDERMODES:
        raise TclError(
            f'bad bordermode "{options.bordermode}": must be {", ".join(BORDERMODES)}'
        )
    for name in ("x", "y"):
        options.__dict__[name] = _place_int(name, getattr(options, name))
    for name in ("width", "height"):
        value = getattr(options, name)
        if value is not None:
            # Not clamped here: a negative width is meaningful alongside
            # relwidth, and the result is clamped once it has been used.
            options.__dict__[name] = _place_int(name, value)
    for name in ("relx", "rely", "relwidth", "relheight"):
        value = getattr(options, name)
        if value is None:
            continue
        try:
            options.__dict__[name] = float(value)
        except (TypeError, ValueError):
            raise TclError(
                f'expected floating-point number but got "{value}"'
            ) from None
    return options


def _place_int(name: str, value: Any) -> int:
    """Parse one of place's cell-valued options.

    Raises:
        TclError: If it is not a whole number.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise TclError(f'bad {name} value "{value}"') from None


class Widget(BaseWidget, Pack, Grid, Place):
    """The base class for every ordinary widget.

    In tkinter this is where the three geometry managers are mixed in
    (``Widget(BaseWidget, Pack, Place, Grid)``); those arrive with the
    geometry manager epic, and this class is where they will attach. Until
    then it is what separates a widget that a manager can place from a
    toplevel that manages itself.
    """


# ======================================================================
# Window manager
# ======================================================================

#: A geometry string: ``WxH``, ``+X+Y``, or both. A leading ``-`` on an offset
#: measures from the right or bottom edge, as in Tk.
_GEOMETRY_RE = re.compile(
    r"^(?:(?P<width>\d+)x(?P<height>\d+))?"
    r"(?:(?P<x>[+-]-?\d+)(?P<y>[+-]-?\d+))?$"
)

#: Window states Tk recognises.
_WM_STATES = ("normal", "iconic", "withdrawn")

#: Attributes wm_attributes understands. Tk's list is mostly X11 compositing
#: and has no meaning for a character cell window; these two do.
_WM_ATTRIBUTES = ("-topmost", "-fullscreen")


class Wm:
    """Window manager methods for a toplevel.

    There is no window manager. A terminal has one surface, no title bars, no
    close buttons and no stacking policy beyond what this library imposes, so
    every method here is the library doing for itself what an X11 window
    manager would otherwise do.

    Two consequences run through the whole class. **A window is always
    inside the terminal**, because there is nowhere for it to overflow to -
    an invariant rather than a courtesy, held by routing every path that
    moves or resizes a window through :meth:`_within_screen`, and
    re-established by :meth:`_reposition_for_screen` when the terminal itself
    changes size. And nothing raises ``WM_DELETE_WINDOW`` on its own: no user
    gesture closes a window here, so an application that wants the protocol
    must invoke it.

    The invariant used to be only established, never maintained: the clamp
    lived in ``_apply_geometry`` and so held against whatever the screen was
    when geometry was last set. A window could then report a position its own
    setter would refuse to produce.
    """

    if TYPE_CHECKING:
        # Supplied by the widget this is mixed into. Declared so the contract
        # is visible and so a mixin referring to them still type-checks.
        tk: Application
        _rect: Rect
        _options: dict[str, Any]
        _is_toplevel: bool

        _menubar_bound: bool
        _menubar_shown: Menu | None

        @property
        def _border_drawn(self) -> bool: ...

        def bind(
            self,
            sequence: str | None = None,
            func: Callable[[Event], Any] | None = None,
            add: bool | str | None = None,
        ) -> Any: ...
        def _allocate(self, rect: Rect) -> None: ...
        def _map(self) -> None: ...
        def _unmap(self) -> None: ...
        def _screen_size(self) -> tuple[int, int]: ...
        def winfo_exists(self) -> bool: ...
        def tkraise(self, aboveThis: Misc | None = None) -> None: ...
        def _invalidate_layout(self) -> None: ...

    def _attach_menubar(self) -> None:
        """Lay the window's ``menu`` across its top row, and keep it there.

        The menubar is a Menu like any other, drawn in a row instead of a
        box. It is positioned here rather than by a geometry manager because
        it is not part of the layout: the window takes its row away from the
        children first, and what is left is what they are offered. A
        ``<Configure>`` binding re-places it, so the bar follows the window
        when the terminal is resized.
        """
        bar = _menubar_of(self)
        old = self._menubar_shown
        if old is not None and old is not bar:
            # Replaced or removed: the old bar goes back to being an ordinary
            # menu, off screen, and its row goes back to the children. Left
            # alone it stayed drawn and live on top of whatever took the row.
            old._as_menubar = False
            if old.winfo_exists():
                old._unmap()
            self._invalidate_layout()
        self._menubar_shown = bar
        if bar is None:
            return
        if old is None:
            self._invalidate_layout()
        if not self._menubar_bound:
            self._menubar_bound = True
            self.bind("<Configure>", lambda _event: self._place_menubar(), add=True)
        self._place_menubar()

    def _place_menubar(self) -> None:
        """Put the menubar across the top of this window's border."""
        bar = self._menubar_shown
        if bar is None or not bar.winfo_exists():
            return
        bar._as_menubar = True
        bar._apply_requested_size()
        edge = BORDER_WIDTH if self._border_drawn else 0
        bar._allocate(Rect(edge, edge, max(0, self._rect.width - 2 * edge), 1))
        bar._map()
        bar._redraw()

    def _setup_wm(self) -> None:
        """Initialise the window manager state.

        Called from the constructor of each window class rather than from an
        ``__init__`` here: the mixin has no say in the order a widget builds
        itself, and these defaults have to be in place before geometry is.
        """
        self._menubar_bound = False
        self._menubar_shown = None
        self._title = ""
        self._protocols: dict[str, Callable[[], Any]] = {}
        self._min_size: tuple[int, int] = (1, 1)
        self._max_size: tuple[int, int] | None = None
        self._resizable: tuple[bool, bool] = (True, True)
        self._wm_state = "normal"
        self._transient_for: Misc | None = None
        self._overrideredirect = False
        self._focus_model = "passive"
        self._grid_spec: tuple[int, int, int, int] | None = None
        self._topmost = False
        self._fullscreen = False

    # ------------------------------------------------------------- titling

    def wm_title(self, string: str | None = None) -> str:
        """Get or set the window's title.

        A toplevel draws it centred on its top border, which is the only
        title bar available. The root has nowhere to put one and keeps it as
        a label only.
        """
        if string is not None:
            self._title = str(string)
            self._redraw_decoration()
        return self._title

    title = wm_title

    # ------------------------------------------------------------ geometry

    def wm_geometry(self, newGeometry: str | None = None) -> str:
        """Get or set size and position as ``WxH+X+Y``, in cells.

        Accepts the partial forms Tk does - ``80x24`` alone, ``+4+2`` alone -
        and a ``-`` offset measuring from the right or bottom edge. The result
        is clamped to the terminal, which a window cannot exceed and outside
        which it cannot be placed.

        Setting has no effect on the root: its size is the terminal's, and
        nothing here can resize that. The call is accepted rather than
        refused, because ``root.geometry("400x300")`` appears in most tkinter
        programs and failing on it would break them for no gain.

        Raises:
            TclError: If the geometry string cannot be parsed.
        """
        if newGeometry is not None and self._is_resizable_window():
            self._apply_geometry(newGeometry)
        rect = self._rect
        return f"{rect.width}x{rect.height}+{rect.x}+{rect.y}"

    geometry = wm_geometry

    #: The geometry the application last asked for, before the screen had its
    #: say. A window displaced by a shrinking terminal returns here when
    #: there is room again; None until geometry() is called.
    _wanted_rect: Rect | None = None

    def _is_resizable_window(self) -> bool:
        """False for the root, whose geometry the terminal decides."""
        return not isinstance(self, Tk)

    def _within_screen(self, rect: Rect) -> Rect:
        """``rect`` brought inside the terminal, size first and then position.

        **The one place that decides where a window may be.** Every path that
        moves or resizes a window goes through here, which is what makes
        "geometry is clamped to the terminal" an invariant rather than
        something that happened to be true when it was last set.

        It was the latter for a long time. The clamp lived inside
        ``_apply_geometry``, so it held against the screen size at the moment
        geometry was set and nothing re-established it afterwards. Two paths
        walked straight past it: a terminal resize, which changes the screen
        rather than the window, and ``minsize``, which grows a window without
        going near ``geometry()``. Measured before this existed, a window at
        ``+30+10`` on a terminal shrunk to 28x8 still reported ``+30+10`` -
        a position ``geometry()`` itself, asked for it, would have refused.

        Size before position, because the position a window can have depends
        on how big it is: clamping x against the old width leaves a window
        hanging off the edge by however much it then shrinks.
        """
        width, height = self._clamp_size(rect.width, rect.height)
        screen_width, screen_height = self._screen_size()
        return Rect(
            clamp(rect.x, 0, max(0, screen_width - width)),
            clamp(rect.y, 0, max(0, screen_height - height)),
            width,
            height,
        )

    def _reposition_for_screen(self) -> None:
        """Put this window back inside a terminal that has changed size.

        Called for every window when the terminal is resized. Two things
        happen, and the second is what keeps the first from being destructive.

        The window is brought inside the new screen, so it cannot end up
        somewhere nothing can reach. That matters most for a modal window:
        measured before this, shrinking the terminal under a dialog left it
        invisible, still holding the grab, and every click in the application
        going to a window nobody could see - a button that looked entirely
        normal and did nothing, with nothing on screen to explain it.

        And the position the application actually asked for is remembered, so
        that growing the terminal again puts the window back where it was
        rather than leaving it wherever a transient shrink pushed it. Without
        that, a one-column shrink and back would quietly rearrange the screen.
        """
        wanted = self._wanted_rect or self._rect
        target = self._within_screen(wanted)
        if target != self._rect:
            self._allocate(target)

    def _apply_geometry(self, spec: str) -> None:
        """Parse a geometry string and move or resize the window to match."""
        match = _GEOMETRY_RE.match(spec.strip())
        if match is None or not any(match.groupdict().values()):
            raise TclError(f'bad geometry specifier "{spec}"')
        screen_width, screen_height = self._screen_size()
        rect = self._rect

        width, height = rect.width, rect.height
        if match["width"] is not None:
            if self._resizable[0]:
                width = int(match["width"])
            if self._resizable[1]:
                height = int(match["height"])
        width, height = self._clamp_size(width, height)

        x, y = rect.x, rect.y
        if match["x"] is not None:
            x = self._edge_offset(match["x"], screen_width, width)
            y = self._edge_offset(match["y"], screen_height, height)
        # What the application asked for, before the screen has its say. This
        # is what the window goes back to if a shrink displaces it and the
        # terminal is later big enough again, and an explicit geometry() call
        # replaces it - a position the application named is the one it meant.
        self._wanted_rect = Rect(x, y, width, height)
        self._allocate(self._within_screen(Rect(x, y, width, height)))

    @staticmethod
    def _edge_offset(token: str, screen: int, extent: int) -> int:
        """Resolve one ``+n`` or ``-n`` offset into a left or top position.

        ``-n`` measures from the far edge, so ``-0`` is flush right and
        ``-10`` leaves ten cells beyond the window.
        """
        value = int(token[1:])
        if token[0] == "-":
            return screen - extent - value
        return value

    def _clamp_size(self, width: int, height: int) -> tuple[int, int]:
        """Hold a size within the window's own limits and the terminal's."""
        screen_width, screen_height = self._screen_size()
        min_width, min_height = self._min_size
        max_width, max_height = self._max_size or (screen_width, screen_height)
        return (
            clamp(width, min_width, min(max_width, screen_width)),
            clamp(height, min_height, min(max_height, screen_height)),
        )

    def wm_minsize(self, width: int | None = None, height: int | None = None) -> Any:
        """Get or set the smallest size this window may be given."""
        if width is None:
            return self._min_size
        self._min_size = (max(1, int(width)), max(1, int(height or 1)))
        self._reapply_size()
        return None

    minsize = wm_minsize

    def wm_maxsize(self, width: int | None = None, height: int | None = None) -> Any:
        """Get or set the largest size this window may be given."""
        if width is None:
            return self._max_size or self._screen_size()
        self._max_size = (int(width), int(height or 1))
        self._reapply_size()
        return None

    maxsize = wm_maxsize

    def wm_resizable(
        self, width: bool | None = None, height: bool | None = None
    ) -> Any:
        """Get or set whether each axis may be resized.

        A locked axis is left alone by :meth:`wm_geometry` rather than making
        the call fail, which is how Tk behaves when a window manager refuses
        a resize.
        """
        if width is None:
            return self._resizable
        self._resizable = (bool(width), bool(height))
        return None

    resizable = wm_resizable

    def _reapply_size(self) -> None:
        """Re-clamp the current size after the limits changed."""
        if not self._is_resizable_window():
            return
        # Through _within_screen rather than _clamp_size alone: a window at
        # the edge that minsize makes bigger has to come back inside, and
        # measured before this it did not - minsize(24, 9) on a 10x4 window
        # at +28+7 of a 40x12 terminal left it hanging 12 columns and 4 rows
        # off the screen, with no resize involved at all.
        target = self._within_screen(self._rect)
        if target != self._rect:
            self._allocate(target)

    def wm_grid(
        self,
        baseWidth: int | None = None,
        baseHeight: int | None = None,
        widthInc: int | None = None,
        heightInc: int | None = None,
    ) -> Any:
        """Get or set the window's size increments.

        Tk uses this to make a window resize in units of a text cell. Here
        every window already does, so this records the request and reports it
        back rather than changing anything.
        """
        if baseWidth is None:
            return self._grid_spec
        self._grid_spec = (
            int(baseWidth),
            int(baseHeight or 0),
            int(widthInc or 1),
            int(heightInc or 1),
        )
        return None

    grid = wm_grid

    # --------------------------------------------------------------- state

    def wm_state(self, newstate: str | None = None) -> str:
        """Get or set the window state: normal, iconic, or withdrawn.

        Iconic and withdrawn both take the window off the screen; they differ
        in intent, and a window manager would show an icon for the first.
        There is nowhere to put an icon, so the two look the same here and
        remain distinct only in what :meth:`wm_state` reports.

        Raises:
            TclError: If the state is not one Tk recognises.
        """
        if newstate is None:
            return self._wm_state
        if newstate not in _WM_STATES:
            raise TclError(f'bad window state "{newstate}"')
        if newstate == "normal":
            self.wm_deiconify()
        elif newstate == "iconic":
            self.wm_iconify()
        else:
            self.wm_withdraw()
        return self._wm_state

    state = wm_state

    def wm_withdraw(self) -> None:
        """Take the window off the screen, forgetting it was ever placed."""
        self._wm_state = "withdrawn"
        self._unmap()

    withdraw = wm_withdraw

    def wm_iconify(self) -> None:
        """Take the window off the screen, as minimising would."""
        self._wm_state = "iconic"
        self._unmap()

    iconify = wm_iconify

    def wm_deiconify(self) -> None:
        """Put the window back on the screen."""
        self._wm_state = "normal"
        self._map()
        self._redraw_decoration()

    deiconify = wm_deiconify

    # ----------------------------------------------------------- protocols

    def wm_protocol(
        self, name: str | None = None, func: Callable[[], Any] | None = None
    ) -> Any:
        """Register, query, or list window manager protocol handlers.

        ``WM_DELETE_WINDOW`` is the one worth having, and **Ctrl-C raises
        it**. A terminal has no close button, but it does have the gesture:
        pressing Ctrl-C on an application that has not bound ``<Control-c>``
        is a user saying "stop this", and :meth:`Tk.mainloop` delivers it
        here. A handler may save, may ask, or may simply return and leave
        the application running; with no handler the default is to close.

        This docstring used to say that nothing raised it, "a terminal
        offers no close button and no user gesture that means close this
        window". The mechanism was right and the gesture had been missed.

        An application may still invoke it directly - :meth:`_invoke_protocol`
        from a key binding, and the dialogs do the same.
        """
        if name is None:
            return tuple(self._protocols)
        if func is None:
            return self._protocols.get(name)
        self._protocols[name] = func
        return None

    protocol = wm_protocol

    def _invoke_protocol(self, name: str) -> bool:
        """Run a registered protocol handler. True if there was one."""
        handler = self._protocols.get(name)
        if handler is None:
            return False
        handler()
        return True

    # -------------------------------------------------------- relationships

    def wm_transient(self, master: Misc | None = None) -> Misc | None:
        """Get or set the window this one is a transient of.

        A transient window belongs to another - a dialog to the window that
        opened it - and follows it: it stays in front of its owner, and goes
        off the screen when the owner does.
        """
        if master is None:
            return self._transient_for
        self._transient_for = master
        self.tkraise(master)
        return None

    transient = wm_transient

    def wm_frame(self) -> str:
        """The window's identifier.

        Tk returns the window manager's frame id, which is a different window
        wrapped around this one. There is no frame, so this is the window's
        own id.
        """
        return str(self.winfo_id())  # type: ignore[attr-defined]

    frame = wm_frame

    def wm_focusmodel(self, model: str | None = None) -> str:
        """Get or set the focus model.

        Recorded rather than acted on: both models describe how a window
        manager hands focus to a window, and focus here never leaves the
        application.

        Raises:
            TclError: If the model is neither "active" nor "passive".
        """
        if model is None:
            return self._focus_model
        if model not in ("active", "passive"):
            raise TclError(f'bad focus model "{model}"')
        self._focus_model = model
        return self._focus_model

    focusmodel = wm_focusmodel

    # ---------------------------------------------------------- decoration

    def wm_overrideredirect(self, boolean: bool | None = None) -> bool:
        """Get or set whether the window manager should ignore this window.

        In Tk this strips the title bar and border a window manager would
        add. The equivalent here is the border the window draws for itself,
        since that is the only decoration there is.
        """
        if boolean is None:
            return self._overrideredirect
        self._overrideredirect = bool(boolean)
        self._redraw_decoration()
        return self._overrideredirect

    overrideredirect = wm_overrideredirect

    def wm_attributes(self, *args: Any) -> Any:
        """Get or set window attributes.

        Two are supported. ``-topmost`` keeps the window in front of the
        others; ``-fullscreen`` makes it the size of the terminal. The rest of
        Tk's list describes X11 compositing - transparency, window type hints -
        and has no meaning for a grid of characters.

        Raises:
            TclError: If an attribute is not one of the supported two.
        """
        if not args:
            return (
                "-topmost",
                self._topmost,
                "-fullscreen",
                self._fullscreen,
            )
        if len(args) == 1:
            return self._attribute(self._checked_attribute(args[0]))
        for name, value in zip(args[::2], args[1::2], strict=False):
            self._set_attribute(self._checked_attribute(name), value)
        return None

    attributes = wm_attributes

    @staticmethod
    def _checked_attribute(name: str) -> str:
        """Validate an attribute name, which Tk spells with a leading dash."""
        if name not in _WM_ATTRIBUTES:
            raise TclError(f'bad attribute "{name}"')
        return str(name)

    def _attribute(self, name: str) -> Any:
        """Read one attribute."""
        return self._topmost if name == "-topmost" else self._fullscreen

    def _set_attribute(self, name: str, value: Any) -> None:
        """Write one attribute, applying what it means."""
        if name == "-topmost":
            self._topmost = bool(value)
            if self._topmost:
                self.tkraise()
            return
        self._fullscreen = bool(value)
        if self._fullscreen and self._is_resizable_window():
            width, height = self._screen_size()
            self._allocate(Rect(0, 0, width, height))

    def _redraw_decoration(self) -> None:
        """Repaint whatever decoration this window draws.

        The root draws none; Toplevel overrides this.
        """

    # ------------------------------------------------------------ reparenting

    def wm_manage(self, widget: Misc) -> None:  # noqa: ARG002 - tkinter signature
        """Turn a managed widget into a toplevel.

        Raises:
            TclError: Always, for now. It means taking a widget away from its
                geometry manager and giving it a window of its own, and there
                are no geometry managers yet to take it from. Tracked as
                TkCurses-113.
        """
        raise TclError(
            "wm_manage needs the geometry managers, which are not implemented "
            "yet (TkCurses-113)"
        )

    manage = wm_manage

    def wm_forget(self, window: Misc) -> None:  # noqa: ARG002 - tkinter signature
        """Turn a toplevel back into a managed widget.

        Raises:
            TclError: Always, for the same reason as :meth:`wm_manage`.
        """
        raise TclError(
            "wm_forget needs the geometry managers, which are not implemented "
            "yet (TkCurses-113)"
        )

    forget = wm_forget


# ======================================================================
# The root window
# ======================================================================

#: Longest the loop will wait on input when no timer is due. It does not sit
#: on a blocking read forever: quit() may be called from another thread, a
#: SIGWINCH may need servicing, and work queued through the dispatcher has to
#: be picked up. A twentieth of a second is below the threshold of noticing
#: and costs nothing while idle.
_IDLE_TIMEOUT_MS = 50

#: How many queued cross-thread calls to run per pass. Bounded so a thread
#: posting work in a tight loop cannot starve input handling.
_DISPATCH_BATCH = 64

#: The root that currently owns the terminal. Curses is process-global -
#: there is one screen, whatever the object model says - so a second live
#: root is refused rather than allowed to corrupt the first.
_active_root: Tk | None = None


class Tk(BaseWidget, Wm):
    """The root window, and the event loop that drives everything.

    Creating one initialises curses and takes over the terminal; destroying
    one gives it back. Because that is process-global state rather than
    something owned by the object, only one may be live at a time, and the
    teardown path runs even when the application fails - a program that dies
    with the terminal in raw mode leaves the user with an unusable shell.

    tkinter's hierarchy is ``Tk(Misc, Wm)``. The window manager half arrives
    with the Wm class; what is here is the root widget and the loop.
    """

    _is_toplevel = True

    #: The root accepts the standard options; the rest of its configuration
    #: is window manager business.
    #: The menubar this window shows, if any. Declared here as well as on
    #: Toplevel because a menubar on the root window is the common case.
    _widget_options: ClassVar[dict[str, Any]] = {"menu": None}

    def __init__(
        self,
        screenName: str | None = None,  # noqa: ARG002 - tkinter signature
        baseName: str | None = None,  # noqa: ARG002 - tkinter signature
        className: str = "Tk",
        useTk: bool = True,
        sync: bool = False,  # noqa: ARG002 - tkinter signature
        use: str | None = None,  # noqa: ARG002 - tkinter signature
    ) -> None:
        """
        Args:
            screenName: Ignored. Names an X display, of which there is none.
            baseName: Ignored. Names the resource file tkinter would read.
            className: The widget class this root binds and looks options up
                under, as in tkinter.
            useTk: False leaves the terminal alone until :meth:`loadtk`,
                the nearest thing here to tkinter's Tcl-without-Tk mode.
            sync: Ignored. X11 synchronous mode.
            use: Ignored. Embeds Tk in a foreign window.

        Raises:
            TclError: If another root already owns the terminal.
        """
        global _default_root, _active_root

        if _active_root is not None and _active_root.winfo_exists():
            raise TclError(
                "a Tk() already owns the terminal; destroy it before creating "
                "another, since curses has one screen per process"
            )

        Misc.__init__(self, None, ".")
        self._setup_wm()
        self.className = className
        self._options = dict(self._option_spec())
        self._takefocus = True
        self._takefocus_given = False

        self._screen = CursesScreen()
        self._mouse_owner: Misc | None = None
        self._input: InputHandler | None = None
        self._motion_asserted = False
        #: Tracebacks that would have landed on the screen, kept until the
        #: terminal is handed back.
        self._held_reports: list[str] = []
        self._started = False
        self._running = False

        if useTk:
            self._start()

        self._install_default_bindings()
        _active_root = self
        if _default_root is None and _support_default_root:
            _default_root = self

    # ------------------------------------------------------------- startup

    def loadtk(self) -> None:
        """Take over the terminal, if ``Tk(useTk=False)`` did not.

        tkinter's loads Tk into an interpreter made without it. The
        equivalent here is starting curses, so a root that already has, or
        has been destroyed, is left as it is.
        """
        if not self._started and not self._destroyed:
            self._start()

    def readprofile(self, baseName: str, className: str) -> None:
        """Run ``~/.<className>.py`` and then ``~/.<baseName>.py``, if they exist.

        tkinter's profile hook, kept for programs that call it. Each file is
        run with ``self`` bound to this root and everything from
        ``tkcurses`` imported, as tkinter imports itself. The ``.tcl`` files
        tkinter would source beside them are skipped: there is no Tcl.

        Unlike tkinter, ``Tk()`` never calls this itself. tkinter's
        constructor does, unless Python was started with ``-E``, which means
        any program would run code from the home directory without asking.
        A program that wants it calls it.
        """
        home = Path(os.environ.get("HOME", os.curdir))
        namespace: dict[str, Any] = {"self": self}
        exec("from tkcurses import *", namespace)
        for name in (className, baseName):
            path = home / f".{name}.py"
            if path.is_file():
                exec(path.read_text(encoding="utf-8"), namespace)

    def _start(self) -> None:
        """Initialise curses and hang the screen-dependent pieces off it.

        Anything that fails here must still give the terminal back, which is
        why the whole body is guarded rather than just the parts that look
        risky: ``initscr()`` has already changed the terminal by the time the
        next line runs.
        """
        # Before curses starts: deciding on OSC 52 asks the terminal a
        # question, and curses would read the answer as keystrokes.
        self.tk.selections.route = choose_route(
            TkCursesConfig.load().clipboard.system,
            os.environ,
            ask_terminal=ask_terminal_for_osc52,
        )
        buffer = self._screen.start()
        try:
            settings = TkCursesConfig.load()
            # ncurses cannot tell a lone Escape from the start of an escape
            # sequence until this long has passed with nothing following. The
            # default is a full second, which makes Escape - the key that
            # cancels things - feel broken.
            #
            # Read from the configuration, not hardcoded: a slow serial link
            # or a terminal that splits a sequence across packets needs
            # longer, and until this line existed the setting was accepted,
            # validated and tested while changing nothing at all.
            with contextlib.suppress(AttributeError, _curses.error):
                _curses.set_escdelay(settings.input.escape_delay)
            mouse = settings.mouse
            self._input = InputHandler(
                self._screen.stdscr,
                click_interval=mouse.click_interval,
                report_motion=mouse.report_motion,
                report_hover=mouse.report_hover,
            )
            # Bindings are almost always made before mainloop(), so the
            # terminal has to be told what they wanted once it exists.
            self.tk.input = self._input
            self.tk.refresh_signal_keys()
            colors = ColorManager()
            if colors.start():
                # Cells are painted through this; without colour support the
                # screen keeps its attributes-only resolver.
                self._screen.attribute_resolver = colors.attribute_for
            # Pictures need more (foreground, background) combinations than
            # curses can name - 255, and a photograph wants thousands - so
            # their cells are written past it when the terminal takes direct
            # colour. See _core/direct.py.
            painter = DirectPainter()
            allowed = TkCursesConfig.load().display.direct_images
            if not allowed:
                pass
            elif colors.depth >= ColorDepth.DIRECT or truecolor_hinted():
                # Exact colour, written as ESC[38;2;r;g;b.
                painter.enable(True)
            elif colors.depth >= ColorDepth.EXTENDED:
                # A palette rather than direct colour, so written as
                # ESC[38;5;N against it. Worth doing for the same reason:
                # a 256-colour terminal has no pair ceiling either once the
                # sequences are written by hand, and going through curses
                # costs a photograph most of its colours.
                painter.enable(True, index_of=colors.index_of)
            self.tk.painter = painter
            # Kept either way, since it is also what anything asking how many
            # colours there are has to ask - and the answer on a terminal
            # without any is a real answer rather than a missing one.
            self.tk.colors = colors
            self.tk.screen = self._screen
            self.tk.panels = PanelStack()
            # The terminal's own cursor, at the focused widget's insert point;
            # see TerminalCursor. Both flush paths place it.
            cursor = TerminalCursor(
                self._focused_insert_cell, self._focused_cursor_style
            )
            self._screen.cursor = cursor
            self.tk.panels.cursor = cursor
            self._rect = Rect(0, 0, buffer.width, buffer.height)
            self._mapped = True
            self._started = True
        except BaseException:
            self._screen.stop()
            self._flush_held_reports()
            raise

    def _install_default_bindings(self) -> None:
        """Bindings every application gets, on the ``all`` tag.

        Tab traversal lives here rather than in any widget: moving the focus
        is the application's business, not the business of whichever widget
        happens to have it. Tk does the same, which is why a widget can leave
        Tab alone and still be reachable from the keyboard.

        Registered on ``all``, the last tag consulted, so a widget that wants
        Tab for itself - a text editor inserting one - binds it and returns
        "break" without having to remove anything.
        """
        if "all" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("all")
        self.bind_all("<Key-Tab>", _focus_next)
        self.bind_all("<Key-ISO_Left_Tab>", _focus_previous)
        # F6 and Shift-F6 as well, because Tab cannot always be spared.
        #
        # A Text wants Tab for indentation, and tkinter's Text takes it: Tk binds
        # <Tab> to insert one and gives traversal to <Control-Tab> instead. That
        # split is not available here - Tab, Control-I and Control-Tab are all the
        # byte 0x09 in a terminal, and the modern CSI encodings for Control-Tab
        # are not parsed, so pressing it would type ";9~" into the document. See
        # TkCurses-87e for the measurements and TkCurses-99j for the parsing.
        #
        # F6 is the conventional "next pane" key - GTK and GNOME use it, and so do
        # many terminal applications - and it survives the journey, measured.
        # Alt-arrows were considered and rejected: i3 and sway bind Mod1+Left and
        # Mod1+Right to window focus by default, so the window manager would eat
        # them before the application saw anything. GNOME reserves Alt-F6 and
        # Shift-Alt-F6 for cycling an application's own windows, which is why the
        # pair here is PLAIN F6 and SHIFT-F6 rather than anything with Alt.
        self.bind_all("<Key-F6>", _focus_next)
        # F18, and this is not a typo. terminfo encodes the shifted function keys
        # as F13 to F24 - this terminal's own kf18 entry is \E[17;2~, which is
        # literally F6 with shift - so Shift-F6 arrives as a key NAMED F18 with
        # no shift bit set. Measured: CSI 17~ gives keysym F6, CSI 17;2~ gives
        # keysym F18, state 0 in both. The <Shift-Key-F6> form is bound too, for
        # a terminal that reports the modifier properly instead.
        self.bind_all("<Key-F18>", _focus_previous)
        self.bind_all("<Shift-Key-F6>", _focus_previous)

    def winfo_class(self) -> str:
        """The class this root binds and reads options under."""
        return self.className

    # ---------------------------------------------------------- event loop

    def mainloop(self, n: int = 0) -> None:
        """Run until :meth:`quit` is called or the root is destroyed.

        Args:
            n: Run at most this many passes, or unlimited when 0. tkinter
                takes the same argument; it is what lets a test drive the
                loop a step at a time.

        **The terminal is given back however the loop ends**, and that is
        not a nicety: curses has put the terminal in cbreak mode, hidden the
        cursor, switched to the alternate screen and possibly turned mouse
        reporting on. A program that exits without undoing those leaves the
        shell unusable until ``reset``. This docstring claimed as much
        before it was true - measured, Ctrl-C left every one of them set.

        **An exception restores the terminal before it continues**, which
        is the whole of the change here. It is not tidiness: whatever
        printed that traceback is about to write it to a terminal that is
        still on the alternate screen, where it will scroll past and vanish
        the moment the screen is swapped back. Restoring first puts it
        somewhere the user can actually read.

        **Ctrl-C is a close request, not a crash.** It arrives as a signal
        only when nothing bound ``<Control-c>`` - see
        :meth:`~tkcurses._core.application.Application.refresh_signal_keys` -
        and it is then delivered to ``WM_DELETE_WINDOW``, tkinter's own
        protocol for "the user asked to close this window". A handler
        registered with ``protocol()`` runs and decides: it may save, it may
        ask, it may refuse and let the application carry on. With no
        handler, the default is to close.

        This is the one place TkCurses deliberately does NOT do what tkinter
        does, and the reason is that the gesture does not mean the same
        thing. A tkinter program is in a window, and Ctrl-C is typed at the
        terminal that launched it - a developer interrupting from outside,
        for whom a traceback is the right answer. A TkCurses program *is*
        the terminal: Ctrl-C is typed at the application, by whoever is
        using it, and it universally means "stop". Answering a user's
        gesture with a Python traceback is not compatibility.

        The mechanism was already here and unused. ``wm_protocol`` said of
        ``WM_DELETE_WINDOW`` that "nothing raises it: a terminal offers no
        close button and no user gesture that means close this window".
        Ctrl-C is that gesture.

        An application that wants the interrupt itself has three ways: bind
        ``<Control-c>``, which takes the key from the tty entirely and never
        makes a signal of it; register ``WM_DELETE_WINDOW`` and raise from
        there; or install its own SIGINT handler.
        """
        self._running = True
        self.tk.quit_requested = False
        passes = 0
        try:
            while self._running and not self.tk.quit_requested:
                if not self.winfo_exists():
                    break
                try:
                    self._loop_once()
                except KeyboardInterrupt:
                    # Handled inside the loop rather than let out of it, so
                    # that a handler which decides NOT to close can simply
                    # return and the application carries on - which is how
                    # WM_DELETE_WINDOW behaves everywhere else.
                    if not self._copy_on_interrupt():
                        self._close_requested()
                passes += 1
                if n and passes >= n:
                    break
        except BaseException:
            # Before the exception goes on, not after: something is about to
            # print it on this terminal, and on the alternate screen it
            # would be swapped away unread. KeyboardInterrupt included - the
            # application may be catching it around this call.
            self._running = False
            with contextlib.suppress(BaseException):
                self.destroy()
            raise
        finally:
            self._running = False

    def _close_requested(self) -> None:
        """The user asked to close the application. Ctrl-C means this.

        Routed through ``WM_DELETE_WINDOW`` so that an application says what
        should happen using tkinter's own API, rather than one invented
        here. With no handler registered the default is to close, which is
        what a terminal user pressing Ctrl-C expects.

        A handler that returns without quitting leaves the application
        running, exactly as declining to close a window does elsewhere.
        """
        if not self._invoke_protocol("WM_DELETE_WINDOW"):
            self.destroy()

    def _loop_once(self) -> None:
        """One pass: queued work, idle work, timers, input, then output.

        The order is not arbitrary. Work queued from another thread runs
        first because it may schedule timers; idle work runs before timers
        because that is what "idle" means; input is read last, with a timeout
        derived from the next timer, so the loop sleeps exactly as long as it
        can afford to. Layout comes after all of them and before drawing,
        since any of them may have changed what there is to draw.
        """
        # Fetched rather than stored: shutdown resets the dispatcher, and a
        # held reference would outlive the one the rest of the process uses.
        CursesDispatcher.get().process_queue(limit=_DISPATCH_BATCH)
        self._guard(self.tk.timers.run_idle)
        self._guard(self.tk.timers.run_due)
        self._read_input()
        # Layout settles before anything is drawn, so a widget is never
        # painted at a size it is about to stop having.
        self._guard(self.tk.layout.run)
        self._update_display()

    def _renew_colour_pairs(self) -> None:
        """Rebuild an exhausted colour-pair table, and put the screen back.

        A pair is the scarcest thing the terminal has - 255 of them, because
        that is all an attribute can name - and they were never given back
        once handed out. Measured on xterm-256color: one demo photograph took
        238 of them and the *second* one exhausted the table, after which
        every later picture was drawn in whatever palette the first had left
        behind. An image viewer is exactly the program that does this.

        Renewing is done here, at the frame boundary, rather than wherever
        the table happens to run dry. Recycling a pair number changes what
        every cell already painted with it *shows*, so it may only happen
        when the whole screen can be put back in the same breath - half way
        through a paint would leave the first half of the frame recoloured.

        Both layers have to be dealt with, and they need different things:

        - The screen buffer holds a cell's colours as **names**, so it only
          needs marking dirty; the repaint re-asks for every one.
        - A widget resolved its attribute once and baked the pair number into
          its curses window, which nothing re-reads. It has to draw again.

        What makes this safe rather than merely hopeful is that the rebuilt
        table is populated by the repaint itself, so it ends up holding
        exactly the colours still on screen. A picture that has gone is
        simply never asked for again.
        """
        colors = self.tk.colors
        if colors is None or not colors.renew_if_exhausted():
            return
        self._screen.buffer.touch_all()
        for child in list(self.children.values()):
            for widget in child._subtree():
                if isinstance(widget, BaseWidget):
                    widget._redraw()
        if self.tk.panels is not None:
            self.tk.panels.touch_all()

    def _read_input(self) -> None:
        """Wait for input up to the next timer's deadline, then route it."""
        if self._input is None:
            return
        if not self._motion_asserted:
            # Once more, now that the screen has been painted and whatever
            # ncurses wanted to say to the terminal has been said. A mouse
            # mode lost during startup is the difference between drags
            # working and a terminal that never reports one, and the cost of
            # being sure is a single write.
            self._motion_asserted = True
            self._input.enable_motion()
        delay = self.tk.timers.next_delay()
        timeout = (
            _IDLE_TIMEOUT_MS
            if delay is None
            else min(int(delay * 1000), _IDLE_TIMEOUT_MS)
        )
        self._input.wait_for_input(max(timeout, 0))
        for event in self._input.poll():
            self._guard(self._route, event)

    def _route(self, event: CoreEvent) -> None:
        """Deliver one event to the widget it belongs to.

        Keyboard goes to the focus, mouse to whatever is under the pointer,
        and a resize to the root, which owns the screen. A grab overrides all
        three: that is what makes a modal dialog modal.
        """
        if isinstance(event, ResizeEvent):
            self._handle_resize()
            return
        if isinstance(event, MouseEvent):
            if event.state in _PRESSES and self.tk.repeat is not None:
                self._release_lost()
            target = self._mouse_target(event)
        else:
            target = self.tk.focus or self
        target = self._through_grab(target)
        target._handle(event)

    def _release_lost(self) -> None:
        """Stop an auto-repeat whose release never arrived.

        A press is held for as long as no release is reported, and ncurses
        drops reports it is not drained fast enough for (see
        ``_arm_press_recovery``), so a repeating Button or Scale could repeat
        for ever. A second press cannot happen with the first button still
        down: it is the proof that the release was lost. The held widget is
        put back up, as its release would have done.
        """
        _cancel_repeat(self)
        owner: Any = self._mouse_owner
        if owner is not None and getattr(owner, "_pressed", False):
            owner._pressed = False
            owner._redraw()

    def _mouse_target(self, event: MouseEvent) -> Misc:
        """The widget a mouse event belongs to, honouring the implicit grab.

        Everything between a press and its release goes to the widget that
        was pressed, wherever the pointer has since wandered. X11 gives a
        widget this grab automatically and Tk relies on it; routing each
        event by position instead means a pointer that drifts a single cell
        between press and release delivers the release somewhere else. The
        pressed widget then never hears that the button came up and stays
        held down, so the *next* click appears to be the one that works -
        intermittently, depending on whether the hand moved.
        """
        # A double or triple click is a press too, and takes the grab like
        # one: without it, the drag after a double-click - which extends the
        # selection a word at a time - went to whatever was under the pointer
        # instead of to the widget pressed. TkCurses-svtr.
        if event.state in _PRESSES:
            self._mouse_owner = self._widget_at(event.x, event.y)
            return self._mouse_owner
        owner = self._mouse_owner
        if owner is not None and owner.winfo_exists():
            if event.state == "released":
                self._mouse_owner = None
            return owner
        self._mouse_owner = None
        return self._widget_at(event.x, event.y)

    def _widget_at(self, x: int, y: int) -> Misc:
        """The widget under a screen cell, falling back to the root.

        The panel stack answers this when there is one, because it knows the
        z-order; before there is, the widget tree's own geometry does.
        """
        stack = self.tk.panels
        if stack is not None:
            panel = stack.panel_at(x, y)
            if panel is not None:
                widget = panel.userptr()
                if isinstance(widget, Misc) and widget.winfo_exists():
                    return widget
        return self.winfo_containing(x, y) or self

    def _through_grab(self, target: Misc) -> Misc:
        """Redirect an event to the grab holder unless it is already inside it."""
        grab = self.tk.grab
        if grab is None or not grab.winfo_exists():
            return target
        if any(widget is grab for widget in target._ancestry()):
            return target
        return grab

    def _handle_resize(self) -> None:
        """Take the terminal's new size and tell the tree about it.

        The event carries a size, but it is not the one used: curses reports
        the old dimensions until resize_term() has been given what the
        terminal actually is, which is what handle_resize() does.
        """
        size = self._screen.handle_resize()
        # The screen is cleared and written again from scratch, so the panels
        # over it have to be written again too - otherwise every widget that
        # happens to keep its geometry through the resize simply vanishes.
        if self.tk.panels is not None:
            self.tk.panels.touch_all()
        self._rect = Rect(0, 0, size.width, size.height)
        # The root's rect is set directly rather than through _allocate, which
        # would give the root a panel it does not want - so its layout has to
        # be told separately. Without this, everything sized against the
        # terminal keeps the size the terminal used to be.
        self.tk.layout.invalidate(self)
        # Laid out here rather than left to the next idle pass, because the
        # windows are put right immediately below and that has to happen
        # against the geometry the new size gives, not the old one.
        self.update_layout()
        # A window is clipped to the screen rather than allowed off the edge,
        # so a widget that was on screen at the old size may be clipped, gone
        # or restorable at the new one. The layout only re-allocates what it
        # manages, and a toplevel is not that: without this a toplevel keeps
        # whatever window the smallest terminal it ever saw left it with.
        # The children's subtrees, not the root's: the root deliberately has
        # no window of its own, and giving it one puts an opaque full-screen
        # panel over everything drawn on the screen behind the widgets.
        # Windows first, and by moving rather than clipping. A Toplevel is
        # both a Wm, which may not overflow the terminal, and a Misc, which
        # may and gets clipped - and it is the Misc rule that _sync_window
        # applies. Re-establishing the stronger one here is what stops a
        # window, and with it a grab, from ending up where nothing can reach.
        for child in list(self.children.values()):
            if isinstance(child, Wm):
                child._reposition_for_screen()
        for child in list(self.children.values()):
            for widget in child._subtree():
                if isinstance(widget, BaseWidget):
                    widget._sync_window()
        self.event_generate("<Configure>", width=size.width, height=size.height)

    def _update_display(self) -> None:
        """Push what changed to the terminal.

        The screen goes first and the panels over it, which is the order they
        are stacked in. Widgets do not draw anything yet; when they do, their
        rendering happens before this.
        """
        if not self._started:
            return
        self._renew_colour_pairs()
        painted = self._screen.refresh()
        if self.tk.panels is not None:
            self.tk.panels.update()
        # After doupdate, never before: curses has finished writing and
        # cannot paint over the picture within this frame. Every frame it
        # has cells, because curses repaints them whenever anything near
        # them changes and does not say so.
        painter = getattr(self.tk, "painter", None)
        if painter is not None and painter.pending:
            CursesDispatcher.get().call(painter.paint, bool(painted))

    def update(self) -> None:
        """Process everything pending without entering the loop.

        Unlike :meth:`Misc.update`, this does read input, because the root is
        the one object entitled to. It is still the reentrancy hazard it is
        in tkinter: a callback that calls ``update()`` can be re-entered by
        the event that arrives during it.
        """
        self._loop_once()

    # ------------------------------------------------------------ teardown

    def quit(self) -> None:
        """Stop the loop without destroying anything.

        The loop notices on its next pass, so the callback calling this runs
        to completion first. The widgets survive, which is what allows
        ``mainloop()`` to be entered again.
        """
        self._running = False
        self.tk.quit_requested = True

    def destroy(self) -> None:
        """Destroy every widget and give the terminal back.

        Ordering matters on the way out as much as on the way in: the widget
        tree goes first, so panels are released while the stack still exists,
        and curses is shut down last.
        """
        global _default_root, _active_root
        if self._destroyed:
            return
        self._running = False
        try:
            super().destroy()
        finally:
            self._shutdown()
        if _default_root is self:
            _default_root = None
        if _active_root is self:
            _active_root = None

    def _shutdown(self) -> None:
        """Release curses and everything hanging off it, once.

        Every step is independent and none may prevent the next: this runs
        while something has already gone wrong, and the terminal has to come
        back regardless.
        """
        if not self._started:
            return
        self._started = False
        self.tk.layout.clear()
        with contextlib.suppress(Exception):
            if self.tk.panels is not None:
                self.tk.panels.clear()
        self.tk.panels = None
        self.tk.screen = None
        self.tk.colors = None
        if self._input is not None:
            self._input.restore()
        self._input = None
        self.tk.input = None
        with contextlib.suppress(Exception):
            self._screen.stop()
            self._flush_held_reports()
            self._report_clipboard_kept_inside()
        CursesDispatcher.reset()

    def __enter__(self) -> Tk:
        """Support ``with Tk() as root:``.

        Not tkinter API. It is here because the alternative to guaranteed
        teardown in a curses program is a wrecked terminal, and a context
        manager is the one construct that guarantees it.
        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Destroy the root, restoring the terminal."""
        self.destroy()

    # ----------------------------------------------------------- callbacks

    def _guard(self, func: Callable[..., Any], *args: Any) -> None:
        """Run ``func``, reporting rather than propagating what it raises.

        One misbehaving binding should not take the application down, which
        is tkinter's rule too. KeyboardInterrupt and SystemExit are not
        caught: those are the user asking to leave.
        """
        try:
            func(*args)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            self.report_callback_exception(*sys.exc_info())

    def report_callback_exception(self, exc: Any, val: Any, tb: Any) -> None:
        """Report an exception that escaped a callback.

        Held back while the screen is up and stderr is the same terminal,
        and printed once the screen has been given back. A traceback written
        to a terminal curses is drawing on lands on top of the display, and
        the buffer repaints only what it knows has changed - so the damage
        stays until something else happens to write over it.

        Written immediately when stderr is a redirect or a pipe, because
        then it cannot damage anything and a developer watching a log wants
        it now.

        The screen is repainted either way. An override that draws its own
        report into the buffer survives that, since a repaint paints from
        the buffer; only writes that went straight to the terminal are
        undone, which is exactly the damage worth undoing.
        """
        text = "".join(traceback.format_exception(exc, val, tb))
        screen = self.tk.screen
        if screen is not None and screen.started and _stderr_is_a_terminal():
            self._held_reports.append(text)
        else:
            _write_to_stderr(text)
        if screen is not None and screen.started:
            with contextlib.suppress(_curses.error):
                screen.repaint()

    def _report_clipboard_kept_inside(self) -> None:
        """Say once, on the way out, that a copy never left this program.

        The acceptance the issue asked for: a terminal that cannot carry the
        clipboard is detected and said, not silently trusted. Said after the
        screen is given back, so it is read rather than painted over.
        TkCurses-hpr.
        """
        selections = self.tk.selections
        route = selections.route
        if not selections.kept_inside or route is None:
            return
        selections.kept_inside = False
        _write_to_stderr(
            "tkcurses: what was copied stayed inside this program - "
            f"{route.reason}. Set clipboard.system to change how it is tried.\n"
        )

    def _flush_held_reports(self) -> None:
        """Print anything held back, now that the screen has been given up."""
        held, self._held_reports = self._held_reports, []
        for text in held:
            _write_to_stderr(text)


def _stderr_is_a_terminal() -> bool:
    """True when writing to stderr would land on a terminal.

    Which is the question that decides whether a report can be printed now:
    a redirect or a pipe cannot be damaged, a terminal curses is drawing on
    can.
    """
    stream = sys.stderr
    try:
        return bool(stream is not None and stream.isatty())
    except (OSError, ValueError):
        return False


def _write_to_stderr(text: str) -> None:
    """Write a report out.

    No line-ending translation, and none needed. curses clears ONLCR, so a
    traceback printed while the screen is up comes out as a staircase with
    each line starting where the last one ended - which is why one is never
    printed then: it either goes to a stream curses has no say over, or it
    waits until curses has given the terminal back.
    """
    with contextlib.suppress(OSError, ValueError):
        sys.stderr.write(text)
        sys.stderr.flush()


class Toplevel(BaseWidget, Wm):
    """A window of its own, floating above the root.

    tkinter leaves a toplevel's frame, title bar and placement to the window
    manager. A terminal has none, so a toplevel here draws its own border and
    chooses its own position, and both are its business rather than a
    manager's: it is mapped the moment it is created and no geometry manager
    ever places it.

    tkinter's hierarchy is ``Toplevel(BaseWidget, Wm)``. The window manager
    methods - title, geometry, protocol - arrive with the Wm class.
    """

    _is_toplevel = True

    #: ``width`` and ``height`` are cells, and zero means "not asked for",
    #: which is what sends the window to its default size. borderwidth is 1
    #: rather than tkinter's 0: there is no window manager to draw a frame,
    #: so without one a toplevel is indistinguishable from what is behind it.
    _widget_options: ClassVar[dict[str, Any]] = {
        "borderwidth": 1,
        "height": 0,
        "menu": None,
        "width": 0,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        class_: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: The window this one belongs to. Defaults to the root.
            cnf: Options as a dictionary.
            name: Path component, generated when omitted.
            class_: The class this window binds and reads options under, as
                tkinter's ``class_`` does. Construction-time only, because
                bindings and option lookups are resolved against it.
            **kw: Options as keywords.
        """
        self._class_name = class_
        self._drag_origin: tuple[int, int, int, int] | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._setup_wm()
        self._allocate(self._default_rect())
        self._map()
        self._install_class_bindings()

    def winfo_class(self) -> str:
        """The class this window binds and reads options under."""
        return self._class_name or type(self).__name__

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register title-row dragging for every window of this class.

        Under ``winfo_class()`` rather than the literal ``"Toplevel"``, which
        matters because a subclass reports its own name here - so
        :class:`tkcurses.simpledialog.Dialog` binds under ``Dialog`` and gets
        the behaviour, where a hard-coded tag would have left every dialog
        in the library the one kind of window that cannot be moved.

        Class bindings rather than instance ones, so an application that
        binds the title row itself runs first and can stop this with
        ``"break"``.
        """
        tag = self.winfo_class()
        if tag in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(tag)
        self.bind_class(tag, "<Button-1>", _toplevel_press)
        self.bind_class(tag, "<B1-Motion>", _toplevel_drag)
        self.bind_class(tag, "<ButtonRelease-1>", _toplevel_release)

    def _default_rect(self) -> Rect:
        """Where the window goes when nothing has said.

        Centred, and clamped to the screen. Tk would hand this to the window
        manager, which typically cascades or centres; centring is the choice
        that keeps a dialog visible on a terminal of any size, and Wm's
        geometry() will override it.
        """
        screen_width, screen_height = self._screen_size()
        width = int(self._options["width"]) or min(
            _DEFAULT_TOPLEVEL_SIZE.width, screen_width
        )
        height = int(self._options["height"]) or min(
            _DEFAULT_TOPLEVEL_SIZE.height, screen_height
        )
        width = clamp(width, 1, screen_width)
        height = clamp(height, 1, screen_height)
        return Rect(
            clamp((screen_width - width) // 2, 0, max(0, screen_width - width)),
            clamp((screen_height - height) // 2, 0, max(0, screen_height - height)),
            width,
            height,
        )

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, resizing the window if its size options changed."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if given and {"width", "height"} & set(given):
            self._allocate(self._default_rect())
        elif given:
            self._draw()
        return result

    config = configure

    def _redraw(self) -> None:
        """Repaint the border and title whenever the window changes."""
        self._draw()

    def _draw(self) -> None:
        """Paint the border into this window's curses window.

        The only rendering in the library so far: a toplevel without a border
        is indistinguishable from whatever it covers, and there is no window
        manager to draw one. Widget rendering proper arrives with the widget
        set, and will draw the interior before this is pushed to the terminal.

        Silent without a screen, which is what lets the geometry above be
        tested with no terminal in the loop.
        """
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.erase)
            if self._bordered:
                dispatcher.call(window.border)
                self._draw_title(dispatcher, window)

    def _draw_title(self, dispatcher: CursesDispatcher, window: Any) -> None:
        """Write the title into the top border, centred and truncated.

        The top border is the only title bar a terminal window has. A title
        longer than the border can hold is cut rather than allowed to run
        over the corners.
        """
        title = getattr(self, "_title", "")
        if not title:
            return
        room = self._rect.width - 2 * BORDER_WIDTH - 2
        text = clip_text(f" {title} ", max(0, room + 2))
        if len(text) < 3:
            return
        column = max(BORDER_WIDTH, (self._rect.width - len(text)) // 2)
        with contextlib.suppress(_curses.error):
            # A_NORMAL: the title had no attribute of its own before this
            # went through _write_line, and the border it sits in has none
            # either.
            # Through the class: a Toplevel is a BaseWidget rather than a
            # _Drawable, and _write_line is a static method on the latter.
            _Drawable._write_line(dispatcher, window, 0, column, text, _curses.A_NORMAL)

    def _redraw_decoration(self) -> None:
        """Repaint the border and title after the window manager changed them."""
        self._draw()


def _toplevel_press(event: Event) -> Any:
    """Start a drag, if the press landed on the title row.

    A terminal has no window manager, so moving a decorated window is this
    library's job - the same job Mutter or KWin would be doing, and the
    reason it is a class binding rather than something an application has to
    write. An ``overrideredirect`` window is excluded on purpose: it has no
    decoration to grab, and on a desktop such a window is the application's
    to move. See ARCHITECTURE.md, "Window Management".

    The title row is row zero, and only row zero. A press anywhere else
    belongs to whatever is there.
    """
    window = event.widget
    if not isinstance(window, Toplevel) or not window._bordered or event.y != 0:
        return None
    window._drag_origin = (
        event.x_root,
        event.y_root,
        window.winfo_x(),
        window.winfo_y(),
    )
    # Clicking a window to move it and having it stay behind another would be
    # surprising, and here there is no window manager to do the raising.
    window.tkraise()
    return None


def _toplevel_drag(event: Event) -> Any:
    """Move the window by however far the pointer has travelled.

    By the distance travelled rather than to the position arrived at, so the
    column of the title that was grabbed stays under the pointer - the rule
    the scrollbar thumb and the sizegrip already follow. ``geometry`` clamps
    to the screen, so a window dragged at the edge stops rather than leaving.
    """
    window = event.widget
    if not isinstance(window, Toplevel):
        return None
    origin = window._drag_origin
    if origin is None:
        return None
    press_x, press_y, left, top = origin
    x = left + (event.x_root - press_x)
    y = top + (event.y_root - press_y)
    window.geometry(f"{window.winfo_width()}x{window.winfo_height()}+{x}+{y}")
    window.update_layout()
    return None


def _toplevel_release(event: Event) -> Any:
    """Finish the drag, leaving the window where it was let go."""
    window = event.widget
    if isinstance(window, Toplevel):
        window._drag_origin = None
    return None


# ======================================================================
# Variables
# ======================================================================


class Variable:
    """A value widgets can share and watch.

    tkinter's variables live in the Tcl interpreter, which is what lets two
    widgets bound to the same one stay in step and what makes a trace fire.
    Here they live in the :class:`~tkcurses._core.application.Application`,
    reached through the master, so the same sharing holds and two
    applications in one process keep separate variables.

    Attributes:
        _default: The value a variable of this class starts with.
    """

    _default: Any = ""

    #: Names automatic variables PY_VAR0, PY_VAR1, as tkinter does, so a
    #: printed variable name reads the same under either library.
    _counter = itertools.count()

    def __init__(
        self,
        master: Misc | None = None,
        value: Any = None,
        name: str | None = None,
    ) -> None:
        """
        Args:
            master: Any widget of the application the variable belongs to.
                Defaults to the implicit root.
            value: Initial value. Without one the variable takes its class's
                default, unless a variable of that name already holds
                something, which is how two Variables can share one name.
            name: The variable's name, generated when omitted.

        Raises:
            TclError: If no master was given and there is no root window.
        """
        if master is None:
            master = _get_default_root("create a variable")
        self._master = master
        self._tk = master.tk
        self._name = name or f"PY_VAR{next(Variable._counter)}"
        self._traces: dict[str, tuple[tuple[str, ...], Callable[..., Any]]] = {}
        self._trace_ids = itertools.count(1)
        if value is not None:
            self.initialize(value)
        elif self._name not in self._tk.variables:
            self.initialize(self._default)

    def __str__(self) -> str:
        """The variable's name, which is how Tk refers to one."""
        return self._name

    def __repr__(self) -> str:
        """Name and current value, for a traceback or a debugger."""
        return f"<{type(self).__name__} {self._name}={self._raw()!r}>"

    def __eq__(self, other: object) -> bool:
        """Equal to another variable of the same class with the same name.

        Not by value: two variables are the same variable or they are not,
        and comparing the values would make an IntVar equal to a StringVar
        that happened to hold the same digits.
        """
        if not isinstance(other, Variable):
            return NotImplemented
        return type(other) is type(self) and other._name == self._name

    def __hash__(self) -> int:
        """Hash by name, to match :meth:`__eq__`."""
        return hash((type(self).__name__, self._name))

    def __del__(self) -> None:
        """Forget the value when the last reference goes.

        Guarded to the point of silence: this runs during garbage collection
        and at interpreter shutdown, where the application may already be
        half torn down and an exception here would be reported out of any
        useful context.
        """
        with contextlib.suppress(Exception):
            self._tk.variables.pop(self._name, None)

    # --------------------------------------------------------------- value

    def get(self) -> Any:
        """The variable's value, converted to this class's type."""
        self._fire("read")
        return self._convert(self._raw())

    def set(self, value: Any) -> None:
        """Set the value, firing any write traces."""
        self._tk.variables[self._name] = value
        self._fire("write")

    initialize = set

    def _raw(self) -> Any:
        """The stored value, unconverted, defaulting if it was never set."""
        return self._tk.variables.get(self._name, self._default)

    def _convert(self, value: Any) -> Any:
        """Coerce a stored value to this class's type. Identity by default."""
        return value

    # -------------------------------------------------------------- traces

    def trace_add(self, mode: str | Sequence[str], callback: Callable[..., Any]) -> str:
        """Call ``callback`` when the variable is read, written, or unset.

        Args:
            mode: One of ``read``, ``write``, ``unset``, or several.
            callback: Invoked as ``callback(name, index, mode)``, the
                arguments Tcl passes and tkinter hands on unchanged.

        Returns:
            A handle for :meth:`trace_remove`.

        Raises:
            TclError: If a mode is not one Tk recognises.
        """
        modes = (mode,) if isinstance(mode, str) else tuple(mode)
        for one in modes:
            if one not in _TRACE_MODES:
                raise TclError(f'bad operation "{one}"')
        handle = f"{self._name}_trace{next(self._trace_ids)}"
        self._traces[handle] = (modes, callback)
        return handle

    def trace_remove(
        self,
        mode: str | Sequence[str],  # noqa: ARG002 - tkinter signature
        cbname: str,
    ) -> None:
        """Remove a trace by the handle :meth:`trace_add` returned.

        The mode is accepted for tkinter's signature and not consulted: the
        handle already identifies one registration.
        """
        self._traces.pop(cbname, None)

    def trace_info(self) -> list[tuple[tuple[str, ...], str]]:
        """Every trace on this variable, as ``(modes, handle)`` pairs."""
        return [(modes, handle) for handle, (modes, _) in self._traces.items()]

    def trace_variable(self, mode: str, callback: Callable[..., Any]) -> str:
        """Add a trace using the old single-letter modes.

        ``r``, ``w`` and ``u`` are what Tk called read, write and unset
        before ``trace_add``. Kept because tkinter code written before 3.6
        still uses them.

        Raises:
            TclError: If the mode letter is not one of the three.
        """
        return self.trace_add(self._legacy_modes(mode), callback)

    #: The oldest spelling of all, which tkinter still defines as this alias.
    trace = trace_variable

    def trace_vdelete(self, mode: str, cbname: str) -> None:
        """Remove a trace added with :meth:`trace_variable`."""
        self.trace_remove(self._legacy_modes(mode), cbname)

    def trace_vinfo(self) -> list[tuple[str, str]]:
        """Traces in the old format: single-letter modes and handles."""
        return [
            ("".join(_LEGACY_LETTERS[one] for one in modes), handle)
            for modes, handle in self.trace_info()
        ]

    @staticmethod
    def _legacy_modes(mode: str) -> tuple[str, ...]:
        """Translate ``rwu`` letters into the modern mode names."""
        try:
            return tuple(_LEGACY_MODES[letter] for letter in mode)
        except KeyError:
            raise TclError(f'bad operation "{mode}"') from None

    def _fire(self, mode: str) -> None:
        """Run the traces registered for ``mode``.

        The list is copied first, so a callback may add or remove a trace -
        including its own - without disturbing the pass it is in.
        """
        for modes, callback in list(self._traces.values()):
            if mode in modes:
                callback(self._name, "", mode)


#: Trace modes Tk recognises. "array" is accepted for compatibility; nothing
#: here is an array, so it never fires.
_TRACE_MODES = ("read", "write", "unset", "array")

#: The single letters Tk used for trace modes before trace_add existed.
_LEGACY_MODES = {"r": "read", "w": "write", "u": "unset"}
_LEGACY_LETTERS = {name: letter for letter, name in _LEGACY_MODES.items()}


class StringVar(Variable):
    """A variable holding text."""

    _default = ""

    def _convert(self, value: Any) -> str:
        """Render the value as text, as Tcl would."""
        return "" if value is None else str(value)


class IntVar(Variable):
    """A variable holding a whole number."""

    _default = 0

    def _convert(self, value: Any) -> int:
        """Parse the value as an integer.

        Raises:
            TclError: If it is not one, matching tkinter, which reports the
                Tcl conversion failure.
        """
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            raise TclError(f'expected integer but got "{value}"') from None


class DoubleVar(Variable):
    """A variable holding a number with a fractional part."""

    _default = 0.0

    def _convert(self, value: Any) -> float:
        """Parse the value as a float.

        Raises:
            TclError: If it is not one.
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            raise TclError(
                f'expected floating-point number but got "{value}"'
            ) from None


class BooleanVar(Variable):
    """A variable holding a truth value."""

    _default = False

    def _convert(self, value: Any) -> bool:
        """Parse the value the way Tcl reads a boolean.

        Raises:
            TclError: If it is none of the spellings Tcl accepts.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise TclError(f'expected boolean value but got "{value}"')


# ======================================================================
# Widgets
# ======================================================================


class XView:
    """The horizontal half of Tk's scroll protocol. ``tkinter.XView``.

    A widget supplies ``xview(*args)`` - the query and the ``moveto`` /
    ``scroll`` forms a Scrollbar sends - and this adds the two named
    spellings a program writes itself, which tkinter implements the same way:
    thin wrappers over ``xview``. One definition here instead of one per
    widget; TkCurses-019 found seven widgets with ``xview`` and without these.
    """

    def xview(self, *args: Any) -> Any:  # pragma: no cover - always overridden
        """Query or move the horizontal view. Every user overrides this."""
        raise NotImplementedError

    def xview_moveto(self, fraction: float) -> None:
        """Put ``fraction`` of the total width off-screen to the left."""
        self.xview("moveto", fraction)

    def xview_scroll(self, number: int, what: str) -> None:
        """Shift the view by ``number`` ``"units"`` or ``"pages"``."""
        self.xview("scroll", number, what)


class YView:
    """The vertical half of Tk's scroll protocol. ``tkinter.YView``.

    ``tree.yview_moveto(0.0)`` - back to the top - and
    ``listbox.yview_scroll(1, "units")`` are what a program's own key handlers
    write. See :class:`XView`.
    """

    def yview(self, *args: Any) -> Any:  # pragma: no cover - always overridden
        """Query or move the vertical view. Every user overrides this."""
        raise NotImplementedError

    def yview_moveto(self, fraction: float) -> None:
        """Put ``fraction`` of the total height off-screen above."""
        self.yview("moveto", fraction)

    def yview_scroll(self, number: int, what: str) -> None:
        """Shift the view by ``number`` ``"units"`` or ``"pages"``."""
        self.yview("scroll", number, what)


class _Drawable(Widget):
    """Painting shared by the widgets that draw a background and a border."""

    def _font_attribute(self) -> int:
        """What this widget's ``font`` option does to its text.

        A terminal has one typeface, so the part of a Tk font specification
        that survives is the styling: bold, italic and underline. A widget
        with no ``font`` option - a Frame, a Scrollbar - has no text of its
        own to style and gets nothing.
        """
        option = self._options.get("font", "")
        named = self.tk.fonts.get(str(option))
        if named is not None:
            # A font created through tkcurses.font. Tk keeps these in the
            # interpreter and a widget names one; the styling lives with the
            # font rather than in the widget's own option string.
            return from_font(
                bold=str(named.get("weight", "normal")) == "bold",
                italic=str(named.get("slant", "roman")) == "italic",
                underline=bool(named.get("underline", False)),
            )
        font = str(option).lower()
        return from_font(
            bold="bold" in font,
            italic="italic" in font,
            underline="underline" in font,
        )

    @property
    def _disabled(self) -> bool:
        """True while the widget refuses to answer the user.

        Here rather than on any one widget: every widget that takes a click
        or a key asks the same question, and the ones that have no ``state``
        at all - a Frame - answer no.
        """
        return str(self._options.get("state", "normal")) == "disabled"

    def _background_attribute(self) -> int:
        """The curses attribute this frame's colours resolve to.

        Falls back to plain when no colour manager is running, which is what a
        terminal without colour gives anyway.
        """
        colors = self.tk.colors
        if colors is None:
            return _curses.A_NORMAL
        return colors.attribute_for(
            str(self._options["foreground"] or "white"),
            str(self._options["background"] or "black"),
        )

    def _border_style(self) -> BorderStyle:
        """The characters this widget's border is drawn with.

        Its own method so that a subclass can answer differently: a themed
        widget takes its box from the theme's glyph set rather than from the
        relief, which is what makes ``Style.theme_use`` visible on screen.
        Before this existed, the nine themed widgets built on ordinary ones
        drew the relief's own characters and a theme change reached none of
        them - TkCurses-5vu, found by a person pressing Ctrl-T in UAT 40.
        """
        return style_for_relief(str(self._options["relief"]) or FLAT)

    def _draw_border(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        width: int,
        height: int,
        attribute: int,
    ) -> None:
        """Draw the box for this frame's relief.

        Drawn character by character rather than with curses' own ``border``,
        because a relief is a choice of line style - single, double, heavy -
        and ``border`` only knows one.
        """
        style = self._border_style()
        attribute |= style.attr
        # The window can be smaller than the widget: one clipped by a screen
        # edge gets only the part of itself that fits, because curses will
        # not make a window that runs off the screen. Drawing the whole
        # widget into it wraps the overflow onto the next row instead of
        # losing it, which is a border that runs on into the line below.
        rows, columns = dispatcher.call(window.getmaxyx)
        right = width - 1
        self._write_line(dispatcher, window, 0, 0, style.top(width), attribute)
        for row in range(1, min(height - 1, rows)):
            self._write_line(dispatcher, window, row, 0, style.vertical, attribute)
            if right < columns:
                self._write_line(
                    dispatcher, window, row, right, style.vertical, attribute
                )
        if height - 1 < rows:
            self._write_line(
                dispatcher, window, height - 1, 0, style.bottom(width), attribute
            )

    @staticmethod
    def _write_line(
        dispatcher: CursesDispatcher,
        window: Any,
        row: int,
        column: int,
        text: str,
        attribute: int,
    ) -> None:
        """Write ``text`` at one position, clipped to what the window holds.

        Two things curses will not do for us. It wraps a write that runs past
        the right edge onto the next row rather than dropping it, so anything
        too wide has to be cut here; and it refuses a write that fills the
        last cell of the last row, because that would scroll a window with
        nowhere to scroll to - so that one cell is inserted instead, which
        puts the character there without advancing. insstr rather than insch
        because a box-drawing character is multibyte and does not fit in the
        single chtype insch takes.
        """
        rows, columns = dispatcher.call(window.getmaxyx)
        if not 0 <= row < rows or not 0 <= column < columns:
            return
        text = _one_cell_each(text)
        text = text[: columns - column]
        if not text:
            return
        with contextlib.suppress(_curses.error):
            if column + len(text) >= columns:
                if text[:-1]:
                    dispatcher.call(window.addstr, row, column, text[:-1], attribute)
                dispatcher.call(window.insstr, row, columns - 1, text[-1], attribute)
            else:
                dispatcher.call(window.addstr, row, column, text, attribute)


#: What a character that is not one printable cell is drawn as instead.
#: A tab becomes a space because a tab IS whitespace - it simply does not
#: advance to a tab stop yet; see TkCurses-wy7. Everything else becomes a
#: question mark, which is visible: a stray control character in a widget is
#: a bug somewhere, and silently drawing nothing hides it.
_STAND_IN = {"\t": " "}


def _one_cell_each(text: str) -> str:
    """Replace anything that would not occupy exactly one cell.

    Every column calculation in this library - clipping to a window, the
    insert cursor, ``bbox``, mapping a click back to an index - assumes one
    character is one cell. A control character breaks that assumption at the
    only point where it cannot be checked: curses draws it as the terminal
    sees fit, and the arithmetic has already been done.

    Measured before this existed: a Text holding "\tAB" drew A at column 10
    while reporting it at column 4, because curses expanded the tab to a tab
    stop and the widget had counted it as one. A Label holding "A\tB" lost
    the B entirely, and an Entry holding "C\tD" pushed the D seven columns
    into a twenty-column box. Every widget was affected, because they all
    write through here.

    The substitution is length-preserving on purpose, so the clipping either
    side of it stays correct.
    """
    if text.isprintable():
        return text
    return "".join(
        character if character.isprintable() else _STAND_IN.get(character, "?")
        for character in text
    )


class Frame(_Drawable):
    """A container, and the first widget that draws itself.

    A frame is a rectangle of background with an optional border, and
    somewhere to put other widgets. Everything interesting about it is
    inherited - it is packed or gridded like anything else, and it lays its
    own children out with a manager of their choosing - so what is added here
    is only the painting.

    Its size comes from its children unless ``width`` or ``height`` says
    otherwise. Setting either fixes that dimension, which is how a frame is
    made to hold a shape its contents would not produce on their own.
    """

    #: ``width`` and ``height`` are cells; zero means "ask the children".
    _widget_options: ClassVar[dict[str, Any]] = {
        "height": 0,
        "width": 0,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        class_: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            class_: The class this frame binds and reads options under, as
                tkinter's ``class_`` does. Construction-time only.
            **kw: Options as keywords.
        """
        self._class_name = class_
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()

    def winfo_class(self) -> str:
        """The class this frame binds and reads options under."""
        return self._class_name or type(self).__name__

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, repainting and resizing as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if {"width", "height"} & set(given):
            self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    def _apply_requested_size(self) -> None:
        """Fix the size from the options, or hand the question to the children.

        Setting only one fixes that axis and leaves the other to the children,
        which is what makes a fixed-width sidebar of variable height
        expressible.

        The size is a *request*, not a guarantee: once the frame has children,
        its geometry manager works out what they need and that wins. Tk
        behaves the same way, and the way to keep an explicit size is
        pack_propagate(False) - the gotcha every tkinter user meets once.
        """
        width = int(self._options["width"])
        height = int(self._options["height"])
        if width or height:
            self._request_size(
                width or self._requested.width, height or self._requested.height
            )

    def _redraw(self) -> None:
        """Paint the frame: background first, then its border.

        Silent without a window or a screen, which is every frame until it has
        been laid out and the terminal is running.
        """
        window = self._window
        if window is None or self.tk.screen is None:
            return
        width, height = self._rect.width, self._rect.height
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(dispatcher, window, width, height, attribute)


def _repaint_when_image_is_collected(reference: weakref.ref[Any]) -> None:
    """Repaint the widget behind ``reference``, its image having gone.

    Module level and weak on purpose: a bound method here would make the
    image own the widget, and the point of the whole arrangement is that it
    does not.
    """
    widget = reference()
    if widget is not None and widget.winfo_exists():
        # Repaint, and deliberately do NOT re-measure. Measured on Tk 9.0.2,
        # deleting an image a Label was showing left the label at its old
        # 22x12 after an update: the geometry it negotiated stays, and only
        # the drawing stops. Re-measuring here would collapse it to nothing,
        # which is tidier and is not what tkinter code has been written
        # against.
        widget._redraw()


#: Cells left between an image and the text beside it. Tk leaves one pixel,
#: which is a fraction of a cell and rounds to nothing; horizontally a whole
#: cell is needed or the art and the first letter run together, while stacked
#: rows are already distinct without one.
IMAGE_GAP = 1


class _TextWidget(_Drawable):
    """A widget whose size and appearance come from a run of text.

    Label and Button both are: they measure themselves from their text, wrap
    it, justify it against itself and anchor the block within whatever area
    they were given. What separates them is what they do afterwards, not how
    the text gets there.

    ``justify`` and ``anchor`` are different questions and a one-line widget
    shows no difference between them: justify aligns the lines against each
    other, anchor puts the resulting block within the widget.
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "anchor": "center",
        "compound": "none",
        "font": "",
        "height": 0,
        "image": "",
        "justify": "center",
        "state": "normal",
        "text": "",
        "textvariable": None,
        "underline": -1,
        "width": 0,
        "wraplength": 0,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``text``, ``textvariable``, ``anchor``, ``justify``,
                ``wraplength``, ``width``, ``height``, ``state``,
                ``underline``, ``font``, and the standard options.
        """
        self._variable_trace: tuple[Variable, str] | None = None
        #: The name of the image this widget is listening to, so that
        #: pointing it at a second one can stop listening to the first. The
        #: NAME, not the image: holding the object would keep it alive, and
        #: an image a widget cannot outlive is the one thing Tk's arrangement
        #: guarantees against.
        self._watched_image: str = ""
        #: Fires when that image is collected, so the widget can repaint
        #: itself empty. See _follow_image.
        self._image_finalizer: weakref.finalize[Any, None] | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._follow_variable()
        self._follow_image()
        self._apply_requested_size()

    # -------------------------------------------------------------- content

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if "textvariable" in given:
            self._follow_variable()
        if "image" in given:
            self._follow_image()
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    # ---------------------------------------------------------------- images

    def _follow_image(self) -> None:
        """Listen to the ``image`` option's image, dropping any previous one.

        Measured on Tk 9.0.2: resizing an image from 4x2 to 20x10 moved a
        live Label's requested size from 6x4 to 22x12 with nothing asked of
        the label at all. A widget follows its image, so it has to be told.

        Raises:
            TclError: If the option names an image that does not exist, which
                is what Tk raises: ``image "nosuch" does not exist``.
        """
        previous = self.tk.images.get(self._watched_image)
        if previous is not None:
            previous._unwatch(self)
        if self._image_finalizer is not None:
            self._image_finalizer.detach()
            self._image_finalizer = None
        self._watched_image = ""
        option = self._options["image"]
        if not option:
            return
        # Normalised to the name, because that is what Tk stores: measured on
        # 9.0.2, a Label built with image=<PhotoImage> answers cget("image")
        # with 'pyimage1'. Keeping the object instead would quietly make the
        # widget an owner of its image, and the whole weak arrangement - a
        # widget outliving its art rather than the other way round - would
        # stop being true the moment anyone passed an object.
        name = str(option)
        self._options["image"] = name
        image = self.tk.images.get(name)
        if image is None:
            raise TclError(f'image "{name}" does not exist')
        image._watch(self, self._image_changed)
        self._watched_image = name
        # An image going away has to repaint the widget, and collection is
        # silent: the registry simply stops holding it, and _users dies with
        # it, so the watch above cannot be what says so. Without this a
        # widget goes on showing art whose image no longer exists - not
        # merely stale, but undrawable, since _image() already returns None
        # and only the last painted cells are still on the screen.
        #
        # Weak on the widget, or the image would keep alive the very widget
        # that is supposed to outlive it. atexit=False because this paints,
        # and interpreter shutdown is no time to be calling curses.
        self._image_finalizer = weakref.finalize(
            image, _repaint_when_image_is_collected, weakref.ref(self)
        )

    def _image_changed(self) -> None:
        """Re-measure and repaint after the image under this widget moved."""
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()

    def _image(self) -> Image | None:
        """The image to draw, or None.

        A name that no longer resolves gives None rather than raising. That
        is deliberate and it is Tk's behaviour: measured, deleting an image a
        Label was showing left the label alive at its old size with the dead
        name still in its ``image`` option. Only *setting* an unknown name is
        an error; having one go away underneath is the documented trap.
        """
        name = str(self._options["image"])
        if not name:
            return None
        return self.tk.images.get(name)

    def _follow_variable(self) -> None:
        """Track the ``textvariable``, dropping any previous one.

        The old trace has to go: a label pointed at a second variable that
        still answered to the first would take its text from whichever was
        written to last.
        """
        if self._variable_trace is not None:
            variable, handle = self._variable_trace
            variable.trace_remove("write", handle)
            self._variable_trace = None
        variable = self._options["textvariable"]
        if variable is None:
            return
        handle = variable.trace_add("write", lambda *_: self._variable_changed())
        self._variable_trace = (variable, handle)
        self._variable_changed()

    def _variable_changed(self) -> None:
        """Re-measure and repaint after the variable behind the text moved.

        The ``text`` option is kept in step with the variable, which is what
        Tk does: measured on 9.0.2, a Label built with ``textvariable=`` and
        no ``text=`` answers ``cget("text")`` with the variable's value and
        keeps answering with it as the variable changes.

        It did not here, and the display was right the whole time - ``_text``
        prefers the variable - so every screen looked correct and only code
        that *asked* a widget what it was showing got an answer that was not
        on the screen.

        Written into the options directly rather than through ``configure``:
        that would re-enter the option machinery on every write, and a
        ``configure`` that wrote the variable back would have the two chasing
        each other.
        """
        variable = self._options["textvariable"]
        if variable is not None:
            self._options["text"] = str(variable.get())
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()

    def _text(self) -> str:
        """The text to display.

        A ``textvariable`` wins over ``text`` when both are set, which is what
        tkinter does: the variable is the live one.
        """
        variable = self._options["textvariable"]
        if variable is not None:
            return str(variable.get())
        return str(self._options["text"])

    def _lines(self) -> list[str]:
        """The text as display lines, wrapped if ``wraplength`` says so."""
        return wrap(self._text(), int(self._options["wraplength"]))

    def _content_size(self) -> tuple[int, int]:
        """How big the image and text together are, in cells."""
        width, height = 0, 0
        for _, rect in self._content_layout():
            width = max(width, rect.x + rect.width)
            height = max(height, rect.y + rect.height)
        return width, height

    def _content_layout(self) -> list[tuple[str, Rect]]:
        """Where the image and the text sit relative to each other.

        Returns ``("image", rect)`` and ``("text", rect)`` pairs, each
        positioned within a block whose origin is (0, 0); the caller anchors
        that block wherever the widget's area allows.

        The arrangement is ``compound``, and its default is the part that
        surprises people. Measured on Tk 9.0.2, a Label with both
        ``text='hello'`` and an 8x4 image:

            compound=none (DEFAULT)  10x6  <- the image, and no text at all
            compound=left/right      45x23    side by side
            compound=top/bottom      36x28    stacked
            compound=center          36x23    the text over the image

        So setting an image on a labelled widget silently hides its text
        unless compound says otherwise, and reproducing that matters more
        than the arrangement being a sensible default.
        """
        lines = self._lines()
        text = Rect(0, 0, *measure(lines))
        image = self._image()
        if image is None:
            # Including when there is no text either: an empty label still
            # occupies a row, because measure([""]) is one line high, and
            # that is what keeps a blank label from collapsing.
            return [("text", text)]
        # In CELLS. The image is a plane of pixels half a cell tall, so its
        # height halves here and its width does not - see ARCHITECTURE.md's
        # "The pixel". Laying out in pixels would make every image twice as
        # tall as it draws.
        picture = Rect(0, 0, image.width(), image.cell_height())
        compound = str(self._options["compound"] or "none")
        if compound == "none" or not self._text():
            # An image and no text is just the image, however compound reads:
            # otherwise an empty string would reserve a gap and a row for
            # nothing.
            return [("image", picture)]
        if compound == "center":
            width = max(picture.width, text.width)
            height = max(picture.height, text.height)
            return [
                (
                    "image",
                    picture.translated(
                        (width - picture.width) // 2, (height - picture.height) // 2
                    ),
                ),
                (
                    "text",
                    text.translated(
                        (width - text.width) // 2, (height - text.height) // 2
                    ),
                ),
            ]
        if compound in ("left", "right"):
            height = max(picture.height, text.height)
            first, second = (picture, text) if compound == "left" else (text, picture)
            names = ("image", "text") if compound == "left" else ("text", "image")
            return [
                (names[0], first.translated(0, (height - first.height) // 2)),
                (
                    names[1],
                    second.translated(
                        first.width + IMAGE_GAP, (height - second.height) // 2
                    ),
                ),
            ]
        width = max(picture.width, text.width)
        first, second = (picture, text) if compound == "top" else (text, picture)
        names = ("image", "text") if compound == "top" else ("text", "image")
        return [
            (names[0], first.translated((width - first.width) // 2, 0)),
            (names[1], second.translated((width - second.width) // 2, first.height)),
        ]

    def _apply_requested_size(self) -> None:
        """Ask for room for the content, or for the size the options name.

        Padding and any border are included: a label asks for what it needs to
        draw, not for what is left after the frame around it.
        """
        text_width, text_height = self._content_size()
        width = int(self._options["width"]) or text_width
        height = int(self._options["height"]) or text_height
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            width + 2 * int(self._options["padx"]) + edge,
            height + 2 * int(self._options["pady"]) + edge,
        )

    # ------------------------------------------------------------- painting

    def _redraw(self) -> None:
        """Paint the background, the border if any, and then the text."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            self._draw_text(dispatcher, window, attribute)

    def _draw_text(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Write the image and the lines into the area left after the border."""
        # Cleared here rather than in _draw_image, which is only reached when
        # there IS an image. A widget whose image has been collected draws
        # nothing and never gets there, so its cells would be repainted past
        # curses for ever - the stale art UAT 35 exists to demonstrate.
        painter = getattr(self.tk, "painter", None)
        if painter is not None:
            painter.clear(self)
        area = self._text_area()
        if area.is_empty:
            return
        layout = self._content_layout()
        places = dict(layout)
        if "image" in places:
            self._draw_image(dispatcher, window, area, places["image"], layout)
        if "text" not in places:
            # compound=none with an image: the text is not drawn at all.
            return
        lines = self._lines()
        attribute |= self._text_attribute()
        across, down = parse_anchor(str(self._options["anchor"]))
        block_width, _ = measure(lines)
        # Clamped to the top, the way the column below is clamped to the
        # left: text taller than the widget has to lose its end rather than
        # its beginning, or it cannot be read at all.
        content_width, content_height = self._content_size()
        text_place = places["text"]
        origin_x = area.x + int((area.width - content_width) * across)
        origin_y = max(area.y, area.y + int((area.height - content_height) * down))
        top = origin_y + text_place.y
        justify = str(self._options["justify"])
        for index, line in enumerate(lines):
            row = top + index
            if not (area.y <= row < area.y + area.height):
                continue
            # Justify from the line's real length, then clip. Clipping first
            # measures the wrong thing: a line wider than the area comes back
            # shortened, and centring the shortened version pushes it right,
            # so text too long to fit ends up hard against the far edge with
            # its beginning cut off.
            column = origin_x + text_place.x
            column += align_offset(len(line), block_width, justify)
            column = max(column, area.x)
            text = clip_text(line, area.x + area.width - column)
            # Through _write_line, which clips again to the window: the area
            # is the widget's, and a widget the screen edge cuts in half has
            # a window smaller than that.
            self._write_line(dispatcher, window, row, column, text, attribute)
        self._draw_underline(dispatcher, window, area, lines, attribute)

    def _draw_image(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        place: Rect,
        layout: list[tuple[str, Rect]],
    ) -> None:
        """Paint the image's cells into ``area`` at ``place``.

        A cell holding None is a hole and is skipped rather than written as a
        space, so art that is not a full rectangle - and a bitmap's clear
        bits - show whatever is behind them instead of punching a block of
        background through it.
        """
        painter = getattr(self.tk, "painter", None)
        image = self._image()
        if image is None:
            return
        del layout
        content_width, content_height = self._content_size()
        across, down = parse_anchor(str(self._options["anchor"]))
        origin_x = area.x + int((area.width - content_width) * across)
        origin_y = max(area.y, area.y + int((area.height - content_height) * down))
        # The same compose() a Canvas draws through, on the same plane: it
        # folds each pair of pixel rows into one cell and says which glyph
        # and which two colours that cell needs. A background of None means
        # the unlit half should show the widget's own colour rather than one
        # of the image's.
        colors = self.tk.colors
        # Absolute screen position, because the painter writes past curses
        # and curses windows are the only thing that knows about offsets.
        where = self._screen_rect()
        buffer = self.tk.screen.buffer if self.tk.screen is not None else None
        background = str(self._options["background"] or "black")
        # Only the pixels that can land in the area. Composing the whole
        # image and discarding what falls outside made a repaint cost what
        # the IMAGE costs rather than what the WINDOW costs: measured, a
        # 320x200 photograph took 47ms a repaint on a 24-row screen, which
        # is past the 50-80ms boundary where ncurses starts dropping mouse
        # reports once a runner is a few times slower.
        # Exact, with no slack. A cell holds ROWS_PER_CELL pixel rows and
        # compose() pairs them from the image's own origin, so area.height
        # cells span exactly that many rows - a spare cell either way was
        # only ever a margin against arithmetic nobody had checked.
        first_row = (area.y - origin_y - place.y) * ROWS_PER_CELL
        last_row = first_row + area.height * ROWS_PER_CELL
        first_column = area.x - origin_x - place.x
        last_column = first_column + area.width
        visible = image.lit((first_column, first_row, last_column, last_row))
        for (x, y), (glyph, fore, back) in compose(visible).items():
            line = origin_y + place.y + y
            column = origin_x + place.x + x
            if not (area.y <= line < area.y + area.height):
                continue
            if not (area.x <= column < area.x + area.width):
                continue
            if colors is None:
                attribute = _curses.A_NORMAL
            else:
                attribute = colors.attribute_for(fore, back or background)
            # Written through curses as well, always. If direct painting
            # never happens - no truecolor, a terminal that ignores it, a
            # closed stream - what shows is the ordinary rendering rather
            # than a hole where the picture was.
            self._write_line(dispatcher, window, line, column, glyph, attribute)
            if painter is not None and painter.enabled:
                screen_row = where.y + line
                screen_column = where.x + column
                # Clipped to the screen, because this writes to the terminal
                # rather than to a window: a position outside it is not
                # ignored the way curses ignores one, it lands somewhere
                # else and can scroll what is already there.
                on_screen = buffer is not None and buffer.contains(
                    screen_row, screen_column
                )
                exact_fore = rgb_of(fore) if on_screen else None
                exact_back = rgb_of(back or background) if on_screen else None
                if exact_fore is not None and exact_back is not None:
                    painter.add(
                        self,
                        screen_row,
                        screen_column,
                        glyph,
                        exact_fore,
                        exact_back,
                    )

    def _text_area(self) -> Rect:
        """Where the text may go, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    _STATE_COLOURS: ClassVar[dict[str, tuple[str | None, str | None]]] = {
        "active": ("activeforeground", "activebackground"),
        "disabled": ("disabledforeground", None),
    }

    def _shown_state(self) -> str:
        """The state the widget is drawn in: ``active`` while held down.

        Tk's press is always on an active button - the pointer is over it,
        or Space has set the state for the flash, in ``tk::ButtonInvoke`` -
        so its active colours show through a press. Here a press is ``_pressed``, on the widgets that
        have one.
        """
        if getattr(self, "_pressed", False):
            return "active"
        return str(self._options["state"])

    def _background_attribute(self) -> int:
        """The widget's colours, or its state's if a program gave them.

        The whole widget, as Tk paints it: an active button's background is
        ``activebackground`` from edge to edge, not only behind the text.
        """
        attribute = super()._background_attribute()
        colours = self._state_colours(self._shown_state())
        return attribute if colours is None else self._coloured(attribute, *colours)

    def _text_attribute(self) -> int:
        """Attributes the font and state put on the text.

        A state given colours is shown by them, in ``_background_attribute``,
        and not reversed or dimmed as well.
        """
        attribute = self._font_attribute()
        state = str(self._options["state"])
        if self._state_colours(state) is None:
            with contextlib.suppress(ValueError):
                attribute = for_state(state, attribute)
        return attribute

    def _draw_underline(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        lines: list[str],
        attribute: int,
    ) -> None:
        """Underline one character, as tkinter's ``underline`` index does.

        The index counts through the text as written, so on wrapped text it
        has to be resolved to a line and a column rather than used directly.
        """
        index = int(self._options["underline"])
        if index < 0:
            return
        remaining = index
        line_number: int | None = None
        for number, line in enumerate(lines):
            if remaining < len(line):
                line_number = number
                break
            remaining -= len(line)
        if line_number is None:
            # The index runs past the end of the text, which is how tkinter
            # code switches the underline off without removing the option.
            return
        block_width, block_height = measure(lines)
        across, down = parse_anchor(str(self._options["anchor"]))
        top = max(area.y, area.y + int((area.height - block_height) * down))
        row = top + line_number
        column = area.x + int((area.width - block_width) * across)
        column += align_offset(
            len(lines[line_number]), block_width, str(self._options["justify"])
        )
        with contextlib.suppress(_curses.error):
            self._write_line(
                dispatcher,
                window,
                row,
                column + remaining,
                lines[line_number][remaining],
                attribute | _curses.A_UNDERLINE,
            )


class Label(_TextWidget):
    """A run of text.

    Its size comes from the text unless ``width`` or ``height`` says
    otherwise, so a label is as wide as its longest line and as tall as it has
    lines. ``wraplength`` breaks the text at that many cells, at word
    boundaries where it can.
    """

    _widget_options: ClassVar[dict[str, Any]] = dict(_STATE_COLOUR_OPTIONS)


class Button(_TextWidget):
    """A button: text in a box that runs something when pressed.

    Invoked by a mouse click, by Return, or by the space bar when it has the
    focus - the three gestures a terminal offers. ``invoke()`` does the same
    thing from code, which is how a dialog's default button is triggered by
    something else entirely.

    Focus and press are shown by markers either side of the text rather than
    by colour: ``|> OK <|`` when focused, and reversed while held down. A
    terminal cannot be relied on for colour, and a button nobody can see the
    focus on is a button nobody can use from the keyboard.
    """

    #: The markers drawn either side of the text. Room for them is reserved
    #: whether or not they are showing, so a button does not change width when
    #: it gains the focus.
    _FOCUS_MARKERS = ("\u25b6", "\u25c0")
    _PRESSED_MARKERS = ("\u258c", "\u2590")

    #: Cells the markers and their spacing occupy, either side of the text.
    _MARKER_WIDTH = 2

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_STATE_COLOUR_OPTIONS,
        "command": None,
        "default": "disabled",
        # The relief while the pointer is over it; "" for no change. Put in
        # place by the <Enter> binding, as Tk's is. TkCurses-gm66.5.
        "overrelief": "",
        "relief": "raised",
        # How long a press waits before invoking again, and how often after
        # that; 0 for never, Tk's default. TkCurses-gm66.6.
        "repeatdelay": 0,
        "repeatinterval": 0,
        "takefocus": True,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``command``, ``state``, plus everything a Label takes.
        """
        self._pressed = False
        self._entered_relief: tuple[str, str] | None = None
        self._repeated = 0
        self._pointer_inside = False
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the default behaviour for every Button in this application.

        Class bindings rather than instance ones, so that a binding of the
        same event on one button runs first and can stop this one with
        ``"break"`` - which is what tkinter's binding order is for, and what
        lets an application override a default without removing it.
        """
        # winfo_class() and not the literal "Button": a subclass that reports
        # another name - ttk.Button reports TButton - binds under that name,
        # and binding under this one would leave it with no bindings at all.
        # Binding tags name one class rather than a chain, so a themed button
        # would have been a button that answered nothing. _ChoiceWidget and
        # Menubutton already ask; this one did not, and it is the same fault
        # that has bitten Spinbox/Entry, OptionMenu/Menubutton and
        # ScrolledText/Text from the other direction.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        self.bind_class(name, "<Button-1>", _button_press)
        self.bind_class(name, "<ButtonRelease-1>", _button_release)
        self.bind_class(name, "<Key-Return>", _button_key)
        self.bind_class(name, "<Key-space>", _button_key)
        self.bind_class(name, "<FocusIn>", _button_refresh)
        self.bind_class(name, "<FocusOut>", _button_refresh)
        if not _is_ttk(self):
            self.bind_class(name, "<Enter>", _button_enter)
            self.bind_class(name, "<Leave>", _button_leave)
            # Where a held press is, for auto-repeat: Tk's Priv(window).
            self.bind_class(name, "<Motion>", _button_motion)

    # ------------------------------------------------------------ behaviour

    def invoke(self) -> Any:
        """Run the button's command and return whatever it returns.

        Does nothing when the button is disabled, which is the whole point of
        disabling one: the guard belongs here rather than in every caller.
        """
        if self._disabled:
            return None
        command = self._options["command"]
        if command is None:
            return None
        return command()

    def flash(self) -> None:
        """Blink the button, as tkinter's does.

        Drawn twice through the dispatcher rather than with a sleep: a button
        that stopped the event loop to flash would also stop the thing it just
        invoked.
        """
        if self._disabled:
            return
        self._pressed = not self._pressed
        self._redraw()
        self.after(80, self._end_flash)

    def _end_flash(self) -> None:
        """Put the button back the way it was after a flash."""
        self._pressed = False
        self._redraw()

    # ------------------------------------------------------------- painting

    def _apply_requested_size(self) -> None:
        """Ask for the text's room plus the markers either side of it."""
        super()._apply_requested_size()
        self._request_size(
            self._requested.width + 2 * self._MARKER_WIDTH, self._requested.height
        )

    def _redraw(self) -> None:
        """Paint the button, then its focus or pressed markers."""
        super()._redraw()
        self._draw_markers()

    def _draw_markers(self) -> None:
        """Draw the markers either side of the text, if there are any to draw."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        if self._pressed:
            left, right = self._PRESSED_MARKERS
        elif self.focus_get() is self:
            left, right = self._FOCUS_MARKERS
        else:
            return
        area = self._text_area()
        if area.is_empty or area.width < 2 * self._MARKER_WIDTH:
            return
        row = area.y + area.height // 2
        attribute = self._background_attribute() | self._text_attribute()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(_curses.error):
            self._write_line(dispatcher, window, row, area.x, left, attribute)
            self._write_line(
                dispatcher, window, row, area.x + area.width - 1, right, attribute
            )


def _button_press(event: Event) -> None:
    """Show the button held down.

    Shared with Checkbutton, which presses and releases the same way and
    differs only in what invoking it does.

    The focus is deliberately left where it was, which is what Tk does -
    checked against Tk 9.0.2, where clicking a button, checkbutton,
    radiobutton, scale or menubutton leaves the focus alone and only an
    entry, spinbox, text or listbox takes it. The rule is worth stating,
    because taking the focus here is superficially helpful and actively
    harmful: a button binds Space and Return to invoke itself, so a button
    that took the focus on being clicked would quietly swallow both from
    whatever had them, and every later Space would press it again.
    """
    button = event.widget
    if button._disabled:
        return
    button._pressed = True
    button._redraw()
    # tk::ButtonDown: a repeatdelay starts the auto-repeat. A repeating press
    # is held on purpose for longer than the recovery allows, so it is not
    # armed for one; Tk._release_lost stands in for it.
    button._repeated = 0
    button._pointer_inside = True
    delay = _repeat_option(button, "repeatdelay")
    if delay > 0:
        _repeat_after(button, delay, _button_auto_invoke, button)
    else:
        _arm_press_recovery(button)


def _button_auto_invoke(button: Any) -> None:
    """Invoke a held button again: Tk's ``tk::ButtonAutoInvoke``.

    Only while the pointer is still over it, as Tk's ``Priv(window)`` says;
    the repeat itself goes on, so coming back over it carries on invoking.
    """
    if button._pointer_inside:
        button._repeated += 1
        button.invoke()
    interval = _repeat_option(button, "repeatinterval")
    if interval > 0:
        _repeat_after(button, interval, _button_auto_invoke, button)


def _button_motion(event: Event) -> None:
    """Note whether a held press is still over the button."""
    button = event.widget
    if button._pressed:
        button._pointer_inside = _within(button, event)


#: The mouse states that put a button down: a double or triple click is a
#: press as well.
_PRESSES = ("pressed", "clicked", "double", "triple")

#: How long a button may stay drawn pressed with no release in sight.
#: Longer than any click, and shorter than a person will spend looking at a
#: control that has stopped working.
PRESS_RECOVERY_MS = 700


def _arm_press_recovery(button: Any) -> None:
    """Put the button back up if its release never arrives.

    **ncurses drops mouse reports that arrive faster than the application
    drains them.** Measured with a plain curses program, no TkCurses
    involved: a handler taking 120ms loses two of the four events from two
    clicks. So a release can simply never be delivered, and a button whose
    look depends on it stays drawn pressed and never invokes - until
    something else happens to repaint it.

    It was filed as needing "a handler slower than any in the library"
    (TkCurses-9lr). Measured on a real screen, that is not so: a Text of
    5000 lines redraws in 350ms and a Canvas of 500 items in 766ms, either
    of which is well past the 50-80ms where reports start being lost. A
    click handler that repaints one of those is enough.

    Recovering rather than preventing, because nothing downstream can
    recover a report ncurses never parsed. The worst case becomes a flicker
    instead of a control that has to be clicked twice to come back.
    """
    handle = getattr(button, "_press_recovery", None)
    if handle is not None:
        with contextlib.suppress(Exception):
            button.after_cancel(handle)

    def recover() -> None:
        button._press_recovery = None
        if button._pressed and button.winfo_exists():
            button._pressed = False
            button._redraw()

    button._press_recovery = button.after(PRESS_RECOVERY_MS, recover)


def _disarm_press_recovery(button: Any) -> None:
    """Drop the safety timer once the release has actually arrived."""
    handle = getattr(button, "_press_recovery", None)
    if handle is not None:
        button._press_recovery = None
        with contextlib.suppress(Exception):
            button.after_cancel(handle)


def _cancel_repeat(widget: Misc) -> None:
    """Stop whatever is auto-repeating: Tk's ``tk::CancelRepeat``."""
    handle = widget.tk.repeat
    if handle is not None:
        widget.tk.repeat = None
        with contextlib.suppress(Exception):
            widget.after_cancel(handle)


def _repeat_after(widget: Misc, ms: int, func: Callable[..., Any], *args: Any) -> None:
    """Schedule the next step of an auto-repeat, in place of any pending one."""
    _cancel_repeat(widget)

    def step() -> None:
        widget.tk.repeat = None
        if widget.winfo_exists():
            func(*args)

    widget.tk.repeat = widget.after(ms, step)


def _repeat_option(widget: Any, name: str) -> int:
    """``repeatdelay`` or ``repeatinterval``, as milliseconds; 0 for none.

    A ttk widget has neither, in Tk: its repeat is ``ttk::Repeatedly``, with
    its own timing, and is not taken here.
    """
    if _is_ttk(widget) or name not in widget._options:
        return 0
    return _as_int(widget._options[name], 0)


def _button_release(event: Event) -> None:
    """Invoke the button, unless the pointer left it first.

    Tk invokes on release rather than press so that pressing and moving away
    is a way to change your mind, which is what every other toolkit does too.
    The release reaches this widget wherever the pointer ended up, because of
    the implicit grab, so whether it counts has to be decided here.
    """
    button = event.widget
    _disarm_press_recovery(button)
    _cancel_repeat(button)
    if not button._pressed:
        return
    button._pressed = False
    button._redraw()
    # tk::ButtonUp: a press that has auto-repeated has invoked already.
    if not button._disabled and _within(button, event) and not button._repeated:
        button.invoke()


def _within(widget: Misc, event: Event) -> bool:
    """True if an event's position lies inside a widget."""
    left, top = widget.winfo_rootx(), widget.winfo_rooty()
    return (
        left <= event.x_root < left + widget.winfo_width()
        and top <= event.y_root < top + widget.winfo_height()
    )


def _button_key(event: Event) -> str:
    """Invoke the button from the keyboard.

    Bound to Return and space on a Button and to space alone on a
    Checkbutton, so which keys reach here is the caller's choice.

    Returns ``"break"`` so the key does not also reach whatever else is bound
    to it - a Return that both presses the button and submits a dialog would
    do the same thing twice.
    """
    button = event.widget
    if not button._disabled:
        button.invoke()
    return "break"


def _button_refresh(event: Event) -> None:
    """Repaint after the focus moved in or out."""
    event.widget._redraw()


def _button_enter(event: Event) -> None:
    """The pointer arrives: the button goes active, in its ``overrelief``.

    Tk's ``tk::ButtonEnter`` and ``tk::CheckEnter``, their X11 versions, in
    ``button.tcl``. ``configure`` rather than a flag, as there, so ``cget``
    reads the relief that is showing. Tk sinks a button re-entered while held;
    a press here is drawn by markers and not by a relief, so a held one keeps
    the relief it has. Nothing reports the pointer crossing a widget yet, so
    this is reached by ``event_generate``. TkCurses-gm66.5.
    """
    button = event.widget
    if button._disabled:
        return
    button.configure(state=ACTIVE)
    over = str(button.cget("overrelief"))
    if over and not button._pressed:
        button._entered_relief = (str(button.cget("relief")), over)
        button.configure(relief=over)


def _button_leave(event: Event) -> None:
    """The pointer goes: back to normal, and the relief it entered with.

    Tk's ``tk::ButtonLeave``: the relief goes back only if it is still the
    one the entry put there, so a program that changed it meanwhile keeps
    its change.
    """
    button = event.widget
    if not button._disabled:
        button.configure(state=NORMAL)
    saved, button._entered_relief = button._entered_relief, None
    if saved is not None and saved[1] == str(button.cget("relief")):
        button.configure(relief=saved[0])


class _ChoiceWidget(_TextWidget):
    """Shared by the two widgets whose state lives in a variable.

    Checkbutton and Radiobutton draw the same way - a small indicator, a
    space, then a label - and keep the same relationship with their
    variable: neither holds any state of its own, both repaint when the
    variable is written, and both let two widgets over one variable agree
    without either knowing the other exists. What separates them is what the
    indicator means and what pressing one does, which is all a subclass has
    to say.
    """

    #: The indicator in each state, unfocused and focused. Focus changes the
    #: brackets rather than the colour: the width is the same either way, so
    #: nothing moves under the hand when the focus arrives, and it survives a
    #: terminal with no colour - the same reason Button draws markers.
    _INDICATORS: ClassVar[dict[str, tuple[str, str]]] = {}

    #: Cells the indicator and the space after it take from the text.
    _INDICATOR_WIDTH = 4

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_STATE_COLOUR_OPTIONS,
        # The indicator's background, and an indicatorless button's while it
        # is on. "" here, Tk's #ffffff: the indicator as it was drawn before.
        "selectcolor": "",
        "command": None,
        "indicatoron": True,
        # An indicatorless button's relief while off, and any button's while
        # the pointer is over it. TkCurses-gm66.5.
        "offrelief": "raised",
        "overrelief": "",
        "takefocus": True,
        "variable": None,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``variable``, ``command``, ``indicatoron``, whatever else
                the subclass declares, plus everything a Label takes.
        """
        self._pressed = False
        self._entered_relief: tuple[str, str] | None = None
        self._repeated = 0
        self._pointer_inside = False
        self._value_trace: tuple[Variable, str] | None = None
        super().__init__(master, cnf, name=name, **kw)
        if self._options["variable"] is None:
            self._options["variable"] = self._make_variable()
        self._follow_value()
        self._install_class_bindings()

    def _make_variable(self) -> Variable:
        """The variable to use when the caller named none."""
        raise NotImplementedError

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the default behaviour for every widget of this class.

        The same handlers Button uses, less Return: Tk's checkbutton and
        radiobutton answer the space bar and not Return, so that Return
        still reaches a dialog's default button from wherever the focus is.
        """
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Button-1>", _button_press)
        bind(name, "<ButtonRelease-1>", _button_release)
        bind(name, "<Key-space>", _button_key)
        bind(name, "<FocusIn>", _button_refresh)
        bind(name, "<FocusOut>", _button_refresh)
        if not _is_ttk(self):
            bind(name, "<Enter>", _button_enter)
            bind(name, "<Leave>", _button_leave)

    # --------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, following a new variable if one was named."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if "variable" in given:
            self._follow_value()
            self._redraw()
        return result

    config = configure

    def _follow_value(self) -> None:
        """Track the ``variable``, dropping any previous one.

        The old trace has to go for the same reason a Label's does: a widget
        still answering the variable it used to show would repaint itself
        whenever something unrelated wrote to it.
        """
        if self._value_trace is not None:
            previous, handle = self._value_trace
            previous.trace_remove("write", handle)
            self._value_trace = None
        variable = self._options["variable"]
        if variable is None:
            return
        handle = variable.trace_add("write", lambda *_: self._redraw())
        self._value_trace = (variable, handle)

    @property
    def _indicator_on(self) -> bool:
        """True while the indicator is drawn, false while it is not."""
        try:
            return self.getboolean(self._options["indicatoron"])
        except TclError:
            return True

    # ----------------------------------------------------------------- value

    @property
    def _indicator_state(self) -> str:
        """Which state the variable puts this widget in. Subclasses decide."""
        raise NotImplementedError

    def _value(self) -> Any:
        """What the variable holds, or None if there is no variable left."""
        variable = self._options["variable"]
        return None if variable is None else variable.get()

    def _write(self, value: Any) -> None:
        """Put a value in the variable, if there still is one."""
        variable = self._options["variable"]
        if variable is not None:
            variable.set(value)

    # ------------------------------------------------------------ behaviour

    def _activate(self) -> None:
        """What pressing this widget does to its variable."""
        raise NotImplementedError

    def invoke(self) -> Any:
        """Do what a click does, and run the command.

        Returns whatever the command returns. Does nothing while disabled -
        the guard belongs here rather than in every caller, and ``invoke`` is
        how a key binding, a test and a click all reach one path.
        """
        if self._disabled:
            return None
        self._activate()
        command = self._options["command"]
        return None if command is None else command()

    def flash(self) -> None:
        """Blink the indicator, as tkinter's does.

        Drawn twice through the after-queue rather than with a sleep: a
        widget that stopped the event loop to flash would also stop whatever
        it was flashing about.
        """
        if self._disabled:
            return
        self._pressed = not self._pressed
        self._redraw()
        self.after(80, self._end_flash)

    def _end_flash(self) -> None:
        """Put the indicator back the way it was after a flash."""
        self._pressed = False
        self._redraw()

    # ------------------------------------------------------------- painting

    def _apply_requested_size(self) -> None:
        """Ask for the text's room plus the indicator to the left of it."""
        super()._apply_requested_size()
        if self._indicator_on:
            self._request_size(
                self._requested.width + self._INDICATOR_WIDTH,
                self._requested.height,
            )

    def _text_area(self) -> Rect:
        """Where the text goes: what is left once the indicator has its cells."""
        area = super()._text_area()
        if not self._indicator_on:
            return area
        return Rect(
            area.x + self._INDICATOR_WIDTH,
            area.y,
            max(0, area.width - self._INDICATOR_WIDTH),
            area.height,
        )

    def _text_attribute(self) -> int:
        """Attributes on the text, including the state of an indicatorless one.

        Without an indicator there is nothing else to show it with, so the
        text carries both: reversed while the widget is on, underlined while
        it has the focus.
        """
        attribute = super()._text_attribute()
        if self._indicator_on:
            return attribute
        if self._indicator_state == "on" and not self._selected_colour():
            attribute |= _curses.A_REVERSE
        if self.focus_get() is self:
            attribute |= _curses.A_UNDERLINE
        return attribute

    def _selected_colour(self) -> bool:
        """True if ``selectcolor`` is given and the terminal can show it."""
        return bool(self._options.get("selectcolor")) and self.tk.colors is not None

    def _background_attribute(self) -> int:
        """An indicatorless button that is on takes ``selectcolor`` as its
        background, "in place of background or activeBackground", as Tk's
        manual has it. With an indicator, ``selectcolor`` is the indicator's.
        """
        attribute = super()._background_attribute()
        if (
            self._indicator_on
            or self._indicator_state != "on"
            or not self._selected_colour()
        ):
            return attribute
        active = self._state_colours(self._shown_state())
        foreground = active[0] if active is not None else ""
        return self._coloured(attribute, foreground, self._options["selectcolor"])

    def _border_style(self) -> BorderStyle:
        """The relief an indicatorless button is drawn in, which is not its own.

        Tk's ``TkpDisplayButton``, in ``unix/tkUnixButton.c``: sunken while
        on; otherwise ``offrelief``, unless the relief is the ``overrelief``,
        which is how it tells that the pointer is over it - the ``<Enter>``
        binding has copied one into the other. With an indicator, the relief
        is the widget's own. TkCurses-gm66.5.
        """
        relief = str(self._options["relief"]) or FLAT
        if not self._indicator_on and not _is_ttk(self):
            if self._indicator_state == "on":
                relief = SUNKEN
            elif relief != str(self._options["overrelief"]):
                relief = str(self._options["offrelief"])
        return style_for_relief(relief)

    def _redraw(self) -> None:
        """Paint the widget, then the indicator to the left of the text."""
        super()._redraw()
        self._draw_indicator()

    def _draw_indicator(self) -> None:
        """Draw the indicator, on the row the text's first line sits on."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        place = self._indicator_place()
        if place is None:
            return
        column, row = place
        focused = self.focus_get() is self
        mark = self._INDICATORS[self._indicator_state][1 if focused else 0]
        attribute = self._background_attribute() | self._text_attribute()
        if self._selected_colour():
            attribute = self._coloured(attribute, "", self._options["selectcolor"])
        if self._pressed and self._state_colours("active") is None:
            attribute |= _curses.A_REVERSE
        with contextlib.suppress(_curses.error):
            self._write_line(
                CursesDispatcher.get(), window, row, column, mark, attribute
            )

    def _indicator_place(self) -> tuple[int, int] | None:
        """Where the indicator's first cell is, as ``(column, row)``, if drawn.

        On the row the text's first line sits on. Shared by the painting and
        by ttk's ``identify``, which must name the cells that were drawn.
        """
        if not self._indicator_on:
            return None
        # The whole area, not the text's - _text_area() has already handed
        # the indicator's cells away and would put it on top of the text.
        area = super()._text_area()
        if area.is_empty or area.width < self._INDICATOR_WIDTH:
            return None
        _, block_height = measure(self._lines())
        _, down = parse_anchor(str(self._options["anchor"]))
        return (area.x, area.y + int((area.height - block_height) * down))


class Checkbutton(_ChoiceWidget):
    """A box that is ticked or not, and a variable that says which.

    The widget keeps no state of its own: the tick comes from comparing its
    ``variable`` against ``onvalue`` every time it paints. That is what makes
    two checkbuttons over one variable show the same tick, and what makes
    setting the variable from code move both of them. A checkbutton made
    without a variable is given one, as tkinter's is - it works out of the
    box at the cost of the caller having nothing to read.

    Tk's third state is drawn too. A variable holding neither value - the
    "some of the selected files are read-only" case - shows ``[-]`` rather
    than guessing, and a click from there turns the button on.

    With ``indicatoron`` false there is no box at all: the text reverses
    while the button is on, which is how a checkbutton is used as a toggle
    in a toolbar.
    """

    _INDICATORS: ClassVar[dict[str, tuple[str, str]]] = {
        "on": ("[x]", "<x>"),
        "off": ("[ ]", "< >"),
        "tristate": ("[-]", "<->"),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "offvalue": 0,
        "onvalue": 1,
        "tristatevalue": "",
    }

    def _make_variable(self) -> Variable:
        """A variable of this checkbutton's own, starting at ``offvalue``.

        Plain Variable rather than IntVar: what it has to hold is whatever
        ``onvalue`` and ``offvalue`` are, and those are only integers by
        default. Each checkbutton gets its own, because two unrelated boxes
        that happened to be made without variables must not move together.
        """
        return Variable(master=self, value=self._options["offvalue"])

    @property
    def _indicator_state(self) -> str:
        """Which of the three states the variable puts this button in.

        Tk's order, which matters: on, then the third state, then off as the
        fallback. So an empty variable with the default ``tristatevalue`` of
        ``""`` shows ``[-]`` rather than ``[ ]``, exactly as Tk's does - a
        surprise worth keeping, because code that means "off" should say so.
        """
        value = self._value()
        if _same_value(value, self._options["onvalue"]):
            return "on"
        if _same_value(value, self._options["tristatevalue"]):
            return "tristate"
        return "off"

    def select(self) -> None:
        """Turn the button on by writing ``onvalue`` to its variable."""
        self._write(self._options["onvalue"])

    def deselect(self) -> None:
        """Turn it off by writing ``offvalue``."""
        self._write(self._options["offvalue"])

    def toggle(self) -> None:
        """Flip the button. From the third state it turns on, as Tk does."""
        if self._indicator_state == "on":
            self.deselect()
        else:
            self.select()

    _activate = toggle


class Radiobutton(_ChoiceWidget):
    """One of a set of choices, of which the variable names the one in force.

    A radiobutton is on when its ``variable`` equals its ``value``, so a
    group is not a container or a list - it is however many radiobuttons
    happen to share a variable. Nothing has to be told which buttons belong
    together, and nothing has to turn the others off: they all repaint from
    the same variable and only one of them can match it.

    Pressing one always selects it. There is no way to turn a radiobutton
    off by clicking it, which is the difference from a checkbutton and the
    reason the two are separate widgets; ``deselect`` exists for code that
    wants a group with nothing chosen.

    A radiobutton made without a variable joins Tk's default group, named
    ``selectedButton``, along with every other one in the same application
    that did the same. That is Tk's behaviour and it is worth keeping, but
    it means two unrelated sets of choices both left without variables will
    fight over one value.
    """

    _INDICATORS: ClassVar[dict[str, tuple[str, str]]] = {
        "on": ("(•)", "<•>"),
        "off": ("( )", "< >"),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "value": "",
    }

    #: The group a radiobutton joins when the caller named no variable.
    _DEFAULT_GROUP = "selectedButton"

    def _make_variable(self) -> Variable:
        """Tk's shared default group, one Variable per application.

        Owned by the application rather than made fresh for each button. A
        Variable forgets its value when its last reference goes, and a group
        whose only owners are its own buttons would be at the mercy of which
        of them outlived the others.
        """
        shared = self.tk.shared_variables.get(self._DEFAULT_GROUP)
        if shared is None:
            shared = Variable(master=self, name=self._DEFAULT_GROUP)
            self.tk.shared_variables[self._DEFAULT_GROUP] = shared
        return shared

    @property
    def _indicator_state(self) -> str:
        """On when the variable holds this button's ``value``."""
        if _same_value(self._value(), self._options["value"]):
            return "on"
        return "off"

    def select(self) -> None:
        """Choose this button by writing its ``value`` to the variable."""
        self._write(self._options["value"])

    def deselect(self) -> None:
        """Leave the group with nothing chosen.

        Writes an empty value rather than this button's, which is what Tk
        does: there is no other way to say "none of them" through a variable
        that names the choice in force.
        """
        self._write("")

    _activate = select


def _same_value(left: Any, right: Any) -> bool:
    """True if two option values are the same value as Tcl would see them.

    Tcl has one type, so a StringVar holding ``"1"`` and an ``onvalue`` of
    the integer 1 are the same thing there. Compared by value first, so that
    1 and 1.0 match, and then as text, so that 1 and "1" do.
    """
    if left is None or right is None:
        return left is right
    with contextlib.suppress(TypeError):
        if left == right:
            return True
    return str(left) == str(right)


class Entry(_Drawable, XView):
    """A one-line text field.

    The editing itself is :class:`~tkcurses._core.editing.TextField`; what is
    here is the widget around it - options, key bindings, the cursor and
    selection on screen, and keeping a ``textvariable`` in step both ways.

    ``state`` has three values rather than two. ``readonly`` shows the text
    and lets it be selected and copied but refuses every edit, which is what
    a field displaying a computed value wants; ``disabled`` refuses the focus
    as well.
    """

    #: Tk's validation pair carries short spellings on the classic Entry, and
    #: they are the ones tkinter's own documentation uses - so a program copied
    #: from it failed here on its first line with ``unknown option "-vcmd"``.
    #: Measured: ttk.Entry has validatecommand and refuses vcmd, which is why
    #: these live on this class rather than in the module table.
    _option_synonyms: ClassVar[dict[str, str]] = {
        **_OPTION_ALIASES,
        "vcmd": "validatecommand",
        "invcmd": "invalidcommand",
    }

    _STATE_COLOURS: ClassVar[dict[str, tuple[str | None, str | None]]] = {
        "disabled": ("disabledforeground", "disabledbackground"),
        "readonly": (None, "readonlybackground"),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_INSERT_CURSOR_OPTIONS,
        **_SELECTION_OPTIONS,
        # The disabled and readonly looks; see _STATE_COLOURS. Tk's defaults
        # are real colours, these are "": dimmed, and as normal.
        "disabledbackground": "",
        "disabledforeground": "",
        "readonlybackground": "",
        # tkinter reports 1, not True: the value is what cget answers.
        "exportselection": 1,
        # Tk 9.0's ghost text - TkCurses-xe9.3. On the CLASSIC entry as well as
        # the themed ones: measured, all four of tk.Entry, ttk.Entry,
        # ttk.Combobox and ttk.Spinbox carry both, as standard options.
        "placeholder": "",
        "placeholderforeground": "",
        "font": "",
        "justify": "left",
        "relief": "sunken",
        "show": "",
        "state": "normal",
        "takefocus": True,
        "textvariable": None,
        "validate": "none",
        "validatecommand": None,
        # The third of Tk's validation trio, and -xscrollcommand, both of which
        # this widget lacked: validatecommand could say what was valid and
        # nothing could say what to do when an edit was refused, and an entry
        # could not be attached to a scrollbar. TkCurses-ale.
        "invalidcommand": None,
        "xscrollcommand": None,
        "width": 20,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``width``, ``textvariable``, ``show``, ``state``,
                ``justify``, ``validate``, ``validatecommand``, and the
                standard options.
        """
        self._field = TextField()
        self._variable_trace: tuple[Variable, str] | None = None
        self._syncing = False
        # True while a validation callback is running, so an edit made from
        # inside one can be told apart from an ordinary edit. TkCurses-tvj.
        self._validating = False
        self._edited_while_validating = False
        # True between a press in the text and its release; see _entry_drag.
        self._dragging = False
        # What a drag extends by - "char", "word" after a double-click, "line"
        # after a triple - whether it has moved off the press, where the
        # pointer was last, and the pending autoscroll. TkCurses-svtr.
        self._select_mode = "char"
        self._moved = False
        self._drag_x = 0
        self._autoscan: str | None = None
        # The screen cell the terminal's cursor goes in; see _draw_cursor.
        self._insert_at: tuple[int, int] | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._follow_variable()
        self._apply_requested_size()
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the editing keys for every Entry in this application."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Any-Key>", _entry_key)
        bind(name, "<Button-1>", _entry_click)
        bind(name, "<Motion>", _entry_drag)
        bind(name, "<ButtonRelease-1>", _entry_release)
        bind(name, "<Double-Button-1>", _entry_double)
        bind(name, "<Triple-Button-1>", _entry_triple)
        if not _is_ttk(self):
            # ttk binds no Ctrl-click: there it is a plain click.
            bind(name, "<Control-Button-1>", _entry_control_click)
        for extend in _EXTEND_MODIFIERS:
            bind(name, f"<{extend}-Button-1>", _entry_shift_click)
            if not _is_ttk(self):
                # ttk binds neither; a doubled shift-click there is just one.
                bind(name, f"<Double-{extend}-Button-1>", _entry_double_shift)
                bind(name, f"<Triple-{extend}-Button-1>", _entry_triple_shift)
        bind(name, "<FocusIn>", _entry_focus_in)
        bind(name, "<FocusOut>", _entry_focus_out)
        _bind_entry_clipboard(bind, name)

    # ---------------------------------------------------------------- state

    @property
    def _editable(self) -> bool:
        """True while the field accepts changes from the keyboard."""
        return str(self._options["state"]) == "normal"

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, following a new variable and repainting as needed."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if "textvariable" in given:
            self._follow_variable()
        if "exportselection" in given:
            # Both directions take effect at once, measured: turning it off
            # drops PRIMARY with the selection still in place, and turning it
            # on exports what is already selected without reselecting it.
            self._claim_primary()
        if "width" in given:
            self._apply_requested_size()
            self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    def _apply_requested_size(self) -> None:
        """Ask for the field's width plus whatever the border and padding need."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            int(self._options["width"]) + 2 * int(self._options["padx"]) + edge,
            1 + 2 * int(self._options["pady"]) + edge,
        )

    # ----------------------------------------------------------- the variable

    def _follow_variable(self) -> None:
        """Track the ``textvariable``, dropping any previous one."""
        if self._variable_trace is not None:
            variable, handle = self._variable_trace
            variable.trace_remove("write", handle)
            self._variable_trace = None
        variable = self._options["textvariable"]
        if variable is None:
            return
        handle = variable.trace_add("write", lambda *_: self._variable_changed())
        self._variable_trace = (variable, handle)
        self._variable_changed()

    def _variable_changed(self) -> None:
        """Take the variable's value, unless this widget is what changed it.

        Without the guard the two would chase each other: every keystroke
        writes the variable, whose trace writes the field, which resets the
        cursor the keystroke just moved.
        """
        if self._syncing:
            return
        variable = self._options["textvariable"]
        if variable is None:
            return
        self._field.text = str(variable.get())
        # Tk's "forced" condition. Measured: this fires when the variable is
        # written AND when one is first attached, at construction or by
        # configure(), which is why it lives here rather than in the trace
        # handler alone. TkCurses-3xb.
        self._validate_forced()
        self._publish_view()
        self._redraw()

    def _publish(self) -> None:
        """Write the field's contents back to the variable, if there is one."""
        variable = self._options["textvariable"]
        if variable is None:
            return
        self._syncing = True
        try:
            variable.set(self._field.text)
        finally:
            self._syncing = False

    # ------------------------------------------------------------ public API

    def get(self) -> str:
        """The text in the field."""
        return self._field.text

    def insert(self, index: Any, string: str) -> None:
        """Insert ``string`` at ``index``, if the state and validator allow it.

        A programmatic edit is validated exactly as a keystroke is, and ignored
        outright when the entry is ``disabled`` or ``readonly``. Both were
        measured on real Tk, and this method did neither: a digits-only entry
        sent ``insert(0, "x")`` ended up holding ``"x"``, with no callback to
        tell the program its own validator had been bypassed. TkCurses-tvj.

        An insert that would change nothing - an empty string - runs no
        callback at all, which is also Tk's behaviour rather than an
        optimisation.
        """
        if not string:
            return
        where = self.index(index)
        text = self._field.text
        self._edit(
            lambda: self._field.insert(where, string),
            text[:where] + string + text[where:],
        )

    def delete(self, first: Any, last: Any = None) -> None:
        """Delete from ``first`` up to but not including ``last``.

        Validated and state-gated like :meth:`insert`. A delete that would
        change nothing - an empty range, or a range starting past the end -
        runs no callback, as measured: ``delete(1, 1)`` and ``delete(5, 9)`` on
        a two-character entry leave the validator untouched.
        """
        start = self.index(first)
        end = start + 1 if last is None else self.index(last)
        text = self._field.text
        if start >= len(text) or end <= start:
            return
        self._edit(lambda: self._field.delete(start, end), text[:start] + text[end:])

    def icursor(self, index: Any) -> None:
        """Put the insertion cursor at ``index``, keeping any selection.

        Measured on Tk 9.0.2: a selection survives ``icursor``. This dropped
        it until TkCurses-elb, which mattered because ttk's own combobox pick
        selects everything and then moves the cursor to the end.
        """
        self._field.place_cursor(self.index(index))
        self._redraw()

    def index(self, index: Any) -> int:
        """Resolve one of Tk's index forms to a number.

        Understands integers, ``end``, ``insert``, ``anchor``, ``sel.first``,
        ``sel.last`` and ``@x`` for a screen column.

        Raises:
            TclError: If the form is not one Tk defines, or names a selection
                that does not exist.
        """
        if isinstance(index, int):
            return self._field.clamp(index)
        text = str(index)
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return self._field.clamp(int(text))
        if text in ("end", END):
            return len(self._field.text)
        if text in ("insert", INSERT):
            return self._field.cursor
        if text.startswith("@"):
            return self._field.index_at(int(text[1:]) - self._text_area().x)
        selection = self._field.selection
        if text in ("sel.first", SEL_FIRST):
            if selection is None:
                raise TclError("selection isn't in widget " + str(self))
            return selection[0]
        if text in ("sel.last", SEL_LAST):
            if selection is None:
                raise TclError("selection isn't in widget " + str(self))
            return selection[1]
        if text in ("anchor", ANCHOR):
            return self._field.cursor
        raise TclError(f'bad entry index "{index}"')

    def _exports_selection(self) -> bool:
        """Whether this widget puts its selection on PRIMARY."""
        return bool(self._options["exportselection"])

    def _claim_primary(self) -> None:
        """Take ownership of PRIMARY, or give it up, as the option says.

        Ownership is claimed when a selection is made rather than held from
        construction: in Tk, creating a second entry does not take PRIMARY from
        the first, and the widget that selected most recently owns it.

        The contents are not copied. The widget registers a handler and
        :meth:`~tkcurses._core.clipboard.Selections.resolve` asks it at the
        moment PRIMARY is read, which is X11's design and what tkinter exposes
        as ``selection_handle``. Three of the four behaviours measured on
        Tcl/Tk 9.0.2 then need no bookkeeping: clearing the selection makes
        PRIMARY stop existing, selecting again makes it exist, and an edit that
        moves the selection needs noticing by nobody.
        """
        selections = self.tk.selections
        if self._exports_selection():
            selections.own(self, PRIMARY, lost=self._lost_primary)
            selections.handle(self, self._primary_selection, PRIMARY)
        elif selections.owner(PRIMARY) is self:
            # Measured: turning -exportselection off drops PRIMARY at once,
            # even though the widget's own selection is untouched.
            selections.disown(self)

    def _lost_primary(self) -> None:
        """Another widget took PRIMARY: drop this one's selection, as Tk does.

        Measured on Tk 9.0.2 - select in one entry, then in another, and the
        first is no longer selected. Without this both stayed highlighted,
        which a person running UAT 43 reported. TkCurses-lw2.
        """
        self._field.select_clear()
        self._redraw()

    def _primary_selection(self, *_args: Any) -> str:
        """The selected text, for whoever is reading PRIMARY.

        Raises:
            TclError: If nothing is selected. A widget owning PRIMARY with an
                empty selection has to read as "doesn't exist" rather than as
                the empty string: tkinter raises, and a caller needs to tell
                "nothing is selected" from "an empty string was selected".
        """
        selection = self._field.selection
        if selection is None:
            raise TclError(f"{PRIMARY} selection doesn't exist or form unknown")
        first, last = selection
        return self._field.text[first:last]

    def selection_range(self, start: Any, end: Any) -> None:
        """Select from ``start`` to ``end``, leaving the anchor where it is.

        A range given backwards or empty clears the selection, as Tk's does.
        See :meth:`TextField.select_range`; TkCurses-bfy.
        """
        self._field.select_range(self.index(start), self.index(end))
        self._claim_primary()
        self._redraw()

    select_range = selection_range

    def selection_clear(self, **kw: Any) -> None:  # noqa: ARG002 - Misc signature
        """Drop the selection; the anchor stays, as Tk's does."""
        self._field.select_clear()
        self._redraw()

    select_clear = selection_clear

    def selection_present(self) -> bool:
        """True if anything is selected."""
        return self._field.selection is not None

    def _has_copyable_selection(self) -> bool:
        return self._field.selection is not None

    select_present = selection_present

    # The three below are Tk's entry selection commands as measured on 9.0.2,
    # which this followed loosely until TkCurses-bfy: selection_from cleared
    # the selection and moved the cursor, selection_to moved the cursor, and
    # selection_adjust was selection_to under another name. None of them
    # moves the cursor in Tk.

    def selection_from(self, index: Any) -> None:
        """Set the anchor for the next :meth:`selection_to`, and only that."""
        self._field.select_from(self.index(index))

    select_from = selection_from

    def selection_to(self, index: Any) -> None:
        """Select from the anchor to ``index``."""
        self._field.select_to(self.index(index))
        self._claim_primary()
        self._redraw()

    select_to = selection_to

    def selection_adjust(self, index: Any) -> None:
        """Move the nearer end of the selection to ``index``.

        See :meth:`TextField.select_adjust` for which end is nearer.
        """
        self._field.select_adjust(self.index(index))
        self._claim_primary()
        self._redraw()

    select_adjust = selection_adjust

    def xview(self, *args: Any) -> Any:
        """Report or move the view, as Tk's entry does.

        With nothing it answers the pair of fractions a scrollbar wants; with
        ``("moveto", fraction)`` or ``("scroll", count, "units"|"pages")`` it is
        a scrollbar driving the entry. An index still works, because that is
        what this used to take.

        It used to return the first visible character as an INT, which meant
        -xscrollcommand could not be honoured and that this widget disagreed
        with its own siblings: Text and Canvas already answer with fractions and
        accept the scrollbar arguments, and so does real tkinter's Entry -
        measured, ``xview()`` on a 10-wide entry holding 43 characters answers
        ``(0.0, 0.023255813953488372)``. TkCurses-ale.

        **Only the view moves.** It used to move the insertion cursor and so
        drop the selection, which Tk's does not do - measured on Tk 9.0.2, an
        entry 5 wide holding ``a``-``z`` with the cursor at 3:

        * ``moveto f`` shows character ``f * length`` first, halves rounded up;
        * ``scroll n units`` moves n characters, ``scroll n pages`` moves
          ``n * max(1, width - 2)`` - 1 at widths 1 to 3, 3 at 5, 6 at 8;
        * an index is shown first;
        * every form stops at ``length - width``, so the last character sits
          at the right edge, and a text shorter than the field never scrolls;
        * the cursor stays at 3 and a selection survives.

        TkCurses-i8s.
        """
        if not args:
            return self._view_fractions()
        width = self._text_area().width
        if args[0] == "moveto":
            # Halves round UP, as Tk's do (2.5 of 26 shows character 3);
            # Python's round() would send them to the even neighbour.
            first = math.floor(float(args[1]) * len(self.get()) + 0.5)
        elif args[0] == "scroll":
            count = int(args[1])
            step = max(1, width - 2) if args[2] == "pages" else 1
            first = self._field.view + count * step
        else:
            first = self.index(args[0])
        self._field.set_view(first, width)
        self._publish_view()
        self._redraw()
        return None

    def _char_bbox(self, index: Any) -> tuple[int, int, int, int]:
        """The cell box of one character, for the subclasses whose Tk has one.

        ``tk.Spinbox`` and the three ttk entries offer ``bbox(index)``; the
        classic ``tk.Entry`` does not - in tkinter its ``bbox`` IS
        ``Misc.bbox``, the grid alias - so this is private here and public
        on each of those. Measured on Tk 9.0.2 (``(x, y, width, height)``,
        relative to the widget):

        * an index past the last character answers the last character's box -
          ``end``, ``len`` and ``99`` all give the same as ``len - 1``;
        * the box is where the character IS, view and all: scrolled off to
          the left its x is negative, off to the right it is past the edge;
        * an empty entry answers a box of width 0 at the start.

        One cell wide and one high, as everything is here. TkCurses-52q.
        """
        area = self._text_area()
        length = len(self._field.text)
        if length == 0:
            return (area.x, area.y, 0, 1)
        position = min(self.index(index), length - 1)
        return (area.x + position - self._field.view, area.y, 1, 1)

    def _view_fractions(self) -> tuple[float, float]:
        """Where the visible run sits in the text, as two fractions."""
        total = len(self.get())
        if total <= 0:
            return (0.0, 1.0)
        width = max(1, self._text_area().width)
        self._field.fit_view(width)
        first = self._field.view
        return (first / total, min(1.0, (first + width) / total))

    def _publish_view(self) -> None:
        """Tell a scrollbar where the view is, if one is listening."""
        command = self._options.get("xscrollcommand")
        if command is not None:
            first, last = self._view_fractions()
            command(first, last)

    # -------------------------------------------------------------- editing

    def _validated(self, proposed: str) -> bool:
        """Ask the ``validatecommand`` whether an edit may go ahead.

        tkinter passes Tcl substitution codes to a registered command; without
        Tcl there is nothing to register against, so the callable is handed
        the proposed contents directly. Anything it raises counts as a
        refusal - a validator that fails should not take the application with
        it.

        Only ``key`` and ``all`` gate an edit. The focus modes validate when
        the focus moves and let every edit through, which was measured rather
        than assumed: a ``validate="focusout"`` entry sent an insert its
        validator refuses keeps the text. This used to test for ``none``
        instead, so the three focus modes vetoed keystrokes that Tk allows.

        A validator that edits the entry, or that raises, turns validation off
        - see :meth:`_turn_validation_off` for why that is Tk's answer rather
        than a shortcut taken here.

        The other two conditions are :meth:`_validate_focus` and
        :meth:`_validate_forced`.
        """
        if self._validating:
            # Noticed under every mode, as Tk notices it: a focus validator
            # that edits the entry fails even though no key validation runs.
            self._edited_while_validating = True
        if str(self._options["validate"]) not in _EDIT_VALIDATED:
            return True
        return self._ask_validator(proposed, can_raise=True)

    def _ask_validator(
        self, proposed: str, *, notify: bool = True, can_raise: bool = False
    ) -> bool:
        """Run the ``validatecommand``, and the ``invalidcommand`` after it.

        The half every validation condition shares. What the answer *means* is
        the condition's business: an edit that is refused is discarded, a focus
        change that is refused still happens, and a ``textvariable`` write
        cannot be refused at all. So this reports the verdict and does not act
        on it.

        Args:
            proposed: The contents being judged - the value the field would
                hold for an edit, the value it holds for every other condition.
            notify: Whether a refusal runs the ``invalidcommand``. The forced
                condition passes False, because - measured - Tk stays silent
                when a variable write fails validation.
            can_raise: Whether there is a caller to hand an error to - an edit
                or ``validate()``, not a focus change. The classic Entry never
                raises; ttk's does, see :meth:`_validator_raised`.

        Returns:
            Whether the validator approved. A validator that raises, or that
            turns validation off by editing the entry, counts as a refusal and
            runs no ``invalidcommand`` whatever ``notify`` says.
        """
        command = self._options["validatecommand"]
        if command is None:
            return True
        if self._validating:
            # An edit from inside a validation callback - _validated has
            # already flagged it. Tk does not recurse: it lets this edit
            # through, which also discards the edit that was being validated -
            # the check below - and the classic Entry turns validation off as
            # well (see _nested_edit).
            self._nested_edit()
            return True
        mode = str(self._options["validate"])
        self._edited_while_validating = False
        self._validating = True
        try:
            try:
                allowed = bool(command(proposed))
            except Exception:
                # tkinter hands Tcl nothing when a Python callback raises, Tcl
                # cannot read that as a boolean, and Tk turns validation off.
                # Measured: the edit is refused and invalidcommand does NOT
                # run, which is why this never reaches _refused.
                self._turn_validation_off()
                self._validator_raised(can_raise=can_raise)
                return False
            if self._edited_while_validating or (
                mode != "none" and str(self._options["validate"]) == "none"
            ):
                # The callback edited the entry, or turned validation off.
                # Whatever it returned, the edit is discarded.
                return False
            if not allowed and notify:
                self._refused(proposed)
            return allowed
        finally:
            self._validating = False

    def _nested_edit(self) -> None:
        """What an edit made from inside a validation callback does to the mode.

        The classic Entry turns validation off - measured, see
        :meth:`_turn_validation_off`. ttk's does not, and overrides this.
        TkCurses-4ag.
        """
        self._turn_validation_off()

    def _validator_raised(self, *, can_raise: bool) -> None:
        """After a validator raised and validation was turned off.

        The classic Entry says nothing: the edit is refused and that is all.
        ttk's raises ``TclError`` to whoever made the edit, and overrides
        this. TkCurses-4ag.
        """

    def _validate_focus(self, condition: str) -> bool | None:
        """Validate because the focus arrived or left, if the mode asks for it.

        Tk's second validation condition, and nothing here acted on it: the
        focus modes were accepted as values of ``validate`` and never did
        anything. Measured on Tcl/Tk 9.0.2, with the mode on the left and the
        condition that fires across the top:

        =========== ========= =========
        mode        focusin   focusout
        =========== ========= =========
        focus       yes       yes
        focusin     yes       -
        focusout    -         yes
        all         yes       yes
        key, none   -         -
        =========== ========= =========

        Unlike an edit, this gates nothing - there is no proposed value to
        refuse, only the value already there. A refusal runs the
        ``invalidcommand`` and leaves the text alone. TkCurses-jd1.
        """
        wanted = _FOCUS_IN_VALIDATED if condition == "focusin" else _FOCUS_OUT_VALIDATED
        if str(self._options["validate"]) not in wanted:
            return None
        return self._ask_validator(self._field.text)

    def _validate_forced(self) -> None:
        """Revalidate after the ``textvariable`` was written behind our back.

        Tk calls this condition ``forced``, and it is the one that cannot say
        no: the variable already holds the value, so there is nothing to
        refuse. Measured on Tcl/Tk 9.0.2 - the value is kept, the
        ``invalidcommand`` does *not* run, and Tk resolves the contradiction by
        turning validation off. It fires under every mode but ``none``,
        including the focus modes, which is why this does not consult
        :data:`_EDIT_VALIDATED`. TkCurses-3xb.

        One deliberate divergence, the single disagreement left in a 31-case
        differential probe: a validator that *edits* the entry while being
        asked about a variable write. Tk abandons the whole update, discards
        the validator's edit too, and leaves the widget holding the old text
        while the variable holds the new - a widget out of step with its own
        textvariable. Here the write and the edit both land. Both agree on the
        part that matters, which is that validation is turned off.
        TkCurses-doh.
        """
        if str(self._options["validate"]) == "none":
            return
        if not self._ask_validator(self._field.text, notify=False):
            self._turn_validation_off()

    def _turn_validation_off(self) -> None:
        """Set ``validate`` to ``none``, as Tk does when a callback misbehaves.

        Tk's own recursion guard, and the reason this library needs one: once
        programmatic edits are validated, a validator that calls ``insert`` on
        the entry it is validating would call itself forever. Tk cuts the loop
        by disabling validation outright, and leaves it disabled - the
        application has to put it back. Measured on real Tk, for a validator
        that inserts into its own entry: the nested edit lands, the edit being
        validated does not, and ``cget("validate")`` reads ``none`` afterwards.

        Written straight to the option dict rather than through
        :meth:`configure`, because this runs from inside a callback that
        ``configure`` may itself have started.
        """
        self._options["validate"] = "none"

    def _border_style(self) -> BorderStyle:
        """The box this entry draws, brightened while it has the focus.

        Tk shows the focus on an entry two ways, and only one of them is the
        insertion cursor. The other is the focus highlight ring, which is drawn
        whatever the state - and the ring is what tells you a *readonly* entry
        has the keyboard, because Tk's manual is explicit that readonly draws
        "no insertion cursor ... even if the input focus is in the widget".

        This library draws no ring, having no cell for it, and until now put
        nothing in its place. So a focused
        readonly entry was indistinguishable from an unfocused one: Tk's cursor
        rule was copied faithfully and Tk's other half of the signal was not.
        Reported from UAT 41 - "though readonly is not modifiable, it should
        still reflect its focus status".

        The border is the cell equivalent: a focused entry draws its box bold
        and an unfocused one does not. ``BorderStyle.attr`` exists for exactly
        this, "used where line style alone is not enough to tell two reliefs
        apart", and ``relief="flat"`` still draws nothing. ``highlightthickness``
        is accepted and does not turn it off (TkCurses-gm66.1): programs set it
        to 0 to hide X11's ring, not to hide the keyboard.

        A_DIM is dropped rather than combined: the default relief for an entry
        is ``sunken``, whose border is dim, and dim-and-bold on one cell is
        whatever the terminal decides.
        """
        style = super()._border_style()
        if self.focus_get() is not self:
            return style
        return replace(style, attr=(style.attr & ~_curses.A_DIM) | _curses.A_BOLD)

    def _refused(self, proposed: str = "") -> None:
        """Run the ``invalidcommand``, which is what Tk does on a refusal.

        The third of Tk's validation trio, and it was missing: a program could
        say what counted as valid and not what to do when an edit did not. As
        with validatecommand, anything it raises is swallowed - a handler for a
        rejected keystroke should not take the application down with it, and
        measured, an invalidcommand that raises does *not* turn validation off
        the way a raising validator does.

        The handler is given the refused text if it will take it, and called
        with nothing if it will not. Tk's invalidcommand is a registered
        command that may ask for any substitution or none, so both arities are
        legitimate there; here, ``invalidcommand=lambda: ...`` was the only
        form that worked, which left a handler no way to see what it was
        rejecting except by reading back the text that had been *kept*.
        TkCurses-1d1.
        """
        command = self._options.get("invalidcommand")
        if command is None:
            return
        with contextlib.suppress(Exception):
            if _takes_an_argument(command):
                command(proposed)
            else:
                command()

    def _edit(self, change: Callable[[], None], proposed: str) -> None:
        """Apply an edit if the state and the validator both allow it."""
        if not self._editable or not self._validated(proposed):
            return
        change()
        self._changed()

    def _set_value(self, value: Any) -> None:
        """Replace the whole text the way ttk's ``set`` does: unconditionally.

        Tk's ``EntrySetValue``, which ``ttk::combobox set`` and
        ``ttk::spinbox set`` both are. Measured against Tk 9.0.2, it is
        nothing like :meth:`delete` followed by :meth:`insert`:

        * **No validation.** A validatecommand that refuses everything is not
          even called, under ``validate="all"`` or ``"key"``, and the value
          lands anyway.
        * **No state gate.** ``readonly`` and ``disabled`` both take the value.
        * **The cursor and selection stay**, clamped to the new text - see
          :attr:`TextField.text`.

        The textvariable is written, as for any change.
        """
        self._field.text = str(value)
        self._changed()

    def _changed(self) -> None:
        """Publish and repaint after the contents changed.

        Not rescroll: an edit made by the program leaves the view where it
        was, as Tk's does. The bindings scroll, through :meth:`_see_cursor`.
        """
        self._publish()
        self._publish_view()
        self._redraw()

    def _see_cursor(self) -> None:
        """Scroll so the cursor is on screen, and say where the view ended up.

        Tk's ``see insert``: for keystrokes and clicks, not for the program's
        own calls. TkCurses-i8s.
        """
        self._field.scroll_into_view(self._text_area().width)
        self._publish_view()

    # ------------------------------------------------------------- painting

    def _text_area(self) -> Rect:
        """Where the text goes, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _showing_placeholder(self) -> bool:
        """Whether the ghost text is what the field is displaying.

        Empty contents and a placeholder to show, and nothing else: measured on
        screen, Tk draws it **whatever the focus and whatever the state**. A
        focused field keeps it, with the insertion cursor before its first
        character; a ``disabled`` or ``readonly`` field keeps it too, which is
        the opposite of how the insertion cursor behaves. TkCurses-xe9.3.
        """
        return not self._field.text and bool(str(self._options["placeholder"]))

    def _displayed(self) -> str:
        """What is on screen: the contents masked by ``show``, or the placeholder.

        **The placeholder is not masked.** Measured, and the one thing here that
        would have been got wrong: a field with ``show="*"`` and a placeholder
        shows the placeholder as plain text, not as asterisks. ``show`` hides
        *contents* - there are none to hide - so the placeholder short-circuits
        it rather than passing through it.
        """
        if self._showing_placeholder():
            return str(self._options["placeholder"])
        mask = str(self._options["show"])
        text = self._field.text
        return mask[0] * len(text) if mask else text

    def _placeholder_attribute(self, attribute: int) -> int:
        """How the ghost text is drawn, as distinct from real contents.

        ``placeholderforeground`` is honoured when it is set. When it is not -
        which is the default - the text is drawn **dim**, and that is a
        deliberate divergence rather than an oversight. Tk's default leaves the
        placeholder in the ordinary foreground colour, which a GUI gets away
        with because the ghost text is a different shade of grey anyway; in a
        terminal it would be indistinguishable from real content, so a field
        that reads as full while ``get()`` answers ``""`` would actively
        mislead. Dim is the terminal's own idiom for "this is not your text".
        """
        colour = str(self._options["placeholderforeground"])
        colors = self.tk.colors
        if colour and colors is not None:
            return (
                colors.attribute_for(
                    colour, str(self._options["background"] or "black")
                )
                | _curses.A_DIM
            )
        return attribute | _curses.A_DIM

    def _redraw(self) -> None:
        """Paint the field, its selection, and the cursor."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = self._text_area()
        # Only pulled back if the text has shrunk away from the right edge; it
        # does not follow the cursor here, or every redraw would undo an
        # xview (TkCurses-i8s). Before layout the width is 0 and this is a
        # no-op, so text inserted early is not scrolled against no width.
        self._field.fit_view(area.width)
        dispatcher = CursesDispatcher.get()
        attribute = self._in_state(
            self._background_attribute() | self._font_attribute()
        )
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if area.is_empty:
                return
            view = self._field.view
            text = self._displayed()[view : view + area.width]
            self._write_line(
                dispatcher,
                window,
                area.y,
                area.x,
                text,
                self._placeholder_attribute(attribute)
                if self._showing_placeholder()
                else attribute,
            )
            self._draw_selection(dispatcher, window, area, attribute)
            self._draw_cursor(dispatcher, window, area, attribute)

    def _draw_selection(
        self, dispatcher: CursesDispatcher, window: Any, area: Rect, attribute: int
    ) -> None:
        """Show the selected range in the select colours, else reversed."""
        selection = self._field.selection
        if selection is None:
            return
        first, last = selection
        start = max(0, self._field.column_of(first))
        stop = min(area.width, self._field.column_of(last))
        if stop <= start:
            return
        text = self._displayed()[self._field.view + start : self._field.view + stop]
        with contextlib.suppress(_curses.error):
            self._write_line(
                dispatcher,
                window,
                area.y,
                area.x + start,
                text,
                self._selection_attribute(attribute),
            )

    def _draw_cursor(
        self, dispatcher: CursesDispatcher, window: Any, area: Rect, attribute: int
    ) -> None:
        """Note where typing will go, while the field has the focus.

        **Noted, not painted.** This painted the insertion point as a reversed
        cell, which is also how a selection is drawn, and a person could not
        tell the cursor from the selected text beside it (UAT 43,
        TkCurses-lw2). The terminal's own cursor is put there instead - see
        :class:`~tkcurses._core.screen.TerminalCursor` - which blinks and has
        the shape the person's terminal is set to.

        Not in an unfocused field, which would claim the keyboard is there
        when it is not; not in a readonly one, which Tk's manual says draws
        no insertion cursor; not when the cursor is scrolled out of view.
        """
        del dispatcher, window, attribute
        self._insert_at = None
        if self.focus_get() is not self or not self._editable:
            return
        column = self._field.column_of(self._field.cursor)
        if not (0 <= column < area.width):
            return
        self._insert_at = (
            self.winfo_rooty() + area.y,
            self.winfo_rootx() + area.x + column,
        )

    def _insert_cell(self) -> tuple[int, int] | None:
        return self._insert_at


#: Keys that move the cursor, as offsets or as absolute positions.
def _takes_an_argument(command: Callable[..., Any]) -> bool:
    """Whether a callback will accept one positional argument.

    Tk's validation callbacks are registered commands that may ask for any
    substitution or for none, so a handler written against Tk may legitimately
    take the refused text or take nothing. Both have to work here.

    A callable whose signature cannot be read - some builtins - is assumed to
    take nothing, which is the arity that worked before this existed.
    """
    try:
        signature = inspect.signature(command)
    except (TypeError, ValueError):
        return False
    try:
        signature.bind("")
    except TypeError:
        return False
    return True


#: Validation modes under which an edit is checked before it is applied.
#: Measured on real Tk: "focus", "focusin" and "focusout" validate when the
#: focus moves and let every edit through, so they are deliberately absent.
_EDIT_VALIDATED = ("key", "all")

#: Modes that validate when the focus arrives, and when it leaves. "focus"
#: means both. Measured; see Entry._validate_focus for the table.
_FOCUS_IN_VALIDATED = ("focus", "focusin", "all")
_FOCUS_OUT_VALIDATED = ("focus", "focusout", "all")

_ENTRY_MOTION: dict[str, Any] = {
    "Left": -1,
    "Right": 1,
    "Home": "start",
    "End": "end",
}


def _entry_key(event: Event) -> str | None:
    """Handle one key in an Entry, then bring the cursor into view.

    Returns ``"break"`` for keys the field consumed, so a Left arrow moving
    the cursor does not also reach whatever else is bound to it. Scrolling to
    the cursor belongs here and not in the edits themselves: Tk's bindings
    do it, its ``insert`` and ``icursor`` do not. TkCurses-i8s.
    """
    result = _entry_keystroke(event)
    if result == "break":
        event.widget._see_cursor()
        event.widget._redraw()
    return result


def _entry_keystroke(event: Event) -> str | None:
    """Apply one key to an Entry's field."""
    entry = event.widget
    field = entry._field
    keysym = event.keysym
    extend = bool(event.state & MOD_SHIFT)

    if keysym in _ENTRY_MOTION:
        motion = _ENTRY_MOTION[keysym]
        if motion == "start":
            field.move_to(0, extend=extend)
        elif motion == "end":
            field.move_to(len(field.text), extend=extend)
        else:
            field.move_by(motion, extend=extend)
        if extend:
            entry._claim_primary()
        return "break"

    if keysym == "BackSpace":
        if not field.delete_selection() and field.cursor > 0:
            entry._edit(
                lambda: field.delete(field.cursor - 1, field.cursor),
                field.text[: field.cursor - 1] + field.text[field.cursor :],
            )
        else:
            entry._changed()
        return "break"

    if keysym == "Delete" and not event.state & MOD_SHIFT:
        # Shift-Delete is <<Cut>>, and Tk lets the virtual event have it:
        # measured, it cuts the selection and deletes nothing else.
        if not field.delete_selection():
            entry._edit(
                lambda: field.delete(field.cursor, field.cursor + 1),
                field.text[: field.cursor] + field.text[field.cursor + 1 :],
            )
        else:
            entry._changed()
        return "break"

    if event.char and event.char.isprintable():
        selection = field.selection
        start = selection[0] if selection else field.cursor
        remainder = (
            field.text[: selection[0]] + field.text[selection[1] :]
            if selection
            else field.text
        )
        proposed = remainder[:start] + event.char + remainder[start:]

        def apply() -> None:
            field.delete_selection()
            field.insert(field.cursor, event.char)

        entry._edit(apply, proposed)
        return "break"
    return None


def _entry_click(event: Event) -> None:
    """Take the focus and put the cursor where the click landed."""
    entry = event.widget
    if str(entry._options["state"]) == "disabled":
        return
    entry.focus_set()
    index = _entry_index_at(entry, event.x)
    entry._field.move_to(index)
    # Tk's tk::EntryButton1 anchors there too: a click, then selection_to,
    # selects from the click (measured). TkCurses-bfy.
    entry._field.select_from(index)
    _entry_start_drag(entry, "char")
    entry._see_cursor()
    entry._redraw()


# ------------------------------------------- selecting with the mouse, Entry
#
# Tk's own Entry bindings, READ from the running interpreter - bind_class
# Entry and TEntry, and the bodies of tk::EntryMouseSelect,
# tk::EntryAutoScan, ttk::entry::Select, WordSelect, CharSelect, ExtendTo
# and AutoScroll - and the selections MEASURED on Tk 9.0.2 by calling those
# procedures at each character (TkCurses-svtr):
#
# * a double-click selects the run around the pointer, word or not (see
#   tkcurses._core.editing.run_start), and a drag after it extends a word at
#   a time; a triple-click selects everything, and a drag after it keeps it;
#   the cursor goes to the end of what was selected.
# * Shift-click: classic Tk adjusts the selection - the nearer end moves, the
#   cursor stays; ttk extends from the far end and moves the cursor there.
# * a drag past either edge scrolls two characters every 50ms, selecting as
#   it goes, until the pointer comes back or the button is let go. A
#   terminal reports the pointer only inside itself, so an entry against the
#   terminal's edge cannot be dragged past that edge.
#
# Two families, because ttk's procedures are not classic Tk's: ttk's word
# drag measures from the anchor where classic measures from the character
# before it, and ttk binds no Double-Shift or Triple-Shift at all. Classic
# Spinbox has its own copy of the selection code with one difference, a
# double-click on the first character of a word selecting nothing - a Tk
# defect, measured, and not copied: it uses Entry's rule here.


#: The modifiers whose click extends a selection. Shift is Tk's. Alt is ours,
#: and a deliberate departure: VTE terminals - GNOME Terminal, Ptyxis and the
#: rest - keep every Shift-click for their own text selection and never send
#: it, even to a program that has asked for the mouse. Measured with a raw
#: probe in the author's terminal: plain, Ctrl- and Alt-clicks all arrived,
#: and not one Shift-click. Tk binds nothing to Alt-click, so nothing is lost;
#: Ctrl-click was the other candidate, and is Tk's "move the cursor and leave
#: the selection". TkCurses-svtr.
_EXTEND_MODIFIERS = ("Shift", "Alt")


def _is_ttk(widget: Any) -> bool:
    """True for a ttk widget, whose bindings are ttk's own procedures."""
    return getattr(widget, "_ttk_class", None) is not None


def _entry_index_at(entry: Any, x: int) -> int:
    """The gap a pointer at widget column ``x`` stands for.

    A terminal cell is a whole character, so the pointer on a character means
    the gap before it - Tk's ClosestGap with the pointer in the left half.

    Held to the visible columns, as Tk's ``@x`` is: a pointer dragged past
    the edge means the edge. Without that it named a character off screen,
    and keeping the cursor in view then jumped the field by the whole
    overshoot instead of the autoscroll's two characters.
    """
    area = entry._text_area()
    column = min(max(x - area.x, 0), max(area.width - 1, 0))
    return int(entry._field.index_at(column))


def _entry_start_drag(entry: Any, mode: str) -> None:
    """Begin a press: what a drag extends by, and nothing moved yet."""
    _cancel_autoscan(entry)
    entry._select_mode = mode
    entry._moved = False
    entry._dragging = True


def _entry_select_to(entry: Any, x: int) -> None:
    """Select from the anchor to the pointer by the current mode.

    Classic Tk's ``tk::EntryMouseSelect`` or ttk's ``ttk::entry::DragTo``,
    by the widget's family. The anchor is the field's own, which a press or a
    shift-click set.
    """
    field = entry._field
    text = field.text  # the real text, as Tk's [$w get]: not what show= shows
    cur = _entry_index_at(entry, x)
    anchor = field._anchor
    if cur != anchor:
        entry._moved = True
    mode = entry._select_mode
    if _is_ttk(entry):
        if mode == "char":
            entry.selection_range(min(cur, anchor), max(cur, anchor))
            entry.icursor(cur)
        elif mode == "word":
            if cur < anchor:
                entry.selection_range(run_start(text, cur), run_end(text, anchor))
                entry.icursor(run_start(text, cur))
            else:
                last = run_end(text, cur)
                entry.selection_range(run_start(text, anchor), last)
                entry.icursor(last)
        elif mode == "line":
            entry.selection_range(0, "end")
            entry.icursor("end")
        entry._see_cursor()
        entry._redraw()
        return
    if mode == "char":
        if entry._moved:
            if cur == anchor:
                entry.selection_clear()
            else:
                entry.selection_range(min(cur, anchor), max(cur, anchor))
    elif mode == "word":
        if cur < anchor:
            first, last = run_start(text, cur), run_end(text, anchor - 1)
        elif cur > anchor:
            first, last = run_start(text, anchor), run_end(text, cur - 1)
        else:
            first, last = run_start(text, anchor), run_end(text, anchor)
        entry.selection_range(first, last)
    elif mode == "line":
        entry.selection_range(0, "end")
    if entry._moved:
        entry.icursor(cur)
    entry._see_cursor()
    entry._redraw()


def _entry_selects(entry: Any) -> bool:
    """Whether a mouse selection gesture applies: not to a disabled entry."""
    return str(entry._options["state"]) != "disabled"


def _entry_double(event: Event) -> None:
    """Select the word under the pointer; a drag then extends by words."""
    entry = event.widget
    if not _entry_selects(entry):
        return
    if _is_ttk(entry):
        # ttk::entry::Select: the anchor moves to the pointer first.
        entry._field.select_from(_entry_index_at(entry, event.x))
    _entry_start_drag(entry, "word")
    _entry_select_to(entry, event.x)
    if not _is_ttk(entry) and entry._field.selection is not None:
        entry.icursor(entry._field.selection[1])
    entry._see_cursor()
    entry._redraw()


def _entry_triple(event: Event) -> None:
    """Select everything; a drag then keeps it so."""
    entry = event.widget
    if not _entry_selects(entry):
        return
    if _is_ttk(entry):
        entry._field.select_from(_entry_index_at(entry, event.x))
    _entry_start_drag(entry, "line")
    _entry_select_to(entry, event.x)
    entry.icursor("end")
    entry._see_cursor()
    entry._redraw()


def _entry_shift_click(event: Event) -> None:
    """Extend the selection to the pointer.

    Classic: ``selection adjust`` - the nearer end moves and the cursor does
    not. ttk: ``ttk::entry::ExtendTo`` - from the far end, or from the cursor
    with nothing selected, and the cursor goes to the pointer.
    """
    entry = event.widget
    if not _entry_selects(entry):
        return
    index = _entry_index_at(entry, event.x)
    _entry_start_drag(entry, "char")
    if not _is_ttk(entry):
        entry.selection_adjust(index)
        return
    field = entry._field
    selection = field.selection
    insert = field.cursor
    if selection is None:
        anchor = insert
    else:
        first, last = selection
        anchor = last if index < first or (insert == first and index <= last) else first
    entry.focus_set()
    field.select_from(anchor)
    entry.selection_range(min(anchor, index), max(anchor, index))
    entry.icursor(index)
    entry._see_cursor()
    entry._redraw()


def _entry_control_click(event: Event) -> None:
    """Move the cursor to the pointer and leave everything else alone.

    Tk's classic Entry and Spinbox bind ``<Control-Button-1>`` to ``%W
    icursor @%x`` and nothing more: the selection stays, its anchor stays,
    and the focus does not move. No drag follows - a Ctrl-drag in Tk selects
    from whatever anchor the LAST plain press left, through state its
    bindings share, which is not copied. TkCurses-mndh.
    """
    entry = event.widget
    _cancel_autoscan(entry)
    entry._dragging = False
    entry.icursor(_entry_index_at(entry, event.x))
    entry._see_cursor()
    entry._redraw()


def _entry_double_shift(event: Event) -> None:
    """Extend the selection from the anchor by whole words (classic only)."""
    entry = event.widget
    if _entry_selects(entry):
        _entry_start_drag(entry, "word")
        _entry_select_to(entry, event.x)


def _entry_triple_shift(event: Event) -> None:
    """Select everything, extending (classic only)."""
    entry = event.widget
    if _entry_selects(entry):
        _entry_start_drag(entry, "line")
        _entry_select_to(entry, event.x)


def _cancel_autoscan(widget: Any) -> None:
    """Stop scrolling a drag along, if it was."""
    pending = getattr(widget, "_autoscan", None)
    if pending is not None:
        widget.after_cancel(pending)
        widget._autoscan = None


def _entry_autoscan(entry: Any) -> None:
    """Scroll two characters towards the pointer and select to it, again.

    Tk's ``tk::EntryAutoScan``: every 50ms while the button is held with the
    pointer past either side of the widget. Motion reports stop when the hand
    does, so without the repeat a drag past the edge would scroll once.
    """
    entry._autoscan = None
    if not entry._dragging or not entry.winfo_exists():
        return
    x = entry._drag_x
    if x >= entry.winfo_width():
        entry.xview("scroll", 2, "units")
    elif x < 0:
        entry.xview("scroll", -2, "units")
    else:
        return
    _entry_select_to(entry, x)
    entry._autoscan = entry.after(50, lambda: _entry_autoscan(entry))


# ------------------------------------------------- the clipboard, on an Entry
#
# Tk's own Entry bindings for the clipboard virtual events, MEASURED on Tk
# 9.0.2 with "hello world" and 0-5 selected (TkCurses-lw2):
#
# * <<Copy>> puts the selection on the clipboard - what is SHOWN, so a
#   show="*" entry copies "*****" - and with nothing selected does nothing.
# * <<Cut>> is copy, then delete. A readonly or disabled entry still copies
#   and refuses the delete.
# * <<Paste>> replaces the selection with the clipboard - a deliberate
#   departure from classic Tk on Linux, which keeps it (see _entry_paste).
#   An empty clipboard pastes nothing.
# * <<Clear>> deletes the selection; <<SelectAll>> selects everything and
#   leaves the cursor; <<PasteSelection>> (middle button) inserts PRIMARY
#   where the click landed.
#
# All of them edit through insert() and delete(), so a validator and the
# state have their say exactly as for any other edit.


def _entry_selected(entry: Any) -> str | None:
    """The selected text as it is shown, or None with nothing selected."""
    selection = entry._field.selection
    if selection is None:
        return None
    first, last = selection
    return str(entry._displayed()[first:last])


def _entry_copy(event: Event) -> None:
    """Put the selection on the clipboard."""
    text = _entry_selected(event.widget)
    if text is not None:
        event.widget.clipboard_clear()
        event.widget.clipboard_append(text)


def _entry_cut(event: Event) -> None:
    """Copy the selection, then delete it if the entry allows."""
    entry = event.widget
    text = _entry_selected(entry)
    if text is None:
        return
    entry.clipboard_clear()
    entry.clipboard_append(text)
    first, last = entry._field.selection
    entry.delete(first, last)
    entry._see_cursor()
    entry._redraw()


def _entry_paste(event: Event) -> None:
    """Insert the clipboard at the cursor, replacing any selection.

    A deliberate departure from classic Tk on Linux, which inserts and keeps
    the selection (X11's rule). Replacing is what ttk does on every platform,
    and classic Tk on Windows and macOS - ttk's PendingDelete: the cursor
    goes to the start of the selection, which is deleted, then the clipboard
    is inserted. A read-only entry refuses both. TkCurses-lw2.
    """
    entry = event.widget
    try:
        text = entry.clipboard_get()
    except TclError:
        return
    selection = entry._field.selection
    if selection is not None and entry._editable:
        entry.icursor(selection[0])
        entry.delete(selection[0], selection[1])
    entry.insert("insert", text)
    entry._see_cursor()
    entry._redraw()


def _entry_clear(event: Event) -> None:
    """Delete the selection."""
    selection = event.widget._field.selection
    if selection is not None:
        event.widget.delete(*selection)


def _entry_select_all(event: Event) -> None:
    """Select everything; the cursor stays where it was."""
    event.widget.selection_range(0, "end")


def _entry_paste_selection(event: Event) -> None:
    """Insert PRIMARY where the middle button was released."""
    entry = event.widget
    if not entry._editable:
        return
    entry.icursor(entry._field.index_at(event.x - entry._text_area().x))
    try:
        text = entry.selection_get()
    except TclError:
        return
    entry.insert("insert", text)
    entry.focus_set()
    entry._see_cursor()
    entry._redraw()


def _bind_entry_clipboard(bind: Callable[..., Any], name: str) -> None:
    """Install the clipboard bindings under one entry class's name.

    Entry, Spinbox and ttk.Combobox each install Entry's keys under their own
    class name - binding tags name one class, not a chain - so each calls
    this.
    """
    bind(name, "<<Copy>>", _entry_copy)
    bind(name, "<<Cut>>", _entry_cut)
    bind(name, "<<Paste>>", _entry_paste)
    bind(name, "<<Clear>>", _entry_clear)
    bind(name, "<<SelectAll>>", _entry_select_all)
    bind(name, "<<PasteSelection>>", _entry_paste_selection)


def _entry_drag(event: Event) -> None:
    """Select from the press to the pointer while the button is held.

    Tk's own ``<B1-Motion>`` binding, read from the running interpreter
    (``tk::EntryMouseSelect``, character mode): the selection runs from the
    anchor the press set to the gap under the pointer, either way round, and
    is cleared where the two meet; the cursor follows the pointer. Entry had
    no drag at all until a person running UAT 43 tried one - TkCurses-lw2.

    A drag arrives as ``<Motion>``, as Text's does: curses reports motion
    with a button held and there is no Button1 modifier to match against,
    and the implicit grab keeps it with the widget that was pressed.
    """
    entry = event.widget
    if not entry._dragging:
        return
    entry._drag_x = event.x
    _entry_select_to(entry, event.x)
    # Past either side, Tk's <B1-Leave> starts the repeat; back inside, its
    # <B1-Enter> stops it. TkCurses-svtr.
    if event.x < 0 or event.x >= entry.winfo_width():
        if entry._autoscan is None:
            entry._autoscan = entry.after(50, lambda: _entry_autoscan(entry))
    else:
        _cancel_autoscan(entry)


def _entry_release(event: Event) -> None:
    """Stop dragging, wherever the pointer ended up."""
    event.widget._dragging = False
    _cancel_autoscan(event.widget)


def _entry_focus_in(event: Event) -> None:
    """Validate if the mode asks for it, then repaint so the cursor appears."""
    event.widget._validate_focus("focusin")
    event.widget._redraw()


def _entry_focus_out(event: Event) -> None:
    """Validate if the mode asks for it, then repaint so the cursor goes.

    Validation first: a focus validator is allowed to edit the entry - measured
    - and painting before it ran would show the text it was about to change.
    """
    event.widget._validate_focus("focusout")
    event.widget._redraw()


class Menubutton(_TextWidget):
    """A button that posts a menu instead of running a command.

    Everything a Label is, plus a ``menu`` and the gestures that open it: a
    click, Return, the space bar, or Down. It is what sits in a toolbar where
    a menubar would be too much, and what :class:`OptionMenu` is built from.

    ``direction`` says which side of the button the menu appears on. The menu
    itself decides whether there is room - a menubutton near the bottom of the
    terminal posts upwards whatever it was asked for, because a menu that
    runs off the screen cannot be read.
    """

    #: Drawn at the right when ``indicatoron`` is true, so a menubutton can
    #: be told from an ordinary button without opening it.
    _INDICATOR = "▾"

    _widget_options: ClassVar[dict[str, Any]] = {
        **_STATE_COLOUR_OPTIONS,
        "direction": "below",
        "indicatoron": False,
        "menu": None,
        "relief": "raised",
        "takefocus": True,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``menu``, ``direction``, ``indicatoron``, plus everything a
                Label takes.
        """
        super().__init__(master, cnf, name=name, **kw)
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the gestures that post a menubutton's menu.

        Under this widget's own class name, not the literal "Menubutton":
        binding tags name one class rather than a chain of them, so an
        OptionMenu - which is a Menubutton - would otherwise match none of
        these and never open. The same trap Spinbox meets with Entry.
        """
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Button-1>", _menubutton_post)
        bind(name, "<Key-Return>", _menubutton_key)
        bind(name, "<Key-space>", _menubutton_key)
        bind(name, "<Key-Down>", _menubutton_key)
        bind(name, "<FocusIn>", _button_refresh)
        bind(name, "<FocusOut>", _button_refresh)

    @property
    def _indicator_on(self) -> bool:
        """True while the little arrow is drawn."""
        try:
            return self.getboolean(self._options["indicatoron"])
        except TclError:
            return False

    def post_menu(self) -> None:
        """Open the menu where ``direction`` says, if there is one."""
        menu = self._options["menu"]
        if menu is None or self._disabled:
            return
        left, top = self.winfo_rootx(), self.winfo_rooty()
        width, height = self._rect.width, self._rect.height
        direction = str(self._options["direction"])
        if direction == "above" or direction == "left":
            where = (left, top)
        elif direction == "right":
            where = (left + width, top)
        elif direction == "flush":
            where = (left, top)
        else:
            where = (left, top + height)
        menu.post(*where)

    # -------------------------------------------------------------- painting

    def _apply_requested_size(self) -> None:
        """Ask for the text's room, plus the indicator if it is showing."""
        super()._apply_requested_size()
        if self._indicator_on:
            self._request_size(self._requested.width + 2, self._requested.height)

    def _text_area(self) -> Rect:
        """Where the text goes, less the indicator's cells."""
        area = super()._text_area()
        if not self._indicator_on:
            return area
        return Rect(area.x, area.y, max(0, area.width - 2), area.height)

    def _redraw(self) -> None:
        """Paint the button, then its indicator and focus marker."""
        super()._redraw()
        self._draw_indicator()

    def _draw_indicator(self) -> None:
        """Draw the arrow at the right, and underline the text when focused.

        Focus is shown by underlining rather than by a marker, because a
        menubutton is usually one of several in a row and markers either side
        would make the row twice as wide.
        """
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = super()._text_area()
        if area.is_empty:
            return
        attribute = self._background_attribute() | self._text_attribute()
        if self.focus_get() is self:
            attribute |= _curses.A_UNDERLINE
        dispatcher = CursesDispatcher.get()
        cell = self._indicator_cell()
        if cell is not None:
            with contextlib.suppress(_curses.error):
                self._write_line(
                    dispatcher, window, cell[1], cell[0], self._INDICATOR, attribute
                )

    def _indicator_cell(self) -> tuple[int, int] | None:
        """The arrow's cell, as ``(column, row)``, if one is drawn.

        Shared by the painting and by ttk's ``identify``, which names it
        ``Menubutton.indicator``.
        """
        area = super()._text_area()
        if area.is_empty or not self._indicator_on or area.width < 2:
            return None
        return (area.x + area.width - 1, area.y + (area.height - 1) // 2)


def _menubutton_post(event: Event) -> None:
    """Open the menu, leaving the focus where it was, as Tk does."""
    event.widget.post_menu()


def _menubutton_key(event: Event) -> str:
    """Open the menu from the keyboard, and keep the key to ourselves."""
    event.widget.post_menu()
    return "break"


class OptionMenu(Menubutton):
    """A menubutton showing the current value of a variable.

    The menu is built for you: one radiobutton entry per value, all sharing
    the variable, so choosing one both sets the variable and changes what the
    button says. That is the whole widget - tkinter's is a Menubutton with a
    constructor that does this, and so is this one.

    The menu is reachable as ``widget["menu"]``, which is how tkinter code
    adds to it or replaces it after the fact.
    """

    def __init__(
        self,
        master: Misc | None,
        variable: Variable,
        value: Any = None,
        *values: Any,
        command: Callable[[Any], Any] | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget.
            variable: The variable the choice is written to, and the one the
                button's text follows.
            value: The value to start on. Included in the menu.
            *values: The rest of the choices.
            command: Called with the chosen value, after the variable is set.
            **kw: Anything else a Menubutton takes.

        Raises:
            TclError: If no values were given at all.
        """
        choices = [] if value is None else [value, *values]
        if not choices:
            raise TclError("OptionMenu needs at least one value")
        kw.setdefault("indicatoron", True)
        kw.setdefault("textvariable", variable)
        super().__init__(master, **kw)
        self._variable = variable
        self._command = command
        self._options["menu"] = Menu(self, name="menu")
        self.set_menu(*choices)

    def set_menu(self, *values: Any, current: Any = None) -> None:
        """Replace the choices, as ttk's OptionMenu does.

        ``current`` is the only way the variable is written from here.
        Building the menu does not touch it, which is what tkinter does: an
        OptionMenu over an empty variable shows nothing until something is
        chosen, and one over a variable that already holds a value leaves it
        alone. Checked against Tk 9.0.2.
        """
        menu = self._options["menu"]
        menu.delete(0, "end")
        for choice in values:
            # Command entries, as tkinter builds them - not radiobuttons.
            # A tick beside the current choice would read better in a
            # terminal, but code that asks the menu what type its entries
            # are would get a different answer than it does under Tk.
            menu.add_command(
                label=str(choice),
                command=lambda chosen=choice: self._chose(chosen),
            )
        if current is not None:
            self._variable.set(current)

    def _chose(self, value: Any) -> None:
        """Set the variable, then run the command with what was chosen."""
        self._variable.set(value)
        if self._command is not None:
            self._command(value)

    def __getitem__(self, key: str) -> Any:
        """``widget["menu"]`` reaches the menu, as it does in tkinter."""
        if key == "menu":
            return self._options["menu"]
        return super().__getitem__(key)


class Message(_TextWidget):
    """A run of text that chooses its own line length.

    A Label wraps where it is told and is otherwise as wide as its longest
    line. A Message is the other way round: given no width at all it picks
    one, aiming for a block of text whose width is ``aspect`` percent of its
    height. The default of 150 gives a block half again as wide as it is
    tall, which is roughly the shape of a paragraph.

    ``width`` overrides the aspect, and ``wraplength`` overrides both - the
    first because Tk says so, the second because a caller who has named an
    exact wrap point has answered the question the aspect exists to guess at.

    Everything else - justification, anchoring, padding, the border - is a
    Label's, because a Message is a Label that has made its mind up about one
    thing.
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "aspect": 150,
        # Tk's Message justifies left rather than centre, which is what makes
        # it read as a paragraph instead of a banner.
        "justify": "left",
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``aspect``, plus everything a Label takes.
        """
        self._aspect_cache: tuple[tuple[str, int], int] | None = None
        super().__init__(master, cnf, name=name, **kw)

    def _lines(self) -> list[str]:
        """The text as display lines, wrapped to whatever width was settled on."""
        return wrap(self._text(), self._wrap_width())

    def _wrap_width(self) -> int:
        """Where the text breaks: the option that says so, or the aspect."""
        for option in ("wraplength", "width"):
            value = int(self._options[option])
            if value > 0:
                return value
        return self._aspect_width()

    def _aspect_width(self) -> int:
        """The line length whose block comes closest to the aspect ratio.

        Searched rather than solved: wrapping is a step function of the width
        - nothing changes until a word moves - so there is no formula that
        gives the answer, and the candidates are few enough to try. The
        result is cached, because it is wanted on every repaint and only the
        text and the aspect can change it.
        """
        text = self._text()
        words = text.split()
        if not words:
            return 0
        aspect = max(1, int(self._options["aspect"]))
        key = (text, aspect)
        if self._aspect_cache is not None and self._aspect_cache[0] == key:
            return self._aspect_cache[1]
        # No narrower than the longest word - narrower than that changes
        # nothing except where the word overflows - and no wider than the
        # whole text on one line.
        narrowest = max(len(word) for word in words)
        best, closest = narrowest, None
        for width in range(narrowest, len(text) + 1):
            block_width, block_height = measure(wrap(text, width))
            if not block_height:
                continue
            error = abs(100 * block_width / block_height - aspect)
            if closest is None or error < closest:
                best, closest = width, error
            if error == 0:
                break
        self._aspect_cache = (key, best)
        return best


class LabelFrame(Frame):
    """A frame with a caption written into its border.

    Everything a Frame is, with a name on it. The caption sits on the border
    line rather than inside the frame, so it costs no room: the children get
    exactly what they would have got from a plain frame of the same size.

    ``labelanchor`` says where on the border the caption goes. Tk allows the
    left and right edges too, with the text turned on its side; a terminal
    cannot turn text on its side, so those anchors put the caption at the
    nearest end of the top or bottom edge instead of pretending otherwise.
    """

    #: Where each of Tk's twelve labelanchor values puts the caption here,
    #: as (edge, alignment). The six that name a vertical edge in Tk are
    #: folded onto the horizontal one nearest them.
    _CAPTION_PLACES: ClassVar[dict[str, tuple[str, str]]] = {
        "nw": ("top", "left"),
        "n": ("top", "centre"),
        "ne": ("top", "right"),
        "wn": ("top", "left"),
        "en": ("top", "right"),
        "w": ("top", "left"),
        "e": ("top", "right"),
        "ws": ("bottom", "left"),
        "es": ("bottom", "right"),
        "sw": ("bottom", "left"),
        "s": ("bottom", "centre"),
        "se": ("bottom", "right"),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "font": "",
        "labelanchor": "nw",
        "relief": GROOVE,
        "text": "",
        "textvariable": None,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        class_: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            class_: The class this frame binds and reads options under.
            **kw: ``text``, ``textvariable``, ``labelanchor``, plus
                everything a Frame takes.
        """
        self._caption_trace: tuple[Variable, str] | None = None
        super().__init__(master, cnf, name=name, class_=class_, **kw)
        self._follow_caption()
        self._apply_requested_size()

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, following a new variable if one was named."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if "textvariable" in given:
            self._follow_caption()
        if given:
            self._apply_requested_size()
            self._invalidate_layout()
            self._redraw()
        return result

    config = configure

    def _follow_caption(self) -> None:
        """Track the ``textvariable``, dropping any previous one."""
        if self._caption_trace is not None:
            previous, handle = self._caption_trace
            previous.trace_remove("write", handle)
            self._caption_trace = None
        variable = self._options["textvariable"]
        if variable is None:
            return
        handle = variable.trace_add("write", lambda *_: self._caption_changed())
        self._caption_trace = (variable, handle)
        self._caption_changed()

    def _caption_changed(self) -> None:
        """Re-measure and repaint after the caption's variable moved.

        The ``text`` option follows the variable here too - see the note on
        ``_TextWidget._variable_changed``. A LabelFrame is a Frame rather
        than a _TextWidget, so it keeps its own copy of this.
        """
        variable = self._options["textvariable"]
        if variable is not None:
            self._options["text"] = str(variable.get())
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()

    def _caption(self) -> str:
        """The caption as it is drawn, spaced away from the border corners."""
        variable = self._options["textvariable"]
        text = (
            str(variable.get()) if variable is not None else str(self._options["text"])
        )
        return f" {text} " if text else ""

    def _apply_requested_size(self) -> None:
        """Never narrower than the caption, whatever the children want.

        A frame that asks for less than its own name leaves the name cut in
        half, which reads as a rendering fault rather than as a small frame.
        """
        super()._apply_requested_size()
        caption = self._caption()
        if not caption:
            return
        self._request_size(
            max(self._requested.width, len(caption) + 2 * BORDER_WIDTH),
            max(self._requested.height, 2),
        )

    def _redraw(self) -> None:
        """Paint the frame, then write the caption over its border."""
        super()._redraw()
        self._draw_caption()

    def _draw_caption(self) -> None:
        """Write the caption into the border line the anchor names."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        place = self._caption_place()
        if place is None:
            return
        row, column, text = place
        attribute = self._background_attribute() | self._font_attribute()
        dispatcher = CursesDispatcher.get()
        with contextlib.suppress(_curses.error):
            # The last-cell case this used to handle here - curses scrolls a
            # window whose cursor has nowhere left to go - is one of the two
            # things _write_line exists for, along with the clipping.
            self._write_line(dispatcher, window, row, column, text, attribute)

    def _caption_place(self) -> tuple[int, int, str] | None:
        """Where the caption is written, as ``(row, column, text)``, if it is.

        Shared by the painting and by ttk's ``identify``, which answers
        nothing over the caption, as Tk's does.
        """
        if not self._border_drawn:
            return None
        caption = self._caption()
        width, height = self._rect.width, self._rect.height
        if not caption or width < 3 or height < 2:
            return None
        edge, alignment = self._CAPTION_PLACES.get(
            str(self._options["labelanchor"]).lower(), ("top", "left")
        )
        room = width - 2 * BORDER_WIDTH
        text = clip_text(caption, room)
        if alignment == "centre":
            column = BORDER_WIDTH + (room - len(text)) // 2
        elif alignment == "right":
            column = width - BORDER_WIDTH - len(text)
        else:
            column = BORDER_WIDTH
        row = 0 if edge == "top" else height - 1
        return (row, column, text)


class Spinbox(Entry):
    """An entry with a pair of arrows that step through a set of values.

    Everything an Entry does, a Spinbox does: it is a text field, it can be
    typed into, and its contents are text whatever the arrows put there. What
    it adds is a way to arrive at a value without typing it - which in a
    terminal, where there is often no mouse, is what the Up and Down keys are
    for.

    There are two kinds. Given ``values``, it steps through that list and the
    numeric options are ignored. Given ``from_`` and ``to``, it counts by
    ``increment`` between them. ``wrap`` decides what happens at the end:
    stop, or come round to the other side.

    ``readonly`` is the state that makes a spinbox a chooser rather than a
    field - the arrows still work, the keyboard cannot put anything else in.
    That is the common use for the ``values`` form, and it is why stepping
    checks for ``disabled`` rather than going through the editing path.
    """

    #: The two arrows, drawn at the right-hand end of the field. Tk stacks
    #: them; a terminal row is one cell tall, so they sit side by side.
    _ARROWS = ("▲", "▼")

    #: Cells the arrows take. Taken out of the text area rather than added to
    #: the widget, so a Spinbox and an Entry of the same ``width`` are the
    #: same size on screen - which is what makes a column of them line up.
    _ARROW_WIDTH = 2

    _widget_options: ClassVar[dict[str, Any]] = {
        # The arrows: activebackground is stored only, since an arrow is not
        # drawn held down; buttonbackground is theirs. TkCurses-gm66.4.
        "activebackground": "",
        "buttonbackground": "",
        # The pointer over the arrows, which a terminal has none of, and their
        # reliefs: sunken is drawn dim. TkCurses-gm66.5.
        "buttoncursor": "",
        "buttondownrelief": "raised",
        "buttonuprelief": "raised",
        "command": None,
        "format": "",
        "from": 0.0,
        "increment": 1.0,
        # An arrow held down steps again after repeatdelay, then every
        # repeatinterval; Tk's defaults. TkCurses-gm66.6.
        "repeatdelay": 400,
        "repeatinterval": 100,
        "to": 0.0,
        "values": None,
        "wrap": False,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``values``, ``from_``, ``to``, ``increment``, ``wrap``,
                ``format``, ``command``, plus everything an Entry takes.
        """
        self._held_arrow: str | None = None
        self._repeated = 0
        super().__init__(master, cnf, name=name, **kw)
        if not self._field.text:
            # Straight into the field, not through _replace: that refuses a
            # disabled widget, and a disabled spinbox showing nothing at all
            # is worse than one showing a value it will not let you change.
            self._field.text = self._first_value()
            self._changed()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the editing keys and the arrows for every Spinbox.

        Binding tags name one class, not a chain of them, so a Spinbox does
        not inherit Entry's class bindings and has to say the same things
        again - which is also the chance to put Up and Down in front of them.
        """
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Any-Key>", _spinbox_key)
        bind(name, "<Button-1>", _spinbox_click)
        bind(name, "<Motion>", _entry_drag)
        bind(name, "<ButtonRelease-1>", _spinbox_release)
        bind(name, "<Double-Button-1>", _spinbox_double)
        if not _is_ttk(self):
            # ttk binds no triple-click: there a third click matches the
            # double-click binding again, a count of at least two.
            bind(name, "<Triple-Button-1>", _spinbox_triple)
        if not _is_ttk(self):
            bind(name, "<Control-Button-1>", _entry_control_click)
        for extend in _EXTEND_MODIFIERS:
            bind(name, f"<{extend}-Button-1>", _entry_shift_click)
            if not _is_ttk(self):
                bind(name, f"<Double-{extend}-Button-1>", _entry_double_shift)
                bind(name, f"<Triple-{extend}-Button-1>", _entry_triple_shift)
        bind(name, "<FocusIn>", _entry_focus_in)
        bind(name, "<FocusOut>", _entry_focus_out)
        _bind_entry_clipboard(bind, name)

    # --------------------------------------------------------------- values

    def _value_list(self) -> list[str]:
        """The ``values`` option as a list, or empty if there is none.

        A string is split on whitespace, because that is what a Tcl list
        looks like arriving through the option database.
        """
        values = self._options["values"]
        if not values:
            return []
        if isinstance(values, str):
            return values.split()
        return [str(value) for value in values]

    def _first_value(self) -> str:
        """What an empty spinbox starts holding."""
        values = self._value_list()
        if values:
            return values[0]
        return self._number_text(float(self._options["from"]))

    def _number_text(self, value: float) -> str:
        """One number as text, honouring ``format`` if it was given.

        Without a format the increment decides: a spinbox counting by 1 has
        no business showing ``3.0``, and one counting by 0.5 has no business
        showing ``3``.
        """
        template = str(self._options["format"])
        if template:
            with contextlib.suppress(TypeError, ValueError):
                return template % value
        increment = abs(float(self._options["increment"]))
        if increment and increment != int(increment):
            return f"{value:.4f}".rstrip("0").rstrip(".") or "0"
        return str(round(value))

    def _replace(self, text: str) -> None:
        """Put ``text`` in the field, as the arrows do.

        Not through :meth:`Entry._edit`: that refuses anything but the normal
        state, and a readonly spinbox's arrows are the whole point of the
        readonly state. The validator still gets its say.
        """
        if self._disabled or not self._validated(text):
            return
        self._field.text = text
        self._field.select_clear()
        self._changed()

    def bbox(self, index: Any) -> tuple[int, int, int, int]:
        """The box of the character at ``index`` - see :meth:`Entry._char_bbox`.

        ``tk.Spinbox`` has this and ``tk.Entry`` does not: tkinter gives the
        classic Entry only ``Misc.bbox``, the grid alias. TkCurses-52q.
        """
        return self._char_bbox(index)

    # ------------------------------------------------------------- stepping

    def _step(self, direction: int) -> None:
        """Move one place up or down the values, or the range."""
        values = self._value_list()
        text = (
            self._list_step(values, direction)
            if values
            else self._number_step(direction)
        )
        if text is None:
            return
        self._replace(text)
        command = self._options["command"]
        if command is not None:
            command()

    def _list_step(self, values: list[str], direction: int) -> str | None:
        """The next entry in ``values``, or None at an end that does not wrap.

        Contents that are not in the list at all - typed in, or left over
        from a previous ``values`` - step to whichever end the arrow points
        away from, so that either arrow gets a spinbox out of that state.
        """
        try:
            index = values.index(self._field.text) + direction
        except ValueError:
            return values[0] if direction > 0 else values[-1]
        if 0 <= index < len(values):
            return values[index]
        if not self._wraps:
            return None
        return values[index % len(values)]

    def _number_step(self, direction: int) -> str | None:
        """The next number in the range, or None at an end that does not wrap."""
        low, high = float(self._options["from"]), float(self._options["to"])
        if low == high:
            return None
        increment = abs(float(self._options["increment"])) or 1.0
        try:
            current = float(self._field.text)
        except ValueError:
            # Something that is not a number at all: the arrows put the
            # spinbox back on the scale rather than refusing to move.
            return self._number_text(low)
        step = increment if high > low else -increment
        value = round(current + step * direction, 10)
        lo, hi = min(low, high), max(low, high)
        if lo <= value <= hi:
            return self._number_text(value)
        if not self._wraps:
            return None
        return self._number_text(high if value < lo else low)

    @property
    def _wraps(self) -> bool:
        """True while stepping past an end comes round to the other."""
        try:
            return self.getboolean(self._options["wrap"])
        except TclError:
            return False

    # ------------------------------------------------------------ public API

    def invoke(self, element: str) -> None:
        """Press one of the arrows from code.

        Args:
            element: ``"buttonup"`` or ``"buttondown"``.

        Raises:
            TclError: If it is neither.
        """
        if element == "buttonup":
            self._step(1)
        elif element == "buttondown":
            self._step(-1)
        else:
            raise TclError(f'bad element "{element}": must be buttondown or buttonup')

    def identify(self, x: int, y: int) -> str:
        """Which part of the spinbox is at a position within this widget.

        Args:
            x: Column within this widget, as an Event reports it.
            y: Row within this widget.

        Returns:
            ``"buttonup"``, ``"buttondown"``, ``"entry"``, or ``"none"``
            for anywhere outside the widget.
        """
        if not (0 <= x < self._rect.width and 0 <= y < self._rect.height):
            return "none"
        up, down = self._arrow_columns()
        if up is None or down is None:
            return "entry"
        if x == up:
            return "buttonup"
        if x == down:
            return "buttondown"
        return "entry"

    # -------------------------------------------------------------- painting

    def _apply_requested_size(self) -> None:
        """Ask for the field's width plus room for the two arrows."""
        super()._apply_requested_size()
        self._request_size(
            self._requested.width + self._ARROW_WIDTH, self._requested.height
        )

    def _text_area(self) -> Rect:
        """Where the text goes: the field, less the arrows at its right end."""
        area = super()._text_area()
        return Rect(area.x, area.y, max(0, area.width - self._ARROW_WIDTH), area.height)

    def _arrow_columns(self) -> tuple[int | None, int | None]:
        """Which columns the two arrows occupy, or None if there is no room."""
        area = super()._text_area()
        if area.width < self._ARROW_WIDTH:
            return (None, None)
        return (area.x + area.width - 2, area.x + area.width - 1)

    def _redraw(self) -> None:
        """Paint the field, then the arrows at its right-hand end."""
        super()._redraw()
        window = self._window
        if window is None or self.tk.screen is None:
            return
        up_column, down_column = self._arrow_columns()
        if up_column is None or down_column is None:
            return
        area = super()._text_area()
        attribute = self._in_state(
            self._background_attribute() | self._font_attribute()
        )
        if self._options["buttonbackground"]:
            state = self._state_colours(str(self._options["state"]))
            attribute = self._coloured(
                attribute,
                state[0] if state is not None else "",
                self._options["buttonbackground"],
            )
        dispatcher = CursesDispatcher.get()
        # Through the shared writer, for the reason the listbox uses it: the
        # second arrow used to go on with insstr, which shifted the row along
        # and pushed a bordered spinbox's right border off the end.
        # Unbordered, the arrows really do reach the last cell and insstr
        # really is needed - _write_line is what tells the two cases apart.
        up, down = self._ARROWS
        for column, arrow, relief in (
            (up_column, up, self._options["buttonuprelief"]),
            (down_column, down, self._options["buttondownrelief"]),
        ):
            self._write_line(
                dispatcher,
                window,
                area.y,
                column,
                arrow,
                attribute | _part_relief(relief),
            )


def _spinbox_key(event: Event) -> str | None:
    """Step on Up and Down, and otherwise behave exactly like an Entry."""
    spinbox = event.widget
    if event.keysym == "Up":
        spinbox._step(1)
        return "break"
    if event.keysym == "Down":
        spinbox._step(-1)
        return "break"
    return _entry_key(event)


def _spinbox_click(event: Event) -> None:
    """Press an arrow, or place the cursor in the text.

    A classic arrow steps when it is released, or repeatedly while it is
    held, as ``tk::spinbox::ArrowPress`` arranges. ttk's steps on the press
    (``ttk::spinbox::Press``), and repeats with timing of its own that is
    not taken here.
    """
    spinbox = event.widget
    # The classic method, by name: a ttk subclass's own identify answers
    # ttk's element names, which this binding cannot act on. TkCurses-d5u.
    part = Spinbox.identify(spinbox, event.x, event.y)
    if part not in ("buttonup", "buttondown"):
        _entry_click(event)
        return
    spinbox.focus_set()
    if _is_ttk(spinbox):
        spinbox._step(1 if part == "buttonup" else -1)
        return
    spinbox._held_arrow = part
    spinbox._repeated = 0
    delay = _repeat_option(spinbox, "repeatdelay")
    if delay > 0:
        _repeat_after(spinbox, delay, _spinbox_invoke, spinbox, part)


def _spinbox_invoke(spinbox: Any, part: str) -> None:
    """Step for a held arrow and go on doing so: ``tk::spinbox::Invoke``."""
    spinbox._step(1 if part == "buttonup" else -1)
    spinbox._repeated += 1
    interval = _repeat_option(spinbox, "repeatinterval")
    if interval > 0:
        _repeat_after(spinbox, interval, _spinbox_invoke, spinbox, part)


def _spinbox_release(event: Event) -> None:
    """Step for an arrow that was pressed and not held: ``tk::spinbox::ButtonUp``.

    Wherever the pointer is now: Tk steps on a release away from the arrow,
    which a press that changes its mind cannot take back.
    """
    spinbox = event.widget
    _cancel_repeat(spinbox)
    part, spinbox._held_arrow = spinbox._held_arrow, None
    if part is not None and not spinbox._repeated:
        spinbox._step(1 if part == "buttonup" else -1)
    _entry_release(event)


def _spinbox_arrow(spinbox: Any, event: Event) -> bool:
    """True if the press was on an arrow, which steps instead of selecting."""
    return Spinbox.identify(spinbox, event.x, event.y) in ("buttonup", "buttondown")


def _spinbox_double(event: Event) -> None:
    """On an arrow, another step; in the text, select.

    Classic: a word, the cursor at its START (``tk::spinbox::MouseSelect`` is
    given ``sel.first``, where Entry's binding moves to ``sel.last``). ttk:
    everything (``ttk::spinbox::DoubleClick`` calls SelectAll). Measured.
    """
    spinbox = event.widget
    if _spinbox_arrow(spinbox, event):
        _spinbox_click(event)
        return
    if not _entry_selects(spinbox):
        return
    if _is_ttk(spinbox):
        _entry_start_drag(spinbox, "char")
        spinbox._dragging = False  # ttk's DoubleClick starts no drag
        spinbox.selection_range(0, "end")
        spinbox.icursor("end")
    else:
        _entry_start_drag(spinbox, "word")
        _entry_select_to(spinbox, event.x)
        if spinbox._field.selection is not None:
            spinbox.icursor(spinbox._field.selection[0])
    spinbox._see_cursor()
    spinbox._redraw()


def _spinbox_triple(event: Event) -> None:
    """On an arrow, another step; in the text, select everything.

    Classic only - ttk binds no triple-click. The cursor goes to 0
    (``MouseSelect ... 0``).
    """
    spinbox = event.widget
    if _spinbox_arrow(spinbox, event):
        _spinbox_click(event)
        return
    if not _entry_selects(spinbox):
        return
    _entry_start_drag(spinbox, "line")
    _entry_select_to(spinbox, event.x)
    spinbox.icursor(0)
    spinbox._see_cursor()
    spinbox._redraw()


#: The tag options whose values are cells and therefore move text about.
#: Setting one of these is what makes a Text pay for margin resolution.
_MARGIN_OPTIONS = frozenset({"lmargin1", "lmargin2", "rmargin"})


def _spaced(
    rows: list[tuple[int, int, int]], above: int, between: int, below: int
) -> list[tuple[int, int, int]]:
    """One line's display rows, with Tk's spacing as blank rows among them.

    A blank row is its neighbour with the line number negated, so it holds
    no index - nothing matches a negative line - and still says which row
    a click on it means. ``spacing2`` is split as Tk splits it, the larger
    half above each continuation row and the rest below the row before:
    measured on Tk 9.0.2, spacing2 of 3 pixels put 1 under the first row
    and 2 over the second.
    """
    out: list[tuple[int, int, int]] = []
    last = len(rows) - 1
    for n, (line, start, stop) in enumerate(rows):
        gap = above if n == 0 else between - between // 2
        out.extend([(-line, start, stop)] * gap)
        out.append((line, start, stop))
        gap = below if n == last else between // 2
        out.extend([(-line, start, stop)] * gap)
    return out


class Text(_Drawable, XView, YView):
    """An editable block of text, with marks and tags.

    The contents, the index arithmetic, the marks and the tag ranges are
    :class:`~tkcurses._core.textbuffer.TextBuffer`; what is here is the widget
    around it - options, key bindings, what the tags look like on screen, and
    the two-directional scrolling that a Text needs and an Entry does not.

    Everything is addressed by index, written ``line.char`` with lines
    counting from 1. ``insert`` is the cursor, ``end`` is past everything, and
    ``sel.first``/``sel.last`` are the ends of the selection. Because Tk keeps
    a newline at the end of the buffer that no edit can remove, ``end`` on a
    one-line Text is ``2.0`` and ``get("1.0", "end")`` comes back with a
    newline nobody typed. That surprises people, and it is kept, because
    tkinter code depends on it.

    ``wrap`` decides what a long line does: ``none`` scrolls sideways,
    ``char`` breaks wherever the width runs out, ``word`` at the last space
    that fits. The distinction between a line in the buffer and a line on
    screen runs through the whole widget - Up and Down move by *display*
    lines, as they do in every editor, while ``insert linestart`` means the
    beginning of the real line.
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_INSERT_CURSOR_OPTIONS,
        **_SELECTION_OPTIONS,
        "blockcursor": 0,
        "inactiveselectbackground": _TerminalsOwn(),
        "insertunfocussed": "none",
        "autoseparators": True,
        "exportselection": True,
        "font": "",
        "height": 24,
        # Undo groups kept, 0 for all; and blank rows above each line, between
        # the rows of a wrapped one, and below each. Tk's are pixels, and
        # these are rows. TkCurses-gm66.8.
        "maxundo": 0,
        "relief": "sunken",
        "spacing1": 0,
        "spacing2": 0,
        "spacing3": 0,
        "state": "normal",
        "tabs": "",
        "tabstyle": "tabular",
        "takefocus": True,
        "undo": False,
        "width": 80,
        "wrap": "char",
        "xscrollcommand": None,
        "yscrollcommand": None,
    }

    #: What a tag can be given. Smaller than Tk's, but no longer by as much:
    #: this list used to exclude MARGINS, on the grounds that they have "no
    #: meaning in a character grid". That was wrong, and the correction is
    #: worth keeping visible. What has no meaning in a character grid is a
    #: PIXEL, not a margin - an indent of four cells is perfectly meaningful,
    #: and the project already maps every other screen distance to cells
    #: (padx, pady, place coordinates, winfo_fpixels at ten to the inch).
    #: Indentation in Tk is a tag feature rather than a tab feature, so
    #: dropping these dropped indentation altogether - TkCurses-wy7.
    #:
    #: Still left out, and correctly: ``offset`` is a sub-cell baseline shift
    #: for super- and subscripts. ``spacing1/2/3`` work in whole rows on the
    #: widget (TkCurses-gm66.8) and are not yet taken per tag. Borders and
    #: bitmaps have no cell equivalent.
    #: Setting one of those still fails loudly rather than quietly doing
    #: nothing.
    _TAG_OPTIONS: ClassVar[dict[str, Any]] = {
        "background": "",
        "foreground": "",
        "font": "",
        "justify": "",
        "lmargin1": 0,
        "lmargin2": 0,
        "lmargincolor": "",
        "rmargin": 0,
        "underline": False,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``width``, ``height``, ``wrap``, ``state``, ``undo``,
                ``autoseparators``, ``maxundo``, ``spacing1``, ``spacing2``,
                ``spacing3``, ``xscrollcommand``, ``yscrollcommand``, and the
                standard options.
        """
        self._buffer = TextBuffer()
        self._top = 0
        self._left = 0
        self._anchor: Index | None = None
        self._dragging = False
        # What a drag extends by, whether it has moved off the press, where the
        # press and the pointer were, and the pending autoscroll. TkCurses-svtr.
        self._select_mode = "char"
        self._moved = False
        self._press_x = 0
        self._drag_at = (0, 0)
        self._autoscan: str | None = None
        # The screen cell the terminal's cursor goes in; see _draw_cursor.
        self._insert_at: tuple[int, int] | None = None
        self._tag_options: dict[str, dict[str, Any]] = {}
        self._tag_order: list[str] = []
        #: Tk's "has this been changed since it was last saved" flag. It is
        #: NOT the undo stack: it works with ``-undo false``, and clearing
        #: it leaves the stack alone.
        self._modified = False
        #: What the last recorded edit was, so autoseparators can break the
        #: group when the user switches between typing and deleting.
        self._last_edit: str | None = None
        #: Whether ANY tag sets a margin. Almost none ever do, and resolving
        #: margins means asking which tags cover a row and walking the raise
        #: order - per row, inside wrapping, which is hot. Measured: doing it
        #: unconditionally took a Text repaint from under 25ms to 31.6ms and
        #: failed the redraw budget. This is the flag that keeps the common
        #: case free.
        self._margined = False
        super().__init__(master, cnf, name=name, **kw)
        self._buffer.undo_enabled = self.getboolean(self._options["undo"])
        self._buffer.max_undo = _as_int(self._options["maxundo"], 0)
        self._stops = parse_tabs(self._options["tabs"], self.winfo_fpixels)
        self._buffer.mark_set("insert", "1.0")
        self._buffer.mark_set("current", "1.0")
        # The selection is a tag like any other, which is why sel.first works
        # as an index. Its colours are the widget's select colours, and in Tk
        # each follows the other: see _SELECTION_TAG_OPTIONS.
        self.tag_configure(
            "sel",
            background=self._options["selectbackground"],
            foreground=self._options["selectforeground"],
        )
        self._apply_requested_size()
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the editing keys and the mouse for every Text here."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Any-Key>", _text_key)
        bind(name, "<<Copy>>", _text_copy)
        bind(name, "<<Cut>>", _text_cut)
        bind(name, "<<Paste>>", _text_paste)
        bind(name, "<<Clear>>", _text_clear)
        bind(name, "<<SelectAll>>", _text_select_all)
        bind(name, "<<PasteSelection>>", _text_paste_selection)
        bind(name, "<Button-1>", _text_press)
        bind(name, "<Double-Button-1>", _text_double)
        bind(name, "<Triple-Button-1>", _text_triple)
        bind(name, "<Control-Button-1>", _text_control_click)
        # Tk binds this to nothing, on purpose: without it a double-click
        # with Ctrl held would select a word, as a plain one does.
        bind(name, "<Control-Double-Button-1>", _do_nothing)
        for extend in _EXTEND_MODIFIERS:
            bind(name, f"<{extend}-Button-1>", _text_shift_press)
            bind(name, f"<Double-{extend}-Button-1>", _text_double_shift)
            bind(name, f"<Triple-{extend}-Button-1>", _text_triple_shift)
        # A drag arrives as Motion - curses reports motion-with-a-button and
        # there is no Button1 modifier to match against - and the implicit
        # grab keeps it with the widget that was pressed.
        bind(name, "<Motion>", _text_motion)
        bind(name, "<ButtonRelease-1>", _text_release)
        bind(name, "<Button-4>", _text_wheel)
        bind(name, "<Button-5>", _text_wheel)
        bind(name, "<FocusIn>", _text_refresh)
        bind(name, "<FocusOut>", _text_refresh)

    # --------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        selection = self._tag_options["sel"]
        for widget_option, tag_option in _SELECTION_TAG_OPTIONS.items():
            selection[tag_option] = self._options[widget_option]
        if {"width", "height"} & set(given):
            self._apply_requested_size()
            self._invalidate_layout()
        if "undo" in given:
            # Turning it off does NOT throw the stack away: Tk keeps it, so
            # switching undo off and on again leaves the history intact.
            self._buffer.undo_enabled = self.getboolean(self._options["undo"])
        if "maxundo" in given:
            self._buffer.max_undo = _as_int(self._options["maxundo"], 0)
            self._buffer.trim_undo()
        if "tabs" in given:
            self._stops = parse_tabs(self._options["tabs"], self.winfo_fpixels)
        self._clamp_view()
        self._redraw()
        self._report_view()
        return result

    config = configure

    @property
    def _editable(self) -> bool:
        """True while the keyboard may change the contents."""
        return str(self._options["state"]) == "normal"

    def _apply_requested_size(self) -> None:
        """Ask for the configured rows and columns, plus border and padding."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            int(self._options["width"]) + 2 * int(self._options["padx"]) + edge,
            int(self._options["height"]) + 2 * int(self._options["pady"]) + edge,
        )

    # --------------------------------------------------------------- indices

    def index(self, spec: Any) -> str:
        """Resolve an index and return it as ``line.char``.

        Returns a string rather than an object, because that is what tkinter
        returns and what code written against it compares and slices.
        """
        return str(self._resolve(spec))

    def compare(self, first: Any, op: str, last: Any) -> bool:
        """Compare two indices with ``<``, ``<=``, ``==``, ``!=``, ``>``, ``>=``."""
        return self._buffer.compare(self._resolve(first), op, self._resolve(last))

    def _resolve(self, spec: Any) -> Index:
        """One index, including the ``@x,y`` form only the widget can answer."""
        if isinstance(spec, Index):
            return self._buffer.clamp(spec)
        text = str(spec).strip()
        if text.startswith("@"):
            position, _, rest = text[1:].partition(",")
            column, _, modifiers = rest.partition(" ")
            index = self._index_at_cell(int(position), int(column))
            if modifiers.strip():
                return self._buffer.index(f"{index} {modifiers.strip()}")
            return index
        return self._buffer.index(text)

    # -------------------------------------------------------------- contents

    def get(self, first: Any, last: Any = None) -> str:
        """The text between two indices, or one character from ``first``."""
        if last is None:
            return self._buffer.get(self._resolve(first))
        return self._buffer.get(self._resolve(first), self._resolve(last))

    def insert(self, index: Any, chars: str, *tags: str) -> None:
        """Insert text, optionally tagging everything inserted.

        A disabled Text ignores it, silently, as Tk's does: "no insertions or
        deletions are allowed", and measured on Tk 9.0.2 nothing is raised
        either. The tkinter idiom for a read-only display is to set the state
        to normal around the insert. TkCurses-aah.
        """
        if not self._editable:
            return
        start = self._resolve(index)
        end = self._buffer.insert(start, chars)
        for tag in tags:
            self.tag_add(tag, start, end)
        self._after_edit()

    def delete(self, first: Any, last: Any = None) -> None:
        """Delete a range, or one character from ``first``.

        Ignored while disabled, as :meth:`insert` is. TkCurses-aah.
        """
        if not self._editable:
            return
        if last is None:
            self._buffer.delete(self._resolve(first))
        else:
            self._buffer.delete(self._resolve(first), self._resolve(last))
        self._after_edit()

    def _after_edit(self) -> None:
        """Put the view back where it should be and repaint."""
        self.see("insert")
        self._redraw()
        self._report_view()
        self._set_modified(True)

    def _set_modified(self, state: bool) -> None:
        """Move the modified flag, announcing it only when it moves.

        Measured against Tk: ``<<Modified>>`` fires on the CHANGE, not on
        the edit. Two inserts in a row give one event, and clearing the flag
        with ``edit_modified(False)`` gives another - it is an event about
        the flag, not about the text. This used to fire on every edit, so a
        handler that saved on it saved far more often than Tk would.
        """
        if state == self._modified:
            return
        self._modified = state
        self.event_generate("<<Modified>>")

    # -------------------------------------------------------------- geometry

    def dlineinfo(self, index: Any) -> tuple[int, int, int, int, int] | None:
        """Where the display line holding ``index`` is, in cells.

        Returns ``(x, y, width, height, baseline)`` relative to this widget,
        or None when that line is not on screen - which is what tkinter
        does, and what makes this worth asking rather than calculating: the
        answer depends on where the view has been scrolled to.

        ``height`` is always 1 and ``baseline`` is always 0. Tk measures
        both in pixels, and in a character grid the row is one cell tall
        with nothing below the letters, so 0 is the honest answer rather
        than a placeholder. ``width`` is the length of the line's text, not
        the width of the widget.

        A *display* line, note, not a logical one: a wrapped paragraph has
        one of these per row on screen.
        """
        found = self._row_and_column(index)
        if found is None:
            return None
        row, _, (line_start, line_stop) = found
        rows = self._display_lines()
        number = rows[row][0]
        left, _ = self._row_margins(number, line_start)
        area = self._text_area()
        y = area.y + (row - self._top)
        if not 0 <= y - area.y < area.height:
            return None
        # The row's width in COLUMNS, not in characters: a tab is wider than
        # one cell, and the indent is not part of the text. Tk reports the
        # indent in x - measured, it answered x=64 for an eight-column
        # margin - and the text's own width beside it.
        text = self._row_text(number, line_start, line_stop)
        width = (
            column_of(
                text,
                len(text),
                start=left,
                stops=self._stops,
                style=str(self._options["tabstyle"]),
            )
            - left
        )
        return (area.x + left - self._left, y, width, 1, 0)

    def bbox(self, index: Any) -> tuple[int, int, int, int] | None:
        """Where the character at ``index`` is, as ``(x, y, width, height)``.

        One cell, so the size is always ``1, 1``. None when the character
        is not on screen, horizontally as well as vertically: a long line
        scrolled sideways puts characters out of view without putting their
        line out of view, and Tk returns None for those too.
        """
        found = self._row_and_column(index)
        if found is None:
            return None
        row, column, _ = found
        area = self._text_area()
        x = area.x + (column - self._left)
        y = area.y + (row - self._top)
        if not 0 <= x - area.x < area.width:
            return None
        if not 0 <= y - area.y < area.height:
            return None
        return (x, y, 1, 1)

    def _row_and_column(self, index: Any) -> tuple[int, int, tuple[int, int]] | None:
        """The display row and column for an index, and that row's extent.

        The inverse of :meth:`_index_at_cell`, and deliberately written as
        such: the two have to agree, or a click and a bbox disagree about
        where the same character is. Both work in rows across the whole
        document; the caller takes ``_top`` and ``_left`` off to reach the
        screen.
        """
        rows = self._display_lines()
        if not rows:
            return None
        resolved = self._resolve(index)
        row, column = self._display_position(resolved, rows)
        _, start, stop = rows[row]
        return row, column, (start, stop)

    # ---------------------------------------------------------------- search

    def search(
        self,
        pattern: str,
        index: Any,
        stopindex: Any = None,
        forwards: bool | None = None,
        backwards: bool | None = None,
        exact: bool | None = None,
        regexp: bool | None = None,
        nocase: bool | None = None,
        count: Any = None,
        elide: bool | None = None,
    ) -> str:
        """Find ``pattern``, returning where it starts as ``line.char``.

        Returns the empty string when there is no match, which is what
        tkinter returns and what calling code tests for.

        Args:
            pattern: Text to find, or a regular expression with ``regexp``.
            index: Where to start looking.
            stopindex: Where to give up. Without it the search WRAPS -
                forwards runs off the end and round to the beginning, and
                backwards the other way. This surprises people, and it is
                what Tk does.
            forwards: Search towards the end. The default.
            backwards: Search towards the beginning instead.
            exact: Match the pattern literally. The default.
            regexp: Match it as a regular expression, **line by line** - so
                ``^`` and ``$`` are the edges of a line and nothing matches
                across a newline. An exact search has no such limit and
                will happily match across one.
            nocase: Ignore case.
            count: A variable to put the match length in, in characters.
                Anything with a ``set`` method, as in tkinter, where it is
                usually an ``IntVar``.
            elide: Accepted and ignored. Tk skips elided text with this;
                nothing is ever elided here because there is no ``elide``
                tag option, so there is nothing for it to do. Taking it and
                doing nothing is better than rejecting a call that would
                work in tkinter.

        Passing both ``exact`` and ``regexp`` is not an error: ``regexp``
        wins, which is measured behaviour rather than a choice made here.
        """
        del forwards, exact, elide  # Defaults; named so the signature matches.
        found = self._buffer.search(
            pattern,
            self._resolve(index),
            None if stopindex is None else self._resolve(stopindex),
            backwards=bool(backwards),
            regexp=bool(regexp),
            nocase=bool(nocase),
        )
        if found is None:
            return ""
        where, length = found
        if count is not None:
            count.set(length)
        return str(where)

    # ------------------------------------------------------------------ undo

    def edit_undo(self) -> None:
        """Take back the most recent group of edits.

        Raises:
            TclError: If there is nothing to undo, as tkinter does.

        With ``-undo false`` this does nothing at all and raises nothing,
        which is also measured rather than assumed: Tk treats "undo is off"
        and "undo is on but the stack is empty" as two different situations,
        and only the second is an error.

        A disabled Text changes nothing, but still raises on an empty stack,
        as Tk's does (measured). **Deliberately unlike Tk**, the stack does
        not move either: Tk 9.0.2's disabled undo pops the group while
        refusing its edits, so the history no longer describes the text and a
        later redo applies the same edit twice - "hello world" became "hello
        world world". Copying that would copy a defect. TkCurses-aah.
        """
        if not self.getboolean(self._options["undo"]):
            return
        if not self._editable:
            if not self._buffer.can_undo:
                raise TclError("nothing to undo")
            return
        if not self._buffer.edit_undo():
            raise TclError("nothing to undo")
        self._last_edit = None
        self._after_undo()

    def edit_redo(self) -> None:
        """Put back the most recently undone group.

        Raises:
            TclError: If there is nothing to redo, as tkinter does.

        Disabled, the same as :meth:`edit_undo`: nothing changes, the stack
        included, and an empty stack still raises.
        """
        if not self.getboolean(self._options["undo"]):
            return
        if not self._editable:
            if not self._buffer.can_redo:
                raise TclError("nothing to redo")
            return
        if not self._buffer.edit_redo():
            raise TclError("nothing to redo")
        self._last_edit = None
        self._after_undo()

    def _after_undo(self) -> None:
        """Repaint after the stack moved the text under the cursor.

        The insert mark is moved by the same ``_shift`` that moves every
        other mark, so it is already somewhere sensible - but it may be off
        screen, and the scrollbars no longer describe what is there.
        """
        self.see("insert")
        self._redraw()
        self._report_view()
        self._set_modified(True)

    def edit_separator(self) -> None:
        """Break the undo group, so the next edit undoes on its own."""
        self._buffer.edit_separator()
        self._last_edit = None

    def edit_reset(self) -> None:
        """Throw away the undo and redo history, keeping the text."""
        self._buffer.edit_reset()
        self._last_edit = None

    def edit_modified(self, arg: Any = None) -> int | None:
        """Read the modified flag, or set it.

        Returns 0 or 1 rather than a bool, which is what tkinter returns and
        what code written against it compares against.
        """
        if arg is None:
            return int(self._modified)
        self._set_modified(self.getboolean(arg))
        return None

    def _separate_if_asked(self, kind: str | None) -> None:
        """Start a new undo group when the user changes what they are doing.

        With ``-autoseparators true`` a run of typing undoes as a run, and
        the run ends where a person would say it ended: when they move the
        cursor, click somewhere else, or switch from typing to deleting.
        Without this every character is its own group and undo becomes
        backspace with extra steps.

        Programmatic ``insert()`` and ``delete()`` deliberately do NOT come
        here. Measured against Tk: three ``insert()`` calls in a row with
        autoseparators on are one group, because Tk's separators come from
        the key bindings rather than from the widget command.
        """
        if not self.getboolean(self._options["autoseparators"]):
            return
        if kind is None or kind != self._last_edit:
            self._buffer.edit_separator()
        self._last_edit = kind

    # ----------------------------------------------------------------- marks

    def mark_set(self, name: str, index: Any) -> None:
        """Put a mark at an index."""
        self._buffer.mark_set(name, self._resolve(index))
        if name == "insert":
            self.see("insert")
        self._redraw()

    def mark_unset(self, *names: str) -> None:
        """Remove marks."""
        self._buffer.mark_unset(*names)
        self._redraw()

    def mark_names(self) -> tuple[str, ...]:
        """Every mark."""
        return self._buffer.mark_names()

    def mark_gravity(self, name: str, direction: str | None = None) -> str:
        """Read or set which side of an insertion a mark ends up on."""
        return self._buffer.mark_gravity(name, direction)

    def mark_next(self, index: Any) -> str | None:
        """The first mark after an index."""
        return self._buffer.mark_next(self._resolve(index))

    def mark_previous(self, index: Any) -> str | None:
        """The last mark before an index."""
        return self._buffer.mark_previous(self._resolve(index))

    # ------------------------------------------------------------------ tags

    def tag_add(self, name: str, first: Any, last: Any = None) -> None:
        """Tag a range."""
        self._note_tag(name)
        if last is None:
            self._buffer.tag_add(name, self._resolve(first))
        else:
            self._buffer.tag_add(name, self._resolve(first), self._resolve(last))
        if name == "sel":
            self._claim_primary()
        self._redraw()

    def tag_remove(self, name: str, first: Any, last: Any = None) -> None:
        """Untag a range."""
        if last is None:
            self._buffer.tag_remove(name, self._resolve(first))
        else:
            self._buffer.tag_remove(name, self._resolve(first), self._resolve(last))
        self._redraw()

    def tag_delete(self, *names: str) -> None:
        """Forget tags entirely, ranges, options and all."""
        self._buffer.tag_delete(*names)
        for name in names:
            self._tag_options.pop(name, None)
            if name in self._tag_order:
                self._tag_order.remove(name)
        self._redraw()

    def tag_names(self, index: Any = None) -> tuple[str, ...]:
        """Every tag, or only those covering one index."""
        if index is None:
            return tuple(self._tag_order)
        return self._buffer.tag_names(self._resolve(index))

    def _has_copyable_selection(self) -> bool:
        return bool(self.tag_ranges("sel"))

    def tag_ranges(self, name: str) -> list[str]:
        """Every range of a tag, flat, as ``line.char`` strings."""
        return [str(index) for index in self._buffer.tag_ranges(name)]

    def tag_nextrange(
        self, name: str, first: Any, last: Any = None
    ) -> tuple[str, str] | tuple[()]:
        """The first range of a tag at or after an index, or ``()``."""
        found = self._buffer.tag_nextrange(
            name, self._resolve(first), None if last is None else self._resolve(last)
        )
        return () if found is None else (str(found[0]), str(found[1]))

    def tag_prevrange(
        self, name: str, first: Any, last: Any = None
    ) -> tuple[str, str] | tuple[()]:
        """The last range of a tag before an index, or ``()``."""
        found = self._buffer.tag_prevrange(
            name, self._resolve(first), None if last is None else self._resolve(last)
        )
        return () if found is None else (str(found[0]), str(found[1]))

    def tag_configure(
        self, name: str, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> Any:
        """Set how a tag looks, or read what it is set to.

        Raises:
            TclError: If an option is not one a tag accepts here.
        """
        self._note_tag(name)
        options = self._tag_options[name]
        given = _given(cnf, kw)
        if not cnf and not kw:
            return dict(options)
        if not given:  # every option None, which tkinter drops
            return None
        for option, value in given.items():
            resolved = _OPTION_ALIASES.get(option, option)
            if resolved not in self._TAG_OPTIONS:
                raise TclError(f'unknown option "-{option}"')
            options[resolved] = value
            if name == "sel" and resolved in _SELECTION_WIDGET_OPTIONS:
                self._options[_SELECTION_WIDGET_OPTIONS[resolved]] = value
            if resolved in _MARGIN_OPTIONS and value not in (0, "", None):
                # Latches on rather than being recomputed: a margin set and
                # then cleared is rare, and paying for the scan once is
                # cheaper than checking every tag on every configure.
                self._margined = True
        self._redraw()
        return None

    tag_config = tag_configure

    def tag_cget(self, name: str, option: str) -> Any:
        """One of a tag's options.

        Raises:
            TclError: If the tag or the option does not exist.
        """
        if name not in self._tag_options:
            raise TclError(f'tag "{name}" is not defined')
        resolved = _OPTION_ALIASES.get(option, option)
        if resolved not in self._TAG_OPTIONS:
            raise TclError(f'unknown option "-{option}"')
        return self._tag_options[name][resolved]

    def tag_raise(self, name: str, above: str | None = None) -> None:
        """Move a tag up the priority order, so it draws over the others."""
        self._reorder(name, above, offset=1)

    def tag_lower(self, name: str, below: str | None = None) -> None:
        """Move a tag down the priority order."""
        self._reorder(name, below, offset=0)

    def _reorder(self, name: str, other: str | None, *, offset: int) -> None:
        """Shared by tag_raise and tag_lower."""
        self._note_tag(name)
        self._tag_order.remove(name)
        if other is None:
            self._tag_order.append(name) if offset else self._tag_order.insert(0, name)
        else:
            self._note_tag(other)
            self._tag_order.insert(self._tag_order.index(other) + offset, name)
        self._redraw()

    def _note_tag(self, name: str) -> None:
        """Record a tag's existence and its place in the priority order."""
        if name not in self._tag_options:
            self._tag_options[name] = dict(self._TAG_OPTIONS)
            self._tag_order.append(name)

    # ------------------------------------------------------------- selection

    def _select(self, first: Any, last: Any) -> None:
        """Replace the selection with one range, dropping it if it is empty."""
        self._buffer.tag_remove("sel", "1.0", "end")
        start, stop = self._resolve(first), self._resolve(last)
        if start != stop:
            self._buffer.tag_add("sel", start, stop)
        self._claim_primary()

    def _claim_primary(self) -> None:
        """Take PRIMARY while something is selected and ``exportselection`` is on.

        The option was stored and never read (TkCurses-9e8): a Text's
        selection never reached PRIMARY, so selecting in a Text did not clear
        an Entry's selection, as Tk's does, and the middle button could not
        paste it. Measured on Tk 9.0.2 between Entry and Text, both ways.
        """
        if not self.tag_ranges("sel") or not self.getboolean(
            self._options["exportselection"]
        ):
            return
        selections = self.tk.selections
        selections.own(self, PRIMARY, lost=self._lost_primary)
        selections.handle(self, self._primary_selection, PRIMARY)

    def _lost_primary(self) -> None:
        """Another widget took PRIMARY: drop this one's selection, as Tk does."""
        self._buffer.tag_remove("sel", "1.0", "end")
        self._redraw()

    def _primary_selection(self, *_args: Any) -> str:
        """The selected text, for whoever reads PRIMARY; raises with none."""
        found = self._selection_range()
        if found is None:
            raise TclError(f"{PRIMARY} selection doesn't exist or form unknown")
        return str(self._buffer.get(*found))

    def _selection_range(self) -> tuple[Index, Index] | None:
        """The selection, or None."""
        ranges = self._buffer.tag_ranges("sel")
        return (ranges[0], ranges[-1]) if ranges else None

    def _delete_selection(self) -> bool:
        """Delete the selected text. True if there was any."""
        found = self._selection_range()
        if found is None:
            return False
        self._buffer.mark_set("insert", found[0])
        self._buffer.delete(found[0], found[1])
        self._anchor = None
        return True

    # ------------------------------------------------------------- editing

    def _move(self, where: Any, *, extend: bool) -> None:
        """Move the insert cursor, dragging the selection along if asked.

        ``extend`` is what a shifted arrow does: the selection runs from
        wherever it was anchored to wherever the cursor has got to. Without
        it the selection is dropped, which is what a plain arrow does.
        """
        # Moving the cursor ends whatever was being typed: the next edit is
        # somewhere else, so it is a new thing to undo.
        self._separate_if_asked(None)
        insert = self._buffer.mark_index("insert") or Index(1, 0)
        if isinstance(where, tuple):
            kind, count = where
            if kind == "word":
                target = self._by_word(insert, count)
            elif kind in ("rowstart", "rowend"):
                target = self._row_edge(insert, end=kind == "rowend")
            else:
                rows = self._view_size()[1]
                target = self._by_row(insert, count * (rows if kind == "page" else 1))
        else:
            target = self._resolve(where)
        if extend and self._anchor is None:
            self._anchor = insert
        self._buffer.mark_set("insert", target)
        if extend and self._anchor is not None:
            self._select(self._anchor, target)
        else:
            self._anchor = None
            self._buffer.tag_remove("sel", "1.0", "end")
        self.see("insert")
        self._redraw()
        self._report_view()

    def _row_edge(self, index: Index, *, end: bool) -> Index:
        """The start or end of the display row an index is on.

        The end stops before the space that caused the wrap, which is where
        Tk puts it: the space belongs to the row but pressing End should not
        land past the last word on it.
        """
        rows = self._display_lines()
        line, start, stop = rows[self._row_of(index, rows)]
        if not end:
            return self._buffer.clamp(Index(line, start))
        text = self._buffer.lines[line - 1] if line <= len(self._buffer.lines) else ""
        while stop > start and text[stop - 1 : stop] == " ":
            stop -= 1
        return self._buffer.clamp(Index(line, stop))

    def _by_word(self, index: Index, direction: int) -> Index:
        """The start of the next or previous word, as Control-arrow moves.

        Forwards means the beginning of the word after this one, not the end
        of this one - which is what Tk does and what makes repeated presses
        walk the words rather than alternate between their two ends.
        """
        offset = self._buffer.offset_of(index)
        text = self._buffer.text
        limit = len(text) - 1
        if direction > 0:
            while offset < limit and _is_word(text[offset]):
                offset += 1
            while offset < limit and not _is_word(text[offset]):
                offset += 1
        else:
            while offset > 0 and not _is_word(text[offset - 1]):
                offset -= 1
            while offset > 0 and _is_word(text[offset - 1]):
                offset -= 1
        return self._buffer.index_of(offset)

    def _by_row(self, index: Index, distance: int) -> Index:
        """The index ``distance`` display rows away, at the same column.

        Display rows, not buffer lines: with wrapping on, Up from the middle
        of a wrapped paragraph has to go to the row above it on screen, which
        is what every editor does and what the buffer alone cannot answer.
        """
        rows = self._text_rows()
        row = self._row_of(index, rows)
        _, start, _ = rows[min(row, len(rows) - 1)]
        column = index.char - start
        target = min(max(row + distance, 0), len(rows) - 1)
        line, new_start, new_stop = rows[target]
        return self._buffer.clamp(Index(line, min(new_start + column, new_stop)))

    def _type(self, characters: str) -> None:
        """Put typed characters in, replacing the selection if there is one."""
        if not self._editable:
            return
        # A newline ends the run: undoing a paragraph should not also take
        # back the one before it.
        self._separate_if_asked("\n" if "\n" in characters else "type")
        self._delete_selection()
        insert = self._buffer.mark_index("insert") or Index(1, 0)
        self._buffer.insert(insert, characters)
        self._anchor = None
        self._after_edit()

    def _backspace(self) -> None:
        """Delete the selection, or the character before the cursor."""
        if not self._editable:
            return
        self._separate_if_asked("erase")
        if not self._delete_selection():
            insert = self._buffer.mark_index("insert") or Index(1, 0)
            start = self._buffer.index(f"{insert} -1c")
            if start == insert:
                return
            self._buffer.delete(start, insert)
        self._after_edit()

    def _delete_forward(self) -> None:
        """Delete the selection, or the character after the cursor."""
        if not self._editable:
            return
        self._separate_if_asked("erase")
        if not self._delete_selection():
            insert = self._buffer.mark_index("insert") or Index(1, 0)
            self._buffer.delete(insert)
        self._after_edit()

    # --------------------------------------------------------- display lines

    def _wrap_mode(self) -> str:
        """How long lines are broken, defaulting to Tk's ``char``."""
        mode = str(self._options["wrap"])
        return mode if mode in ("none", "char", "word") else "char"

    def _view_size(self) -> tuple[int, int]:
        """The cells the text is laid out in, as ``(width, height)``.

        Falls back to the configured width and height until the widget has
        been given a rect. Without that fallback, anything asking for the
        display lines or the view before layout wraps every line to a single
        cell - one display row per character - which makes `yview` nonsense
        and turns a large document into a very slow one.
        """
        area = self._text_area()
        if area.width > 0 and area.height > 0:
            return (area.width, area.height)
        return (
            max(1, int(self._options["width"])),
            max(1, int(self._options["height"])),
        )

    def _display_lines(self) -> list[tuple[int, int, int]]:
        """Every row the text would occupy, as ``(line, start, end)``.

        One entry per line on screen rather than per line in the buffer: with
        wrapping on, one is many of the other, and everything about scrolling
        and about Up and Down is counted in these.
        """
        width = self._view_size()[0]
        mode = self._wrap_mode()
        above, between, below = (
            _as_int(self._options[name], 0)
            for name in ("spacing1", "spacing2", "spacing3")
        )
        spaced = above > 0 or between > 0 or below > 0
        rows: list[tuple[int, int, int]] = []
        for number, line in enumerate(self._buffer.lines, start=1):
            wrapped = self._wrap_line(number, line, width, mode)
            if spaced:
                wrapped = _spaced(wrapped, above, between, below)
            rows.extend(wrapped)
        return rows or [(1, 0, 0)]

    def _text_rows(self) -> list[tuple[int, int, int]]:
        """The display rows that hold text, leaving out the spacing.

        What Up and Down count in: a blank row of ``spacing1`` is somewhere
        the view can be, not somewhere the cursor can.
        """
        return [row for row in self._display_lines() if row[0] > 0]

    def _wrap_line(
        self, number: int, line: str, width: int, mode: str
    ) -> list[tuple[int, int, int]]:
        """Break one buffer line into the rows it occupies.

        Not ``wrap_spans``, which counts CHARACTERS and assumes every row is
        the same width. Neither holds here any more:

        - a tab is as wide as the gap to its next stop, so a row has to be
          measured in columns;
        - ``lmargin2`` indents the wrapped rows and not the first, so the
          width available CHANGES from one row to the next, and ``rmargin``
          narrows them all. Measured against Tk: a hanging indent of eight
          in a forty-column widget gave a first row of 38 characters and
          later rows of 28 and 29.

        So each row asks for its own margins before it is filled, which is
        the whole reason this exists rather than a width argument.
        """
        if mode == "none" or not line:
            return [(number, 0, len(line))]
        # FAST PATH, and it is not an optimisation so much as a repair. With
        # no margins and no tab in the line, a character is a cell and every
        # row is the same width - exactly what wrap_spans assumes - so the
        # arithmetic below is not needed and must not be paid for.
        #
        # Measured: without this, 5000 short lines cost a string slice, a
        # list allocation and a Python loop EACH, on every _display_lines
        # call. On Python 3.14 that was +1.5% and invisible; on 3.10 and
        # 3.11 it took the repaint from under 100ms to 146 and 132, and CI
        # failed on those two versions while the other three passed.
        # TkCurses-a0u covers the headroom that made it fatal rather than
        # merely slower.
        if not self._margined and "\t" not in line:
            return [
                (number, start, stop) for start, stop in wrap_spans(line, width, mode)
            ]
        style = str(self._options["tabstyle"])
        rows: list[tuple[int, int, int]] = []
        start = 0
        while True:
            left, right = self._row_margins(number, start)
            room = max(1, width - left - right)
            stop = self._fits(line, start, left, room, style)
            if mode == "word" and stop < len(line):
                cut = line.rfind(" ", start, stop)
                if cut > start:
                    stop = cut + 1
            rows.append((number, start, stop))
            if stop >= len(line):
                return rows
            if stop <= start:  # A single character wider than the row.
                rows[-1] = (number, start, start + 1)
                stop = start + 1
            start = stop

    def _fits(self, line: str, start: int, left: int, room: int, style: str) -> int:
        """How much of ``line`` from ``start`` fits in ``room`` columns.

        Walks and stops at the edge rather than laying the whole remainder
        out and then reading it: the first version built a column for every
        character after ``start``, once per row, which is quadratic in the
        length of a line and was wasted work even when it was affordable.
        """
        edge = left + room
        column = left
        tab = 0
        for offset in range(start, len(line)):
            if column >= edge:
                return offset
            if line[offset] != "\t":
                column += 1
                continue
            number = self._stops.index_after(column) if style == WORDPROCESSOR else tab
            target = self._stops.nth(number)
            column = target if target > column else column + 1
            tab += 1
        return len(line)

    def _row_of(
        self, index: Index, rows: list[tuple[int, int, int]] | None = None
    ) -> int:
        """Which display row an index falls on."""
        return self._display_position(index, rows)[0]

    def _display_position(
        self, index: Index, rows: list[tuple[int, int, int]] | None = None
    ) -> tuple[int, int]:
        """Where an index sits, as ``(row, column within that row)``."""
        rows = self._display_lines() if rows is None else rows
        # A wrap boundary belongs to both rows: it is the end of one and the
        # start of the next. It has to resolve to the *later* one, or the
        # cursor is drawn one cell past the end of the row above - painting
        # the first character of the next row there into the bargain.
        for row, (line, start, stop) in enumerate(rows):
            if line == index.line and start <= index.char < stop:
                return row, self._column_in(line, start, stop, index.char)
        # Nothing contains it, so it is at the end of a line: the last row of
        # that line is where it goes.
        for row, (line, start, stop) in enumerate(rows):
            if line == index.line and index.char == stop:
                return row, self._column_in(line, start, stop, index.char)
        # `end` on a buffer whose last line has text is a line past every
        # display row, so it has none of its own; it belongs at the end of
        # the last one. Without this the cursor came back at column 0 and
        # blanked the first character of the bottom line.
        last = max(0, len(rows) - 1)
        while last > 0 and rows[last][0] < 0:
            last -= 1
        line, start, stop = rows[last]
        return last, self._column_in(line, start, stop, stop)

    def _margin_at(self, line: int, start: int, option: str) -> int:
        """A margin in cells, from the tags covering a display line's start.

        Tk decides by "the first non-elided character of the display line",
        not by the tag under the cursor and not by any tag overlapping the
        row - measured: a tag added from part way through the first row
        still indents the wrapped row below it, because that row's first
        character is inside the tag.

        The last tag in the raise order wins, which is how tag priority
        works everywhere else in this widget.
        """
        value = 0
        at = Index(line, start)
        covering = set(self._buffer.tag_names(at))
        for name in self._tag_order:
            if name not in covering:
                continue
            setting = self._tag_options.get(name, {}).get(option)
            if setting not in (None, ""):
                value = round(self.winfo_fpixels(cast("str | int | float", setting)))
        return max(0, value)

    def _row_margins(self, line: int, start: int) -> tuple[int, int]:
        """The left and right margins of one display row, in cells.

        ``start == 0`` is what makes a row the FIRST of its text line, which
        is the whole difference between lmargin1 and lmargin2: the first
        display line takes lmargin1 and every wrapped one takes lmargin2.
        """
        if not self._margined:
            return 0, 0
        left = self._margin_at(line, start, "lmargin1" if start == 0 else "lmargin2")
        return left, self._margin_at(line, start, "rmargin")

    def _row_text(self, line: int, start: int, stop: int) -> str:
        """The characters one display row holds."""
        lines = self._buffer.lines
        return lines[line - 1][start:stop] if line <= len(lines) else ""

    def _column_in(self, line: int, start: int, stop: int, char: int) -> int:
        """Which column of its row a character sits in.

        Was ``char - start`` until tabs existed, and still is for a row
        without any: a character is a cell everywhere else in this library.
        A tab is the exception, so the answer comes from the layout rather
        than from arithmetic - TkCurses-wy7.
        """
        text = self._row_text(line, start, stop)
        left, _ = self._row_margins(line, start)
        if "\t" not in text:
            return left + char - start
        return column_of(
            text,
            char - start,
            start=left,
            stops=self._stops,
            style=str(self._options["tabstyle"]),
        )

    def _index_at_cell(self, x: int, y: int) -> Index:
        """The index at a cell within this widget, for a click or ``@x,y``."""
        area = self._text_area()
        rows = self._display_lines()
        row = min(max(self._top + (y - area.y), 0), len(rows) - 1)
        line, start, stop = rows[row]
        # Spacing belongs to the row beside it, measured: with spacing1 and
        # spacing3 of 16 pixels, every y from 2 to 40 answers 1.0 in Tk.
        line = abs(line)
        column = max(0, x - area.x) + self._left
        left, _ = self._row_margins(line, start)
        offset = char_at(
            self._row_text(line, start, stop),
            column,
            start=left,
            stops=self._stops,
            style=str(self._options["tabstyle"]),
        )
        return self._buffer.clamp(Index(line, min(start + offset, stop)))

    # --------------------------------------------------------------- the view

    def see(self, index: Any) -> None:
        """Scroll the least that puts an index on screen, both directions."""
        target = self._resolve(index)
        width, height = self._view_size()
        rows = self._display_lines()
        row = self._row_of(target, rows)
        if row < self._top:
            self._top = row
        elif row >= self._top + height:
            self._top = row - height + 1
        if self._wrap_mode() == "none":
            if target.char < self._left:
                self._left = target.char
            elif target.char > self._left + width - 1:
                self._left = target.char - width + 1
        self._top = max(0, min(self._top, max(0, len(rows) - 1)))
        self._left = max(0, self._left)
        # A scrollbar cannot know the view moved unless it is told, and see()
        # is the one thing that moves it without going through _scroll.
        self._report_view()

    def _clamp_view(self) -> None:
        """Keep the view inside the text after anything that could move it."""
        rows = len(self._display_lines())
        self._top = max(0, min(self._top, max(0, rows - 1)))
        if self._wrap_mode() != "none":
            self._left = 0

    def yview(self, *args: Any) -> tuple[float, float] | None:
        """Read or move the vertical view, in the shape Tk uses.

        With no arguments returns ``(first, last)`` as fractions, which is
        what a Scrollbar's ``set`` wants. Otherwise takes ``("moveto", f)`` or
        ``("scroll", n, "units"|"pages")``, which is what a Scrollbar sends.
        """
        if not args:
            return self._view_fractions()
        self._scroll(args, vertical=True)
        return None

    def xview(self, *args: Any) -> tuple[float, float] | None:
        """Read or move the horizontal view, in the same shape."""
        if not args:
            return self._horizontal_fractions()
        self._scroll(args, vertical=False)
        return None

    def _scroll(self, args: tuple[Any, ...], *, vertical: bool) -> None:
        """Apply one Tk scrolling command to one axis."""
        view = self._view_size()
        span = view[1] if vertical else view[0]
        total = (
            len(self._display_lines())
            if vertical
            else max(1, max((len(line) for line in self._buffer.lines), default=1))
        )
        current = self._top if vertical else self._left
        action = str(args[0])
        if action == "moveto":
            current = int(float(args[1]) * total)
        elif action == "scroll":
            count = int(float(args[1]))
            unit = str(args[2]) if len(args) > 2 else "units"
            current += count * (span if unit.startswith("page") else 1)
        else:
            raise TclError(f'bad option "{action}": must be moveto or scroll')
        limit = max(0, total - (span if vertical else 0))
        if vertical:
            self._top = max(0, min(current, limit))
        else:
            self._left = max(0, min(current, max(0, total - span)))
        self._redraw()
        self._report_view()

    def _view_fractions(self) -> tuple[float, float]:
        """Where the vertical view is, as two fractions of the whole."""
        total = max(1, len(self._display_lines()))
        height = self._view_size()[1]
        return (
            min(1.0, self._top / total),
            min(1.0, (self._top + height) / total),
        )

    def _horizontal_fractions(self) -> tuple[float, float]:
        """Where the horizontal view is, as two fractions of the longest line."""
        total = max(1, max((len(line) for line in self._buffer.lines), default=1))
        width = self._view_size()[0]
        return (
            min(1.0, self._left / total),
            min(1.0, (self._left + width) / total),
        )

    def _report_scroll_view(self) -> None:
        """A resize changes how much is visible, so the scrollbar is retold."""
        self._report_view()

    def _report_view(self) -> None:
        """Tell the scrollbars where the view is, if anything is listening."""
        for option, fractions in (
            ("yscrollcommand", self._view_fractions()),
            ("xscrollcommand", self._horizontal_fractions()),
        ):
            command = self._options[option]
            if command is not None:
                command(*fractions)

    # -------------------------------------------------------------- painting

    def _text_area(self) -> Rect:
        """Where the text goes, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _redraw(self) -> None:
        """Paint the border, the visible rows, their tags, and the cursor."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._in_state(
            self._background_attribute() | self._font_attribute()
        )
        area = self._text_area()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if area.is_empty:
                return
            rows = self._display_lines()
            lines = self._buffer.lines
            for offset in range(area.height):
                row = self._top + offset
                if row >= len(rows):
                    break
                self._draw_row(
                    dispatcher, window, area, offset, rows[row], lines, attribute
                )
            self._draw_cursor(dispatcher, window, area, rows, attribute)

    def _draw_row(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        offset: int,
        span: tuple[int, int, int],
        lines: list[str],
        attribute: int,
    ) -> None:
        """Draw one display row, then whatever tags cover part of it."""
        line, start, stop = span
        if line < 0:
            return
        text = lines[line - 1][start:stop] if line <= len(lines) else ""
        left, _ = self._row_margins(line, start)
        # Built so that an index into this string IS a column: the margin as
        # leading blanks, then the drawn form of the text. A tab is the gap
        # it spans - handing a raw one to curses is what made every widget
        # disagree with its own arithmetic (TkCurses-zrm).
        if "\t" in text:
            text = render(
                text,
                start=left,
                stops=self._stops,
                style=str(self._options["tabstyle"]),
            )
        text = " " * left + text
        self._draw_margin(dispatcher, window, area, offset, span, left)
        visible = text[self._left : self._left + area.width]
        self._write_line(
            dispatcher, window, area.y + offset, area.x, visible, attribute
        )
        for name in self._tag_order:
            self._draw_tagged(
                dispatcher, window, area, offset, span, visible, name, attribute
            )

    def _draw_margin(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        offset: int,
        span: tuple[int, int, int],
        left: int,
    ) -> None:
        """Paint the cells an indent leaves empty, if a tag asks for it.

        Tk's ``-lmargincolor``: "the background color to use in regions that
        do not contain characters because they are indented". There is no
        text there to carry the colour, so it is written as blanks.
        """
        line, start, _ = span
        if left <= 0 or self._left >= left:
            return
        colour = ""
        covering = set(self._buffer.tag_names(Index(line, start)))
        for name in self._tag_order:
            if name in covering:
                setting = self._tag_options.get(name, {}).get("lmargincolor")
                if setting:
                    colour = str(setting)
        if not colour:
            return
        colors = self.tk.colors
        if colors is None:
            return
        attribute = colors.attribute_for(
            str(self._options["foreground"] or "white"), colour
        )
        width = min(left - self._left, area.width)
        self._write_line(
            dispatcher, window, area.y + offset, area.x, " " * width, attribute
        )

    def _draw_tagged(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        offset: int,
        span: tuple[int, int, int],
        visible: str,
        name: str,
        attribute: int,
    ) -> None:
        """Redraw the parts of one row that a tag covers.

        Drawn over the plain text rather than worked out per character before
        anything is written: tags overlap, and painting them in priority order
        is what makes the topmost one win without having to resolve the whole
        stack up front.
        """
        line, start, _ = span
        tagged = self._tag_attribute(name)
        if tagged is None:
            return
        first = start + self._left
        for column, character in enumerate(visible):
            at = Index(line, first + column)
            if name not in self._buffer.tag_names(at):
                continue
            self._write_line(
                dispatcher,
                window,
                area.y + offset,
                area.x + column,
                character,
                with_colors(attribute, tagged & _curses.A_COLOR)
                | (tagged & ~_curses.A_COLOR),
            )

    def _tag_attribute(self, name: str) -> int | None:
        """What a tag does to the cells it covers, or None if nothing.

        ``sel`` is the selection, drawn by ``_selected_text_attribute``.
        """
        options = self._tag_options.get(name)
        if options is None:
            return None
        attribute = 0
        font = str(options.get("font", "")).lower()
        attribute |= from_font(
            bold="bold" in font,
            italic="italic" in font,
            underline="underline" in font or bool(options.get("underline")),
        )
        foreground, background = options.get("foreground"), options.get("background")
        if name == "sel":
            return self._selected_text_attribute(attribute, foreground, background)
        colors = self.tk.colors
        if colors is not None and (foreground or background):
            attribute |= colors.attribute_for(
                str(foreground or self._options["foreground"] or "white"),
                str(background or self._options["background"] or "black"),
            )
        return attribute or None

    def _selected_text_attribute(
        self, attribute: int, foreground: Any, background: Any
    ) -> int | None:
        """What the ``sel`` tag does: the select colours, else reversed.

        Without the focus, ``inactiveselectbackground`` takes the background's
        place, as in Tk, and a ``""`` a program gave it hides the selection.
        The ``""`` it starts at does not: that one is the terminal's own look,
        the same as with the focus (TkCurses-gm66.3, and ``_TerminalsOwn``).
        """
        if self.focus_get() is not self:
            inactive = self._options["inactiveselectbackground"]
            if inactive == "" and not isinstance(inactive, _TerminalsOwn):
                return None
            if inactive:
                background = inactive
        return self._selection_attribute(attribute, foreground or "", background or "")

    def _draw_cursor(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        rows: list[tuple[int, int, int]],
        attribute: int,
    ) -> None:
        """Note where typing will go, while the widget has the focus.

        Noted for the terminal's own cursor rather than painted as a reversed
        cell, which could not be told from a selection - see Entry's
        ``_draw_cursor`` and TkCurses-lw2.
        """
        del dispatcher, window, attribute
        self._insert_at = None
        if self.focus_get() is not self:
            return
        insert = self._buffer.mark_index("insert")
        if insert is None:
            return
        at, within = self._display_position(insert, rows)
        row = at - self._top
        if not 0 <= row < area.height:
            return
        column = within - self._left
        if not 0 <= column < area.width:
            return
        self._insert_at = (
            self.winfo_rooty() + area.y + row,
            self.winfo_rootx() + area.x + column,
        )

    def _insert_cell(self) -> tuple[int, int] | None:
        return self._insert_at


#: Keys that move the insert cursor without changing anything, and what they
#: mean as an index expression or as a display-line movement.
_TEXT_MOTION: dict[str, Any] = {
    "Left": "insert -1c",
    "Right": "insert +1c",
    # Home and End move within the *display* line, not the logical one: on a
    # wrapped paragraph they go to the beginning and end of the row on
    # screen. Checked against Tk 9.0.2, which answers 1.17 for Home pressed
    # at 1.20 on a line whose second row starts there.
    "Home": ("rowstart", 0),
    "End": ("rowend", 0),
    "Prior": ("page", -1),
    "Next": ("page", 1),
    "Up": ("row", -1),
    "Down": ("row", 1),
}

#: The same keys with Control held, which in Tk move by word and to the ends
#: of the whole document rather than of a line.
_TEXT_CONTROL_MOTION: dict[str, Any] = {
    "Home": "1.0",
    "End": "end -1c",
    "Left": ("word", -1),
    "Right": ("word", 1),
}


def _is_word(character: str) -> bool:
    """True for the characters Tk counts as part of a word."""
    return character.isalnum() or character == "_"


def _text_key(event: Event) -> str | None:
    """Handle one key in a Text.

    Returns ``"break"`` for keys the widget consumed, so a Left arrow moving
    the cursor does not also reach whatever else is bound to it. Tab is left
    alone deliberately: a widget that swallowed it would trap the focus, and
    a terminal user with no mouse would have nowhere to go.
    """
    text = event.widget
    keysym = event.keysym
    extend = bool(event.state & MOD_SHIFT)

    if event.state & MOD_CTRL and keysym in _TEXT_CONTROL_MOTION:
        text._move(_TEXT_CONTROL_MOTION[keysym], extend=extend)
        return "break"
    if keysym in _TEXT_MOTION:
        text._move(_TEXT_MOTION[keysym], extend=extend)
        return "break"
    if keysym == "BackSpace":
        text._backspace()
        return "break"
    if keysym == "Delete" and not event.state & MOD_SHIFT:
        text._delete_forward()
        return "break"
    if keysym == "Return":
        text._type("\n")
        return "break"
    if keysym == "Tab":
        return None
    if len(event.char) == 1 and event.char.isprintable():
        text._type(event.char)
        return "break"
    return None


# ---------------------------------------------------- the clipboard, on a Text
#
# The same rules as an Entry's (see _entry_copy), measured on Tk 9.0.2's Text:
# copy the "sel" range; cut is copy then delete, and a disabled Text still
# copies; paste replaces the selection (a deliberate departure from Linux Tk,
# see _entry_paste); select-all tags 1.0 to end and leaves the cursor.
# TkCurses-lw2.
#
# insert() and delete() ignore a disabled Text themselves (TkCurses-aah), but
# the handlers still ask first: a cut must know whether to delete after
# copying, and a paste must not move the cursor on its way to being refused.


def _text_selected(text: Any) -> tuple[str, str, str] | None:
    """The selection as ``(first, last, text)``, or None with nothing selected."""
    ranges = text.tag_ranges("sel")
    if not ranges:
        return None
    first, last = str(ranges[0]), str(ranges[1])
    return (first, last, str(text.get(first, last)))


def _text_writable(text: Any) -> bool:
    return str(text.cget("state")) != "disabled"


def _text_copy(event: Event) -> None:
    """Put the selection on the clipboard."""
    selected = _text_selected(event.widget)
    if selected is not None:
        event.widget.clipboard_clear()
        event.widget.clipboard_append(selected[2])


def _text_cut(event: Event) -> None:
    """Copy the selection, then delete it unless the Text is disabled."""
    text = event.widget
    selected = _text_selected(text)
    if selected is None:
        return
    text.clipboard_clear()
    text.clipboard_append(selected[2])
    if _text_writable(text):
        text.delete(selected[0], selected[1])
        text.see("insert")


def _text_paste(event: Event) -> None:
    """Insert the clipboard at the insert mark, replacing any selection.

    Classic Tk on Linux keeps the selection; on Windows and macOS it deletes
    it first, and this does too - a deliberate departure, as for Entry.
    TkCurses-lw2.
    """
    text = event.widget
    if not _text_writable(text):
        return
    try:
        data = text.clipboard_get()
    except TclError:
        return
    selected = _text_selected(text)
    if selected is not None:
        text.mark_set("insert", selected[0])
        text.delete(selected[0], selected[1])
    text.insert("insert", data)
    text.see("insert")


def _text_clear(event: Event) -> None:
    """Delete the selection."""
    selected = _text_selected(event.widget)
    if selected is not None and _text_writable(event.widget):
        event.widget.delete(selected[0], selected[1])


def _text_select_all(event: Event) -> None:
    """Select everything; the insert mark stays where it was."""
    event.widget.tag_add("sel", "1.0", "end")


def _text_paste_selection(event: Event) -> None:
    """Insert PRIMARY where the middle button was released."""
    text = event.widget
    if not _text_writable(text):
        return
    text.mark_set("insert", f"@{event.x},{event.y}")
    try:
        data = text.selection_get()
    except TclError:
        return
    text.insert("insert", data)
    text.focus_set()
    text.see("insert")


def _text_press(event: Event) -> None:
    """Take the focus, put the cursor where the click was, and start a drag."""
    text = event.widget
    text.focus_set()
    text._separate_if_asked(None)
    index = text._index_at_cell(event.x, event.y)
    text._buffer.mark_set("insert", index)
    text._buffer.mark_set("current", index)
    text._anchor = index
    _text_start_drag(text, "char", event.x)
    text._select(index, index)
    text._redraw()


# -------------------------------------------- selecting with the mouse, Text
#
# Tk's Text bindings, READ from the running interpreter - bind_class Text and
# the bodies of tk::TextButton1, tk::TextSelectTo, tk::TextResetAnchor,
# tk::TextAutoScan, tk::TextPrevPos and tk::TextNextPos - and the selections
# MEASURED on Tk 9.0.2 by calling them (TkCurses-svtr):
#
# * a double-click selects the run around the pointer, as an Entry's does,
#   except that a run can cross lines - a newline is not a word character,
#   so "foo  \n  bar" double-clicked in the spaces selects "  \n  ". The
#   cursor goes to the START of it, where an Entry's goes to the end.
# * a triple-click selects the line with its newline.
# * a drag after either extends a word or a line at a time.
# * Shift-click moves whichever end of the selection Tk's
#   tk::TextResetAnchor picks - the far end from the pointer, decided by
#   character count - and selects from there to the pointer.
# * a drag past the top or bottom scrolls, one line more than the pointer
#   is past the edge, every 50ms; past either side, two columns.


def _text_start_drag(text: Any, mode: str, x: int) -> None:
    """Begin a press: what a drag extends by, and nothing moved yet."""
    _cancel_autoscan(text)
    text._select_mode = mode
    text._moved = False
    text._press_x = x
    text._dragging = True


def _text_select_to(text: Any, x: int, y: int) -> None:
    """Select from the anchor to the pointer by the mode - ``tk::TextSelectTo``.

    The anchor is taken to have right gravity, the pointer being on a
    character rather than between two: the word or line it is IN.
    """
    buffer = text._buffer
    # Held to the visible cells, as Tk's @x,y is: past an edge means the edge.
    # The autoscroll moves the view; this only says where in it. See
    # _entry_index_at for what went wrong without it.
    area = text._text_area()
    x = min(max(x, area.x), area.x + max(area.width - 1, 0))
    y = min(max(y, area.y), area.y + max(area.height - 1, 0))
    cur = text._index_at_cell(x, y)
    if text._anchor is None:
        text._anchor = cur
    anchor = text._anchor
    if cur != anchor or x != text._press_x:
        text._moved = True
    mode = text._select_mode
    if mode == "char":
        first, last = min(anchor, cur), max(anchor, cur)
    elif mode == "word":
        whole = buffer.text
        first_at = buffer.offset_of(anchor)
        last_at = min(first_at + 1, len(whole))
        here = buffer.offset_of(cur)
        if here < first_at:
            first_at = here
        elif here > last_at:
            last_at = here
        first = buffer.index_of(run_start(whole, first_at))
        last = buffer.index_of(run_end(whole, last_at - 1))
    else:
        first, last = Index(anchor.line, 0), Index(anchor.line + 1, 0)
        if cur < first:
            first = Index(cur.line, 0)
        elif cur >= last:
            last = Index(cur.line + 1, 0)
        last = min(last, buffer.end())
    if text._moved or mode != "char":
        buffer.mark_set("insert", cur)
        text._select(first, last)
    text.see("insert")
    text._redraw()
    text._report_view()


def _text_control_click(event: Event) -> None:
    """Move the insert mark to the pointer and leave the selection alone.

    Tk's ``<Control-Button-1>``: ``mark set insert @%x,%y``, and an undo
    separator when ``-autoseparators`` is on, because "an operation that
    moves the insert mark without making it one end of the selection must
    insert an autoseparator" (Tk's own comment, text.tcl). The focus does not
    move and no drag follows. TkCurses-mndh.
    """
    text = event.widget
    _cancel_autoscan(text)
    text._dragging = False
    text._separate_if_asked(None)
    text._buffer.mark_set("insert", text._index_at_cell(event.x, event.y))
    text.see("insert")
    text._redraw()


def _do_nothing(event: Event) -> None:
    """A binding that does nothing, to stand in front of a less specific one."""
    del event


def _text_double(event: Event) -> None:
    """Select the word under the pointer, the cursor at its start."""
    text = event.widget
    _text_start_drag(text, "word", event.x)
    _text_select_to(text, event.x, event.y)
    _text_cursor_to_selection(text)


def _text_triple(event: Event) -> None:
    """Select the line under the pointer and its newline."""
    text = event.widget
    _text_start_drag(text, "line", event.x)
    _text_select_to(text, event.x, event.y)
    _text_cursor_to_selection(text)


def _text_cursor_to_selection(text: Any) -> None:
    """Put the cursor at the start of the selection, as Tk's binding does."""
    found = text._selection_range()
    if found is not None:
        text._buffer.mark_set("insert", found[0])
        text._redraw()


def _text_shift_press(event: Event) -> None:
    """Extend from whichever end ``tk::TextResetAnchor`` keeps, to the pointer."""
    text = event.widget
    _text_reset_anchor(text, text._index_at_cell(event.x, event.y))
    text._select_mode = "char"
    text._dragging = True
    _text_select_to(text, event.x, event.y)


def _text_reset_anchor(text: Any, at: Index) -> None:
    """Make the end of the selection farther from ``at`` the anchor.

    ``tk::TextResetAnchor``, ported with its quirk: its test for a selection
    spanning few lines compares the first line with the LAST plus two, which
    always holds, so the choice is always made by counting characters - the
    nearer end moves when the click is inside. With nothing selected the
    anchor stays where the last click left it, so a click then a shift-click
    selects between the two (Tk's comment cites its bug 5929).
    """
    found = text._selection_range()
    if found is None:
        return
    first, last = found
    if at < first:
        text._anchor = last
        return
    if at > last:
        text._anchor = first
        return
    total = len(text._buffer.get(first, last))
    if total <= 2:
        return
    before = len(text._buffer.get(first, at))
    text._anchor = last if before < total // 2 else first


def _text_double_shift(event: Event) -> None:
    """Extend the selection from the anchor by whole words."""
    text = event.widget
    text._select_mode = "word"
    text._dragging = True
    _text_select_to(text, event.x, event.y)


def _text_triple_shift(event: Event) -> None:
    """Extend the selection from the anchor by whole lines."""
    text = event.widget
    text._select_mode = "line"
    text._dragging = True
    _text_select_to(text, event.x, event.y)


def _text_motion(event: Event) -> None:
    """Extend the selection to the pointer while a drag is going on."""
    text = event.widget
    if not text._dragging:
        return
    text._drag_at = (event.x, event.y)
    _text_select_to(text, event.x, event.y)
    outside = not (
        0 <= event.x < text.winfo_width() and 0 <= event.y < text.winfo_height()
    )
    if outside:
        if text._autoscan is None:
            text._autoscan = text.after(50, lambda: _text_autoscan(text))
    else:
        _cancel_autoscan(text)


def _text_autoscan(text: Any) -> None:
    """Scroll towards the pointer and select to it, every 50ms - ``tk::TextAutoScan``.

    Tk scrolls ``1 + y - height`` PIXELS past the bottom; a row is the unit
    here, and one row below a Text is roughly one line of Tk's, so it scrolls
    a line more than the pointer is past the edge.
    """
    text._autoscan = None
    if not text._dragging or not text.winfo_exists():
        return
    x, y = text._drag_at
    height, width = text.winfo_height(), text.winfo_width()
    if y >= height:
        text.yview("scroll", 1 + y - height, "units")
    elif y < 0:
        text.yview("scroll", -1 + y, "units")
    elif x >= width:
        text.xview("scroll", 2, "units")
    elif x < 0:
        text.xview("scroll", -2, "units")
    else:
        return
    _text_select_to(text, x, y)
    text._autoscan = text.after(50, lambda: _text_autoscan(text))


def _text_release(event: Event) -> None:
    """Stop dragging, wherever the pointer ended up."""
    event.widget._dragging = False
    _cancel_autoscan(event.widget)


def _text_wheel(event: Event) -> None:
    """Scroll the view without moving the cursor, as a wheel should."""
    event.widget.yview("scroll", -event.delta * 3, "units")


def _text_refresh(event: Event) -> None:
    """Repaint after the focus moved in or out."""
    event.widget._redraw()


@dataclass
class _CanvasItem:
    """One thing drawn on a Canvas.

    Attributes:
        ident: The number ``create_*`` returned, and the item's first tag.
        kind: ``line``, ``rectangle``, ``oval``, ``polygon`` or ``text``.
        coords: Pixel coordinates, flat, as Tk passes them.
        options: Everything else, already checked against the type's options.
    """

    ident: int
    kind: str
    coords: list[int]
    options: dict[str, Any]

    @property
    def tags(self) -> tuple[str, ...]:
        """The item's tags, as a tuple however they were given."""
        tags = self.options.get("tags") or ()
        if isinstance(tags, str):
            return tuple(tags.split())
        return tuple(str(tag) for tag in tags)

    def points(self) -> list[tuple[int, int]]:
        """The coordinates as pairs."""
        return list(zip(self.coords[::2], self.coords[1::2], strict=False))


class Canvas(_Drawable, XView, YView):
    """A drawing surface, measured in half-cells.

    A character cell is about twice as tall as it is wide, so a canvas that
    treated one cell as one unit would draw every circle as a tall ellipse.
    This one is a plane of **half-cells** instead - ``▀`` and ``▄`` divide a
    cell across the middle, and each half is very nearly square - so a circle
    is a circle. :mod:`tkcurses._core.canvas` does the drawing and the
    folding of pixel pairs into cells.

    Two coordinate systems therefore meet on this widget, and only one of
    them is Tk's:

    - ``width`` and ``height`` are in **cells**, like every other widget
      here. Pixel dimensions have no cell equivalent and are left out rather
      than accepted and ignored.
    - Item coordinates are in **pixels**: one cell wide, half a cell tall. A
      canvas 40 cells by 10 is a plane 40 pixels by 20.

    Text is the one thing that cannot live on that plane: a glyph occupies a
    whole cell. A text item therefore snaps to the nearest cell row, and
    while it is on top nothing else can share those cells - which is what you
    want for a label on a diagram, and worth knowing before putting one in
    the middle of a drawing.
    """

    #: What each kind of item accepts, on top of the options every item has.
    #: Deliberately smaller than Tk's: dashes, stipples, arrowheads and line
    #: widths have no meaning in a grid of characters, so asking for one
    #: fails rather than quietly doing nothing.
    _COMMON_ITEM_OPTIONS: ClassVar[dict[str, Any]] = {
        "state": "normal",
        "tags": (),
    }
    _ITEM_OPTIONS: ClassVar[dict[str, dict[str, Any]]] = {
        "line": {"fill": "white"},
        "rectangle": {"fill": "", "outline": "white"},
        "oval": {"fill": "", "outline": "white"},
        "polygon": {"fill": "white", "outline": ""},
        "text": {
            "anchor": "center",
            "fill": "white",
            "font": "",
            "justify": "left",
            "text": "",
        },
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_INSERT_CURSOR_OPTIONS,
        **_SELECTION_OPTIONS,
        "selectborderwidth": 1,  # Tk's default on a Canvas alone
        # How far from an item's ink still counts as being on it. Tk's
        # default is 1, and a terminal needs it more than Tk does: a thin
        # outline is one pixel wide and a click only names a whole cell.
        "closeenough": 1,
        "height": 10,
        "relief": "sunken",
        "scrollregion": None,
        "state": "normal",
        "takefocus": False,
        "width": 40,
        "xscrollcommand": None,
        "yscrollcommand": None,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``width`` and ``height`` in cells, ``scrollregion``,
                ``xscrollcommand``, ``yscrollcommand``, and the standard
                options.
        """
        self._items: list[_CanvasItem] = []
        self._ids = itertools.count(1)
        self._left = 0
        self._top = 0
        self._item_bindings: dict[str, dict[str, list[Callable[[Event], Any]]]] = {}
        self._current: int | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Route mouse events to whichever item is under the pointer."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        for sequence in (
            "<Button-1>",
            "<ButtonRelease-1>",
            "<Motion>",
            "<Double-Button-1>",
        ):
            self.bind_class(name, sequence, _canvas_mouse)

    # --------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if {"width", "height"} & set(given):
            self._apply_requested_size()
            self._invalidate_layout()
        self._redraw()
        self._report_view()
        return result

    config = configure

    def _apply_requested_size(self) -> None:
        """Ask for the configured cells, plus border and padding."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            int(self._options["width"]) + 2 * int(self._options["padx"]) + edge,
            int(self._options["height"]) + 2 * int(self._options["pady"]) + edge,
        )

    def _plane_size(self) -> tuple[int, int]:
        """The visible plane, in pixels, falling back to the options.

        Before the widget is laid out its area is nothing, and a canvas asked
        what it can show would answer nothing - so scrolling and ``bbox``
        would both be wrong until the first paint.
        """
        area = self._text_area()
        if area.width > 0 and area.height > 0:
            return (area.width, area.height * 2)
        return (
            max(1, int(self._options["width"])),
            max(1, int(self._options["height"])) * 2,
        )

    def _text_area(self) -> Rect:
        """Where the drawing goes, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    # ----------------------------------------------------------- making items

    def create_line(self, *args: Any, **kw: Any) -> int:
        """Draw a run of connected straight segments. Returns the item id."""
        return self._create("line", args, kw, least=2)

    def create_rectangle(self, *args: Any, **kw: Any) -> int:
        """Draw a rectangle from two opposite corners."""
        return self._create("rectangle", args, kw, least=2, exactly=2)

    def create_oval(self, *args: Any, **kw: Any) -> int:
        """Draw the ellipse inscribed in the rectangle given by two corners."""
        return self._create("oval", args, kw, least=2, exactly=2)

    def create_polygon(self, *args: Any, **kw: Any) -> int:
        """Draw a closed shape through three or more points."""
        return self._create("polygon", args, kw, least=3)

    def create_text(self, *args: Any, **kw: Any) -> int:
        """Draw a string at a point, snapped to the nearest cell row."""
        return self._create("text", args, kw, least=1, exactly=1)

    def _create(
        self,
        kind: str,
        args: tuple[Any, ...],
        options: dict[str, Any],
        *,
        least: int,
        exactly: int | None = None,
    ) -> int:
        """Make an item of one kind, checking its coordinates and options.

        Raises:
            TclError: If there are too few points, the wrong number of them,
                or an option the item does not take.
        """
        options = _given(None, options)
        coords = _canvas_coords(args)
        points = len(coords) // 2
        if points < least or (exactly is not None and points != exactly):
            raise TclError(f"wrong # coordinates: expected {exactly or least}")
        item = _CanvasItem(
            ident=next(self._ids),
            kind=kind,
            coords=coords,
            options=self._checked_item_options(kind, options),
        )
        self._items.append(item)
        self._redraw()
        return item.ident

    def _checked_item_options(self, kind: str, given: dict[str, Any]) -> dict[str, Any]:
        """Resolve an item's options against what its type accepts.

        Raises:
            TclError: If an option is not one the type takes.
        """
        spec = {**self._COMMON_ITEM_OPTIONS, **self._ITEM_OPTIONS[kind]}
        options = dict(spec)
        for name, value in given.items():
            option = _OPTION_ALIASES.get(name, name)
            if option not in spec:
                raise TclError(f'unknown option "-{name}"')
            options[option] = value
        return options

    # ----------------------------------------------------------- finding them

    def _item(self, ident: int) -> _CanvasItem | None:
        """One item by id, or None if it has been deleted."""
        return next((item for item in self._items if item.ident == ident), None)

    def _matching(self, spec: Any) -> list[_CanvasItem]:
        """Every item a tag, an id, or ``all`` names, in display order."""
        if isinstance(spec, int):
            item = self._item(spec)
            return [item] if item is not None else []
        tag = str(spec)
        if tag == "all":
            return list(self._items)
        if tag == "current":
            # Tk's dynamic tag for whatever the pointer is over. It is not
            # stored on the item, so gettags() does not report it - the one
            # place this differs from Tk, and the alternative is gettags
            # returning a tag nobody set.
            item = None if self._current is None else self._item(self._current)
            return [item] if item is not None else []
        if tag.isdigit():
            item = self._item(int(tag))
            return [item] if item is not None else []
        return [item for item in self._items if tag in item.tags]

    def find_all(self) -> tuple[int, ...]:
        """Every item, in the order they are drawn."""
        return tuple(item.ident for item in self._items)

    def find_withtag(self, spec: Any) -> tuple[int, ...]:
        """Every item a tag or an id names."""
        return tuple(item.ident for item in self._matching(spec))

    def find_overlapping(self, x0: int, y0: int, x1: int, y1: int) -> tuple[int, ...]:
        """Every item whose extent meets a rectangle."""
        left, right = sorted((int(x0), int(x1)))
        top, bottom = sorted((int(y0), int(y1)))
        found = []
        for item in self._items:
            box = self._item_bbox(item)
            if box is None:
                continue
            if (
                box[0] <= right
                and box[2] >= left
                and box[1] <= bottom
                and box[3] >= top
            ):
                found.append(item.ident)
        return tuple(found)

    def find_closest(self, x: int, y: int) -> tuple[int, ...]:
        """The item nearest a point, or nothing if the canvas is empty.

        Distance is measured to the item's extent rather than to its ink,
        which is Tk's own approximation for everything but a line.
        """
        best: tuple[float, int] | None = None
        for item in self._items:
            box = self._item_bbox(item)
            if box is None:
                continue
            near_x = min(max(int(x), box[0]), box[2])
            near_y = min(max(int(y), box[1]), box[3])
            distance = (near_x - int(x)) ** 2 + (near_y - int(y)) ** 2
            if best is None or distance <= best[0]:
                best = (distance, item.ident)
        return () if best is None else (best[1],)

    # ------------------------------------------------------------ changing them

    def coords(self, spec: Any, *args: Any) -> list[int] | None:
        """Read or replace an item's coordinates."""
        items = self._matching(spec)
        if not args:
            return list(items[0].coords) if items else []
        coords = _canvas_coords(args)
        for item in items:
            item.coords = list(coords)
        self._redraw()
        return None

    def move(self, spec: Any, dx: int, dy: int) -> None:
        """Shift everything a tag names by a distance in pixels."""
        for item in self._matching(spec):
            item.coords = [
                value + (int(dx) if index % 2 == 0 else int(dy))
                for index, value in enumerate(item.coords)
            ]
        self._redraw()

    def delete(self, *specs: Any) -> None:
        """Remove everything the tags name."""
        doomed = {item.ident for spec in specs for item in self._matching(spec)}
        self._items = [item for item in self._items if item.ident not in doomed]
        if self._current in doomed:
            self._current = None
        self._redraw()

    def itemconfigure(
        self, spec: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> Any:
        """Set options on everything a tag names, or read one item's options.

        Raises:
            TclError: If an option is not one the item's type takes.
        """
        items = self._matching(spec)
        given = _given(cnf, kw)
        if not cnf and not kw:
            return dict(items[0].options) if items else {}
        if not given:  # every option None, which tkinter drops
            return None
        for item in items:
            spec_for_kind = {
                **self._COMMON_ITEM_OPTIONS,
                **self._ITEM_OPTIONS[item.kind],
            }
            for name, value in given.items():
                option = _OPTION_ALIASES.get(name, name)
                if option not in spec_for_kind:
                    raise TclError(f'unknown option "-{name}"')
                item.options[option] = value
        self._redraw()
        return None

    itemconfig = itemconfigure

    def itemcget(self, spec: Any, option: str) -> Any:
        """One option of the first item a tag names.

        Raises:
            TclError: If nothing matches, or the option is not one it takes.
        """
        items = self._matching(spec)
        if not items:
            raise TclError(f'unknown item "{spec}"')
        name = _OPTION_ALIASES.get(option, option)
        if name not in items[0].options:
            raise TclError(f'unknown option "-{option}"')
        return items[0].options[name]

    def type(self, spec: Any) -> str | None:
        """What kind of item a tag names, or None if nothing does."""
        items = self._matching(spec)
        return items[0].kind if items else None

    def bbox(self, *specs: Any) -> tuple[int, int, int, int] | None:
        """The extent of everything the tags name, in pixels."""
        boxes = [
            box
            for spec in (specs or ("all",))
            for item in self._matching(spec)
            if (box := self._item_bbox(item)) is not None
        ]
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    def _item_bbox(self, item: _CanvasItem) -> tuple[int, int, int, int] | None:
        """One item's extent, in pixels."""
        if item.kind == "text":
            return self._text_bbox(item)
        return bbox_of(item.points())

    def _text_bbox(self, item: _CanvasItem) -> tuple[int, int, int, int] | None:
        """A text item's extent, in pixels, cell-aligned as it is drawn."""
        placed = self._text_origin(item)
        if placed is None:
            return None
        column, row, lines = placed
        width = max((len(line) for line in lines), default=0)
        return (
            column,
            row * 2,
            column + max(0, width - 1),
            row * 2 + 2 * len(lines) - 1,
        )

    # ---------------------------------------------------------------- tagging

    def gettags(self, spec: Any) -> tuple[str, ...]:
        """The tags on the first item a tag or id names."""
        items = self._matching(spec)
        return items[0].tags if items else ()

    def addtag_withtag(self, new: str, spec: Any) -> None:
        """Add a tag to everything another tag names."""
        for item in self._matching(spec):
            if new not in item.tags:
                item.options["tags"] = (*item.tags, new)

    def dtag(self, spec: Any, tag: str | None = None) -> None:
        """Remove a tag. Without one, remove the tag that was used to find them."""
        target = str(spec) if tag is None else tag
        for item in self._matching(spec):
            item.options["tags"] = tuple(t for t in item.tags if t != target)

    def tag_raise(self, spec: Any, above: Any = None) -> None:
        """Move items to the front of the drawing order, or above another."""
        self._reorder_items(spec, above, to_front=True)

    def tag_lower(self, spec: Any, below: Any = None) -> None:
        """Move items to the back of the drawing order, or below another."""
        self._reorder_items(spec, below, to_front=False)

    def _reorder_items(self, spec: Any, other: Any, *, to_front: bool) -> None:
        """Shared by tag_raise and tag_lower."""
        moving = self._matching(spec)
        if not moving:
            return
        idents = {item.ident for item in moving}
        rest = [item for item in self._items if item.ident not in idents]
        if other is None:
            self._items = rest + moving if to_front else moving + rest
        else:
            anchors = [
                item for item in self._matching(other) if item.ident not in idents
            ]
            if not anchors:
                self._items = rest + moving if to_front else moving + rest
            else:
                at = rest.index(anchors[-1] if to_front else anchors[0])
                cut = at + 1 if to_front else at
                self._items = rest[:cut] + moving + rest[cut:]
        self._redraw()

    # --------------------------------------------------------- item bindings

    def tag_bind(
        self,
        spec: Any,
        sequence: str | None = None,
        func: Callable[[Event], Any] | None = None,
        add: bool | str | None = None,
    ) -> None:
        """Bind an event on the items a tag names.

        Unlike :meth:`Misc.bind`, this is not a binding on the widget: the
        event is delivered only while the pointer is over one of the items,
        and ``event.widget`` is still the canvas. The item it happened to is
        the one ``find_withtag("current")`` names, as in Tk.

        Args:
            spec: A tag, or an item id.
            sequence: The event, such as ``"<Button-1>"``.
            func: What to call.
            add: True to keep any binding already there.
        """
        if sequence is None or func is None:
            return
        bindings = self._item_bindings.setdefault(str(spec), {})
        if add in (True, "+"):
            bindings.setdefault(sequence, []).append(func)
        else:
            bindings[sequence] = [func]

    def tag_unbind(self, spec: Any, sequence: str) -> None:
        """Remove the bindings a tag has for one event."""
        self._item_bindings.get(str(spec), {}).pop(sequence, None)

    def _item_at(self, x: int, y: int) -> int | None:
        """The topmost item whose ink covers a pixel.

        Ink, not extent. A diagonal line's bounding box is the whole
        rectangle it crosses, so testing by extent let a thin line claim
        everything around it - clicking inside a square picked out the
        diagonal drawn across it rather than the square. Tk tests the item's
        real shape too, which also means that clicking the middle of an
        *unfilled* rectangle selects nothing: there is nothing there.

        Both halves of the clicked cell count. A click names a cell, and
        either of the two pixels stacked in it may be the one with ink.
        """
        slack = max(0, int(self._options["closeenough"]))
        reach = range(-slack, slack + 1)
        for item in reversed(self._items):
            if str(item.options.get("state")) == "hidden":
                continue
            box = self._item_bbox(item)
            # The extent is only a cheap filter before the ink is looked at,
            # and it has to admit both halves of the cell for the same reason
            # the ink test does.
            if box is None or not (
                box[0] - slack <= x <= box[2] + slack
                and any(box[1] - slack <= row <= box[3] + slack for row in (y, y ^ 1))
            ):
                continue
            # Text fills the cells it occupies, so its extent is its ink.
            if item.kind == "text":
                return item.ident
            pixels = self._item_pixels(item)
            if any(
                (x + across, row + down) in pixels
                for row in (y, y ^ 1)
                for across in reach
                for down in reach
            ):
                return item.ident
        return None

    def _deliver(self, ident: int | None, sequence: str, event: Event) -> None:
        """Run whatever is bound to one event on one item.

        The item's own id is consulted first, then its tags in the order they
        were given, then ``all`` - which is the order Tk searches, the id
        being the item's first tag there.
        """
        if ident is None:
            return
        item = self._item(ident)
        if item is None:
            return
        keys = [str(ident), *item.tags, "all"]
        if ident == self._current:
            keys.insert(-1, "current")
        for key in keys:
            for callback in self._item_bindings.get(key, {}).get(sequence, ()):
                callback(event)

    # ---------------------------------------------------------------- the view

    def canvasx(self, screen_x: int) -> int:
        """The canvas pixel a screen column is showing."""
        return int(screen_x) - self.winfo_rootx() - self._text_area().x + self._left

    def canvasy(self, screen_y: int) -> int:
        """The canvas pixel row a screen row is showing.

        The top half of the cell, since a row holds two pixel rows and the
        upper one is the one a click is taken to mean.
        """
        row = int(screen_y) - self.winfo_rooty() - self._text_area().y
        return row * 2 + self._top

    def _scroll_region(self) -> tuple[int, int, int, int]:
        """What there is to scroll over: the option, or everything drawn."""
        region = self._options["scrollregion"]
        if region:
            values = _canvas_coords(
                region if isinstance(region, (tuple, list)) else region.split()
            )
            if len(values) >= 4:
                return (values[0], values[1], values[2], values[3])
        return self.bbox() or (0, 0, *self._plane_size())

    def yview(self, *args: Any) -> tuple[float, float] | None:
        """Read or move the vertical view, in the shape Tk uses."""
        if not args:
            return self._fractions(vertical=True)
        self._scroll(args, vertical=True)
        return None

    def xview(self, *args: Any) -> tuple[float, float] | None:
        """Read or move the horizontal view."""
        if not args:
            return self._fractions(vertical=False)
        self._scroll(args, vertical=False)
        return None

    def _scroll(self, args: tuple[Any, ...], *, vertical: bool) -> None:
        """Apply one Tk scrolling command to one axis."""
        left, top, right, bottom = self._scroll_region()
        width, height = self._plane_size()
        span = height if vertical else width
        total = max(1, (bottom - top) if vertical else (right - left))
        origin = top if vertical else left
        action = str(args[0])
        if action == "moveto":
            position = origin + int(float(args[1]) * total)
        elif action == "scroll":
            count = int(float(args[1]))
            unit = str(args[2]) if len(args) > 2 else "units"
            # A vertical unit is a cell, which is two pixels: scrolling by one
            # would swap which half of the cell each pixel row lands in, and
            # the whole picture would shimmer.
            step = span if unit.startswith("page") else (2 if vertical else 1)
            position = (self._top if vertical else self._left) + count * step
        else:
            raise TclError(f'bad option "{action}": must be moveto or scroll')
        limit = max(origin, origin + total - span)
        position = max(origin, min(position, limit))
        if vertical:
            self._top = position - position % 2
        else:
            self._left = position
        self._redraw()
        self._report_view()

    def _fractions(self, *, vertical: bool) -> tuple[float, float]:
        """Where one axis of the view is, as two fractions of the region."""
        left, top, right, bottom = self._scroll_region()
        width, height = self._plane_size()
        span = height if vertical else width
        total = max(1, (bottom - top) if vertical else (right - left))
        origin = top if vertical else left
        start = ((self._top if vertical else self._left) - origin) / total
        return (min(1.0, max(0.0, start)), min(1.0, max(0.0, start + span / total)))

    def _report_scroll_view(self) -> None:
        """A resize changes how much is visible, so the scrollbar is retold."""
        self._report_view()

    def _report_view(self) -> None:
        """Tell the scrollbars where the view is, if anything is listening."""
        for option, fractions in (
            ("yscrollcommand", self._fractions(vertical=True)),
            ("xscrollcommand", self._fractions(vertical=False)),
        ):
            command = self._options[option]
            if command is not None:
                command(*fractions)

    # --------------------------------------------------------------- painting

    def _item_pixels(self, item: _CanvasItem) -> dict[tuple[int, int], str]:
        """Every pixel one item lights, and what colour.

        Interior first and outline second, so an outline of a different
        colour is not swallowed by the fill underneath it.
        """
        points = item.points()
        fill = str(item.options.get("fill") or "")
        outline = str(item.options.get("outline") or "")
        pixels: dict[tuple[int, int], str] = {}
        if item.kind == "line":
            pixels.update(dict.fromkeys(line_pixels(points), fill or "white"))
        elif item.kind in ("rectangle", "oval"):
            (x0, y0), (x1, y1) = points[0], points[1]
            solid = (
                filled_rectangle_pixels
                if item.kind == "rectangle"
                else filled_oval_pixels
            )
            edge = rectangle_pixels if item.kind == "rectangle" else oval_pixels
            if fill:
                pixels.update(dict.fromkeys(solid(x0, y0, x1, y1), fill))
            if outline:
                pixels.update(dict.fromkeys(edge(x0, y0, x1, y1), outline))
        elif item.kind == "polygon":
            if fill:
                pixels.update(dict.fromkeys(filled_polygon_pixels(points), fill))
            if outline:
                pixels.update(dict.fromkeys(polygon_pixels(points), outline))
        return pixels

    def _text_origin(self, item: _CanvasItem) -> tuple[int, int, list[str]] | None:
        """Where a text item starts, as ``(column, cell row, lines)``.

        The row is a cell row, not a pixel row: a glyph fills a cell, so a
        text item snaps to the nearest one rather than straddling two.
        """
        points = item.points()
        if not points:
            return None
        lines = str(item.options.get("text") or "").split("\n")
        if not lines:
            return None
        x, y = points[0]
        width = max((len(line) for line in lines), default=0)
        across, down = parse_anchor(str(item.options.get("anchor") or "center"))
        column = x - int(width * across)
        # The cell the point falls in, then whole rows off it for a block of
        # several lines. Taking half the block height off in *pixels* first
        # shifted a single line half a cell and rounded it onto the wrong row.
        row = y // 2 - int(len(lines) * down)
        return (column, row, lines)

    def _redraw(self) -> None:
        """Paint the border, then every item in the order it was made."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        base = self._background_attribute() | self._font_attribute()
        with contextlib.suppress(ValueError):
            base = for_state(str(self._options["state"]), base)
        area = self._text_area()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", base)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, base
                )
            if not area.is_empty:
                for column, row, glyph, attribute in self._painted(area, base):
                    self._write_line(
                        dispatcher,
                        window,
                        area.y + row,
                        area.x + column,
                        glyph,
                        attribute,
                    )

    def _painted(self, area: Rect, base: int) -> list[tuple[int, int, str, int]]:
        """Every cell to draw, worked out item by item in drawing order.

        Items are composed one at a time rather than all at once so that a
        later item covers an earlier one, including where a drawing and a
        piece of text want the same cell. Composing the whole plane first and
        laying text over it afterwards would put every label on top, whatever
        order it was made in.
        """
        pixels: dict[tuple[int, int], str] = {}
        cells: dict[tuple[int, int], tuple[str, int]] = {}
        for item in self._items:
            if str(item.options.get("state")) == "hidden":
                continue
            if item.kind == "text":
                self._compose_text(item, pixels, cells, base)
            else:
                drawn = self._item_pixels(item)
                pixels.update(drawn)
                # Only the cells this item touched are recomposed. Folding
                # the whole plane for every item would make drawing cost the
                # square of what is on the canvas.
                affected = {}
                for x, y in drawn:
                    for half in (y - y % 2, y - y % 2 + 1):
                        if (x, half) in pixels:
                            affected[(x, half)] = pixels[(x, half)]
                for at, (glyph, fore, back) in compose(affected).items():
                    cells[at] = (glyph, self._ink(fore, back, base))
        painted = []
        top_row = self._top // 2
        for (x, row), (glyph, attribute) in cells.items():
            column, screen_row = x - self._left, row - top_row
            if 0 <= column < area.width and 0 <= screen_row < area.height:
                painted.append((column, screen_row, glyph, attribute))
        return painted

    def _compose_text(
        self,
        item: _CanvasItem,
        pixels: dict[tuple[int, int], str],
        cells: dict[tuple[int, int], tuple[str, int]],
        base: int,
    ) -> None:
        """Put a text item's glyphs into the cells, clearing what was under.

        The pixels beneath are dropped, so a drawing item made later composes
        from its own ink alone rather than resurrecting what the text covered.
        """
        placed = self._text_origin(item)
        if placed is None:
            return
        column, row, lines = placed
        attribute = self._ink(str(item.options.get("fill") or ""), None, base)
        font = str(item.options.get("font") or "").lower()
        attribute |= from_font(
            bold="bold" in font,
            italic="italic" in font,
            underline="underline" in font,
        )
        justify = str(item.options.get("justify") or "left")
        width = max((len(line) for line in lines), default=0)
        for offset, line in enumerate(lines):
            start = column + align_offset(len(line), width, justify)
            for index, character in enumerate(line):
                at = (start + index, row + offset)
                pixels.pop((at[0], at[1] * 2), None)
                pixels.pop((at[0], at[1] * 2 + 1), None)
                cells[at] = (character, attribute)

    def _ink(self, foreground: str, background: str | None, base: int) -> int:
        """The attribute a cell needs, given the colours its two halves want."""
        colors = self.tk.colors
        if colors is None:
            return base
        return with_colors(
            base,
            colors.attribute_for(
                foreground or str(self._options["foreground"] or "white"),
                background or str(self._options["background"] or "black"),
            ),
        )


def _canvas_coords(args: Any) -> list[int]:
    """Flatten coordinates however they were given.

    Tk takes ``(x0, y0, x1, y1)``, ``((x0, y0), (x1, y1))`` and a single
    sequence of any of those, so all three arrive here and all three work.
    """
    flat: list[int] = []
    values = list(args)
    if len(values) == 1 and isinstance(values[0], (list, tuple)):
        values = list(values[0])
    for value in values:
        if isinstance(value, (list, tuple)):
            flat.extend(round(float(part)) for part in value)
        else:
            flat.append(round(float(value)))
    return flat


def _canvas_mouse(event: Event) -> None:
    """Deliver a mouse event to whichever item is under the pointer.

    Enter and Leave are synthesised here rather than reported by curses:
    there is no such thing as a pointer crossing an item at the terminal
    level, so the canvas works it out by noticing that the item under the
    pointer has changed.
    """
    canvas = event.widget
    x, y = canvas.canvasx(event.x_root), canvas.canvasy(event.y_root)
    found = canvas._item_at(x, y)
    if found != canvas._current:
        canvas._deliver(canvas._current, "<Leave>", event)
        canvas._current = found
        canvas._deliver(found, "<Enter>", event)
    sequence = {
        "ButtonPress": f"<Button-{event.num}>",
        "ButtonRelease": f"<ButtonRelease-{event.num}>",
        "Motion": "<Motion>",
        "Double": f"<Double-Button-{event.num}>",
    }.get(event.type, "")
    if sequence:
        canvas._deliver(canvas._current, sequence, event)


class Menu(_Drawable):
    """A list of things to choose, posted over everything else.

    A menu is the one widget here that is placed against the *screen* rather
    than inside its parent. It is not packed or gridded: it is **posted** at a
    point - by :meth:`post`, by :meth:`tk_popup`, or by a menubar - and
    :mod:`tkcurses._core.menus` works out where it actually fits. A menu with
    no room below its point is drawn above it, one that would run off the
    right is pulled left, and one taller than the screen scrolls rather than
    being cut off.

    While a menu is posted it holds the grab and the focus, so every key and
    every click reaches it - including a click somewhere else, which is how it
    knows to dismiss itself. Escape dismisses it too, and so does invoking
    anything on it.

    The same widget is also a **menubar** when a toplevel is given one
    through its ``menu`` option. It then draws in a row across the top of
    that window, its cascades post beneath their labels, and the toplevel
    lays its children out in what is left.
    """

    #: Entry kinds, and what each one accepts on top of the common options.
    #: -columnbreak on every kind but a separator, which refuses it - as Tk
    #: 9.0.2 does, measured ("unknown option"). TkCurses-aj1.13.1.
    _ENTRY_OPTIONS: ClassVar[dict[str, dict[str, Any]]] = {
        "command": {"columnbreak": 0},
        "cascade": {"menu": None, "columnbreak": 0},
        "checkbutton": {
            "onvalue": 1,
            "offvalue": 0,
            "variable": None,
            "columnbreak": 0,
        },
        "radiobutton": {"value": "", "variable": None, "columnbreak": 0},
        "separator": {},
    }
    _COMMON_ENTRY_OPTIONS: ClassVar[dict[str, Any]] = {
        "accelerator": "",
        "command": None,
        "label": "",
        "state": "normal",
        "underline": -1,
    }

    #: What a ticked checkbutton and a chosen radiobutton look like.
    _INDICATORS: ClassVar[dict[str, tuple[str, str]]] = {
        "checkbutton": ("[x] ", "[ ] "),
        "radiobutton": ("(•) ", "( ) "),
    }

    _STATE_COLOURS: ClassVar[dict[str, tuple[str | None, str | None]]] = {
        "active": ("activeforeground", "activebackground"),
        "disabled": ("disabledforeground", None),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        **_STATE_COLOUR_OPTIONS,
        # The active entry's border, which a row-high entry has no room for,
        # and its relief: sunken is drawn dim. TkCurses-gm66.5.
        "activeborderwidth": 1,
        "activerelief": "raised",
        # The tick or bullet of a chosen check or radio entry. "" here, Tk's
        # #000000: drawn as the label is. TkCurses-gm66.4.
        "selectcolor": "",
        "postcommand": None,
        "relief": "raised",
        "takefocus": False,
        "tearoff": False,
        "title": "",
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``postcommand``, ``title``, and the standard options.
        """
        self._entries: list[MenuEntry] = []
        self._active: int | None = None
        self._posted = False
        self._first = 0
        self._as_menubar = False
        self._open_cascade: Menu | None = None
        self._parent_menu: Menu | None = None
        self._focus_before: Misc | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the keys and clicks every Menu answers."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Any-Key>", _menu_key)
        bind(name, "<Button-1>", _menu_click)
        bind(name, "<Motion>", _menu_motion)

    # ---------------------------------------------------------- making entries

    def add(self, kind: str, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append an entry of one kind.

        Raises:
            TclError: If the kind is not one Tk defines, or an option is not
                one that kind takes.
        """
        self.insert(len(self._entries), kind, cnf, **kw)

    def insert(
        self, index: Any, kind: str, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Put an entry of one kind at a position.

        Raises:
            TclError: If the kind or an option is not one Tk defines.
        """
        if kind not in self._ENTRY_OPTIONS:
            raise TclError(f'bad menu entry type "{kind}"')
        entry = MenuEntry(kind, self._checked_entry(kind, _given(cnf, kw)))
        self._entries.insert(self._insert_at(index), entry)
        self._apply_requested_size()
        self._refresh()

    def add_command(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append an entry that runs something."""
        self.add("command", cnf, **kw)

    def add_cascade(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append an entry that opens a submenu."""
        self.add("cascade", cnf, **kw)

    def add_checkbutton(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append an entry that toggles a variable."""
        self.add("checkbutton", cnf, **kw)

    def add_radiobutton(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append an entry that sets a variable to its own value."""
        self.add("radiobutton", cnf, **kw)

    def add_separator(self, cnf: dict[str, Any] | None = None, **kw: Any) -> None:
        """Append a dividing line."""
        self.add("separator", cnf, **kw)

    def insert_command(
        self, index: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Insert an entry that runs something."""
        self.insert(index, "command", cnf, **kw)

    def insert_cascade(
        self, index: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Insert an entry that opens a submenu."""
        self.insert(index, "cascade", cnf, **kw)

    def insert_checkbutton(
        self, index: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Insert an entry that toggles a variable."""
        self.insert(index, "checkbutton", cnf, **kw)

    def insert_radiobutton(
        self, index: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Insert an entry that sets a variable."""
        self.insert(index, "radiobutton", cnf, **kw)

    def insert_separator(
        self, index: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        """Insert a dividing line."""
        self.insert(index, "separator", cnf, **kw)

    def _checked_entry(self, kind: str, given: dict[str, Any]) -> dict[str, Any]:
        """Resolve an entry's options against what its kind accepts.

        Raises:
            TclError: If an option is not one the kind takes.
        """
        spec = {**self._COMMON_ENTRY_OPTIONS, **self._ENTRY_OPTIONS[kind]}
        options = dict(spec)
        for name, value in given.items():
            option = _OPTION_ALIASES.get(name, name)
            if option not in spec:
                raise TclError(f'unknown option "-{name}"')
            options[option] = value
        return options

    # -------------------------------------------------------------- indices

    def index(self, spec: Any) -> int | None:
        """Resolve one of Tk's entry indices.

        Takes a number, ``end`` or ``last``, ``active``, ``none``, ``@y`` for
        a row within the menu, or the label of an entry. Returns None for
        ``none`` and for a label that matches nothing, which is what Tk does.
        """
        if spec is None:
            return None
        if isinstance(spec, int):
            return spec if 0 <= spec < len(self._entries) else None
        text = str(spec).strip()
        if text in ("end", "last"):
            return len(self._entries) - 1 if self._entries else None
        if text == "active":
            return self._active
        if text == "none":
            return None
        if text.startswith("@"):
            # "@y", or "@x,y" in a menu laid out in columns - Tk 9.0.2 takes
            # both, measured, and "@y" alone reads as the first column.
            x, _, y = text[1:].rpartition(",")
            if x:
                return self._entry_at(int(x), int(y))
            return self._entry_at_row(int(y))
        if text.lstrip("-").isdigit():
            number = int(text)
            return number if 0 <= number < len(self._entries) else None
        return next(
            (n for n, entry in enumerate(self._entries) if entry.label == text), None
        )

    def _insert_at(self, spec: Any) -> int:
        """Where an insertion goes, clamped into the list."""
        if isinstance(spec, int):
            return max(0, min(spec, len(self._entries)))
        resolved = self.index(spec)
        return len(self._entries) if resolved is None else resolved

    def _entry_at_row(self, row: int) -> int | None:
        """Which entry a row within the widget falls on, in the first column."""
        if self._as_menubar:
            return self._entry_at_column(row)
        return self._entry_at(self._text_area().x, row)

    def _entry_at(self, column: int, row: int) -> int | None:
        """Which entry a cell within the widget falls on.

        A menu in one column answers by the row alone, wherever across it
        the cell is, as it always has; one laid out in columns asks which
        column the cell is in, too. TkCurses-aj1.13.1.
        """
        if self._as_menubar:
            return self._entry_at_column(column)
        area = self._text_area()
        places = self._places()
        columned = self._columned(places)
        wanted = row - area.y + (0 if columned else self._first)
        for number, place in enumerate(places):
            if place.row != wanted:
                continue
            if not columned:
                return number
            if place.x <= column - area.x < place.x + place.width + COLUMN_GAP:
                return number
        return None

    def _places(self) -> list[Placed]:
        """Where each entry goes when posted - see :func:`lay_out`."""
        places, _ = lay_out(self._entries, indicators=self._has_indicators())
        return places

    @staticmethod
    def _columned(places: list[Placed]) -> bool:
        """True if the entries are laid out in more than one column."""
        return any(place.x for place in places)

    def _entry_at_column(self, column: int) -> int | None:
        """Which menubar entry a column falls on."""
        at = self._text_area().x
        for number, entry in enumerate(self._entries):
            width = len(entry.label) + 2
            if at <= column < at + width:
                return number
            at += width
        return None

    def type(self, spec: Any) -> str | None:
        """What kind of entry an index names."""
        at = self.index(spec)
        return None if at is None else self._entries[at].kind

    def yposition(self, spec: Any) -> int:
        """The row an entry occupies within the menu, as Tk reports it.

        Within its column, in a menu laid out in columns.
        """
        at = self.index(spec)
        if at is None:
            return 0
        places = self._places()
        if self._columned(places):
            return places[at].row
        return at - self._first

    def xposition(self, spec: Any) -> int:
        """The column an entry's column starts at, counted as yposition is.

        0 in a menu of one column; in one laid out with ``-columnbreak``,
        how far across its column begins. Tk answers in pixels and counts
        the border; this counts cells from where the entries start, as
        :meth:`yposition` does. TkCurses-aj1.13.1.
        """
        at = self.index(spec)
        return 0 if at is None else self._places()[at].x

    # ------------------------------------------------------ changing entries

    def delete(self, first: Any, last: Any = None) -> None:
        """Remove entries from ``first`` up to and including ``last``."""
        start = self.index(first)
        if start is None:
            return
        stop = start if last is None else self.index(last)
        if stop is None:
            stop = len(self._entries) - 1
        del self._entries[start : stop + 1]
        if self._active is not None and self._active >= len(self._entries):
            self._active = None
        self._apply_requested_size()
        self._refresh()

    def entryconfigure(
        self, spec: Any, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> Any:
        """Set options on one entry, or read them all.

        Raises:
            TclError: If the index names nothing, or an option is not one the
                entry's kind takes.
        """
        at = self.index(spec)
        if at is None:
            raise TclError(f'bad menu entry index "{spec}"')
        entry = self._entries[at]
        if not cnf and not kw:
            return dict(entry.options)
        given = _given(cnf, kw)
        if not given:  # every option None, which tkinter drops
            return None
        spec_for_kind = {
            **self._COMMON_ENTRY_OPTIONS,
            **self._ENTRY_OPTIONS[entry.kind],
        }
        for name, value in given.items():
            option = _OPTION_ALIASES.get(name, name)
            if option not in spec_for_kind:
                raise TclError(f'unknown option "-{name}"')
            entry.options[option] = value
        self._apply_requested_size()
        self._refresh()
        return None

    entryconfig = entryconfigure

    def entrycget(self, spec: Any, option: str) -> Any:
        """One option of one entry.

        Raises:
            TclError: If the index or the option names nothing.
        """
        at = self.index(spec)
        if at is None:
            raise TclError(f'bad menu entry index "{spec}"')
        name = _OPTION_ALIASES.get(option, option)
        if name not in self._entries[at].options:
            raise TclError(f'unknown option "-{option}"')
        return self._entries[at].options[name]

    # ------------------------------------------------------------ behaviour

    def activate(self, spec: Any) -> None:
        """Make an entry the active one, or ``none`` to make none of them."""
        at = self.index(spec)
        if at is not None and not self._entries[at].selectable:
            return
        self._active = at
        if at is not None and not self._as_menubar:
            self._first = self._scrolled_to(at)
        self._refresh()

    def invoke(self, spec: Any) -> Any:
        """Do what choosing an entry does, and return what its command did.

        A cascade opens its submenu rather than running anything; a
        checkbutton or radiobutton writes its variable first; everything else
        dismisses the menu before running, so that a command which posts
        another window does not fight with this one.
        """
        at = self.index(spec)
        if at is None:
            return None
        entry = self._entries[at]
        if not entry.selectable:
            return None
        if entry.kind == "cascade":
            self._open(at)
            return None
        self._write_variable(entry)
        self._dismiss_all()
        command = entry.options.get("command")
        return None if command is None else command()

    def bind_accelerators(self, target: Misc | None = None) -> list[str]:
        """Bind every entry's accelerator to the entry, submenus included.

        **Not tkinter API** - a TkCurses addition, like ``winfo_colordepth``.
        In Tk the accelerator is display only: its manual says the option
        "does not actually set the corresponding binding", so an application
        writes each shortcut twice, as text and as a binding, and the two
        drift apart. This makes the binding from the text, read by
        :func:`~tkcurses._core.menus.accelerator_sequence` - ``Ctrl+O``,
        ``^S``, ``Alt+F4``, ``Ctrl+X Ctrl+S``.

        Args:
            target: The widget to bind on. By default every widget, through
                ``bind_all``, which is how Tk programs usually bind a menu's
                shortcuts.

        Returns:
            The sequences bound, in order.

        Raises:
            ValueError: If an accelerator cannot be read, naming the entry -
                before anything is bound, so it is all or nothing.

        Each binding is added rather than replacing what is there, and runs
        the entry by what it IS, not by its index: entries inserted
        afterwards do not move it onto another. A disabled entry's shortcut
        does nothing, as choosing it would. TkCurses-aj1.13.1.
        """
        found: list[tuple[str, Menu, MenuEntry]] = []
        self._collect_accelerators(found, set())
        bind = target.bind if target is not None else self.bind_all
        for sequence, menu, entry in found:
            bind(sequence, _accelerated(menu, entry), add=True)
        return [sequence for sequence, _, _ in found]

    def _collect_accelerators(
        self, found: list[tuple[str, Menu, MenuEntry]], seen: set[int]
    ) -> None:
        """Gather (sequence, menu, entry) for this menu and its submenus."""
        if id(self) in seen:
            return
        seen.add(id(self))
        for entry in self._entries:
            if entry.accelerator:
                try:
                    sequence = accelerator_sequence(entry.accelerator)
                except ValueError as error:
                    raise ValueError(f"menu entry {entry.label!r}: {error}") from None
                found.append((sequence, self, entry))
            submenu = entry.options.get("menu")
            if entry.kind == "cascade" and isinstance(submenu, Menu):
                submenu._collect_accelerators(found, seen)

    def _write_variable(self, entry: MenuEntry) -> None:
        """Put the entry's value in its variable, for the two kinds that have one."""
        variable = entry.options.get("variable")
        if variable is None:
            return
        if entry.kind == "checkbutton":
            on, off = entry.options["onvalue"], entry.options["offvalue"]
            variable.set(off if _same_value(variable.get(), on) else on)
        elif entry.kind == "radiobutton":
            variable.set(entry.options["value"])

    def _indicator_for(self, entry: MenuEntry) -> str:
        """The tick or bullet an entry shows, or spaces to line up with one."""
        if entry.kind not in self._INDICATORS:
            return "    " if self._has_indicators() else ""
        on, off = self._INDICATORS[entry.kind]
        variable = entry.options.get("variable")
        if variable is None:
            return off
        wanted = (
            entry.options["onvalue"]
            if entry.kind == "checkbutton"
            else entry.options["value"]
        )
        return on if _same_value(variable.get(), wanted) else off

    def _has_indicators(self) -> bool:
        """True if any entry needs room on the left for a tick."""
        return any(entry.kind in self._INDICATORS for entry in self._entries)

    # -------------------------------------------------------------- posting

    def post(self, x: int, y: int) -> None:
        """Put the menu on screen at a point, moving it to fit.

        Args:
            x: Screen column to post at.
            y: Screen row.
        """
        command = self._options["postcommand"]
        if command is not None:
            command()
        width, height = self._posted_size()
        screen_width, screen_height = self._screen_size()
        x, y, height = place_popup(x, y, width, height, screen_width, screen_height)
        self._posted = True
        # place_popup works in screen cells; _allocate takes coordinates
        # relative to the master, as every geometry manager hands it. They
        # are the same thing only for a menu whose master is the root, which
        # is why nothing noticed until an OptionMenu made its menu a child of
        # the button - Tk builds it that way too - and the menu was allocated
        # at an offset and posted off the screen.
        master = self.master
        origin_x = master.winfo_rootx() if master is not None else 0
        origin_y = master.winfo_rooty() if master is not None else 0
        self._allocate(Rect(x - origin_x, y - origin_y, width, height))
        self._map()
        self._restack_panels()
        self._focus_before = self.tk.focus
        self.grab_set()
        self.focus_set()
        self._first = self._scrolled_to(self._active or 0)
        self._refresh()

    def unpost(self) -> None:
        """Take the menu off screen, and any submenu with it."""
        if self._open_cascade is not None:
            self._open_cascade.unpost()
            self._open_cascade = None
        if not self._posted:
            return
        self._posted = False
        self._active = None
        self.grab_release()
        self._unmap()
        parent = self._parent_menu
        self._parent_menu = None
        previous = self._focus_before
        self._focus_before = None
        if parent is not None and parent._as_menubar:
            # A dropdown of the menubar takes the bar's highlight with it, as
            # Tk's MenuUnpost does ("$parent activate {}", read from Tk
            # 9.0.2). The bar is never posted, so the branch below never ran
            # for it, and Colours stayed highlighted after Escape - looking
            # like a keyboard mode the bar was not in. Found by the author in
            # UAT 46; TkCurses-aj1.13.1. Opening the next menu along the bar
            # comes through here too, and _open sets the new active entry
            # after closing the old dropdown, so it is not lost.
            parent._open_cascade = None
            parent._active = None
            parent._refresh()
        if parent is not None and parent._posted:
            parent._open_cascade = None
            parent.grab_set()
            parent.focus_set()
        elif previous is not None and previous.winfo_exists():
            previous.focus_set()
        # Nothing to give the focus back to: _unmap has already taken it off
        # this menu, and leaving it there is what stopped Escape closing the
        # application after a menu had been opened once.

    def tk_popup(self, x: int, y: int, entry: Any = None) -> None:
        """Post the menu at a point, optionally with one entry active."""
        self.post(x, y)
        if entry is not None:
            self.activate(entry)

    def _open(self, at: int) -> None:
        """Post the submenu of a cascade entry, beside its own row."""
        entry = self._entries[at]
        submenu: Menu | None = entry.options.get("menu")
        if submenu is None:
            return
        # `_posted` first: comparing against _open_cascade, which is
        # `Menu | None`, widens submenu back to include None for a type
        # checker, and the two tests are independent anyway.
        if submenu._posted and self._open_cascade is submenu:
            return
        if self._open_cascade is not None:
            self._open_cascade.unpost()
        self._active = at
        submenu._parent_menu = self
        self._open_cascade = submenu
        if self._as_menubar:
            submenu.post(
                self.winfo_rootx() + self._label_column(at), self.winfo_rooty() + 1
            )
        else:
            submenu.post(
                self.winfo_rootx() + self._rect.width,
                self.winfo_rooty() + (at - self._first),
            )
        self._refresh()

    def _label_column(self, at: int) -> int:
        """Where one menubar label starts, relative to the bar."""
        column = self._text_area().x
        for entry in self._entries[:at]:
            column += len(entry.label) + 2
        return column

    def _dismiss_all(self) -> None:
        """Unpost this menu and every one above it, back to the menubar.

        Each one in turn, rather than walking to the root and unposting that:
        a menubar is never itself posted, so doing it that way dismissed
        nothing at all and left the dropdown on screen. The parent is taken
        before unposting, because unposting forgets it.
        """
        menu: Menu | None = self
        while menu is not None:
            parent = menu._parent_menu
            if menu._posted:
                menu.unpost()
            else:
                menu._open_cascade = None
                menu._active = None
                menu._refresh()
            menu = parent

    # -------------------------------------------------------------- geometry

    def _scrolled_to(self, at: int) -> int:
        """The first row to show so ``at`` is visible.

        A menu laid out in columns does not scroll - a column is how a long
        menu was made short - so it always starts at the top.
        """
        if self._columned(self._places()):
            return 0
        return visible_window(len(self._entries), at, self._rows())

    def _posted_size(self) -> tuple[int, int]:
        """The size a posted menu wants, border included."""
        _, (width, height) = lay_out(self._entries, indicators=self._has_indicators())
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        return (width + edge + 2, height + edge)

    def _apply_requested_size(self) -> None:
        """Ask for a bar's row, or for what the entries need when posted."""
        if self._as_menubar:
            self._request_size(
                sum(len(entry.label) + 2 for entry in self._entries) or 1, 1
            )
            return
        width, height = self._posted_size()
        self._request_size(width, height)

    def _rows(self) -> int:
        """How many entries are visible at once."""
        return max(1, self._text_area().height)

    def _text_area(self) -> Rect:
        """Where the entries go, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn and not self._as_menubar else 0
        return Rect(
            edge + 1 if not self._as_menubar else 0,
            edge,
            max(0, self._rect.width - 2 * edge - (2 if not self._as_menubar else 0)),
            max(0, self._rect.height - 2 * edge),
        )

    def _refresh(self) -> None:
        """Repaint, and push it to the terminal if one is running."""
        self._redraw()
        screen = self.tk.screen
        if screen is not None and self._mapped:
            with contextlib.suppress(_curses.error):
                screen.refresh()

    # -------------------------------------------------------------- painting

    def _redraw(self) -> None:
        """Paint the menu, as a bar across the top or as a posted box."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute() | self._font_attribute()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._as_menubar:
                self._draw_bar(dispatcher, window, attribute)
                return
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            self._draw_entries(dispatcher, window, attribute)

    def _draw_bar(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Draw the labels in a row, the open one picked out."""
        column = 0
        for number, entry in enumerate(self._entries):
            text = f" {entry.label} "
            style = attribute
            if number == self._active:
                style = self._in_state(style, "active")
                style |= _part_relief(self._options["activerelief"])
            if str(entry.options.get("state")) == "disabled":
                style = self._in_state(style, "disabled")
            self._write_line(
                dispatcher,
                window,
                0,
                column,
                clip_text(text, self._rect.width - column),
                style,
            )
            column += len(text)
            if column >= self._rect.width:
                break

    def _draw_entries(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Draw the visible entries, the active one picked out."""
        area = self._text_area()
        if area.is_empty:
            return
        cascades = any(entry.kind == "cascade" for entry in self._entries)
        places = self._places()
        columned = self._columned(places)
        for number, place in enumerate(places):
            row = place.row - (0 if columned else self._first)
            if not 0 <= row < area.height:
                continue
            entry = self._entries[number]
            # One column draws across the whole menu, as it always has; a
            # column of several, across its own width.
            x = area.x + place.x if columned else area.x
            width = min(place.width, area.width - place.x) if columned else area.width
            if width <= 0:
                continue
            style = attribute
            if str(entry.options.get("state")) == "disabled":
                style = self._in_state(style, "disabled")
            if number == self._active:
                style = self._in_state(style, "active")
                style |= _part_relief(self._options["activerelief"])
            if entry.kind == "separator":
                self._write_line(
                    dispatcher,
                    window,
                    area.y + row,
                    x - 1 if not columned else x,
                    "─" * (width + 2 if not columned else width),
                    attribute,
                )
                continue
            text = self._indicator_for(entry) + entry.label
            line = text.ljust(width)
            accelerator = entry.accelerator
            if accelerator:
                line = line[: width - len(accelerator)] + accelerator
            if entry.kind == "cascade" and cascades:
                line = line[: width - 1] + CASCADE_GLYPH
            self._write_line(
                dispatcher,
                window,
                area.y + row,
                x,
                clip_text(line, width),
                style,
            )
            self._draw_chosen_mark(
                dispatcher,
                window,
                area.y + row,
                x,
                entry,
                style,
                number == self._active,
            )
            self._draw_underline(
                dispatcher,
                window,
                Rect(x, area.y, width, area.height),
                row,
                entry,
                style,
            )

    def _draw_chosen_mark(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        row: int,
        x: int,
        entry: MenuEntry,
        style: int,
        active: bool,
    ) -> None:
        """Draw a chosen entry's tick or bullet in ``selectcolor``, if given.

        Tk's manual: "the color to display in the indicator when the check
        button or radio button is selected". The mark, not the brackets.
        """
        colour = self._options["selectcolor"]
        if not colour or entry.kind not in self._INDICATORS:
            return
        mark = self._INDICATORS[entry.kind][0]
        if self._indicator_for(entry) != mark:
            return
        state = self._state_colours("active") if active else None
        background = state[1] if state is not None else ""
        self._write_line(
            dispatcher,
            window,
            row,
            x + 1,
            mark[1],
            self._coloured(style, colour, background),
        )

    def _draw_underline(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        row: int,
        entry: MenuEntry,
        style: int,
    ) -> None:
        """Underline the mnemonic character, as tkinter's ``underline`` does."""
        index = int(entry.options.get("underline", -1))
        if not 0 <= index < len(entry.label):
            return
        column = area.x + len(self._indicator_for(entry)) + index
        if column >= area.x + area.width:
            return
        with contextlib.suppress(_curses.error):
            self._write_line(
                dispatcher,
                window,
                area.y + row,
                column,
                entry.label[index],
                style | _curses.A_UNDERLINE,
            )

    # --------------------------------------------------------------- moving

    def _step(self, direction: int) -> None:
        """Move the active entry, skipping what cannot be chosen."""
        if not self._entries:
            return
        count = len(self._entries)
        at = (
            self._active if self._active is not None else -1 if direction > 0 else count
        )
        for _ in range(count):
            at = (at + direction) % count
            if self._entries[at].selectable:
                self.activate(at)
                return

    def _within(self, x: int, y: int) -> bool:
        """True if a screen cell is inside this menu."""
        left, top = self.winfo_rootx(), self.winfo_rooty()
        return (
            left <= x < left + self._rect.width and top <= y < top + self._rect.height
        )


def _menu_key(event: Event) -> str | None:
    """Move about a posted menu, choose an entry, or dismiss it.

    Returns ``"break"`` for everything the menu consumed. A posted menu holds
    the grab, so it sees every key; letting one through would send it to a
    widget the user cannot currently see.
    """
    menu = event.widget
    keysym = event.keysym
    if keysym == "Escape":
        menu.unpost()
        return "break"
    if menu._as_menubar:
        return _menubar_key(menu, keysym)
    if keysym == "Up":
        menu._step(-1)
    elif keysym == "Down":
        menu._step(1)
    elif keysym == "Home":
        menu.activate(_first_selectable(menu, 1))
    elif keysym == "End":
        menu.activate(_first_selectable(menu, -1))
    elif keysym in ("Return", "space"):
        menu.invoke("active")
    elif keysym == "Right":
        if menu.type("active") == "cascade":
            menu.invoke("active")
        else:
            _to_parent_bar(menu, 1)
    elif keysym == "Left":
        # A submenu closes back to the menu it came from; a dropdown of the
        # menubar moves along the bar instead, as Tk's MenuNextMenu does.
        # This asked only "is there a parent?", and a menubar is one, so Left
        # in a dropdown closed it rather than opening the menu to its left.
        parent = menu._parent_menu
        if parent is not None and not parent._as_menubar:
            menu.unpost()
        else:
            _to_parent_bar(menu, -1)
    else:
        _by_mnemonic(menu, event.char)
    # Every key, whether the menu had a use for it or not: Tk's Menu class
    # binds <KeyPress> to "tk::TraverseWithinMenu %W %A; break", read from
    # Tk 9.0.2. A key let through reached bind_all shortcuts behind the open
    # menu - F5 chose "Last file" with Colours open in UAT 46, found by the
    # author. TkCurses-aj1.13.1.
    return "break"


def _menubar_key(menu: Menu, keysym: str) -> str | None:
    """Move along a menubar, and open what is under the cursor."""
    if keysym == "Left":
        menu._step(-1)
        _reopen(menu)
    elif keysym == "Right":
        menu._step(1)
        _reopen(menu)
    elif keysym in ("Down", "Return", "space"):
        menu.invoke("active")
    else:
        return None
    return "break"


def _reopen(menu: Menu) -> None:
    """Follow the active menubar entry with its dropdown, if one is open."""
    if menu._open_cascade is not None and menu._active is not None:
        menu._open(menu._active)


def _to_parent_bar(menu: Menu, direction: int) -> None:
    """Step along the menubar a dropdown belongs to, opening the next one."""
    root_menu: Menu | None = menu
    while root_menu is not None and root_menu._parent_menu is not None:
        root_menu = root_menu._parent_menu
    if root_menu is None or not root_menu._as_menubar:
        return
    root_menu._step(direction)
    if root_menu._active is not None:
        root_menu._open(root_menu._active)


def _accelerated(menu: Menu, entry: MenuEntry) -> Callable[[Event], str]:
    """A binding that chooses ``entry``, wherever it now is in ``menu``."""

    def choose(_event: Event) -> str:
        if entry in menu._entries:
            menu.invoke(menu._entries.index(entry))
        return "break"

    return choose


def _first_selectable(menu: Menu, direction: int) -> int:
    """The first or last entry that can be chosen."""
    numbers = list(range(len(menu._entries)))
    if direction < 0:
        numbers.reverse()
    return next((n for n in numbers if menu._entries[n].selectable), menu._active or 0)


def _by_mnemonic(menu: Menu, char: str) -> str | None:
    """Choose the entry whose underlined letter was typed.

    Returns None when nothing matches. The open menu keeps the key either
    way - see :func:`_menu_key`.
    """
    if not char or not char.isprintable():
        return None
    for number, entry in enumerate(menu._entries):
        index = int(entry.options.get("underline", -1))
        if not entry.selectable or not 0 <= index < len(entry.label):
            continue
        if entry.label[index].lower() == char.lower():
            menu.activate(number)
            menu.invoke(number)
            return "break"
    return None


def _menu_click(event: Event) -> None:
    """Choose what was clicked, or dismiss the menu if the click was elsewhere.

    A posted menu holds the grab, so a click anywhere on the screen arrives
    here - which is exactly what makes clicking away from a menu close it.
    """
    menu = event.widget
    if not menu._within(event.x_root, event.y_root):
        if menu._as_menubar:
            menu._open_cascade = None
            menu._active = None
            menu._refresh()
        else:
            menu._dismiss_all()
        return
    at = menu._entry_at(
        event.x_root - menu.winfo_rootx(), event.y_root - menu.winfo_rooty()
    )
    if at is not None:
        menu.activate(at)
        menu.invoke(at)


def _menu_motion(event: Event) -> None:
    """Follow the pointer, as a menu does while it is open."""
    menu = event.widget
    if not menu._within(event.x_root, event.y_root):
        return
    at = menu._entry_at(
        event.x_root - menu.winfo_rootx(), event.y_root - menu.winfo_rooty()
    )
    if at is None or at == menu._active:
        return
    menu.activate(at)
    # A cascade already open follows the pointer to the next one, which is
    # what makes running down a menubar with the button held work.
    if menu._open_cascade is not None and menu._entries[at].kind == "cascade":
        menu._open(at)


class Listbox(_Drawable, XView, YView):
    """A scrollable list of strings, one of which is selected.

    Four selection modes, as in Tk. ``browse`` - the default - keeps one item
    selected and moves it with the arrows; ``single`` selects only by click or
    by space, leaving the arrows to move an *active* item that is not
    selected; ``multiple`` toggles items independently; ``extended`` adds
    shifted ranges to that.

    The distinction between active and selected is the one worth holding on
    to: the active item is where the keyboard is, and in every mode but
    browse it can be somewhere the selection is not.
    """

    _STATE_COLOURS: ClassVar[dict[str, tuple[str | None, str | None]]] = {
        "disabled": ("disabledforeground", None),
    }

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        **_SELECTION_OPTIONS,
        "disabledforeground": "",  # dimmed, as before; see _in_state
        "activestyle": "underline",
        "font": "",
        "height": 10,
        "relief": "sunken",
        "selectmode": "browse",
        "state": "normal",
        "takefocus": True,
        "width": 20,
        "xscrollcommand": None,
        "yscrollcommand": None,
    }

    #: Markers either side of a selected row.
    _SELECTED_MARKERS = ("\u25b6", "\u25c0")

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``height``, ``width``, ``selectmode``, ``state``, and the
                standard options.
        """
        self._items: list[str] = []
        self._selection: set[int] = set()
        self._active = 0
        self._anchor = 0
        self._top = 0
        # Characters scrolled off to the left, shared by every row as in Tk.
        self._left = 0
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the list keys for every Listbox in this application."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Any-Key>", _listbox_key)
        bind(name, "<Button-1>", _listbox_click)
        # A separate binding, because modifiers match exactly: <Button-1>
        # does not fire for a shifted click, in Tk or here. Binding the plain
        # one and expecting both is a mistake this rule makes easy.
        bind(name, "<Shift-Button-1>", _listbox_click)
        bind(name, "<Button-4>", _listbox_wheel)
        bind(name, "<Button-5>", _listbox_wheel)
        bind(name, "<FocusIn>", _listbox_refresh)
        bind(name, "<FocusOut>", _listbox_refresh)

    def _apply_requested_size(self) -> None:
        """Ask for the configured rows and columns, plus border and padding."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            int(self._options["width"]) + 2 * int(self._options["padx"]) + edge,
            int(self._options["height"]) + 2 * int(self._options["pady"]) + edge,
        )

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if {"width", "height"} & set(given):
            self._apply_requested_size()
            self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    # ------------------------------------------------------------- contents

    def insert(self, index: Any, *elements: str) -> None:
        """Insert items before ``index``; ``end`` appends."""
        at = len(self._items) if index in ("end", END) else self.index(index)
        self._items[at:at] = [str(element) for element in elements]
        self._shift_state(at, len(elements))
        self._redraw()

    def delete(self, first: Any, last: Any = None) -> None:
        """Delete items from ``first`` up to and including ``last``.

        Tk's range is inclusive here, unlike Entry's - a difference in Tk
        itself rather than one introduced here.
        """
        start = self.index(first)
        stop = start if last is None else self.index(last)
        if stop < start:
            return
        removed = self._items[start : stop + 1]
        del self._items[start : stop + 1]
        self._selection = {
            i if i < start else i - len(removed)
            for i in self._selection
            if not start <= i <= stop
        }
        self._active = min(self._active, max(0, len(self._items) - 1))
        self._clamp_view()
        self._redraw()

    def get(self, first: Any, last: Any = None) -> Any:
        """One item, or a tuple of them when ``last`` is given."""
        start = self.index(first)
        if last is None:
            return self._items[start] if 0 <= start < len(self._items) else ""
        return tuple(self._items[start : self.index(last) + 1])

    def size(self) -> int:
        """How many items there are."""
        return len(self._items)

    def _shift_state(self, at: int, count: int) -> None:
        """Move the selection and active item along after an insertion."""
        self._selection = {i + count if i >= at else i for i in self._selection}
        if self._active >= at:
            self._active += count
        self._clamp_view()

    # -------------------------------------------------------------- indices

    def index(self, index: Any) -> int:
        """Resolve one of Tk's index forms to a number.

        Understands integers, ``end``, ``active``, ``anchor`` and ``@x,y``.

        Raises:
            TclError: If the form is not one Tk defines.
        """
        if isinstance(index, int):
            return max(0, min(len(self._items), index))
        text = str(index)
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return max(0, min(len(self._items), int(text)))
        if text in ("end", END):
            return len(self._items)
        if text == "active":
            return self._active
        if text in ("anchor", ANCHOR):
            return self._anchor
        if text.startswith("@"):
            _, _, coords = text.partition("@")
            _, _, y = coords.partition(",")
            return self.nearest(int(y or 0))
        raise TclError(f'bad listbox index "{index}"')

    def nearest(self, y: int) -> int:
        """The item nearest row ``y`` **within this widget**.

        Widget-relative, as Tk's is: "given a y-coordinate within the listbox
        window". Measured on 9.0.2, ``nearest(0)`` is the first visible item
        wherever the listbox sits on screen, and handing it a screen row
        gives nonsense.

        It used to subtract ``winfo_rooty()``, which made the tkinter idiom -
        ``listbox.nearest(event.y)`` in a binding - answer with the first
        item for every click, since the widget-relative y came out negative
        and clamped. Nothing internal depended on it: the click handler works
        the row out itself. TkCurses-9hr.
        """
        row = y - self._text_area().y
        return max(0, min(max(0, len(self._items) - 1), self._top + max(0, row)))

    # ------------------------------------------------------------ selection

    def curselection(self) -> tuple[int, ...]:
        """The selected indices, in order."""
        return tuple(sorted(self._selection))

    def selection_set(self, first: Any, last: Any = None) -> None:
        """Select from ``first`` to ``last`` inclusive."""
        start = self.index(first)
        stop = start if last is None else self.index(last)
        if str(self._options["selectmode"]) in ("browse", "single"):
            self._selection = {start}
        else:
            self._selection |= {
                i
                for i in range(min(start, stop), max(start, stop) + 1)
                if 0 <= i < len(self._items)
            }
        self._notify()

    select_set = selection_set

    def selection_clear(  # type: ignore[override]
        self, first: Any = 0, last: Any = None
    ) -> None:
        """Deselect from ``first`` to ``last`` inclusive.

        The signature disagrees with ``Misc.selection_clear``, which clears
        the X selection and takes keyword arguments. tkinter has the same
        clash for the same reason - a list's selection and the display's
        selection are different things that ended up with one name.
        """
        start = self.index(first)
        stop = (
            len(self._items)
            if last is None and first == 0
            else (start if last is None else self.index(last))
        )
        self._selection -= set(range(min(start, stop), max(start, stop) + 1))
        self._notify()

    select_clear = selection_clear

    def selection_includes(self, index: Any) -> bool:
        """True if ``index`` is selected."""
        return self.index(index) in self._selection

    select_includes = selection_includes

    def selection_anchor(self, index: Any) -> None:
        """Set the anchor a shifted range extends from."""
        self._anchor = self.index(index)

    select_anchor = selection_anchor

    def activate(self, index: Any) -> None:
        """Make ``index`` the active item - where the keyboard is."""
        self._active = max(0, min(max(0, len(self._items) - 1), self.index(index)))
        self.see(self._active)
        self._redraw()

    def _notify(self) -> None:
        """Tell the application the selection changed, and repaint.

        ``<<ListboxSelect>>`` is how tkinter code hears about it, and what a
        form uses to enable its buttons.
        """
        self._redraw()
        self.event_generate("<<ListboxSelect>>")

    # ----------------------------------------------------------- scrolling

    def see(self, index: Any) -> None:
        """Scroll so ``index`` is visible, moving as little as possible."""
        position = self.index(index)
        height = self._text_area().height
        if height <= 0:
            return
        if position < self._top:
            self._top = position
        elif position > self._top + height - 1:
            self._top = position - height + 1
        self._clamp_view()

    def yview(self, *args: Any) -> Any:
        """Get or set the visible window.

        Called with nothing it reports the view as the pair of fractions a
        scrollbar wants. Called by a scrollbar it takes Tk's own arguments -
        ``("moveto", fraction)`` or ``("scroll", count, "units"|"pages")`` -
        which is what lets any scrollbar drive any widget without either
        knowing what the other is.
        """
        if not args:
            return self._view_fractions()
        if len(args) == 1:
            self._top = self.index(args[0])
        elif args[0] == "moveto":
            # Rounded, halves up, as Tk does; this truncated. TkCurses-md5.
            self._top = math.floor(float(args[1]) * len(self._items) + 0.5)
        elif args[0] == "scroll":
            count = int(args[1])
            step = max(1, self._text_area().height) if args[2] == "pages" else 1
            self._top += count * step
        self._clamp_view()
        self._redraw()
        return None

    def xview(self, *args: Any) -> Any:
        """Report or move the horizontal view, in characters.

        Missing outright until TkCurses-019, so a horizontal scrollbar could
        not be attached to a listbox at all. Measured against Tk 9.0.2, a
        10-wide listbox holding a 30-character item:

        * ``xview()`` answers ``(0.0, 0.333...)`` - the offset and the
          offset-plus-width, each over the WIDEST item.
        * a unit is one character; a page is the width less two, never less
          than one (8 at width 10, 18 at 20, 1 at 3).
        * ``moveto`` rounds to the nearest character - 0.49 and 0.51 of 30
          both land on 15 - and a bare index is a character offset. All three
          are clamped so the widest item's end is the furthest you can go.

        The width here is the text's, between the two selection markers.
        """
        if not args:
            return self._horizontal_fractions()
        width = self._body_width()
        if len(args) == 1:
            try:
                left = int(args[0])
            except (TypeError, ValueError):
                raise TclError(f'expected integer but got "{args[0]}"') from None
        elif args[0] == "moveto":
            # Halves round UP, as Tk's do; round() would send 2.5 to 2.
            # TkCurses-5e0.
            left = math.floor(float(args[1]) * self._widest() + 0.5)
        elif args[0] == "scroll":
            what = str(args[2])
            if what not in ("units", "pages"):
                raise TclError(f'bad argument "{what}": must be pages or units')
            step = max(1, width - 2) if what == "pages" else 1
            left = self._left + int(args[1]) * step
        else:
            raise TclError(f'expected integer but got "{args[0]}"')
        self._left = max(0, min(left, self._widest() - width))
        self._publish_view()
        self._redraw()
        return None

    def _widest(self) -> int:
        """The longest item, in cells: what the horizontal view is a fraction of."""
        return max((len(item) for item in self._items), default=0)

    def _body_width(self) -> int:
        """How many cells of each item show, between the selection markers."""
        return max(1, self._text_area().width - 2)

    def _horizontal_fractions(self) -> tuple[float, float]:
        """Where the visible columns are, as two fractions of the widest item.

        The offset is NOT clamped here, and that is Tk's too: measured, scroll
        one character right and then delete the wide item, and ``xview()``
        answers ``(0.2, 1.0)`` over a five-character remainder. It holds until
        the view next moves.
        """
        widest = self._widest()
        if widest <= 0:
            return (0.0, 1.0)
        width = self._body_width()
        return (
            min(1.0, self._left / widest),
            min(1.0, (self._left + width) / widest),
        )

    def _view_fractions(self) -> tuple[float, float]:
        """Where the window is, as two fractions of the whole list."""
        total = len(self._items)
        if total <= 0:
            return (0.0, 1.0)
        height = max(1, self._text_area().height)
        return (self._top / total, min(1.0, (self._top + height) / total))

    def _report_scroll_view(self) -> None:
        """A resize changes how much is visible, so the scrollbar is retold."""
        self._publish_view()

    def _publish_view(self) -> None:
        """Tell the scrollbars where the view is, if any are listening."""
        command = self._options["yscrollcommand"]
        if command is not None:
            first, last = self._view_fractions()
            command(first, last)
        command = self._options["xscrollcommand"]
        if command is not None:
            first, last = self._horizontal_fractions()
            command(first, last)

    def _clamp_view(self) -> None:
        """Keep the visible window inside the list, and report where it is."""
        height = max(1, self._text_area().height)
        self._top = max(0, min(self._top, max(0, len(self._items) - height)))
        self._publish_view()

    def bbox(self, index: Any) -> tuple[int, int, int, int] | None:
        """Where an item is on screen, or None if it is scrolled out of view."""
        position = self.index(index)
        area = self._text_area()
        row = position - self._top
        if not (0 <= row < area.height):
            return None
        return (
            self.winfo_rootx() + area.x,
            self.winfo_rooty() + area.y + row,
            area.width,
            1,
        )

    # ------------------------------------------------------------- painting

    def _text_area(self) -> Rect:
        """Where the items go, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _redraw(self) -> None:
        """Paint the visible items, marking the selected and active ones."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = self._text_area()
        dispatcher = CursesDispatcher.get()
        attribute = self._in_state(
            self._background_attribute() | self._font_attribute()
        )
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if area.is_empty:
                return
            self._clamp_view()
            for row in range(area.height):
                position = self._top + row
                if position >= len(self._items):
                    break
                self._draw_item(dispatcher, window, area, row, position, attribute)

    def _draw_item(
        self,
        dispatcher: CursesDispatcher,
        window: Any,
        area: Rect,
        row: int,
        position: int,
        attribute: int,
    ) -> None:
        """Draw one row: its markers if selected, then its text."""
        selected = position in self._selection
        style = self._selection_attribute(attribute) if selected else attribute
        if position == self._active and self.focus_get() is self and not selected:
            style |= _curses.A_UNDERLINE
        left, right = self._SELECTED_MARKERS if selected else (" ", " ")
        body = clip_text(self._items[position][self._left :], max(0, area.width - 2))
        line = f"{left}{body}".ljust(area.width - 1)[: area.width - 1] + right
        # One write, through the shared writer. The marker used to go on
        # separately with insstr, which INSERTS: it shifted the row one cell
        # right and dropped the last one, and on a bordered listbox the cell
        # it dropped was the border. insstr is right only at the window's
        # genuinely last cell, and _write_line is the one thing that knows
        # when that is.
        self._write_line(dispatcher, window, area.y + row, area.x, line, style)


def _listbox_key(event: Event) -> str | None:
    """Move the active item, or select with the space bar."""
    listbox = event.widget
    if str(listbox._options["state"]) == "disabled":
        return None
    keysym = event.keysym
    height = max(1, listbox._text_area().height)
    moves = {
        "Up": -1,
        "Down": 1,
        "Prior": -height,
        "Next": height,
        "Home": -len(listbox._items),
        "End": len(listbox._items),
    }
    if keysym in moves:
        listbox.activate(listbox._active + moves[keysym])
        if str(listbox._options["selectmode"]) == "browse":
            # browse drags the selection along with the active item, which is
            # what makes a plain list usable with the arrows alone.
            listbox.selection_clear(0, "end")
            listbox.selection_set(listbox._active)
        return "break"
    if keysym == "space":
        _listbox_toggle(listbox, listbox._active, extend=False)
        return "break"
    return None


def _listbox_click(event: Event) -> None:
    """Take the focus and select the row that was clicked."""
    listbox = event.widget
    if str(listbox._options["state"]) == "disabled":
        return
    listbox.focus_set()
    row = listbox._top + max(0, event.y - listbox._text_area().y)
    if row >= len(listbox._items):
        return
    listbox.activate(row)
    _listbox_toggle(listbox, row, extend=bool(event.state & MOD_SHIFT))


def _listbox_toggle(listbox: Listbox, index: int, *, extend: bool) -> None:
    """Apply a selection gesture according to the selection mode."""
    mode = str(listbox._options["selectmode"])
    if mode in ("browse", "single"):
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
    elif mode == "extended" and extend:
        listbox.selection_set(listbox._anchor, index)
    elif index in listbox._selection:
        listbox.selection_clear(index)
    else:
        listbox.selection_set(index)
        listbox.selection_anchor(index)


def _listbox_wheel(event: Event) -> None:
    """Scroll the list by the wheel, without moving the selection."""
    listbox = event.widget
    listbox.yview("scroll", -1 if event.num == 4 else 1, "units")


def _listbox_refresh(event: Event) -> None:
    """Repaint after the focus moved, so the active row shows or stops."""
    event.widget._redraw()


class PanedWindow(_Drawable):
    """A container whose children are divided by sashes a person can drag.

    It is the only widget here that is also a geometry manager: children are
    added with :meth:`add` rather than packed or gridded, and
    :class:`~tkcurses._core.paned.PanedLayout` arranges them. The difference
    from pack is that the arrangement is *stateful* - a sash someone dragged
    stays where they put it, and a later resize works from there rather than
    starting again from what the children ask for.

    Drag a sash with the mouse, or move it with the arrows once the paned
    window has the focus: a terminal user with no mouse would otherwise have
    no way to resize a pane at all.
    """

    #: The sash, drawn along the whole division.
    _SASH: ClassVar[dict[str, str]] = {"horizontal": "│", "vertical": "─"}

    #: Drawn in the middle of the sash when ``showhandle`` is on, so a sash
    #: can be told from a border.
    _HANDLE: ClassVar[dict[str, str]] = {"horizontal": "┃", "vertical": "━"}

    _widget_options: ClassVar[dict[str, Any]] = {
        "orient": "horizontal",
        "relief": "flat",
        "sashwidth": 1,
        "showhandle": True,
        "takefocus": True,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``orient``, ``showhandle``, and the standard options.
        """
        self._active_sash: int | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._paned = PanedLayout(str(self._options["orient"]))
        self._layout_manager = self._paned
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register sash dragging and the keys that move one."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Button-1>", _paned_press)
        bind(name, "<Motion>", _paned_motion)
        bind(name, "<ButtonRelease-1>", _paned_release)
        bind(name, "<Any-Key>", _paned_key)
        # The sash marks itself as the focused thing, so it has to be
        # repainted when the focus arrives and again when it leaves. A click
        # repainted it as a side effect of starting a drag; Tab had nothing
        # to trigger a repaint, so the focus moved in silence.
        bind(name, "<FocusIn>", _paned_refresh)
        bind(name, "<FocusOut>", _paned_refresh)

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-laying the panes out as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if "orient" in given:
            self._paned.orient = str(self._options["orient"])
        if given:
            self._invalidate_layout()
            self._redraw()
        return result

    config = configure

    # ------------------------------------------------------------------ panes

    def add(self, child: Widget, **kw: Any) -> None:
        """Add a pane at the end.

        Args:
            child: The widget to put in it. Must be a child of this window.
            **kw: ``minsize``, ``sticky``, ``width`` or ``height``.
        """
        self._paned.add(child, self._pane_options(kw, child))
        self._manage(child)

    def insert(self, index: Any, child: Widget, **kw: Any) -> None:
        """Add a pane at a position rather than at the end."""
        self._paned.insert(
            self._pane_index(index), child, self._pane_options(kw, child)
        )
        self._manage(child)

    def _manage(self, child: Widget) -> None:
        """Take a child on, the way pack and grid take one on.

        A geometry manager does two things beyond deciding where a child
        goes: it records that it is the one managing it, so a second manager
        cannot also claim it, and it maps the child so there is a window to
        draw into. Adding a pane without this laid the panes out correctly
        and drew nothing at all.
        """
        child._manager = "paned"
        child._map()
        self._invalidate_layout()
        self._redraw()

    def forget(self, child: Widget | None = None) -> None:
        """Take a pane out and unmap its child.

        With no argument this is the ``forget`` every widget has, which stops
        *this* window being managed by its own parent. Tk's PanedWindow has
        the same overloading, for the same reason: both meanings are wanted
        and there is only one name for them.
        """
        if child is None:
            super().forget()
            return
        self._paned.remove(child)
        child._unmap()
        self._invalidate_layout()
        self._redraw()

    def remove(self, child: Widget) -> None:
        """Take a pane out, the spelling Tk also accepts."""
        self.forget(child)

    def panes(self) -> list[str]:
        """The panes' widget paths, in order, as Tk reports them."""
        return [child._w for child in self._paned.slaves()]

    def _pane_options(self, given: dict[str, Any], child: Widget) -> PaneOptions:
        """``child``'s pane options with the keywords it was given applied.

        **Only what is given changes.** Measured on Tk 9.0.2, a pane added with
        ``minsize=10, sticky="n"`` keeps its minsize through
        ``paneconfigure(child, sticky="s")``, and a second ``add`` of the same
        child is the same as a ``paneconfigure``. These were built from the
        keywords alone, so every option left out went back to its default -
        TkCurses-z6pp.

        Raises:
            TclError: If an option is not one a pane takes.
        """
        given = _given(None, given)
        allowed = {"minsize", "sticky", "width", "height"}
        unknown = set(given) - allowed
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        options = self._paned.options_for(child) or PaneOptions()
        if "minsize" in given:
            options = replace(options, minsize=int(given["minsize"]))
        if "sticky" in given:
            options = replace(options, sticky=str(given["sticky"]))
        along = "height" if self._paned.vertical else "width"
        if along in given:
            options = replace(options, size=int(given[along]))
        return options

    def _pane_index(self, index: Any) -> int:
        """Where a pane goes, taking a number, a widget or a widget path."""
        if isinstance(index, int):
            return index
        children = self._paned.slaves()
        for position, child in enumerate(children):
            if child is index or child._w == str(index):
                return position
        return len(children)

    def panecget(self, child: Widget, option: str) -> Any:
        """One option of one pane.

        Raises:
            TclError: If the widget is not a pane here, or the option is not
                one a pane takes.
        """
        options = self._paned.options_for(child)
        if options is None:
            raise TclError(f'not managed by this window: "{child}"')
        if option == "minsize":
            return options.minsize
        if option == "sticky":
            return options.sticky
        if option in ("width", "height"):
            return options.size
        raise TclError(f'unknown option "-{option}"')

    def paneconfigure(self, child: Widget, **kw: Any) -> None:
        """Change one pane's options.

        Raises:
            TclError: If the widget is not a pane here.
        """
        if self._paned.options_for(child) is None:
            raise TclError(f'not managed by this window: "{child}"')
        if kw and not _given(None, kw):
            return  # every option None, which tkinter drops
        self._paned.add(child, self._pane_options(kw, child))
        self._invalidate_layout()
        self._redraw()

    paneconfig = paneconfigure

    # ------------------------------------------------------------------ sashes

    def sash_coord(self, index: int) -> tuple[int, int]:
        """Where a sash begins, in cells relative to this widget."""
        area = self._content_area()
        offset = self._paned.sash_position(index)
        if self._paned.vertical:
            return (area.x, area.y + offset)
        return (area.x + offset, area.y)

    def sash_place(self, index: int, x: int, y: int) -> None:
        """Put a sash at a position, in cells relative to this widget."""
        area = self._content_area()
        position = (y - area.y) if self._paned.vertical else (x - area.x)
        self._paned.move_sash(index, position, self._screen_area())
        self._apply_panes()

    def identify(self, x: int, y: int) -> tuple[int, str] | tuple[()]:
        """Which sash is at a position within this widget, if any.

        Returns ``(index, "sash")`` as Tk does, or ``()`` for anywhere that
        is not on one.
        """
        area = self._content_area()
        offset = (y - area.y) if self._paned.vertical else (x - area.x)
        for index in range(max(0, len(self._paned.slaves()) - 1)):
            at = self._paned.sash_position(index)
            if at <= offset < at + SASH_WIDTH:
                return (index, "sash")
        return ()

    def _screen_area(self) -> Rect:
        """The region the panes are laid out in, in screen cells."""
        return self._content_rect()

    def _content_area(self) -> Rect:
        """The region the panes occupy, relative to this widget's window."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _apply_panes(self) -> None:
        """Re-place the panes after a sash moved, without a full relayout.

        A sash drag must not go through the engine: the engine would ask the
        children what they want and undo the drag, which is the whole reason
        the sizes are remembered.
        """
        self._paned.apply(self, self._screen_area())
        for child in self._paned.slaves():
            child._map()
        self._redraw()

    def _move_sash_by(self, distance: int) -> None:
        """Nudge the active sash, for the keyboard."""
        index = self._active_sash if self._active_sash is not None else 0
        if index >= max(0, len(self._paned.slaves()) - 1):
            return
        self._active_sash = index
        self._paned.move_sash(
            index, self._paned.sash_position(index) + distance, self._screen_area()
        )
        self._apply_panes()

    # -------------------------------------------------------------- painting

    def _redraw(self) -> None:
        """Paint the background, any border, and the sashes between panes."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute() | self._font_attribute()
        area = self._content_area()
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            self._draw_sashes(dispatcher, window, area, attribute)

    def _draw_sashes(
        self, dispatcher: CursesDispatcher, window: Any, area: Rect, attribute: int
    ) -> None:
        """Draw a line down each division, with a handle in the middle of it."""
        if area.is_empty:
            return
        kind = "vertical" if self._paned.vertical else "horizontal"
        line, handle = self._SASH[kind], self._HANDLE[kind]
        show = self._showhandle
        for index in range(max(0, len(self._paned.slaves()) - 1)):
            offset = self._paned.sash_position(index)
            focused = self.focus_get() is self and index == (self._active_sash or 0)
            style = attribute | (_curses.A_REVERSE if focused else 0)
            if self._paned.vertical:
                if not 0 <= offset < area.height:
                    continue
                middle = area.x + area.width // 2
                for column in range(area.width):
                    glyph = handle if show and column == middle else line
                    self._write_line(
                        dispatcher,
                        window,
                        area.y + offset,
                        area.x + column,
                        glyph,
                        style,
                    )
            else:
                if not 0 <= offset < area.width:
                    continue
                middle = area.y + area.height // 2
                for row in range(area.height):
                    glyph = handle if show and row == middle else line
                    self._write_line(
                        dispatcher, window, area.y + row, area.x + offset, glyph, style
                    )

    @property
    def _showhandle(self) -> bool:
        """True while the sash shows a handle in its middle."""
        try:
            return self.getboolean(self._options["showhandle"])
        except TclError:
            return True


def _paned_refresh(event: Event) -> None:
    """Repaint after the focus moved in or out."""
    event.widget._redraw()


def _paned_press(event: Event) -> None:
    """Take the focus, and start dragging a sash if one was clicked.

    The one widget here that does take the focus on a click, and the one
    with no Tk counterpart to be faithful to: Tk's panedwindow has no
    takefocus option at all and no keyboard bindings, so its sashes are
    mouse-only. Ours can be moved with the arrows, which is the only way to
    resize a pane without a mouse, and the focus has to arrive somehow. It
    costs nothing, because this widget binds neither Space nor Return and
    passes on every key it does not use.
    """
    paned = event.widget
    paned.focus_set()
    # The classic method, by name: a ttk subclass's own identify answers
    # ttk's element names, which this binding cannot act on. TkCurses-d5u.
    found = PanedWindow.identify(paned, event.x, event.y)
    paned._active_sash = found[0] if found else None
    paned._redraw()


def _paned_motion(event: Event) -> None:
    """Move the sash being dragged to the pointer."""
    paned = event.widget
    if paned._active_sash is None:
        return
    paned.sash_place(paned._active_sash, event.x, event.y)


def _paned_release(event: Event) -> None:
    """Stop dragging, leaving the sash where it was let go."""
    event.widget._redraw()


def _paned_key(event: Event) -> str | None:
    """Move the active sash with the arrows.

    Along the window's own direction only: the other two arrows would have
    nothing to move, and swallowing them would trap a keyboard user.
    """
    paned = event.widget
    back, forward = ("Up", "Down") if paned._paned.vertical else ("Left", "Right")
    if event.keysym == back:
        paned._move_sash_by(-1)
    elif event.keysym == forward:
        paned._move_sash_by(1)
    elif event.keysym == "Tab" or len(event.keysym) > 1:
        return None
    else:
        return None
    return "break"


class Scrollbar(_Drawable):
    """A scroll control: arrows, a trough, and a thumb showing the view.

    A scrollbar holds no content of its own. It is told where the view is by
    whatever it scrolls, through :meth:`set`, and it tells that thing to move
    by calling its ``command``. Neither end knows anything else about the
    other, which is why any widget with a ``yview`` can be scrolled by one.

    The command is called the way Tk calls it: ``("moveto", fraction)`` when
    the thumb is dragged, and ``("scroll", count, "units" | "pages")`` when an
    arrow or the trough is clicked.
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        # Tk's are real colours; "" draws the scrollbar as it was. See
        # _part_attribute. TkCurses-gm66.4.
        "activebackground": "",
        "troughcolor": "",
        # The active element's relief, which a press sinks, and the width of
        # the arrows' and slider's borders - "" for borderwidth's. A part is
        # one cell, with no edge to draw one on. TkCurses-gm66.5.
        "activerelief": "raised",
        "elementborderwidth": "",
        "command": None,
        # A drag that scrolls only when released, and an arrow or the trough
        # held down scrolling again after repeatdelay, then every
        # repeatinterval; Tk's defaults. TkCurses-gm66.6.
        "jump": 0,
        "orient": "vertical",
        "relief": "sunken",
        "repeatdelay": 300,
        "repeatinterval": 100,
        "takefocus": False,
        "width": 1,
    }

    #: Trough, thumb, and the two arrows, vertical then horizontal.
    _TROUGH = "\u2591"
    _THUMB = "\u2588"
    _ARROWS: ClassVar[dict[str, tuple[str, str]]] = {
        "vertical": ("\u25b2", "\u25bc"),
        "horizontal": ("\u25c4", "\u25ba"),
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``orient``, ``command``, and the standard options.
        """
        self._first = 0.0
        self._last = 1.0
        self._drag_from: tuple[int, int] | None = None
        self._drag_view = (0.0, 1.0)
        self._active_relief: str | None = None
        self._drag_origin = 0.0
        #: The element :meth:`activate` named, or "" for none.
        self._active_element = ""
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the click behaviour for every Scrollbar in this application."""
        # winfo_class() and not the literal: a subclass reporting another name
        # - every ttk widget does - must bind under THAT name or it receives
        # nothing, because binding tags name one class and not a chain.
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Button-1>", _scrollbar_press)
        # The three together are what makes the thumb draggable, and Tk binds
        # exactly these three. The press holds the implicit grab, so a drag
        # that wanders off the bar still arrives here - with coordinates
        # outside it, which is what the arithmetic wants.
        bind(name, "<B1-Motion>", _scrollbar_drag)
        bind(name, "<ButtonRelease-1>", _scrollbar_release)

    @property
    def _vertical(self) -> bool:
        """True if this scrollbar runs up and down."""
        return str(self._options["orient"]) != "horizontal"

    def _apply_requested_size(self) -> None:
        """One cell across, and as long as whatever it is packed beside."""
        thickness = max(1, int(self._options["width"]))
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        if self._vertical:
            self._request_size(thickness + edge, 3 + edge)
        else:
            self._request_size(3 + edge, thickness + edge)

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if {"width", "orient"} & set(given):
            self._apply_requested_size()
            self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    # ---------------------------------------------------------------- state

    def set(self, first: float, last: float) -> None:
        """Record where the view is, as two fractions of the whole.

        Called by the widget being scrolled, not by the application. Values
        outside 0 to 1 are clamped rather than refused: a widget reporting a
        view slightly past its own end is common enough during editing that
        failing on it would be worse than tidying it up.
        """
        self._first = min(max(float(first), 0.0), 1.0)
        self._last = min(max(float(last), self._first), 1.0)
        self._redraw()

    def get(self) -> tuple[float, float]:
        """Where the view is, as ``(first, last)``."""
        return self._first, self._last

    def activate(self, index: str | None = None) -> str | None:
        """Mark one element active, or ask which one is.

        Measured on Tk 9.0.2: only ``arrow1``, ``slider`` and ``arrow2`` can
        be active. Any other name, a trough included, clears it rather than
        raising, and asking with none active answers None.

        The active element is drawn on ``activebackground``, when a program
        gives one (TkCurses-gm66.4), and dim while ``activerelief`` is sunken,
        which a press makes it (TkCurses-gm66.5). Tk's ``scrlbar.tcl`` also
        activates the element under the pointer on ``<Enter>`` and
        ``<Motion>``, which is not bound here.

        Args:
            index: The element to make active. Omitted, nothing changes.

        Returns:
            The active element's name when asked, None when setting.
        """
        if index is None:
            return self._active_element or None
        self._active_element = index if index in ("arrow1", "slider", "arrow2") else ""
        self._redraw()
        return None

    def fraction(self, x: int, y: int) -> float:
        """The fraction of the way along that a position within this widget is.

        Args:
            x: Column within this widget, as an Event reports it.
            y: Row within this widget.
        """
        area = self._trough_bounds()
        if area <= 0:
            return 0.0
        offset = y if self._vertical else x
        return min(max((offset - self._trough_start()) / area, 0.0), 1.0)

    def delta(self, deltax: int, deltay: int) -> float:
        """What fraction of the whole a movement of this many cells is.

        tkinter's own method, and the one a drag is built on: the distance
        the pointer has travelled since the press converts to a change in
        the view's position, which is added to where the view started.

        Args:
            deltax: Cells moved across.
            deltay: Cells moved down.
        """
        area = self._trough_bounds()
        if area <= 0:
            return 0.0
        return (deltay if self._vertical else deltax) / area

    def identify(self, x: int, y: int) -> str:
        """Which part of the scrollbar is at a position within this widget.

        Args:
            x: Column within this widget, as an Event reports it - not a
                screen column. That is the coordinate Tk's identify takes.
            y: Row within this widget.
        """
        offset = y if self._vertical else x
        start = self._trough_start()
        if offset < start:
            return "arrow1"
        if offset >= start + self._trough_bounds():
            return "arrow2"
        thumb_start, thumb_end = self._thumb_range()
        if thumb_start <= offset - start < thumb_end:
            return "slider"
        return "trough1" if offset - start < thumb_start else "trough2"

    # -------------------------------------------------------------- geometry

    def _length(self) -> int:
        """Cells along the scrollbar's own direction.

        ``_border_drawn`` and not ``_bordered``, which is the whole bug a
        person found in UAT 40: a vertical scrollbar is one cell WIDE, so
        ``_border_drawn`` is False - it needs two cells each way - while
        ``_bordered`` is True, because the relief is not flat. This method took
        two rows off for a border, and ``_redraw`` inset the glyphs by nothing,
        so a scrollbar nine rows tall drew seven cells from the top and left two
        rows that still took clicks and still painted their background. A
        restyle made it obvious: the blue ran two rows past the last glyph.

        ``_border_drawn``'s own docstring says everything measuring the space
        left inside has to agree with the painting. This did not.
        """
        edge = 2 * BORDER_WIDTH if self._border_drawn else 0
        span = self._rect.height if self._vertical else self._rect.width
        return max(0, span - edge)

    def _trough_start(self) -> int:
        """Where the trough begins, after the first arrow."""
        return (BORDER_WIDTH if self._border_drawn else 0) + 1

    def _trough_bounds(self) -> int:
        """Cells of trough, once the two arrows have taken theirs."""
        return max(0, self._length() - 2)

    def _thumb_range(self) -> tuple[int, int]:
        """The thumb's extent within the trough, as ``(start, end)``.

        The thumb is never shorter than one cell: a view onto a very long
        document would otherwise round to nothing and leave the scrollbar
        looking broken.
        """
        trough = self._trough_bounds()
        if trough <= 0:
            return (0, 0)
        start = int(self._first * trough)
        end = max(start + 1, int(self._last * trough))
        return (min(start, trough - 1), min(end, trough))

    # -------------------------------------------------------------- painting

    def _redraw(self) -> None:
        """Paint the arrows, the trough, and the thumb."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        length = self._length()
        if length <= 0:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute()
        first_arrow, last_arrow = self._ARROWS[
            "vertical" if self._vertical else "horizontal"
        ]
        trough = self._trough_bounds()
        thumb_start, thumb_end = self._thumb_range()
        cells = [(first_arrow, self._part_attribute("arrow1", attribute))]
        thumb = self._part_attribute("slider", attribute)
        empty = self._part_attribute("trough", attribute)
        for index in range(trough):
            cells.append(
                (self._THUMB, thumb)
                if thumb_start <= index < thumb_end
                else (self._TROUGH, empty)
            )
        cells.append((last_arrow, self._part_attribute("arrow2", attribute)))

        edge = BORDER_WIDTH if self._border_drawn else 0
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            # A cell at a time, each in its part's colours. One write of the
            # whole row was enough while every part looked the same.
            for offset, (cell, look) in enumerate(cells):
                row, column = (offset, 0) if self._vertical else (0, offset)
                self._write_line(
                    dispatcher, window, edge + row, edge + column, cell, look
                )

    def _part_attribute(self, part: str, attribute: int) -> int:
        """How one part is drawn: ``troughcolor`` behind the trough, and
        ``activebackground`` behind the element ``activate`` names.

        Both "" by default, Tk's being real colours: the scrollbar as it was.
        TkCurses-gm66.4.
        """
        if part == "trough":
            return self._coloured(attribute, "", self._options["troughcolor"])
        if part == self._active_element:
            attribute = self._coloured(attribute, "", self._options["activebackground"])
            return attribute | _part_relief(self._options["activerelief"])
        return attribute


def _scrollbar_press(event: Event) -> None:
    """Scroll by whatever part of the scrollbar was pressed.

    The Scrollbar's mouse bindings follow Tk's ``scrlbar.tcl`` (see
    ARCHITECTURE.md). A press on the thumb moves nothing. Tk remembers where the press landed
    and where the view was, and waits for the pointer to move - measured
    against Tk 9.0, where pressing the slider and releasing it without moving
    calls the command not at all.
    """
    bar = event.widget
    if not _is_ttk(bar):
        # tk::ScrollButtonDown: the active element sinks until the release.
        bar._active_relief = str(bar.cget("activerelief"))
        bar.configure(activerelief=SUNKEN)
    command = bar._options["command"]
    if command is None:
        return
    # The classic method, by name: a ttk subclass's own identify answers
    # ttk's element names, which this binding cannot act on. TkCurses-d5u.
    part = Scrollbar.identify(bar, event.x, event.y)
    if part == "slider":
        bar._drag_from = (event.x, event.y)
        bar._drag_origin = bar._first
        bar._drag_view = (bar._first, bar._last)
        return
    _scrollbar_select(bar, part, "initial")


#: What each part of a scrollbar scrolls by, as ``tk::ScrollSelect`` has it.
_SCROLLBAR_STEPS = {
    "arrow1": (-1, "units"),
    "arrow2": (1, "units"),
    "trough1": (-1, "pages"),
    "trough2": (1, "pages"),
}


def _scrollbar_select(bar: Any, part: str, repeat: str) -> None:
    """Scroll for a pressed part, and keep on while it is held.

    Tk's ``tk::ScrollSelect``: the first step at once, the second after
    ``repeatdelay``, the rest every ``repeatinterval``. The part is the one
    first pressed, so a trough held down goes on paging after the thumb has
    passed the pointer, as Tk's does. An interval of 0 stops the repeat
    rather than scheduling it at once for ever, which Tk would.
    """
    step = _SCROLLBAR_STEPS.get(part)
    command = bar._options["command"]
    if step is None or command is None:
        return
    command("scroll", *step)
    wait = _repeat_option(
        bar, "repeatdelay" if repeat == "initial" else "repeatinterval"
    )
    if wait > 0:
        _repeat_after(bar, wait, _scrollbar_select, bar, part, "again")


def _scrollbar_drag(event: Event) -> None:
    """Move the view by however far the thumb has been dragged.

    The view follows the pointer rather than jumping to it: the offset within
    the thumb where the press landed is preserved, because what moves is the
    *distance* travelled rather than the position arrived at.
    """
    bar = event.widget
    origin = bar._drag_from
    command = bar._options["command"]
    if origin is None or command is None:
        return
    moved = bar.delta(event.x - origin[0], event.y - origin[1])
    if _jumps(bar):
        # tk::ScrollDrag with -jump: the thumb moves and the view waits.
        first, last = bar._drag_view
        bar.set(first + moved, last + moved)
        return
    command("moveto", min(max(bar._drag_origin + moved, 0.0), 1.0))


def _jumps(bar: Any) -> bool:
    """True if a classic scrollbar's ``jump`` holds the scroll for the release."""
    if _is_ttk(bar):
        return False
    try:
        return bool(bar.getboolean(bar._options["jump"]))
    except TclError:
        return False


def _scrollbar_release(event: Event) -> None:
    """End a press: the repeat stops, and a jump drag scrolls at last.

    ``tk::ScrollButtonUp``, which puts back the relief the press sank, and
    ``tk::ScrollEndDrag``, which scrolls to where a ``jump`` drag ended.
    Without ``jump`` the drag has scrolled already and nothing more is done.
    """
    bar = event.widget
    _cancel_repeat(bar)
    origin, bar._drag_from = bar._drag_from, None
    command = bar._options["command"]
    if origin is not None and command is not None and _jumps(bar):
        moved = bar.delta(event.x - origin[0], event.y - origin[1])
        command("moveto", min(max(bar._drag_origin + moved, 0.0), 1.0))
    relief = bar._active_relief
    if relief is not None:
        bar._active_relief = None
        bar.configure(activerelief=relief)


class Scale(_Drawable):
    """A number chosen by sliding a handle along a trough.

    The value is the widget's own, not the caller's, so ``get`` and ``set``
    work with no variable at all; a ``variable`` makes it visible to other
    widgets in the usual way, and the two are kept in step both directions.

    ``from_`` sits at the left of a horizontal scale and at the *top* of a
    vertical one, which is Tk's arrangement and the reason a vertical scale
    counts downwards by default. Naming a ``to`` below ``from_`` reverses the
    scale rather than failing - a volume control that runs 10 to 0 is a real
    thing, and every conversion here works from the two ends rather than
    assuming which is larger.

    ``resolution`` is the step the value snaps to, measured from ``from_``.
    Everything that moves the handle goes through that snap, so a scale with
    a resolution of 5 cannot be left holding 7 by any route - including a
    variable written from elsewhere.

    Focus is shown by caps at the ends of the trough, ``[`` and ``]``. Room
    for them is reserved whether or not they are showing, so nothing moves
    when the focus arrives; it is the same bargain Button makes with its
    markers, and for the same reason - a terminal cannot be relied on for
    colour.
    """

    #: Trough and handle, the same two glyphs a Scrollbar uses, because they
    #: are the same two things.
    _TROUGH = "░"
    _SLIDER = "█"

    #: Drawn at the ends of the trough while the scale has the focus.
    _FOCUS_CAPS = ("[", "]")

    _widget_options: ClassVar[dict[str, Any]] = {
        "highlightthickness": 1,  # Tk's default; see Widget._widget_options
        # The handle while active or dragged, and the trough. Tk's are real
        # colours; "" draws the scale as it was. TkCurses-gm66.4.
        "activebackground": "",
        "troughcolor": "",
        "bigincrement": 0,
        "command": None,
        "digits": 0,
        "font": "",
        "from": 0.0,
        "label": "",
        "length": 20,
        "orient": "vertical",
        "resolution": 1.0,
        "showvalue": True,
        # The handle's length in cells, along the trough, and its relief,
        # which the press sinks while it is dragged. Tk's length is 30
        # pixels; one cell is the handle as it was. TkCurses-gm66.5.
        "sliderlength": 1,
        "sliderrelief": "raised",
        # A trough held down steps again after repeatdelay, then every
        # repeatinterval; Tk's defaults. TkCurses-gm66.6.
        "repeatdelay": 300,
        "repeatinterval": 100,
        "state": "normal",
        "takefocus": True,
        "tickinterval": 0,
        "to": 100.0,
        "variable": None,
        "width": 1,
    }

    def __init__(
        self,
        master: Misc | None = None,
        cnf: dict[str, Any] | None = None,
        *,
        name: str | None = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            cnf: Options as a dictionary, merged with the keywords.
            name: Path component, generated when omitted.
            **kw: ``from_``, ``to``, ``resolution``, ``orient``, ``length``,
                ``width``, ``label``, ``showvalue``, ``tickinterval``,
                ``variable``, ``command``, ``digits``, ``bigincrement``,
                ``state``, and the standard options.
        """
        self._dragging = False
        #: Cells from the handle's middle to where it was taken hold of:
        #: Tk's Priv(deltaX), so a drag does not jump the handle.
        self._drag_lead = 0
        self._slider_relief: str | None = None
        self._syncing = False
        self._variable_trace: tuple[Variable, str] | None = None
        super().__init__(master, cnf, name=name, **kw)
        self._value = self._snap(self._range()[0])
        self._follow_variable()
        self._apply_requested_size()
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the default behaviour for every Scale in this application.

        Under ``winfo_class()`` rather than the literal ``"Scale"``: binding
        tags name one class, so ``ttk.Scale`` - which reports ``TScale`` -
        would otherwise match none of these and answer no gesture at all.
        The same cure Menubutton carries for OptionMenu.
        """
        name = self.winfo_class()
        if name in self.tk.bound_classes:
            return
        self.tk.bound_classes.add(name)
        bind = self.bind_class
        bind(name, "<Button-1>", _scale_press)
        bind(name, "<Button-2>", _scale_jump)
        bind(name, "<ButtonRelease-2>", _scale_release)
        # A drag arrives as Motion: curses reports motion-with-a-button, and
        # there is no Button1 modifier to match a <B1-Motion> against. The
        # press holds the implicit grab, so every one of these belongs to
        # this scale however far the pointer has wandered.
        bind(name, "<Motion>", _scale_motion)
        bind(name, "<ButtonRelease-1>", _scale_release)
        bind(name, "<Any-Key>", _scale_key)
        bind(name, "<FocusIn>", _scale_refresh)
        bind(name, "<FocusOut>", _scale_refresh)

    # --------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = _given(cnf, kw)
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if "variable" in given:
            self._follow_variable()
        if {"from", "to", "resolution"} & set(given):
            # The value may no longer be reachable: a range that moved under
            # it has to pull it back rather than leave the handle off the end.
            self.set(self._value)
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()
        return result

    config = configure

    @property
    def _vertical(self) -> bool:
        """True if this scale runs up and down."""
        return str(self._options["orient"]) != "horizontal"

    def _range(self) -> tuple[float, float]:
        """The two ends, in the order the options name them."""
        return float(self._options["from"]), float(self._options["to"])

    def _thickness(self) -> int:
        """Cells across the trough, at right angles to its length."""
        return max(1, int(self._options["width"]))

    @property
    def _showvalue(self) -> bool:
        """True while the current value is drawn beside the handle."""
        try:
            return self.getboolean(self._options["showvalue"])
        except TclError:
            return True

    # ----------------------------------------------------------- the variable

    def _follow_variable(self) -> None:
        """Track the ``variable``, dropping any previous one."""
        if self._variable_trace is not None:
            previous, handle = self._variable_trace
            previous.trace_remove("write", handle)
            self._variable_trace = None
        variable = self._options["variable"]
        if variable is None:
            return
        handle = variable.trace_add("write", lambda *_: self._variable_changed())
        self._variable_trace = (variable, handle)
        self._variable_changed()

    def _variable_changed(self) -> None:
        """Take the variable's value, unless this scale is what changed it.

        Without the guard the two chase each other: the scale writes the
        variable, whose trace writes the scale, which snaps and writes back.
        """
        if self._syncing:
            return
        variable = self._options["variable"]
        if variable is None:
            return
        with contextlib.suppress(TclError, TypeError, ValueError):
            self.set(float(variable.get()))

    def _publish(self) -> None:
        """Write the value back to the variable, if there is one."""
        variable = self._options["variable"]
        if variable is None:
            return
        self._syncing = True
        try:
            # As text, which is how Tcl holds it: writing the float 6.0 into
            # an IntVar leaves it holding something it cannot read back.
            variable.set(self._format(self._value))
        finally:
            self._syncing = False

    # ---------------------------------------------------------------- value

    def get(self) -> float:
        """The value the handle is on."""
        return self._value

    def set(self, value: float) -> None:
        """Move the handle to ``value``, snapped to the resolution and clamped.

        Calls the ``command`` only when the value actually changes, which is
        what Tk does and what keeps a drag along one cell from firing it on
        every motion event.
        """
        snapped = self._snap(float(value))
        changed = snapped != self._value
        self._value = snapped
        self._publish()
        self._redraw()
        if changed:
            command = self._options["command"]
            if command is not None:
                command(self._format(snapped))

    def _snap(self, value: float) -> float:
        """Round to the nearest step and pull inside the two ends.

        Steps are measured from ``from_``, as Tk measures them, so a scale
        from 1 to 10 by 2 offers 1, 3, 5 and not 2, 4, 6.
        """
        low, high = self._range()
        resolution = float(self._options["resolution"])
        if resolution > 0:
            value = low + round((value - low) / resolution) * resolution
            # round() leaves floating-point dust on anything but integers;
            # a scale showing 0.30000000000000004 is a scale nobody trusts.
            value = round(value, 10)
        return min(max(value, min(low, high)), max(low, high))

    def _format(self, value: float) -> str:
        """The value as text, with as many decimals as it actually has.

        ``digits`` wins when it is set, as it does in Tk; otherwise the
        resolution says how precise the value can be, and showing more than
        that is noise.
        """
        digits = int(self._options["digits"])
        if digits > 0:
            return f"{value:.{digits}g}"
        resolution = abs(float(self._options["resolution"]))
        if resolution == 0 or resolution != int(resolution):
            text = f"{value:.4f}".rstrip("0").rstrip(".")
            return text or "0"
        return str(round(value))

    # -------------------------------------------------------------- geometry

    def _content_area(self) -> Rect:
        """What is left of the widget after its border and padding."""
        edge = BORDER_WIDTH if self._border_drawn else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _value_width(self) -> int:
        """Cells the widest value this scale can show would need.

        The two ends are not enough. A scale from 0 to 1 by 0.1 reads "0"
        and "1" at its ends and "0.5" everywhere between, so measuring the
        ends alone reserves one cell and leaves the value nowhere to go -
        which on a vertical scale means it is simply not drawn.
        """
        low, high = self._range()
        resolution = abs(float(self._options["resolution"]))
        candidates = [low, high]
        if resolution:
            candidates += [self._snap(low + resolution), self._snap(high - resolution)]
        return max(len(self._format(value)) for value in candidates)

    def _head_rows(self) -> int:
        """Rows above the trough, for the label and - horizontally - the value."""
        if self._vertical:
            return 1 if str(self._options["label"]) else 0
        return 1 if str(self._options["label"]) or self._showvalue else 0

    def _tick_span(self) -> int:
        """Room the tick numbers need: a row below, or a column to the left."""
        if not float(self._options["tickinterval"]):
            return 0
        return 1 if not self._vertical else self._value_width() + 1

    def _trough_span(self) -> int:
        """Cells of trough available, after the caps have taken theirs."""
        area = self._content_area()
        if self._vertical:
            return max(0, area.height - self._head_rows() - 2)
        return max(0, area.width - 2)

    def _apply_requested_size(self) -> None:
        """Ask for the trough plus whatever is drawn around it."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        length = max(1, int(self._options["length"]))
        label = len(str(self._options["label"]))
        if self._vertical:
            across = self._thickness() + self._tick_span()
            if self._showvalue:
                across += self._value_width() + 1
            width = max(across, label)
            height = length + 2 + self._head_rows()
        else:
            width = max(length + 2, label + self._value_width() + 1)
            height = self._thickness() + self._head_rows() + self._tick_span()
        self._request_size(width + 2 * padx + edge, height + 2 * pady + edge)

    def _trough_origin(self) -> tuple[int, int]:
        """Where the first cell of the trough sits within the widget."""
        area = self._content_area()
        if self._vertical:
            across = self._tick_span()
            if self._showvalue:
                across += self._value_width() + 1
            return (area.x + across, area.y + self._head_rows() + 1)
        return (area.x + 1, area.y + self._head_rows())

    def _slider_cells(self) -> int:
        """How many cells the handle covers: ``sliderlength``, within the trough.

        Never less than one, which Tk also keeps a negative length from going
        below, and never more than the trough has.
        """
        length = _as_int(self._options["sliderlength"], 1)
        return max(1, min(length, self._trough_span()))

    def _slider_lead(self) -> int:
        """Cells of handle before its middle one, the cell a value is at."""
        return (self._slider_cells() - 1) // 2

    def _positions(self) -> int:
        """How many places the handle can stand: the trough less its length.

        Tk's arithmetic, in cells: the slider's middle travels the trough's
        length less the slider's, so a long handle still reaches both ends.
        """
        return max(1, self._trough_span() - self._slider_cells() + 1)

    def _offset_for(self, value: float) -> int:
        """Which trough cell a value falls on: the handle's middle cell there."""
        positions = self._positions()
        low, high = self._range()
        if positions <= 1 or high == low:
            return self._slider_lead()
        fraction = (value - low) / (high - low)
        start = min(max(round(fraction * (positions - 1)), 0), positions - 1)
        return start + self._slider_lead()

    def _value_at(self, offset: int) -> float:
        """The value whose handle has its middle at a trough cell."""
        positions = self._positions()
        low, high = self._range()
        if positions <= 1:
            return self._snap(low)
        start = offset - self._slider_lead()
        fraction = min(max(start, 0), positions - 1) / (positions - 1)
        return self._snap(low + fraction * (high - low))

    def _on_slider(self, offset: int) -> bool:
        """True if a trough cell is one the handle covers."""
        start = self._offset_for(self._value) - self._slider_lead()
        return start <= offset < start + self._slider_cells()

    def coords(self, value: float | None = None) -> tuple[int, int]:
        """Where the handle for a value sits, relative to this widget.

        Args:
            value: The value to locate. The current one when omitted.
        """
        if value is None:
            value = self._value
        x, y = self._trough_origin()
        offset = self._offset_for(self._snap(float(value)))
        return (x, y + offset) if self._vertical else (x + offset, y)

    def identify(self, x: int, y: int) -> str:
        """Which part of the scale is at a screen position.

        Args:
            x: Column within this widget, as an Event reports it - not a
                screen column. That is the coordinate Tk's identify takes.
            y: Row within this widget.

        Returns:
            ``"slider"``, ``"trough1"`` for the side towards ``from_``,
            ``"trough2"`` for the side towards ``to``, or ``""`` for anywhere
            else on the widget - the label, the ticks, or the caps.
        """
        origin_x, origin_y = self._trough_origin()
        offset = (y - origin_y) if self._vertical else (x - origin_x)
        if not 0 <= offset < self._trough_span():
            return ""
        if self._on_slider(offset):
            return "slider"
        return "trough1" if offset < self._offset_for(self._value) else "trough2"

    # -------------------------------------------------------------- painting

    def _redraw(self) -> None:
        """Paint the label, the value, the trough and its handle, and the ticks."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute() | self._font_attribute()
        # Tk shows an active scale by its handle, in activebackground. Given
        # one, that is how it is shown here too, instead of reversed whole.
        if not (self._active_handle() and self._handle_coloured()):
            attribute = self._in_state(attribute)
        with contextlib.suppress(_curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._border_drawn:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            self._draw_head(dispatcher, window, attribute)
            self._draw_trough(dispatcher, window, attribute)
            self._draw_ticks(dispatcher, window, attribute)

    def _draw_head(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """The label, and the value where the orientation puts it.

        Horizontally the value rides above the handle, as Tk's does, so it
        reads as belonging to the handle rather than to the widget. There is
        no room for that vertically, so it goes in its own column beside the
        handle's row instead.
        """
        area = self._content_area()
        label = str(self._options["label"])
        if label and area.width > 0:
            self._write_line(
                dispatcher,
                window,
                area.y,
                area.x,
                clip_text(label, area.width),
                attribute,
            )
        if not self._showvalue:
            return
        text = self._format(self._value)
        origin_x, origin_y = self._trough_origin()
        if self._vertical:
            column = origin_x - len(text) - 1
            row = origin_y + self._offset_for(self._value)
        else:
            column = origin_x + self._offset_for(self._value)
            row = origin_y - 1
            column = min(column, area.x + area.width - len(text))
            # The label shares this row, so the value is pushed clear of it
            # rather than written through it - "V0lume" is not a label.
            if label:
                column = max(column, area.x + len(label) + 1)
        if row < area.y or column < area.x:
            return
        self._write_line(
            dispatcher, window, row, column, clip_text(text, area.width), attribute
        )

    def _draw_trough(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """The trough, the handle on it, and the focus caps at its ends."""
        span = self._trough_span()
        if span <= 0:
            return
        origin_x, origin_y = self._trough_origin()
        empty = self._coloured(attribute, "", self._options["troughcolor"])
        held = attribute
        if self._active_handle() and self._handle_coloured():
            held = self._coloured(attribute, "", self._options["activebackground"])
        held |= _part_relief(self._options["sliderrelief"])
        cells = [
            (self._SLIDER, held) if self._on_slider(offset) else (self._TROUGH, empty)
            for offset in range(span)
        ]
        focused = self.focus_get() is self
        left, right = self._FOCUS_CAPS if focused else (" ", " ")
        if self._vertical:
            self._write_line(
                dispatcher, window, origin_y - 1, origin_x, left, attribute
            )
            for thick in range(self._thickness()):
                for offset, (cell, look) in enumerate(cells):
                    self._write_line(
                        dispatcher,
                        window,
                        origin_y + offset,
                        origin_x + thick,
                        cell,
                        look,
                    )
            self._write_line(
                dispatcher, window, origin_y + span, origin_x, right, attribute
            )
        else:
            for thick in range(self._thickness()):
                self._write_line(
                    dispatcher, window, origin_y + thick, origin_x - 1, left, attribute
                )
                for offset, (cell, look) in enumerate(cells):
                    self._write_line(
                        dispatcher,
                        window,
                        origin_y + thick,
                        origin_x + offset,
                        cell,
                        look,
                    )
                self._write_line(
                    dispatcher,
                    window,
                    origin_y + thick,
                    origin_x + span,
                    right,
                    attribute,
                )

    def _active_handle(self) -> bool:
        """True while the handle is active: the state says so, or it is held.

        Tk's ``tk::ScaleActivate``, in ``scale.tcl``, makes the scale active
        while the pointer is over its handle, which it is for the whole of a
        drag. Here there is no hover, so only the drag is seen.
        """
        return str(self._options["state"]) == "active" or self._dragging

    def _handle_coloured(self) -> bool:
        """True if ``activebackground`` is given and the terminal can show it."""
        return bool(self._options["activebackground"]) and self.tk.colors is not None

    def _draw_ticks(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Numbers at every ``tickinterval`` along the trough.

        Drawn only where they fit without overwriting the tick before them,
        so a long range on a short trough thins out rather than turning into
        a row of collided digits.
        """
        interval = abs(float(self._options["tickinterval"]))
        if not interval:
            return
        span = self._trough_span()
        if span <= 0:
            return
        area = self._content_area()
        origin_x, origin_y = self._trough_origin()
        low, high = self._range()
        step = interval if high >= low else -interval
        taken = -1
        value = low
        for _ in range(1000):
            if (step > 0 and value > high) or (step < 0 and value < high):
                break
            text = self._format(value)
            offset = self._offset_for(value)
            if self._vertical:
                row, column = origin_y + offset, area.x
                if row > taken:
                    self._write_line(
                        dispatcher,
                        window,
                        row,
                        column + self._value_width() - len(text),
                        text,
                        attribute,
                    )
                    taken = row
            else:
                row = origin_y + self._thickness()
                column = min(origin_x + offset, area.x + area.width - len(text))
                if column > taken:
                    self._write_line(dispatcher, window, row, column, text, attribute)
                    taken = column + len(text)
            value += step


def _scale_press(event: Event) -> None:
    """Take hold of the handle, or step towards a click on the trough.

    Tk's ``tk::ScaleButtonDown``: the trough steps one ``resolution`` at a
    time, and again while it is held (``tk::ScaleIncrement``); only the
    handle drags, from where it was taken hold of. Button 2 jumps the handle
    to the pointer instead (``_scale_jump``). A ttk scale jumps on button 1,
    as it always has here.

    The focus stays where it was, as it does in Tk: the arrows move a scale
    that has the focus, and a click is already a way of setting the value.
    """
    scale = event.widget
    if scale._disabled:
        return
    if _is_ttk(scale):
        _scale_jump(event)
        return
    x = event.x_root - scale.winfo_rootx()
    y = event.y_root - scale.winfo_rooty()
    part = Scale.identify(scale, x, y)
    if part == "slider":
        scale._dragging = True
        scale._drag_lead = _scale_offset(scale, event) - scale._offset_for(scale._value)
        _scale_sink(scale)
    elif part == "trough1":
        _scale_increment(scale, "up", "initial")
    elif part == "trough2":
        _scale_increment(scale, "down", "initial")


def _scale_jump(event: Event) -> None:
    """Put the handle under the pointer and drag it from there.

    Tk's ``tk::ScaleButton2Down``, on button 2, which is how a classic scale
    is set by a click in Tk; ttk's ``ttk::scale::Jump`` does the same.
    """
    scale = event.widget
    if scale._disabled:
        return
    scale._dragging = True
    scale._drag_lead = 0
    _scale_move_to(scale, event)


def _scale_increment(scale: Scale, direction: str, repeat: str) -> None:
    """Step the value one ``resolution``, and keep stepping while held.

    Tk's ``tk::ScaleIncrement``, with ``little`` steps: ``up`` is towards
    ``from_``, whichever end that is. The second step comes after
    ``repeatdelay`` and the rest every ``repeatinterval``; an interval of 0
    stops the repeat rather than spinning, which Tk's would. Tk's catching up
    after a slow ``command`` is not done: the after-queue here waits for the
    command to finish before it counts.
    """
    step = abs(float(scale._options["resolution"]))
    backwards = float(scale._options["from"]) > float(scale._options["to"])
    if backwards != (direction == "up"):
        step = -step
    scale.set(scale.get() + step)
    wait = _repeat_option(
        scale, "repeatdelay" if repeat == "initial" else "repeatinterval"
    )
    if wait > 0:
        _repeat_after(scale, wait, _scale_increment, scale, direction, "again")


def _scale_sink(scale: Scale) -> None:
    """Sink the handle while it is held, as Tk's ``tk::ScaleButtonDown`` does:
    raised becomes sunken and ridge groove, the rest stay as they are."""
    relief = str(scale.cget("sliderrelief"))
    scale._slider_relief = relief
    held = {RAISED: SUNKEN, RIDGE: GROOVE}.get(relief)
    if held is not None:
        scale.configure(sliderrelief=held)


def _scale_motion(event: Event) -> None:
    """Follow the pointer while the handle is being dragged: ``tk::ScaleDrag``."""
    scale = event.widget
    if scale._dragging and not scale._disabled:
        scale.set(scale._value_at(_scale_offset(scale, event) - scale._drag_lead))


def _scale_release(event: Event) -> None:
    """Stop repeating and dragging, wherever the pointer ended up, and put the
    relief back as ``tk::CancelRepeat`` and ``tk::ScaleEndDrag`` do."""
    scale = event.widget
    _cancel_repeat(scale)
    scale._dragging = False
    relief = scale._slider_relief
    if relief is not None:
        scale._slider_relief = None
        scale.configure(sliderrelief=relief)


def _scale_move_to(scale: Scale, event: Event) -> None:
    """Set the value from a pointer position on the trough."""
    scale.set(scale._value_at(_scale_offset(scale, event)))


def _scale_offset(scale: Scale, event: Event) -> int:
    """Which trough cell the pointer is level with."""
    origin_x, origin_y = scale._trough_origin()
    if scale._vertical:
        return event.y_root - scale.winfo_rooty() - origin_y
    return event.x_root - scale.winfo_rootx() - origin_x


def _scale_key(event: Event) -> str | None:
    """Move the handle by the keyboard.

    The arrows along the scale's own direction step by the resolution, with
    Control stepping by ``bigincrement``; Home and End go to the two ends.
    Anything else is left alone so that Tab still leaves the widget.
    """
    scale = event.widget
    if scale._disabled:
        return None
    low, high = scale._range()
    step = abs(float(scale._options["resolution"])) or 1.0
    big = abs(float(scale._options["bigincrement"])) or abs(high - low) / 10 or step
    if event.state & MOD_CTRL:
        step = big
    if high < low:
        step = -step
    back, forward = ("Up", "Down") if scale._vertical else ("Left", "Right")
    keysym = event.keysym
    if keysym == back:
        scale.set(scale._value - step)
    elif keysym == forward:
        scale.set(scale._value + step)
    elif keysym == "Prior":
        scale.set(scale._value - (big if high >= low else -big))
    elif keysym == "Next":
        scale.set(scale._value + (big if high >= low else -big))
    elif keysym == "Home":
        scale.set(low)
    elif keysym == "End":
        scale.set(high)
    else:
        return None
    return "break"


def _scale_refresh(event: Event) -> None:
    """Repaint after the focus moved in or out."""
    event.widget._redraw()
