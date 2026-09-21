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

"""Reading the image formats tkinter reads, with nothing but the standard library.

tkinter 8.6 and later give PhotoImage PNG, GIF, PGM and PPM, and BitmapImage
XBM. Those are decoded here, into the rows of ``#rrggbb`` a
:class:`~tkcurses._core.images.PhotoImage` holds - so a decoded photograph is
the same kind of thing as art typed into a source file, and everything
downstream, the quantising included, is already written.

**No dependency is taken for this.** ``pyproject.toml`` says
``dependencies = []`` and that is a deliberate property of the library, not
an oversight nobody has got round to. PNG needs ``zlib``, which is in the
standard library; GIF's LZW and the netpbm headers are short enough to
write. Pillow appears only in the test extra, as something to check the
answers against.

**The format is sniffed from the content, never from the name.** Measured on
Tk 9.0.2: opening a PNG while saying ``format="gif"`` fails with
``couldn't recognize data in image file``, so Tk is plainly looking at the
bytes. A file whose name says one thing and whose content says another is
read as its content, and the error when nothing matches is worded as Tk
words it.

What is deliberately not supported, and says so rather than guessing: PNG
bit depths other than 8, and animation beyond a GIF's first frame. Adam7
interlacing *is* read - it was refused for a while, and Tk 9.0.2 reads
these, so leaving it refused was a divergence rather than a shared limit.
"""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

from tkcurses._core.errors import TclError

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["decode", "sniff"]

#: Rows of colour, ``None`` where the image is transparent - the shape a
#: PhotoImage stores.
Rows = list[list[str | None]]

#: Magic numbers, longest first so a prefix cannot shadow a longer match.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_GIF_MAGICS = (b"GIF87a", b"GIF89a")
_NETPBM_MAGICS = (b"P1", b"P2", b"P3", b"P4", b"P5", b"P6")

#: Below this, a pixel's alpha is taken as "not there at all". A half-cell
#: either paints or it does not: there is no blending to be done until draw
#: time, and by then the pixel has been folded into a glyph with one colour.
#: Halfway is the only defensible place to put it.
ALPHA_THRESHOLD = 128


def sniff(data: bytes) -> str | None:
    """The format ``data`` is in, or None if it is not one we read."""
    if data.startswith(_PNG_MAGIC):
        return "png"
    if data.startswith(_GIF_MAGICS):
        return "gif"
    if data[:2] in _NETPBM_MAGICS:
        return "netpbm"
    return None


def decode(data: bytes, path: str = "") -> Rows:
    """Decode ``data`` into rows of colour.

    Args:
        data: The whole file.
        path: What to name in an error, as Tk names the file it was given.

    Raises:
        TclError: If the data is in no format we read, or in one we read but
            a variant we do not. Worded as Tk words it.
    """
    kind = sniff(data)
    if kind == "netpbm":
        return _decode_netpbm(data, path)
    if kind == "png":
        return _decode_png(data, path)
    if kind == "gif":
        return _decode_gif(data, path)
    raise TclError(f'couldn\'t recognize data in image file "{path}"')


def _unreadable(path: str, because: str) -> TclError:
    """Tk's wording, with the reason appended so it is actually actionable.

    Tk says only ``couldn't recognize data in image file "x.png"``, which is
    the right thing to say when it cannot tell what a file is, and unhelpful
    when it knows exactly what the file is and will not read that variant.
    """
    return TclError(f'couldn\'t recognize data in image file "{path}": {because}')


class _Cache:
    """Hands out one string per colour.

    A 600x400 photograph is 240,000 pixels, and building a separate
    ``"#rrggbb"`` for each is both slow and needlessly large when a
    photograph has far fewer distinct colours than pixels. Measured on a
    photograph: 240,000 pixels, 27,000 distinct colours.
    """

    def __init__(self) -> None:
        self._seen: dict[tuple[int, int, int], str] = {}

    def __call__(self, red: int, green: int, blue: int) -> str:
        key = (red, green, blue)
        found = self._seen.get(key)
        if found is None:
            found = f"#{red:02x}{green:02x}{blue:02x}"
            self._seen[key] = found
        return found


# ------------------------------------------------------------------- netpbm


