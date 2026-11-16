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
# Portions follow the behaviour of ncurses routines, each named beside the
# code that follows it. ncurses is copyright Thomas E. Dickey and the Free
# Software Foundation, Inc., and is credited under its own licence; see
# THIRD_PARTY_NOTICES.md.

"""The curses API, on the same screen as the widgets.

Sample output:
    from tkcurses import curses
    tk.Button(root, text="A widget").pack(side="bottom", pady=1)
    stdscr = curses.initscr()
    win = curses.newwin(5, 26, 1, 7)
    win.box()
    win.addstr(1, 2, "A curses window", curses.A_BOLD)
    win.addstr(3, 2, "on the same screen")
    win.refresh()

Import it in place of the standard library's: ``from tkcurses import
curses``. A curses program then runs as it did, and can also use
widgets - a tkinter application with one area drawn the curses way, or
a curses program that opens a dialog.

:func:`initscr` and :func:`wrapper` start it, as in curses. If a tkinter
application already has the screen up, they share it, and :func:`endwin`
leaves the application's screen running. A window keeps its own cells
and appears when it is refreshed, so the usual rule holds: the window
refreshed last is the one on top. :mod:`tkcurses.panel` keeps several in
order.

Every constant - ``A_BOLD``, ``KEY_UP``, ``COLOR_RED``, ``ACS_HLINE``,
``error`` - is the standard library's, under the same name.

Text is written as given, as curses writes it. A control character is
shown as curses shows it, ``^[`` for Escape, so no escape sequence
reaches the terminal. A Unicode format character is passed on, though,
the bidirectional controls among them: after U+202E, a terminal that
honours it shows the rest of the line right to left, so what appears is
not what was written. Text from outside the program - a file name, a
message from the network - can be filtered before it is drawn, for
instance by leaving out each character whose
``unicodedata.category(char)`` is ``"Cf"``. The widgets do this for the
text they draw.

Differences from curses:
    A function not listed here is the standard library's own, and acts
    on the terminal directly rather than through this library. The ones
    a program draws and reads keys with are all here.

    ``idlok``, ``idcok``, ``immedok`` and the subwindow ``sync`` calls
    are accepted and do nothing, and ``setscrreg`` is not honoured yet;
    each says so below.

TkCurses extension:
    tkinter has no such module.
"""
# This is a facade over the screen and cell buffer the widgets draw on, not a
# reimplementation of curses - the backend already is curses - so a curses
# program gets the double-buffered painting, resize handling and colour depth
# detection without being written differently. Two corrections to what
# ARCHITECTURE.md specified: has_colors() and can_change_color() were to
# answer True always, and they delegate and tell the truth, because a program
# asks precisely so it can draw differently. Importing this module is safe for
# the rest of the package only because tkcurses/__init__.py imports the
# standard library as _curses: importing the submodule binds the attribute
# "curses" on the package, which is __init__'s own global namespace.

from __future__ import annotations

import contextlib
import curses as _curses
import locale
from typing import TYPE_CHECKING, Any

from tkcurses._core.cells import cells, char_cells, clip_cells, skip_cells
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.screen import BLANK, CursesScreen, ScreenBuffer

if TYPE_CHECKING:
    from collections.abc import Callable

    from tkcurses._core.application import Application

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
    "getwin",
    "has_colors",
    "init_pair",
    "initscr",
    "isendwin",
    "keyname",
    "napms",
    "newpad",
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


def _running_application() -> Application | None:
    """The running Tk application's shared state, if one is up."""
    # Imported here rather than at the top: tkcurses does not import this
    # module, but importing it from here at module level would depend on
    # which of the two was imported first.
    import tkcurses

    root = tkcurses._active_root
    if root is None or not root.winfo_exists():
        return None
    return root.tk


def _running_application_screen() -> CursesScreen | None:
    """The screen a Tk application already has up, if one has.

    This is what lets the two halves share a terminal rather than fight over
    it: a curses window opened inside a running tkinter application draws
    onto the same cells the widgets do, and one refresh paints both.
    """
    application = _running_application()
    if application is None:
        return None
    screen = application.screen
    return screen if screen is not None and screen.started else None


def _repaint() -> None:
    """Paint the whole terminal again, the widgets included when it is an
    application's - they are part of the screen a clearok asks for."""
    application = None if _owns_screen else _running_application()
    if application is not None:
        application.repaint()
    else:
        _require_screen().repaint()


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


