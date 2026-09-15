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

"""The curses API, drawn on the same screen the widgets use.

The project's premise has two halves. A tkinter program runs on this layer;
this module is so that a curses program can too, and so that the two can be
the same program - a curses application that opens a tkinter dialog, or a
tkinter application with one pane drawn the old way.

**This is not a reimplementation of curses.** The backend already is curses.
What this is, is a facade over :class:`~tkcurses._core.screen.CursesScreen`
and :class:`~tkcurses._core.screen.ScreenBuffer` that presents them the way
curses presents them, so a curses program gets this layer's double-buffered
painting, its resize handling and its colour depth detection without being
written any differently.

Anything not defined here is forwarded to the standard library's curses, so
every constant - ``A_BOLD``, ``KEY_UP``, ``COLOR_RED``, ``ACS_HLINE``,
``error`` - is available under the name it always had, and stays current with
whatever Python provides. The cost of that convenience is that a function
this module has not wrapped operates on the real terminal directly rather
than through the buffer; the ones that matter are wrapped.

Two corrections to what ARCHITECTURE.md specified, both of which the colour
cycle established:

``has_colors()`` and ``can_change_color()`` were to answer True always. They
do not. A terminal has one of five colour depths and a vt100 has none, so
both delegate to the real curses and tell the truth. A curses program asks
those questions precisely so it can draw differently, and a compatibility
layer that lies to it is worse than one that is missing.

Importing this module is safe for the rest of the package, and that took
arranging. ``tkcurses.curses`` is a submodule, so importing it makes Python
bind it as the attribute ``curses`` on the ``tkcurses`` package - which is
``tkcurses/__init__.py``'s own global namespace. That module now imports the
standard library as ``_curses`` for exactly this reason.
"""

from __future__ import annotations

import contextlib
import curses as _curses
from typing import TYPE_CHECKING, Any

from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.screen import BLANK, CursesScreen, ScreenBuffer

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Window",
    "beep",
    "can_change_color",
    "cbreak",
    "color_pair",
    "curs_set",
    "doupdate",
    "echo",
    "endwin",
    "flash",
    "flushinp",
    "has_colors",
    "init_pair",
    "initscr",
    "isendwin",
    "keyname",
    "napms",
    "newwin",
    "nl",
    "nocbreak",
    "noecho",
    "nonl",
    "noraw",
    "raw",
    "start_color",
    "unctrl",
    "ungetch",
    "wrapper",
]


