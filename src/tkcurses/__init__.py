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
import os
import sys
import time
from typing import TYPE_CHECKING, Any, ClassVar

from tkcurses._core.application import Application
from tkcurses._core.bindings import (
    EventPattern,
    parse_sequence,
    pattern_for_event,
)
from tkcurses._core.clipboard import CLIPBOARD, PRIMARY
from tkcurses._core.colors import palette_rgb, parse_color, rgb_for
from tkcurses._core.errors import TclError, TkCursesError
from tkcurses._core.events import Event as CoreEvent
from tkcurses._core.events import KeyEvent, MouseEvent, ResizeEvent
from tkcurses._core.geometry import Rect, Size
from tkcurses.constants import FLAT

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from tkcurses._core.panels import Panel

__version__ = "0.1.0"

__all__ = [
    "BaseWidget",
    "Event",
    "Misc",
    "NoDefaultRoot",
    "TclError",
    "TkCursesError",
    "Widget",
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
        return sum(widget._rect.x for widget in self._ancestry())

    def winfo_rooty(self) -> int:
        """Row on the screen, in cells."""
        return sum(widget._rect.y for widget in self._ancestry())

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
        self._takefocus = bool(self._options.get("takefocus", True))
        self._panel: Panel | None = None

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
        if (rect.width, rect.height) != (previous.width, previous.height):
            # Curses cannot resize a window in place, and replacing it is also
            # what keeps a shrink from leaving the vacated cells behind.
            stack.replace_window(self._panel, rect)
        elif (rect.x, rect.y) != (previous.x, previous.y):
            stack.move(self._panel, rect.x, rect.y)

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
        if self._panel is None:
            self._panel = stack.new_panel(self._rect, userptr=self)
        else:
            stack.show(self._panel)

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


class Widget(BaseWidget):
    """The base class for every ordinary widget.

    In tkinter this is where the three geometry managers are mixed in
    (``Widget(BaseWidget, Pack, Place, Grid)``); those arrive with the
    geometry manager epic, and this class is where they will attach. Until
    then it is what separates a widget that a manager can place from a
    toplevel that manages itself.
    """