def newpad(nlines: int, ncols: int) -> Window:
    """A pad: a window as large as it needs to be, never on the screen
    itself, a part of which :meth:`Window.refresh` shows wherever it is
    told to.

    Raises:
        error: If either size is not above nought, as curses does.
    """
    _require_screen()
    if nlines <= 0 or ncols <= 0:
        raise _curses.error("curses function returned NULL")
    pad = Window(ScreenBuffer(ncols, nlines), 0, 0, nlines, ncols, owns=True)
    pad._pad = True
    return pad


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
    """Whether this terminal has colour at all. A vt100 has none."""
    # Not always True, whatever the specification said: a program asks this so
    # it can draw differently.
    return bool(CursesDispatcher.get().call(_curses.has_colors))


def can_change_color() -> bool:
    """Whether this terminal's palette entries can be redefined."""
    # Not always True either, for the same reason as has_colors.
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
    """A curses window. Made by :func:`initscr`, :func:`newwin`,
    :meth:`subwin` and :meth:`derwin`, not directly.

    A window has cells of its own, and writing into it changes nothing on
    the terminal until :meth:`noutrefresh` copies them to the screen and
    :func:`doupdate` paints it. So two overlapping windows do not overwrite
    one another as they are written: whichever refreshed last is the one
    seen, as in curses.

    A subwindow shares its parent's cells, at an offset, so what is written
    into one shows in the other.
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
        #: The rows :meth:`scroll` and a newline at the bottom move, set by
        #: :meth:`setscrreg`; the whole window until then. None is "all".
        self._region: tuple[int, int] | None = None
        self._keypad = False
        self._leave_ok = False
        self._clear_ok = False
        #: Whether this is a pad, made by :func:`newpad` or :meth:`subpad`.
        self._pad = False
        #: Where a pad was last shown, as its six refresh arguments, so a
        #: pad shown somewhere new is copied whole. None until then.
        self._pad_view: tuple[int, int, int, int, int, int] | None = None
        #: What :attr:`encoding` answers: the locale's, as curses takes it.
        self._encoding = _screen_encoding()
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
        """Move the whole window to ``(y, x)`` on the screen.

        Raises:
            error: For a pad, which is never on the screen to move.
        """
        if self._pad:
            raise _curses.error("mvwin() returned ERR")
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
        window = self._derive(nlines, ncols, begin_y, begin_x)
        # The standard library's subwin passes its encoding on, and its
        # derwin does not: measured, and kept.
        window._encoding = self._encoding
        return window

    #: A pad's subwindows are pads, and made the same way.
    subpad = subwin

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
        window = Window(
            self._buffer,
            begin_y,
            begin_x,
            nlines,
            ncols,
            owns=False,
            offset_y=self._offset_y + (begin_y - self._begin_y),
            offset_x=self._offset_x + (begin_x - self._begin_x),
        )
        window._pad = self._pad
        return window

    # ------------------------------------------------------------- writing

    def _contains(self, y: int, x: int) -> bool:
        """Whether ``(y, x)`` is a cell this window has."""
        return 0 <= y < self._height and 0 <= x < self._width

    def _put(self, y: int, x: int, text: str, attr: int) -> None:
        """Write into the storage, clipped to this window.

        Clipped in cells: a wide character takes two and a combining mark
        none, and one cut by the window's left edge shows as a blank.
        """
        if not text or not (0 <= y < self._height):
            return
        start = max(0, x)
        rest, blanks = skip_cells(text, start - x)
        visible = clip_cells(BLANK * blanks + rest, max(0, self._width - start))
        if visible:
            self._buffer.write(
                self._offset_y + y, self._offset_x + start, visible, attr=attr
            )
            self._mark(y, start, start + max(1, cells(visible)) - 1)

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

    def _write(self, y: int, x: int, text: str, attr: int, name: str) -> None:
        """Write text from ``(y, x)`` as curses' ``waddch`` does.

        A newline clears the rest of the row and goes to the start of the
        next; a character that fills the last column wraps at once, and a
        wide one that does not fit wraps first. Going on from the bottom of
        the scrolling region scrolls it when :meth:`scrollok` allows, and
        from the bottom row otherwise is curses' ``ERR``, raised once the
        text before it is written - measured against the standard library's
        curses, which wrote "ab" and raised for ``"ab\n"`` on the last row.
        """
        run, run_x, col = "", x, x

        def flush() -> None:
            if run:
                self._put(y, run_x, run, attr)

        for char in text:
            if char == "\n":
                flush()
                if col < self._width:
                    blank = self._background * (self._width - col)
                    self._put(y, col, blank, self._background_attr)
                self._cursor_y, self._cursor_x = y, min(col, self._width - 1)
                y = self._next_line(y, name)
                run, run_x, col = "", 0, 0
                continue
            width = char_cells(char)
            if width and col + width > self._width and col > 0:
                flush()
                self._cursor_y, self._cursor_x = y, self._width - 1
                y = self._next_line(y, name)
                run, run_x, col = "", 0, 0
            run += char
            col += width
            if col >= self._width:
                flush()
                self._cursor_y, self._cursor_x = y, self._width - 1
                y = self._next_line(y, name)
                run, run_x, col = "", 0, 0
        flush()
        self._cursor_y = y
        self._cursor_x = min(max(0, col), max(0, self._width - 1))

    def _next_line(self, y: int, name: str) -> int:
        """The row a newline or a wrap goes to from ``y``, scrolling the
        region if ``y`` is its bottom; ``ERR`` where curses has nowhere to
        go."""
        top, bottom = self._region or (0, self._height - 1)
        if y == bottom:
            if not self._scroll_ok:
                raise _curses.error(f"{name}() returned ERR")
            self._scroll_rows(top, bottom, 1)
            return y
        if y < self._height - 1:
            return y + 1
        if not self._scroll_ok:
            raise _curses.error(f"{name}() returned ERR")
        return y

    def _scroll_rows(self, top: int, bottom: int, lines: int) -> None:
        """Move rows ``top`` to ``bottom`` up by ``lines``, down if negative,
        filling with the background."""
        rows = [self._read(row, 0, self._width) for row in range(top, bottom + 1)]
        blank = self._background * self._width
        for index, row in enumerate(range(top, bottom + 1)):
            source = index + lines
            text = rows[source] if 0 <= source < len(rows) else blank
            self._put(row, 0, text, self._attr)

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
        self._write(y, x, text[:1], self._styled(rest, 1), "addch")

    def addstr(self, *args: Any) -> None:
        """Put a string at the cursor, or at a given ``y, x``."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        # In cells, as curses moves: two for an ideograph, none for a mark.
        self._write(y, x, text, self._styled(rest, 1), "addwstr")

    def addnstr(self, *args: Any) -> None:
        """Put at most ``n`` characters of a string."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        count = int(rest[1]) if len(rest) > 1 else len(text)
        clipped = text[: max(0, count)]
        self._write(y, x, clipped, self._styled(rest, 2), "addnwstr")

    def insch(self, *args: Any) -> None:
        """Insert a character, pushing the rest of the line right."""
        y, x, rest = self._place(args)
        char = rest[0] if rest else BLANK
        text = chr(char) if isinstance(char, int) else str(char)
        self._shift_right(y, x, char_cells(text[:1]))
        self._put(y, x, text[:1], self._styled(rest, 1))

    def insstr(self, *args: Any) -> None:
        """Insert a string, pushing the rest of the line right."""
        y, x, rest = self._place(args)
        text = str(rest[0]) if rest else ""
        self._shift_right(y, x, cells(text))
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
        """Scroll the region :meth:`setscrreg` set - the whole window until
        then - up, or down for a negative count, if :meth:`scrollok` allows."""
        if not self._scroll_ok:
            raise _curses.error("scroll() returned ERR")
        top, bottom = self._region or (0, self._height - 1)
        self._scroll_rows(top, bottom, lines)

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
        """Set the background, and apply it to every cell already there: a
        cell holding the old background character takes the new one, as
        curses' ``wbkgd`` does, so ``bkgd(".")`` fills a blank window."""
        previous = self._background
        self.bkgdset(ch, attr)
        for row in range(self._height):
            text = self._read(row, 0, self._width)
            text = "".join(
                self._background if char == previous else char for char in text
            )
            self._put(row, 0, text, attr)

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

        Differences from curses:
            The defaults are the box-drawing characters the widgets use, not
            ``ACS_VLINE`` and its relatives. On a terminal that shows Unicode
            they look the same.
        """
        # Two reasons, and the second decided it: the ACS constants do not
        # exist until initscr has run, so a window drawn before there is a
        # screen would fail on them; and this layer writes characters into a
        # cell buffer rather than handing codes to curses, which is the same
        # reason the widgets draw their borders this way.
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

    def noutrefresh(self, *args: int) -> None:
        """Copy this window onto the screen, without painting it yet.

        A pad takes six arguments, as :meth:`refresh` does, and nothing
        else does.
        """
        if self._pad or args:
            self._pad_refresh(args, "noutrefresh", "pnoutrefresh")
            return
        self._copy_touched()

    def _copy_touched(self) -> None:
        """Copy what has changed in this window onto the screen."""
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

    def refresh(self, *args: int) -> None:
        """Copy this window onto the screen and paint it.

        A pad shows the part of itself from ``(pminrow, pmincol)`` in the
        screen's rectangle from ``(sminrow, smincol)`` to ``(smaxrow,
        smaxcol)``: ``pad.refresh(pminrow, pmincol, sminrow, smincol,
        smaxrow, smaxcol)``. The rectangle is cut short where the pad ends.

        Raises:
            error: For a pad without the six arguments, or a rectangle that
                runs off the screen or is inside out, in curses' words.
            TypeError: For arguments to a window that is not a pad.
        """
        if self._pad or args:
            self._pad_refresh(args, "refresh", "prefresh")
            doupdate()
            return
        self._copy_touched()
        if self._clear_ok:
            self._clear_ok = False
            _repaint()
            return
        doupdate()

    def _pad_refresh(self, args: tuple[int, ...], name: str, pname: str) -> None:
        """A pad's refresh, as ncurses' ``pnoutrefresh`` works it out."""
        if not self._pad:
            raise TypeError(f"{name}() takes no arguments ({len(args)} given)")
        if len(args) != 6:
            if name == "refresh":
                raise _curses.error("refresh() for a pad requires 6 arguments")
            raise _curses.error(f"{name}() called for a pad requires 6 arguments")
        pminrow, pmincol, sminrow, smincol, smaxrow, smaxcol = (int(a) for a in args)
        pminrow, pmincol = max(0, pminrow), max(0, pmincol)
        sminrow, smincol = max(0, sminrow), max(0, smincol)
        pmaxrow = pminrow + smaxrow - sminrow
        if pmaxrow > self._height - 1:
            smaxrow -= pmaxrow - (self._height - 1)
        pmaxcol = pmincol + smaxcol - smincol
        if pmaxcol > self._width - 1:
            smaxcol -= pmaxcol - (self._width - 1)
        screen = _require_screen()
        destination = screen.buffer
        if (
            smaxrow >= destination.height
            or smaxcol >= destination.width
            or sminrow > smaxrow
            or smincol > smaxcol
        ):
            raise _curses.error(f"{pname}() returned ERR")
        view = (pminrow, pmincol, sminrow, smincol, smaxrow, smaxcol)
        whole = view != self._pad_view
        self._pad_view = view
        for offset in range(smaxrow - sminrow + 1):
            row = pminrow + offset
            touched = self._touched.pop(row, None)
            if whole:
                first, last = pmincol, pmincol + smaxcol - smincol
            elif touched is None:
                continue
            else:
                first = max(touched[0], pmincol)
                last = min(touched[1], pmincol + smaxcol - smincol)
            for column in range(first, last + 1):
                cell = self._buffer.cell(self._offset_y + row, self._offset_x + column)
                destination.write(
                    sminrow + offset,
                    smincol + column - pmincol,
                    cell.char,
                    fg=cell.fg,
                    bg=cell.bg,
                    attr=cell.attr,
                )

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
        """Mark a rectangle of the window for copying at the next refresh.

        Args:
            y, x: The rectangle's top left, within the window.
            height, width: Its size.

        TkCurses extension:
            curses has no such call. :func:`tkcurses.panel.update_panels` uses
            it to put back what a hidden panel covered.
        """
        # The only thing that can restore the background where a panel was
        # hidden or moved away from is the window behind it - copied over just
        # that rectangle, not the whole of it.
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
        """Set the rows :meth:`scroll`, and a newline or a wrap on the
        bottom one, move: a header and a status line stay put above and
        below a scrolling log.

        Raises:
            error: Unless ``0 <= top <= bottom`` and ``bottom`` is a row of
                the window, as curses refuses it.
        """
        if not 0 <= top <= bottom < self._height:
            raise _curses.error("wsetscrreg() returned ERR")
        self._region = (top, bottom)

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
        """The rest of the cursor's row, from the cursor.

        TkCurses extension:
            curses has no such call; it is :meth:`instr` at the cursor.
        """
        return self._read(self._cursor_y, self._cursor_x, self._width).encode()

    # ------------------------------------------------------------ encoding

    @property
    def encoding(self) -> str:
        """The encoding the window's bytes are in: the locale's, as curses
        takes it at the start. A subwindow made by :meth:`subwin` takes its
        parent's, and one made by :meth:`derwin` the locale's - the standard
        library's own inconsistency, kept.

        Raises:
            TypeError: When set to anything but a string, or deleted.
        """
        return self._encoding

    @encoding.setter
    def encoding(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("setting encoding to a non-string")
        self._encoding = value

    @encoding.deleter
    def encoding(self) -> None:
        raise TypeError("encoding may not be deleted")

    # ------------------------------------------------------------- copying

    def overlay(self, destwin: Window, *args: int) -> None:
        """Copy this window's text onto ``destwin`` where they overlap on the
        screen, leaving ``destwin`` as it was wherever this one is blank.

        With six more arguments - ``sminrow, smincol, dminrow, dmincol,
        dmaxrow, dmaxcol`` - the rectangle is given instead: from
        ``(sminrow, smincol)`` in this window to ``(dminrow, dmincol)``
        through ``(dmaxrow, dmaxcol)`` in ``destwin``.

        Raises:
            error: If the windows do not overlap, or the rectangle runs off
                either window, in curses' words.
        """
        self._copy_onto(destwin, args, "overlay", over=True)

    def overwrite(self, destwin: Window, *args: int) -> None:
        """Copy this window onto ``destwin`` where they overlap on the
        screen, blanks too; with six more arguments, a rectangle, as
        :meth:`overlay` takes it.

        Raises:
            error: If the windows do not overlap, or the rectangle runs off
                either window, in curses' words.
        """
        self._copy_onto(destwin, args, "overwrite", over=False)

    def _copy_onto(
        self, destwin: Window, args: tuple[int, ...], name: str, *, over: bool
    ) -> None:
        """ncurses' ``overlap`` and ``copywin``: the overlap worked out from
        where the two windows begin, or the rectangle given."""
        if len(args) not in (0, 6):
            raise TypeError(f"_curses.window.{name} requires 1 to 7 arguments")
        if args:
            sminrow, smincol, dminrow, dmincol, dmaxrow, dmaxcol = map(int, args)
            message = "copywin() returned ERR"
        else:
            top = max(self._begin_y, destwin._begin_y)
            left = max(self._begin_x, destwin._begin_x)
            bottom = min(
                self._begin_y + self._height, destwin._begin_y + destwin._height
            )
            right = min(self._begin_x + self._width, destwin._begin_x + destwin._width)
            if bottom <= top or right <= left:
                raise _curses.error(f"{name}() returned ERR")
            sminrow, smincol = top - self._begin_y, left - self._begin_x
            dminrow, dmincol = top - destwin._begin_y, left - destwin._begin_x
            dmaxrow = bottom - 1 - destwin._begin_y
            dmaxcol = right - 1 - destwin._begin_x
            message = f"{name}() returned ERR"
        rows, columns = dmaxrow - dminrow, dmaxcol - dmincol
        if (
            min(sminrow, smincol, dminrow, dmincol) < 0
            or dmaxrow >= destwin._height
            or dmaxcol >= destwin._width
            or sminrow + rows >= self._height
            or smincol + columns >= self._width
            or rows < 0
            or columns < 0
        ):
            raise _curses.error(message)
        for row in range(rows + 1):
            for column in range(columns + 1):
                cell = self._buffer.cell(
                    self._offset_y + sminrow + row, self._offset_x + smincol + column
                )
                if not cell.char or (over and cell.char == " "):
                    continue
                destwin._buffer.write(
                    destwin._offset_y + dminrow + row,
                    destwin._offset_x + dmincol + column,
                    cell.char,
                    fg=cell.fg,
                    bg=cell.bg,
                    attr=cell.attr,
                )
            destwin._mark(dminrow + row, dmincol, dmincol + columns)

    # -------------------------------------------------------------- saving

    def putwin(self, file: Any) -> None:
        """Write the window to ``file``, opened for bytes, in ncurses' own
        format, so that :func:`getwin` - or the standard library's - can
        read it back.

        Differences from curses:
            A character beyond Latin-1 is written as its UTF-8 bytes, which
            a curses built for wide characters reads as several.
        """
        file.write(_window_text(self).encode("latin-1"))

    def __repr__(self) -> str:
        return (
            f"<tkcurses.curses.Window {self._width}x{self._height}"
            f" at ({self._begin_y}, {self._begin_x})>"
        )


# --------------------------------------------------------------------------
# putwin and getwin
# --------------------------------------------------------------------------
#
# ncurses' own text format for a saved window (write_win and read_win in
# ncurses/base/lib_screen.c), measured from the standard library's putwin
# against ncurses 6.6: four 0x88 bytes and a version line, ``name=value``
# lines for what is not the default, ``rows:``, then one line a row. In a
# row, ``\s`` is a space, ``\\`` a backslash, ``\NNN`` a byte in octal
# and ``\{BOLD|C1}`` the attributes - and colour pair - from there on.

_MAGIC = b"\x88\x88\x88\x88"

#: The attribute names ncurses writes, in its order.
_ATTRIBUTE_NAMES = (
    "STANDOUT", "UNDERLINE", "REVERSE", "BLINK", "DIM", "BOLD", "ALTCHARSET",
    "INVIS", "PROTECT", "HORIZONTAL", "LEFT", "LOW", "RIGHT", "TOP",
    "VERTICAL", "ITALIC",
)  # fmt: skip


def _screen_encoding() -> str:
    """The locale's encoding, which is what curses gives a window."""
    try:
        return locale.nl_langinfo(locale.CODESET) or "utf-8"
    except (AttributeError, ValueError):  # pragma: no cover - not POSIX
        return "utf-8"


