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

from tkcurses._core import x11colors
from tkcurses._core.colors import from_linear, linear_of, rgb_for, rgb_of
from tkcurses._core.errors import TclError
from tkcurses._core.imagefiles import (
    decode,
    encode_gif,
    encode_png,
    encode_ppm,
    sniff,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

__all__ = ["BitmapImage", "Image", "PhotoImage"]

#: A pixel with nothing in it. Not a colour: the pixel declines to paint, and
#: what is behind it shows through. There is no alpha channel to zero.
TRANSPARENT = None

#: How many colours :meth:`PhotoImage.fit_pairs` adds between checks. One
#: compose pass costs about as much as several splits, so checking after
#: every single colour doubles the work to land a little nearer the budget.
_FIT_STEP = 4

#: All a curses attribute can name, and so every pair that can exist at once.
#: Used only as the fallback budget for :meth:`PhotoImage.fit_pairs` when
#: there is no terminal to ask; the live number is ColorManager.remaining.
_PAIR_CEILING = 255

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


def _split_once(
    boxes: list[list[tuple[str, int]]],
) -> bool:
    """Split the widest box in place. False when nothing can be split.

    One step of the median cut, kept separate so the palette can be grown a
    colour at a time. :meth:`PhotoImage.fit_pairs` needs the whole sequence
    of palettes, and rebuilding each from scratch was measured at 8.7
    seconds for one photograph - the splits are the same every time, so they
    are done once.
    """
    chosen: list[tuple[str, int]] | None = None
    widest = -1.0
    axis = 0
    for box in boxes:
        if len(box) < 2:
            continue
        for channel in range(3):
            levels = [_channel(colour, channel) for colour, _ in box]
            # Weighted by pixels, so the box that covers more of the picture
            # is split first when two are equally spread.
            spread = (max(levels) - min(levels)) * sum(count for _, count in box) ** 0.5
            if spread > widest:
                chosen, widest, axis = box, spread, channel
    if chosen is None:
        return False
    chosen.sort(key=lambda item: _channel(item[0], axis))
    half = sum(count for _, count in chosen) / 2
    running = 0
    cut = 1
    for index, (_, count) in enumerate(chosen):
        running += count
        if running >= half:
            cut = max(1, min(index, len(chosen) - 1))
            break
    boxes.remove(chosen)
    boxes.append(chosen[:cut])
    boxes.append(chosen[cut:])
    return True


def _mapping_of(boxes: list[list[tuple[str, int]]]) -> dict[str, str]:
    """Every colour mapped to the pixel-weighted mean of its box."""
    mapping: dict[str, str] = {}
    for box in boxes:
        total = sum(count for _, count in box) or 1
        averaged = tuple(
            round(
                sum(_channel(colour, channel) * count for colour, count in box) / total
            )
            for channel in range(3)
        )
        stands_in = f"#{averaged[0]:02x}{averaged[1]:02x}{averaged[2]:02x}"
        for colour, _ in box:
            mapping[colour] = stands_in
    return mapping


def _spans(source: int, target: int) -> list[list[tuple[int, float]]]:
    """For each output index, which input indices it covers and by how much.

    The whole of arbitrary-ratio resampling: output pixel ``i`` covers the
    half-open input range ``[i * source / target, (i + 1) * source / target)``,
    which generally starts and ends part way through an input pixel. Each
    input index is paired with the fraction of itself that falls inside.

    Worked out once per axis rather than per pixel, because the spans are the
    same down every column and along every row.
    """
    spans: list[list[tuple[int, float]]] = []
    scale = source / target
    for index in range(target):
        start = index * scale
        stop = start + scale
        first = min(int(start), source - 1)
        # The epsilon keeps an exact boundary - which a whole-number ratio
        # hits on every pixel - from reaching into the next input pixel for a
        # zero-width sliver.
        last = min(int(stop - 1e-9), source - 1)
        covered = [
            (where, min(stop, where + 1) - max(start, where))
            for where in range(first, last + 1)
            if min(stop, where + 1) > max(start, where)
        ]
        spans.append(covered or [(first, 1.0)])
    return spans


def _median_cut(counts: dict[str, int], colours: int) -> dict[str, str]:
    """Choose ``colours`` representatives for the colours in ``counts``.

    Returns a mapping from every colour present to the one that stands in for
    it. ``counts`` is colour to pixel count, and the counts matter: a colour
    covering half the picture has to survive a split that a hundred stray
    colours would otherwise win.

    The classic median cut. Two choices inside it were measured rather than
    reasoned about, because the reasoning was wrong the first time:

    **Which box to split** is decided by its widest channel scaled by the
    square root of the pixels it covers. The weighting earns its place: on
    mickey.gif reduced to 53x33, dropping it costs 15.36 against 14.45 at 16
    colours and 11.21 against 8.98 at 32.

    **Where to split it** is the median *pixel* - walk the sorted colours
    accumulating counts, cut where half the pixels have gone past. This was
    first documented here as the obviously right choice, on the grounds that
    cutting at the middle of the *list* spends the palette on rare colours.
    Measured, that is not true: median-colour is better on mickey at 8 and 16
    colours (20.18 against 22.79, 13.11 against 14.45) and the two are within
    noise of each other on earth.gif. Across six cases it is 3 wins to 2 with
    a tie, which is a wash.

    Median-pixel is kept because it wins in the range that actually gets
    used: :meth:`PhotoImage.fit_pairs` settles on 24 to 29 colours for a
    full-screen photograph, and at 32 colours median-pixel leads on mickey
    (8.98 against 9.94) and ties on earth. It is a close-run choice and not
    a principle, which is the honest thing to record.
    """
    boxes = [list(counts.items())]
    while len(boxes) < colours and _split_once(boxes):
        pass
    return _mapping_of(boxes)


def _channel(colour: str, index: int) -> int:
    """One channel of a colour, or 0 for anything unreadable."""
    parts = rgb_of(colour)
    return 0 if parts is None else parts[index]


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
        #: Counts changes, so something derived from the pixels - a palette
        #: fitted to the colour pairs left - knows when it is stale.
        self._revision = 0
        #: The colours last chosen to fit the colour pairs left, and what
        #: they were chosen for.
        self._fit_cache: tuple[Any, dict[str, str] | None] | None = None
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
        """``'photo'`` or ``'bitmap'``, as Tk names its image types.

        Raises:
            TclError: If the image has been deleted, in Tk's words.
        """
        self._check_exists()
        return self._type

    # -------------------------------------------------------------- shape

    def width(self) -> int:
        """The image's width in pixels, which is also its width in cells.

        Raises:
            TclError: If the image has been deleted, in Tk's words.
        """
        self._check_exists()
        return len(self._pixels[0]) if self._pixels else 0

    def height(self) -> int:
        """The image's height in pixels. Two pixel rows make a cell.

        Raises:
            TclError: If the image has been deleted, in Tk's words.
        """
        self._check_exists()
        return len(self._pixels)

    # ----------------------------------------------------------- deleting

    #: Set by ``image delete``: the name is gone, and this object, as
    #: tkinter's does, answers that it no longer exists.
    _deleted = False

    def _check_exists(self) -> None:
        if self._deleted:
            raise TclError(f'image "{self._name}" does not exist')

    def _delete(self) -> None:
        """``image delete``: drop the name, and repaint whatever showed it.

        A widget showing it keeps its name and its size and draws nothing
        where the image was, as Tk's does.
        """
        self._deleted = True
        if self._tk.images.get(self._name) is self:
            del self._tk.images[self._name]
        if self._tk.created_images.get(self._name) is self:
            del self._tk.created_images[self._name]
        for user in list(self._users):
            redraw = getattr(user, "_redraw", None)
            if redraw is not None:
                redraw()
        self._users.clear()

    def _in_use(self) -> bool:
        """Whether a living widget shows this image: ``image inuse``."""
        for user in list(self._users):
            exists = getattr(user, "winfo_exists", None)
            if exists is None or exists():
                return True
        return False

    def cell_height(self) -> int:
        """Rows of terminal needed to show it: two pixel rows to a cell, a lone
        pixel row rounding up.

        TkCurses extension:
            tkinter's images have no such method.
        """
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
        self._revision += 1
        for callback in list(self._users.values()):
            callback()

    # ------------------------------------------------------------ reading

    def _at(self, x: int, y: int) -> Pixel:
        """The pixel at ``(x, y)``, checked against the image's extent."""
        if not (0 <= y < self.height() and 0 <= x < self.width()):
            raise TclError(f"{self._name} get: coordinates out of range")
        return self._pixels[y][x]

    def rows(self) -> list[Row]:
        """A copy of the pixels, row by row.

        TkCurses extension:
            tkinter's images have no such method.
        """
        return [list(row) for row in self._pixels]

    def lit(
        self, region: tuple[int, int, int, int] | None = None
    ) -> dict[tuple[int, int], str]:
        """Every pixel that paints, keyed by ``(x, y)`` - what a widget composes
        to draw the image.

        Args:
            region: ``(x0, y0, x1, y1)`` in pixels, half-open, to limit the
                result to. Pass the part that can actually be shown: a large
                picture otherwise hands over every pixel on every repaint.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # Every pixel that paints, keyed by ``(x, y)``.
        #
        # Exactly what :func:`~tkcurses._core.canvas.compose` takes, which is
        # the point of sharing the plane: a widget draws an image by composing
        # this, the same way a canvas draws a circle.
        #
        # Args:
        #     region: ``(x0, y0, x1, y1)`` in pixels, half-open, to limit the
        #         result to. **A caller drawing into a window should pass the
        #         part it can actually show.** Without it a 320x200 photograph
        #         hands over 64,000 pixels and composes 32,000 cells on every
        #         repaint, of which a 120x24 window keeps 9% - which is the
        #         same fault TkCurses-g9w found in Text and Canvas, doing work
        #         proportional to the content instead of to the window.
        if region is None:
            return {
                (x, y): colour
                for y, row in enumerate(self._pixels)
                for x, colour in enumerate(row)
                if colour is not None
            }
        x0, y0, x1, y1 = region
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, self.width()), min(y1, self.height())
        return {
            (x, y): colour
            for y in range(y0, y1)
            for x, colour in enumerate(self._pixels[y][x0:x1], start=x0)
            if colour is not None
        }


#: Tk's complaint when ``copy`` is given more numbers than an option takes:
#: measured, the extra one is read as the next argument and the whole
#: command is refused.
_COPY_USAGE = (
    'wrong # args: should be "{} copy source-image ?-compositingrule rule? '
    '?-from x1 y1 x2 y2? ?-to x1 y1 x2 y2? ?-zoom x y? ?-subsample x y?"'
)


#: The formats Tk 9.0.2 has for a photo, and which way each goes. ``svg``
#: is read only, and ``default`` - Tk's list of rows - only as a string.
_FORMATS = ("default", "gif", "png", "ppm", "svg")
#: What :func:`~tkcurses._core.imagefiles.sniff` calls each format Tk names.
_SNIFFED = {"gif": "gif", "png": "png", "ppm": "netpbm"}


def _format_word(format: Any) -> str | None:
    """A ``-format`` value's format name, lower case; the options after it
    (``"gif -index 1"``) are Tk's own for that format and ignored here."""
    words = str(format or "").split()
    return words[0].lower() if words else None


def true_rgb(spec: Any) -> tuple[int, int, int] | None:
    """The RGB a colour names, as Tk would store it: ``#rgb`` forms and the
    X11 names, before any terminal has had a say. None when it names none.

    :func:`~tkcurses._core.colors.rgb_of` answers what a terminal shows
    instead; a written image wants the colour that was asked for.
    """
    text = str(spec)
    if text.startswith("#"):
        return rgb_for(text)
    name = x11colors.lookup(text)
    return None if name is None else x11colors.NAMES[name]


def _grey(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Tk's grey for a colour: ``(11r + 16g + 5b + 16) >> 5``, from
    ``ImgGetPhoto`` in tkImgPhoto.c, under ``-grayscale``."""
    level = (rgb[0] * 11 + rgb[1] * 16 + rgb[2] * 5 + 16) >> 5
    return level, level, level


def _open_failure(path: str, exc: OSError) -> TclError:
    """Tk's words for a file it could not open."""
    reason = (exc.strerror or "no such file or directory").lower()
    return TclError(f'couldn\'t open "{path}": {reason}')


def _corner_values(image: str, option: str, values: Sequence[int]) -> list[int]:
    """``-from`` or ``-to``'s numbers, as two or four.

    Measured on Tk 9.0.2: one number stands for both of a pair and a third
    for the fourth, so ``(1,)`` is ``(1, 1)`` and ``(0, 0, 1)`` is
    ``(0, 0, 1, 1)``.
    """
    numbers = [int(value) for value in values]
    if not numbers:
        raise TclError(f'the "{option}" option requires one to four integer values')
    if len(numbers) > 4:
        raise TclError(_COPY_USAGE.format(image))
    if any(number < 0 for number in numbers):
        raise TclError(f"value(s) for the {option} option must be non-negative")
    if len(numbers) % 2:
        numbers.append(numbers[-1])
    return numbers


def _factor_pair(
    image: str, option: str, factor: int | Sequence[int] | None
) -> tuple[int, int]:
    """``-zoom`` or ``-subsample`` as ``(across, down)``; one number is both."""
    if factor is None:
        return 1, 1
    numbers = [int(factor)] if isinstance(factor, int) else [int(n) for n in factor]
    if not numbers:
        raise TclError(f'the "{option}" option requires one or two integer values')
    if len(numbers) > 2:
        raise TclError(_COPY_USAGE.format(image))
    return numbers[0], numbers[-1]


class PhotoImage(Image):
    """A plane of coloured pixels.

    A pixel is one column wide and half a row tall. The image reads and
    writes Tk's formats - PNG, GIF and PPM files, and rows of colours - so
    what tkinter saves this opens, and the other way round.

    Args:
        name: The image's name, generated when omitted.
        cnf: Options as a dictionary, tkinter's older spelling.
        master: Any widget of the application the image belongs to.
        **kw: ``width`` and ``height`` in pixels; ``data`` as rows of
            colours (``"{red blue} {green white}"``) or image data, bytes
            or base64; ``file`` to read; ``format`` naming the format
            ``data`` or ``file`` must be in; ``palette`` mapping characters
            to colours, which makes ``data`` and ``file`` character art; and
            ``foreground`` for what an unmapped character paints.

    Raises:
        TclError: If ``file`` cannot be read, or ``data`` is neither rows
            of colours nor an image, in Tk's words.

    Differences from tkinter:
        A pixel made transparent forgets its colour, so :meth:`data`
        reports it as ``#000000``; Tk keeps the colour and reports that.
        Tk's ``palette`` sets how many colours a display may use; here it is
        the character art's key. Tk's ``gamma`` is not taken.

    TkCurses extension:
        Character art: with a ``palette``, rows of characters each stand
        for a colour, and :meth:`data` and :meth:`write` give art back for
        a ``palette`` of their own.

    Example:
        >>> photo = PhotoImage(data=["#.#", ".#."],     # doctest: +SKIP
        ...                    palette={"#": "cyan"})
        >>> photo.width(), photo.height(), photo.cell_height()
        (3, 2, 1)

    Sample output:
        picture = tk.PhotoImage(
            data=["..rr..", ".rrrr.", "rryyrr", ".gggg."],
            palette={"r": "red", "y": "yellow", "g": "green"},
        )
        tk.Label(root, image=picture).pack()
    """

    _type = "photo"

    def _init(self, options: dict[str, Any]) -> None:
        self._options = {
            "width": 0,
            "height": 0,
            "data": "",
            "file": "",
            "format": "",
            "palette": None,
            "foreground": "white",
            "background": "",
        }
        #: The width and height a caller asked for, 0 where none was. The
        #: options cannot answer this: they follow the pixels. It decides
        #: whether :meth:`copy_replace` may grow the image - measured on Tk
        #: 9.0.2, an image made with ``width=2, height=2`` keeps that size
        #: and clips what is copied in, and one made without grows to fit.
        self._user_size = {"width": 0, "height": 0}
        self._configure(options)

    def _configure(self, options: dict[str, Any]) -> None:
        unknown = set(options) - set(self._options)
        if unknown:
            raise TclError(f'unknown option "-{sorted(unknown)[0]}"')
        self._options.update(options)
        for axis in ("width", "height"):
            if axis in options:
                self._user_size[axis] = int(options[axis] or 0)
        if options.get("file"):
            self._read_file(str(options["file"]))
        elif options.get("data"):
            self._load(self._parse_data(options["data"], self._options["format"]))
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

    def _load(self, rows: list[Row]) -> None:
        """Replace the image with ``rows``, as Tk's ``-data`` and ``-file``
        do: an axis given a size keeps it, and the rest takes the rows'."""
        width = len(rows[0]) if rows else 0
        height = len(rows)
        if self._options["palette"] is not None:
            width = max((len(row) for row in rows), default=0)
        size = {"width": width, "height": height}
        for axis in size:
            if self._user_size[axis]:
                size[axis] = self._user_size[axis]
        self._pixels = [
            [
                rows[y][x] if y < len(rows) and x < len(rows[y]) else TRANSPARENT
                for x in range(size["width"])
            ]
            for y in range(size["height"])
        ]
        self._options["width"] = size["width"]
        self._options["height"] = size["height"]

    def _parse_data(self, data: Any, format: Any = None) -> list[Row]:
        """Pixels from what Tk's ``put`` and ``-data`` take.

        That is image data - PNG, GIF or PPM bytes, or the same as base64 -
        or rows of colours: a list of rows, each a list of colours or a
        string of them (``"red blue"``), or one string of rows in braces
        (``"{red blue} {green white}"``), as measured on Tk 9.0.2. With a
        ``palette`` it is character art instead: each row a string of
        characters, or one string of rows split at newlines.

        Raises:
            TclError: For rows of different lengths, a colour Tk would not
                know, or image data that is not in ``format``, in Tk's words.
        """
        if self._options["palette"] is not None and not isinstance(
            data, (bytes, bytearray)
        ):
            return [[self._colour_of(item) for item in row] for row in _rows_of(data)]
        word = _format_word(format)
        image = self._image_bytes(data)
        if image is not None:
            kind = sniff(image)
            if word in _SNIFFED and kind != _SNIFFED[word]:
                raise TclError(f"couldn't recognize image data in {word} format")
            if kind is not None:
                return decode(image)
        if isinstance(data, (bytes, bytearray)):
            raise TclError("couldn't recognize image data")
        from tkcurses import _tcl_list

        rows = _tcl_list(data) if isinstance(data, str) else list(data)
        parsed = [
            [
                self._colour_of(item)
                for item in (_tcl_list(row) if isinstance(row, str) else row)
            ]
            for row in rows
        ]
        for number, row in enumerate(parsed):
            if len(row) != len(parsed[0]):
                raise TclError(
                    f"invalid row # {number}: all rows must have the same number"
                    " of elements"
                )
            for pixel in row:
                if pixel is not TRANSPARENT and true_rgb(pixel) is None:
                    raise TclError(f'invalid color name "{pixel}"')
        return parsed

    @staticmethod
    def _image_bytes(data: Any) -> bytes | None:
        """``data`` as image file bytes, if it is some or base64 of some."""
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if not isinstance(data, str) or len(data) < 8 or " " in data.strip():
            return None
        import base64
        import binascii

        try:
            raw = base64.b64decode(data, validate=False)
        except (binascii.Error, ValueError):
            return None
        return raw if sniff(raw) is not None else None

    def _read_file(self, path: str) -> None:
        """Load an image file, or rows of art from a text one.

        Sniffed from the content, never from the name - which is what Tk
        does: measured on 9.0.2, opening a PNG while saying ``format="gif"``
        still fails with ``couldn't recognize data in image file``, so it is
        plainly reading the bytes.

        A file in none of the image formats is read as rows of characters -
        but only when a ``palette`` has been declared, because that is how a
        caller says "this is character art, and here is what the characters
        mean". Without one it is refused, which is what Tk does: measured,
        ``PhotoImage(file=)`` on a text file raises ``couldn't recognize
        data in image file``. The rule keeps art loadable without making
        every text file on the disk a valid image - an image viewer that
        opened a README as a 37-pixel-wide picture is what that cost.
        """
        self._load(self._file_rows(path, self._options["format"]))

    def _file_rows(self, path: str, format: Any = None) -> list[Row]:
        """A file's pixels: an image file, or character art when a
        ``palette`` says how to read one.

        Raises:
            TclError: In Tk's words, for a file that cannot be opened, a
                format Tk has no reader for, or content that is not in the
                format named - or in any, when none is.
        """
        word = _format_word(format)
        if word == "default":
            raise TclError("-file option isn't supported for default images")
        if word is not None and word not in _SNIFFED:
            raise TclError(f'image file format "{word}" is not supported')
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            raise _open_failure(path, exc) from None
        unrecognised = TclError(f'couldn\'t recognize data in image file "{path}"')
        kind = sniff(raw)
        if word is not None and kind != _SNIFFED[word]:
            raise unrecognised
        if kind is not None:
            return decode(raw, path)
        if self._options.get("palette") is None:
            raise unrecognised
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise unrecognised from None
        return [
            [self._colour_of(item) for item in row]
            for row in text.rstrip("\n").split("\n")
        ]

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

    def put(self, data: Any, to: Sequence[int] | None = None) -> None:
        """Write colours into the image.

        Args:
            data: Rows of colours as Tk takes them - ``"red"`` for one
                pixel, ``"{red blue} {green white}"`` or
                ``[["red", "blue"], ["green", "white"]]`` for rows - or
                image data, PNG, GIF or PPM, as bytes or base64. With a
                ``palette``, rows of characters instead.
            to: ``(x, y)`` to place at, or ``(x1, y1, x2, y2)`` to fill:
                rows smaller than the region tile across it. Without it the
                data goes at the origin.

        An image with no ``width`` or ``height`` of its own grows to take
        what is put, as in Tk; one given a size keeps it and clips.

        Raises:
            TclError: In Tk's words, for rows of different lengths, a colour
                Tk would not know, or a ``to`` of more than four numbers.

        TkCurses extension:
            ``None`` or ``" "`` in a row is a hole, painting nothing.
        """
        if (
            self._options["palette"] is not None
            and isinstance(data, str)
            and "\n" not in data
        ):
            # One colour, put("red", to=...), even where rows are art: a
            # row of art is given as a list.
            rows = [[self._colour_of(data) if data in ("", " ") else data]]
        else:
            rows = self._parse_data(data)
        rows = [row for row in rows if row]
        if not rows:
            return
        wide = max(len(row) for row in rows)
        if to is None:
            x1, y1, x2, y2 = 0, 0, wide, len(rows)
        else:
            corners = _corner_values(self._name, "-to", to)
            x1, y1 = corners[0], corners[1]
            if len(to) <= 2:
                x2, y2 = x1 + wide, y1 + len(rows)
            else:
                x2, y2 = corners[2], corners[3]
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
        size = {"width": self.width(), "height": self.height()}
        for axis, far in (("width", x2), ("height", y2)):
            if not self._user_size[axis]:
                size[axis] = max(size[axis], far)
        if (size["width"], size["height"]) != (self.width(), self.height()):
            self._resize(size["width"], size["height"])
        for y in range(max(y1, 0), min(y2, self.height())):
            source = rows[(y - y1) % len(rows)]
            for x in range(max(x1, 0), min(x2, self.width())):
                self._pixels[y][x] = source[(x - x1) % len(source)]
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

    def copy(
        self,
        *,
        from_coords: Sequence[int] | None = None,
        zoom: int | Sequence[int] | None = None,
        subsample: int | Sequence[int] | None = None,
    ) -> PhotoImage:
        """A new image with the same pixels and options.

        The keywords are Python 3.13's, and mean what they mean to
        :meth:`copy_replace`, which this is built on as it is in tkinter.
        """
        clone = PhotoImage(master=self._master)
        clone._options.update(self._options)
        clone.copy_replace(
            self,
            from_coords=from_coords,
            zoom=zoom,
            subsample=subsample,
            compositingrule="set",
        )
        clone._remeasure()
        return clone

    def zoom(
        self, x: int, y: int | None = None, *, from_coords: Sequence[int] | None = None
    ) -> PhotoImage:
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
        return self.copy(from_coords=from_coords, zoom=(across, down))

    def subsample(
        self, x: int, y: int | None = None, *, from_coords: Sequence[int] | None = None
    ) -> PhotoImage:
        """A copy keeping every ``x``-th pixel across and ``y``-th down.

        Raises:
            TclError: If either factor is not positive.
        """
        across, down = x, x if y is None else y
        if across <= 0 or down <= 0:
            raise TclError("subsample factors must be positive")
        return self.copy(from_coords=from_coords, subsample=(across, down))

    def copy_replace(
        self,
        sourceImage: PhotoImage | str,
        *,
        from_coords: Sequence[int] | None = None,
        to: Sequence[int] | None = None,
        shrink: bool = False,
        zoom: int | Sequence[int] | None = None,
        subsample: int | Sequence[int] | None = None,
        compositingrule: str | None = None,
    ) -> None:
        """Copy a region of another image into this one, in place.

        Python 3.13's spelling of Tk's ``$photo copy``. Every rule below was
        measured on Tk 9.0.2 rather than read, because ``photo(n)`` leaves
        most of them out:

        - ``from_coords`` and ``to`` take one to four numbers. One is used
          for both of a pair and a third stands for the fourth, so ``(1,)``
          is ``(1, 1)`` and ``(0, 0, 1)`` is ``(0, 0, 1, 1)``. Reversed
          corners are put in order. A region outside the source is refused.
        - The source region is subsampled, then zoomed. A negative subsample
          walks that axis backwards, mirroring it; a zero copies nothing.
        - ``to`` with two numbers places the region; with four it tiles it
          across that rectangle, starting at the rectangle's corner.
        - An image with no ``width``/``height`` of its own grows to take the
          region, and with ``shrink`` becomes exactly as large as the
          region's far corner. One whose size was given keeps it, and clips.
        - ``overlay``, the default, lets the destination show through the
          source's holes; ``set`` copies the holes too.

        Args:
            sourceImage: A PhotoImage, or the name of one. It may be this
                image: the region is read before anything is written.

        Raises:
            TclError: With Tk's message, for a source that is not a photo
                image, coordinates that are negative or of the wrong count,
                a ``from_coords`` outside the source, a zoom that is not
                positive, or a compositing rule other than the two.
        """
        source = self._photo_named(sourceImage)
        rule = compositingrule or "overlay"
        if rule not in ("overlay", "set"):
            raise TclError(f'bad compositing rule "{rule}": must be overlay or set')
        self._copy_block(
            source._pixels,
            from_coords=from_coords,
            to=to,
            shrink=shrink,
            zoom=zoom,
            subsample=subsample,
            rule=rule,
        )

    def _copy_block(
        self,
        pixels: list[Row],
        *,
        from_coords: Sequence[int] | None = None,
        to: Sequence[int] | None = None,
        shrink: bool = False,
        zoom: int | Sequence[int] | None = None,
        subsample: int | Sequence[int] | None = None,
        rule: str = "overlay",
    ) -> None:
        """:meth:`copy_replace`'s work on rows of pixels, which is also
        :meth:`read`'s once the file is decoded: Tk's ``read`` takes the
        same ``-from``, ``-to`` and ``-shrink``, measured to behave alike."""
        source_width = len(pixels[0]) if pixels else 0
        source_height = len(pixels)
        across, down = _factor_pair(self._name, "-subsample", subsample)
        wide, tall = _factor_pair(self._name, "-zoom", zoom)
        if wide <= 0 or tall <= 0:
            raise TclError("value(s) for the -zoom option must be positive")
        place = None if to is None else _corner_values(self._name, "-to", to)

        x1, y1, x2, y2 = 0, 0, source_width, source_height
        if from_coords is not None:
            given = _corner_values(self._name, "-from", from_coords)
            x1, y1 = given[0], given[1]
            if len(given) == 4:
                x2, y2 = given[2], given[3]
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            if x2 > source_width or y2 > source_height:
                raise TclError(
                    "coordinates for -from option extend outside source image"
                )
        if across == 0 or down == 0:
            return

        columns = range(x1, x2, across) if across > 0 else range(x2 - 1, x1 - 1, across)
        lines = range(y1, y2, down) if down > 0 else range(y2 - 1, y1 - 1, down)
        block = [
            [pixel for x in columns for pixel in [pixels[y][x]] * wide]
            for y in lines
            for _ in range(tall)
        ]
        width = len(block[0]) if block else 0
        height = len(block)
        if width == 0 or height == 0:
            return

        if place is None:
            tx1, ty1, tx2, ty2 = 0, 0, width, height
        elif len(place) == 2:
            tx1, ty1 = place
            tx2, ty2 = tx1 + width, ty1 + height
        else:
            tx1, tx2 = min(place[0], place[2]), max(place[0], place[2])
            ty1, ty2 = min(place[1], place[3]), max(place[1], place[3])

        size = {"width": self.width(), "height": self.height()}
        for axis, far in (("width", tx2), ("height", ty2)):
            if self._user_size[axis]:
                continue
            size[axis] = far if shrink else max(size[axis], far)
        if (size["width"], size["height"]) != (self.width(), self.height()):
            self._resize(size["width"], size["height"])

        span = min(tx2, size["width"]) - tx1
        if span > 0:
            repeats = -(-span // width)
            for y in range(ty1, min(ty2, size["height"])):
                segment = (block[(y - ty1) % height] * repeats)[:span]
                target = self._pixels[y]
                if rule == "set" or TRANSPARENT not in segment:
                    target[tx1 : tx1 + span] = segment
                    continue
                for offset, pixel in enumerate(segment):
                    if pixel is not TRANSPARENT:
                        target[tx1 + offset] = pixel
        self._changed()

    def _photo_named(self, image: PhotoImage | str) -> PhotoImage:
        """The PhotoImage ``image`` is or names, as Tk resolves a source."""
        if isinstance(image, PhotoImage):
            return image
        found = self._tk.images.get(str(image))
        if not isinstance(found, PhotoImage):
            raise TclError(f'image "{image}" does not exist or is not a photo image')
        return found

    def reduce(self, x: int, y: int | None = None) -> PhotoImage:
        """A copy averaged down by ``x`` across and ``y`` down.

        The counterpart to :meth:`subsample`, which keeps every n-th pixel and
        throws the rest away. Subsample is Tk's and exact; for fitting a
        photograph to a window, averaging keeps far more of the picture, from
        256 colours up. At eight colours the two are much the same.

        A block that is more than half holes stays a hole, so a silhouette
        keeps its shape instead of growing a fringe of half-lit edges.

        Raises:
            TclError: If either factor is not positive.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # A copy averaged down by ``x`` across and ``y`` down.
        #
        # The counterpart to :meth:`subsample`, which keeps every n-th pixel
        # and throws the rest away. Both are wanted: subsample is Tk's, it is
        # exact, and it is what a caller porting tkinter code reaches for -
        # but for fitting a photograph to a window it discards most of the
        # picture, and what survives is whichever pixels happened to land on
        # the grid.
        #
        # Measured on the perl-Tk demo images, 320x200 reduced by six, scored
        # against a Lanczos reference computed in linear light *after*
        # quantising to the terminal palette - so this is the error a person
        # actually sees, against a resampling this code does not share any
        # arithmetic with:
        #
        #     picture      depth       subsample   reduce   better by
        #     earth.gif    8 colours       25085    25363       -1%
        #                  256              2293      494       78%
        #                  truecolor        2106      260       88%
        #     mickey.gif   8 colours       10969     9569       13%
        #                  256              7405     1299       82%
        #                  truecolor        7073      680       90%
        #
        # Averaging wins decisively from 256 colours up, and mickey.gif is the
        # interesting case: flat cartoon colour with hard edges is where
        # dropping pixels should keep the palette intact and averaging should
        # muddy it, and it still loses by 90%.
        #
        # **At eight colours it is a wash**, and on earth.gif fractionally
        # worse. With only eight colours to land on, a careful average and a
        # dropped pixel usually quantise to the same entry, and where they
        # differ it is a coin toss. The earlier version of this table claimed a
        # win at every depth; it was measured before :meth:`_average` worked in
        # linear light and against a reference built the same way, which
        # flattered it.
        #
        # A block that is more than half holes stays a hole, so a silhouette
        # keeps its shape instead of growing a fringe of half-lit edges.
        #
        # Raises:
        #     TclError: If either factor is not positive.
        across, down = x, x if y is None else y
        if across <= 0 or down <= 0:
            raise TclError("reduce factors must be positive")
        clone = self.copy()
        clone._pixels = [
            [
                self._average(column, row, across, down)
                for column in range(0, self.width() - across + 1, across)
            ]
            for row in range(0, self.height() - down + 1, down)
        ]
        clone._remeasure()
        return clone

    def _average(self, x: int, y: int, across: int, down: int) -> Pixel:
        """The mean colour of one block, or None where it is mostly hole.

        **Averaged in linear light, not in sRGB bytes.** sRGB carries roughly
        a 2.2 gamma, so the mean of two bytes is not the byte of the mean
        brightness - and the error is always in the same direction, darker.
        Measured on a 50/50 black-and-white checkerboard reduced to one
        pixel: averaging the bytes gives 127 where the light says 188.

        It shows up wherever a block spans an edge, so it is worst on exactly
        the pictures that look drawn rather than photographed. Per channel,
        against the light-correct answer, before this was fixed:

            mickey.gif    mean 14.69   max 74
            earth.gif     mean  3.10   max 32
            gradient.png  mean  0.66   max  1
        """
        red = green = blue = 0.0
        lit = 0
        for row in self._pixels[y : y + down]:
            for pixel in row[x : x + across]:
                if pixel is None:
                    continue
                parts = rgb_of(pixel)
                if parts is None:
                    continue
                red += linear_of(parts[0])
                green += linear_of(parts[1])
                blue += linear_of(parts[2])
                lit += 1
        if lit * 2 <= across * down:
            # More hole than colour. Averaging the few lit pixels here would
            # spread a shape's edge outwards by half a block on every side.
            return TRANSPARENT
        return (
            f"#{from_linear(red / lit):02x}"
            f"{from_linear(green / lit):02x}"
            f"{from_linear(blue / lit):02x}"
        )

    def resize(self, width: int, height: int) -> PhotoImage:
        """A copy resampled to exactly ``width`` by ``height`` pixels.

        **The one to use when fitting a picture to a space.** :meth:`reduce`
        takes a whole-number factor, so a picture lands on whatever size a whole
        number happens to give rather than the size on offer. Each output pixel
        here is the average of the input it covers, so the ratio need not be
        whole. A block more than half hole stays a hole, as with :meth:`reduce`.

        Raises:
            TclError: If either dimension is not positive.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # A copy resampled to exactly ``width`` by ``height`` pixels.
        #
        # **The one to use when fitting a picture to a space.** :meth:`reduce`
        # takes a whole-number factor, so a picture lands on whatever size a
        # whole number happens to give rather than the size on offer. Measured
        # on mickey.gif, 320 pixels wide:
        #
        #     panel offered   reduce() delivers   width used
        #               120           106 cells          88%
        #               100            80 cells          80%
        #                90            80 cells          88%
        #
        # A fifth of the width thrown away at a 100-cell panel, and with it a
        # fifth of the detail, for nothing but arithmetic.
        #
        # It costs accuracy even at a size a whole number fits. An integer
        # factor covers exactly three input pixels where the true ratio might
        # be 3.019, so the sampling grid drifts across the picture and the
        # remainder is dropped. Scored perceptually on mickey at 106x66,
        # reduce() differed from a correct box filter by 16.16 - more than a
        # correct box filter differs from Lanczos, at 9.12.
        #
        # Each output pixel is the average of the input it covers, weighted by
        # how much of each input pixel falls inside it, so the ratio need not
        # be whole. In linear light, like :meth:`reduce` - see
        # :func:`~tkcurses._core.colors.to_linear`. A block more than half hole
        # stays a hole, by the same rule and for the same reason.
        #
        # Raises:
        #     TclError: If either dimension is not positive.
        if width <= 0 or height <= 0:
            raise TclError("resize needs a positive width and height")
        if not self._pixels or not self._pixels[0]:
            return self.copy()
        columns = _spans(self.width(), width)
        rows = _spans(self.height(), height)
        # Converted once per distinct colour rather than once per visit. A
        # pixel on a block boundary is looked at by several output pixels,
        # and parsing its hex each time was most of the cost: measured, 231ms
        # against 33ms for one photograph.
        linear: dict[str, tuple[float, float, float] | None] = {}
        for line in self._pixels:
            for pixel in line:
                if pixel is not None and pixel not in linear:
                    parts = rgb_of(pixel)
                    linear[pixel] = (
                        None
                        if parts is None
                        else (
                            linear_of(parts[0]),
                            linear_of(parts[1]),
                            linear_of(parts[2]),
                        )
                    )
        clone = self.copy()
        clone._pixels = [
            [self._area(column, row, linear) for column in columns] for row in rows
        ]
        clone._remeasure()
        return clone

    def _area(
        self,
        columns: list[tuple[int, float]],
        rows: list[tuple[int, float]],
        linear: dict[str, tuple[float, float, float] | None],
    ) -> Pixel:
        """The weighted mean of one fractional block, or None where mostly hole."""
        red = green = blue = 0.0
        lit = total = 0.0
        for y, down in rows:
            line = self._pixels[y]
            for x, across in columns:
                weight = down * across
                total += weight
                pixel = line[x]
                if pixel is None:
                    continue
                parts = linear.get(pixel)
                if parts is None:
                    continue
                red += parts[0] * weight
                green += parts[1] * weight
                blue += parts[2] * weight
                lit += weight
        if lit * 2 <= total:
            return TRANSPARENT
        return (
            f"#{from_linear(red / lit):02x}"
            f"{from_linear(green / lit):02x}"
            f"{from_linear(blue / lit):02x}"
        )

    def quantize(self, colours: int) -> PhotoImage:
        """A copy using at most ``colours`` colours, chosen from this picture.

        Where :meth:`dither` snaps every pixel to a colour the terminal already
        has, this picks a small palette out of the picture itself - which is only
        worth doing where those colours can be shown exactly, on a terminal with
        true colour. Snapped to a smaller palette afterwards, the two errors add
        up and the picture is worse than not doing it at all.

        An image already within ``colours`` comes back unchanged, so this is
        safe to apply to flat art that never needed it. Holes stay holes.

        Args:
            colours: The most colours the result may use.

        Raises:
            TclError: If ``colours`` is not positive.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # A copy using at most ``colours`` colours, chosen from this picture.
        #
        # The counterpart to :meth:`dither`, and the difference between them is
        # *whose* palette is used. ``dither`` snaps every pixel to a colour the
        # terminal already has; this picks a small palette **out of the picture
        # itself**, which is only worth doing if those colours can then be
        # reproduced exactly.
        #
        # That is the whole point, and it is easy to get backwards. A palette of
        # sixteen colours taken from the picture and then snapped to the 256
        # cube is *worse than not doing it at all*, because the two errors
        # stack. Measured, mean per-pixel error against the unquantised image,
        # with the distinct ``(fg, bg)`` pairs each needs:
        #
        #     picture   256 cube, shared   16 taken then snapped   16 exact
        #     mickey    231 pairs  18.35   97 pairs  23.89         149 pairs  14.45
        #     earth     230 pairs  14.34   102 pairs 16.32         143 pairs   7.50
        #
        # So a small *exact* palette beats a large shared one on accuracy and
        # on pairs together - earth halves its error while using 87 fewer pairs
        # - and the same palette approximated is a regression. Use this where
        # the colours it picks will be shown as asked for.
        #
        # Why pairs and not colours: a pair is a *combination* of foreground and
        # background, and there are only 255 of them on a screen. They do not
        # scale with the palette - earth.gif at full size is 253 colours but
        # 8583 pairs - so :meth:`fit_pairs` is what sizes a palette to fit,
        # rather than arithmetic on this number.
        #
        # Median cut, weighted by how many pixels each colour covers: split the
        # box with the widest spread along that channel, at the median pixel
        # rather than the median colour, so a colour covering half the picture
        # is not outvoted by a hundred stray ones. Holes stay holes.
        #
        # Note:
        #     An image already within ``colours`` comes back unchanged, so this
        #     is safe to apply to flat art that never needed it.
        #
        # Args:
        #     colours: The most colours the result may use.
        #
        # Raises:
        #     TclError: If ``colours`` is not positive.
        if colours <= 0:
            raise TclError("quantize needs a positive number of colours")
        counts: dict[str, int] = {}
        for row in self._pixels:
            for pixel in row:
                if pixel is not None:
                    counts[pixel] = counts.get(pixel, 0) + 1
        clone = self.copy()
        if len(counts) <= colours:
            return clone
        return self._mapped(_median_cut(counts, colours))

    def pairs_needed(self, depth: Any = None) -> int:
        """How many distinct ``(fg, bg)`` colour pairs drawing this would take.

        A terminal runs out of colour pairs - it has 255 - before it runs out of
        colours, and a pair is a combination, so this is not the colour count.
        It is counted as the terminal will show the picture, which on a terminal
        with few colours is far fewer than the picture holds.

        Args:
            depth: What the terminal can show. Defaults to what the
                application's terminal reports.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # How many distinct ``(fg, bg)`` combinations drawing this would take.
        #
        # The number that actually matters, because a colour pair is what the
        # terminal runs out of - 255 of them, and a pair is a *combination*, so
        # this is not the colour count and does not track it. Measured,
        # earth.gif at full size is 253 colours and 8583 pairs.
        #
        # **Counted as the terminal will resolve them, not as the picture
        # stores them.** Those are wildly different numbers wherever the
        # palette is small: mickey.gif at 120x38 holds 1862 distinct
        # combinations, and on an eight-colour terminal they land on 42.
        # Counting the stored colours made :meth:`fit_pairs` believe an
        # eight-colour terminal was 1800 pairs short and crush the picture to
        # five colours - throwing away three quarters of what that terminal
        # could actually have shown.
        #
        # Args:
        #     depth: What the terminal can show. Defaults to whatever the
        #         application's terminal reports, so the usual call takes no
        #         argument at all.
        #
        # Counted through the same :func:`~tkcurses._core.canvas.compose` that
        # draws the image, so it is the real demand rather than an estimate.
        from tkcurses._core.canvas import compose
        from tkcurses._core.colors import ColorDepth, _resolve_rgb

        if depth is None:
            manager = getattr(self._tk, "colors", None)
            depth = getattr(manager, "depth", ColorDepth.DIRECT)
        if depth >= ColorDepth.DIRECT:
            # Every colour is itself, so the stored combinations are the
            # real ones and there is nothing to resolve.
            return len({(fore, back) for _, fore, back in compose(self.lit()).values()})

        def entry(spec: str | None, background: bool) -> tuple[int, int] | None:
            if spec is None:
                return None
            parts = rgb_of(spec)
            if parts is None:
                return None
            resolved = _resolve_rgb(parts, depth, background=background)
            return (resolved.color, resolved.attr)

        return len(
            {
                (entry(fore, False), entry(back, True))
                for _, fore, back in compose(self.lit()).values()
            }
        )

    def fit_pairs(self, budget: int | None = None, depth: Any = None) -> PhotoImage:
        """A copy that can be drawn within ``budget`` colour pairs.

        Reduces the palette - by the same median cut :meth:`quantize` uses - only
        as far as it has to, and not at all if the picture already fits. Small or
        flat art comes back untouched.

        A widget showing a picture does this for itself when it draws, so a
        program calls it only to choose the budget, or to see the result.

        Args:
            budget: The most pairs the result may need. Defaults to what the
                terminal has left right now: widgets and text have already taken
                some of them.

        Raises:
            TclError: If ``budget`` is not positive.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # A copy that can be drawn within ``budget`` colour pairs.
        #
        # Reduces the palette - by the same median cut :meth:`quantize` uses -
        # only as far as it has to, and not at all if the picture already fits.
        # Small or flat art comes back untouched.
        #
        # This exists because the palette size cannot be a constant. Measured
        # on two pictures at the same 53x33 size, a 32-colour palette needs 275
        # pairs on one and 304 on the other, both over the 255 ceiling, while
        # 16 colours needs 149 and 143 and sits comfortably under. Which size
        # fits depends on the picture, on how large it is drawn, and on what
        # else is on screen - so it is found by asking rather than assumed.
        #
        # **Grown one colour at a time rather than searched.** The first
        # version binary-searched the palette size and rebuilt the whole median
        # cut for each probe, which measured **8.7 seconds** on earth.gif - the
        # splits are identical every time, so they are now done once and the
        # pair count checked as the palette grows. The same call is 40ms.
        #
        # Args:
        #     budget: The most pairs the result may need. Defaults to what the
        #         terminal has left right now, which is the honest number: an
        #         image cannot assume the whole table, because widgets and text
        #         have already taken some of it.
        #
        # Raises:
        #     TclError: If ``budget`` is not positive.
        if budget is None:
            manager = getattr(self._tk, "colors", None)
            budget = getattr(manager, "remaining", 0) or _PAIR_CEILING
        if budget <= 0:
            raise TclError("fit_pairs needs a positive budget")
        if self.pairs_needed(depth) <= budget:
            return self.copy()

        counts: dict[str, int] = {}
        for row in self._pixels:
            for pixel in row:
                if pixel is not None:
                    counts[pixel] = counts.get(pixel, 0) + 1

        boxes = [list(counts.items())]
        best = self._mapped(_mapping_of(boxes))
        while len(boxes) < len(counts):
            # Checked every few colours rather than every one: a compose pass
            # costs about as much as several splits, and the pair count moves
            # smoothly enough that landing a little under the budget is
            # better than paying to land exactly on it.
            for _ in range(_FIT_STEP):
                if not _split_once(boxes):
                    break
            candidate = self._mapped(_mapping_of(boxes))
            if candidate.pairs_needed(depth) > budget:
                return best
            best = candidate
        return best

    def _mapped(self, mapping: dict[str, str]) -> PhotoImage:
        """A copy with every pixel replaced through ``mapping``. Holes stay."""
        clone = self.copy()
        clone._pixels = [
            [TRANSPARENT if pixel is None else mapping[pixel] for pixel in row]
            for row in self._pixels
        ]
        return clone

    def dither(self, depth: Any = None) -> PhotoImage:
        """A copy whose every pixel is a colour the terminal really has, with the
        difference spread into its neighbours - Floyd-Steinberg error diffusion.

        **A tool, not a default.** Dithering works when the eye merges
        neighbouring pixels, and a pixel here is half a character cell: what
        shows is usually the pattern. It is worth trying for a large image in a
        small font; :meth:`reduce` is the one that helps everywhere. An image
        already made of colours the terminal has comes back unchanged - at true
        colour, every image does.

        Args:
            depth: What the terminal can show. Defaults to what the
                application's terminal reports.

        TkCurses extension:
            tkinter's images have no such method.
        """
        # The docstring this replaced, with its measurements:
        # A copy whose every pixel is a colour the terminal really has.
        #
        # The palette is chosen for the terminal's depth, and the error each
        # pixel accumulates by being moved to the nearest available colour is
        # pushed into its neighbours - Floyd-Steinberg, the standard weights.
        # Over a few cells the eye averages them back to the colour that was
        # actually there.
        #
        # This exists because a better *match* cannot help. ``#482424`` is 31%
        # of the perl-Tk mickey.gif, and the xterm-256 palette has nothing for
        # it: the 6x6x6 cube is empty between 0 and 95 while the grey ramp is
        # dense there, so a third of the picture becomes one flat neutral
        # grey. Plain RGB, redmean, a chroma penalty and CIE Lab all choose
        # that same grey, because it genuinely is the nearest colour there is.
        #
        # **Whether this is an improvement depends on something a terminal
        # usually does not give you, so read this before reaching for it.**
        #
        # Error diffusion trades colour accuracy for spatial noise, and it
        # only pays when the eye merges neighbouring pixels back together. It
        # does that on a monitor, where a pixel is a quarter of a millimetre.
        # A pixel here is half a character cell - tens of screen pixels - and
        # the eye merges nothing. You see the dither pattern itself.
        #
        # Measured against the fitted source, over two photographs and a
        # gradient at two depths:
        #
        #     picture        depth      flat   dithered
        #     mickey.gif     8         71.58      90.87
        #     mickey.gif     256       29.15      30.05
        #     earth.gif      8        126.70     120.65
        #     earth.gif      256       18.95      24.67
        #     gradient.png   8        149.57     151.47
        #     gradient.png   256       29.29      34.60
        #
        # Flat wins five of those six per-pixel, and every time at 256
        # colours. After a 3x3 blur the order reverses everywhere and by a
        # wide margin - on the gradient at 8 colours, 26.71 dithered against
        # 140.29 flat.
        #
        # Both sets are true and they disagree, because they assume different
        # viewers. The first is what a terminal shows.
        #
        # So this is a tool and not a default. It is worth having for the case
        # where the cells really are small - a large image at a small font -
        # and :meth:`reduce` is the one that helps everywhere.
        #
        # A person looking at the four side by side picked averaged-and-flat
        # as the best of them, which is what sent me back to measure without
        # the blur. The blurred number was the only one I had taken, and it
        # encoded an assumption about the viewer that I had never checked.
        #
        # Args:
        #     depth: What the terminal can show. Defaults to whatever the
        #         application's terminal reports, so the usual call takes no
        #         argument at all.
        #
        # Note:
        #     Self-limiting. A pixel the palette holds exactly accumulates no
        #     error, so an image already made of available colours comes back
        #     unchanged - at truecolor, every image does.
        from tkcurses._core.colors import ColorDepth, _resolve_rgb, rgb_of_number

        if depth is None:
            manager = getattr(self._tk, "colors", None)
            depth = getattr(manager, "depth", ColorDepth.BASIC)
        clone = self.copy()
        if depth >= ColorDepth.DIRECT:
            return clone  # every colour is available; there is no error

        # Keyed on the triple, and resolved straight from it. Formatting a
        # hex string per pixel and handing it to parse_color to be parsed
        # back cost 1.7 seconds on a 320x200 image; error diffusion produces
        # a different triple almost every pixel, so that cache never hit.
        nearest: dict[tuple[int, int, int], tuple[tuple[int, int, int], str]] = {}

        def available(rgb: tuple[int, int, int]) -> tuple[tuple[int, int, int], str]:
            # Keyed on the triple rounded to four levels. Error diffusion
            # produces a different exact triple at almost every pixel, so an
            # exact key never hits and each miss scans the whole palette -
            # measured, that alone was 82ms on a 53x33 image. The palette's
            # own steps are tens of units apart (the xterm cube goes 0, 95,
            # 135, ...), so a four-unit key cannot change which entry is
            # nearest except at an exact tie, where the two answers differ
            # by less than the tie margin and diffusion absorbs it anyway.
            key = (rgb[0] & ~3, rgb[1] & ~3, rgb[2] & ~3)
            found = nearest.get(key)
            if found is None:
                shown = rgb_of_number(_resolve_rgb(rgb, depth).color, depth) or rgb
                found = (shown, f"#{shown[0]:02x}{shown[1]:02x}{shown[2]:02x}")
                nearest[key] = found
            return found

        # The error is carried in floating point and only rounded when a
        # pixel is matched, which is how the method is usually written.
        # Measured on a grey ramp, truncating it at every step instead makes
        # no difference worth the name - RMS 10.90 against 10.96 - so this
        # is convention rather than a claim.
        carried: list[list[list[float]]] = []
        for row in self._pixels:
            carried.append(
                [
                    [float(part) for part in (rgb_of(pixel) or (0, 0, 0))]
                    if pixel is not None
                    else []
                    for pixel in row
                ]
            )

        height, width = self.height(), self.width()
        for y in range(height):
            for x in range(width):
                wanted = carried[y][x]
                if not wanted:
                    continue  # a hole stays a hole and spreads no error
                got, spec = available(
                    (
                        int(max(0.0, min(255.0, wanted[0]))),
                        int(max(0.0, min(255.0, wanted[1]))),
                        int(max(0.0, min(255.0, wanted[2]))),
                    )
                )
                clone._pixels[y][x] = spec
                error = [wanted[i] - got[i] for i in range(3)]
                for dx, dy, share in (
                    (1, 0, 7 / 16),
                    (-1, 1, 3 / 16),
                    (0, 1, 5 / 16),
                    (1, 1, 1 / 16),
                ):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and carried[ny][nx]:
                        for i in range(3):
                            carried[ny][nx][i] += error[i] * share
        return clone

    def _remeasure(self) -> None:
        """Put the width and height options back in step with the pixels."""
        self._options["width"] = self.width()
        self._options["height"] = self.height()

    # --------------------------------------------------------- whole file

    def _region(self, from_coords: Sequence[int] | None) -> list[Row]:
        """The pixels ``-from`` names: all of them, from a corner to the far
        one, or between two corners in either order."""
        x1, y1, x2, y2 = 0, 0, self.width(), self.height()
        if from_coords is not None:
            given = _corner_values(self._name, "-from", from_coords)
            x1, y1 = given[0], given[1]
            if len(from_coords) > 2:
                x2, y2 = given[2], given[3]
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            if x2 > self.width() or y2 > self.height():
                raise TclError("coordinates for -from option extend outside image")
        return [row[x1:x2] for row in self._pixels[y1:y2]]

    def _rgb_rows(
        self,
        from_coords: Sequence[int] | None,
        background: Any,
        grayscale: bool,
    ) -> list[list[tuple[int, int, int] | None]]:
        """The region as RGB, holes filled with ``background`` when one is
        given and turned grey with the rest under ``grayscale``."""
        fill = None
        if background:
            fill = true_rgb(background)
            if fill is None:
                raise TclError(f'unknown color name "{background}"')
        rows: list[list[tuple[int, int, int] | None]] = []
        for row in self._region(from_coords):
            converted: list[tuple[int, int, int] | None] = []
            for pixel in row:
                rgb = fill if pixel is TRANSPARENT else true_rgb(pixel) or (0, 0, 0)
                converted.append(_grey(rgb) if grayscale and rgb is not None else rgb)
            rows.append(converted)
        return rows

    def data(
        self,
        format: Any = None,
        *,
        from_coords: Sequence[int] | None = None,
        background: Any = None,
        grayscale: bool = False,
        palette: Mapping[str, str] | None = None,
    ) -> Any:
        """The image's pixels, as Tk's ``data`` gives them.

        Without a format, a tuple of rows, each a string of ``#rrggbb``
        colours; a hole is ``#000000``. With ``"png"``, ``"gif"`` or
        ``"ppm"``, the bytes of that file, and with ``"default"`` the rows
        as one Tcl list in bytes. A name is reported as the colour it names:
        ``red`` is ``#ff0000``, whatever this terminal shows for it.

        Args:
            format: The format, as Tk names it; a format's own options
                after the name, ``"gif -index 1"``, are ignored.
            from_coords: The region: ``(x, y)`` to the far corner, or
                ``(x1, y1, x2, y2)``.
            background: A colour for the holes.
            grayscale: Every colour as Tk's grey for it.
            palette: Character art instead - see below.

        Raises:
            TclError: In Tk's words, for a format Tk does not have or
                cannot write as a string, a region outside the image, an
                unknown background colour, or a GIF of more than 255
                colours.

        TkCurses extension:
            ``palette``, a mapping from colour to character, answers rows
            of characters, the character art a PhotoImage can be made from:
            a colour not in it is ``#`` and a hole a space.
        """
        if palette is not None:
            marks = dict(palette)
            return [
                "".join(
                    " " if pixel is None else marks.get(pixel, "#") for pixel in row
                )
                for row in self._region(from_coords)
            ]
        word = _format_word(format)
        if word is not None and word not in _FORMATS:
            raise TclError(f'image string format "{word}" is unknown')
        if word == "svg":
            raise TclError('image string format "svg" is not supported')
        rows = self._rgb_rows(from_coords, background, grayscale)
        if word in ("gif", "png", "ppm"):
            return _ENCODERS[word](rows)
        text = tuple(
            " ".join("#%02x%02x%02x" % (pixel or (0, 0, 0)) for pixel in row)
            for row in rows
        )
        if word == "default":
            return " ".join("{" + row + "}" for row in text).encode("ascii")
        return text

    def read(
        self,
        filename: str,
        format: Any = None,
        *,
        from_coords: Sequence[int] | None = None,
        to: Sequence[int] | None = None,
        shrink: bool = False,
    ) -> None:
        """Read an image file into this image, as Tk's ``read``.

        The file's region ``from_coords`` goes at ``to``, the origin by
        default, replacing what was there, holes and all. An image with no
        size of its own grows to take it, and with ``shrink`` becomes
        exactly as large as it reaches; one given a size keeps it and
        clips.

        Args:
            filename: The file. Its content decides how it is read.
            format: ``"png"``, ``"gif"`` or ``"ppm"``: the file must be in
                it, and is refused otherwise, as Tk refuses it.

        Raises:
            TclError: In Tk's words, for a file that cannot be opened or
                is not an image in the format, or a region outside it.

        TkCurses extension:
            With a ``palette``, a text file of character art is read too.
        """
        self._copy_block(
            self._file_rows(filename, format),
            from_coords=from_coords,
            to=to,
            shrink=shrink,
            rule="set",
        )

    def write(
        self,
        filename: str,
        format: Any = None,
        from_coords: Sequence[int] | None = None,
        *,
        background: Any = None,
        grayscale: bool = False,
        palette: Mapping[str, str] | None = None,
    ) -> None:
        """Write the image to a file, as Tk's ``write``: a PPM unless
        ``format`` says ``"png"`` or ``"gif"``.

        ``from_coords``, ``background`` and ``grayscale`` are as for
        :meth:`data`. A PPM has no holes, so they are written black, as Tk
        writes them.

        Raises:
            TclError: In Tk's words, for a format Tk does not have or cannot
                write to a file, a file that cannot be opened, or a GIF of
                more than 255 colours.

        TkCurses extension:
            ``palette`` writes the character art :meth:`data` answers for
            it, one row a line.
        """
        if palette is not None:
            rows = self.data(from_coords=from_coords, palette=palette)
            content = ("\n".join(rows) + "\n").encode("utf-8")
        else:
            word = _format_word(format) or "ppm"
            if word not in _FORMATS:
                raise TclError(f'image file format "{word}" is unknown')
            if word not in _ENCODERS:
                raise TclError(
                    f'image file format "{word}" has no file writing capability'
                )
            content = _ENCODERS[word](
                self._rgb_rows(from_coords, background, grayscale)
            )
        try:
            Path(filename).write_bytes(content)
        except OSError as exc:
            raise _open_failure(filename, exc) from None


#: The formats Tk writes, each to its encoder.
_ENCODERS = {"gif": encode_gif, "png": encode_png, "ppm": encode_ppm}


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

    Sample output:
        arrow = tk.BitmapImage(foreground="cyan", data=(
            "#define a_width 8\\n#define a_height 4\\n"
            "static unsigned char a_bits[] = {0x18, 0x3c, 0x7e, 0xff};"
        ))
        tk.Label(root, image=arrow).pack()
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
