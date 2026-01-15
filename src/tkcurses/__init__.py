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

__version__ = "0.1.0"

__all__: list[str] = []
