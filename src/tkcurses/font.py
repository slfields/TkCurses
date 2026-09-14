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

"""Named fonts, for a device with one font.

A terminal's typeface and its size belong to whoever opened the terminal.
Nothing here can change either, and a module that pretended otherwise would
be the worst kind of compatibility: code that runs, reports success, and
does nothing. So a Font here is honest about which of its six attributes
survive.

============  ==========================================================
attribute     what happens to it
============  ==========================================================
``family``    Reported as ``fixed`` and ignored. There is one typeface.
``size``      Reported as ``1``, meaning one character cell. Setting it
              is remembered and changes nothing.
``weight``    **Real.** ``bold`` is drawn bold.
``slant``     **Real** where the terminal has italics, which many do not
              - and that is the terminal's business, not ours.
``underline`` **Real.**
``overstrike`` Remembered and ignored: curses has no strikeout.
============  ==========================================================

What is genuinely useful here is :meth:`Font.measure`, which answers in
cells and is exact rather than approximate - the whole difficulty of
measuring text in a proportional font does not arise. A widget laid out from
``measure`` will fit.

Fonts are named, as they are in Tk, and a widget names one in its ``font``
option. The name is looked up when the widget draws, so ``Label(font=bold)``
with a Font object works the way it does in tkinter, through ``str()``.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

import tkcurses

if TYPE_CHECKING:
    from tkcurses import Misc

__all__ = [
    "BOLD",
    "ITALIC",
    "NORMAL",
    "ROMAN",
    "Font",
    "families",
    "names",
    "nametofont",
]

__version__ = "0.9"

# weight / slant, as tkinter spells them
NORMAL = "normal"
ROMAN = "roman"
BOLD = "bold"
ITALIC = "italic"

#: The one typeface there is. Tk reports a real family name; this reports
#: what is true of every terminal, which is that its font is fixed-pitch and
#: chosen elsewhere.
FAMILY = "fixed"

#: A character cell. Tk's sizes are points, or pixels when negative; the only
#: unit that means anything here is the cell, and everything is one.
SIZE = 1

#: What a Font starts as, and what ``actual`` fills in around.
DEFAULTS: dict[str, Any] = {
    "family": FAMILY,
    "size": SIZE,
    "weight": NORMAL,
    "slant": ROMAN,
    "underline": 0,
    "overstrike": 0,
}


def _root_of(root: Misc | None, what: str) -> Misc:
    """The widget whose application owns the font table."""
    if root is None:
        return tkcurses._get_default_root(what)
    return root


class Font:
    """A named font.

    Attributes:
        name: What widgets call it in their ``font`` option.
    """

    counter = itertools.count(1)

    def __init__(
        self,
        root: Misc | None = None,
        font: Any = None,
        name: str | None = None,
        exists: bool = False,
        **options: Any,
    ) -> None:
        """
        Args:
            root: Any widget; its application holds the font table.
            font: An existing font to copy - a name, a Font, or a
                ``(family, size, *styles)`` tuple as Tk accepts.
            name: What to call this one. Generated when omitted.
            exists: True to point at a font already defined rather than
                create one.
            **options: ``family``, ``size``, ``weight``, ``slant``,
                ``underline``, ``overstrike``.

        Raises:
            TclError: If ``exists`` is true and no font has that name, or if
                a font of that name already exists and ``exists`` is false.
        """
        self._root = _root_of(root, "use font")
        self.name = name or f"font{next(self.counter)}"
        table = self._root.tk.fonts

        if exists:
            if self.name not in table:
                raise tkcurses.TclError(
                    f"named font {self.name} does not already exist"
                )
            self.delete_font = False
            if font or options:
                table[self.name].update(_describe(font, options, self._root))
            return

        if self.name in table:
            raise tkcurses.TclError(f"font {self.name!r} already exists")
        table[self.name] = {**DEFAULTS, **_describe(font, options, self._root)}
        self.delete_font = True

    # ------------------------------------------------------------- the name

    def __str__(self) -> str:
        """The name, which is what a widget's ``font`` option holds."""
        return self.name

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__module__}.{self.__class__.__qualname__}"
            f" object {self.name!r}>"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Font):
            return NotImplemented
        return self.name == other.name and self._root.tk is other._root.tk

    def __hash__(self) -> int:
        return hash(self.name)

    def __getitem__(self, key: str) -> Any:
        return self.cget(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.configure(**{key: value})

    def __del__(self) -> None:
        # Never raises: a font outliving its application is an ordinary way
        # for a program to end, not a fault to report during teardown.
        try:
            if self.delete_font:
                self._root.tk.fonts.pop(self.name, None)
        except Exception:
            pass

    # ------------------------------------------------------------- options

    @property
    def _options(self) -> dict[str, Any]:
        """This font's entry in the application's table."""
        return self._root.tk.fonts.setdefault(self.name, dict(DEFAULTS))

    def copy(self) -> Font:
        """A distinct font with the same attributes."""
        return Font(self._root, **self._options)

    def cget(self, option: str) -> Any:
        """One attribute, as it was asked for.

        Raises:
            TclError: If it is not one of the six a font has.
        """
        if option not in DEFAULTS:
            raise tkcurses.TclError(f'unknown option "-{option}"')
        return self._options[option]

    def config(self, **options: Any) -> dict[str, Any] | None:
        """Read every attribute, or change the ones given.

        Raises:
            TclError: If an option is not one of the six.
        """
        if not options:
            return dict(self._options)
        unknown = set(options) - set(DEFAULTS)
        if unknown:
            raise tkcurses.TclError(f'unknown option "-{sorted(unknown)[0]}"')
        self._options.update(options)
        return None

    configure = config

    def actual(self, option: str | None = None, displayof: Misc | None = None) -> Any:  # noqa: ARG002
        """What the terminal will really do with this font.

        Not what was asked for. The family is the terminal's, the size is one
        cell whatever was requested, and only the styling a terminal can draw
        comes back as it was set - which is the same honesty ``winfo_rgb``
        applies to a colour it cannot show exactly.
        """
        real = {
            **self._options,
            "family": FAMILY,
            "size": SIZE,
            # Nothing draws a strikeout, so nothing reports one.
            "overstrike": 0,
        }
        if option is not None:
            if option not in DEFAULTS:
                raise tkcurses.TclError(f'unknown option "-{option}"')
            return real[option]
        return real

    # ------------------------------------------------------------ measuring

    def measure(self, text: str, displayof: Misc | None = None) -> int:  # noqa: ARG002
        """How many cells ``text`` needs.

        Exact, which it never is in a proportional font: a character cell is
        a character cell, so a widget laid out from this will fit.
        """
        return len(text)

    def metrics(self, *options: str, **kw: Any) -> Any:
        """Line metrics, in cells.

        A cell is the whole line: one row tall, nothing above the baseline
        and nothing below it, and every character the same width - which is
        what ``fixed`` means and why it is the one metric here that could
        ever have been false.
        """
        kw.pop("displayof", None)
        real = {"ascent": 1, "descent": 0, "linespace": 1, "fixed": 1}
        if options:
            unknown = set(options) - set(real)
            if unknown:
                raise tkcurses.TclError(f'unknown option "-{sorted(unknown)[0]}"')
            if len(options) == 1:
                return real[options[0]]
            return {name: real[name] for name in options}
        return real


def _describe(font: Any, options: dict[str, Any], root: Misc) -> dict[str, Any]:
    """Turn whatever was passed as ``font`` into attributes.

    Tk takes three shapes: the name of a font, a ``(family, size, *styles)``
    tuple, or nothing at all with the attributes given as keywords.
    """
    if font is None:
        return dict(options)
    if isinstance(font, Font):
        return dict(font.config() or {})
    if isinstance(font, (list, tuple)):
        described: dict[str, Any] = {}
        parts = list(font)
        if parts:
            described["family"] = str(parts[0])
        if len(parts) > 1:
            described["size"] = parts[1]
        for style in parts[2:]:
            text = str(style).lower()
            if text == BOLD:
                described["weight"] = BOLD
            elif text == ITALIC:
                described["slant"] = ITALIC
            elif text == "underline":
                described["underline"] = 1
            elif text == "overstrike":
                described["overstrike"] = 1
        return described
    named = root.tk.fonts.get(str(font))
    if named is not None:
        return dict(named)
    # A description in Tk's string form: "Courier 10 bold italic".
    parts = str(font).split()
    described = {}
    if parts:
        described["family"] = parts[0]
    for part in parts[1:]:
        text = part.lower()
        if text == BOLD:
            described["weight"] = BOLD
        elif text == ITALIC:
            described["slant"] = ITALIC
        elif text == "underline":
            described["underline"] = 1
        elif text == "overstrike":
            described["overstrike"] = 1
        elif text.lstrip("-").isdigit():
            described["size"] = int(text)
    return described


def nametofont(name: str, root: Misc | None = None) -> Font:
    """The font already defined under this name.

    Raises:
        TclError: If nothing is defined under it.
    """
    return Font(name=name, exists=True, root=root)


def families(
    root: Misc | None = None,
    displayof: Misc | None = None,  # noqa: ARG001 - tkinter signature
) -> tuple[str, ...]:
    """The typefaces there are, which is one."""
    _root_of(root, "use font.families()")
    return (FAMILY,)


def names(root: Misc | None = None) -> tuple[str, ...]:
    """The names of the fonts defined so far."""
    return tuple(_root_of(root, "use font.names()").tk.fonts)