def _netpbm_tokens(data: bytes, start: int) -> Iterator[tuple[bytes, int]]:
    """Header tokens and the offset just past each.

    Comments run from ``#`` to end of line and may appear *anywhere* in the
    header, including between the width and the height - which is why this
    is a scanner rather than a split().
    """
    position = start
    while position < len(data):
        byte = data[position : position + 1]
        if byte.isspace():
            position += 1
            continue
        if byte == b"#":
            while position < len(data) and data[position : position + 1] not in (
                b"\n",
                b"\r",
            ):
                position += 1
            continue
        end = position
        while end < len(data) and not data[end : end + 1].isspace():
            end += 1
        yield data[position:end], end
        position = end


def _decode_netpbm(data: bytes, path: str) -> Rows:
    """P1-P6: the plain and binary bitmap, greymap and pixmap formats."""
    magic = data[:2]
    wanted = 3 if magic in (b"P1", b"P4") else 4  # P1/P4 have no maxval
    tokens: list[bytes] = []
    after = 2
    for token, end in _netpbm_tokens(data, 2):
        tokens.append(token)
        after = end
        if len(tokens) == wanted - 1:
            break
    if len(tokens) < wanted - 1:
        raise _unreadable(path, "the header ends before the image does")
    try:
        width = int(tokens[0])
        height = int(tokens[1])
        maxval = int(tokens[2]) if wanted == 4 else 1
    except ValueError:
        raise _unreadable(path, "the header is not numbers") from None
    if width <= 0 or height <= 0:
        raise _unreadable(path, f"a {width}x{height} image has no pixels")
    if maxval <= 0 or maxval > 65535:
        raise _unreadable(path, f"maxval {maxval} is out of range")

    colour = _Cache()
    if magic in (b"P1", b"P2", b"P3"):
        return _netpbm_ascii(data, after, magic, width, height, maxval, colour, path)
    # Binary: exactly one whitespace byte separates the header from the data.
    return _netpbm_binary(data, after + 1, magic, width, height, maxval, colour, path)


def _scale(sample: int, maxval: int) -> int:
    """A sample scaled to eight bits, whatever the file's maxval."""
    if maxval == 255:
        return min(sample, 255)
    return min(round(sample * 255 / maxval), 255)


def _netpbm_ascii(
    data: bytes,
    start: int,
    magic: bytes,
    width: int,
    height: int,
    maxval: int,
    colour: _Cache,
    path: str,
) -> Rows:
    """P1, P2 and P3: samples written out as decimal numbers."""
    per_pixel = 3 if magic == b"P3" else 1
    try:
        values = [int(token) for token, _ in _netpbm_tokens(data, start)]
    except ValueError:
        raise _unreadable(path, "a sample is not a number") from None
    needed = width * height * per_pixel
    if len(values) < needed:
        raise _unreadable(path, f"{len(values)} samples where {needed} were declared")
    rows: Rows = []
    index = 0
    for _ in range(height):
        row: list[str | None] = []
        for _ in range(width):
            if magic == b"P1":
                # The only format where 1 means black: it is a bitmap, and
                # a set bit is ink rather than light.
                level = 0 if values[index] else 255
                row.append(colour(level, level, level))
                index += 1
            elif magic == b"P2":
                level = _scale(values[index], maxval)
                row.append(colour(level, level, level))
                index += 1
            else:
                red, green, blue = values[index : index + 3]
                row.append(
                    colour(
                        _scale(red, maxval), _scale(green, maxval), _scale(blue, maxval)
                    )
                )
                index += 3
        rows.append(row)
    return rows


