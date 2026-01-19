"""TkCurses - A tkinter-compatible API for curses-based terminal applications.

TkCurses provides a familiar tkinter-like interface for building terminal user
interfaces using the curses library. It allows developers to create TUI applications
using the same patterns and concepts they know from tkinter GUI development.

Key Features:
    - tkinter-compatible widget API
    - Familiar geometry managers (pack, grid, place)
    - Event binding system similar to tkinter
    - Standard dialog boxes (messagebox, filedialog, etc.)
    - TTK-style themed widgets for terminals

Example:
    >>> import tkcurses as tk
    >>> root = tk.Tk()
    >>> label = tk.Label(root, text="Hello, Terminal!")
    >>> label.pack()
    >>> root.mainloop()
"""

from __future__ import annotations

import curses
import signal
import time
from typing import Any, Callable, Optional, TYPE_CHECKING

from ._core.colors import ColorManager
from ._core.config import TkCursesConfig
from ._core.dispatcher import CursesDispatcher
from ._core.events import Event, KeyEvent, MouseEvent, ResizeEvent
from ._core.geometry import Rect, Size
from ._core.input import InputHandler
from ._core.layout import GridLayoutCache, LayoutManager
from ._core.panels import PanelStack
from ._core.screen import CursesScreen

if TYPE_CHECKING:
    import curses
    from curses import _CursesWindow
    from ._core.panels import Panel

__version__ = "0.1.0"

__all__: list[str] = [
    "Misc",
    "Wm",
    "BaseWidget",
    "Pack",
    "Place",
    "Grid",
    "Widget",
    "Tk",
    "Toplevel",
    "Variable",
    "StringVar",
    "IntVar",
    "DoubleVar",
    "BooleanVar",
]


class Misc:
    """Base class for event handling, focus management, and clipboard support.

    This class provides the foundational functionality that all TkCurses widgets
    inherit. It mirrors the functionality of tkinter.Misc and provides:

    - Event binding system (bind, unbind, bind_all, etc.)
    - Focus management (focus_set, focus_get, focus traversal)
    - Clipboard operations (clipboard_clear, clipboard_append, clipboard_get)
    - Timing callbacks (after, after_idle, after_cancel)
    - Widget information queries (winfo_* methods)
    - Configuration management (cget, configure)

    This class is not typically instantiated directly but is used as a base
    class for Tk, Toplevel, and all widgets.

    Example:
        >>> # Widgets inherit from Misc, so all widgets have these methods
        >>> button = Button(root, text="Click me")
        >>> button.bind("<Button-1>", lambda e: print("Clicked!"))
        >>> button.focus_set()
        >>> button.after(1000, lambda: print("1 second later"))

    Attributes:
        _widget_name: Unique name for this widget (for nametowidget lookups).
        _bindings: Dictionary mapping event sequences to callback lists.
        _has_focus: Whether this widget currently has focus.
        _after_callbacks: Dictionary of scheduled after() callbacks.
        _after_id_counter: Counter for generating unique after IDs.
    """

    # Class-level storage for global bindings and clipboard
    _global_bindings: dict[str, list[tuple[Optional[str], Callable[[Event], Any]]]] = {}
    _class_bindings: dict[str, dict[str, list[tuple[Optional[str], Callable[[Event], Any]]]]] = {}
    _clipboard: str = ""
    _selection: str = ""
    _focused_widget: Optional[Misc] = None
    _widget_registry: dict[str, Misc] = {}
    _after_queue: list[tuple[float, str, Callable[[], Any]]] = []
    _after_id_counter: int = 0

    def __init__(self) -> None:
        """Initialize the Misc base class.

        Sets up event binding storage, focus tracking, and callback scheduling
        infrastructure for the widget.
        """
        self._widget_name: str = f"w{id(self)}"
        self._bindings: dict[str, list[tuple[Optional[str], Callable[[Event], Any]]]] = {}
        self._has_focus: bool = False
        self._config: dict[str, Any] = {}

        # Register this widget
        Misc._widget_registry[self._widget_name] = self

    # =========================================================================
    # Event Binding Methods
    # =========================================================================

    def bind(
        self,
        sequence: str,
        func: Optional[Callable[[Event], Any]] = None,
        add: Optional[str] = None,
    ) -> str:
        """Bind an event sequence to a callback function.

        Registers a callback to be invoked when the specified event occurs on
        this widget. Event sequences follow tkinter conventions like:

        - Keyboard: "<Key-a>", "<Return>", "<Control-c>", "<Shift-Up>"
        - Mouse: "<Button-1>", "<Double-Button-1>", "<B1-Motion>"
        - Other: "<FocusIn>", "<FocusOut>", "<Configure>"

        Args:
            sequence: Event sequence string (e.g., "<Button-1>", "<Key-a>").
            func: Callback function taking an Event parameter. If None, returns
                the current binding for this sequence.
            add: If "+" or True, adds to existing bindings instead of replacing.
                Default is to replace.

        Returns:
            A string function identifier that can be used with unbind().
            If func is None, returns the current binding script.

        Example:
            >>> def on_click(event):
            ...     print(f"Clicked at {event.x}, {event.y}")
            >>> button.bind("<Button-1>", on_click)
            >>> # Add another binding without replacing
            >>> button.bind("<Button-1>", on_double_click, add="+")
        """
        if func is None:
            # Query mode: return current bindings
            bindings = self._bindings.get(sequence, [])
            return "\n".join(str(f) for _, f in bindings) if bindings else ""

        # Generate unique function ID
        func_id = f"func_{id(func)}"

        if add in ("+", True):
            # Add to existing bindings
            if sequence not in self._bindings:
                self._bindings[sequence] = []
            self._bindings[sequence].append((func_id, func))
        else:
            # Replace existing bindings
            self._bindings[sequence] = [(func_id, func)]

        return func_id

    def bind_all(
        self,
        sequence: str,
        func: Optional[Callable[[Event], Any]] = None,
        add: Optional[str] = None,
    ) -> str:
        """Bind an event sequence globally to all widgets.

        Registers a callback that will be invoked when the specified event occurs
        on any widget in the application. Global bindings are checked after
        widget-specific bindings.

        Args:
            sequence: Event sequence string (e.g., "<Control-q>", "<F1>").
            func: Callback function taking an Event parameter. If None, returns
                the current global binding.
            add: If "+" or True, adds to existing bindings instead of replacing.

        Returns:
            A string function identifier that can be used with unbind_all().

        Example:
            >>> # Global keyboard shortcut
            >>> root.bind_all("<Control-q>", lambda e: root.quit())
            >>> # Help key available everywhere
            >>> root.bind_all("<F1>", lambda e: show_help())
        """
        if func is None:
            # Query mode: return current global bindings
            bindings = Misc._global_bindings.get(sequence, [])
            return "\n".join(str(f) for _, f in bindings) if bindings else ""

        # Generate unique function ID
        func_id = f"func_{id(func)}"

        if add in ("+", True):
            # Add to existing bindings
            if sequence not in Misc._global_bindings:
                Misc._global_bindings[sequence] = []
            Misc._global_bindings[sequence].append((func_id, func))
        else:
            # Replace existing bindings
            Misc._global_bindings[sequence] = [(func_id, func)]

        return func_id

    def bind_class(
        self,
        className: str,
        sequence: str,
        func: Optional[Callable[[Event], Any]] = None,
        add: Optional[str] = None,
    ) -> str:
        """Bind an event sequence to all widgets of a specific class.

        Registers a callback that will be invoked when the specified event occurs
        on any widget of the given class. Class bindings are checked between
        widget bindings and global bindings.

        Args:
            className: Name of the widget class (e.g., "Button", "Entry").
            sequence: Event sequence string (e.g., "<Return>", "<Button-1>").
            func: Callback function taking an Event parameter. If None, returns
                the current class binding.
            add: If "+" or True, adds to existing bindings instead of replacing.

        Returns:
            A string function identifier that can be used with unbind_class().

        Example:
            >>> # All buttons respond to Enter key
            >>> root.bind_class("Button", "<Return>", lambda e: e.widget.invoke())
            >>> # All entries validate on focus out
            >>> root.bind_class("Entry", "<FocusOut>", validate_entry)
        """
        if func is None:
            # Query mode: return current class bindings
            if className in Misc._class_bindings:
                bindings = Misc._class_bindings[className].get(sequence, [])
                return "\n".join(str(f) for _, f in bindings) if bindings else ""
            return ""

        # Generate unique function ID
        func_id = f"func_{id(func)}"

        # Ensure class dict exists
        if className not in Misc._class_bindings:
            Misc._class_bindings[className] = {}

        if add in ("+", True):
            # Add to existing bindings
            if sequence not in Misc._class_bindings[className]:
                Misc._class_bindings[className][sequence] = []
            Misc._class_bindings[className][sequence].append((func_id, func))
        else:
            # Replace existing bindings
            Misc._class_bindings[className][sequence] = [(func_id, func)]

        return func_id

    def unbind(self, sequence: str, funcid: Optional[str] = None) -> None:
        """Remove an event binding from this widget.

        Removes the callback(s) associated with the given event sequence.
        If funcid is provided, only that specific callback is removed.
        Otherwise, all callbacks for the sequence are removed.

        Args:
            sequence: Event sequence string (e.g., "<Button-1>").
            funcid: Optional function identifier returned by bind(). If None,
                removes all bindings for this sequence.

        Example:
            >>> fid = button.bind("<Button-1>", on_click)
            >>> # Remove just this specific binding
            >>> button.unbind("<Button-1>", fid)
            >>> # Remove all Button-1 bindings
            >>> button.unbind("<Button-1>")
        """
        if sequence not in self._bindings:
            return

        if funcid is None:
            # Remove all bindings for this sequence
            del self._bindings[sequence]
        else:
            # Remove specific binding by funcid
            self._bindings[sequence] = [
                (fid, func) for fid, func in self._bindings[sequence]
                if fid != funcid
            ]
            # Clean up empty list
            if not self._bindings[sequence]:
                del self._bindings[sequence]

    def unbind_all(self, sequence: str) -> None:
        """Remove all global bindings for an event sequence.

        Removes all globally-bound callbacks for the specified event sequence.

        Args:
            sequence: Event sequence string (e.g., "<Control-q>").

        Example:
            >>> root.bind_all("<Control-q>", quit_app)
            >>> # Later, remove the global binding
            >>> root.unbind_all("<Control-q>")
        """
        if sequence in Misc._global_bindings:
            del Misc._global_bindings[sequence]

    def unbind_class(self, className: str, sequence: str) -> None:
        """Remove all class bindings for an event sequence.

        Removes all class-level callbacks for the specified event sequence
        on the given widget class.

        Args:
            className: Name of the widget class (e.g., "Button").
            sequence: Event sequence string (e.g., "<Return>").

        Example:
            >>> root.bind_class("Button", "<Return>", invoke_button)
            >>> # Later, remove the class binding
            >>> root.unbind_class("Button", "<Return>")
        """
        if className in Misc._class_bindings:
            if sequence in Misc._class_bindings[className]:
                del Misc._class_bindings[className][sequence]

    def _event_dispatch(self, event: Event) -> None:
        """Dispatch an event to registered callbacks.

        Internal method that handles event propagation through the binding
        hierarchy: widget bindings, then class bindings, then global bindings.

        Args:
            event: The event to dispatch.
        """
        # Convert event to sequence string
        sequence = self._event_to_sequence(event)

        # Check widget-specific bindings
        if sequence in self._bindings:
            for _, func in self._bindings[sequence]:
                try:
                    func(event)
                except Exception as e:
                    # In tkinter, binding errors are typically silently caught
                    # or sent to the error handler
                    print(f"Error in binding callback: {e}")

        # Check class bindings
        class_name = self.__class__.__name__
        if class_name in Misc._class_bindings:
            if sequence in Misc._class_bindings[class_name]:
                for _, func in Misc._class_bindings[class_name][sequence]:
                    try:
                        func(event)
                    except Exception as e:
                        print(f"Error in class binding callback: {e}")

        # Check global bindings
        if sequence in Misc._global_bindings:
            for _, func in Misc._global_bindings[sequence]:
                try:
                    func(event)
                except Exception as e:
                    print(f"Error in global binding callback: {e}")

    def _event_to_sequence(self, event: Event) -> str:
        """Convert an Event object to a tkinter-style event sequence string.

        Args:
            event: The event to convert.

        Returns:
            Event sequence string (e.g., "<Button-1>", "<Key-a>").
        """
        if isinstance(event, KeyEvent):
            # Build key sequence with modifiers
            parts = []
            if event.modifiers & 0x02:  # MOD_CTRL
                parts.append("Control")
            if event.modifiers & 0x04:  # MOD_ALT
                parts.append("Alt")
            if event.modifiers & 0x01:  # MOD_SHIFT
                parts.append("Shift")

            # Add key symbol
            parts.append(f"Key-{event.keysym}")

            return f"<{'-'.join(parts)}>"

        elif isinstance(event, MouseEvent):
            # Build mouse sequence with modifiers
            parts = []
            if event.modifiers & 0x01:  # MOD_SHIFT
                parts.append("Shift")
            if event.modifiers & 0x02:  # MOD_CTRL
                parts.append("Control")
            if event.modifiers & 0x04:  # MOD_ALT
                parts.append("Alt")

            # Map mouse state to event type
            if event.state == "pressed":
                parts.append(f"Button-{event.button}")
            elif event.state == "released":
                parts.append(f"ButtonRelease-{event.button}")
            elif event.state == "double":
                parts.append(f"Double-Button-{event.button}")
            elif event.state == "triple":
                parts.append(f"Triple-Button-{event.button}")
            elif event.state == "drag":
                parts.append(f"B{event.button}-Motion")
            elif event.state == "motion":
                parts.append("Motion")

            return f"<{'-'.join(parts)}>"

        return f"<{event.type}>"

    # =========================================================================
    # Focus Management Methods
    # =========================================================================

    def focus_set(self) -> None:
        """Set keyboard focus to this widget.

        Makes this widget the active widget for keyboard input. Only one
        widget can have focus at a time.

        Example:
            >>> entry = Entry(root)
            >>> entry.pack()
            >>> entry.focus_set()  # User can now type in the entry
        """
        # Remove focus from previous widget
        if Misc._focused_widget is not None:
            Misc._focused_widget._has_focus = False

        # Set focus to this widget
        self._has_focus = True
        Misc._focused_widget = self

    def focus_get(self) -> Optional[Misc]:
        """Get the widget that currently has focus.

        Returns:
            The widget with focus, or None if no widget has focus.

        Example:
            >>> focused = root.focus_get()
            >>> if focused:
            ...     print(f"Focus is on: {focused._widget_name}")
        """
        return Misc._focused_widget

    def focus_force(self) -> None:
        """Force keyboard focus to this widget.

        Similar to focus_set() but more aggressive. In tkinter, this also
        raises the window. In TkCurses, it's equivalent to focus_set().

        Example:
            >>> button.focus_force()
        """
        self.focus_set()

    def focus_displayof(self) -> Optional[Misc]:
        """Get the widget with focus on the same display.

        In tkinter, this considers X11 display. In TkCurses, this is
        equivalent to focus_get() since there's only one terminal display.

        Returns:
            The widget with focus, or None.
        """
        return self.focus_get()

    def tk_focusNext(self) -> Optional[Misc]:
        """Get the next widget in focus traversal order.

        Returns the next widget that should receive focus when Tab is pressed.
        Focus order is typically determined by widget creation order.

        Returns:
            The next widget in focus order, or None if there is none.

        Example:
            >>> next_widget = entry.tk_focusNext()
            >>> if next_widget:
            ...     next_widget.focus_set()
        """
        # Get all registered widgets
        widgets = list(Misc._widget_registry.values())
        if not widgets:
            return None

        try:
            current_idx = widgets.index(self)
            next_idx = (current_idx + 1) % len(widgets)
            return widgets[next_idx]
        except ValueError:
            # Widget not in registry
            return None

    def tk_focusPrev(self) -> Optional[Misc]:
        """Get the previous widget in focus traversal order.

        Returns the previous widget that should receive focus when
        Shift+Tab is pressed.

        Returns:
            The previous widget in focus order, or None if there is none.

        Example:
            >>> prev_widget = entry.tk_focusPrev()
            >>> if prev_widget:
            ...     prev_widget.focus_set()
        """
        # Get all registered widgets
        widgets = list(Misc._widget_registry.values())
        if not widgets:
            return None

        try:
            current_idx = widgets.index(self)
            prev_idx = (current_idx - 1) % len(widgets)
            return widgets[prev_idx]
        except ValueError:
            # Widget not in registry
            return None

    def tk_focusFollowsMouse(self) -> None:
        """Enable focus-follows-mouse mode.

        In this mode, widgets automatically receive focus when the mouse
        cursor moves over them. This is a stub in TkCurses.

        Example:
            >>> root.tk_focusFollowsMouse()
        """
        # Stub: would require mouse motion tracking integration
        pass

    # =========================================================================
    # Clipboard Methods
    # =========================================================================

    def clipboard_clear(self) -> None:
        """Clear the clipboard.

        Removes all content from the TkCurses internal clipboard. Note that
        this is a terminal-local clipboard, not the system clipboard.

        Example:
            >>> root.clipboard_clear()
        """
        Misc._clipboard = ""

    def clipboard_append(self, string: str) -> None:
        """Append text to the clipboard.

        Adds the given string to the end of the current clipboard contents.

        Args:
            string: Text to append to clipboard.

        Example:
            >>> root.clipboard_clear()
            >>> root.clipboard_append("Hello ")
            >>> root.clipboard_append("World")
            >>> print(root.clipboard_get())  # "Hello World"
        """
        Misc._clipboard += string

    def clipboard_get(self) -> str:
        """Get the current clipboard contents.

        Returns:
            The current text content of the clipboard.

        Example:
            >>> text = root.clipboard_get()
            >>> entry.insert(0, text)
        """
        return Misc._clipboard

    def selection_clear(self) -> None:
        """Clear the current selection.

        Removes all content from the TkCurses internal selection buffer.

        Example:
            >>> root.selection_clear()
        """
        Misc._selection = ""

    def selection_get(self) -> str:
        """Get the current selection contents.

        Returns:
            The current text content of the selection.

        Example:
            >>> selected = root.selection_get()
            >>> print(f"Selected: {selected}")
        """
        return Misc._selection

    def selection_own(self) -> None:
        """Claim ownership of the selection.

        In tkinter, this involves X11 selection protocols. In TkCurses,
        this is a stub since we use internal selection storage.

        Example:
            >>> widget.selection_own()
        """
        # Stub: selection is always internal
        pass

    # =========================================================================
    # Timing Methods
    # =========================================================================

    def after(
        self,
        ms: int,
        func: Optional[Callable[..., Any]] = None,
        *args: Any,
    ) -> str:
        """Schedule a callback to be invoked after a delay.

        Registers a function to be called after the specified number of
        milliseconds. The callback will be invoked by the main event loop.

        Args:
            ms: Delay in milliseconds before invoking the callback.
            func: Callback function to invoke. If None, acts as a sleep.
            *args: Arguments to pass to the callback function.

        Returns:
            A unique identifier that can be used with after_cancel().

        Example:
            >>> def say_hello():
            ...     print("Hello after 1 second!")
            >>> callback_id = root.after(1000, say_hello)
            >>> # Cancel if needed
            >>> root.after_cancel(callback_id)
        """
        # Generate unique after ID
        Misc._after_id_counter += 1
        after_id = f"after#{Misc._after_id_counter}"

        # Calculate execution time
        execute_time = time.time() + (ms / 1000.0)

        # Create callback wrapper
        if func is None:
            # No-op for sleep-style calls
            callback = lambda: None
        else:
            callback = lambda: func(*args)

        # Add to after queue
        Misc._after_queue.append((execute_time, after_id, callback))
        Misc._after_queue.sort(key=lambda x: x[0])  # Sort by execution time

        return after_id

    def after_cancel(self, id: str) -> None:
        """Cancel a scheduled after() callback.

        Removes the callback with the given ID from the scheduling queue.
        If the callback has already executed or the ID is invalid, this
        method does nothing.

        Args:
            id: The identifier returned by after().

        Example:
            >>> callback_id = root.after(5000, long_operation)
            >>> # Changed our mind
            >>> root.after_cancel(callback_id)
        """
        Misc._after_queue = [
            (t, aid, cb) for t, aid, cb in Misc._after_queue
            if aid != id
        ]

    def after_idle(self, func: Callable[..., Any], *args: Any) -> str:
        """Schedule a callback to be invoked when the event loop is idle.

        Registers a function to be called when there are no pending events
        to process. This is useful for low-priority background tasks.

        Args:
            func: Callback function to invoke.
            *args: Arguments to pass to the callback function.

        Returns:
            A unique identifier that can be used with after_cancel().

        Example:
            >>> def update_status():
            ...     status_label.config(text="Ready")
            >>> root.after_idle(update_status)
        """
        # Schedule for immediate execution (time 0)
        Misc._after_id_counter += 1
        after_id = f"idle#{Misc._after_id_counter}"

        callback = lambda: func(*args)
        Misc._after_queue.append((time.time(), after_id, callback))
        Misc._after_queue.sort(key=lambda x: x[0])

        return after_id

    @classmethod
    def _process_after_queue(cls) -> None:
        """Process all due after() callbacks.

        Internal method called by the main event loop to execute scheduled
        callbacks whose time has come.
        """
        current_time = time.time()

        # Process all callbacks whose time has come
        while cls._after_queue and cls._after_queue[0][0] <= current_time:
            _, after_id, callback = cls._after_queue.pop(0)
            try:
                callback()
            except Exception as e:
                # In tkinter, callback errors are typically caught
                print(f"Error in after callback {after_id}: {e}")

    # =========================================================================
    # Widget Query Methods
    # =========================================================================

    def winfo_children(self) -> list[Misc]:
        """Get a list of all child widgets.

        Returns:
            List of child widgets. Override in container widgets.

        Example:
            >>> for child in frame.winfo_children():
            ...     print(child._widget_name)
        """
        return []

    def winfo_class(self) -> str:
        """Get the widget's class name.

        Returns:
            The class name of this widget (e.g., "Button", "Entry").

        Example:
            >>> print(button.winfo_class())  # "Button"
        """
        return self.__class__.__name__

    def winfo_containing(self, rootX: int, rootY: int) -> Optional[Misc]:
        """Get the widget at the specified screen coordinates.

        Args:
            rootX: X coordinate (column) in root window coordinates.
            rootY: Y coordinate (row) in root window coordinates.

        Returns:
            The widget at those coordinates, or None. Override in widgets
            with geometry information.

        Example:
            >>> widget = root.winfo_containing(10, 5)
            >>> if widget:
            ...     print(f"Widget at (10,5): {widget.winfo_class()}")
        """
        return None

    def winfo_exists(self) -> bool:
        """Check if the widget still exists.

        Returns:
            True if the widget exists, False if it has been destroyed.

        Example:
            >>> if widget.winfo_exists():
            ...     widget.config(text="Still here!")
        """
        return self._widget_name in Misc._widget_registry

    def winfo_height(self) -> int:
        """Get the widget's height.

        Returns:
            Height in character cells. Override in widgets with geometry.

        Example:
            >>> height = frame.winfo_height()
            >>> print(f"Frame is {height} rows tall")
        """
        return 0

    def winfo_width(self) -> int:
        """Get the widget's width.

        Returns:
            Width in character cells. Override in widgets with geometry.

        Example:
            >>> width = frame.winfo_width()
            >>> print(f"Frame is {width} columns wide")
        """
        return 0

    def winfo_id(self) -> str:
        """Get the widget's unique identifier.

        Returns:
            A unique string identifier for this widget.

        Example:
            >>> print(widget.winfo_id())  # "w140234567890"
        """
        return self._widget_name

    def winfo_ismapped(self) -> bool:
        """Check if the widget is visible (mapped).

        Returns:
            True if the widget is visible, False otherwise. Override in
            widgets with visibility tracking.

        Example:
            >>> if widget.winfo_ismapped():
            ...     print("Widget is visible")
        """
        return True

    def winfo_viewable(self) -> bool:
        """Check if the widget is viewable.

        A widget is viewable if it and all its ancestors up to the
        nearest toplevel are mapped (visible).

        Returns:
            True if the widget is viewable, False otherwise.

        Example:
            >>> if widget.winfo_viewable():
            ...     print("Widget is fully visible")
        """
        # Check if this widget is mapped
        if not self.winfo_ismapped():
            return False

        # Check ancestors up to toplevel
        parent_name = self.winfo_parent()
        if parent_name and hasattr(self, "_master") and self._master is not None:
            return self._master.winfo_viewable()

        return True

    def winfo_name(self) -> str:
        """Get the widget's name.

        Returns:
            The widget's name string.

        Example:
            >>> print(widget.winfo_name())  # "w140234567890"
        """
        return self._widget_name

    def winfo_parent(self) -> str:
        """Get the parent widget's name.

        Returns:
            Name of the parent widget, or empty string if no parent.
            Override in widgets that track their parent.

        Example:
            >>> parent_name = widget.winfo_parent()
            >>> parent = root.nametowidget(parent_name)
        """
        return ""

    def winfo_reqheight(self) -> int:
        """Get the widget's requested height.

        Returns:
            Requested height in character cells. Override in widgets.

        Example:
            >>> req_height = widget.winfo_reqheight()
        """
        return self.winfo_height()

    def winfo_reqwidth(self) -> int:
        """Get the widget's requested width.

        Returns:
            Requested width in character cells. Override in widgets.

        Example:
            >>> req_width = widget.winfo_reqwidth()
        """
        return self.winfo_width()

    def winfo_rootx(self) -> int:
        """Get the widget's x coordinate in root window coordinates.

        Returns:
            X coordinate (column) relative to root window. Override in widgets.

        Example:
            >>> x = widget.winfo_rootx()
        """
        return 0

    def winfo_rooty(self) -> int:
        """Get the widget's y coordinate in root window coordinates.

        Returns:
            Y coordinate (row) relative to root window. Override in widgets.

        Example:
            >>> y = widget.winfo_rooty()
        """
        return 0

    def winfo_screenheight(self) -> int:
        """Get the screen height.

        Returns:
            Terminal height in rows. Override to return actual screen size.

        Example:
            >>> height = root.winfo_screenheight()
            >>> print(f"Terminal is {height} rows tall")
        """
        # Will be overridden by Tk/Toplevel to return actual terminal size
        return 24

    def winfo_screenwidth(self) -> int:
        """Get the screen width.

        Returns:
            Terminal width in columns. Override to return actual screen size.

        Example:
            >>> width = root.winfo_screenwidth()
            >>> print(f"Terminal is {width} columns wide")
        """
        # Will be overridden by Tk/Toplevel to return actual terminal size
        return 80

    def winfo_toplevel(self) -> Misc:
        """Get the top-level window containing this widget.

        Returns:
            The top-level window. Override in widgets to return actual toplevel.

        Example:
            >>> toplevel = widget.winfo_toplevel()
        """
        return self

    def winfo_x(self) -> int:
        """Get the widget's x coordinate relative to parent.

        Returns:
            X coordinate (column) relative to parent widget. Override in widgets.

        Example:
            >>> x = widget.winfo_x()
        """
        return 0

    def winfo_y(self) -> int:
        """Get the widget's y coordinate relative to parent.

        Returns:
            Y coordinate (row) relative to parent widget. Override in widgets.

        Example:
            >>> y = widget.winfo_y()
        """
        return 0

    # =========================================================================
    # Configuration Methods
    # =========================================================================

    def cget(self, option: str) -> Any:
        """Get the value of a configuration option.

        Args:
            option: Name of the configuration option.

        Returns:
            The current value of the option.

        Raises:
            KeyError: If the option doesn't exist.

        Example:
            >>> text = label.cget("text")
            >>> print(text)
        """
        return self._config.get(option)

    def configure(self, **options: Any) -> None:
        """Configure widget options.

        Sets multiple configuration options at once. If called with no
        arguments, returns a dictionary of all configuration options.

        Args:
            **options: Keyword arguments for options to set.

        Returns:
            None, or dict of all options if no arguments provided.

        Example:
            >>> label.configure(text="New Text", fg="blue")
            >>> # Get all options
            >>> config = label.configure()
        """
        if not options:
            # Query mode: return all options
            return dict(self._config)

        # Update configuration
        self._config.update(options)

    def config(self, **options: Any) -> None:
        """Alias for configure().

        Short form of configure() for setting widget options.

        Args:
            **options: Keyword arguments for options to set.

        Example:
            >>> button.config(text="Click Me", state="disabled")
        """
        return self.configure(**options)

    def keys(self) -> list[str]:
        """Get a list of all configuration option names.

        Returns:
            List of option names that can be configured.

        Example:
            >>> options = widget.keys()
            >>> print(options)  # ['text', 'fg', 'bg', ...]
        """
        return list(self._config.keys())

    # =========================================================================
    # Widget Management Methods
    # =========================================================================

    def nametowidget(self, name: str) -> Optional[Misc]:
        """Get a widget by its path name.

        Looks up a widget in the global widget registry by name.

        Args:
            name: The widget's name/path.

        Returns:
            The widget with that name, or None if not found.

        Example:
            >>> widget = root.nametowidget("w140234567890")
            >>> if widget:
            ...     widget.focus_set()
        """
        return Misc._widget_registry.get(name)

    def register(self, func: Callable[..., Any]) -> str:
        """Register a Python function for validation callbacks.

        Creates a unique identifier for a function that can be used in
        validation callbacks (e.g., for Entry widgets).

        Args:
            func: The function to register.

        Returns:
            A unique string identifier for the function.

        Example:
            >>> def validate_int(value):
            ...     return value.isdigit()
            >>> vcmd = root.register(validate_int)
            >>> entry = Entry(root, validate="key", validatecommand=(vcmd, "%P"))
        """
        return f"func_{id(func)}"

    def quit(self) -> None:
        """Exit the main event loop.

        Stops the application's main loop, causing mainloop() to return.
        Override in Tk/Toplevel classes to implement actual quit behavior.

        Example:
            >>> button = Button(root, text="Quit", command=root.quit)
        """
        # Will be overridden by Tk class
        pass

    def update(self) -> None:
        """Process all pending events and redraw.

        Forces immediate processing of all pending events and updates the
        display. Use sparingly as it can cause performance issues.

        Example:
            >>> # Update display immediately
            >>> label.config(text="Processing...")
            >>> root.update()
            >>> # Do some work...
        """
        # Process after queue
        self._process_after_queue()
        # Will be overridden by Tk class to also refresh display

    def update_idletasks(self) -> None:
        """Process idle callbacks without waiting for events.

        Processes only the idle callbacks (from after_idle()) without
        waiting for or processing other events.

        Example:
            >>> root.update_idletasks()
        """
        # Process only idle callbacks (those with time <= current time)
        self._process_after_queue()

    def wait_variable(self, var: Any) -> None:
        """Wait for a variable to change.

        Blocks until the specified variable's value changes. This requires
        integration with the Variable class (StringVar, IntVar, etc.).

        Args:
            var: A Variable instance to monitor.

        Example:
            >>> result = StringVar()
            >>> # Some callback will eventually set result
            >>> root.wait_variable(result)
            >>> print(f"Result: {result.get()}")
        """
        # Stub: requires Variable class with trace mechanism
        pass

    def wait_visibility(self, window: Optional[Misc] = None) -> None:
        """Wait for a window to become visible.

        Blocks until the specified window is visible on screen.

        Args:
            window: The window to wait for. If None, waits for self.

        Example:
            >>> dialog = Toplevel(root)
            >>> root.wait_visibility(dialog)
        """
        # Stub: requires visibility tracking
        pass

    def wait_window(self, window: Optional[Misc] = None) -> None:
        """Wait for a window to be destroyed.

        Blocks until the specified window is destroyed. This is commonly
        used with dialogs to wait for the user's response.

        Args:
            window: The window to wait for. If None, waits for self.

        Example:
            >>> dialog = Toplevel(root)
            >>> # ... configure dialog ...
            >>> root.wait_window(dialog)  # Block until dialog closes
        """
        # Stub: requires window destruction tracking
        pass