def __getattr__(name: str) -> Any:
    """Forward anything not defined here to the standard library's curses.

    Which is where every constant comes from. Listing ``A_BOLD`` and the two
    hundred ``KEY_`` names by hand would be two hundred chances to mistype
    one and a list that goes stale the first time Python adds a key.
    """
    try:
        return getattr(_curses, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


# --------------------------------------------------------------------------
# The screen
# --------------------------------------------------------------------------

#: What :meth:`Window.border` draws with when a side is left to the default,
#: in curses' own order: the two sides, the two rails, then the corners.
#: These are the characters the widgets draw borders with, so a curses window
#: and a widget beside it meet at the same glyph.
BORDER_DEFAULTS = (
    "\u2502",
    "\u2502",
    "\u2500",
    "\u2500",
    "\u250c",
    "\u2510",
    "\u2514",
    "\u2518",
)

#: ACS names in the order :data:`BORDER_DEFAULTS` gives their characters, so
#: a caller that passes ACS_VLINE gets the box-drawing character for it.
_ACS_NAMES = {
    "ACS_VLINE": "\u2502",
    "ACS_HLINE": "\u2500",
    "ACS_ULCORNER": "\u250c",
    "ACS_URCORNER": "\u2510",
    "ACS_LLCORNER": "\u2514",
    "ACS_LRCORNER": "\u2518",
    "ACS_LTEE": "\u251c",
    "ACS_RTEE": "\u2524",
    "ACS_TTEE": "\u252c",
    "ACS_BTEE": "\u2534",
    "ACS_PLUS": "\u253c",
    "ACS_CKBOARD": "\u2592",
    "ACS_BLOCK": "\u2588",
    "ACS_DIAMOND": "\u25c6",
    "ACS_DEGREE": "\u00b0",
    "ACS_BULLET": "\u00b7",
    "ACS_LARROW": "\u2190",
    "ACS_RARROW": "\u2192",
    "ACS_DARROW": "\u2193",
    "ACS_UARROW": "\u2191",
}


def _acs_character(value: int) -> str:
    """The box-drawing character an ACS value stands for.

    The ACS constants only exist once initscr has run, so the lookup is built
    on demand and falls back to the low byte - which is the VT100 charset
    letter, and the best available answer when there is no screen to ask.
    """
    for name, character in _ACS_NAMES.items():
        if getattr(_curses, name, None) == value:
            return character
    return chr(value & 0xFF)


#: The screen this module is drawing on, between initscr() and endwin().
_screen: CursesScreen | None = None

#: The window covering it, which is what initscr() hands back.
_stdscr: Window | None = None

#: Whether this module started the screen, and so may stop it. False when it
#: attached to one a Tk application already had up - stopping that would tear
#: the terminal out from under the application that owns it.
_owns_screen = False


def _running_application_screen() -> CursesScreen | None:
    """The screen a Tk application already has up, if one has.

    This is what lets the two halves share a terminal rather than fight over
    it: a curses window opened inside a running tkinter application draws
    onto the same cells the widgets do, and one refresh paints both.
    """
    # Imported here rather than at the top: tkcurses does not import this
    # module, but importing it from here at module level would depend on
    # which of the two was imported first.
    import tkcurses

    root = tkcurses._active_root
    if root is None or not root.winfo_exists():
        return None
    screen = root.tk.screen
    return screen if screen is not None and screen.started else None


def _require_screen() -> CursesScreen:
    """The running screen, or the error curses raises when there is none."""
    if _screen is None:
        raise _curses.error("must call initscr() first")
    return _screen


def initscr() -> Window:
    """Start curses and return the window covering the terminal.

    As in curses, calling this twice without an :func:`endwin` between is an
    error rather than a second screen: there is one terminal.

    If a tkinter application already has the screen up, this attaches to it
    rather than starting a second one - which is what lets a curses window
    and a widget share a terminal. :func:`endwin` then leaves that screen
    alone, since the application owns it.
    """
    global _screen, _stdscr, _owns_screen
    if _screen is not None:
        raise _curses.error("initscr() called twice")
    existing = _running_application_screen()
    if existing is not None:
        screen, buffer, _owns_screen = existing, existing.buffer, False
    else:
        screen = CursesScreen()
        buffer = screen.start()
        _owns_screen = True
    _screen = screen
    # Cells of its own, not the screen's. It matters: in curses a refresh
    # copies a window's whole content over the screen, so stdscr.refresh()
    # after win.refresh() erases the window - measured by running the same
    # program against the standard library, where that is what happens. A
    # stdscr sharing the screen's cells would have nothing to copy and would
    # leave the window standing, which is a different program.
    _stdscr = Window(
        ScreenBuffer(buffer.width, buffer.height),
        0,
        0,
        buffer.height,
        buffer.width,
        owns=True,
    )
    return _stdscr


def endwin() -> None:
    """Give the terminal back. Harmless if curses was never started.

    Gives back only what this module took: a screen belonging to a running
    tkinter application is left running.
    """
    global _screen, _stdscr, _owns_screen
    if _screen is not None and _owns_screen:
        _screen.stop()
    _screen = None
    _stdscr = None
    _owns_screen = False


def isendwin() -> bool:
    """True when curses is not currently holding the terminal."""
    return _screen is None or not _screen.started


def wrapper(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run ``func(stdscr, *args)`` with curses up, and give the terminal back.

    The terminal is a process-wide resource: left in raw mode it makes the
    user's shell unusable, so teardown runs even when ``func`` raises. That
    is the entire reason curses has this function and the reason to use it.
    """
    try:
        window = initscr()
        noecho()
        cbreak()
        window.keypad(True)
        with contextlib.suppress(_curses.error):
            start_color()
        return func(window, *args, **kwargs)
    finally:
        endwin()


def newwin(nlines: int, ncols: int, begin_y: int = 0, begin_x: int = 0) -> Window:
    """A new window of its own, at ``(begin_y, begin_x)`` on the screen.

    Zero for either dimension means "the rest of the screen from here", which
    is curses' own rule and what makes ``newwin(0, 0)`` the whole terminal.
    """
    screen = _require_screen()
    height = nlines or max(0, screen.buffer.height - begin_y)
    width = ncols or max(0, screen.buffer.width - begin_x)
    return Window(
        ScreenBuffer(width, height), begin_y, begin_x, height, width, owns=True
    )


def doupdate() -> None:
    """Paint everything marked by :meth:`Window.noutrefresh`."""
    if _screen is not None:
        _screen.refresh()


# --------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------


def start_color() -> None:
    """Initialise colour. A terminal without any is not an error."""
    CursesDispatcher.get().call(_curses.start_color)


def has_colors() -> bool:
    """Whether this terminal has colour at all.

    Not always True, whatever the specification said. A vt100 has none, and a
    program asks this so it can draw differently.
    """
    return bool(CursesDispatcher.get().call(_curses.has_colors))


def can_change_color() -> bool:
    """Whether this terminal's palette entries can be redefined.

    Not always True either, and for the same reason.
    """
    return bool(CursesDispatcher.get().call(_curses.can_change_color))


def init_pair(pair_number: int, fg: int, bg: int) -> None:
    """Define a colour pair, as curses does."""
    CursesDispatcher.get().call(_curses.init_pair, pair_number, fg, bg)


def init_color(color_number: int, r: int, g: int, b: int) -> None:
    """Redefine a palette entry, on a terminal that allows it."""
    CursesDispatcher.get().call(_curses.init_color, color_number, r, g, b)


def color_pair(pair_number: int) -> int:
    """The attribute that selects a colour pair."""
    return int(_curses.color_pair(pair_number))


def pair_number(attr: int) -> int:
    """The colour pair an attribute selects."""
    return int(_curses.pair_number(attr))


def pair_content(pair_number: int) -> tuple[int, int]:
    """The foreground and background a pair was defined with."""
    return CursesDispatcher.get().call(_curses.pair_content, pair_number)


def color_content(color_number: int) -> tuple[int, int, int]:
    """The RGB a palette entry holds."""
    return CursesDispatcher.get().call(_curses.color_content, color_number)


# --------------------------------------------------------------------------
# Terminal modes and odds and ends
# --------------------------------------------------------------------------


def _mode(func: Callable[..., Any], *args: Any) -> None:
    """Run one terminal-mode call on the curses thread, ignoring absence."""
    with contextlib.suppress(_curses.error):
        CursesDispatcher.get().call(func, *args)


def cbreak() -> None:
    """Deliver keys as they are typed, without waiting for a line."""
    _mode(_curses.cbreak)


def nocbreak() -> None:
    """Go back to line-at-a-time input."""
    _mode(_curses.nocbreak)


def echo() -> None:
    """Echo typed characters."""
    _mode(_curses.echo)


def noecho() -> None:
    """Do not echo typed characters."""
    _mode(_curses.noecho)


def raw() -> None:
    """Deliver every key, interrupt and suspend characters included."""
    _mode(_curses.raw)


def noraw() -> None:
    """Let the terminal turn interrupt and suspend back into signals."""
    _mode(_curses.noraw)


def nl() -> None:
    """Translate Return into newline on input."""
    _mode(_curses.nl)


def nonl() -> None:
    """Stop translating Return into newline."""
    _mode(_curses.nonl)


def curs_set(visibility: int) -> int:
    """Hide or show the cursor. Returns the previous setting."""
    try:
        return int(CursesDispatcher.get().call(_curses.curs_set, visibility))
    except _curses.error:
        # A terminal with no cursor-visibility capability raises rather than
        # ignoring it, and a program that only wanted the cursor out of the
        # way should not die of it.
        return 0


def beep() -> None:
    """Sound the terminal's bell."""
    _mode(_curses.beep)


def flash() -> None:
    """Flash the screen instead of sounding the bell."""
    _mode(_curses.flash)


def napms(ms: int) -> None:
    """Sleep for ``ms`` milliseconds."""
    CursesDispatcher.get().call(_curses.napms, ms)


def flushinp() -> None:
    """Throw away anything typed but not yet read."""
    _mode(_curses.flushinp)


def ungetch(ch: int | str) -> None:
    """Push a key back, so the next read returns it."""
    CursesDispatcher.get().call(_curses.ungetch, ch)


def keyname(k: int) -> bytes:
    """The name curses gives a key code."""
    return _curses.keyname(k)


def unctrl(ch: int | str) -> bytes:
    """A printable rendering of a character, control characters included."""
    return _curses.unctrl(ch)


def getmouse() -> tuple[int, int, int, int, int]:
    """The mouse event behind the last ``KEY_MOUSE``."""
    return CursesDispatcher.get().call(_curses.getmouse)


def mousemask(mask: int) -> tuple[int, int]:
    """Choose which mouse events to report."""
    return CursesDispatcher.get().call(_curses.mousemask, mask)


def mouseinterval(interval: int) -> Any:
    """Set the milliseconds allowed between press and release for a click."""
    return CursesDispatcher.get().call(_curses.mouseinterval, interval)


# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------


class Window:
    """A curses window over a :class:`ScreenBuffer`.

    The storage model is curses' own, which is what makes the behaviour
    match. A window has cells of its own; writing into it changes nothing on
    the terminal until :meth:`noutrefresh` copies them to the screen and
    :func:`doupdate` paints it. So two overlapping windows do not overwrite
    one another as they are written - whichever refreshed last is the one you
    see, which is exactly the rule a curses program is written against.

    A subwindow does not get storage of its own: it shares its parent's, at
    an offset, so writing into the child shows through the parent. That too
    is curses, and it is the reason subwindows are useful rather than merely
    convenient.
    """

    def __init__(
        self,
        buffer: ScreenBuffer,
        begin_y: int,
        begin_x: int,
        nlines: int,
        ncols: int,
        *,
        owns: bool,
        offset_y: int = 0,
        offset_x: int = 0,
    ) -> None:
        self._buffer = buffer
        self._begin_y, self._begin_x = begin_y, begin_x
        self._offset_y, self._offset_x = offset_y, offset_x
        self._height, self._width = nlines, ncols
        self._owns = owns
        self._cursor_y = self._cursor_x = 0
        self._attr = 0
        self._background = BLANK
        self._background_attr = 0
        self._scroll_ok = False
        self._keypad = False
        self._leave_ok = False
        self._clear_ok = False
        # What has changed since the last refresh, as ``row: (first, last)``
        # columns - and this is the whole of curses' refresh rule.
        #
        # A refresh copies the touched *part of each touched line* in this
        # window and nothing else. Both halves of that were measured against
        # the standard library, and each is a rule on its own:
        #
        # Lines: refreshing stdscr erases a window it overlaps in one program
        # and leaves it standing in another, the difference being only
        # whether stdscr had been refreshed before.
        #
        # Ranges: a program that writes five characters onto a line and
        # refreshes leaves the rest of that line alone - so a panel's border
        # further along it survives. Copying whole lines wiped it.
        #
        # A new window starts wholly touched, as curses' does: it is blank,
        # and its first refresh paints that blank over whatever was
        # underneath, even where nothing has been written into it.
        self._touched: dict[int, tuple[int, int]] = {
            row: (0, max(0, ncols - 1)) for row in range(nlines)
        }

    # ------------------------------------------------------------ geometry

    def getmaxyx(self) -> tuple[int, int]:
        """The window's size, as ``(lines, columns)``."""
        return (self._height, self._width)

    def getbegyx(self) -> tuple[int, int]:
        """Where the window sits on the screen, as ``(y, x)``."""
        return (self._begin_y, self._begin_x)

    def getyx(self) -> tuple[int, int]:
        """Where the cursor is within the window."""
        return (self._cursor_y, self._cursor_x)

    def getparyx(self) -> tuple[int, int]:
        """Where a subwindow sits inside its parent, or ``(-1, -1)``."""
        if self._owns:
            return (-1, -1)
        return (self._offset_y, self._offset_x)

    def enclose(self, y: int, x: int) -> bool:
        """Whether a screen position falls inside this window."""
        return (
            self._begin_y <= y < self._begin_y + self._height
            and self._begin_x <= x < self._begin_x + self._width
        )

    def move(self, y: int, x: int) -> None:
        """Put the cursor at ``(y, x)``, refusing a position outside."""
        if not self._contains(y, x):
            raise _curses.error("move() returned ERR")
        self._cursor_y, self._cursor_x = y, x

    def mvwin(self, y: int, x: int) -> None:
        """Move the whole window to ``(y, x)`` on the screen."""
        self._begin_y, self._begin_x = y, x

    def mvderwin(self, y: int, x: int) -> None:
        """Move a subwindow to ``(y, x)`` within its parent."""
        self._offset_y, self._offset_x = y, x

    def resize(self, nlines: int, ncols: int) -> None:
        """Resize the window, keeping whatever still fits."""
        if self._owns:
            self._buffer.resize(ncols, nlines)
        self._height, self._width = nlines, ncols
        self._cursor_y = min(self._cursor_y, max(0, nlines - 1))
        self._cursor_x = min(self._cursor_x, max(0, ncols - 1))

    def subwin(self, *args: int) -> Window:
        """A window sharing this one's cells, given in screen coordinates.

        ``subwin(nlines, ncols, begin_y, begin_x)`` or ``subwin(begin_y,
        begin_x)`` for one running to this window's bottom-right corner.
        """
        if len(args) == 2:
            begin_y, begin_x = args
            nlines = self._begin_y + self._height - begin_y
            ncols = self._begin_x + self._width - begin_x
        else:
            nlines, ncols, begin_y, begin_x = args
        return self._derive(nlines, ncols, begin_y, begin_x)

    def derwin(self, *args: int) -> Window:
        """The same as :meth:`subwin`, but positioned within this window."""
        if len(args) == 2:
            offset_y, offset_x = args
            nlines = self._height - offset_y
            ncols = self._width - offset_x
        else:
            nlines, ncols, offset_y, offset_x = args
        return self._derive(
            nlines, ncols, self._begin_y + offset_y, self._begin_x + offset_x
        )

    def _derive(self, nlines: int, ncols: int, begin_y: int, begin_x: int) -> Window:
        """One subwindow, sharing this window's storage at an offset."""
        nlines = nlines or max(0, self._begin_y + self._height - begin_y)
        ncols = ncols or max(0, self._begin_x + self._width - begin_x)
        return Window(
            self._buffer,
            begin_y,
            begin_x,
            nlines,
            ncols,
            owns=False,
            offset_y=self._offset_y + (begin_y - self._begin_y),
            offset_x=self._offset_x + (begin_x - self._begin_x),
        )

    # ------------------------------------------------------------- writing

    def _contains(self, y: int, x: int) -> bool:
        """Whether ``(y, x)`` is a cell this window has."""
        return 0 <= y < self._height and 0 <= x < self._width

    def _put(self, y: int, x: int, text: str, attr: int) -> None:
        """Write into the storage, clipped to this window."""
        if not text or not (0 <= y < self._height):
            return
        start = max(0, x)
        visible = text[start - x :][: max(0, self._width - start)]
        if visible:
            self._buffer.write(
                self._offset_y + y, self._offset_x + start, visible, attr=attr
            )
            self._mark(y, start, start + len(visible) - 1)

    def _mark(self, row: int, first: int, last: int) -> None:
        """Widen the range of one row that the next refresh will copy."""
        known = self._touched.get(row)
        if known is None:
            self._touched[row] = (first, last)
        else:
            self._touched[row] = (min(known[0], first), max(known[1], last))

    def _whole(self) -> tuple[int, int]:
        """The range covering a whole row."""
        return (0, max(0, self._width - 1))

    def _advance(self, y: int, x: int, count: int) -> None:
        """Move the cursor on by ``count`` cells, wrapping as curses does."""
        x += count
        while x >= self._width and self._width:
            x -= self._width
            y += 1
        self._cursor_y = min(y, max(0, self._height - 1))
        self._cursor_x = min(x, max(0, self._width - 1))

    def _place(self, args: tuple[Any, ...]) -> tuple[int, int, tuple[Any, ...]]:
        """Unpick curses' overloads: a leading ``y, x`` or the cursor."""
        if len(args) >= 2 and isinstance(args[0], int) and isinstance(args[1], int):
            return int(args[0]), int(args[1]), args[2:]
        return self._cursor_y, self._cursor_x, args

    def _styled(self, rest: tuple[Any, ...], index: int) -> int:
        """The attribute an overload carried, or the window's current one."""
        if len(rest) > index and isinstance(rest[index], int):
            return int(rest[index]) | self._background_attr
        return self._attr | self._background_attr

    def addch(self, *args: Any) -> None:
        """Put one character at the cursor, or at a given ``y, x``."""
        y, x, rest = self._place(args)
        char = rest[0] if rest else BLANK
        text = chr(char) if isinstance(char, int) else str(char)
        self._put(y, x, text[:1], self._styled(rest, 1))
        self._advance(y, x, 1)

    def addstr(self, *args: Any) -> None:
        """Put a string at the cursor, or at a given ``y, x``."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        self._put(y, x, text, self._styled(rest, 1))
        self._advance(y, x, len(text))

    def addnstr(self, *args: Any) -> None:
        """Put at most ``n`` characters of a string."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        count = int(rest[1]) if len(rest) > 1 else len(text)
        clipped = text[: max(0, count)]
        self._put(y, x, clipped, self._styled(rest, 2))
        self._advance(y, x, len(clipped))

    def insch(self, *args: Any) -> None:
        """Insert a character, pushing the rest of the line right."""
        y, x, rest = self._place(args)
        char = rest[0] if rest else BLANK
        text = chr(char) if isinstance(char, int) else str(char)
        self._shift_right(y, x, 1)
        self._put(y, x, text[:1], self._styled(rest, 1))

    def insstr(self, *args: Any) -> None:
        """Insert a string, pushing the rest of the line right."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        self._shift_right(y, x, len(text))
        self._put(y, x, text, self._styled(rest, 1))

    def echochar(self, ch: Any, attr: int = 0) -> None:
        """Add a character and refresh at once, as curses does."""
        self.addch(ch, attr)
        self.refresh()

    def _shift_right(self, y: int, x: int, count: int) -> None:
        """Push the rest of a line right, dropping what falls off the end."""
        if count <= 0 or not self._contains(y, max(0, x)):
            return
        tail = self._read(y, x, self._width - x - count)
        self._put(y, x + count, tail, self._attr)

    def _read(self, y: int, x: int, length: int) -> str:
        """The characters a stretch of one row holds."""
        if length <= 0:
            return ""
        return "".join(
            self._buffer.cell(self._offset_y + y, self._offset_x + column).char
            for column in range(x, min(x + length, self._width))
        )

    # ------------------------------------------------------------- reading

    def inch(self, *args: int) -> int:
        """The character and attributes at a position, packed as curses does."""
        y, x, _ = self._place(args)
        if not self._contains(y, x):
            return 0
        cell = self._buffer.cell(self._offset_y + y, self._offset_x + x)
        return ord(cell.char[0]) | cell.attr if cell.char else cell.attr

    def instr(self, *args: Any) -> bytes:
        """The text on a row from a position, as curses returns it."""
        y, x, rest = self._place(args)
        length = int(rest[0]) if rest and isinstance(rest[0], int) else self._width - x
        return self._read(y, x, length).encode()

    # ------------------------------------------------------------- erasing

    def erase(self) -> None:
        """Blank every cell, without forcing a repaint."""
        for row in range(self._height):
            self._put(row, 0, self._background * self._width, self._background_attr)
        self._cursor_y = self._cursor_x = 0

    def clear(self) -> None:
        """Blank the window and repaint it whole at the next refresh."""
        self.erase()
        self.touchwin()
        self._clear_ok = True

    def clrtoeol(self) -> None:
        """Blank from the cursor to the end of its row."""
        width = self._width - self._cursor_x
        self._put(
            self._cursor_y,
            self._cursor_x,
            self._background * width,
            self._background_attr,
        )

    def clrtobot(self) -> None:
        """Blank from the cursor to the end of the window."""
        self.clrtoeol()
        for row in range(self._cursor_y + 1, self._height):
            self._put(row, 0, self._background * self._width, self._background_attr)

    def delch(self, *args: int) -> None:
        """Delete a character, pulling the rest of the line left."""
        y, x, _ = self._place(args)
        if not self._contains(y, x):
            return
        tail = self._read(y, x + 1, self._width - x - 1)
        self._put(y, x, tail + self._background, self._attr)

    def deleteln(self) -> None:
        """Delete the cursor's row, pulling the rows below it up."""
        for row in range(self._cursor_y, self._height - 1):
            self._put(row, 0, self._read(row + 1, 0, self._width), self._attr)
        self._put(
            self._height - 1,
            0,
            self._background * self._width,
            self._background_attr,
        )

    def insertln(self) -> None:
        """Insert a blank row at the cursor, pushing the rows below it down."""
        for row in range(self._height - 1, self._cursor_y, -1):
            self._put(row, 0, self._read(row - 1, 0, self._width), self._attr)
        self._put(
            self._cursor_y, 0, self._background * self._width, self._background_attr
        )

    def scroll(self, lines: int = 1) -> None:
        """Scroll the window, if it has been told it may."""
        if not self._scroll_ok:
            raise _curses.error("scroll() returned ERR")
        rows = [self._read(row, 0, self._width) for row in range(self._height)]
        blank = self._background * self._width
        for row in range(self._height):
            source = row + lines
            text = rows[source] if 0 <= source < self._height else blank
            self._put(row, 0, text, self._attr)

    # ---------------------------------------------------------- attributes

    def attron(self, attr: int) -> None:
        """Add attributes to the ones used from now on."""
        self._attr |= attr

    def attroff(self, attr: int) -> None:
        """Take attributes away from the ones used from now on."""
        self._attr &= ~attr

    def attrset(self, attr: int) -> None:
        """Replace the attributes used from now on."""
        self._attr = attr

    def standout(self) -> None:
        """Draw in reverse video from now on."""
        self.attron(_curses.A_STANDOUT)

    def standend(self) -> None:
        """Stop drawing in reverse video, and clear every other attribute."""
        self._attr = 0

    def chgat(self, *args: Any) -> None:
        """Restyle a run of cells without changing what they say."""
        y, x, rest = self._place(args)
        count = int(rest[0]) if rest and isinstance(rest[0], int) else -1
        attr = self._styled(rest, 1)
        length = self._width - x if count < 0 else count
        self._put(y, x, self._read(y, x, length), attr)

    def bkgdset(self, ch: Any = BLANK, attr: int = 0) -> None:
        """Set the background for cells written from now on."""
        text = chr(ch) if isinstance(ch, int) else str(ch)
        self._background = (text or BLANK)[:1]
        self._background_attr = attr

    def bkgd(self, ch: Any = BLANK, attr: int = 0) -> None:
        """Set the background, and apply it to every cell already there."""
        self.bkgdset(ch, attr)
        for row in range(self._height):
            self._put(row, 0, self._read(row, 0, self._width), attr)

    def getbkgd(self) -> int:
        """The background character and its attributes, packed as curses does."""
        return ord(self._background) | self._background_attr

    # ------------------------------------------------------------- drawing

    def hline(self, *args: Any) -> None:
        """Draw a horizontal run of one character."""
        y, x, rest = self._place(args)
        char, count = self._line_args(rest)
        self._put(y, x, char * count, self._styled(rest, 2))

    def vline(self, *args: Any) -> None:
        """Draw a vertical run of one character."""
        y, x, rest = self._place(args)
        char, count = self._line_args(rest)
        attr = self._styled(rest, 2)
        for offset in range(count):
            self._put(y + offset, x, char, attr)

    @staticmethod
    def _line_args(rest: tuple[Any, ...]) -> tuple[str, int]:
        """The character and length an hline/vline overload carried."""
        char = rest[0] if rest else BLANK
        text = chr(char) if isinstance(char, int) else str(char)
        count = int(rest[1]) if len(rest) > 1 else 1
        return (text or BLANK)[:1], max(0, count)

    def border(self, *sides: Any) -> None:
        """Draw a border, taking the eight characters curses takes.

        A zero or an omitted side means the default for that side, which is
        what lets ``border(0, 0, 0, 0)`` mean a plain box.

        The defaults are the box-drawing characters the widgets use, not
        ``ACS_VLINE`` and its relatives. Two reasons, and the second is the
        one that decided it: the ACS constants do not exist until initscr has
        run, so a window drawn before there is a screen would fail on them;
        and this layer writes characters into a cell buffer rather than
        handing codes to curses, which is the same reason the widgets draw
        their borders this way.
        """
        given = list(sides) + [0] * (8 - len(sides))
        parts = [
            self._one_char(value) if value else default
            for value, default in zip(given, BORDER_DEFAULTS, strict=True)
        ]
        left, right, top, bottom, top_left, top_right, bottom_left, bottom_right = parts
        if self._height < 2 or self._width < 2:
            return
        inner = self._width - 2
        self._put(0, 0, top_left + top * inner + top_right, self._attr)
        self._put(
            self._height - 1,
            0,
            bottom_left + bottom * inner + bottom_right,
            self._attr,
        )
        for row in range(1, self._height - 1):
            self._put(row, 0, left, self._attr)
            self._put(row, self._width - 1, right, self._attr)

    def box(self, vertch: Any = 0, horch: Any = 0) -> None:
        """Draw a plain box, which is :meth:`border` with two characters."""
        self.border(vertch, vertch, horch, horch, 0, 0, 0, 0)

    @staticmethod
    def _one_char(value: Any) -> str:
        """One drawing character, from whichever form curses accepts.

        An ACS value carries ``A_ALTCHARSET`` above a VT100 charset letter -
        ``ACS_VLINE`` is that flag over an ``x`` - so taking the low byte of
        one would draw a literal x. Those are translated instead.
        """
        if isinstance(value, int):
            if value & _curses.A_ALTCHARSET:
                return _acs_character(value)
            return chr(value) if value else BLANK
        return (str(value) or BLANK)[:1]

    # ------------------------------------------------------------ painting

    def noutrefresh(self) -> None:
        """Copy this window onto the screen, without painting it yet."""
        screen = _require_screen()
        destination = screen.buffer
        if self is _stdscr and (
            self._height != destination.height or self._width != destination.width
        ):
            # The terminal was resized under it. curses makes a program ask
            # for this; here the window that stands for the whole screen can
            # simply follow it, and a program that never handles KEY_RESIZE
            # keeps working instead of drawing into the old shape.
            self.resize(destination.height, destination.width)
        for row, (first, last) in sorted(self._touched.items()):
            target_row = self._begin_y + row
            if not 0 <= row < self._height:
                continue
            if not 0 <= target_row < destination.height:
                continue
            for column in range(first, min(last + 1, self._width)):
                target_column = self._begin_x + column
                if not 0 <= target_column < destination.width:
                    continue
                cell = self._buffer.cell(self._offset_y + row, self._offset_x + column)
                destination.write(
                    target_row,
                    target_column,
                    cell.char,
                    fg=cell.fg,
                    bg=cell.bg,
                    attr=cell.attr,
                )
        self._touched.clear()

    def refresh(self) -> None:
        """Copy this window onto the screen and paint it."""
        self.noutrefresh()
        if self._clear_ok:
            self._clear_ok = False
            _require_screen().repaint()
            return
        doupdate()

    def redrawwin(self) -> None:
        """Copy and repaint the whole window at the next refresh."""
        self.touchwin()
        self._clear_ok = True

    def redrawln(self, beg: int, num: int) -> None:
        """Copy and repaint a run of rows at the next refresh."""
        self.touchline(beg, num)
        self._clear_ok = True

    def touchwin(self) -> None:
        """Mark every row whole, so the next refresh copies all of it."""
        self._touched = {row: self._whole() for row in range(self._height)}

    def touchline(self, start: int, count: int, changed: bool = True) -> None:
        """Mark a run of rows whole, or mark them as unchanged."""
        for row in range(max(0, start), min(self._height, start + count)):
            if changed:
                self._touched[row] = self._whole()
            else:
                self._touched.pop(row, None)

    def touch_region(self, y: int, x: int, height: int, width: int) -> None:
        """Mark a rectangle for copying at the next refresh.

        Not one of curses' own, and here for one caller: :mod:`tkcurses.panel`
        has to put the background back where a panel was hidden or moved
        away from, and the only thing that can is the window behind it -
        copied over just that rectangle, not the whole of it.
        """
        for row in range(max(0, y), min(self._height, y + height)):
            first, last = max(0, x), min(self._width, x + width) - 1
            if first <= last:
                self._mark(row, first, last)

    def untouchwin(self) -> None:
        """Mark every row as unchanged, so the next refresh copies none."""
        self._touched.clear()

    def is_wintouched(self) -> bool:
        """Whether any row is waiting to be copied."""
        return bool(self._touched)

    def is_linetouched(self, line: int) -> bool:
        """Whether one row is waiting to be copied."""
        return line in self._touched

    # ------------------------------------------------------------ settings

    def keypad(self, flag: bool = True) -> None:
        """Have arrow and function keys arrive as single ``KEY_`` codes."""
        self._keypad = bool(flag)
        screen = _screen
        if screen is not None and screen.started:
            CursesDispatcher.get().call(screen.stdscr.keypad, bool(flag))

    def nodelay(self, flag: bool = True) -> None:
        """Make :meth:`getch` return at once when nothing has been typed."""
        screen = _screen
        if screen is not None and screen.started:
            CursesDispatcher.get().call(screen.stdscr.nodelay, bool(flag))

    def timeout(self, delay: int) -> None:
        """How long :meth:`getch` waits: blocking, non-blocking, or a limit."""
        screen = _screen
        if screen is not None and screen.started:
            CursesDispatcher.get().call(screen.stdscr.timeout, delay)

    def notimeout(self, flag: bool) -> None:
        """Whether to wait for the rest of an escape sequence."""
        screen = _screen
        if screen is not None and screen.started:
            with contextlib.suppress(_curses.error):
                CursesDispatcher.get().call(screen.stdscr.notimeout, bool(flag))

    def scrollok(self, flag: bool) -> None:
        """Whether the window may scroll."""
        self._scroll_ok = bool(flag)

    def setscrreg(self, top: int, bottom: int) -> None:
        """Set the rows scrolling affects.

        Recorded and not yet honoured: :meth:`scroll` moves the whole window.
        """
        del top, bottom

    def clearok(self, flag: bool) -> None:
        """Whether the next refresh repaints everything."""
        self._clear_ok = bool(flag)

    def leaveok(self, flag: bool) -> None:
        """Whether the hardware cursor may be left wherever it lands."""
        self._leave_ok = bool(flag)

    def idlok(self, flag: bool) -> None:
        """Whether to use the terminal's line insert and delete.

        A no-op: this layer repaints from a cell buffer and has no use for
        them. Accepted rather than refused, because a curses program sets it
        and would otherwise fail on a line it is entitled to write.
        """
        del flag

    def idcok(self, flag: bool) -> None:
        """Whether to use the terminal's character insert and delete. A no-op."""
        del flag

    def immedok(self, flag: bool) -> None:
        """Whether every change paints at once. A no-op; use refresh()."""
        del flag

    def syncok(self, flag: bool) -> None:
        """Whether a subwindow syncs its parent automatically.

        A no-op, and it can be: a subwindow shares its parent's cells here,
        so there is never anything to sync.
        """
        del flag

    def syncup(self) -> None:
        """Sync a subwindow's changes to its parent. Nothing to do."""

    def syncdown(self) -> None:
        """Sync a parent's changes to a subwindow. Nothing to do."""

    def cursyncup(self) -> None:
        """Sync a subwindow's cursor to its parent. Nothing to do."""

    # --------------------------------------------------------------- input

    def getch(self, *args: int) -> int:
        """Read one key, moving the cursor first if given somewhere to be.

        The terminal has one keyboard, so this reads from it rather than from
        the window - which is what curses does too, the window mattering only
        for the keypad setting and where the cursor was left.
        """
        if args:
            self.move(*args[:2])
        screen = _require_screen()
        return int(CursesDispatcher.get().call(screen.stdscr.getch))

    def getkey(self, *args: int) -> str:
        """Read one key and return its name, as curses does."""
        key = self.getch(*args)
        if key == -1:
            raise _curses.error("no input")
        return _curses.keyname(key).decode()

    def get_wch(self, *args: int) -> int | str:
        """Read one key as a character where it is one, or a code where not."""
        if args:
            self.move(*args[:2])
        screen = _require_screen()
        key: int | str = CursesDispatcher.get().call(screen.stdscr.get_wch)
        return key

    def getstr(self, *args: Any) -> bytes:
        """Read a line, ending at Return. Backspace removes a character."""
        y, x, rest = self._place(args)
        limit = int(rest[0]) if rest and isinstance(rest[0], int) else self._width - x
        typed: list[str] = []
        while True:
            key = self.getch()
            if key in (ord("\n"), ord("\r"), _curses.KEY_ENTER):
                break
            if key in (_curses.KEY_BACKSPACE, 127, 8):
                if typed:
                    typed.pop()
                    self._put(y, x + len(typed), BLANK, self._attr)
                    self.refresh()
                continue
            if 32 <= key < 127 and len(typed) < limit:
                typed.append(chr(key))
                self._put(y, x + len(typed) - 1, typed[-1], self._attr)
                self.refresh()
        return "".join(typed).encode()

    def instr_at_cursor(self) -> bytes:
        """The rest of the cursor's row. Not curses; convenient in tests."""
        return self._read(self._cursor_y, self._cursor_x, self._width).encode()

    def __repr__(self) -> str:
        return (
            f"<tkcurses.curses.Window {self._width}x{self._height}"
            f" at ({self._begin_y}, {self._begin_x})>"
        )
