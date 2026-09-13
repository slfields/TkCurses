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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tkcurses._core.bindings import BindingTable, VirtualEvents
from tkcurses._core.clipboard import Selections
from tkcurses._core.layout import LayoutEngine
from tkcurses._core.timers import AfterQueue

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tkcurses import Misc
    from tkcurses._core.colors import ColorManager
    from tkcurses._core.panels import PanelStack
    from tkcurses._core.screen import CursesScreen

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

    def get(self, path: str, class_name: str, name: str) -> Any:
        """Best value of option ``name`` for a widget, or None.

        The widget is identified by both its path (``.frame.ok``) and its
        class (``Button``), because a pattern may select either.
        """
        best: _Option | None = None
        for option in self._options:
            if not self._applies(option.pattern, path, class_name, name):
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
    def _applies(pattern: str, path: str, class_name: str, name: str) -> bool:
        """True if ``pattern`` selects option ``name`` on this widget.

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
        if option not in (name, "*"):
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


class Application:
    """One widget tree's shared state.

    Every widget holds a reference to the same instance; ``Tk()`` creates it
    and children inherit it from their master.
    """

    def __init__(self) -> None:
        self.bindings = BindingTable()
        self.virtual_events = VirtualEvents()
        self.timers = AfterQueue()
        self.selections = Selections()
        self.options = OptionDatabase()
        self.widgets = WidgetRegistry()
        self.layout = LayoutEngine()

        #: Values behind ``getvar``/``setvar`` and the Variable classes.
        self.variables: dict[str, Any] = {}

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
        self.focus: Misc | None = None
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

        #: Widget holding the input grab, and whether it is global. A grab
        #: diverts events away from the rest of the application, which is how
        #: a modal dialog stays modal.
        self.grab: Misc | None = None
        self.grab_global = False

        #: Widget classes whose default bindings have been installed. Class
        #: bindings are per application, and a widget registering its own on
        #: every instance would stack up one copy per widget.
        self.bound_classes: set[str] = set()

        #: Counters behind automatic widget names (!button, !button2).
        self.name_counts: dict[str, int] = {}

        #: Set by quit(); the main loop checks it. It lives here rather than
        #: on the root widget so that quit() works from any widget, as it
        #: does in tkinter.
        self.quit_requested = False

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
