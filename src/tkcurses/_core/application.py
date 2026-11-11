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

"""State shared by every widget in one application.

tkinter keeps this in the Tcl interpreter: bindings, timers, the option
database, variable values and the clipboard are all interpreter-wide, which is
why two widgets in the same tree see each other's ``after`` handles and why
two separate ``Tk()`` instances do not. :class:`Application` is the same idea
without Tcl — one object per widget tree, reached from any widget through the
``tk`` attribute that tkinter code already expects to find there.

Keeping it in one object, rather than in module-level globals, is what makes a
second application in the same process work: tests create and discard them
constantly, and a global registry would leak bindings from one into the next.
"""

from __future__ import annotations

import fnmatch
import itertools
import weakref
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkcurses._core.bindings import BindingTable, VirtualEvents, parse_sequence
from tkcurses._core.clipboard import Selections
from tkcurses._core.errors import TclError
from tkcurses._core.events import MOD_CTRL
from tkcurses._core.input import SIGNAL_KEYS
from tkcurses._core.layout import LayoutEngine
from tkcurses._core.timers import AfterQueue

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tkcurses import Misc
    from tkcurses._core.colors import ColorManager
    from tkcurses._core.direct import DirectPainter
    from tkcurses._core.input import InputHandler
    from tkcurses._core.panels import PanelStack
    from tkcurses._core.screen import CursesScreen
    from tkcurses.ttk import Theme

__all__ = ["Application", "OptionDatabase", "WidgetRegistry"]

#: Priority names tkinter accepts for ``option_add``, with their numeric
#: weights. Higher wins; a bare integer is also allowed.
_PRIORITIES: dict[str, int] = {
    "widgetDefault": 20,
    "startupFile": 40,
    "userDefault": 60,
    "interactive": 80,
}


@dataclass(order=True)
class _Option:
    """One entry in the option database, ordered by how strongly it applies."""

    priority: int
    sequence: int
    pattern: str = field(compare=False, default="")
    value: Any = field(compare=False, default=None)


class OptionDatabase:
    """A simplified resource database.

    Tk's option database resolves a pattern against a widget's full path and
    class hierarchy, with tight and loose binding rules that almost nothing
    uses. What is kept here is the part that is used in practice: patterns
    ending in the option name, prefixed by a class name, a widget path, or
    ``*`` for anything. ``*Button.background`` and ``*background`` both work;
    per-level tight binding does not.
    """

    def __init__(self) -> None:
        self._options: list[_Option] = []
        self._sequence = 0

    def add(self, pattern: str, value: Any, priority: int | str | None = None) -> None:
        """Register ``pattern`` with ``value``.

        ``priority`` takes tkinter's names (``widgetDefault`` through
        ``interactive``) or a number. Later entries win ties, so the same
        pattern added twice behaves as a replacement.
        """
        self._sequence += 1
        self._options.append(
            _Option(
                priority=self._weight(priority),
                sequence=self._sequence,
                pattern=pattern,
                value=value,
            )
        )

    def clear(self) -> None:
        """Discard every option."""
        self._options.clear()

    def get(self, path: str, class_name: str, name: str, option_class: str = "") -> Any:
        """Best value of an option for a widget, or None.

        The widget is identified by both its path (``.frame.ok``) and its
        class (``Button``), because a pattern may select either. The option
        is identified as Tk identifies it, by its database name
        (``highlightThickness``) and class (``HighlightThickness``), and a
        pattern may end in either - case and all: measured on Tk 9.0.2,
        ``*Button.highlightthickness`` reaches no Button. The most recently
        added of the best priority wins, however specific the others: a
        later ``*highlightThickness`` beat ``*Button.HighlightThickness``.
        """
        names = (name, option_class) if option_class else (name,)
        best: _Option | None = None
        for option in self._options:
            if not self._applies(option.pattern, path, class_name, names):
                continue
            if best is None or option > best:
                best = option
        return None if best is None else best.value

    def __len__(self) -> int:
        """How many options are registered."""
        return len(self._options)

    @staticmethod
    def _weight(priority: int | str | None) -> int:
        """Numeric weight for a priority given by name, number, or not at all."""
        if priority is None:
            return _PRIORITIES["interactive"]
        if isinstance(priority, str):
            try:
                return _PRIORITIES[priority]
            except KeyError:
                raise ValueError(f"unknown option priority {priority!r}") from None
        return priority

    @staticmethod
    def _applies(
        pattern: str, path: str, class_name: str, names: tuple[str, ...]
    ) -> bool:
        """True if ``pattern`` selects an option called one of ``names`` on
        this widget.

        A pattern's last component is the option name; everything before it
        selects the widget. Both of Tk's separators end a component, ``.`` for
        one level and ``*`` for any number, and only the last one is looked
        at, which is the simplification: ``*Frame.Button.background`` selects
        on ``Button`` alone rather than on the pair. What is before the option
        is matched with shell globbing against the widget's path and against
        its class, so ``*Button.background`` and ``.dialog.ok.background``
        both find their widget.
        """
        cut = max(pattern.rfind("."), pattern.rfind("*"))
        option = pattern[cut + 1 :]
        if not option:
            return False
        if option not in names and option != "*":
            return False
        head = pattern[:cut] if cut >= 0 else ""
        if head in ("", "*"):
            return True
        return fnmatch.fnmatch(path, head) or fnmatch.fnmatch(
            class_name, head.lstrip("*.")
        )


