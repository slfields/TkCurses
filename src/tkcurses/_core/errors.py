"""Exception types.

tkinter reports almost every failure as ``TclError``, and application code
catches it by that name. There is no Tcl here, but the name is part of the API
being mirrored, so it is kept and given a docstring that says what it actually
means.

The type lives in ``_core`` rather than in the public module so that internal
components can raise it without importing the package they are imported by.
"""

from __future__ import annotations

__all__ = ["TclError", "TkCursesError"]


class TkCursesError(Exception):
    """Base class for errors raised by TkCurses."""


#: What tkinter calls its errors. Application code written against tkinter
#: catches ``TclError``, so the name has to exist and has to be what gets
#: raised; ``TkCursesError`` is there for code that would rather say what it
#: means.
TclError = TkCursesError
