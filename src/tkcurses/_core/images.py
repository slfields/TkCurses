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

"""Images, on the same pixel plane everything else draws on.

**One pixel is one cell wide and half a cell tall**, which is the pixel
:mod:`tkcurses._core.canvas` already defined and the only one the library
has. An image 8 by 4 therefore occupies 8 cells across and 2 down, and is
drawn by the same :func:`~tkcurses._core.canvas.compose` that draws a canvas:
``▀``, ``▄`` and ``█``, with up to two colours in a cell.

This module was first written the other way round, with a pixel being a whole
character cell and an image being a grid of glyphs. That was internally
consistent and it was wrong. It put a second meaning of "pixel" into a
library that already had one, ``get()`` returned a glyph where Tk returns a
colour, and an image could not be handed to a canvas without a conversion
nobody had specified - so ``create_image`` was impossible by construction
rather than by choice. One plane, one pixel.

A pixel holds a colour, or nothing. Nothing is transparency: the pixel
declines to paint and whatever is behind it shows through, which is what
there is instead of an alpha channel.

Authoring is the one place this differs from Tk in shape rather than in
units, and it has to: nobody types a photograph. Two forms are accepted, and
both are rows:

    PhotoImage(data=["  ##  ", " #### "], palette={"#": "red"})
    PhotoImage(data=[["red", "blue"], ["blue", "red"]])

The first is XPM's idea - characters standing for colours - which is how
people have drawn small images in text since X11, and it is what a source
file can hold legibly. The second is the literal plane. A character with no
palette entry is transparent, so a space is a hole by default and art needs
no separate mask.

What is faithfully reproduced, because programs depend on it:

    An image is referred to by *name*. ``str(photo)`` is that name, a widget's
    ``image`` option holds it, and ``cget("image")`` gives it back. Measured
    on Tk 9.0.2: ``str(p)`` is ``'pyimage1'`` and ``lab.cget("image")`` is the
    same string, not the object.

    An image that nothing references is gone, and a widget showing it keeps
    its size and draws nothing. This is the trap every tkinter tutorial warns
    about - "keep a reference or your image disappears" - and it is
    reproduced rather than fixed, because code written against tkinter is
    written around it. Measured: after deleting an image a live Label showed,
    the label stayed alive at its old 22x12 and ``cget("image")`` still
    returned the dead name. Collection is silent, so a finalizer rather than
    the change notification is what repaints the widget empty.

    A widget follows its image. Measured: resizing an image from 4x2 to 20x10
    moved a Label's request from 6x4 to 22x12 with no call on the label at
    all. So an image tells the widgets using it when it changes, which is
    what :meth:`Image._changed` is for.

    ``get()`` answers with a triple, and a pixel painting nothing reads
    ``(0, 0, 0)``. Measured on Tk: a blanked PhotoImage reads ``(0, 0, 0)``
    at every pixel, and whether it is transparent is a separate question
    asked with ``transparency_get``.
"""

from __future__ import annotations

import itertools
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tkcurses._core.colors import rgb_of
from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

__all__ = ["BitmapImage", "Image", "PhotoImage"]

#: A pixel with nothing in it. Not a colour: the pixel declines to paint, and
#: what is behind it shows through. There is no alpha channel to zero.
TRANSPARENT = None

#: One pixel: the colour it paints, or None for a hole.
Pixel = str | None
Row = list[Pixel]

#: What ``get`` reports for a pixel that paints nothing. Measured on Tk
#: 9.0.2: a blanked PhotoImage reads (0, 0, 0) everywhere, and whether the
#: pixel is transparent is a separate question.
UNLIT = (0, 0, 0)

#: Pixel rows to a cell. ``▀`` is the upper, ``▄`` the lower.
ROWS_PER_CELL = 2


def cells_tall(pixel_rows: int) -> int:
    """Cells needed to show ``pixel_rows`` rows, a lone row rounding up."""
    return (pixel_rows + ROWS_PER_CELL - 1) // ROWS_PER_CELL


