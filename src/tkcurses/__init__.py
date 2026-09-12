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

__version__ = "0.1.0"

__all__ = ["__version__"]