def _attribute_bits(name: str) -> int:
    return int(getattr(_curses, f"A_{name}", 0))


def _split_attr(attr: int) -> tuple[int, int]:
    """Attributes without the character or colour, and the colour pair."""
    pair = (attr & _curses.A_COLOR) >> 8
    return attr & ~(_curses.A_COLOR | _curses.A_CHARTEXT), pair


def _attribute_spec(attrs: int, pair: int | None) -> str:
    names = [n for n in _ATTRIBUTE_NAMES if attrs & _attribute_bits(n)] or ["NORMAL"]
    if pair is not None:
        names.append(f"C{pair}")
    return "\\{" + "|".join(names) + "}"


def _escaped(char: str) -> str:
    if char == " ":
        return "\\s"
    if char == "\\":
        return "\\\\"
    if " " < char < "\x7f":
        return char
    try:
        data = char.encode("latin-1")
    except UnicodeEncodeError:
        data = char.encode("utf-8")
    return "".join(f"\\{byte:03o}" for byte in data)


def _window_text(window: Window) -> str:
    """The window in ncurses' putwin format, as text of bytes below 256."""
    version = ".".join(map(str, getattr(_curses, "ncurses_version", (6, 0, 0))))
    lines = [f"ncurses {version}"]

    def field(name: str, value: int) -> None:
        if value:
            lines.append(f"{name}={value}")

    field("_cury", window._cursor_y)
    field("_curx", window._cursor_x)
    field("_maxy", window._height - 1)
    field("_maxx", window._width - 1)
    field("_begy", 0 if window._pad else window._begin_y)
    field("_begx", 0 if window._pad else window._begin_x)
    field("_flags", (16 if window._pad else 0) | (0 if window._owns else 1))
    attrs, pair = _split_attr(window._attr)
    if attrs:
        lines.append(f"_attrs={_attribute_spec(attrs, None)}")
    for flag, on in (
        ("_clear", window._clear_ok),
        ("_leaveok", window._leave_ok),
        ("_scroll", window._scroll_ok),
        ("_idcok", True),
        ("_use_keypad", window._keypad),
    ):
        if on:
            lines.append(f"flag={flag}")
    lines.append("_delay=-1")
    top, bottom = window._region or (0, window._height - 1)
    field("_regtop", top)
    field("_regbottom", bottom)
    if window._pad:
        for name, value in zip(
            ("y", "x", "top", "left", "bottom", "right"),
            window._pad_view or (-1,) * 6,
            strict=True,
        ):
            lines.append(f"_pad._pad_{name}={value}")
    background_attrs, _ = _split_attr(window._background_attr)
    spec = _attribute_spec(background_attrs, None) if background_attrs else ""
    lines.append(f"_bkgrnd={spec}{_escaped(window._background)}")
    field("_color", pair)
    lines.append("rows:")
    for row in range(window._height):
        text, current = "", (0, 0)
        for column in range(window._width):
            cell = window._buffer.cell(
                window._offset_y + row, window._offset_x + column
            )
            if not cell.char:
                continue
            attrs, pair = _split_attr(cell.attr)
            if (attrs, pair) != current:
                text += _attribute_spec(attrs, pair if pair != current[1] else None)
                current = (attrs, pair)
            text += "".join(_escaped(char) for char in cell.char)
        lines.append(f"{row + 1}:{text}")
    return _MAGIC.decode("latin-1") + "\n".join(lines) + "\n"