def _rows_of(data: str | Iterable[Any]) -> list[Any]:
    """Split ``data`` into rows, accepting a string with newlines in it."""
    if isinstance(data, str):
        return data.split("\n")
    return list(data)


class Image:
    """What PhotoImage and BitmapImage have in common.

    tkinter has this class too, and it carries less than you would expect:
    measured, ``tkinter.Image`` defines only ``config``, ``configure``,
    ``height``, ``type`` and ``width``. ``cget`` is PhotoImage's alone -
    ``BitmapImage`` genuinely has no ``cget`` method, and a caller reads its
    options with ``image["foreground"]``. That asymmetry is tkinter's, and it
    is kept.
    """

    #: What ``type()`` reports. Tk's image types are strings, not classes.
    _type = "image"

    #: Names automatic images pyimage1, pyimage2, as tkinter does, so a
    #: printed image name reads the same under either library. One counter
    #: for both classes, which is also Tk's arrangement.
    _counter = itertools.count(1)

    def __init__(
        self,
        name: str | None = None,
        cnf: dict[str, Any] | None = None,
        master: Any = None,
        **kw: Any,
    ) -> None:
        """
        Args:
            name: The image's name, generated when omitted.
            cnf: Options as a dictionary, which is tkinter's older spelling.
            master: Any widget of the application the image belongs to.
                Defaults to the implicit root.
            **kw: Options, merged over ``cnf``.

        Raises:
            TclError: If no master was given and there is no root window.
        """
        import tkcurses

        if master is None:
            master = tkcurses._get_default_root("create an image")
        self._master = master
        self._tk = master.tk
        self._name = name or f"pyimage{next(Image._counter)}"
        #: Pixels, row-major. Every image is a rectangle; ragged rows are
        #: padded with holes when they go in, so nothing downstream checks.
        self._pixels: list[Row] = []
        #: Widgets to tell when this image changes, held weakly so that
        #: showing an image never keeps a destroyed widget alive.
        self._users: weakref.WeakKeyDictionary[Any, Callable[[], None]] = (
            weakref.WeakKeyDictionary()
        )
        self._options: dict[str, Any] = {}
        self._tk.images[self._name] = self
        options = {**(cnf or {}), **kw}
        self._init(options)

    def _init(self, options: dict[str, Any]) -> None:
        """Set the image up from its options. Subclasses override this."""
        raise NotImplementedError

    # ------------------------------------------------------------- naming

    def __str__(self) -> str:
        """The image's name, which is how Tk refers to one."""
        return self._name

    def __repr__(self) -> str:
        """Name and size in pixels, for a traceback or a debugger."""
        return f"<{type(self).__name__} {self._name} {self.width()}x{self.height()}>"

    def __eq__(self, other: object) -> bool:
        """Equal to an image of the same class with the same name."""
        if not isinstance(other, Image):
            return NotImplemented
        return type(self) is type(other) and self._name == other._name

    def __hash__(self) -> int:
        """Hashable by name, so an image can be a dictionary key."""
        return hash((type(self).__name__, self._name))

    def type(self) -> str:
        """``'photo'`` or ``'bitmap'``, as Tk names its image types."""
        return self._type

    # -------------------------------------------------------------- shape

    def width(self) -> int:
        """The image's width in pixels, which is also its width in cells."""
        return len(self._pixels[0]) if self._pixels else 0

    def height(self) -> int:
        """The image's height in pixels. Two pixel rows make a cell."""
        return len(self._pixels)

    def cell_height(self) -> int:
        """Rows of terminal needed to show it, a lone pixel row rounding up."""
        return cells_tall(self.height())

    # ------------------------------------------------------------ options

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> Any:
        """Change options, or report them all when given none."""
        options = {**(cnf or {}), **kw}
        if not options:
            return dict(self._options)
        self._configure(options)
        self._changed()
        return None

    #: tkinter's abbreviation, and the one older code uses.
    config = configure

    def __setitem__(self, key: str, value: Any) -> None:
        """``image[option] = value``, as tkinter allows."""
        self.configure({key: value})

    def __getitem__(self, key: str) -> Any:
        """``image[option]``. BitmapImage's only way of reading one."""
        try:
            return self._options[key]
        except KeyError:
            raise TclError(f'unknown option "-{key}"') from None

    def _configure(self, options: dict[str, Any]) -> None:
        """Apply changed options. Subclasses override this."""
        raise NotImplementedError

    # ------------------------------------------------------------ redraw

    def _watch(self, widget: Any, callback: Callable[[], None]) -> None:
        """Have ``callback`` run whenever this image changes.

        Held weakly against the widget: a widget that is destroyed stops
        being told, without the image having to be asked to forget it.
        """
        self._users[widget] = callback

    def _unwatch(self, widget: Any) -> None:
        """Stop telling ``widget`` about changes."""
        self._users.pop(widget, None)

    def _changed(self) -> None:
        """Tell every widget showing this image that it has changed.

        Both halves matter, and they are different: a widget has to lay out
        again if the size moved, and repaint either way. Measured on Tk
        9.0.2, resizing an image under a live Label moved the label's
        requested size with no call on the label at all.
        """
        for callback in list(self._users.values()):
            callback()

    # ------------------------------------------------------------ reading

    def _at(self, x: int, y: int) -> Pixel:
        """The pixel at ``(x, y)``, checked against the image's extent."""
        if not (0 <= y < self.height() and 0 <= x < self.width()):
            raise TclError(f"{self._name} get: coordinates out of range")
        return self._pixels[y][x]

    def rows(self) -> list[Row]:
        """A copy of the pixels, row by row."""
        return [list(row) for row in self._pixels]

    def lit(self) -> dict[tuple[int, int], str]:
        """Every pixel that paints, keyed by ``(x, y)``.

        Exactly what :func:`~tkcurses._core.canvas.compose` takes, which is
        the point of sharing the plane: a widget draws an image by composing
        this, the same way a canvas draws a circle.
        """
        return {
            (x, y): colour
            for y, row in enumerate(self._pixels)
            for x, colour in enumerate(row)
            if colour is not None
        }


