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
import curses
import itertools
import os
import re
import sys
import time
import traceback
from dataclasses import replace
from typing import TYPE_CHECKING, Any, ClassVar

from tkcurses._core.application import Application
from tkcurses._core.attributes import for_state, from_font, style_for_relief
from tkcurses._core.bindings import (
    EventPattern,
    parse_sequence,
    pattern_for_event,
)
from tkcurses._core.clipboard import CLIPBOARD, PRIMARY
from tkcurses._core.colors import ColorManager, palette_rgb, parse_color, rgb_for
from tkcurses._core.dispatcher import CursesDispatcher
from tkcurses._core.editing import TextField
from tkcurses._core.errors import TclError, TkCursesError
from tkcurses._core.events import MOD_SHIFT, KeyEvent, MouseEvent, ResizeEvent
from tkcurses._core.events import Event as CoreEvent
from tkcurses._core.geometry import (
    BORDER_WIDTH,
    Insets,
    Rect,
    Size,
    clamp,
    clip_text,
    content_rect,
)
from tkcurses._core.grid import (
    GridLayout,
    GridOptions,
    LineConfig,
    parse_sticky,
)
from tkcurses._core.input import InputHandler
from tkcurses._core.pack import FILLS, SIDES, PackLayout, PackOptions, parse_anchor
from tkcurses._core.panels import PanelStack
from tkcurses._core.place import BORDERMODES, PlaceLayout, PlaceOptions
from tkcurses._core.screen import CursesScreen
from tkcurses._core.text import align_offset, measure, wrap
from tkcurses.constants import ANCHOR, END, FLAT, INSERT, SEL_FIRST, SEL_LAST

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from tkcurses._core.layout import Layout
    from tkcurses._core.panels import Panel

__version__ = "0.1.0"