class WidgetRegistry:
    """Every widget in the application, by path name.

    ``nametowidget`` needs it, and so does anything that has to turn a path
    string back into an object, which is how Tk's own API passes widgets
    around.
    """

    def __init__(self) -> None:
        self._widgets: dict[str, Misc] = {}

    def add(self, path: str, widget: Misc) -> None:
        """Register ``widget`` under ``path``."""
        self._widgets[path] = widget

    def remove(self, path: str) -> None:
        """Forget ``path``, if it is known."""
        self._widgets.pop(path, None)

    def get(self, path: str) -> Misc | None:
        """The widget at ``path``, or None."""
        return self._widgets.get(path)

    def __contains__(self, path: object) -> bool:
        """True if a widget is registered at ``path``."""
        return path in self._widgets

    def __len__(self) -> int:
        """How many widgets are registered."""
        return len(self._widgets)

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered paths."""
        return iter(self._widgets)


#: The clipboard virtual events every application starts with, as Tk's do
#: (``tk.tcl`` defines them at startup). Tk's own sequences, MEASURED on Tk
#: 9.0.2 with ``event_info``, less the ones measured not to reach a program in
#: a terminal (TkCurses-lw2, a key probe run in the author's terminal):
#:
#: * ``Control-c`` is NOT here. It is the close gesture, and copies only when
#:   the focused widget has a selection - decided in the interrupt handler,
#:   not by a binding, because binding ``<Control-c>`` takes the key from the
#:   tty and there would be no close gesture left. See ``Misc.mainloop``.
#: * ``F16``/``F18``/``F20`` and ``Meta-w`` are not here: function keys past
#:   F12 arrive undecoded, and Alt arrives as Escape then the letter.
#: * ``Shift-Insert`` stays, though many terminals keep it for their own
#:   paste - in the author's it typed the system clipboard in as keystrokes,
#:   which is a paste anyway. ``Control-Insert`` likewise, for the terminals
#:   that pass it.
DEFAULT_VIRTUAL_EVENTS: dict[str, tuple[str, ...]] = {
    "<<Copy>>": ("<Control-Key-Insert>",),
    "<<Cut>>": ("<Control-Key-x>", "<Control-Key-w>", "<Shift-Key-Delete>"),
    "<<Paste>>": ("<Control-Key-v>", "<Control-Key-y>", "<Shift-Key-Insert>"),
    "<<PasteSelection>>": ("<ButtonRelease-2>",),
    # Both: Tk's own is Control-slash, but a terminal sends one byte, 0x1f,
    # for Ctrl-/ and Ctrl-_ alike, and it is decoded as underscore - measured
    # in a pty. Without the second, Ctrl-/ would select nothing.
    "<<SelectAll>>": ("<Control-Key-slash>", "<Control-Key-underscore>"),
    "<<Clear>>": (),
    # tk.tcl's X11 keys less the Lock forms: a terminal sends Control-z as
    # 0x1A whatever Caps Lock says, so Lock never reaches a binding. Control-
    # Shift-z is the same byte as Control-z and arrives only from a terminal
    # that reports modifiers. Control-z is the tty's suspend key, and is
    # taken from it only while a Text with -undo has the focus - see
    # Application.refresh_signal_keys. Alt-z, which a terminal can send, is
    # Text's own binding, not a sequence here: Tk 9.0.2 never fires a virtual
    # event of two keys (VirtualEvents.add). TkCurses-5t48.
    "<<Undo>>": ("<Control-Key-z>",),
    "<<Redo>>": ("<Control-Key-Z>",),
    # The navigation events, as tk.tcl defines them for X11 and in its
    # order - the order settles which of two runs when both fit a key
    # equally. Not <<SelectNone>>: its Control-backslash is the tty's quit
    # key. TkCurses-yu5l. With the emacs keys tk::EventMotifBindings adds
    # while tk_strictMotif is off, as it is unless a program sets it, less
    # their Select forms: Control-B is the byte Control-b is, so a terminal
    # cannot send it. TkCurses-wmaq.
    "<<NextChar>>": ("<Key-Right>", "<Control-Key-f>"),
    "<<SelectNextChar>>": ("<Shift-Key-Right>",),
    "<<PrevChar>>": ("<Key-Left>", "<Control-Key-b>"),
    "<<SelectPrevChar>>": ("<Shift-Key-Left>",),
    "<<NextWord>>": ("<Control-Key-Right>",),
    "<<SelectNextWord>>": ("<Control-Shift-Key-Right>",),
    "<<PrevWord>>": ("<Control-Key-Left>",),
    "<<SelectPrevWord>>": ("<Control-Shift-Key-Left>",),
    "<<LineStart>>": ("<Key-Home>", "<Control-Key-a>"),
    "<<SelectLineStart>>": ("<Shift-Key-Home>",),
    "<<LineEnd>>": ("<Key-End>", "<Control-Key-e>"),
    "<<SelectLineEnd>>": ("<Shift-Key-End>",),
    "<<PrevLine>>": ("<Key-Up>", "<Control-Key-p>"),
    "<<NextLine>>": ("<Key-Down>", "<Control-Key-n>"),
    "<<SelectPrevLine>>": ("<Shift-Key-Up>",),
    "<<SelectNextLine>>": ("<Shift-Key-Down>",),
    "<<PrevPara>>": ("<Control-Key-Up>",),
    "<<NextPara>>": ("<Control-Key-Down>",),
    "<<SelectPrevPara>>": ("<Control-Shift-Key-Up>",),
    "<<SelectNextPara>>": ("<Control-Shift-Key-Down>",),
}


#: The Tcl and Tk TkCurses follows: what ``info patchlevel`` answers.
TCL_PATCHLEVEL = "9.0.2"
TCL_VERSION = "9.0"

#: Tk 9.0.2's ``tk`` subcommands, in the order its refusal lists them.
_TK_SUBCOMMANDS = (
    "appname", "busy", "caret", "fontchooser", "inactive", "print", "scaling",
    "sysnotify", "systray", "useinputmethods", "windowingsystem",
)  # fmt: skip


def _tcl_double(value: Any) -> float:
    """``value`` as Tcl reads a floating-point number, or Tcl's refusal."""
    text = str(value).strip()
    try:
        if "_" in text or text.lower().lstrip("+-") in ("nan", "inf", "infinity"):
            raise ValueError
        return float(text)
    except ValueError:
        raise TclError(f'expected floating-point number but got "{value}"') from None