class PhotoImage(Image):
    """A plane of coloured pixels.

    Args:
        name: The image's name, generated when omitted.
        cnf: Options as a dictionary, tkinter's older spelling.
        master: Any widget of the application the image belongs to.
        **kw: ``width`` and ``height`` in pixels, ``data`` as rows,
            ``palette`` mapping characters to colours, ``file`` to read rows
            from, and ``foreground`` for what an unmapped character paints.

    Raises:
        TclError: If ``file`` cannot be read, which is what Tk raises for an
            image file it cannot open.

    Example:
        >>> photo = PhotoImage(data=["#.#", ".#."],     # doctest: +SKIP
        ...                    palette={"#": "cyan"})
        >>> photo.width(), photo.height(), photo.cell_height()
        (3, 2, 1)
    """

    _type = "photo"

    def _init(self, options: dict[str, Any]) -> None:
        self._options = {
            "width": 0,
            "height": 0,
            "data": "",
            "file": "",
            "palette": None,
            "foreground": "white",
            "background": "",
        }
        self._configure(options)

    def _configure(self, options: dict[str, Any]) -> None:
        unknown = set(options) - set(self._options)
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        self._options.update(options)
        if options.get("file"):
            self._read_file(str(options["file"]))
        elif options.get("data"):
            self._set_rows(_rows_of(options["data"]))
        elif "width" in options or "height" in options:
            self._resize(int(self._options["width"]), int(self._options["height"]))

    # ------------------------------------------------------------ building

    def _colour_of(self, item: Any) -> Pixel:
        """One piece of source data as a colour, or None for a hole."""
        if item is None:
            return TRANSPARENT
        text = str(item)
        palette = self._options["palette"]
        if palette is not None:
            # A character with no entry is a hole, so a space needs no rule
            # and art needs no separate mask.
            found: Pixel = palette.get(text)
            return found
        if text in ("", " "):
            return TRANSPARENT
        return text

    def _set_rows(self, rows: Sequence[Any]) -> None:
        """Replace the whole image, padding it rectangular with holes."""
        split = [list(row) for row in rows]
        width = max((len(row) for row in split), default=0)
        self._pixels = [
            [
                self._colour_of(row[x]) if x < len(row) else TRANSPARENT
                for x in range(width)
            ]
            for row in split
        ]
        self._options["width"] = width
        self._options["height"] = len(split)

    def _read_file(self, path: str) -> None:
        """Load rows from a text file, one line per pixel row."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise TclError(
                f'couldn\'t open "{path}": {exc.strerror or "no such file or directory"}'
            ) from None
        self._set_rows(text.rstrip("\n").split("\n"))

    def _resize(self, width: int, height: int) -> None:
        """Grow or crop to ``width`` x ``height`` pixels, keeping the overlap."""
        rows: list[Row] = []
        for y in range(height):
            old = self._pixels[y] if y < len(self._pixels) else []
            rows.append([old[x] if x < len(old) else TRANSPARENT for x in range(width)])
        self._pixels = rows
        self._options["width"] = width
        self._options["height"] = height

    # ------------------------------------------------------------ content

    def cget(self, option: str) -> Any:
        """One option's value. PhotoImage has this and BitmapImage does not."""
        return self[option]

    def blank(self) -> None:
        """Clear every pixel, leaving the image its size and transparent."""
        self._pixels = [[TRANSPARENT] * self.width() for _ in range(self.height())]
        self._changed()

    def get(self, x: int, y: int) -> tuple[int, int, int]:
        """The pixel's colour as ``(r, g, b)``, as Tk's ``get`` reports it.

        The triple is the RGB the terminal palette actually renders for that
        colour, not an invented one: a terminal has the colours it has, and
        saying otherwise would make ``get`` a less honest answer rather than
        a more precise one. A pixel that paints nothing reads ``(0, 0, 0)``,
        which is what a blanked Tk image reads; ``transparency_get`` is the
        question that distinguishes them, there as here.

        Raises:
            TclError: If the coordinates are outside the image, which is what
                Tk raises: ``pyimage1 get: coordinates out of range``.
        """
        colour = self._at(x, y)
        if colour is None:
            return UNLIT
        return rgb_of(colour) or UNLIT

    def put(self, data: Any, to: tuple[int, ...] | None = None) -> None:
        """Write colours into the image.

        Args:
            data: One colour, which fills the region ``to`` names - Tk's
                ``put("red", to=...)`` - or rows, as the constructor takes
                them. Rows smaller than the region tile across it.
            to: ``(x, y)`` to place at, or ``(x1, y1, x2, y2)`` to fill.
                Without it the data goes at the origin.

        Raises:
            TclError: If ``to`` is neither two numbers nor four.
        """
        # A plain string is one colour, filling the region - Tk's
        # put("red", to=...) - and a list is rows. That is the only rule
        # separating them, and without it "blue" came apart into the
        # characters b, l, u, e and painted four holes.
        solid = isinstance(data, str) and "\n" not in data
        rows = [[data]] if solid else [list(row) for row in _rows_of(data)]
        rows = [row for row in rows if row]
        if not rows:
            return
        wide = max(len(row) for row in rows)
        if to is None:
            x1, y1, x2, y2 = 0, 0, wide, len(rows)
        elif len(to) == 2:
            x1, y1 = to
            x2, y2 = x1 + wide, y1 + len(rows)
        elif len(to) == 4:
            x1, y1, x2, y2 = to
        else:
            raise TclError("wrong # coordinates: expected 2 or 4")
        for y in range(max(y1, 0), min(y2, self.height())):
            source = rows[(y - y1) % len(rows)]
            for x in range(max(x1, 0), min(x2, self.width())):
                item = source[(x - x1) % len(source)]
                self._pixels[y][x] = item if solid else self._colour_of(item)
        self._changed()

    def transparency_get(self, x: int, y: int) -> bool:
        """Whether ``(x, y)`` paints nothing and shows what is behind it."""
        return self._at(x, y) is TRANSPARENT

    def transparency_set(self, x: int, y: int, flag: bool) -> None:
        """Make ``(x, y)`` a hole, or paint it the image's foreground."""
        self._at(x, y)  # for the range check, and its Tk error message
        self._pixels[y][x] = (
            TRANSPARENT if flag else str(self._options["foreground"] or "white")
        )
        self._changed()

    # ------------------------------------------------------------ copying

    def copy(self) -> PhotoImage:
        """A new image with the same pixels and options."""
        clone = PhotoImage(master=self._master)
        clone._options.update(self._options)
        clone._pixels = self.rows()
        return clone

    def zoom(self, x: int, y: int | None = None) -> PhotoImage:
        """A copy with every pixel repeated ``x`` across and ``y`` down.

        ``y`` defaults to ``x``, as in Tk. Worth knowing what doubling means
        on this plane: two pixel rows make a cell, so ``zoom(2)`` turns each
        row into a whole cell rather than half of one.

        Raises:
            TclError: If either factor is not positive.
        """
        across, down = x, x if y is None else y
        if across <= 0 or down <= 0:
            raise TclError("zoom factors must be positive")
        clone = self.copy()
        clone._pixels = [
            [pixel for pixel in row for _ in range(across)]
            for row in self._pixels
            for _ in range(down)
        ]
        clone._remeasure()
        return clone

    def subsample(self, x: int, y: int | None = None) -> PhotoImage:
        """A copy keeping every ``x``-th pixel across and ``y``-th down.

        Raises:
            TclError: If either factor is not positive.
        """
        across, down = x, x if y is None else y
        if across <= 0 or down <= 0:
            raise TclError("subsample factors must be positive")
        clone = self.copy()
        clone._pixels = [row[::across] for row in self._pixels[::down]]
        clone._remeasure()
        return clone

    def _remeasure(self) -> None:
        """Put the width and height options back in step with the pixels."""
        self._options["width"] = self.width()
        self._options["height"] = self.height()

    # --------------------------------------------------------- whole file

    def data(self, palette: Mapping[str, str] | None = None) -> list[str]:
        """The image as rows of characters, for writing out or comparing.

        Args:
            palette: Colour to character. Without one every pixel that paints
                becomes ``#`` and every hole a space, which gives the shape
                of the image rather than its colours.
        """
        marks = dict(palette or {})
        return [
            "".join(" " if pixel is None else marks.get(pixel, "#") for pixel in row)
            for row in self._pixels
        ]

    def read(self, filename: str) -> None:
        """Replace the image with the rows in a text file."""
        self._read_file(filename)
        self._changed()

    def write(self, filename: str, palette: Mapping[str, str] | None = None) -> None:
        """Write the image out as rows of characters."""
        Path(filename).write_text(
            "\n".join(self.data(palette)) + "\n", encoding="utf-8"
        )