def _unescaped_row(text: str) -> list[tuple[str, int]]:
    """A saved row's characters, each with its attributes."""
    cells: list[tuple[str, int]] = []
    attrs = pair = 0
    pending = bytearray()

    def settle() -> None:
        if not pending:
            return
        try:
            chars = pending.decode("utf-8")
        except UnicodeDecodeError:
            chars = pending.decode("latin-1")
        cells.extend((char, attrs | (pair << 8)) for char in chars)
        pending.clear()

    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\":
            settle()
            cells.append((char, attrs | (pair << 8)))
            index += 1
            continue
        following = text[index + 1 : index + 2]
        if following == "s":
            settle()
            cells.append((" ", attrs | (pair << 8)))
            index += 2
        elif following == "{":
            settle()
            end = text.index("}", index)
            attrs = 0
            for name in text[index + 2 : end].split("|"):
                if name.startswith("C") and name[1:].isdigit():
                    pair = int(name[1:])
                elif name != "NORMAL":
                    attrs |= _attribute_bits(name)
            index = end + 1
        elif following.isdigit():
            pending.append(int(text[index + 1 : index + 4], 8) & 0xFF)
            index += 4
        else:
            settle()
            cells.append((following, attrs | (pair << 8)))
            index += 2
    settle()
    return cells