class Application:
    """One widget tree's shared state.

    Every widget holds a reference to the same instance; ``Tk()`` creates it
    and children inherit it from their master.
    """

    def __init__(self) -> None:
        self.bindings = BindingTable(on_change=self.refresh_signal_keys)
        self.virtual_events = VirtualEvents()
        for virtual, sequences in DEFAULT_VIRTUAL_EVENTS.items():
            self.virtual_events.add(
                virtual, *(parse_sequence(sequence) for sequence in sequences)
            )
        # After the defaults: there is no terminal to tell about them yet.
        self.virtual_events.on_change = self.refresh_signal_keys
        self.timers = AfterQueue()
        self.selections = Selections()
        self.options = OptionDatabase()
        self.widgets = WidgetRegistry()
        self.layout = LayoutEngine()

        #: Values behind ``getvar``/``setvar`` and the Variable classes.
        self.variables: dict[str, Any] = {}

        #: Traces on those values, by variable name and then by handle: each
        #: is ``(modes, callback, listed)``. By name, as Tcl keeps them, so
        #: every Variable of one name, ``setvar`` and a widget bound by name
        #: all fire and hear the same traces. ``listed`` is False for a
        #: widget's own, which Tk keeps in C where ``trace info`` cannot
        #: see them.
        self.variable_traces: dict[str, dict[str, tuple[Any, ...]]] = {}
        self.trace_counter = itertools.count(1)
        #: Tk's text debug flag, which every Text shares; see Text.debug.
        self.text_debug = False

        #: The drag in progress, if any. tkinter keeps this on the root as a
        #: name-mangled attribute; it belongs with the rest of the per-tree
        #: state, and being here is what lets a second dnd_start find it.
        self.dnd: Any = None

        #: Named fonts, by name, as tkcurses.font creates them. Tk keeps
        #: these in the interpreter and widgets name one in their ``font``
        #: option; this is where a widget looks the name up to find out
        #: what styling it stands for.
        self.fonts: dict[str, dict[str, Any]] = {}

        #: Images by name, as PhotoImage and BitmapImage create them.
        #: Widgets name one in their ``image`` option rather than holding
        #: the object, which is how Tk refers to an image and what lets
        #: ``cget("image")`` give a name back. Weak: an image that nothing
        #: else references is gone, exactly as in Tk, where a widget showing
        #: a collected image keeps its size and shows nothing - the trap
        #: every tkinter tutorial warns about, reproduced rather than fixed.
        self.images: weakref.WeakValueDictionary[str, Any] = (
            weakref.WeakValueDictionary()
        )

        #: Variable objects the library itself owns, by name. A Variable
        #: forgets its value when the last reference to it goes, so a
        #: default shared by several widgets - Tk's ``selectedButton``
        #: radiobutton group - cannot be a new object per widget: destroying
        #: any one of them would wipe the group's value. Held here instead,
        #: so it lives as long as the application and no longer.
        self.shared_variables: dict[str, Any] = {}

        #: Widget that currently has keyboard focus, and the last widget to
        #: have had it within each toplevel, which is what focus_lastfor()
        #: reports and what a toplevel restores when it is raised again.
        self._focus: Misc | None = None
        self.focus_history: dict[int, Misc] = {}

        #: Set by tk_focusFollowsMouse(), which is one-way in Tk: there is no
        #: call to turn it back off.
        self.focus_follows_mouse = False

        #: Where the mouse was last seen, in cells. Curses reports a position
        #: only when the mouse does something, so this is the last report
        #: rather than a live query, which is all winfo_pointerxy() can offer.
        self.pointer: tuple[int, int] = (0, 0)

        #: The running screen, once Tk() has started one. winfo_screenwidth()
        #: and friends ask it for the terminal size and fall back to the
        #: environment when no screen is up, so they work before mainloop().
        self.screen: CursesScreen | None = None

        #: The running input handler, once Tk() has started one. Held here
        #: so that binding a key the terminal would otherwise swallow can
        #: reach the tty, which is the one thing the binding table's
        #: contents - rather than the events it dispatches - decide.
        self.input: InputHandler | None = None

        #: The z-ordered windows, once Tk() has started curses. None until
        #: then: a panel is a curses window, and there are none before
        #: initscr(). Widgets track where they would be laid out regardless,
        #: so the tree is fully formed by the time a stack exists to build it
        #: on - and a test can install one with stub factories to exercise the
        #: lifecycle without a terminal.
        self.panels: PanelStack | None = None

        #: Colour pairs, once Tk has started curses. None until then, and a
        #: widget asked to draw without one falls back to attributes alone -
        #: a terminal with no colour behaves the same way.
        self.colors: ColorManager | None = None

        #: Cells written past curses, for pictures that want more colour
        #: combinations than curses can name. None until Tk has started.
        #: See :mod:`tkcurses._core.direct`.
        self.painter: DirectPainter | None = None

        #: Widget holding the input grab, and whether it is global. A grab
        #: diverts events away from the rest of the application, which is how
        #: a modal dialog stays modal.
        self.grab: Misc | None = None
        self.grab_global = False

        #: The ttk style database, one per application so that a Style()
        #: made anywhere changes widgets made anywhere else - which is what
        #: tkinter gets by talking to the interpreter. None until the first
        #: Style() is constructed, since an application using none of ttk
        #: should not pay for six themes.
        self.themes: dict[str, Theme] | None = None

        #: Which of them is in use.
        self.theme_in_use = "default"

        #: Widget classes whose default bindings have been installed. Class
        #: bindings are per application, and a widget registering its own on
        #: every instance would stack up one copy per widget.
        self.bound_classes: set[str] = set()

        #: The pending step of whatever is auto-repeating while a mouse button
        #: is held - a Button, a Scale's trough, a Scrollbar's arrow or a
        #: Spinbox's - as an ``after`` handle. One for the application, as
        #: Tk's ``Priv(afterId)`` is: only one thing can be held at a time.
        self.repeat: str | None = None

        #: The screen's width in millimetres once ``tk scaling`` has set it,
        #: as Tk keeps it; None for ten cells to the inch.
        self.screen_millimetres: float | None = None

        #: Counters behind automatic widget names (!button, !button2).
        self.name_counts: dict[str, int] = {}

        #: Set by quit(); the main loop checks it. It lives here rather than
        #: on the root widget so that quit() works from any widget, as it
        #: does in tkinter.
        self.quit_requested = False

    def call(self, *args: Any) -> Any:
        """Run a Tcl command, as ``widget.tk.call`` does in tkinter - the few
        a tkinter program reaches for.

        There is no Tcl interpreter here: a command works only if TkCurses
        serves it. Served, each answering as Tk 9.0.2 does through tkinter:

        * ``info patchlevel`` and ``info tclversion``;
        * ``tk windowingsystem``, which is ``x11``: the keys, the mouse and
          the virtual events here follow Tk's X11 bindings;
        * ``tk scaling``, read and set;
        * on any widget, ``cget`` and ``configure`` with Tk's arguments -
          ``tk.call(button, "configure", "-text", "Go")``;
        * a Treeview's ``cellselection``.

        The first argument is a command name or a widget (or its path name);
        a single tuple of every argument is taken too, as tkinter takes it.
        Answers come back as tkinter gives them: ``""`` for nothing, a tuple
        for a list.

        Raises:
            TclError: In Tk's words for a mistake in a served command, and
                saying so for a command TkCurses does not serve.
        """
        if len(args) == 1 and isinstance(args[0], (tuple, list)):
            args = tuple(args[0])
        if not args:
            raise TclError("TkCurses has no Tcl interpreter: call needs a command")
        command = str(args[0])
        widget = self.widgets.get(command)
        if widget is not None:
            if len(args) < 2:
                raise TclError(f'wrong # args: should be "{command} option ?arg ...?"')
            return widget._tcl_command(str(args[1]), args[2:])
        if command == "info":
            return self._info_command(args[1:])
        if command == "tk":
            return self._tk_command(args[1:])
        if command.startswith("."):
            raise TclError(f'invalid command name "{command}"')
        raise TclError(f'TkCurses has no Tcl interpreter: it does not run "{command}"')

    def _info_command(self, args: tuple[Any, ...]) -> str:
        """``info patchlevel`` and ``info tclversion``: the Tcl TkCurses
        follows, 9.0.2, as Tk 9.0.2 ships with it."""
        if not args:
            raise TclError('wrong # args: should be "info subcommand ?arg ...?"')
        answers = {"patchlevel": TCL_PATCHLEVEL, "tclversion": TCL_VERSION}
        name = str(args[0])
        if name not in answers:
            raise TclError(f'TkCurses does not interpret "info {name}"')
        if len(args) > 1:
            raise TclError(f'wrong # args: should be "info {name}"')
        return answers[name]

    def _tk_command(self, args: tuple[Any, ...]) -> Any:
        """``tk windowingsystem`` and ``tk scaling``; Tk's table for the
        rest, so a misspelling is refused as Tk refuses it."""
        if not args:
            raise TclError('wrong # args: should be "tk subcommand ?arg ...?"')
        given = str(args[0])
        matches = [name for name in _TK_SUBCOMMANDS if name.startswith(given)]
        if given in _TK_SUBCOMMANDS:
            matches = [given]
        if len(matches) != 1:
            listed = ", ".join(_TK_SUBCOMMANDS[:-1]) + f", or {_TK_SUBCOMMANDS[-1]}"
            raise TclError(
                f'unknown or ambiguous subcommand "{given}": must be {listed}'
            )
        name = matches[0]
        if name == "windowingsystem":
            if len(args) > 1:
                raise TclError('wrong # args: should be "tk windowingsystem"')
            return "x11"
        if name == "scaling":
            return self._scaling(args[1:])
        raise TclError(f'TkCurses does not interpret "tk {name}"')

    def _scaling(self, args: tuple[Any, ...]) -> Any:
        """``tk scaling ?-displayof window? ?factor?``: pixels per point.

        A pixel here is a cell, at ten to the inch, so it starts at 10/72.
        Setting it follows ScalingCmd in Tk's tkCmds.c: Tk keeps no factor,
        it gives the screen a new width in millimetres, rounded and at least
        one, and reads the factor back from that - so 2.0 reads back a
        little off, and nothing above zero is refused, while zero or less
        reads back as large as the screen allows. The terminal's columns are
        the screen's pixels.

        It is read back and changes nothing else: a cell does not grow, so
        distances stay ten cells to the inch whatever it is set to.
        """
        if args and str(args[0]) == "-displayof":
            if len(args) < 2:
                raise TclError('value for "-displayof" missing')
            if self.widgets.get(str(args[1])) is None:
                raise TclError(f'bad window path name "{args[1]}"')
            args = args[2:]
        if len(args) > 1:
            raise TclError(
                'wrong # args: should be "tk scaling ?-displayof window? ?factor?"'
            )
        columns = max(1, self._screen_columns())
        if not args:
            millimetres = self.screen_millimetres or columns * 25.4 / 10.0
            return 25.4 / 72 * columns / millimetres
        factor = _tcl_double(args[0])
        width = int((25.4 / 72) / factor * columns + 0.5) if factor > 0 else 0
        self.screen_millimetres = max(1, width)
        return ""

    def _screen_columns(self) -> int:
        """The terminal's width in cells: the screen's, or the environment's
        before there is one."""
        if self.screen is not None and getattr(self.screen, "started", False):
            return int(self.screen.size.width)
        import shutil

        return shutil.get_terminal_size((80, 24)).columns

    def splitlist(self, value: Any) -> tuple[Any, ...]:
        """A Tcl list's elements as a tuple, as tkinter's ``splitlist``.

        A tuple is handed back as it is and a list as a tuple; a string is
        split as Tcl splits a list, braces and quotes included.
        """
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        from tkcurses import _tcl_list

        return tuple(_tcl_list(value))

    @property
    def focus(self) -> Misc | None:
        return self._focus

    @focus.setter
    def focus(self, widget: Misc | None) -> None:
        changed = widget is not self._focus
        self._focus = widget
        if changed:
            self.refresh_signal_keys()

    def repaint(self) -> None:
        """Paint the whole terminal again: the cells, then the widgets.

        For putting the screen right after something has written to the
        terminal behind this library's back. The screen alone is not enough.
        Its repaint covers the cells under the widgets, and every widget is
        a curses panel above them, which curses then believes is already on
        the terminal and never sends again - so a repaint of the cells alone
        wiped every widget off the screen and left them off. TkCurses-wbpi.
        """
        if self.screen is None or not self.screen.started:
            return
        self.screen.repaint()
        if self.panels is not None:
            self.panels.touch_all()
            self.panels.update()

    def refresh_signal_keys(self) -> None:
        """Take back from the tty exactly the signal keys something binds.

        Binding ``<Control-c>`` is itself the request: a tkinter developer
        writes the binding and expects it to fire, and there is no second
        switch to find. The terminal gives up only the key actually bound,
        so an application that binds Control-C still answers Control-
        backslash if it stops responding - and unbinding gives the signal
        straight back.

        Called whenever anything is bound or unbound, a virtual event's keys
        change or the focus moves, and again when the input handler arrives,
        since bindings are usually made before there is a terminal to tell.

        The focused widget may claim keys of its own, through
        ``_claimed_signal_keys``: a Text with ``-undo`` takes Control-z for
        ``<<Undo>>`` while it has the focus, and gives suspend back when it
        loses it, so a program with a Text still suspends from everywhere
        else. TkCurses-5t48.
        """
        handler = self.input
        if handler is None:
            return
        wanted = self.bindings.details_bound_with(MOD_CTRL) & set(SIGNAL_KEYS)
        claims = getattr(self._focus, "_claimed_signal_keys", None)
        if claims is not None:
            wanted |= claims()
        handler.claim_signal_keys(wanted)

    def next_name(self, class_name: str) -> str:
        """An unused automatic widget name for ``class_name``.

        Matches tkinter's scheme: the first Button is ``!button``, the second
        ``!button2``. Code that prints widget paths in a test or a log then
        reads the same under either library.
        """
        count = self.name_counts.get(class_name, 0) + 1
        self.name_counts[class_name] = count
        suffix = "" if count == 1 else str(count)
        return f"!{class_name.lower()}{suffix}"