class BitmapImage(Image):
    """A two-colour image: one bit per pixel, which is what this plane holds.

    Tk's BitmapImage reads XBM, where every pixel is one bit - set pixels
    drawn in ``foreground``, clear ones in ``background``. That is the one
    image format that survives the move to a terminal intact, because a bit
    per pixel is exactly what a plane of half-cells can hold, so this reads
    real XBM rather than standing in for it. A clear bit with no
    ``background`` is a hole, so a shape does not paint a rectangle of
    background around itself.

    Args:
        name: The image's name, generated when omitted.
        cnf: Options as a dictionary, tkinter's older spelling.
        master: Any widget of the application the image belongs to.
        **kw: ``data`` as XBM source or rows of text, ``file`` to read it
            from, and ``foreground`` and ``background`` colours.

    Raises:
        TclError: If ``data`` is XBM that cannot be parsed, which Tk reports
            as ``format error in bitmap data``.
    """

    _type = "bitmap"

    def _init(self, options: dict[str, Any]) -> None:
        self._options = {
            "data": "",
            "file": "",
            "foreground": "white",
            "background": "",
            "maskdata": "",
            "maskfile": "",
        }
        #: The last source parsed, kept so that changing only the colours can
        #: redraw the same bits. Not an option: it is not one a caller sets,
        #: and it has no business in what configure() reports.
        self._source = ""
        self._configure(options)

    def _configure(self, options: dict[str, Any]) -> None:
        unknown = set(options) - set(self._options)
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        self._options.update(options)
        source = ""
        if options.get("file"):
            path = str(options["file"])
            try:
                source = Path(path).read_text(encoding="utf-8")
            except OSError as exc:
                raise TclError(
                    f'couldn\'t read bitmap file "{path}": '
                    f"{exc.strerror or 'no such file or directory'}"
                ) from None
        elif options.get("data"):
            # A list of rows is as legitimate as a string here, and str() on
            # one would have quietly drawn its repr - brackets, quotes and
            # all - as if it were a bitmap.
            source = "\n".join(str(row) for row in _rows_of(options["data"]))
        if source:
            self._set_bits(source)
        elif self._source and ("foreground" in options or "background" in options):
            self._set_bits(self._source)

    def _set_bits(self, source: str) -> None:
        """Parse ``source`` as XBM if it says it is, else as rows of text."""
        self._source = source
        on = str(self._options["foreground"] or "white")
        off = str(self._options["background"] or "") or TRANSPARENT
        if "#define" in source:
            # Anything declaring XBM dimensions is XBM, and XBM that does not
            # then carry its bits is broken rather than art: falling through
            # to the text path would have drawn the #define lines themselves.
            bits = _parse_xbm(source)
            self._pixels = [[on if bit else off for bit in row] for row in bits]
        else:
            rows = _rows_of(source.rstrip("\n"))
            width = max((len(row) for row in rows), default=0)
            self._pixels = [
                [
                    on if character not in " .0" else off
                    for character in row.ljust(width)
                ]
                for row in rows
            ]