def _netpbm_binary(
    data: bytes,
    start: int,
    magic: bytes,
    width: int,
    height: int,
    maxval: int,
    colour: _Cache,
    path: str,
) -> Rows:
    """P4, P5 and P6: samples as bytes."""
    wide = maxval > 255
    if magic == b"P4":
        stride = (width + 7) // 8
        if len(data) - start < stride * height:
            raise _unreadable(path, "the pixel data ends early")
        rows: Rows = []
        for y in range(height):
            row: list[str | None] = []
            base = start + y * stride
            for x in range(width):
                # Most significant bit leftmost here, unlike XBM.
                bit = (data[base + x // 8] >> (7 - x % 8)) & 1
                level = 0 if bit else 255
                row.append(colour(level, level, level))
            rows.append(row)
        return rows

    per_pixel = 3 if magic == b"P6" else 1
    size = 2 if wide else 1
    needed = width * height * per_pixel * size
    if len(data) - start < needed:
        raise _unreadable(
            path,
            f"{len(data) - start} bytes of pixel data where {needed} were declared",
        )

    def sample(at: int) -> int:
        if wide:
            return _scale((data[at] << 8) | data[at + 1], maxval)
        return _scale(data[at], maxval)

    rows = []
    position = start
    for _ in range(height):
        row = []
        for _ in range(width):
            if per_pixel == 1:
                level = sample(position)
                row.append(colour(level, level, level))
                position += size
            else:
                row.append(
                    colour(
                        sample(position),
                        sample(position + size),
                        sample(position + 2 * size),
                    )
                )
                position += 3 * size
        rows.append(row)
    return rows


# ---------------------------------------------------------------------- png


#: Bytes per pixel for each PNG colour type. Type 3 is an index into the
#: palette, so one byte covers it whatever the palette holds.
_PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

_PNG_COLOUR_NAMES = {
    0: "greyscale",
    2: "RGB",
    3: "palette",
    4: "greyscale with alpha",
    6: "RGBA",
}


def _png_chunks(data: bytes, path: str) -> Iterator[tuple[bytes, bytes]]:
    """Type and payload of each chunk, in order.

    The CRC after each payload is skipped rather than checked. A corrupt
    chunk shows up as a zlib error or a short row soon enough, and refusing
    a file whose pixels are perfectly readable because four trailing bytes
    disagree would be worse than useless in a viewer.
    """
    position = len(_PNG_MAGIC)
    while position + 8 <= len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        kind = data[position + 4 : position + 8]
        start = position + 8
        if start + length > len(data):
            raise _unreadable(
                path,
                f"the {kind.decode('ascii', 'replace')} chunk runs past the end of the file",
            )
        yield kind, data[start : start + length]
        position = start + length + 4  # four more for the CRC
    return


#: Adam7's seven passes: where each starts and how far it steps, in x and
#: y. Each pass is a little image in its own right - filtered against its
#: own width, not the full one - which is the part that catches people.
_ADAM7 = (
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
)


def _pass_size(
    width: int, height: int, spread: tuple[int, int, int, int]
) -> tuple[int, int]:
    """How many pixels one Adam7 pass holds, which can be none at all."""
    x0, y0, dx, dy = spread
    return (
        0 if width <= x0 else (width - x0 + dx - 1) // dx,
        0 if height <= y0 else (height - y0 + dy - 1) // dy,
    )


def _paeth(left: int, above: int, corner: int) -> int:
    """PNG's predictor: whichever of the three neighbours the gradient favours."""
    estimate = left + above - corner
    from_left = abs(estimate - left)
    from_above = abs(estimate - above)
    from_corner = abs(estimate - corner)
    if from_left <= from_above and from_left <= from_corner:
        return left
    if from_above <= from_corner:
        return above
    return corner


def _png_unfilter(
    raw: bytes, height: int, stride: int, step: int, path: str
) -> bytearray:
    """Undo the per-row filters, leaving the raw scanlines end to end.

    Every row carries a filter byte and is predicted from the row above and
    the pixel to the left, so this cannot be done out of order or in
    parallel: row N needs row N-1 already undone.
    """
    if len(raw) < height * (stride + 1):
        raise _unreadable(
            path,
            f"{len(raw)} bytes of pixel data where {height * (stride + 1)} were declared",
        )
    out = bytearray(height * stride)
    for y in range(height):
        source = y * (stride + 1)
        kind = raw[source]
        line = source + 1
        target = y * stride
        previous = target - stride
        for x in range(stride):
            value = raw[line + x]
            left = out[target + x - step] if x >= step else 0
            above = out[previous + x] if y else 0
            corner = out[previous + x - step] if y and x >= step else 0
            if kind == 0:
                pass
            elif kind == 1:
                value += left
            elif kind == 2:
                value += above
            elif kind == 3:
                value += (left + above) // 2
            elif kind == 4:
                value += _paeth(left, above, corner)
            else:
                raise _unreadable(
                    path, f"row {y} uses filter {kind}, which is not a filter"
                )
            out[target + x] = value & 0xFF
    return out


def _png_deinterlace(
    raw: bytes, width: int, height: int, step: int, path: str
) -> bytearray:
    """Undo Adam7, returning the scanlines as if they had never been split.

    Each pass is its own little image: its own width, its own filter bytes,
    its own row above for the predictors. Unfiltering the lot against the
    full width - which is the obvious mistake - gives seven bands of noise.
    """
    out = bytearray(height * width * step)
    at = 0
    for spread in _ADAM7:
        x0, y0, dx, dy = spread
        across, down = _pass_size(width, height, spread)
        if not across or not down:
            continue  # a pass can be empty on a narrow or short image
        stride = across * step
        wanted = down * (stride + 1)
        if len(raw) - at < wanted:
            raise _unreadable(
                path,
                f"{len(raw) - at} bytes left where a pass needs {wanted}",
            )
        block = _png_unfilter(raw[at : at + wanted], down, stride, step, path)
        at += wanted
        for row in range(down):
            for column in range(across):
                source = row * stride + column * step
                target = ((y0 + row * dy) * width + (x0 + column * dx)) * step
                out[target : target + step] = block[source : source + step]
    return out


def _decode_png(data: bytes, path: str) -> Rows:
    """Non-interlaced, 8-bit PNG: greyscale, RGB, palette, and either with alpha."""
    width = height = depth = colour_type = interlace = 0
    palette = b""
    transparency = b""
    compressed = bytearray()
    seen_header = False
    for kind, payload in _png_chunks(data, path):
        if kind == b"IHDR":
            if len(payload) < 13:
                raise _unreadable(path, "the IHDR chunk is too short to be one")
            width = int.from_bytes(payload[0:4], "big")
            height = int.from_bytes(payload[4:8], "big")
            depth = payload[8]
            colour_type = payload[9]
            interlace = payload[12]
            seen_header = True
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"IDAT":
            compressed += payload
        elif kind == b"IEND":
            break
    if not seen_header:
        raise _unreadable(path, "there is no IHDR chunk")
    if width <= 0 or height <= 0:
        raise _unreadable(path, f"a {width}x{height} image has no pixels")
    if interlace not in (0, 1):
        raise _unreadable(path, f"interlace method {interlace} is not one")
    if depth != 8:
        raise _unreadable(path, f"a bit depth of {depth} is not supported, only 8")
    if colour_type not in _PNG_CHANNELS:
        raise _unreadable(path, f"colour type {colour_type} is not a colour type")
    if colour_type == 3 and not palette:
        raise _unreadable(path, "a palette image with no PLTE chunk")
    if not compressed:
        raise _unreadable(path, "there is no IDAT chunk")

    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise _unreadable(
            path, f"the compressed data will not inflate: {exc}"
        ) from None

    step = _PNG_CHANNELS[colour_type]
    stride = width * step
    if interlace:
        flat = _png_deinterlace(raw, width, height, step, path)
    else:
        flat = _png_unfilter(raw, height, stride, step, path)

    colour = _Cache()
    rows: Rows = []
    for y in range(height):
        row: list[str | None] = []
        base = y * stride
        for x in range(width):
            at = base + x * step
            if colour_type == 0:
                level = flat[at]
                row.append(colour(level, level, level))
            elif colour_type == 2:
                row.append(colour(flat[at], flat[at + 1], flat[at + 2]))
            elif colour_type == 3:
                index = flat[at]
                if (index + 1) * 3 > len(palette):
                    raise _unreadable(
                        path, f"pixel index {index} is past the end of the palette"
                    )
                if index < len(transparency) and transparency[index] < ALPHA_THRESHOLD:
                    row.append(None)
                else:
                    at3 = index * 3
                    row.append(colour(palette[at3], palette[at3 + 1], palette[at3 + 2]))
            elif colour_type == 4:
                level = flat[at]
                row.append(
                    None
                    if flat[at + 1] < ALPHA_THRESHOLD
                    else colour(level, level, level)
                )
            else:
                row.append(
                    None
                    if flat[at + 3] < ALPHA_THRESHOLD
                    else colour(flat[at], flat[at + 1], flat[at + 2])
                )
        rows.append(row)
    return rows


# ---------------------------------------------------------------------- gif


#: Where each of a GIF's four interlace passes starts, and how far it steps.
#: Unlike PNG's Adam7 this is rows only, which is why it is worth doing here
#: and not there: four slices, no per-pixel arithmetic.
_GIF_PASSES = ((0, 8), (4, 8), (2, 4), (1, 2))


def _gif_blocks(data: bytes, start: int) -> tuple[bytes, int]:
    """Join a run of length-prefixed sub-blocks, and say where it ended."""
    out = bytearray()
    position = start
    while position < len(data):
        size = data[position]
        position += 1
        if size == 0:
            break
        out += data[position : position + size]
        position += size
    return bytes(out), position


def _gif_lzw(data: bytes, minimum: int, expected: int, path: str) -> list[int]:
    """GIF's variable-width LZW, returning colour indices.

    The width grows from ``minimum + 1`` as the table fills and resets on a
    clear code. Encoders differ on when they emit that clear, and some never
    emit the end code at all, so running out of input is a reason to stop
    rather than to complain.
    """
    if not 2 <= minimum <= 11:
        raise _unreadable(path, f"an LZW minimum code size of {minimum} is impossible")
    clear = 1 << minimum
    end = clear + 1
    table: list[list[int]] = [[index] for index in range(clear)] + [[], []]
    width = minimum + 1
    out: list[int] = []
    previous: list[int] | None = None
    bits = 0
    held = 0
    position = 0
    while len(out) < expected:
        while bits < width:
            if position >= len(data):
                return out
            held |= data[position] << bits
            bits += 8
            position += 1
        code = held & ((1 << width) - 1)
        held >>= width
        bits -= width
        if code == clear:
            table = [[index] for index in range(clear)] + [[], []]
            width = minimum + 1
            previous = None
            continue
        if code == end:
            break
        if code < len(table):
            entry = table[code]
        elif previous is not None and code == len(table):
            # The encoder may name a sequence in the same step that defines
            # it. Legal, common, and the usual place a decoder goes wrong.
            entry = [*previous, previous[0]]
        else:
            raise _unreadable(path, f"code {code} is not in the table yet")
        out += entry
        if previous is not None and len(table) < 4096:
            table.append([*previous, entry[0]])
            if len(table) == (1 << width) and width < 12:
                width += 1
        previous = entry
    return out


def _decode_gif(data: bytes, path: str) -> Rows:
    """The first frame of a GIF, 87a or 89a."""
    if len(data) < 13:
        raise _unreadable(path, "the file ends inside its header")
    flags = data[10]
    global_size = 2 << (flags & 0x07) if flags & 0x80 else 0
    position = 13
    global_table = data[position : position + global_size * 3]
    position += global_size * 3

    transparent: int | None = None
    while position < len(data):
        marker = data[position]
        if marker == 0x21:  # extension
            label = data[position + 1]
            if label == 0xF9:  # graphic control
                block, position = _gif_blocks(data, position + 2)
                if block and block[0] & 0x01:
                    transparent = block[3]
            else:
                _, position = _gif_blocks(data, position + 2)
            continue
        if marker == 0x3B:  # trailer
            raise _unreadable(path, "there is no image in this file")
        if marker != 0x2C:
            raise _unreadable(path, f"0x{marker:02x} is not a block this reads")

        # Image descriptor: position, size, then the local table flags.
        width = int.from_bytes(data[position + 5 : position + 7], "little")
        height = int.from_bytes(data[position + 7 : position + 9], "little")
        local = data[position + 9]
        position += 10
        table = global_table
        if local & 0x80:
            local_size = 2 << (local & 0x07)
            table = data[position : position + local_size * 3]
            position += local_size * 3
        interlaced = bool(local & 0x40)
        if width <= 0 or height <= 0:
            raise _unreadable(path, f"a {width}x{height} image has no pixels")
        if not table:
            raise _unreadable(path, "the image names no colour table")

        minimum = data[position]
        compressed, _ = _gif_blocks(data, position + 1)
        indices = _gif_lzw(compressed, minimum, width * height, path)
        if len(indices) < width * height:
            raise _unreadable(
                path,
                f"{len(indices)} pixels where {width * height} were declared",
            )

        colour = _Cache()
        lines: Rows = []
        for y in range(height):
            line: list[str | None] = []
            base = y * width
            for x in range(width):
                index = indices[base + x]
                if index == transparent or (index + 1) * 3 > len(table):
                    line.append(None)
                else:
                    at = index * 3
                    line.append(colour(table[at], table[at + 1], table[at + 2]))
            lines.append(line)
        if not interlaced:
            return lines
        # Four passes of rows, in the order the file stores them.
        ordered: Rows = [[] for _ in range(height)]
        source = 0
        for start, step in _GIF_PASSES:
            for y in range(start, height, step):
                ordered[y] = lines[source]
                source += 1
        return ordered
    raise _unreadable(path, "there is no image in this file")