class Wm:
    """Window manager methods for Tk and Toplevel windows.

    This class provides window management functionality that mirrors tkinter.Wm.
    It handles window geometry, title, state, protocols, and various window
    attributes. In TkCurses, these methods control terminal window behavior
    rather than GUI windows.

    This class is not instantiated directly but is used as a mixin base class
    for Tk and Toplevel classes, providing them with window manager capabilities.

    Window states in TkCurses:
        - "normal": Window is visible and active
        - "iconic": Window is minimized (stub, same as withdrawn)
        - "withdrawn": Window is hidden
        - "zoomed": Window is fullscreen (uses full terminal dimensions)

    Example:
        >>> root = Tk()
        >>> root.title("My Application")
        >>> root.geometry("80x24+0+0")
        >>> root.state("zoomed")  # Fullscreen mode
        >>> root.protocol("WM_DELETE_WINDOW", on_close)

    Attributes:
        _width: Window width in columns.
        _height: Window height in rows.
        _x: Window x position (column).
        _y: Window y position (row).
        _title: Window title string.
        _state: Window state ("normal", "iconic", "withdrawn", "zoomed").
        _protocols: Dictionary mapping protocol names to callback functions.
        _min_width: Minimum window width.
        _min_height: Minimum window height.
        _max_width: Maximum window width.
        _max_height: Maximum window height.
        _resizable_width: Whether window width is resizable.
        _resizable_height: Whether window height is resizable.
        _attributes: Dictionary of window attributes.
        _transient_master: Transient parent window.
    """

    def __init__(self) -> None:
        """Initialize window manager attributes.

        Sets up default window geometry, state, and other window manager
        properties. These will be overridden by window configuration calls.
        """
        self._width: int = 80
        self._height: int = 24
        self._x: int = 0
        self._y: int = 0
        self._title: str = ""
        self._state: str = "normal"
        self._protocols: dict[str, Callable[[], Any]] = {}
        self._min_width: Optional[int] = None
        self._min_height: Optional[int] = None
        self._max_width: Optional[int] = None
        self._max_height: Optional[int] = None
        self._resizable_width: bool = True
        self._resizable_height: bool = True
        self._attributes: dict[str, Any] = {}
        self._transient_master: Optional[Any] = None

    # =========================================================================
    # Window Geometry Methods
    # =========================================================================

    def wm_geometry(self, newGeometry: Optional[str] = None) -> Optional[str]:
        """Get or set the window geometry.

        The geometry string specifies the window size and position in the
        format "WIDTHxHEIGHT+X+Y" where WIDTH and HEIGHT are in columns and
        rows, and X and Y are the position coordinates.

        Args:
            newGeometry: Geometry string like "80x24+0+0". If None, returns
                current geometry.

        Returns:
            Current geometry string if newGeometry is None, otherwise None.

        Example:
            >>> root.wm_geometry("80x24+5+5")  # 80 cols, 24 rows at position (5,5)
            >>> current = root.wm_geometry()
            >>> print(current)  # "80x24+5+5"
        """
        if newGeometry is None:
            # Query mode: return current geometry
            return f"{self._width}x{self._height}+{self._x}+{self._y}"

        # Parse geometry string
        import re

        match = re.match(
            r'^(\d+)x(\d+)(?:([+-])(\d+)([+-])(\d+))?$',
            newGeometry.strip(),
        )
        if not match:
            raise ValueError(f'Invalid geometry string: {newGeometry!r}')

        # Set size
        self._width = int(match.group(1))
        self._height = int(match.group(2))

        # Set position if provided
        if match.group(3) is not None:
            x_sign = -1 if match.group(3) == '-' else 1
            self._x = x_sign * int(match.group(4))
            y_sign = -1 if match.group(5) == '-' else 1
            self._y = y_sign * int(match.group(6))

        return None

    def wm_minsize(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[tuple[int, int]]:
        """Get or set the minimum window size.

        Args:
            width: Minimum width in columns. If None, queries current minimum.
            height: Minimum height in rows. If None, queries current minimum.

        Returns:
            Current minimum size as (width, height) if querying, otherwise None.

        Example:
            >>> root.wm_minsize(40, 10)  # Set minimum size
            >>> min_w, min_h = root.wm_minsize()  # Query minimum size
        """
        if width is None and height is None:
            # Query mode: return current minimums
            return (self._min_width or 1, self._min_height or 1)

        # Set minimum size
        if width is not None:
            self._min_width = max(1, width)
        if height is not None:
            self._min_height = max(1, height)

        return None

    def wm_maxsize(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[tuple[int, int]]:
        """Get or set the maximum window size.

        Args:
            width: Maximum width in columns. If None, queries current maximum.
            height: Maximum height in rows. If None, queries current maximum.

        Returns:
            Current maximum size as (width, height) if querying, otherwise None.

        Example:
            >>> root.wm_maxsize(120, 40)  # Set maximum size
            >>> max_w, max_h = root.wm_maxsize()  # Query maximum size
        """
        if width is None and height is None:
            # Query mode: return current maximums
            # Return terminal dimensions as default max
            return (self._max_width or 999, self._max_height or 999)

        # Set maximum size
        if width is not None:
            self._max_width = max(1, width)
        if height is not None:
            self._max_height = max(1, height)

        return None

    def wm_resizable(
        self,
        width: Optional[bool] = None,
        height: Optional[bool] = None,
    ) -> Optional[tuple[bool, bool]]:
        """Get or set window resizability flags.

        Args:
            width: Whether window width can be resized. If None, queries current.
            height: Whether window height can be resized. If None, queries current.

        Returns:
            Current resizable flags as (width, height) if querying, otherwise None.

        Example:
            >>> root.wm_resizable(True, False)  # Width resizable, height fixed
            >>> can_resize_w, can_resize_h = root.wm_resizable()
        """
        if width is None and height is None:
            # Query mode: return current flags
            return (self._resizable_width, self._resizable_height)

        # Set resizable flags
        if width is not None:
            self._resizable_width = bool(width)
        if height is not None:
            self._resizable_height = bool(height)

        return None

    # =========================================================================
    # Window Title/Identity Methods
    # =========================================================================

    def wm_title(self, string: Optional[str] = None) -> Optional[str]:
        """Get or set the window title.

        Args:
            string: Title string to set. If None, returns current title.

        Returns:
            Current title if string is None, otherwise None.

        Example:
            >>> root.wm_title("My Application")
            >>> print(root.wm_title())  # "My Application"
        """
        if string is None:
            # Query mode: return current title
            return self._title

        # Set title
        self._title = string
        return None

    def wm_iconname(self, newName: Optional[str] = None) -> Optional[str]:
        """Get or set the icon name.

        In GUI toolkits, this sets the name shown when the window is iconified.
        In TkCurses, this is a stub for compatibility.

        Args:
            newName: Icon name to set. If None, returns current icon name.

        Returns:
            Current icon name if newName is None, otherwise None.

        Example:
            >>> root.wm_iconname("MyApp")
        """
        # Stub: terminals don't have window icons
        # Use title as fallback
        if newName is None:
            return self._title
        return None

    def wm_iconbitmap(self, bitmap: Optional[str] = None) -> None:
        """Set the window icon bitmap.

        In GUI toolkits, this sets the window icon image. In TkCurses,
        this is a stub for compatibility since terminals don't support icons.

        Args:
            bitmap: Path to bitmap file (ignored).

        Example:
            >>> root.wm_iconbitmap("icon.xbm")  # No effect in terminal
        """
        # Stub: terminals don't have window icons
        pass

    # =========================================================================
    # Window State Methods
    # =========================================================================

    def wm_state(self, newstate: Optional[str] = None) -> Optional[str]:
        """Get or set the window state.

        Valid states:
            - "normal": Window is visible and active
            - "iconic": Window is minimized (stub, same as withdrawn)
            - "withdrawn": Window is hidden
            - "zoomed": Window is fullscreen (uses full terminal dimensions)

        Args:
            newstate: State to set. If None, returns current state.

        Returns:
            Current state if newstate is None, otherwise None.

        Example:
            >>> root.wm_state("zoomed")  # Go fullscreen
            >>> print(root.wm_state())  # "zoomed"
        """
        if newstate is None:
            # Query mode: return current state
            return self._state

        # Validate state
        valid_states = ("normal", "iconic", "withdrawn", "zoomed")
        if newstate not in valid_states:
            raise ValueError(
                f'Invalid state {newstate!r}. Must be one of: {valid_states}'
            )

        # Set state
        self._state = newstate
        return None

    def wm_withdraw(self) -> None:
        """Hide the window.

        Sets the window state to "withdrawn", making it invisible.
        The window can be shown again with wm_deiconify().

        Example:
            >>> root.wm_withdraw()  # Hide window
        """
        self._state = "withdrawn"

    def wm_deiconify(self) -> None:
        """Show the window.

        Sets the window state to "normal", making it visible. This reverses
        the effect of wm_withdraw() or wm_iconify().

        Example:
            >>> root.wm_withdraw()
            >>> # ... later ...
            >>> root.wm_deiconify()  # Show window again
        """
        self._state = "normal"

    def wm_iconify(self) -> None:
        """Iconify (minimize) the window.

        In TkCurses, this is equivalent to wm_withdraw() since terminals
        don't have a true iconified state. The window is simply hidden.

        Example:
            >>> root.wm_iconify()  # Minimize window
        """
        # Stub: terminals don't have iconified state
        # Treat as withdrawn
        self._state = "iconic"

    # =========================================================================
    # Window Attributes Methods
    # =========================================================================

    def attributes(self, *args: Any) -> Any:
        """Get or set window attributes.

        Attributes control window behavior and appearance. Format:
            - Query all: attributes() -> dict
            - Query one: attributes("-fullscreen") -> value
            - Set one: attributes("-fullscreen", True)
            - Set many: attributes("-fullscreen", True, "-topmost", True)

        Supported attributes:
            -fullscreen: Boolean, fullscreen mode (same as "zoomed" state)
            -topmost: Boolean, keep window on top (stub for terminal)
            -alpha: Float 0.0-1.0, transparency (stub, terminals don't support)

        Args:
            *args: Attribute name(s) and value(s).

        Returns:
            Value(s) when querying, None when setting.

        Example:
            >>> root.attributes("-fullscreen", True)
            >>> is_fullscreen = root.attributes("-fullscreen")
            >>> all_attrs = root.attributes()
        """
        if not args:
            # Query all attributes
            return dict(self._attributes)

        if len(args) == 1:
            # Query single attribute
            attr_name = args[0]
            if not isinstance(attr_name, str) or not attr_name.startswith('-'):
                raise ValueError(f'Invalid attribute name: {attr_name!r}')
            return self._attributes.get(attr_name, None)

        # Set attributes
        if len(args) % 2 != 0:
            raise ValueError('Attributes must be provided in name-value pairs')

        for i in range(0, len(args), 2):
            attr_name = args[i]
            attr_value = args[i + 1]

            if not isinstance(attr_name, str) or not attr_name.startswith('-'):
                raise ValueError(f'Invalid attribute name: {attr_name!r}')

            # Handle special attributes
            if attr_name == '-fullscreen':
                # Fullscreen is equivalent to "zoomed" state
                if attr_value:
                    self._state = "zoomed"
                else:
                    self._state = "normal"

            # Store attribute
            self._attributes[attr_name] = attr_value

        return None

    def wm_attributes(self, *args: Any) -> Any:
        """Alias for attributes().

        See attributes() for documentation.
        """
        return self.attributes(*args)

    # =========================================================================
    # Window Protocol Methods
    # =========================================================================

    def wm_protocol(
        self,
        name: Optional[str] = None,
        func: Optional[Callable[[], Any]] = None,
    ) -> Optional[str]:
        """Register or query a window protocol handler.

        Window protocols are special events handled by the window manager.
        Common protocols:
            - "WM_DELETE_WINDOW": Called when window is closed
            - "WM_TAKE_FOCUS": Called when window gains focus
            - "WM_SAVE_YOURSELF": Called before window manager restart

        Args:
            name: Protocol name (e.g., "WM_DELETE_WINDOW").
            func: Callback function to register. If None and name is provided,
                returns the current handler. If both are None, returns list
                of registered protocols.

        Returns:
            Handler function or protocol list when querying, None when setting.

        Example:
            >>> def on_close():
            ...     if messagebox.askokcancel("Quit", "Really quit?"):
            ...         root.destroy()
            >>> root.wm_protocol("WM_DELETE_WINDOW", on_close)
        """
        if name is None:
            # Query mode: return list of all protocols
            return list(self._protocols.keys())

        if func is None:
            # Query mode: return handler for this protocol
            handler = self._protocols.get(name)
            return handler if handler else ""

        # Register protocol handler
        self._protocols[name] = func
        return None

    # =========================================================================
    # Transient/Focus Methods
    # =========================================================================

    def wm_transient(self, master: Optional[Any] = None) -> Optional[str]:
        """Set or query the transient parent window.

        A transient window is a dialog or popup that is associated with
        a parent window. Transient windows typically:
            - Stay on top of their parent
            - Minimize/close when parent does
            - Don't appear in taskbar separately

        Args:
            master: Parent window to set as transient master. If None and
                currently transient, returns master. If empty string,
                removes transient relationship.

        Returns:
            Master window name if querying, None otherwise.

        Example:
            >>> dialog = Toplevel(root)
            >>> dialog.wm_transient(root)  # Make dialog transient to root
        """
        if master is None:
            # Query mode: return current master
            return str(self._transient_master) if self._transient_master else ""

        if master == "":
            # Clear transient relationship
            self._transient_master = None
        else:
            # Set transient master
            self._transient_master = master

        return None

    def wm_focusmodel(self, model: Optional[str] = None) -> Optional[str]:
        """Get or set the focus model.

        Focus models:
            - "active": Window actively grabs focus
            - "passive": Window waits for focus to be given

        In TkCurses, this is a stub for compatibility.

        Args:
            model: Focus model to set ("active" or "passive").

        Returns:
            Current focus model if querying, None otherwise.

        Example:
            >>> root.wm_focusmodel("active")
        """
        # Stub: terminals don't have distinct focus models
        if model is None:
            return "passive"
        return None

    def lift(self, aboveThis: Optional[Any] = None) -> None:
        """Raise the window in the stacking order.

        Brings the window to the front, above other windows.

        Args:
            aboveThis: Window to raise above. If None, raises to top.

        Example:
            >>> root.lift()  # Bring root window to front
        """
        # Stub: will be implemented in Tk/Toplevel with panel stacking
        pass

    def lower(self, belowThis: Optional[Any] = None) -> None:
        """Lower the window in the stacking order.

        Sends the window to the back, below other windows.

        Args:
            belowThis: Window to lower below. If None, lowers to bottom.

        Example:
            >>> root.lower()  # Send root window to back
        """
        # Stub: will be implemented in Tk/Toplevel with panel stacking
        pass

    # =========================================================================
    # Other Window Manager Methods
    # =========================================================================

    def wm_overrideredirect(self, boolean: Optional[bool] = None) -> Optional[bool]:
        """Get or set override-redirect flag.

        When True, the window bypasses the window manager and has no
        decorations or standard behaviors. In TkCurses, this is a stub.

        Args:
            boolean: Override-redirect flag to set.

        Returns:
            Current flag if querying, None otherwise.

        Example:
            >>> root.wm_overrideredirect(True)  # No window decorations
        """
        # Stub: terminals don't have window decorations
        if boolean is None:
            return False
        return None

    def wm_positionfrom(self, who: Optional[str] = None) -> Optional[str]:
        """Get or set the position source indicator.

        Indicates who specified the window position:
            - "user": Position set by user
            - "program": Position set by program

        In TkCurses, this is a stub for compatibility.

        Args:
            who: Position source to set ("user" or "program").

        Returns:
            Current source if querying, None otherwise.

        Example:
            >>> root.wm_positionfrom("user")
        """
        # Stub: terminals don't track position source
        if who is None:
            return "program"
        return None

    def wm_sizefrom(self, who: Optional[str] = None) -> Optional[str]:
        """Get or set the size source indicator.

        Indicates who specified the window size:
            - "user": Size set by user
            - "program": Size set by program

        In TkCurses, this is a stub for compatibility.

        Args:
            who: Size source to set ("user" or "program").

        Returns:
            Current source if querying, None otherwise.

        Example:
            >>> root.wm_sizefrom("user")
        """
        # Stub: terminals don't track size source
        if who is None:
            return "program"
        return None

    def wm_client(self, name: Optional[str] = None) -> Optional[str]:
        """Get or set the WM_CLIENT_MACHINE property.

        Specifies the client machine hostname for X11 session management.
        In TkCurses, this is a stub for compatibility.

        Args:
            name: Client machine name to set.

        Returns:
            Current client name if querying, None otherwise.

        Example:
            >>> root.wm_client("localhost")
        """
        # Stub: terminals don't use X11 client machine
        if name is None:
            return ""
        return None

    def wm_colormapwindows(self, *wlist: Any) -> Optional[tuple[Any, ...]]:
        """Get or set the colormap windows list.

        Used in X11 for colormap management. In TkCurses, this is a stub
        for compatibility.

        Args:
            *wlist: Windows to set in colormap list.

        Returns:
            Current colormap window list if querying, None otherwise.

        Example:
            >>> root.wm_colormapwindows()
        """
        # Stub: terminals don't use X11 colormaps
        if not wlist:
            return ()
        return None

    def wm_command(self, value: Optional[str] = None) -> Optional[str]:
        """Get or set the WM_COMMAND property.

        Specifies the command used to start the application for X11 session
        management. In TkCurses, this is a stub for compatibility.

        Args:
            value: Command string to set.

        Returns:
            Current command if querying, None otherwise.

        Example:
            >>> root.wm_command("python myapp.py")
        """
        # Stub: terminals don't use X11 WM_COMMAND
        if value is None:
            return ""
        return None

    def wm_frame(self) -> str:
        """Get the window frame identifier.

        Returns the platform-specific window frame ID. In X11, this is the
        X window ID. In TkCurses, returns a dummy identifier.

        Returns:
            Frame identifier string.

        Example:
            >>> frame_id = root.wm_frame()
        """
        # Return dummy frame ID
        return f"0x{id(self):x}"

    def wm_group(self, pathName: Optional[str] = None) -> Optional[str]:
        """Get or set the window group leader.

        Window groups allow multiple windows to be treated as a unit.
        In TkCurses, this is a stub for compatibility.

        Args:
            pathName: Path name of group leader window.

        Returns:
            Current group leader if querying, None otherwise.

        Example:
            >>> root.wm_group(".main")
        """
        # Stub: terminals don't have window groups
        if pathName is None:
            return ""
        return None

    # =========================================================================
    # Method Aliases (tkinter compatibility)
    # =========================================================================
    # In tkinter, wm_* methods have short aliases without the wm_ prefix

    geometry = wm_geometry
    minsize = wm_minsize
    maxsize = wm_maxsize
    resizable = wm_resizable
    title = wm_title
    iconname = wm_iconname
    iconbitmap = wm_iconbitmap
    state = wm_state
    withdraw = wm_withdraw
    deiconify = wm_deiconify
    iconify = wm_iconify
    protocol = wm_protocol
    transient = wm_transient
    focusmodel = wm_focusmodel
    overrideredirect = wm_overrideredirect
    positionfrom = wm_positionfrom
    sizefrom = wm_sizefrom
    client = wm_client
    colormapwindows = wm_colormapwindows
    command = wm_command
    frame = wm_frame
    group = wm_group


class BaseWidget:
    """Base class for widget creation and curses window management.

    BaseWidget provides the foundational functionality for all TkCurses widgets,
    handling widget lifecycle, curses window management, and the widget hierarchy.
    It manages the creation and destruction of curses windows, integrates with
    the PanelStack for z-ordering, and maintains parent-child relationships.

    This class is not typically instantiated directly but is used as a base
    class for Widget, Tk, and Toplevel. It provides the core infrastructure
    that all widgets build upon.

    Key responsibilities:
        - Widget lifecycle (creation, configuration, destruction)
        - Curses window allocation and management
        - Panel creation for z-ordering
        - Parent-child hierarchy tracking
        - Widget naming and path generation
        - Geometry allocation and size requests
        - Rendering interface (abstract methods for subclasses)

    Example:
        >>> # BaseWidget is typically not used directly
        >>> # It's inherited by Widget and other classes
        >>> class MyWidget(BaseWidget):
        ...     def _draw(self):
        ...         # Implement custom drawing
        ...         pass

    Attributes:
        master: The parent widget (None for root windows).
        _children: List of child widgets.
        _widget_path: Hierarchical widget path name (e.g., ".!frame.!button").
        _curses_window: The underlying curses window object.
        _panel: The curses panel for z-ordering.
        _is_destroyed: Whether the widget has been destroyed.
        _is_mapped: Whether the widget is visible.
        _requested_width: Width requested by the widget.
        _requested_height: Height requested by the widget.
        _allocated_width: Width allocated by geometry manager.
        _allocated_height: Height allocated by geometry manager.
        _allocated_x: X position allocated by geometry manager.
        _allocated_y: Y position allocated by geometry manager.
    """

    # Class-level counter for generating unique widget names
    _widget_counter: dict[str, int] = {}

    def __init__(self, master: Optional[BaseWidget] = None, **kw: Any) -> None:
        """Initialize the BaseWidget.

        Creates a new widget with optional parent. The widget is registered
        with its parent and configuration options are stored for later
        application when the widget is realized.

        Args:
            master: Parent widget. If None, this is a top-level widget.
            **kw: Configuration options to apply to the widget. Common
                options include:
                - background/bg: Background color
                - foreground/fg: Foreground color
                - width: Requested width in columns
                - height: Requested height in rows
                - cursor: Cursor style (stub)
                - takefocus: Whether widget accepts focus

        Example:
            >>> # Typically used in subclass constructors
            >>> frame = Frame(root, width=40, height=10, bg="blue")
        """
        self.master: Optional[BaseWidget] = master
        self._children: list[BaseWidget] = []
        self._curses_window: Optional[_CursesWindow] = None
        self._panel: Optional[Panel] = None
        self._is_destroyed: bool = False
        self._is_mapped: bool = False

        # Geometry management
        self._requested_width: int = 0
        self._requested_height: int = 0
        self._allocated_width: int = 0
        self._allocated_height: int = 0
        self._allocated_x: int = 0
        self._allocated_y: int = 0

        # Layout management
        self._layout_dirty: bool = True
        self._has_border: bool = False
        self._pack_propagate_flag: bool = True
        self._grid_propagate_flag: bool = True

        # Get screen and dispatcher instances
        self._screen: CursesScreen = CursesScreen()
        self._dispatcher: CursesDispatcher = CursesDispatcher.get()
        self._panel_stack: PanelStack = PanelStack.get()

        # Generate unique widget path name
        self._widget_path: str = self._generate_widget_path()

        # Register with parent
        if self.master is not None:
            self.master._add_child(self)

        # Store configuration options (will be applied when widget is realized)
        self._widget_config: dict[str, Any] = {}
        if kw:
            self._configure_widget(**kw)

    def _generate_widget_path(self) -> str:
        """Generate a unique hierarchical widget path name.

        Creates a path name in the form ".!class_name.!class_name2" where
        each component represents a widget in the hierarchy. Each widget
        class has a counter to ensure unique names.

        Returns:
            A unique widget path string.

        Example:
            >>> widget._generate_widget_path()
            '.!frame1'
            >>> child._generate_widget_path()
            '.!frame1.!button1'
        """
        class_name = self.__class__.__name__.lower()

        # Increment counter for this widget class
        if class_name not in BaseWidget._widget_counter:
            BaseWidget._widget_counter[class_name] = 0
        BaseWidget._widget_counter[class_name] += 1

        # Generate unique name with counter
        widget_name = f"!{class_name}{BaseWidget._widget_counter[class_name]}"

        # Build hierarchical path
        if self.master is None:
            # Root widget
            return "."
        elif hasattr(self.master, "_widget_path"):
            # Append to parent's path
            parent_path = self.master._widget_path
            if parent_path == ".":
                return f".{widget_name}"
            else:
                return f"{parent_path}.{widget_name}"
        else:
            # Fallback
            return f".{widget_name}"

    # =========================================================================
    # Widget Hierarchy Methods
    # =========================================================================

    def _add_child(self, widget: BaseWidget) -> None:
        """Add a child widget to this widget's children list.

        Args:
            widget: The child widget to add.

        Example:
            >>> parent._add_child(child_widget)
        """
        if widget not in self._children:
            self._children.append(widget)

    def _remove_child(self, widget: BaseWidget) -> None:
        """Remove a child widget from this widget's children list.

        Args:
            widget: The child widget to remove.

        Example:
            >>> parent._remove_child(child_widget)
        """
        if widget in self._children:
            self._children.remove(widget)

    # =========================================================================
    # Curses Window Management Methods
    # =========================================================================

    def _create_window(
        self,
        height: int,
        width: int,
        y: int,
        x: int,
    ) -> None:
        """Create a curses subwindow for this widget.

        Creates a new curses window and associated panel for z-ordering.
        The window is created as a subwindow of the parent's window, or
        of stdscr for root widgets.

        Args:
            height: Window height in rows.
            width: Window width in columns.
            y: Y position (row) relative to parent.
            x: X position (column) relative to parent.

        Raises:
            RuntimeError: If curses screen is not initialized.

        Example:
            >>> widget._create_window(10, 40, 5, 5)
        """
        if self._curses_window is not None:
            # Window already exists, destroy it first
            self._destroy_window()

        # Ensure screen is initialized
        if self._screen.stdscr is None:
            raise RuntimeError("Curses screen not initialized")

        # Determine parent window
        if self.master is None or not hasattr(self.master, "_curses_window"):
            # Root widget - use stdscr
            parent_window = self._screen.stdscr
        else:
            # Child widget - use parent's window
            parent_window = self.master._curses_window
            if parent_window is None:
                raise RuntimeError("Parent widget window not initialized")

        # Create subwindow through dispatcher for thread safety
        def create_subwin() -> _CursesWindow:
            import curses
            # Ensure dimensions are valid
            h = max(1, height)
            w = max(1, width)
            # Create subwindow
            try:
                return parent_window.subwin(h, w, y, x)
            except curses.error as e:
                # If subwin fails, try derwin (derivative window)
                try:
                    return parent_window.derwin(h, w, y, x)
                except curses.error:
                    # Re-raise original error
                    raise e

        self._curses_window = self._dispatcher.call(create_subwin)

        # Create panel for z-ordering
        self._panel = self._panel_stack.create_panel(self._curses_window)

        # Mark as mapped (visible)
        self._is_mapped = True

    def _destroy_window(self) -> None:
        """Destroy the curses window and panel for this widget.

        Removes the widget from the panel stack and deallocates its
        curses window. Safe to call even if no window exists.

        Example:
            >>> widget._destroy_window()
        """
        # Remove from panel stack
        if self._panel is not None:
            try:
                self._panel_stack.remove_panel(self._panel)
            except Exception:
                pass
            self._panel = None

        # Clear window reference
        # Note: curses windows are automatically deallocated by Python's GC
        # when the reference count drops to zero
        self._curses_window = None
        self._is_mapped = False

    def _resize_window(self, height: int, width: int) -> None:
        """Resize the curses window.

        Args:
            height: New height in rows.
            width: New width in columns.

        Example:
            >>> widget._resize_window(20, 60)
        """
        if self._curses_window is None:
            return

        curses_window = self._curses_window  # Capture for closure

        def resize() -> None:
            import curses
            try:
                curses_window.resize(height, width)
            except curses.error:
                # If resize fails, recreate the window
                self._create_window(
                    height,
                    width,
                    self._allocated_y,
                    self._allocated_x,
                )

        self._dispatcher.call(resize)

    # =========================================================================
    # Widget Lifecycle Methods
    # =========================================================================

    def destroy(self) -> None:
        """Destroy this widget and all its children.

        Recursively destroys all child widgets, then destroys this widget's
        curses window and panel. Removes the widget from its parent's
        children list.

        Example:
            >>> widget.destroy()
        """
        if self._is_destroyed:
            return

        # Destroy all children first
        for child in list(self._children):
            child.destroy()
        self._children.clear()

        # Destroy curses window and panel
        self._destroy_window()

        # Remove from parent's children
        if self.master is not None:
            self.master._remove_child(self)

        # Mark as destroyed
        self._is_destroyed = True

    def _configure_widget(self, **kw: Any) -> None:
        """Apply configuration options to the widget.

        Stores configuration options and handles common option aliases.
        Specific option handling should be implemented in subclasses.

        Args:
            **kw: Configuration options to apply. Common options:
                - background/bg: Background color
                - foreground/fg: Foreground color
                - width: Requested width
                - height: Requested height
                - cursor: Cursor style
                - takefocus: Whether widget accepts focus

        Example:
            >>> widget._configure_widget(width=40, height=10, bg="blue")
        """
        # Handle option aliases
        if "bg" in kw and "background" not in kw:
            kw["background"] = kw.pop("bg")
        if "fg" in kw and "foreground" not in kw:
            kw["foreground"] = kw.pop("fg")

        # Store configuration
        self._widget_config.update(kw)

        # Handle size requests
        if "width" in kw:
            self._requested_width = int(kw["width"])
        if "height" in kw:
            self._requested_height = int(kw["height"])

    # =========================================================================
    # Rendering Interface Methods
    # =========================================================================

    def _draw(self) -> None:
        """Draw the widget to its curses window.

        This is an abstract method that should be overridden by subclasses
        to implement widget-specific rendering. The default implementation
        does nothing.

        Subclasses should use self._curses_window to draw content.

        Example:
            >>> def _draw(self):
            ...     if self._curses_window:
            ...         self._curses_window.addstr(0, 0, "Hello")
        """
        # Abstract method - override in subclasses
        pass

    def _redraw(self) -> None:
        """Request a redraw of this widget.

        Calls _draw() to render the widget, then updates the panel stack
        to make changes visible. Safe to call even if widget has no window.

        Example:
            >>> widget._redraw()
        """
        if self._curses_window is None or self._is_destroyed:
            return

        # Draw the widget
        self._draw()

        # Update panel stack to make changes visible
        self._panel_stack.update()

    def _get_content_area(self) -> tuple[int, int, int, int]:
        """Get the drawable content area inside any borders.

        Returns the area available for widget content, accounting for
        any borders or padding. For widgets without borders, this is
        the full allocated size.

        Returns:
            Tuple of (y, x, height, width) defining the content area.
            If no window exists, returns (0, 0, 0, 0).

        Example:
            >>> y, x, height, width = widget._get_content_area()
            >>> # Draw content within this area
        """
        if self._curses_window is None:
            return (0, 0, 0, 0)

        # For base widgets, content area is the full window
        # Subclasses can override to account for borders
        return (0, 0, self._allocated_height, self._allocated_width)

    # =========================================================================
    # Geometry Interface Methods
    # =========================================================================

    def _request_size(self, width: int, height: int) -> None:
        """Request a specific size from the parent/geometry manager.

        Updates the widget's requested dimensions. The actual allocated
        size is determined by the geometry manager.

        Args:
            width: Requested width in columns.
            height: Requested height in rows.

        Example:
            >>> widget._request_size(40, 10)
        """
        self._requested_width = width
        self._requested_height = height

    def _allocate_size(self, width: int, height: int, x: int, y: int) -> None:
        """Receive allocated size and position from geometry manager.

        Called by geometry managers (pack, grid, place) to allocate space
        to the widget. Creates or resizes the curses window to match the
        allocated dimensions.

        Args:
            width: Allocated width in columns.
            height: Allocated height in rows.
            x: Allocated x position (column) relative to parent.
            y: Allocated y position (row) relative to parent.

        Example:
            >>> widget._allocate_size(40, 10, 5, 5)
        """
        self._allocated_width = width
        self._allocated_height = height
        self._allocated_x = x
        self._allocated_y = y

        # Create or resize window to match allocation
        if self._curses_window is None:
            self._create_window(height, width, y, x)
        else:
            # Resize existing window
            self._resize_window(height, width)

            # Move window to new position if needed
            if self._panel is not None:
                self._panel.move(y, x)

    # =========================================================================
    # Layout Methods
    # =========================================================================

    def _mark_layout_dirty(self) -> None:
        """Mark this widget and ancestors as needing layout recalculation.

        Called when a widget's geometry configuration changes. Propagates
        the dirty flag up to the root to ensure the entire affected tree
        is relaid out.

        Example:
            >>> widget._mark_layout_dirty()
        """
        LayoutManager.mark_dirty(self)

    def _do_layout(self) -> None:
        """Perform layout calculation for this widget and descendants.

        Calculates positions and sizes for all child widgets based on
        their geometry manager configurations (pack, grid, place).

        Example:
            >>> root._do_layout()
        """
        LayoutManager.do_layout(self)

    def _get_natural_size(self) -> Size:
        """Get the widget's natural/preferred size.

        Returns the size the widget would prefer to be, based on its
        content and configuration. This is used by geometry managers
        to determine how much space to allocate.

        Returns:
            Size with preferred width and height in cell units.

        Example:
            >>> size = widget._get_natural_size()
            >>> print(f"Preferred size: {size.width}x{size.height}")
        """
        # Use requested size if set
        width = self._requested_width if self._requested_width > 0 else 10
        height = self._requested_height if self._requested_height > 0 else 1

        # If propagation is enabled, consider children
        if self._pack_propagate_flag and hasattr(self, "pack_slaves"):
            children = self.pack_slaves()
            if children:
                child_size = self._calculate_children_pack_size()
                width = max(width, child_size.width)
                height = max(height, child_size.height)

        if self._grid_propagate_flag and hasattr(self, "grid_slaves"):
            children = self.grid_slaves()
            if children:
                child_size = self._calculate_children_grid_size()
                width = max(width, child_size.width)
                height = max(height, child_size.height)

        # Account for border
        if self._has_border:
            width += 2
            height += 2

        return Size(width, height)

    def _calculate_children_pack_size(self) -> Size:
        """Calculate total size needed for packed children.

        Returns:
            Size with total width and height needed.
        """
        if not hasattr(self, "pack_slaves"):
            return Size(0, 0)

        children = self.pack_slaves()
        if not children:
            return Size(0, 0)

        total_width = 0
        total_height = 0
        max_width = 0
        max_height = 0

        for child in children:
            info = getattr(child, "_pack_info", None)
            if info is None:
                continue

            size = child._get_natural_size()
            side = info.get("side", "top").lower()
            padx = info.get("padx", 0)
            pady = info.get("pady", 0)
            if isinstance(padx, (list, tuple)):
                padx = padx[0] if padx else 0
            if isinstance(pady, (list, tuple)):
                pady = pady[0] if pady else 0

            if side in ("top", "bottom"):
                total_height += size.height + 2 * pady
                max_width = max(max_width, size.width + 2 * padx)
            else:
                total_width += size.width + 2 * padx
                max_height = max(max_height, size.height + 2 * pady)

        return Size(max(total_width, max_width), max(total_height, max_height))

    def _calculate_children_grid_size(self) -> Size:
        """Calculate total size needed for gridded children.

        Returns:
            Size with total width and height needed.
        """
        if not hasattr(self, "grid_slaves") or not hasattr(self, "grid_size"):
            return Size(0, 0)

        children = self.grid_slaves()
        if not children:
            return Size(0, 0)

        num_cols, num_rows = self.grid_size()
        if num_cols == 0 or num_rows == 0:
            return Size(0, 0)

        col_widths = [1] * num_cols
        row_heights = [1] * num_rows

        for child in children:
            info = getattr(child, "_grid_info", None)
            if info is None:
                continue

            col = info.get("column", 0)
            row = info.get("row", 0)
            colspan = info.get("columnspan", 1)
            rowspan = info.get("rowspan", 1)

            if colspan == 1 and col < num_cols:
                size = child._get_natural_size()
                padx = info.get("padx", 0)
                if isinstance(padx, (list, tuple)):
                    padx = padx[0] if padx else 0
                col_widths[col] = max(col_widths[col], size.width + 2 * padx)

            if rowspan == 1 and row < num_rows:
                size = child._get_natural_size()
                pady = info.get("pady", 0)
                if isinstance(pady, (list, tuple)):
                    pady = pady[0] if pady else 0
                row_heights[row] = max(row_heights[row], size.height + 2 * pady)

        return Size(sum(col_widths), sum(row_heights))

    def _get_minimum_size(self) -> Size:
        """Get the widget's minimum required size.

        Returns the absolute minimum size the widget needs to be
        functional, accounting for borders and essential content.

        Returns:
            Size with minimum width and height in cell units.

        Example:
            >>> min_size = widget._get_minimum_size()
        """
        # Minimum 1x1 for content, plus border if present
        if self._has_border:
            return Size(3, 3)  # 1 content + 2 border
        return Size(1, 1)

    def _get_content_bounds(self) -> Rect:
        """Get the area available for child widgets.

        Returns the rectangular region where children can be placed,
        accounting for borders and other decorations.

        Returns:
            Rect representing the content area.

        Example:
            >>> bounds = widget._get_content_bounds()
            >>> # Layout children within bounds
        """
        width = self._allocated_width or getattr(self, "_width", 80)
        height = self._allocated_height or getattr(self, "_height", 24)
        x = self._allocated_x
        y = self._allocated_y

        if self._has_border:
            return Rect(x + 1, y + 1, max(1, width - 2), max(1, height - 2))
        return Rect(x, y, width, height)

    def _apply_layout(self, result: Any) -> None:
        """Apply calculated layout result to this widget.

        Called by layout engines to set the widget's position and size.
        The result is a LayoutResult object with x, y, width, height.

        Args:
            result: LayoutResult from a layout engine.
        """
        from ._core.layout import LayoutResult

        if isinstance(result, LayoutResult):
            self._allocated_x = result.x
            self._allocated_y = result.y
            self._allocated_width = result.width
            self._allocated_height = result.height

            # Update curses window if it exists
            if hasattr(self, '_window') and self._window is not None:
                try:
                    # Get dispatcher from master
                    dispatcher = None
                    if hasattr(self, 'master') and hasattr(self.master, '_dispatcher'):
                        dispatcher = self.master._dispatcher
                    elif hasattr(self, '_tk_root') and hasattr(self._tk_root, '_dispatcher'):
                        dispatcher = self._tk_root._dispatcher

                    if dispatcher:
                        # Resize and move window
                        dispatcher.call(
                            self._window.resize,
                            max(1, result.height),
                            max(1, result.width),
                        )
                        dispatcher.call(
                            self._window.mvwin,
                            result.y,
                            result.x,
                        )
                except curses.error:
                    # Window operations may fail at boundaries
                    pass


class Pack:
    """Pack geometry manager stub for Widget class.

    The Pack geometry manager arranges widgets in blocks before placing them
    in the parent widget. Widgets are positioned one after another in a
    specified direction (side), and can expand to fill available space.

    This is a stub implementation that stores pack options but does not
    perform actual layout calculations. Layout calculation will be implemented
    in Phase 3.

    Pack options:
        side: Which side to pack against (TOP, BOTTOM, LEFT, RIGHT).
        fill: Whether to fill available space (NONE, X, Y, BOTH).
        expand: Whether to expand to use extra space (0 or 1).
        anchor: Where to position widget (N, S, E, W, NE, NW, SE, SW, CENTER).
        padx, pady: External padding in pixels.
        ipadx, ipady: Internal padding in pixels.
        in_: Parent widget to pack into.
        before, after: Sibling widget for ordering.

    Example:
        >>> button = Button(root, text="Click")
        >>> button.pack(side=LEFT, fill=X, expand=True)
        >>> button.pack_info()
        {'side': 'left', 'fill': 'x', 'expand': True, ...}
    """

    def __init__(self) -> None:
        """Initialize Pack geometry manager stub.

        Sets up internal storage for pack options.
        """
        self._pack_info: Optional[dict[str, Any]] = None

    def pack(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Pack widget with specified options.

        Stores pack configuration options and marks this widget as being
        managed by the pack geometry manager. If widget was previously
        managed by grid or place, those managers are forgotten.

        Args:
            cnf: Dictionary of pack options.
            **kw: Pack options as keyword arguments.

        Example:
            >>> widget.pack(side='left', fill='x')
            >>> widget.pack({'side': 'top', 'expand': True})
        """
        # Merge cnf and kw
        options = dict(cnf, **kw)

        # Forget other geometry managers
        if hasattr(self, "_grid_info") and self._grid_info is not None:
            self._grid_info = None
        if hasattr(self, "_place_info") and self._place_info is not None:
            self._place_info = None

        # Initialize pack_info if needed
        if self._pack_info is None:
            self._pack_info = {
                "side": "top",
                "fill": "none",
                "expand": 0,
                "anchor": "center",
                "padx": 0,
                "pady": 0,
                "ipadx": 0,
                "ipady": 0,
            }

        # Handle 'in' parameter (Python keyword workaround)
        if "in" in options:
            options["in_"] = options.pop("in")

        # Update pack options
        self._pack_info.update(options)

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def pack_configure(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Alias for pack().

        See pack() for documentation.
        """
        self.pack(cnf, **kw)

    def pack_forget(self) -> None:
        """Remove widget from pack geometry manager.

        Unmaps the widget and removes pack configuration. The widget
        can be packed again later with pack().

        Example:
            >>> widget.pack_forget()  # Hide widget
            >>> widget.pack()  # Show again with previous options
        """
        self._pack_info = None

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def pack_info(self) -> dict[str, Any]:
        """Return pack configuration options.

        Returns:
            Dictionary of current pack options, or empty dict if not packed.

        Example:
            >>> widget.pack(side='left', fill='x')
            >>> info = widget.pack_info()
            >>> print(info['side'])  # 'left'
        """
        if self._pack_info is None:
            return {}
        return dict(self._pack_info)

    def pack_propagate(self, flag: Optional[bool] = None) -> Optional[bool]:
        """Get or set pack propagation flag.

        Propagation controls whether the parent widget resizes to fit
        its packed children. If False, the parent's size is fixed.

        Args:
            flag: Propagation flag to set. If None, returns current flag.

        Returns:
            Current propagation flag if flag is None, otherwise None.

        Example:
            >>> frame.pack_propagate(False)  # Fixed size frame
            >>> can_propagate = frame.pack_propagate()
        """
        if flag is None:
            return getattr(self, "_pack_propagate_flag", True)

        self._pack_propagate_flag = bool(flag)
        if hasattr(self, "_mark_layout_dirty"):
            self._mark_layout_dirty()
        return None

    def pack_slaves(self) -> list[Any]:
        """Return list of widgets packed in this widget.

        Returns:
            List of child widgets managed by pack geometry manager.

        Example:
            >>> frame = Frame(root)
            >>> button1 = Button(frame).pack()
            >>> button2 = Button(frame).pack()
            >>> slaves = frame.pack_slaves()
            >>> len(slaves)  # 2
        """
        # Return children that have pack_info
        if not hasattr(self, "_children"):
            return []

        return [
            child
            for child in self._children
            if hasattr(child, "_pack_info") and child._pack_info is not None
        ]


class Grid:
    """Grid geometry manager stub for Widget class.

    The Grid geometry manager arranges widgets in a table structure with
    rows and columns. Each widget occupies one or more cells, and can be
    configured to stick to sides of its cell or span multiple cells.

    This is a stub implementation that stores grid options but does not
    perform actual layout calculations. Layout calculation will be implemented
    in Phase 3.

    Grid options:
        row, column: Grid position (default 0).
        rowspan, columnspan: Number of cells to span (default 1).
        sticky: Sides to stick to (N, S, E, W combinations).
        padx, pady: External padding.
        ipadx, ipady: Internal padding.
        in_: Parent widget to grid into.

    Example:
        >>> label = Label(root, text="Name:")
        >>> label.grid(row=0, column=0, sticky='w')
        >>> entry = Entry(root)
        >>> entry.grid(row=0, column=1, sticky='ew')
    """

    def __init__(self) -> None:
        """Initialize Grid geometry manager stub.

        Sets up internal storage for grid options.
        """
        self._grid_info: Optional[dict[str, Any]] = None
        self._grid_removed: bool = False
        self._row_config: dict[int, dict[str, Any]] = {}
        self._col_config: dict[int, dict[str, Any]] = {}
        self._grid_layout_cache: Optional[Any] = None
        self._grid_anchor_value: str = "nw"

    def grid(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Grid widget with specified options.

        Stores grid configuration options and marks this widget as being
        managed by the grid geometry manager. If widget was previously
        managed by pack or place, those managers are forgotten.

        Args:
            cnf: Dictionary of grid options.
            **kw: Grid options as keyword arguments.

        Example:
            >>> widget.grid(row=0, column=1, sticky='nsew')
            >>> widget.grid({'row': 2, 'columnspan': 2})
        """
        # Merge cnf and kw
        options = dict(cnf, **kw)

        # Forget other geometry managers
        if hasattr(self, "_pack_info") and self._pack_info is not None:
            self._pack_info = None
        if hasattr(self, "_place_info") and self._place_info is not None:
            self._place_info = None

        # Initialize grid_info if needed
        if self._grid_info is None:
            self._grid_info = {
                "row": 0,
                "column": 0,
                "rowspan": 1,
                "columnspan": 1,
                "sticky": "",
                "padx": 0,
                "pady": 0,
                "ipadx": 0,
                "ipady": 0,
            }

        # Handle 'in' parameter (Python keyword workaround)
        if "in" in options:
            options["in_"] = options.pop("in")

        # Update grid options
        self._grid_info.update(options)
        self._grid_removed = False

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def grid_configure(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Alias for grid().

        See grid() for documentation.
        """
        self.grid(cnf, **kw)

    def grid_forget(self) -> None:
        """Remove widget from grid geometry manager.

        Unmaps the widget and removes grid configuration. The widget
        can be gridded again later with grid().

        Example:
            >>> widget.grid_forget()  # Hide widget
            >>> widget.grid()  # Show again with previous options
        """
        self._grid_info = None
        self._grid_removed = False

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def grid_remove(self) -> None:
        """Remove widget from grid but remember configuration.

        Unlike grid_forget(), this remembers the grid options so that
        grid() without arguments will restore the previous configuration.

        Example:
            >>> widget.grid(row=5, column=3)
            >>> widget.grid_remove()  # Hide but remember row=5, column=3
            >>> widget.grid()  # Restore at row=5, column=3
        """
        self._grid_removed = True

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def grid_info(self) -> dict[str, Any]:
        """Return grid configuration options.

        Returns:
            Dictionary of current grid options, or empty dict if not gridded.

        Example:
            >>> widget.grid(row=1, column=2)
            >>> info = widget.grid_info()
            >>> print(info['row'])  # 1
        """
        if self._grid_info is None or self._grid_removed:
            return {}
        return dict(self._grid_info)

    def grid_propagate(self, flag: Optional[bool] = None) -> Optional[bool]:
        """Get or set grid propagation flag.

        Propagation controls whether the parent widget resizes to fit
        its gridded children. If False, the parent's size is fixed.

        Args:
            flag: Propagation flag to set. If None, returns current flag.

        Returns:
            Current propagation flag if flag is None, otherwise None.

        Example:
            >>> frame.grid_propagate(False)  # Fixed size frame
            >>> can_propagate = frame.grid_propagate()
        """
        if flag is None:
            return getattr(self, "_grid_propagate_flag", True)

        self._grid_propagate_flag = bool(flag)
        if hasattr(self, "_mark_layout_dirty"):
            self._mark_layout_dirty()
        return None

    def grid_slaves(
        self,
        row: Optional[int] = None,
        column: Optional[int] = None,
    ) -> list[Any]:
        """Return list of widgets gridded in this widget.

        Args:
            row: If specified, only return widgets in this row.
            column: If specified, only return widgets in this column.

        Returns:
            List of child widgets managed by grid geometry manager.

        Example:
            >>> all_gridded = frame.grid_slaves()
            >>> row_0 = frame.grid_slaves(row=0)
            >>> col_1 = frame.grid_slaves(column=1)
        """
        if not hasattr(self, "_children"):
            return []

        slaves = [
            child
            for child in self._children
            if hasattr(child, "_grid_info")
            and child._grid_info is not None
            and not getattr(child, "_grid_removed", False)
        ]

        # Filter by row/column if specified
        if row is not None:
            slaves = [s for s in slaves if s._grid_info.get("row") == row]
        if column is not None:
            slaves = [s for s in slaves if s._grid_info.get("column") == column]

        return slaves

    def grid_bbox(
        self,
        column: Optional[int] = None,
        row: Optional[int] = None,
        col2: Optional[int] = None,
        row2: Optional[int] = None,
    ) -> Optional[tuple[int, int, int, int]]:
        """Get bounding box of grid cells.

        Returns the bounding box for the specified grid cell(s) in the
        form (x, y, width, height).

        Args:
            column: Starting column (default: all columns).
            row: Starting row (default: all rows).
            col2: Ending column (default: same as column).
            row2: Ending row (default: same as row).

        Returns:
            Tuple (x, y, width, height) or None if grid is empty.

        Example:
            >>> bbox = frame.grid_bbox(0, 0)  # Cell at row=0, col=0
            >>> bbox = frame.grid_bbox(0, 0, 2, 1)  # Range of cells
        """
        cache = getattr(self, "_grid_layout_cache", None)
        if cache is None:
            return None

        if not cache.col_widths or not cache.row_heights:
            return None

        num_cols = len(cache.col_widths)
        num_rows = len(cache.row_heights)

        if column is None:
            # Return entire grid bbox
            total_w = sum(cache.col_widths)
            total_h = sum(cache.row_heights)
            x = cache.col_positions[0] if cache.col_positions else 0
            y = cache.row_positions[0] if cache.row_positions else 0
            return (x, y, total_w, total_h)

        # Ensure valid indices
        if column < 0 or column >= num_cols:
            return None
        if row is None:
            row = 0
        if row < 0 or row >= num_rows:
            return None

        col2 = col2 if col2 is not None else column
        row2 = row2 if row2 is not None else row

        col2 = min(col2, num_cols - 1)
        row2 = min(row2, num_rows - 1)

        x = cache.col_positions[column]
        y = cache.row_positions[row]
        w = sum(cache.col_widths[column : col2 + 1])
        h = sum(cache.row_heights[row : row2 + 1])

        return (x, y, w, h)

    def grid_anchor(self, anchor: Optional[str] = None) -> Optional[str]:
        """Set or get the anchor point for the grid.

        When the grid is smaller than its allocated space, the anchor
        determines where the grid is positioned within that space.

        Args:
            anchor: Anchor position (n, s, e, w, ne, nw, se, sw, center).
                If None, returns the current anchor value.

        Returns:
            Current anchor value if querying, None if setting.

        Example:
            >>> frame.grid_anchor("center")  # Center grid in frame
            >>> current = frame.grid_anchor()  # Get current anchor
        """
        if anchor is None:
            return self._grid_anchor_value

        valid_anchors = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "center"}
        anchor_lower = anchor.lower()
        if anchor_lower not in valid_anchors:
            raise ValueError(f"Invalid anchor: {anchor}")

        self._grid_anchor_value = anchor_lower
        self._mark_layout_dirty()
        return None

    def grid_columnconfigure(
        self,
        index: int,
        cnf: dict[str, Any] = {},
        **kw: Any,
    ) -> Any:
        """Configure column properties.

        Sets properties for a grid column such as weight (for resizing),
        minimum size, and padding.

        Args:
            index: Column index to configure.
            cnf: Dictionary of column options.
            **kw: Column options as keyword arguments.

        Returns:
            Column configuration dict if no options given, otherwise None.

        Example:
            >>> frame.grid_columnconfigure(0, weight=1)  # Column 0 expands
            >>> frame.grid_columnconfigure(1, minsize=100)
        """
        # Ensure _col_config exists
        if not hasattr(self, "_col_config"):
            self._col_config = {}

        if not cnf and not kw:
            # Query mode - return current config or defaults
            config = self._col_config.get(index, {})
            return {
                "weight": config.get("weight", 0),
                "minsize": config.get("minsize", 0),
                "pad": config.get("pad", 0),
            }

        # Set mode - merge options
        options = dict(cnf, **kw)
        if index not in self._col_config:
            self._col_config[index] = {}
        self._col_config[index].update(options)

        # Mark layout dirty
        if hasattr(self, "_mark_layout_dirty"):
            self._mark_layout_dirty()

        return None

    def grid_rowconfigure(
        self,
        index: int,
        cnf: dict[str, Any] = {},
        **kw: Any,
    ) -> Any:
        """Configure row properties.

        Sets properties for a grid row such as weight (for resizing),
        minimum size, and padding.

        Args:
            index: Row index to configure.
            cnf: Dictionary of row options.
            **kw: Row options as keyword arguments.

        Returns:
            Row configuration dict if no options given, otherwise None.

        Example:
            >>> frame.grid_rowconfigure(0, weight=1)  # Row 0 expands
            >>> frame.grid_rowconfigure(1, minsize=50)
        """
        # Ensure _row_config exists
        if not hasattr(self, "_row_config"):
            self._row_config = {}

        if not cnf and not kw:
            # Query mode - return current config or defaults
            config = self._row_config.get(index, {})
            return {
                "weight": config.get("weight", 0),
                "minsize": config.get("minsize", 0),
                "pad": config.get("pad", 0),
            }

        # Set mode - merge options
        options = dict(cnf, **kw)
        if index not in self._row_config:
            self._row_config[index] = {}
        self._row_config[index].update(options)

        # Mark layout dirty
        if hasattr(self, "_mark_layout_dirty"):
            self._mark_layout_dirty()

        return None

    def grid_location(self, x: int, y: int) -> tuple[int, int]:
        """Get grid cell at specified coordinates.

        Returns the (column, row) of the grid cell at the given
        coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Tuple (column, row) of grid cell at coordinates.
            Returns (-1, -1) if coordinates are outside the grid.

        Example:
            >>> col, row = frame.grid_location(50, 30)
        """
        cache = getattr(self, "_grid_layout_cache", None)
        if cache is None:
            return (-1, -1)

        if not cache.col_positions or not cache.row_positions:
            return (-1, -1)

        # Find column
        col = -1
        for i, pos in enumerate(cache.col_positions):
            if i < len(cache.col_widths):
                if pos <= x < pos + cache.col_widths[i]:
                    col = i
                    break

        # Find row
        row = -1
        for i, pos in enumerate(cache.row_positions):
            if i < len(cache.row_heights):
                if pos <= y < pos + cache.row_heights[i]:
                    row = i
                    break

        return (col, row)

    def grid_size(self) -> tuple[int, int]:
        """Get grid dimensions.

        Returns the size of the grid in (columns, rows). This is the
        maximum column and row occupied by any widget.

        Returns:
            Tuple (columns, rows) of grid size.

        Example:
            >>> cols, rows = frame.grid_size()
            >>> print(f"Grid is {cols}x{rows}")
        """
        # Stub: will be implemented in Phase 3
        if not hasattr(self, "_children"):
            return (0, 0)

        slaves = self.grid_slaves()
        if not slaves:
            return (0, 0)

        max_col = max(
            (s._grid_info.get("column", 0) + s._grid_info.get("columnspan", 1) - 1)
            for s in slaves
        )
        max_row = max(
            (s._grid_info.get("row", 0) + s._grid_info.get("rowspan", 1) - 1)
            for s in slaves
        )

        return (max_col + 1, max_row + 1)


class Place:
    """Place geometry manager stub for Widget class.

    The Place geometry manager positions widgets at absolute or relative
    coordinates within their parent. This provides pixel-perfect control
    over widget placement.

    This is a stub implementation that stores place options but does not
    perform actual layout calculations. Layout calculation will be implemented
    in Phase 3.

    Place options:
        x, y: Absolute position in pixels.
        relx, rely: Relative position (0.0-1.0).
        width, height: Absolute size in pixels.
        relwidth, relheight: Relative size (0.0-1.0).
        anchor: Anchor point for positioning (N, S, E, W, NE, NW, SE, SW, CENTER).
        in_: Parent widget to place into.
        bordermode: INSIDE or OUTSIDE (positioning relative to border).

    Example:
        >>> button = Button(root, text="Click")
        >>> button.place(relx=0.5, rely=0.5, anchor='center')  # Center of parent
        >>> label = Label(root, text="Info")
        >>> label.place(x=10, y=20, width=100, height=30)  # Absolute positioning
    """

    def __init__(self) -> None:
        """Initialize Place geometry manager stub.

        Sets up internal storage for place options.
        """
        self._place_info: Optional[dict[str, Any]] = None

    def place(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Place widget with specified options.

        Stores place configuration options and marks this widget as being
        managed by the place geometry manager. If widget was previously
        managed by pack or grid, those managers are forgotten.

        Args:
            cnf: Dictionary of place options.
            **kw: Place options as keyword arguments.

        Example:
            >>> widget.place(x=10, y=20)
            >>> widget.place(relx=0.5, rely=0.5, anchor='center')
        """
        # Merge cnf and kw
        options = dict(cnf, **kw)

        # Forget other geometry managers
        if hasattr(self, "_pack_info") and self._pack_info is not None:
            self._pack_info = None
        if hasattr(self, "_grid_info") and self._grid_info is not None:
            self._grid_info = None

        # Initialize place_info if needed
        if self._place_info is None:
            self._place_info = {
                "x": 0,
                "y": 0,
                "relx": 0.0,
                "rely": 0.0,
                "width": None,
                "height": None,
                "relwidth": None,
                "relheight": None,
                "anchor": "nw",
                "bordermode": "inside",
            }

        # Handle 'in' parameter (Python keyword workaround)
        if "in" in options:
            options["in_"] = options.pop("in")

        # Update place options
        self._place_info.update(options)

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def place_configure(self, cnf: dict[str, Any] = {}, **kw: Any) -> None:
        """Alias for place().

        See place() for documentation.
        """
        self.place(cnf, **kw)

    def place_forget(self) -> None:
        """Remove widget from place geometry manager.

        Unmaps the widget and removes place configuration. The widget
        can be placed again later with place().

        Example:
            >>> widget.place_forget()  # Hide widget
            >>> widget.place()  # Show again with previous options
        """
        self._place_info = None

        # Mark parent as needing layout
        if hasattr(self, "master") and self.master is not None:
            if hasattr(self.master, "_mark_layout_dirty"):
                self.master._mark_layout_dirty()

    def place_info(self) -> dict[str, Any]:
        """Return place configuration options.

        Returns:
            Dictionary of current place options, or empty dict if not placed.

        Example:
            >>> widget.place(x=10, y=20)
            >>> info = widget.place_info()
            >>> print(info['x'])  # 10
        """
        if self._place_info is None:
            return {}
        return dict(self._place_info)

    def place_slaves(self) -> list[Any]:
        """Return list of widgets placed in this widget.

        Returns:
            List of child widgets managed by place geometry manager.

        Example:
            >>> frame = Frame(root)
            >>> button1 = Button(frame)
            >>> button1.place(x=0, y=0)
            >>> button2 = Button(frame)
            >>> button2.place(x=50, y=0)
            >>> slaves = frame.place_slaves()
            >>> len(slaves)  # 2
        """
        # Return children that have place_info
        if not hasattr(self, "_children"):
            return []

        return [
            child
            for child in self._children
            if hasattr(child, "_place_info") and child._place_info is not None
        ]


class Widget(BaseWidget, Pack, Place, Grid):
    """Base widget class combining BaseWidget with geometry managers.

    Widget is the fundamental base class for all TkCurses widgets (Button,
    Label, Frame, etc.). It combines BaseWidget (which handles curses window
    management and widget hierarchy) with the three geometry managers
    (Pack, Place, Grid) through multiple inheritance.

    This class ensures that only one geometry manager is active at a time.
    When a different geometry manager is used, the previous one is
    automatically forgotten.

    Widget inherits from:
        - BaseWidget: Widget lifecycle, curses window management, hierarchy
        - Pack: Pack geometry manager methods (pack, pack_forget, etc.)
        - Place: Place geometry manager methods (place, place_forget, etc.)
        - Grid: Grid geometry manager methods (grid, grid_forget, etc.)

    This class is not typically instantiated directly but is used as a base
    class for concrete widgets like Button, Label, Entry, etc.

    Example:
        >>> # Widget is used as a base class for actual widgets
        >>> class MyWidget(Widget):
        ...     def __init__(self, master=None, **kw):
        ...         super().__init__(master, **kw)
        ...         self._config.update(kw)
        ...
        ...     def _draw(self):
        ...         # Custom drawing code
        ...         pass
        >>>
        >>> # Use geometry managers
        >>> widget = MyWidget(root)
        >>> widget.pack(side='left', fill='x')  # Use pack
        >>> widget.grid(row=0, column=1)  # Switches to grid, forgets pack
        >>> widget.place(x=10, y=20)  # Switches to place, forgets grid

    Note:
        Actual layout calculation is not implemented in this phase. These are
        stub implementations that store geometry options for later use by the
        layout engine in Phase 3.
    """

    def __init__(self, master: Optional[BaseWidget] = None, **kw: Any) -> None:
        """Initialize Widget with geometry manager support.

        Creates a widget with the specified parent and configuration options.
        Initializes all three geometry managers (pack, place, grid) in their
        initial inactive state.

        Args:
            master: Parent widget. If None, this is a top-level widget.
            **kw: Configuration options for the widget. See BaseWidget
                for common options.

        Example:
            >>> widget = Widget(root, width=40, height=10)
        """
        # Initialize base widget first
        BaseWidget.__init__(self, master, **kw)

        # Initialize geometry managers
        Pack.__init__(self)
        Place.__init__(self)
        Grid.__init__(self)


class Tk(Misc, Wm):
    """Main application window and event loop for TkCurses.

    Tk represents the root window of a TkCurses application. It manages the
    terminal screen, initializes the curses environment, handles the event loop,
    and coordinates all widget rendering and input handling.

    This is the primary entry point for TkCurses applications. There should be
    exactly one Tk instance per application. Creating a second Tk instance will
    raise a TkCursesError.

    Key responsibilities:
        - Initialize and cleanup the curses screen (via CursesScreen)
        - Manage the main event loop (keyboard, mouse, timers, resize)
        - Coordinate event dispatching to widgets
        - Handle application-level protocols (quit, cleanup, etc.)
        - Provide the root window for widget hierarchy

    Example:
        >>> import tkcurses as tk
        >>> root = tk.Tk()
        >>> root.title("My TkCurses App")
        >>> label = tk.Label(root, text="Hello, Terminal!")
        >>> label.pack()
        >>> root.mainloop()

    Attributes:
        _screen: The CursesScreen singleton managing terminal state.
        _dispatcher: The CursesDispatcher for thread-safe curses calls.
        _input_handler: The InputHandler for keyboard/mouse events.
        _panel_stack: The PanelStack managing window z-order.
        _color_manager: The ColorManager for color pair management.
        _quit_flag: Flag indicating whether to exit the event loop.
        _destroyed: Flag indicating whether the window has been destroyed.
    """

    _instance: Optional[Tk] = None
    _instance_exists: bool = False

    def __init__(
        self,
        screenName: Optional[str] = None,
        baseName: Optional[str] = None,
        className: str = 'Tk',
        useTk: bool = True,
        sync: bool = False,
        use: Optional[str] = None,
    ) -> None:
        """Initialize the Tk root window and curses environment.

        Creates the main application window and initializes all necessary
        TkCurses subsystems including screen, input handling, panels, and
        color management.

        Args:
            screenName: X11 display name (ignored in TkCurses, for compatibility).
            baseName: Base name for Tk instance (ignored, for compatibility).
            className: Widget class name. Default: 'Tk'.
            useTk: Whether to use Tk (ignored, for compatibility).
            sync: Whether to use synchronous mode (ignored, for compatibility).
            use: Window ID to embed in (ignored, for compatibility).

        Raises:
            RuntimeError: If a Tk instance already exists.

        Example:
            >>> root = Tk()
            >>> root.title("My Application")
            >>> root.mainloop()
        """
        # Enforce singleton pattern
        if Tk._instance_exists:
            raise RuntimeError(
                "A Tk instance already exists. Only one Tk instance "
                "is allowed per application. Use Toplevel for additional windows."
            )

        # Initialize base classes
        Misc.__init__(self)
        Wm.__init__(self)

        # Mark instance as existing
        Tk._instance = self
        Tk._instance_exists = True

        # Store class name
        self._class_name = className

        # Initialize curses screen
        self._screen = CursesScreen()
        self._screen.initialize()

        # Set default geometry to terminal size
        self._width = self._screen.width
        self._height = self._screen.height
        self._x = 0
        self._y = 0

        # Initialize dispatcher
        self._dispatcher = CursesDispatcher.get()

        # Load configuration
        self._config = TkCursesConfig.load()

        # Initialize input handler
        self._input_handler = InputHandler(self._screen.stdscr, self._config)

        # Initialize panel stack
        self._panel_stack = PanelStack.get()

        # Initialize color manager
        self._color_manager = ColorManager()

        # Create a panel for the root window
        if self._screen.stdscr:
            self._panel = self._panel_stack.create_panel(self._screen.stdscr)
            self._panel.bottom()  # Root window stays at bottom

        # Event loop control flags
        self._quit_flag = False
        self._destroyed = False

        # Layout management
        self._children: list[Any] = []
        self._layout_dirty: bool = True
        self._has_border: bool = False
        self._pack_propagate_flag: bool = True
        self._grid_propagate_flag: bool = True
        self._row_config: dict[int, dict[str, Any]] = {}
        self._col_config: dict[int, dict[str, Any]] = {}
        self._grid_layout_cache: Optional[Any] = None

        # Set up signal handlers for terminal resize
        self._setup_resize_handler()

    def _setup_resize_handler(self) -> None:
        """Set up signal handler for terminal resize events.

        Registers a SIGWINCH handler to detect terminal resize and update
        the curses screen accordingly.
        """
        def handle_resize(signum: int, frame: Any) -> None:
            """Handle SIGWINCH signal (terminal resize)."""
            if not self._destroyed:
                # Update curses dimensions
                curses.update_lines_cols()
                self._width = curses.COLS
                self._height = curses.LINES

                # Resize the screen
                self._screen.resize_term(curses.LINES, curses.COLS)

                # Mark all widgets as needing layout recalculation
                LayoutManager.mark_all_dirty(self)

                # Generate a resize event for widgets to handle
                resize_event = ResizeEvent(
                    width=curses.COLS,
                    height=curses.LINES,
                )
                self._dispatch_event(resize_event)

        # Register the signal handler
        try:
            signal.signal(signal.SIGWINCH, handle_resize)
        except (AttributeError, ValueError):
            # SIGWINCH not available on all platforms (e.g., Windows)
            pass

    def _dispatch_event(self, event: Event | list[Event] | None) -> None:
        """Dispatch an event to the appropriate widget.

        Routes events through the binding system to find and invoke
        registered event handlers.

        Args:
            event: Event to dispatch, or list of events, or None.
        """
        if event is None:
            return

        # Handle list of events
        if isinstance(event, list):
            for evt in event:
                self._dispatch_event(evt)
            return

        # Determine event sequence string for binding lookup
        sequence = self._event_to_sequence(event)
        if not sequence:
            return

        # Try widget-specific bindings first
        if hasattr(event, 'widget') and event.widget:
            if self._invoke_bindings(event.widget, sequence, event):
                return

        # Try class bindings
        if hasattr(event, 'widget') and event.widget:
            class_name = event.widget.__class__.__name__
            if class_name in Misc._class_bindings:
                if sequence in Misc._class_bindings[class_name]:
                    for _, func in Misc._class_bindings[class_name][sequence]:
                        try:
                            func(event)
                        except Exception as e:
                            print(f"Error in class binding: {e}")
                    return

        # Try global bindings
        if sequence in Misc._global_bindings:
            for _, func in Misc._global_bindings[sequence]:
                try:
                    func(event)
                except Exception as e:
                    print(f"Error in global binding: {e}")

    def _event_to_sequence(self, event: Event) -> Optional[str]:
        """Convert an Event object to a binding sequence string.

        Args:
            event: Event to convert.

        Returns:
            Event sequence string (e.g., "<Button-1>", "<Key-a>"), or None.
        """
        if isinstance(event, KeyEvent):
            # Format: <Key-keysym> or <Control-keysym>, etc.
            modifiers = []
            if event.modifiers & 0x01:  # MOD_SHIFT
                modifiers.append("Shift")
            if event.modifiers & 0x02:  # MOD_CTRL
                modifiers.append("Control")
            if event.modifiers & 0x04:  # MOD_ALT
                modifiers.append("Alt")

            if modifiers:
                return f"<{'-'.join(modifiers)}-{event.keysym}>"
            else:
                return f"<Key-{event.keysym}>"

        elif isinstance(event, MouseEvent):
            # Format: <Button-1>, <B1-Motion>, <ButtonRelease-1>, etc.
            if event.state == 'pressed':
                return f"<Button-{event.button}>"
            elif event.state == 'released':
                return f"<ButtonRelease-{event.button}>"
            elif event.state == 'drag':
                return f"<B{event.button}-Motion>"
            elif event.state == 'double':
                return f"<Double-Button-{event.button}>"
            elif event.state == 'triple':
                return f"<Triple-Button-{event.button}>"
            elif event.state == 'motion':
                return "<Motion>"

        elif isinstance(event, ResizeEvent):
            return "<Configure>"

        return None

    def _invoke_bindings(
        self,
        widget: Misc,
        sequence: str,
        event: Event,
    ) -> bool:
        """Invoke bindings for a specific widget and sequence.

        Args:
            widget: Widget to invoke bindings on.
            sequence: Event sequence string.
            event: Event object to pass to callbacks.

        Returns:
            True if any bindings were invoked, False otherwise.
        """
        if sequence not in widget._bindings:
            return False

        for _, func in widget._bindings[sequence]:
            try:
                func(event)
            except Exception as e:
                print(f"Error in widget binding: {e}")

        return True

    def mainloop(self, n: int = 0) -> None:
        """Run the main event loop.

        Processes keyboard/mouse events, timer callbacks, and screen updates
        until quit() is called or the window is destroyed. This is the primary
        method that keeps a TkCurses application running.

        The event loop performs these operations in sequence:
            1. Process queued after() callbacks
            2. Process any dispatcher queue items (from other threads)
            3. Poll for input events with timeout
            4. Dispatch events to appropriate widgets
            5. Update panel display
            6. Handle Ctrl+C gracefully

        Args:
            n: Number of events to process before returning. If 0 (default),
                runs indefinitely until quit() is called.

        Example:
            >>> root = Tk()
            >>> root.title("Event Loop Example")
            >>> root.mainloop()  # Runs until quit() is called
            >>>
            >>> # Process exactly 10 events then return
            >>> root.mainloop(n=10)

        Note:
            This method blocks until the event loop exits. Any code after
            mainloop() will not execute until the application quits.
        """
        events_processed = 0
        self._quit_flag = False

        try:
            while not self._quit_flag and not self._destroyed:
                # Process pending after() callbacks
                Misc._process_after_queue()

                # Process dispatcher queue (calls from other threads)
                self._dispatcher.process_queue()

                # Check for input with timeout
                if self._input_handler.wait_for_input(
                    timeout_ms=self._config.input.poll_timeout
                ):
                    # Get the event
                    event = self._input_handler.get_event()

                    # Dispatch to appropriate widget
                    if event is not None:
                        self._dispatch_event(event)
                        events_processed += 1

                        # If n > 0, exit after processing n events
                        if n > 0 and events_processed >= n:
                            break

                # Perform layout calculation if needed
                if getattr(self, "_layout_dirty", False):
                    self._do_layout()

                # Update display
                try:
                    self._panel_stack.update()
                    if self._screen.stdscr:
                        self._screen.stdscr.refresh()
                except curses.error:
                    # Ignore curses errors during refresh (e.g., terminal too small)
                    pass

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            self.quit()

    def quit(self) -> None:
        """Exit the main event loop.

        Sets a flag that causes mainloop() to exit on its next iteration.
        Does not immediately exit or destroy the window - it just signals
        that the event loop should stop.

        After quit() is called, you can still interact with the window
        or call destroy() to clean up resources.

        Example:
            >>> root = Tk()
            >>> # Bind Ctrl+Q to quit
            >>> root.bind_all("<Control-q>", lambda e: root.quit())
            >>> root.mainloop()
            >>> # After quit(), we're here
            >>> root.destroy()  # Clean up
        """
        self._quit_flag = True

    def destroy(self) -> None:
        """Destroy the root window and cleanup curses.

        Performs complete cleanup of all TkCurses resources:
            - Invokes WM_DELETE_WINDOW protocol if registered
            - Cleans up input handler
            - Cleans up curses screen (restores terminal)
            - Clears singleton instance flag
            - Marks window as destroyed

        After calling destroy(), the Tk instance cannot be used anymore.
        This method should be called before the application exits to ensure
        the terminal is properly restored.

        Example:
            >>> root = Tk()
            >>> # ... use the application ...
            >>> root.destroy()  # Clean up before exit
        """
        if self._destroyed:
            return

        # Invoke WM_DELETE_WINDOW protocol if registered
        if "WM_DELETE_WINDOW" in self._protocols:
            try:
                self._protocols["WM_DELETE_WINDOW"]()
            except Exception as e:
                print(f"Error in WM_DELETE_WINDOW protocol: {e}")

        # Set flags
        self._destroyed = True
        self._quit_flag = True

        # Cleanup input handler
        if hasattr(self, '_input_handler'):
            self._input_handler.cleanup()

        # Cleanup curses screen
        if hasattr(self, '_screen'):
            self._screen.cleanup()

        # Clear singleton flag
        Tk._instance = None
        Tk._instance_exists = False

    @property
    def tk(self) -> Tk:
        """Return self for tkinter compatibility.

        In tkinter, widgets have a .tk attribute that references the Tk
        instance. For the Tk class itself, this just returns self.

        Returns:
            This Tk instance.

        Example:
            >>> root = Tk()
            >>> assert root.tk is root
        """
        return self

    def winfo_toplevel(self) -> Tk:
        """Return the top-level window (self for Tk).

        Returns:
            This Tk instance.

        Example:
            >>> root = Tk()
            >>> assert root.winfo_toplevel() is root
        """
        return self

    def winfo_screenwidth(self) -> int:
        """Get the terminal width in columns.

        Returns:
            Terminal width in columns.

        Example:
            >>> root = Tk()
            >>> print(f"Terminal is {root.winfo_screenwidth()} columns wide")
        """
        return self._screen.width

    def winfo_screenheight(self) -> int:
        """Get the terminal height in rows.

        Returns:
            Terminal height in rows.

        Example:
            >>> root = Tk()
            >>> print(f"Terminal is {root.winfo_screenheight()} rows tall")
        """
        return self._screen.height

    def bell(self) -> None:
        """Ring the terminal bell.

        Produces an audible beep or visual bell (depending on terminal
        settings) to alert the user.

        Example:
            >>> root = Tk()
            >>> root.bell()  # Beep!
        """
        try:
            self._dispatcher.call(curses.beep)
        except curses.error:
            # Bell not available on this terminal
            pass

    # =========================================================================
    # Layout Methods
    # =========================================================================

    def _add_child(self, widget: Any) -> None:
        """Add a child widget to this window's children list."""
        if widget not in self._children:
            self._children.append(widget)

    def _remove_child(self, widget: Any) -> None:
        """Remove a child widget from this window's children list."""
        if widget in self._children:
            self._children.remove(widget)

    def _do_layout(self) -> None:
        """Perform layout calculation for this window and descendants."""
        LayoutManager.do_layout(self)

    def _mark_layout_dirty(self) -> None:
        """Mark this window as needing layout recalculation."""
        self._layout_dirty = True

    def _get_content_bounds(self) -> Rect:
        """Get the area available for child widgets."""
        return Rect(0, 0, self._width, self._height)

    def _get_natural_size(self) -> Size:
        """Get the window's natural size."""
        return Size(self._width, self._height)

    def pack_slaves(self) -> list[Any]:
        """Return list of widgets packed in this window."""
        return [
            child
            for child in self._children
            if hasattr(child, "_pack_info") and child._pack_info is not None
        ]

    def grid_slaves(self, row: Optional[int] = None, column: Optional[int] = None) -> list[Any]:
        """Return list of widgets gridded in this window."""
        slaves = [
            child
            for child in self._children
            if hasattr(child, "_grid_info")
            and child._grid_info is not None
            and not getattr(child, "_grid_removed", False)
        ]
        if row is not None:
            slaves = [s for s in slaves if s._grid_info.get("row") == row]
        if column is not None:
            slaves = [s for s in slaves if s._grid_info.get("column") == column]
        return slaves

    def grid_size(self) -> tuple[int, int]:
        """Get grid dimensions."""
        slaves = self.grid_slaves()
        if not slaves:
            return (0, 0)
        max_col = max(
            (s._grid_info.get("column", 0) + s._grid_info.get("columnspan", 1) - 1)
            for s in slaves
        )
        max_row = max(
            (s._grid_info.get("row", 0) + s._grid_info.get("rowspan", 1) - 1)
            for s in slaves
        )
        return (max_col + 1, max_row + 1)

    def place_slaves(self) -> list[Any]:
        """Return list of widgets placed in this window."""
        return [
            child
            for child in self._children
            if hasattr(child, "_place_info") and child._place_info is not None
        ]

    @classmethod
    def _reset_singleton(cls) -> None:
        """Reset the singleton state (for testing only).

        Warning:
            This method is intended for testing purposes only. Using it in
            production code may lead to unexpected behavior.
        """
        cls._instance = None
        cls._instance_exists = False


class Toplevel(Misc, Wm):
    """Additional window for TkCurses applications.

    Toplevel represents a secondary window in a TkCurses application.
    Unlike Tk, multiple Toplevel windows can exist simultaneously.
    Each Toplevel has its own curses window and panel for independent
    positioning and z-ordering.

    A Tk instance must exist before creating a Toplevel. The Toplevel
    shares the event loop and screen management with the root Tk window
    but maintains its own geometry, title, and state.

    Key features:
        - Independent window positioning and sizing
        - Own title and window manager state
        - Stacks above the root window by default
        - Can be shown, hidden, or destroyed independently

    Example:
        >>> import tkcurses as tk
        >>> root = tk.Tk()
        >>> root.title("Main Window")
        >>>
        >>> # Create a secondary window
        >>> top = tk.Toplevel(root)
        >>> top.title("Secondary Window")
        >>> top.geometry("40x10+5+5")
        >>>
        >>> label = tk.Label(top, text="This is a popup!")
        >>> label.pack()
        >>>
        >>> root.mainloop()

    Attributes:
        master: The parent window (typically the Tk root).
        _window: The curses window for this Toplevel.
        _panel: The panel managing this window's z-order.
    """

    def __init__(
        self,
        master: Optional[Tk | Toplevel] = None,
        className: str = 'Toplevel',
        **kw: Any,
    ) -> None:
        """Initialize a new Toplevel window.

        Creates a new curses window and panel for the Toplevel.
        The window is created with a default size and positioned
        at (0, 0), but can be configured using geometry().

        Args:
            master: Parent window. If None, uses the Tk root.
                Must be either Tk or another Toplevel.
            className: Widget class name. Default: 'Toplevel'.
            **kw: Additional configuration options (for tkinter compatibility).

        Raises:
            RuntimeError: If no Tk instance exists.

        Example:
            >>> root = Tk()
            >>> top = Toplevel(root)
            >>> top.title("My Toplevel")
            >>> top.geometry("30x10+5+3")
        """
        # Find the Tk root
        if master is None:
            if Tk._instance is None:
                raise RuntimeError(
                    "Cannot create Toplevel without a Tk instance. "
                    "Create a Tk() first."
                )
            self._master = Tk._instance
        else:
            self._master = master

        # Get the root Tk instance
        if isinstance(self._master, Tk):
            self._tk_root = self._master
        else:
            # Navigate up the hierarchy to find Tk
            self._tk_root = self._master._tk_root

        # Initialize base classes
        Misc.__init__(self)
        Wm.__init__(self)

        # Store class name
        self._class_name = className

        # Get screen dimensions from the root
        self._screen = self._tk_root._screen

        # Default size: slightly smaller than terminal
        default_width = max(20, self._screen.width - 10)
        default_height = max(10, self._screen.height - 4)
        default_x = 2
        default_y = 2

        # Store geometry
        self._width = default_width
        self._height = default_height
        self._x = default_x
        self._y = default_y

        # Create curses window
        self._dispatcher = self._tk_root._dispatcher
        try:
            self._window = self._dispatcher.call(
                curses.newwin,
                self._height,
                self._width,
                self._y,
                self._x,
            )
        except curses.error as e:
            raise RuntimeError(
                f"Failed to create Toplevel window ({self._width}x{self._height} "
                f"at {self._x},{self._y}): {e}"
            ) from e

        # Create panel for z-ordering
        self._panel_stack = self._tk_root._panel_stack
        self._panel = self._panel_stack.create_panel(self._window)
        self._panel.top()  # Toplevel windows stack on top

        # Reference to color manager
        self._color_manager = self._tk_root._color_manager

        # Window state flags
        self._destroyed = False

        # Store reference in master's children for hierarchy tracking
        if not hasattr(self._master, '_toplevels'):
            self._master._toplevels = []
        self._master._toplevels.append(self)

        # Apply any keyword configuration
        if kw:
            self.configure(**kw)

        # Layout management - child widgets
        self._children: list[BaseWidget] = []

        # Layout flags
        self._layout_dirty: bool = True
        self._has_border: bool = False
        self._pack_propagate_flag: bool = True
        self._grid_propagate_flag: bool = True

        # Grid row/column configuration
        self._row_config: dict[int, dict[str, Any]] = {}
        self._col_config: dict[int, dict[str, Any]] = {}
        self._grid_layout_cache: GridLayoutCache | None = None

    @property
    def tk(self) -> Tk:
        """Return the Tk root instance.

        Provides access to the root Tk instance for this Toplevel,
        which manages the screen and event loop.

        Returns:
            The Tk root instance.

        Example:
            >>> top = Toplevel(root)
            >>> assert top.tk is root
        """
        return self._tk_root

    @property
    def master(self) -> Tk | Toplevel:
        """Return the parent window.

        Returns:
            The parent window (Tk or Toplevel).
        """
        return self._master

    def winfo_toplevel(self) -> Toplevel:
        """Return self as the top-level window.

        For Toplevel widgets, this returns itself.

        Returns:
            This Toplevel instance.

        Example:
            >>> top = Toplevel(root)
            >>> assert top.winfo_toplevel() is top
        """
        return self

    def winfo_screenwidth(self) -> int:
        """Get the terminal width in columns.

        Returns:
            Terminal width in columns.
        """
        return self._screen.width

    def winfo_screenheight(self) -> int:
        """Get the terminal height in rows.

        Returns:
            Terminal height in rows.
        """
        return self._screen.height

    def winfo_width(self) -> int:
        """Get the width of this Toplevel in columns.

        Returns:
            Width of this window in columns.
        """
        return self._width

    def winfo_height(self) -> int:
        """Get the height of this Toplevel in rows.

        Returns:
            Height of this window in rows.
        """
        return self._height

    def winfo_x(self) -> int:
        """Get the x position of this Toplevel.

        Returns:
            X (column) position of this window.
        """
        return self._x

    def winfo_y(self) -> int:
        """Get the y position of this Toplevel.

        Returns:
            Y (row) position of this window.
        """
        return self._y

    def geometry(self, newGeometry: Optional[str] = None) -> str:
        """Set or query window geometry.

        Overrides the Wm.geometry method to actually resize and move
        the curses window when the geometry is changed.

        Args:
            newGeometry: Geometry string in format "WxH+X+Y" or "WxH".
                If None, returns current geometry.

        Returns:
            Current geometry string.

        Raises:
            ValueError: If the geometry string format is invalid.

        Example:
            >>> top = Toplevel(root)
            >>> top.geometry("40x15+10+5")
            >>> print(top.geometry())  # "40x15+10+5"
        """
        if newGeometry is None:
            # Query mode
            return f"{self._width}x{self._height}+{self._x}+{self._y}"

        # Store old values BEFORE parsing (to detect changes)
        old_width, old_height = self._width, self._height
        old_x, old_y = self._x, self._y

        # Parse geometry string using inherited method
        # This updates self._width, self._height, self._x, self._y
        result = Wm.wm_geometry(self, newGeometry)

        # Check if size or position changed
        size_changed = (old_width != self._width or old_height != self._height)
        position_changed = (old_x != self._x or old_y != self._y)

        if size_changed:
            # Need to resize the window
            try:
                self._dispatcher.call(
                    self._window.resize,
                    self._height,
                    self._width,
                )
            except curses.error:
                # If resize fails, try recreating the window
                try:
                    new_window = self._dispatcher.call(
                        curses.newwin,
                        self._height,
                        self._width,
                        self._y,
                        self._x,
                    )
                    self._panel.replace(new_window)
                    self._window = new_window
                except curses.error as e:
                    # Restore old dimensions on failure
                    self._width, self._height = old_width, old_height
                    self._x, self._y = old_x, old_y
                    raise ValueError(f"Failed to resize Toplevel: {e}") from e

        if position_changed and not size_changed:
            # Just move the panel
            try:
                self._panel.move(self._y, self._x)
            except Exception as e:
                self._x, self._y = old_x, old_y
                raise ValueError(f"Failed to move Toplevel: {e}") from e
        elif position_changed and size_changed:
            # Already moved via window recreation, or need to move
            try:
                self._panel.move(self._y, self._x)
            except Exception:
                pass  # Already at correct position from newwin

        # Update panel stack to reflect changes
        if size_changed or position_changed:
            self._panel_stack.update()

        return result

    def lift(self, aboveThis: Optional[Toplevel] = None) -> None:
        """Raise this window above others in the stacking order.

        Moves this Toplevel to the top of the window stack, making it
        appear above all other windows.

        Args:
            aboveThis: If specified, raise this window just above the
                given window (currently ignored, raises to top).

        Example:
            >>> top1 = Toplevel(root)
            >>> top2 = Toplevel(root)
            >>> top1.lift()  # top1 now above top2
        """
        if not self._destroyed:
            self._panel.top()

    def lower(self, belowThis: Optional[Toplevel] = None) -> None:
        """Lower this window below others in the stacking order.

        Moves this Toplevel to the bottom of the window stack (but still
        above the root Tk window).

        Args:
            belowThis: If specified, lower this window just below the
                given window (currently ignored, lowers to bottom).

        Example:
            >>> top1 = Toplevel(root)
            >>> top2 = Toplevel(root)
            >>> top2.lower()  # top2 now below top1
        """
        if not self._destroyed:
            self._panel.bottom()

    def transient(self, master: Optional[Tk | Toplevel] = None) -> Optional[Tk | Toplevel]:
        """Set or query the transient master for this window.

        Transient windows are typically used for dialogs and stay above
        their master window. In TkCurses, this is primarily for
        tkinter compatibility.

        Args:
            master: The master window for this transient. If None,
                returns the current transient master.

        Returns:
            The current transient master, or None.

        Example:
            >>> dialog = Toplevel(root)
            >>> dialog.transient(root)
        """
        if master is None:
            return getattr(self, '_transient_master', None)
        self._transient_master = master
        # Ensure transient windows stay on top
        self._panel.top()
        return None

    def grab_set(self) -> None:
        """Set a grab on this window.

        When a grab is set, all input events are directed to this window.
        This is commonly used for modal dialogs. Currently a stub for
        tkinter compatibility.

        Example:
            >>> dialog = Toplevel(root)
            >>> dialog.grab_set()  # Make dialog modal
        """
        # Stub: would need InputHandler integration for modal behavior
        pass

    def grab_release(self) -> None:
        """Release the grab on this window.

        Releases a grab previously set with grab_set(). Currently a stub
        for tkinter compatibility.

        Example:
            >>> dialog.grab_release()
        """
        pass

    def focus_set(self) -> None:
        """Set focus to this Toplevel window.

        Raises this window and sets keyboard focus to it.

        Example:
            >>> top.focus_set()
        """
        # Raise the window
        self.lift()
        # Set focus via Misc
        Misc.focus_set(self)

    def bell(self) -> None:
        """Ring the terminal bell.

        Produces an audible beep or visual bell.

        Example:
            >>> top.bell()
        """
        try:
            self._dispatcher.call(curses.beep)
        except curses.error:
            pass

    def destroy(self) -> None:
        """Destroy this Toplevel window.

        Removes the panel, cleans up the curses window, and removes
        this Toplevel from its parent's children list.

        After calling destroy(), the Toplevel cannot be used anymore.

        Example:
            >>> top = Toplevel(root)
            >>> # ... use the window ...
            >>> top.destroy()
        """
        if self._destroyed:
            return

        # Invoke WM_DELETE_WINDOW protocol if registered
        if "WM_DELETE_WINDOW" in self._protocols:
            try:
                self._protocols["WM_DELETE_WINDOW"]()
            except Exception as e:
                print(f"Error in WM_DELETE_WINDOW protocol: {e}")

        # Mark as destroyed
        self._destroyed = True

        # Remove panel from stack
        try:
            self._panel_stack.remove_panel(self._panel)
        except Exception:
            pass  # Panel may already be removed

        # Delete the curses window
        try:
            self._dispatcher.call(self._window.clear)
            del self._window
        except Exception:
            pass

        # Remove from parent's children list
        if hasattr(self._master, '_toplevels'):
            try:
                self._master._toplevels.remove(self)
            except ValueError:
                pass

        # Unregister from widget registry
        if self._widget_name in Misc._widget_registry:
            del Misc._widget_registry[self._widget_name]

    def wait_window(self, window: Optional[Toplevel] = None) -> None:
        """Wait until the window is destroyed.

        Blocks until the specified window (or self) is destroyed.
        Currently a stub for tkinter compatibility - returns immediately.

        Args:
            window: Window to wait for. If None, waits for self.

        Example:
            >>> dialog = Toplevel(root)
            >>> dialog.wait_window()  # Blocks until dialog.destroy()
        """
        # Stub: would require integration with mainloop for blocking
        pass

    # -------------------------------------------------------------------------
    # Layout Management Methods
    # -------------------------------------------------------------------------

    def _add_child(self, child: BaseWidget) -> None:
        """Add a child widget to this Toplevel.

        Called by widget creation to register child widgets.

        Args:
            child: The child widget to add.
        """
        if child not in self._children:
            self._children.append(child)

    def _remove_child(self, child: BaseWidget) -> None:
        """Remove a child widget from this Toplevel.

        Called when a widget is destroyed or forgotten.

        Args:
            child: The child widget to remove.
        """
        if child in self._children:
            self._children.remove(child)

    def _mark_layout_dirty(self) -> None:
        """Mark this Toplevel as needing layout recalculation.

        Called when children are added, removed, or their geometry options change.
        """
        self._layout_dirty = True

    def _do_layout(self) -> None:
        """Perform layout calculation for all children.

        Calculates positions and sizes for all children based on their
        geometry manager (pack, grid, or place) settings.
        """
        if not self._layout_dirty:
            return

        # Get content bounds for layout
        content_bounds = self._get_content_bounds()

        # Group children by geometry manager
        pack_children: list[BaseWidget] = []
        grid_children: list[BaseWidget] = []
        place_children: list[BaseWidget] = []

        for child in self._children:
            manager = getattr(child, '_geometry_manager', None)
            if manager == 'pack':
                pack_children.append(child)
            elif manager == 'grid':
                grid_children.append(child)
            elif manager == 'place':
                place_children.append(child)

        # Calculate layouts using engines
        from ._core.layout import PackLayoutEngine, GridLayoutEngine, PlaceLayoutEngine

        if pack_children:
            pack_results = PackLayoutEngine.calculate(pack_children, content_bounds)
            for child, result in pack_results.items():
                child._apply_layout(result)

        if grid_children:
            grid_results, cache = GridLayoutEngine.calculate(
                grid_children, content_bounds,
                self._row_config, self._col_config
            )
            self._grid_layout_cache = cache
            for child, result in grid_results.items():
                child._apply_layout(result)

        if place_children:
            place_results = PlaceLayoutEngine.calculate(place_children, content_bounds)
            for child, result in place_results.items():
                child._apply_layout(result)

        self._layout_dirty = False

        # Recursively layout children
        for child in self._children:
            if hasattr(child, '_do_layout'):
                child._do_layout()

    def _get_content_bounds(self) -> Rect:
        """Get the bounds available for child widgets.

        Returns:
            A Rect representing the content area (excluding borders if present).
        """
        x = 0
        y = 0
        width = self._width
        height = self._height

        # Adjust for border if present
        if self._has_border:
            x += 1
            y += 1
            width = max(0, width - 2)
            height = max(0, height - 2)

        return Rect(x=x, y=y, width=width, height=height)

    def _get_natural_size(self) -> Size:
        """Get the natural size of this Toplevel based on children.

        Returns:
            The size that would fit all children without clipping.
        """
        # If propagation is disabled, use configured size
        if not self._pack_propagate_flag and not self._grid_propagate_flag:
            return Size(self._width, self._height)

        # Calculate based on children
        max_width = 0
        max_height = 0

        for child in self._children:
            manager = getattr(child, '_geometry_manager', None)

            if manager == 'pack' and self._pack_propagate_flag:
                child_size = child._get_natural_size()
                options = getattr(child, '_pack_info', {})
                padx = options.get('padx', 0)
                pady = options.get('pady', 0)
                ipadx = options.get('ipadx', 0)
                ipady = options.get('ipady', 0)

                req_w = child_size.width + 2 * (padx + ipadx)
                req_h = child_size.height + 2 * (pady + ipady)

                side = options.get('side', 'top')
                if side in ('top', 'bottom'):
                    max_width = max(max_width, req_w)
                    max_height += req_h
                else:
                    max_width += req_w
                    max_height = max(max_height, req_h)

            elif manager == 'grid' and self._grid_propagate_flag:
                child_size = child._get_natural_size()
                options = getattr(child, '_grid_info', {})
                padx = options.get('padx', 0)
                pady = options.get('pady', 0)
                ipadx = options.get('ipadx', 0)
                ipady = options.get('ipady', 0)

                max_width = max(max_width, child_size.width + 2 * (padx + ipadx))
                max_height = max(max_height, child_size.height + 2 * (pady + ipady))

            elif manager == 'place':
                # Place children don't affect natural size
                pass

        # Add border if present
        if self._has_border:
            max_width += 2
            max_height += 2

        return Size(
            max(max_width, self._width),
            max(max_height, self._height)
        )

    def pack_slaves(self) -> list[BaseWidget]:
        """Return a list of all children managed by pack geometry manager.

        Returns:
            List of widgets managed by pack in this Toplevel.
        """
        return [
            child for child in self._children
            if getattr(child, '_geometry_manager', None) == 'pack'
        ]

    def grid_slaves(self, row: int | None = None, column: int | None = None) -> list[BaseWidget]:
        """Return a list of all children managed by grid geometry manager.

        Args:
            row: If specified, only return widgets in this row.
            column: If specified, only return widgets in this column.

        Returns:
            List of widgets managed by grid, optionally filtered by row/column.
        """
        result = []
        for child in self._children:
            if getattr(child, '_geometry_manager', None) != 'grid':
                continue
            info = getattr(child, '_grid_info', {})
            if row is not None and info.get('row') != row:
                continue
            if column is not None and info.get('column') != column:
                continue
            result.append(child)
        return result

    def place_slaves(self) -> list[BaseWidget]:
        """Return a list of all children managed by place geometry manager.

        Returns:
            List of widgets managed by place in this Toplevel.
        """
        return [
            child for child in self._children
            if getattr(child, '_geometry_manager', None) == 'place'
        ]

    def grid_size(self) -> tuple[int, int]:
        """Return the grid dimensions (columns, rows).

        Returns:
            Tuple of (max_column + 1, max_row + 1) for grid children.
        """
        max_col = 0
        max_row = 0
        for child in self._children:
            if getattr(child, '_geometry_manager', None) != 'grid':
                continue
            info = getattr(child, '_grid_info', {})
            col = info.get('column', 0) + info.get('columnspan', 1)
            row = info.get('row', 0) + info.get('rowspan', 1)
            max_col = max(max_col, col)
            max_row = max(max_row, row)
        return (max_col, max_row)

    def grid_bbox(
        self,
        column: int | None = None,
        row: int | None = None,
        col2: int | None = None,
        row2: int | None = None,
    ) -> tuple[int, int, int, int] | None:
        """Return the bounding box of a grid cell or range.

        Args:
            column: Starting column (or None for all).
            row: Starting row (or None for all).
            col2: Ending column (or None for single column).
            row2: Ending row (or None for single row).

        Returns:
            Tuple (x, y, width, height) or None if no grid children.
        """
        if self._grid_layout_cache is None:
            return None

        cache = self._grid_layout_cache

        if column is None:
            column = 0
        if row is None:
            row = 0
        if col2 is None:
            col2 = column
        if row2 is None:
            row2 = row

        # Calculate bounding box from cached positions
        if column >= len(cache.col_positions) or row >= len(cache.row_positions):
            return None

        x = cache.col_positions[column]
        y = cache.row_positions[row]

        # Calculate width
        if col2 + 1 < len(cache.col_positions):
            width = cache.col_positions[col2 + 1] - x
        else:
            width = sum(cache.col_widths[column:col2 + 1])

        # Calculate height
        if row2 + 1 < len(cache.row_positions):
            height = cache.row_positions[row2 + 1] - y
        else:
            height = sum(cache.row_heights[row:row2 + 1])

        return (x, y, width, height)

    def grid_columnconfigure(
        self,
        index: int | str,
        cnf: dict[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any] | None:
        """Configure column options for grid layout.

        Args:
            index: Column index or 'all'.
            cnf: Configuration dict.
            **kw: Configuration options (weight, minsize, pad, uniform).

        Returns:
            Current configuration if querying, None if setting.
        """
        options = cnf or {}
        options.update(kw)

        if not options:
            # Query mode
            if isinstance(index, int) and index in self._col_config:
                return self._col_config[index].copy()
            return {'weight': 0, 'minsize': 0, 'pad': 0, 'uniform': None}

        # Set mode
        if isinstance(index, str) and index == 'all':
            max_col = self.grid_size()[0]
            for col in range(max_col):
                if col not in self._col_config:
                    self._col_config[col] = {}
                self._col_config[col].update(options)
        else:
            idx = int(index)
            if idx not in self._col_config:
                self._col_config[idx] = {}
            self._col_config[idx].update(options)

        self._mark_layout_dirty()
        return None

    def grid_rowconfigure(
        self,
        index: int | str,
        cnf: dict[str, Any] | None = None,
        **kw: Any,
    ) -> dict[str, Any] | None:
        """Configure row options for grid layout.

        Args:
            index: Row index or 'all'.
            cnf: Configuration dict.
            **kw: Configuration options (weight, minsize, pad, uniform).

        Returns:
            Current configuration if querying, None if setting.
        """
        options = cnf or {}
        options.update(kw)

        if not options:
            # Query mode
            if isinstance(index, int) and index in self._row_config:
                return self._row_config[index].copy()
            return {'weight': 0, 'minsize': 0, 'pad': 0, 'uniform': None}

        # Set mode
        if isinstance(index, str) and index == 'all':
            max_row = self.grid_size()[1]
            for r in range(max_row):
                if r not in self._row_config:
                    self._row_config[r] = {}
                self._row_config[r].update(options)
        else:
            idx = int(index)
            if idx not in self._row_config:
                self._row_config[idx] = {}
            self._row_config[idx].update(options)

        self._mark_layout_dirty()
        return None

    def grid_location(self, x: int, y: int) -> tuple[int, int]:
        """Return the grid cell containing a point.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Tuple (column, row) of the cell at that location.
        """
        if self._grid_layout_cache is None:
            return (0, 0)

        cache = self._grid_layout_cache

        # Find column
        col = 0
        for i, pos in enumerate(cache.col_positions):
            if x >= pos:
                col = i
            else:
                break

        # Find row
        row = 0
        for i, pos in enumerate(cache.row_positions):
            if y >= pos:
                row = i
            else:
                break

        return (col, row)


class Variable:
    """Base class for tkinter-style Variable classes.

    Variable provides a mechanism for storing values that can trigger
    callbacks when modified. This is useful for binding widget values
    to variables and for creating reactive data flows.

    Subclasses provide type-specific behavior:
        - StringVar: String values
        - IntVar: Integer values
        - DoubleVar: Float values
        - BooleanVar: Boolean values

    Variables maintain a list of trace callbacks that are invoked when
    the value changes. Traces can be set for write, read, or unset operations.

    Example:
        >>> var = StringVar()
        >>> var.set("Hello")
        >>> print(var.get())  # "Hello"
        >>>
        >>> # With trace callback
        >>> def on_change(*args):
        ...     print(f"Value changed to: {var.get()}")
        >>> var.trace_add("write", on_change)
        >>> var.set("World")  # Prints: "Value changed to: World"

    Attributes:
        _value: The current stored value.
        _name: Unique name for this variable (for compatibility).
        _traces: Dictionary mapping trace IDs to callback info.
    """

    # Class-level counter for generating unique variable names
    _counter: int = 0

    def __init__(
        self,
        master: Optional[Misc] = None,
        value: Any = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the Variable.

        Args:
            master: Widget that owns this variable (for compatibility,
                currently unused in TkCurses).
            value: Initial value. If None, uses the default for the type.
            name: Variable name. If None, generates a unique name.

        Example:
            >>> var = Variable(value="initial")
            >>> print(var.get())  # "initial"
        """
        self._master = master

        # Generate unique name if not provided
        if name is None:
            Variable._counter += 1
            self._name = f"PY_VAR{Variable._counter}"
        else:
            self._name = name

        # Initialize value
        self._value: Any = self._default() if value is None else value

        # Trace callbacks: {trace_id: (mode, callback)}
        self._traces: dict[str, tuple[str, Callable[..., Any]]] = {}
        self._trace_counter: int = 0

    def _default(self) -> Any:
        """Return the default value for this variable type.

        Subclasses override this to provide type-specific defaults.

        Returns:
            The default value (empty string for base Variable).
        """
        return ""

    def get(self) -> Any:
        """Get the current value.

        Invokes any "read" traces before returning the value.

        Returns:
            The current stored value.

        Example:
            >>> var = Variable(value="test")
            >>> print(var.get())  # "test"
        """
        self._invoke_traces("read")
        return self._value

    def set(self, value: Any) -> None:
        """Set a new value.

        Invokes any "write" traces after setting the value.

        Args:
            value: The new value to store.

        Example:
            >>> var = Variable()
            >>> var.set("new value")
            >>> print(var.get())  # "new value"
        """
        self._value = value
        self._invoke_traces("write")

    def trace_add(
        self,
        mode: str,
        callback: Callable[..., Any],
    ) -> str:
        """Add a trace callback.

        Registers a callback to be invoked when the variable changes.
        The callback receives three arguments: the variable name,
        an empty string (for tkinter compatibility), and the mode.

        Args:
            mode: When to invoke the callback:
                - "write": After value is modified
                - "read": Before value is read
                - "unset": When variable is deleted (not implemented)
            callback: Function to call. Receives (name, index, mode).

        Returns:
            A trace ID that can be used with trace_remove().

        Example:
            >>> def on_write(name, index, mode):
            ...     print(f"Variable {name} was written")
            >>> trace_id = var.trace_add("write", on_write)
        """
        self._trace_counter += 1
        trace_id = f"trace{self._trace_counter}"
        self._traces[trace_id] = (mode, callback)
        return trace_id

    def trace_remove(self, mode: str, cbname: str) -> None:
        """Remove a trace callback.

        Removes a previously registered trace callback.

        Args:
            mode: The trace mode (for compatibility, currently ignored).
            cbname: The trace ID returned by trace_add().

        Example:
            >>> trace_id = var.trace_add("write", callback)
            >>> var.trace_remove("write", trace_id)
        """
        if cbname in self._traces:
            del self._traces[cbname]

    def trace_info(self) -> list[tuple[tuple[str, ...], str]]:
        """Get information about all traces.

        Returns:
            A list of ((mode,), callback_id) tuples for each trace.

        Example:
            >>> var.trace_add("write", callback)
            >>> info = var.trace_info()
            >>> print(info)  # [(('write',), 'trace1')]
        """
        return [((mode,), trace_id) for trace_id, (mode, _) in self._traces.items()]

    def _invoke_traces(self, mode: str) -> None:
        """Invoke all trace callbacks for the given mode.

        Internal method that calls all registered traces that match
        the specified mode.

        Args:
            mode: The trace mode ("read", "write", or "unset").
        """
        for trace_id, (trace_mode, callback) in list(self._traces.items()):
            if trace_mode == mode:
                try:
                    callback(self._name, "", mode)
                except Exception as e:
                    # In tkinter, trace errors are typically caught
                    print(f"Error in trace callback: {e}")

    # Legacy trace methods (for tkinter compatibility)
    def trace(
        self,
        mode: str,
        callback: Callable[..., Any],
    ) -> str:
        """Legacy trace method (deprecated in tkinter 8.6).

        Use trace_add() instead.

        Args:
            mode: "w" for write, "r" for read, "u" for unset.
            callback: The callback function.

        Returns:
            A trace ID.
        """
        mode_map = {"w": "write", "r": "read", "u": "unset"}
        return self.trace_add(mode_map.get(mode, mode), callback)

    def trace_variable(
        self,
        mode: str,
        callback: Callable[..., Any],
    ) -> str:
        """Legacy trace method (deprecated in tkinter 8.6).

        Use trace_add() instead.
        """
        return self.trace(mode, callback)

    def trace_vdelete(self, mode: str, cbname: str) -> None:
        """Legacy trace delete method (deprecated in tkinter 8.6).

        Use trace_remove() instead.
        """
        self.trace_remove(mode, cbname)

    def trace_vinfo(self) -> list[tuple[tuple[str, ...], str]]:
        """Legacy trace info method (deprecated in tkinter 8.6).

        Use trace_info() instead.
        """
        return self.trace_info()

    def __str__(self) -> str:
        """Return the variable name.

        Returns:
            The unique name of this variable.
        """
        return self._name

    def __repr__(self) -> str:
        """Return a string representation.

        Returns:
            A string showing the class and current value.
        """
        return f"{self.__class__.__name__}({self._value!r})"

    def __eq__(self, other: object) -> bool:
        """Check equality by comparing values.

        Args:
            other: Another Variable or value to compare.

        Returns:
            True if values are equal.
        """
        if isinstance(other, Variable):
            return self._value == other._value
        return self._value == other


class StringVar(Variable):
    """Variable class for storing string values.

    StringVar stores string values and provides type-specific behavior.
    Values are automatically converted to strings when set.

    Example:
        >>> name = StringVar(value="Alice")
        >>> print(name.get())  # "Alice"
        >>>
        >>> # Bind to an Entry widget
        >>> entry = Entry(root, textvariable=name)
        >>> name.set("Bob")  # Entry updates automatically

    Note:
        Unlike tkinter, TkCurses does not automatically update widget
        displays when variables change. This functionality will be
        added when widgets are implemented.
    """

    def __init__(
        self,
        master: Optional[Misc] = None,
        value: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the StringVar.

        Args:
            master: Widget that owns this variable (for compatibility).
            value: Initial string value. Defaults to empty string.
            name: Variable name. If None, generates a unique name.

        Example:
            >>> var = StringVar(value="Hello")
        """
        super().__init__(master, value, name)

    def _default(self) -> str:
        """Return the default value (empty string).

        Returns:
            An empty string.
        """
        return ""

    def get(self) -> str:
        """Get the current string value.

        Returns:
            The current string value.

        Example:
            >>> var = StringVar(value="test")
            >>> print(var.get())  # "test"
        """
        self._invoke_traces("read")
        return str(self._value)

    def set(self, value: str) -> None:
        """Set a new string value.

        The value is converted to a string if it isn't already.

        Args:
            value: The new value (will be converted to string).

        Example:
            >>> var = StringVar()
            >>> var.set("Hello")
            >>> var.set(123)  # Converted to "123"
        """
        self._value = str(value)
        self._invoke_traces("write")


class IntVar(Variable):
    """Variable class for storing integer values.

    IntVar stores integer values and provides type-specific behavior.
    Values are converted to integers when set, with validation.

    Example:
        >>> count = IntVar(value=0)
        >>> count.set(42)
        >>> print(count.get())  # 42
        >>>
        >>> # Bind to a Scale widget
        >>> scale = Scale(root, variable=count, from_=0, to=100)
        >>> count.set(50)  # Scale updates automatically
    """

    def __init__(
        self,
        master: Optional[Misc] = None,
        value: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the IntVar.

        Args:
            master: Widget that owns this variable (for compatibility).
            value: Initial integer value. Defaults to 0.
            name: Variable name. If None, generates a unique name.

        Example:
            >>> var = IntVar(value=10)
        """
        super().__init__(master, value, name)

    def _default(self) -> int:
        """Return the default value (0).

        Returns:
            Zero.
        """
        return 0

    def get(self) -> int:
        """Get the current integer value.

        Returns:
            The current integer value.

        Example:
            >>> var = IntVar(value=42)
            >>> print(var.get())  # 42
        """
        self._invoke_traces("read")
        return int(self._value)

    def set(self, value: int) -> None:
        """Set a new integer value.

        The value is converted to an integer if possible.

        Args:
            value: The new value (will be converted to int).

        Raises:
            ValueError: If the value cannot be converted to int.

        Example:
            >>> var = IntVar()
            >>> var.set(42)
            >>> var.set("123")  # Converted to 123
        """
        self._value = int(value)
        self._invoke_traces("write")


class DoubleVar(Variable):
    """Variable class for storing floating-point values.

    DoubleVar stores float values and provides type-specific behavior.
    Values are converted to floats when set, with validation.

    Example:
        >>> price = DoubleVar(value=19.99)
        >>> price.set(24.99)
        >>> print(price.get())  # 24.99
        >>>
        >>> # Use with Scale for fractional values
        >>> scale = Scale(root, variable=price, from_=0.0, to=100.0)
    """

    def __init__(
        self,
        master: Optional[Misc] = None,
        value: Optional[float] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the DoubleVar.

        Args:
            master: Widget that owns this variable (for compatibility).
            value: Initial float value. Defaults to 0.0.
            name: Variable name. If None, generates a unique name.

        Example:
            >>> var = DoubleVar(value=3.14)
        """
        super().__init__(master, value, name)

    def _default(self) -> float:
        """Return the default value (0.0).

        Returns:
            Zero as a float.
        """
        return 0.0

    def get(self) -> float:
        """Get the current float value.

        Returns:
            The current float value.

        Example:
            >>> var = DoubleVar(value=3.14)
            >>> print(var.get())  # 3.14
        """
        self._invoke_traces("read")
        return float(self._value)

    def set(self, value: float) -> None:
        """Set a new float value.

        The value is converted to a float if possible.

        Args:
            value: The new value (will be converted to float).

        Raises:
            ValueError: If the value cannot be converted to float.

        Example:
            >>> var = DoubleVar()
            >>> var.set(3.14)
            >>> var.set("2.71")  # Converted to 2.71
        """
        self._value = float(value)
        self._invoke_traces("write")


class BooleanVar(Variable):
    """Variable class for storing boolean values.

    BooleanVar stores boolean values and provides type-specific behavior.
    Values are converted to booleans when set.

    Example:
        >>> enabled = BooleanVar(value=True)
        >>> print(enabled.get())  # True
        >>>
        >>> # Bind to a Checkbutton
        >>> check = Checkbutton(root, variable=enabled, text="Enable")
        >>> enabled.set(False)  # Checkbutton unchecks

    Note:
        In tkinter, BooleanVar stores 0/1 internally but returns
        True/False from get(). This implementation follows that behavior.
    """

    def __init__(
        self,
        master: Optional[Misc] = None,
        value: Optional[bool] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the BooleanVar.

        Args:
            master: Widget that owns this variable (for compatibility).
            value: Initial boolean value. Defaults to False.
            name: Variable name. If None, generates a unique name.

        Example:
            >>> var = BooleanVar(value=True)
        """
        super().__init__(master, value, name)

    def _default(self) -> bool:
        """Return the default value (False).

        Returns:
            False.
        """
        return False

    def get(self) -> bool:
        """Get the current boolean value.

        Returns:
            The current boolean value.

        Example:
            >>> var = BooleanVar(value=True)
            >>> print(var.get())  # True
        """
        self._invoke_traces("read")
        return bool(self._value)

    def set(self, value: bool) -> None:
        """Set a new boolean value.

        The value is converted to a boolean.

        Args:
            value: The new value (will be converted to bool).

        Example:
            >>> var = BooleanVar()
            >>> var.set(True)
            >>> var.set(1)  # Converted to True
            >>> var.set(0)  # Converted to False
        """
        self._value = bool(value)
        self._invoke_traces("write")