def _parse_xbm(source: str) -> list[list[int]]:
    """Bits from XBM source, row by row.

    XBM packs each row into whole bytes, least significant bit leftmost, and
    pads the last byte of a row - so a 12-wide bitmap uses two bytes a row
    and four bits of each second byte are padding that must be dropped, or
    every row after the first is shifted.

    Raises:
        TclError: If the source has no dimensions or no data, reported the
            way Tk reports it: ``format error in bitmap data``.
    """
    width = height = None
    for line in source.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "#define":
            if parts[1].endswith("_width"):
                width = int(parts[2])
            elif parts[1].endswith("_height"):
                height = int(parts[2])
    start = source.find("{")
    end = source.rfind("}")
    if width is None or height is None or start < 0 or end < 0:
        raise TclError("format error in bitmap data")
    try:
        values = [
            int(item.strip(), 0)
            for item in source[start + 1 : end].split(",")
            if item.strip()
        ]
    except ValueError:
        raise TclError("format error in bitmap data") from None
    per_row = (width + 7) // 8
    if len(values) < per_row * height:
        raise TclError("format error in bitmap data")
    rows: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for byte in values[y * per_row : (y + 1) * per_row]:
            row.extend((byte >> bit) & 1 for bit in range(8))
        rows.append(row[:width])
    return rows