def getwin(file: Any) -> Window:
    """Read a window :meth:`Window.putwin` wrote - or the standard
    library's - from ``file``, opened for bytes, and make it again where it
    was.

    Raises:
        error: If what is read is not a saved window.
        TypeError: If the file gives text rather than bytes.
    """
    _require_screen()
    data = file.read()
    if isinstance(data, str):
        raise TypeError("f.read() returned str instead of bytes")
    if not data.startswith(_MAGIC):
        raise _curses.error("curses function returned NULL")
    lines = data[len(_MAGIC) :].decode("latin-1").split("\n")
    if not lines[0].startswith("ncurses"):
        raise _curses.error("curses function returned NULL")
    fields: dict[str, str] = {}
    flags: set[str] = set()
    rows: list[str] = []
    in_rows = False
    for line in lines[1:]:
        if in_rows:
            if ":" in line:
                rows.append(line.split(":", 1)[1])
        elif line == "rows:":
            in_rows = True
        elif line.startswith("flag="):
            flags.add(line[5:])
        elif "=" in line:
            name, value = line.split("=", 1)
            fields[name] = value

    def number(name: str) -> int:
        return int(fields.get(name, "0"))

    height, width = number("_maxy") + 1, number("_maxx") + 1
    window = Window(
        ScreenBuffer(width, height),
        number("_begy"),
        number("_begx"),
        height,
        width,
        owns=True,
    )
    window._pad = bool(number("_flags") & 16)
    window._cursor_y, window._cursor_x = number("_cury"), number("_curx")
    attrs = sum(attr for _, attr in _unescaped_row(fields.get("_attrs", "") + "x"))
    window._attr = attrs | (number("_color") << 8)
    background = _unescaped_row(fields.get("_bkgrnd", "\\s"))
    if background:
        window._background, window._background_attr = background[-1]
    window._clear_ok = "_clear" in flags
    window._leave_ok = "_leaveok" in flags
    window._scroll_ok = "_scroll" in flags
    window._keypad = "_use_keypad" in flags
    if "_regtop" in fields or "_regbottom" in fields:
        region = (number("_regtop"), number("_regbottom"))
        if region != (0, height - 1):
            window._region = region
    for y, text in enumerate(rows[:height]):
        x = 0
        for char, attr in _unescaped_row(text):
            window._put(y, x, char, attr)
            x += max(1, char_cells(char))
    return window