__all__ = [
    "BaseWidget",
    "BooleanVar",
    "Button",
    "Checkbutton",
    "DoubleVar",
    "Entry",
    "Event",
    "Frame",
    "Grid",
    "IntVar",
    "Label",
    "Listbox",
    "Misc",
    "NoDefaultRoot",
    "Pack",
    "Place",
    "Scrollbar",
    "StringVar",
    "TclError",
    "Tk",
    "TkCursesError",
    "Toplevel",
    "Variable",
    "Widget",
    "Wm",
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
    - that one is named by ``winfo_manager()``. A widget can be packed into
    its parent while gridding its own children.
    """

    #: True for Tk and Toplevel. Bindings, focus history and coordinate
    #: origins all stop at a toplevel, so the widget layer marks them here.
    _is_toplevel = False

    #: State shared with every other widget in the same application.
    tk: Application

    #: The parent widget, None for the root of the tree.
    master: Misc | None

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
        #: The geometry manager laying out this widget's children, and
        #: whether this widget resizes itself to fit them.
        self._layout_manager: Layout | None = None
        self._layout_propagate = True
        #: The stacked window this widget draws into, once it has one.
        self._panel: Panel | None = None
        self._mapped = False
        self._takefocus = True
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
            if widget._takefocus and widget is not self.winfo_toplevel()
        ]
        if not order:
            return None
        try:
            index = order.index(self)
        except ValueError:
            return order[0 if direction > 0 else -1]
        return order[(index + direction) % len(order)]

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
        return self.tk.timers.after(ms, func, *args)

    def after_idle(self, func: Callable[..., Any], *args: Any) -> str:
        """Run ``func`` when the event loop next has nothing else to do."""
        return self.tk.timers.after_idle(func, *args)

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
            with contextlib.suppress(curses.error):
                curses.beep()
            return
        with contextlib.suppress(OSError, ValueError):
            sys.stdout.write("\a")
            sys.stdout.flush()

    # ==================================================================
    # Clipboard and selection
    # ==================================================================

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
        """Claim the selection for this widget."""
        self.tk.selections.own(self, kw.get("selection", PRIMARY))

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
        return content_rect(
            rect,
            bordered=self._bordered,
            padding=Insets.symmetric(
                horizontal=int(self._options.get("padx", 0)),
                vertical=int(self._options.get("pady", 0)),
            ),
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
        return list(manager.slaves(self))

    slaves = pack_slaves

    def grid_slaves(
        self, row: int | None = None, column: int | None = None
    ) -> list[Misc]:
        """The children this container is gridding, optionally in one cell."""
        manager = self._layout_manager
        if not isinstance(manager, GridLayout):
            return []
        return list(manager.slaves(self, row=row, column=column))

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
        self, index: int, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> Any:
        """Get or set how one row behaves: weight, minsize, pad, uniform."""
        return self._line_configure("row", index, cnf, kw)

    def grid_columnconfigure(
        self, index: int, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> Any:
        """Get or set how one column behaves."""
        return self._line_configure("column", index, cnf, kw)

    rowconfigure = grid_rowconfigure
    columnconfigure = grid_columnconfigure

    def _line_configure(
        self, axis: str, index: int, cnf: dict[str, Any] | None, kw: dict[str, Any]
    ) -> Any:
        """Shared implementation of grid_rowconfigure and grid_columnconfigure.

        Raises:
            TclError: If an option is not one Tk accepts for a grid line.
        """
        manager = _grid_layout_of(self)
        current = (
            manager.row_config(index) if axis == "row" else manager.column_config(index)
        )
        given = {**(cnf or {}), **kw}
        if not given:
            return {
                "weight": current.weight,
                "minsize": current.minsize,
                "pad": current.pad,
                "uniform": current.uniform,
            }
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
        return list(manager.slaves(self))

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
        return curses.COLORS if self.tk.screen is not None else 8

    def winfo_depth(self) -> int:
        """Bits per cell, derived from the colour count."""
        return max(1, self.winfo_cells().bit_length() - 1)

    def winfo_screendepth(self) -> int:
        """Bits per cell for the screen, which is the only display there is."""
        return self.winfo_depth()

    def winfo_rgb(self, color: str) -> tuple[int, int, int]:
        """A colour's channel values, 16 bits each, as tkinter reports them.

        For a name or a hex string the terminal cannot show exactly, this is
        what will actually be rendered rather than what was asked for: there
        are eight colours to choose from, and reporting the request back would
        hide the approximation.
        """
        direct = rgb_for(color)
        rgb = direct if direct is not None else palette_rgb(parse_color(color))
        return (rgb[0] * 257, rgb[1] * 257, rgb[2] * 257)

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
        """
        options = {**(cnf or {}), **kw}
        if not options:
            return dict(self._options)
        for key, value in options.items():
            self._options[key] = value
        return None

    config = configure

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
_OPTION_ALIASES: dict[str, str] = {
    "bg": "background",
    "fg": "foreground",
    "bd": "borderwidth",
}

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

    #: Options every widget accepts. The set is deliberately smaller than
    #: tkinter's: X11 options with no cell equivalent (highlightthickness,
    #: screen distances in pixels) are left out rather than accepted and
    #: ignored, so that setting one fails loudly instead of quietly.
    _widget_options: ClassVar[dict[str, Any]] = {
        "background": "",
        "borderwidth": 0,
        "cursor": "",
        "foreground": "",
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
        self._options = self._initial_options({**(cnf or {}), **kw})
        self._takefocus = bool(self._options.get("takefocus", False))

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

    def _checked(self, given: dict[str, Any]) -> dict[str, Any]:
        """Resolve aliases and reject anything this widget does not accept."""
        spec = self._option_spec()
        resolved: dict[str, Any] = {}
        for name, value in given.items():
            option = _OPTION_ALIASES.get(name, name)
            if option not in spec:
                raise TclError(f'unknown option "-{name}"')
            resolved[option] = value
        return resolved

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, or return them all when called with none.

        Raises:
            TclError: If an option is not one this widget accepts.
        """
        given = {**(cnf or {}), **kw}
        if not given:
            return dict(self._options)
        self._options.update(self._checked(given))
        if "takefocus" in self._options:
            self._takefocus = bool(self._options["takefocus"])
        return None

    config = configure

    def cget(self, key: str) -> Any:
        """The value of one option, accepting the short spellings.

        Raises:
            TclError: If this widget has no such option.
        """
        option = _OPTION_ALIASES.get(key, key)
        try:
            return self._options[option]
        except KeyError:
            raise TclError(f'unknown option "-{key}"') from None

    def keys(self) -> list[str]:
        """The option names this widget accepts, sorted."""
        return sorted(self._option_spec())

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
        if (rect.width, rect.height) != (previous.width, previous.height) and (
            self._layout_manager is not None
        ):
            # A container given a new size has to place its children again.
            # Propagation travels upward - what a widget needs - and this is
            # the other direction: what it was actually given. Without it a
            # container laid out before its own parent keeps children sized
            # against a region it no longer has.
            self.tk.layout.invalidate(self)
        stack = self.tk.panels
        if stack is None:
            return
        if rect.is_empty:
            self._destroy_window()
            return
        if self._panel is None:
            if self._mapped:
                self._create_window()
            return
        # Compared against where the panel actually is, not against the
        # widget's previous rect: a rect is an offset from the master, so an
        # ancestor moving relocates the panel without changing it.
        target = self._visible_rect()
        if target.is_empty:
            # Entirely off screen. The widget keeps its geometry and gets its
            # window back when it comes into view again.
            self._destroy_window()
            return
        current = self._panel.rect
        if (target.width, target.height) != (current.width, current.height):
            # Curses cannot resize a window in place, and replacing it is also
            # what keeps a shrink from leaving the vacated cells behind.
            stack.replace_window(self._panel, target)
            self._redraw()
        elif (target.x, target.y) != (current.x, current.y):
            stack.move(self._panel, target.x, target.y)
            self._redraw()

    def _map(self) -> None:
        """Put the widget on screen, creating its window if it has none.

        Idempotent: a geometry manager may re-map a widget it has already
        placed, and mapping twice should not raise ``<Map>`` twice.
        """
        if self._mapped:
            return
        self._mapped = True
        self._create_window()
        self.event_generate("<Map>")

    def _unmap(self) -> None:
        """Take the widget off screen, keeping its window for a later map.

        The window is hidden rather than destroyed, because an unmapped
        widget is usually on its way back - a notebook tab, a hidden frame -
        and rebuilding the window each time would throw away its contents.
        """
        if not self._mapped:
            return
        self._mapped = False
        if self._panel is not None:
            self.tk.panels.hide(self._panel)  # type: ignore[union-attr]
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
        _manager: str

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...

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
        options = {**(cnf or {}), **kw}
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot pack the root window")
        before = options.pop("before", None)
        after = options.pop("after", None)

        layout = _pack_layout_of(container)
        layout.add(self, _pack_options(options), before=before, after=after)
        self._manager = "pack"
        self._map()
        container.tk.layout.invalidate(container)

    pack = pack_configure

    def pack_forget(self) -> None:
        """Stop packing this widget and take it off the screen.

        Its packing options are forgotten, which is what will separate this
        from ``grid_remove``: packing it again starts from the defaults.
        """
        container = self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, PackLayout):
            manager.remove(self)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._unmap()

    forget = pack_forget

    def pack_info(self) -> dict[str, Any]:
        """How this widget is packed.

        Raises:
            TclError: If it is not packed. Tk reports that rather than
                returning defaults, which would read as though it were.
        """
        container = self.master
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
            "padx": options.padx,
            "pady": options.pady,
            "ipadx": options.ipadx,
            "ipady": options.ipady,
        }

    info = pack_info


#: What each layout class is called in the error a mixed container raises.
_MANAGER_NAMES = {
    "PackLayout": "pack",
    "GridLayout": "grid",
    "PlaceLayout": "place",
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


def _pack_options(given: dict[str, Any]) -> PackOptions:
    """Build and check one widget's packing options.

    Raises:
        TclError: If an option is unknown or its value is not one Tk accepts.
            Checked here rather than left to produce a strange layout later: a
            misspelled ``fill`` is otherwise invisible.
    """
    options = PackOptions()
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
    for name in ("padx", "pady", "ipadx", "ipady"):
        value = getattr(options, name)
        try:
            setattr(options, name, max(0, int(value)))
        except (TypeError, ValueError):
            raise TclError(f'bad pad value "{value}"') from None
    return options


class Grid:
    """Gridding: place a widget in a row and a column.

    The mixin half of the grid manager; the sizing is in
    :mod:`tkcurses._core.grid`.
    """

    if TYPE_CHECKING:
        master: Misc | None
        _manager: str

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...

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
        options = {**(cnf or {}), **kw}
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot grid the root window")
        layout = _grid_layout_of(container)
        remembered = layout.remembered(self)
        if not options and remembered is not None:
            layout.add(self, remembered)
        else:
            layout.add(self, _grid_options(options, remembered))
        self._manager = "grid"
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
        container = self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, GridLayout):
            manager.remove(self, keep=keep)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._unmap()

    def grid_info(self) -> dict[str, Any]:
        """Where this widget sits in the grid.

        Raises:
            TclError: If it is not gridded.
        """
        container = self.master
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
            "padx": options.padx,
            "pady": options.pady,
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
    for name in ("row", "column", "padx", "pady", "ipadx", "ipady"):
        value = getattr(options, name)
        try:
            setattr(options, name, max(0, int(value)))
        except (TypeError, ValueError):
            raise TclError(f'expected integer but got "{value}"') from None
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
        _manager: str

        def _map(self) -> None: ...
        def _unmap(self) -> None: ...

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
        options = {**(cnf or {}), **kw}
        container = options.pop("in_", None) or options.pop("in", None) or self.master
        if container is None:
            raise TclError("cannot place the root window")
        layout = _place_layout_of(container)
        layout.add(self, _place_options(options))
        self._manager = "place"
        self._map()
        container.tk.layout.invalidate(container)

    place = place_configure

    def place_forget(self) -> None:
        """Stop placing this widget and take it off the screen."""
        container = self.master
        if container is None:
            return
        manager = container._layout_manager
        if isinstance(manager, PlaceLayout):
            manager.remove(self)
            container.tk.layout.invalidate(container)
        self._manager = ""
        self._unmap()

    def place_info(self) -> dict[str, Any]:
        """How this widget is placed.

        Raises:
            TclError: If it is not placed.
        """
        container = self.master
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


def _place_options(given: dict[str, Any]) -> PlaceOptions:
    """Build and check one widget's placement options.

    Raises:
        TclError: If an option is unknown or its value is not one Tk accepts.
    """
    options = PlaceOptions()
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

    Two consequences run through the whole class. Geometry is clamped to the
    terminal, because there is nowhere for a window to overflow to. And
    nothing raises ``WM_DELETE_WINDOW`` on its own: no user gesture closes a
    window here, so an application that wants the protocol must invoke it.
    """

    if TYPE_CHECKING:
        # Supplied by the widget this is mixed into. Declared so the contract
        # is visible and so a mixin referring to them still type-checks.
        tk: Application
        _rect: Rect
        _options: dict[str, Any]
        _is_toplevel: bool

        def _allocate(self, rect: Rect) -> None: ...
        def _map(self) -> None: ...
        def _unmap(self) -> None: ...
        def _screen_size(self) -> tuple[int, int]: ...
        def winfo_exists(self) -> bool: ...
        def tkraise(self, aboveThis: Misc | None = None) -> None: ...

    def _setup_wm(self) -> None:
        """Initialise the window manager state.

        Called from the constructor of each window class rather than from an
        ``__init__`` here: the mixin has no say in the order a widget builds
        itself, and these defaults have to be in place before geometry is.
        """
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

    def _is_resizable_window(self) -> bool:
        """False for the root, whose geometry the terminal decides."""
        return not isinstance(self, Tk)

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
        x = clamp(x, 0, max(0, screen_width - width))
        y = clamp(y, 0, max(0, screen_height - height))
        self._allocate(Rect(x, y, width, height))

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
        width, height = self._clamp_size(self._rect.width, self._rect.height)
        if (width, height) != (self._rect.width, self._rect.height):
            self._allocate(Rect(self._rect.x, self._rect.y, width, height))

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

        ``WM_DELETE_WINDOW`` is the one worth having, and nothing raises it:
        a terminal offers no close button and no user gesture that means
        "close this window". An application that wants it must call
        :meth:`_invoke_protocol`, typically from a key binding, and the
        dialogs will do the same once they exist.
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

#: How long ncurses waits for the rest of an escape sequence before deciding
#: a lone Escape was meant. Tracked as TkCurses-dn5 for a config option; this
#: is the value most terminal applications settle on.
_ESCAPE_DELAY_MS = 25

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
    _widget_options: ClassVar[dict[str, Any]] = {}

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
            useTk: Ignored; there is no Tcl-without-Tk mode to select.
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

        self._screen = CursesScreen()
        self._mouse_owner: Misc | None = None
        self._input: InputHandler | None = None
        self._started = False
        self._running = False

        if useTk:
            self._start()

        self._install_default_bindings()
        _active_root = self
        if _default_root is None and _support_default_root:
            _default_root = self

    # ------------------------------------------------------------- startup

    def _start(self) -> None:
        """Initialise curses and hang the screen-dependent pieces off it.

        Anything that fails here must still give the terminal back, which is
        why the whole body is guarded rather than just the parts that look
        risky: ``initscr()`` has already changed the terminal by the time the
        next line runs.
        """
        buffer = self._screen.start()
        try:
            # ncurses cannot tell a lone Escape from the start of an escape
            # sequence until this long has passed with nothing following. The
            # default is a full second, which makes Escape - the key that
            # cancels things - feel broken. Every terminal in use sends the
            # rest of a sequence in the same packet, so a short wait loses
            # nothing and makes the key usable.
            with contextlib.suppress(AttributeError, curses.error):
                curses.set_escdelay(_ESCAPE_DELAY_MS)
            self._input = InputHandler(self._screen.stdscr)
            colors = ColorManager()
            if colors.start():
                # Cells are painted through this; without colour support the
                # screen keeps its attributes-only resolver.
                self._screen.attribute_resolver = colors.attribute_for
                self.tk.colors = colors
            self.tk.screen = self._screen
            self.tk.panels = PanelStack()
            self._rect = Rect(0, 0, buffer.width, buffer.height)
            self._mapped = True
            self._started = True
        except BaseException:
            self._screen.stop()
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

        The terminal is restored on the way out however the loop ends,
        including an exception escaping a callback that
        :meth:`report_callback_exception` chose to re-raise.
        """
        self._running = True
        self.tk.quit_requested = False
        passes = 0
        try:
            while self._running and not self.tk.quit_requested:
                if not self.winfo_exists():
                    break
                self._loop_once()
                passes += 1
                if n and passes >= n:
                    break
        finally:
            self._running = False

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

    def _read_input(self) -> None:
        """Wait for input up to the next timer's deadline, then route it."""
        if self._input is None:
            return
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
            target = self._mouse_target(event)
        else:
            target = self.tk.focus or self
        target = self._through_grab(target)
        target._handle(event)

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
        if event.state in ("pressed", "clicked"):
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
        self._rect = Rect(0, 0, size.width, size.height)
        # The root's rect is set directly rather than through _allocate, which
        # would give the root a panel it does not want - so its layout has to
        # be told separately. Without this, everything sized against the
        # terminal keeps the size the terminal used to be.
        self.tk.layout.invalidate(self)
        self.event_generate("<Configure>", width=size.width, height=size.height)

    def _update_display(self) -> None:
        """Push what changed to the terminal.

        The screen goes first and the panels over it, which is the order they
        are stacked in. Widgets do not draw anything yet; when they do, their
        rendering happens before this.
        """
        if not self._started:
            return
        self._screen.refresh()
        if self.tk.panels is not None:
            self.tk.panels.update()

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
        self._input = None
        with contextlib.suppress(Exception):
            self._screen.stop()
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

        Writes to stderr, which in a curses program is usually a redirect or
        the scrollback after exit rather than the screen. Override it to put
        the report somewhere the application can show.

        Line endings are rewritten while the screen is up. curses clears
        ONLCR, so the terminal stops turning a newline into a carriage return
        and line feed: a traceback written with bare newlines comes out as a
        staircase, each line starting where the last one ended. Nothing else
        in the library writes to the terminal directly, so the translation
        belongs here rather than in a wrapper around stderr.
        """
        text = "".join(traceback.format_exception(exc, val, tb))
        screen = self.tk.screen
        if screen is not None and screen.started:
            text = text.replace("\n", "\r\n")
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
        super().__init__(master, cnf, name=name, **kw)
        self._setup_wm()
        self._allocate(self._default_rect())
        self._map()

    def winfo_class(self) -> str:
        """The class this window binds and reads options under."""
        return self._class_name or type(self).__name__

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
        given = {**(cnf or {}), **kw}
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
        with contextlib.suppress(curses.error):
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
        with contextlib.suppress(curses.error):
            dispatcher.call(window.addstr, 0, column, text)

    def _redraw_decoration(self) -> None:
        """Repaint the border and title after the window manager changed them."""
        self._draw()


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


class _Drawable(Widget):
    """Painting shared by the widgets that draw a background and a border."""

    def _background_attribute(self) -> int:
        """The curses attribute this frame's colours resolve to.

        Falls back to plain when no colour manager is running, which is what a
        terminal without colour gives anyway.
        """
        colors = self.tk.colors
        if colors is None:
            return curses.A_NORMAL
        return colors.attribute_for(
            str(self._options["foreground"] or "white"),
            str(self._options["background"] or "black"),
        )

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
        style = style_for_relief(str(self._options["relief"]) or FLAT)
        attribute |= style.attr
        with contextlib.suppress(curses.error):
            dispatcher.call(window.addstr, 0, 0, style.top(width), attribute)
            for row in range(1, height - 1):
                dispatcher.call(window.addstr, row, 0, style.vertical, attribute)
                dispatcher.call(
                    window.addstr, row, width - 1, style.vertical, attribute
                )
            # The last cell of the bottom row is inserted rather than added:
            # writing it with addstr would scroll a window whose cursor has
            # nowhere left to go, which curses refuses. insstr rather than
            # insch because a box-drawing character is multibyte and does not
            # fit in the single chtype insch takes.
            dispatcher.call(
                window.addstr, height - 1, 0, style.bottom(width)[:-1], attribute
            )
            dispatcher.call(
                window.insstr, height - 1, width - 1, style.bottom_right, attribute
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
        given = {**(cnf or {}), **kw}
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
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._bordered and width >= 2 and height >= 2:
                self._draw_border(dispatcher, window, width, height, attribute)


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
        "font": "",
        "height": 0,
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
        super().__init__(master, cnf, name=name, **kw)
        self._follow_variable()
        self._apply_requested_size()

    # -------------------------------------------------------------- content

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = {**(cnf or {}), **kw}
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if "textvariable" in given:
            self._follow_variable()
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()
        return result

    config = configure

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
        """Re-measure and repaint after the variable behind the text moved."""
        self._apply_requested_size()
        self._invalidate_layout()
        self._redraw()

    @property
    def _disabled(self) -> bool:
        """True while the widget refuses to be invoked.

        Here rather than on Button because ``state`` is declared here, and
        every widget that answers a click has the same question to ask.
        """
        return str(self._options["state"]) == "disabled"

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

    def _apply_requested_size(self) -> None:
        """Ask for room for the text, or for the size the options name.

        Padding and any border are included: a label asks for what it needs to
        draw, not for what is left after the frame around it.
        """
        text_width, text_height = measure(self._lines())
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
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._bordered and self._rect.width >= 2 and self._rect.height >= 2:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            self._draw_text(dispatcher, window, attribute)

    def _draw_text(
        self, dispatcher: CursesDispatcher, window: Any, attribute: int
    ) -> None:
        """Write the lines into the area left after border and padding."""
        area = self._text_area()
        if area.is_empty:
            return
        lines = self._lines()
        attribute |= self._text_attribute()
        across, down = parse_anchor(str(self._options["anchor"]))
        block_width, block_height = measure(lines)
        top = area.y + int((area.height - block_height) * down)
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
            column = area.x + int((area.width - block_width) * across)
            column += align_offset(len(line), block_width, justify)
            column = max(column, area.x)
            text = clip_text(line, area.x + area.width - column)
            with contextlib.suppress(curses.error):
                dispatcher.call(window.addstr, row, column, text, attribute)
        self._draw_underline(dispatcher, window, area, lines, attribute)

    def _text_area(self) -> Rect:
        """Where the text may go, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._bordered else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _text_attribute(self) -> int:
        """Attributes the font and state put on the text."""
        font = str(self._options["font"]).lower()
        attribute = from_font(
            bold="bold" in font,
            italic="italic" in font,
            underline="underline" in font,
        )
        with contextlib.suppress(ValueError):
            attribute = for_state(str(self._options["state"]), attribute)
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
        row = area.y + int((area.height - block_height) * down) + line_number
        column = area.x + int((area.width - block_width) * across)
        column += align_offset(
            len(lines[line_number]), block_width, str(self._options["justify"])
        )
        with contextlib.suppress(curses.error):
            dispatcher.call(
                window.addstr,
                row,
                column + remaining,
                lines[line_number][remaining],
                attribute | curses.A_UNDERLINE,
            )


class Label(_TextWidget):
    """A run of text.

    Its size comes from the text unless ``width`` or ``height`` says
    otherwise, so a label is as wide as its longest line and as tall as it has
    lines. ``wraplength`` breaks the text at that many cells, at word
    boundaries where it can.
    """


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
        "command": None,
        "default": "disabled",
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
            **kw: ``command``, ``state``, plus everything a Label takes.
        """
        self._pressed = False
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
        if "Button" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("Button")
        self.bind_class("Button", "<Button-1>", _button_press)
        self.bind_class("Button", "<ButtonRelease-1>", _button_release)
        self.bind_class("Button", "<Key-Return>", _button_key)
        self.bind_class("Button", "<Key-space>", _button_key)
        self.bind_class("Button", "<FocusIn>", _button_refresh)
        self.bind_class("Button", "<FocusOut>", _button_refresh)

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
        with contextlib.suppress(curses.error):
            dispatcher.call(window.addstr, row, area.x, left, attribute)
            dispatcher.call(
                window.addstr, row, area.x + area.width - 1, right, attribute
            )


def _button_press(event: Event) -> None:
    """Take the focus and show the button held down.

    Shared with Checkbutton, which presses and releases the same way and
    differs only in what invoking it does.
    """
    button = event.widget
    if button._disabled:
        return
    button.focus_set()
    button._pressed = True
    button._redraw()


def _button_release(event: Event) -> None:
    """Invoke the button, unless the pointer left it first.

    Tk invokes on release rather than press so that pressing and moving away
    is a way to change your mind, which is what every other toolkit does too.
    The release reaches this widget wherever the pointer ended up, because of
    the implicit grab, so whether it counts has to be decided here.
    """
    button = event.widget
    if not button._pressed:
        return
    button._pressed = False
    button._redraw()
    if not button._disabled and _within(button, event):
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


class Checkbutton(_TextWidget):
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

    #: The box in each state, unfocused and focused. Focus changes the
    #: brackets rather than the colour: it is the same width, so nothing
    #: moves when the focus arrives, and it survives a terminal with no
    #: colour - which is the same reason Button draws markers.
    _INDICATORS: ClassVar[dict[str, tuple[str, str]]] = {
        "on": ("[x]", "<x>"),
        "off": ("[ ]", "< >"),
        "tristate": ("[-]", "<->"),
    }

    #: Cells the box and the space after it take from the text.
    _INDICATOR_WIDTH = 4

    _widget_options: ClassVar[dict[str, Any]] = {
        "command": None,
        "indicatoron": True,
        "offvalue": 0,
        "onvalue": 1,
        "takefocus": True,
        "tristatevalue": "",
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
            **kw: ``variable``, ``onvalue``, ``offvalue``, ``tristatevalue``,
                ``command``, ``indicatoron``, plus everything a Label takes.
        """
        self._pressed = False
        self._value_trace: tuple[Variable, str] | None = None
        super().__init__(master, cnf, name=name, **kw)
        if self._options["variable"] is None:
            # A variable of its own, so that a checkbutton created with no
            # arguments still ticks. Plain Variable rather than IntVar: the
            # values it has to hold are whatever onvalue and offvalue are,
            # and those are only integers by default.
            self._options["variable"] = Variable(
                master=self, value=self._options["offvalue"]
            )
        self._follow_value()
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the default behaviour for every Checkbutton here.

        The same handlers Button uses, less Return: Tk's checkbutton answers
        the space bar and not Return, so that Return still reaches a dialog's
        default button from wherever the focus happens to be.
        """
        if "Checkbutton" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("Checkbutton")
        bind = self.bind_class
        bind("Checkbutton", "<Button-1>", _button_press)
        bind("Checkbutton", "<ButtonRelease-1>", _button_release)
        bind("Checkbutton", "<Key-space>", _button_key)
        bind("Checkbutton", "<FocusIn>", _button_refresh)
        bind("Checkbutton", "<FocusOut>", _button_refresh)

    # --------------------------------------------------------------- options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, following a new variable if one was named."""
        given = {**(cnf or {}), **kw}
        result = super().configure(cnf, **kw)
        if "variable" in given:
            self._follow_value()
            self._redraw()
        return result

    config = configure

    def _follow_value(self) -> None:
        """Track the ``variable``, dropping any previous one.

        The old trace has to go for the same reason a Label's does: a widget
        still answering to the variable it used to show would repaint itself
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
        """True while the box is drawn, false while the widget is a toggle."""
        try:
            return self.getboolean(self._options["indicatoron"])
        except TclError:
            return True

    # ----------------------------------------------------------------- value

    @property
    def _indicator_state(self) -> str:
        """Which of the three states the variable puts this button in.

        Tk's order, which matters: on, then the third state, then off as the
        fallback. So an empty variable with the default ``tristatevalue`` of
        ``""`` shows ``[-]`` rather than ``[ ]``, exactly as Tk's does - a
        surprise worth keeping, because code that means "off" should say so.
        """
        variable = self._options["variable"]
        value = None if variable is None else variable.get()
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

    def _write(self, value: Any) -> None:
        """Put a value in the variable, if there still is one."""
        variable = self._options["variable"]
        if variable is not None:
            variable.set(value)

    # ------------------------------------------------------------ behaviour

    def invoke(self) -> Any:
        """Toggle the button and run its command, as a click does.

        Returns whatever the command returns. Does nothing while disabled -
        the guard belongs here rather than in every caller, and ``invoke`` is
        how a key binding, a test and a click all reach one path.
        """
        if self._disabled:
            return None
        self.toggle()
        command = self._options["command"]
        return None if command is None else command()

    def flash(self) -> None:
        """Blink the box, as tkinter's does.

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
        """Put the box back the way it was after a flash."""
        self._pressed = False
        self._redraw()

    # ------------------------------------------------------------- painting

    def _apply_requested_size(self) -> None:
        """Ask for the text's room plus the box to the left of it."""
        super()._apply_requested_size()
        if self._indicator_on:
            self._request_size(
                self._requested.width + self._INDICATOR_WIDTH,
                self._requested.height,
            )

    def _text_area(self) -> Rect:
        """Where the text goes: what is left once the box has its cells."""
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
        """Attributes on the text, including a boxless button's own state.

        Without a box there is nothing else to show it with, so the text
        itself carries both: reversed while the button is on, underlined
        while it has the focus.
        """
        attribute = super()._text_attribute()
        if self._indicator_on:
            return attribute
        if self._indicator_state == "on":
            attribute |= curses.A_REVERSE
        if self.focus_get() is self:
            attribute |= curses.A_UNDERLINE
        return attribute

    def _redraw(self) -> None:
        """Paint the widget, then the box to the left of the text."""
        super()._redraw()
        self._draw_indicator()

    def _draw_indicator(self) -> None:
        """Draw the box, on the row the text's first line sits on."""
        window = self._window
        if window is None or self.tk.screen is None or not self._indicator_on:
            return
        # The whole area, not the text's - _text_area() has already handed
        # the box's cells away and would put it on top of the text.
        area = super()._text_area()
        if area.is_empty or area.width < self._INDICATOR_WIDTH:
            return
        focused = self.focus_get() is self
        box = self._INDICATORS[self._indicator_state][1 if focused else 0]
        attribute = self._background_attribute() | self._text_attribute()
        if self._pressed:
            attribute |= curses.A_REVERSE
        _, block_height = measure(self._lines())
        _, down = parse_anchor(str(self._options["anchor"]))
        row = area.y + int((area.height - block_height) * down)
        with contextlib.suppress(curses.error):
            CursesDispatcher.get().call(window.addstr, row, area.x, box, attribute)


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


class Entry(_Drawable):
    """A one-line text field.

    The editing itself is :class:`~tkcurses._core.editing.TextField`; what is
    here is the widget around it - options, key bindings, the cursor and
    selection on screen, and keeping a ``textvariable`` in step both ways.

    ``state`` has three values rather than two. ``readonly`` shows the text
    and lets it be selected and copied but refuses every edit, which is what
    a field displaying a computed value wants; ``disabled`` refuses the focus
    as well.
    """

    _widget_options: ClassVar[dict[str, Any]] = {
        "justify": "left",
        "relief": "sunken",
        "show": "",
        "state": "normal",
        "takefocus": True,
        "textvariable": None,
        "validate": "none",
        "validatecommand": None,
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
        super().__init__(master, cnf, name=name, **kw)
        self._follow_variable()
        self._apply_requested_size()
        self._install_class_bindings()

    # ------------------------------------------------------------- bindings

    def _install_class_bindings(self) -> None:
        """Register the editing keys for every Entry in this application."""
        if "Entry" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("Entry")
        bind = self.bind_class
        bind("Entry", "<Any-Key>", _entry_key)
        bind("Entry", "<Button-1>", _entry_click)
        bind("Entry", "<FocusIn>", _entry_refresh)
        bind("Entry", "<FocusOut>", _entry_refresh)

    # ---------------------------------------------------------------- state

    @property
    def _editable(self) -> bool:
        """True while the field accepts changes from the keyboard."""
        return str(self._options["state"]) == "normal"

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, following a new variable and repainting as needed."""
        given = {**(cnf or {}), **kw}
        result = super().configure(cnf, **kw)
        if not given:
            return result
        if "textvariable" in given:
            self._follow_variable()
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
        self._refresh_view()
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
        """Insert ``string`` at ``index``."""
        self._field.insert(self.index(index), string)
        self._changed()

    def delete(self, first: Any, last: Any = None) -> None:
        """Delete from ``first`` up to but not including ``last``."""
        self._field.delete(
            self.index(first), None if last is None else self.index(last)
        )
        self._changed()

    def icursor(self, index: Any) -> None:
        """Put the insertion cursor at ``index``."""
        self._field.move_to(self.index(index))
        self._refresh_view()
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

    def selection_range(self, start: Any, end: Any) -> None:
        """Select from ``start`` to ``end``."""
        self._field.select_range(self.index(start), self.index(end))
        self._redraw()

    select_range = selection_range

    def selection_clear(self, **kw: Any) -> None:  # noqa: ARG002 - Misc signature
        """Drop the selection."""
        self._field.select_clear()
        self._redraw()

    select_clear = selection_clear

    def selection_present(self) -> bool:
        """True if anything is selected."""
        return self._field.selection is not None

    select_present = selection_present

    def selection_from(self, index: Any) -> None:
        """Start a selection at ``index``."""
        self._field.select_range(self.index(index), self.index(index))
        self._field.move_to(self.index(index))
        self._redraw()

    select_from = selection_from

    def selection_to(self, index: Any) -> None:
        """Extend the selection to ``index``."""
        self._field.move_to(self.index(index), extend=True)
        self._refresh_view()
        self._redraw()

    select_to = selection_to
    selection_adjust = selection_to
    select_adjust = selection_to

    def xview(self, index: Any = None) -> int:
        """Get or set the first character shown."""
        if index is not None:
            self._field.move_to(self.index(index))
            self._refresh_view()
            self._redraw()
        return self._field.view

    # -------------------------------------------------------------- editing

    def _validated(self, proposed: str) -> bool:
        """Ask the ``validatecommand`` whether an edit may go ahead.

        tkinter passes Tcl substitution codes to a registered command; without
        Tcl there is nothing to register against, so the callable is handed
        the proposed contents directly. Anything it raises counts as a
        refusal - a validator that fails should not take the application with
        it.
        """
        if str(self._options["validate"]) in ("none", ""):
            return True
        command = self._options["validatecommand"]
        if command is None:
            return True
        try:
            return bool(command(proposed))
        except Exception:
            return False

    def _edit(self, change: Callable[[], None], proposed: str) -> None:
        """Apply an edit if the state and the validator both allow it."""
        if not self._editable or not self._validated(proposed):
            return
        change()
        self._changed()

    def _changed(self) -> None:
        """Publish, rescroll and repaint after the contents changed."""
        self._publish()
        self._refresh_view()
        self._redraw()

    def _refresh_view(self) -> None:
        """Scroll so the cursor is on screen."""
        self._field.scroll_into_view(self._text_area().width)

    # ------------------------------------------------------------- painting

    def _text_area(self) -> Rect:
        """Where the text goes, in cells relative to this widget's window."""
        edge = BORDER_WIDTH if self._bordered else 0
        padx, pady = int(self._options["padx"]), int(self._options["pady"])
        return Rect(
            edge + padx,
            edge + pady,
            max(0, self._rect.width - 2 * (edge + padx)),
            max(0, self._rect.height - 2 * (edge + pady)),
        )

    def _displayed(self) -> str:
        """What is on screen, masked if ``show`` says so."""
        mask = str(self._options["show"])
        text = self._field.text
        return mask[0] * len(text) if mask else text

    def _redraw(self) -> None:
        """Paint the field, its selection, and the cursor."""
        window = self._window
        if window is None or self.tk.screen is None:
            return
        area = self._text_area()
        # The window is a function of the cursor and the current width, and
        # the width is not known until the widget has been laid out - text
        # inserted before then scrolled against a field of no width at all.
        self._field.scroll_into_view(area.width)
        dispatcher = CursesDispatcher.get()
        attribute = self._background_attribute()
        with contextlib.suppress(ValueError):
            attribute = for_state(str(self._options["state"]), attribute)
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._bordered and self._rect.width >= 2 and self._rect.height >= 2:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if area.is_empty:
                return
            view = self._field.view
            text = self._displayed()[view : view + area.width]
            dispatcher.call(window.addstr, area.y, area.x, text, attribute)
            self._draw_selection(dispatcher, window, area, attribute)
            self._draw_cursor(dispatcher, window, area, attribute)

    def _draw_selection(
        self, dispatcher: CursesDispatcher, window: Any, area: Rect, attribute: int
    ) -> None:
        """Show the selected range in reverse video."""
        selection = self._field.selection
        if selection is None:
            return
        first, last = selection
        start = max(0, self._field.column_of(first))
        stop = min(area.width, self._field.column_of(last))
        if stop <= start:
            return
        text = self._displayed()[self._field.view + start : self._field.view + stop]
        with contextlib.suppress(curses.error):
            dispatcher.call(
                window.addstr,
                area.y,
                area.x + start,
                text,
                attribute | curses.A_REVERSE,
            )

    def _draw_cursor(
        self, dispatcher: CursesDispatcher, window: Any, area: Rect, attribute: int
    ) -> None:
        """Show where typing will go, but only while the field has the focus.

        A cursor drawn in an unfocused field claims the keyboard is there when
        it is not, which in a form of several fields is actively misleading.
        """
        if self.focus_get() is not self or not self._editable:
            return
        column = self._field.column_of(self._field.cursor)
        if not (0 <= column < area.width):
            return
        under = self._displayed()[self._field.cursor : self._field.cursor + 1] or " "
        with contextlib.suppress(curses.error):
            dispatcher.call(
                window.addstr,
                area.y,
                area.x + column,
                under,
                attribute | curses.A_REVERSE,
            )


#: Keys that move the cursor, as offsets or as absolute positions.
_ENTRY_MOTION: dict[str, Any] = {
    "Left": -1,
    "Right": 1,
    "Home": "start",
    "End": "end",
}


def _entry_key(event: Event) -> str | None:
    """Handle one key in an Entry.

    Returns ``"break"`` for keys the field consumed, so a Left arrow moving
    the cursor does not also reach whatever else is bound to it.
    """
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
        entry._refresh_view()
        entry._redraw()
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

    if keysym == "Delete":
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
    entry._field.move_to(entry._field.index_at(event.x - entry._text_area().x))
    entry._refresh_view()
    entry._redraw()


def _entry_refresh(event: Event) -> None:
    """Repaint after the focus moved, so the cursor appears or goes."""
    event.widget._redraw()


class Listbox(_Drawable):
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

    _widget_options: ClassVar[dict[str, Any]] = {
        "activestyle": "underline",
        "height": 10,
        "relief": "sunken",
        "selectmode": "browse",
        "state": "normal",
        "takefocus": True,
        "width": 20,
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
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the list keys for every Listbox in this application."""
        if "Listbox" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("Listbox")
        bind = self.bind_class
        bind("Listbox", "<Any-Key>", _listbox_key)
        bind("Listbox", "<Button-1>", _listbox_click)
        # A separate binding, because modifiers match exactly: <Button-1>
        # does not fire for a shifted click, in Tk or here. Binding the plain
        # one and expecting both is a mistake this rule makes easy.
        bind("Listbox", "<Shift-Button-1>", _listbox_click)
        bind("Listbox", "<Button-4>", _listbox_wheel)
        bind("Listbox", "<Button-5>", _listbox_wheel)
        bind("Listbox", "<FocusIn>", _listbox_refresh)
        bind("Listbox", "<FocusOut>", _listbox_refresh)

    def _apply_requested_size(self) -> None:
        """Ask for the configured rows and columns, plus border and padding."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        self._request_size(
            int(self._options["width"]) + 2 * int(self._options["padx"]) + edge,
            int(self._options["height"]) + 2 * int(self._options["pady"]) + edge,
        )

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Set options, re-measuring and repainting as the change requires."""
        given = {**(cnf or {}), **kw}
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
        """The item nearest a screen row."""
        row = y - self.winfo_rooty() - self._text_area().y
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
            self._top = int(float(args[1]) * len(self._items))
        elif args[0] == "scroll":
            count = int(args[1])
            step = max(1, self._text_area().height) if args[2] == "pages" else 1
            self._top += count * step
        self._clamp_view()
        self._redraw()
        return None

    def _view_fractions(self) -> tuple[float, float]:
        """Where the window is, as two fractions of the whole list."""
        total = len(self._items)
        if total <= 0:
            return (0.0, 1.0)
        height = max(1, self._text_area().height)
        return (self._top / total, min(1.0, (self._top + height) / total))

    def _publish_view(self) -> None:
        """Tell the scrollbar where the view is, if one is listening."""
        command = self._options["yscrollcommand"]
        if command is not None:
            first, last = self._view_fractions()
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
        edge = BORDER_WIDTH if self._bordered else 0
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
        attribute = self._background_attribute()
        with contextlib.suppress(ValueError):
            attribute = for_state(str(self._options["state"]), attribute)
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._bordered and self._rect.width >= 2 and self._rect.height >= 2:
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
        style = attribute | (curses.A_REVERSE if selected else 0)
        if position == self._active and self.focus_get() is self and not selected:
            style |= curses.A_UNDERLINE
        left, right = self._SELECTED_MARKERS if selected else (" ", " ")
        body = clip_text(self._items[position], max(0, area.width - 2))
        line = f"{left}{body}".ljust(area.width - 1)[: area.width - 1]
        with contextlib.suppress(curses.error):
            dispatcher.call(window.addstr, area.y + row, area.x, line, style)
            dispatcher.call(
                window.insstr, area.y + row, area.x + area.width - 1, right, style
            )


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
        "command": None,
        "orient": "vertical",
        "relief": "sunken",
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
        super().__init__(master, cnf, name=name, **kw)
        self._apply_requested_size()
        self._install_class_bindings()

    def _install_class_bindings(self) -> None:
        """Register the click behaviour for every Scrollbar in this application."""
        if "Scrollbar" in self.tk.bound_classes:
            return
        self.tk.bound_classes.add("Scrollbar")
        self.bind_class("Scrollbar", "<Button-1>", _scrollbar_click)

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
        given = {**(cnf or {}), **kw}
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

    def fraction(self, x: int, y: int) -> float:
        """The fraction of the way along a screen position lies."""
        area = self._trough_bounds()
        if area <= 0:
            return 0.0
        offset = y - self.winfo_rooty() if self._vertical else x - self.winfo_rootx()
        return min(max((offset - self._trough_start()) / area, 0.0), 1.0)

    def identify(self, x: int, y: int) -> str:
        """Which part of the scrollbar is at a screen position."""
        offset = y - self.winfo_rooty() if self._vertical else x - self.winfo_rootx()
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
        """Cells along the scrollbar's own direction."""
        edge = 2 * BORDER_WIDTH if self._bordered else 0
        span = self._rect.height if self._vertical else self._rect.width
        return max(0, span - edge)

    def _trough_start(self) -> int:
        """Where the trough begins, after the first arrow."""
        return (BORDER_WIDTH if self._bordered else 0) + 1

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
        cells = [first_arrow]
        for index in range(trough):
            cells.append(
                self._THUMB if thumb_start <= index < thumb_end else self._TROUGH
            )
        cells.append(last_arrow)

        edge = BORDER_WIDTH if self._bordered else 0
        with contextlib.suppress(curses.error):
            dispatcher.call(window.bkgd, " ", attribute)
            dispatcher.call(window.erase)
            if self._bordered and self._rect.width >= 2 and self._rect.height >= 2:
                self._draw_border(
                    dispatcher, window, self._rect.width, self._rect.height, attribute
                )
            if self._vertical:
                for offset, cell in enumerate(cells):
                    dispatcher.call(window.addstr, edge + offset, edge, cell, attribute)
            else:
                dispatcher.call(window.addstr, edge, edge, "".join(cells), attribute)


def _scrollbar_click(event: Event) -> None:
    """Scroll by whatever part of the scrollbar was clicked."""
    bar = event.widget
    command = bar._options["command"]
    if command is None:
        return
    part = bar.identify(event.x_root, event.y_root)
    if part == "arrow1":
        command("scroll", -1, "units")
    elif part == "arrow2":
        command("scroll", 1, "units")
    elif part == "trough1":
        command("scroll", -1, "pages")
    elif part == "trough2":
        command("scroll", 1, "pages")
    else:
        command("moveto", bar.fraction(event.x_root, event.y_root))
