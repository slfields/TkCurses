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

"""Decoding the image formats tkinter reads.

Two kinds of test here, and they catch different things.

**Hand-written files with known bytes** pin down the corners: a comment
between the width and the height, a maxval that is not 255, a truncated
file. These are small enough to reason about completely.

**Comparison against Pillow** is what makes a *large* image testable at all.
A 60x40 photograph cannot be eyeballed, but "every pixel equals what an
independent decoder produced from the same bytes" can be asserted, and that
is the check that caught the XBM bit order being backwards. Skipped, not
failed, when Pillow is absent - it is a test-only dependency and the library
takes none.
"""

from __future__ import annotations

import io
import zlib

import pytest

from tkcurses._core.errors import TclError
from tkcurses._core.imagefiles import decode, sniff

_pil = pytest.importorskip("PIL.Image", reason="Pillow is the decoding oracle")
PIL = _pil


def as_rows(image):
    """A Pillow image as the rows of ``#rrggbb`` we would produce."""
    rgb = image.convert("RGB")
    return [
        ["#{:02x}{:02x}{:02x}".format(*rgb.getpixel((x, y))) for x in range(rgb.width)]
        for y in range(rgb.height)
    ]


def photograph(width=37, height=23):
    """Something with enough going on that a shifted row would show."""
    image = PIL.new("RGB", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel(
                (x, y),
                ((x * 7 + y * 3) % 256, (x * x + y) % 256, (x + y * 11) % 256),
            )
    return image


# ------------------------------------------------------------------ sniffing


@pytest.mark.parametrize(
    ("magic", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"rest", "png"),
        (b"GIF87a" + b"rest", "gif"),
        (b"GIF89a" + b"rest", "gif"),
        (b"P1\n1 1\n0\n", "netpbm"),
        (b"P6\n1 1 255\n\x00\x00\x00", "netpbm"),
        (b"not an image at all", None),
        (b"", None),
        (b"P", None),
    ],
)
def test_the_format_is_sniffed_from_the_content(magic, expected):
    assert sniff(magic) == expected


def test_a_file_in_no_known_format_is_refused_as_tk_words_it(tmp_path):
    with pytest.raises(TclError, match="couldn't recognize data in image file"):
        decode(b"hello, world", "greeting.txt")


# -------------------------------------------------------------- netpbm, P6


def test_a_binary_ppm_matches_pillow(tmp_path):
    path = tmp_path / "shot.ppm"
    image = photograph()
    image.save(path)  # Pillow writes P6
    assert path.read_bytes()[:2] == b"P6"
    assert decode(path.read_bytes(), str(path)) == as_rows(image)


def test_a_binary_pgm_matches_pillow(tmp_path):
    path = tmp_path / "shot.pgm"
    image = photograph().convert("L")
    image.save(path)  # P5
    assert path.read_bytes()[:2] == b"P5"
    assert decode(path.read_bytes(), str(path)) == as_rows(image)


def test_an_ascii_ppm_matches_pillow(tmp_path):
    path = tmp_path / "shot.ppm"
    image = photograph(9, 7)
    image.save(path, format="PPM")
    raw = path.read_bytes()
    # Rewrite it as P3 by hand, since Pillow only writes the binary forms.
    header = f"P3\n{image.width} {image.height}\n255\n".encode()
    body = " ".join(
        str(value)
        for y in range(image.height)
        for x in range(image.width)
        for value in image.getpixel((x, y))
    ).encode()
    assert decode(header + body, "ascii.ppm") == as_rows(image)
    assert decode(raw, "binary.ppm") == as_rows(image)


def test_an_ascii_pgm_reads_grey_levels():
    data = b"P2\n3 2\n255\n0 128 255\n255 128 0\n"
    assert decode(data, "g.pgm") == [
        ["#000000", "#808080", "#ffffff"],
        ["#ffffff", "#808080", "#000000"],
    ]


def test_a_plain_bitmap_treats_one_as_ink():
    """P1 is the only netpbm where 1 means black: it is ink, not light."""
    assert decode(b"P1\n2 2\n1 0\n0 1\n", "b.pbm") == [
        ["#000000", "#ffffff"],
        ["#ffffff", "#000000"],
    ]


def test_a_binary_bitmap_packs_rows_to_whole_bytes():
    """Most significant bit leftmost here - the opposite way round to XBM."""
    data = b"P4\n12 2\n" + bytes([0b11110000, 0b11110000, 0b00001111, 0b00000000])
    rows = decode(data, "b.pbm")
    shapes = [
        "".join("#" if cell == "#000000" else "." for cell in row) for row in rows
    ]
    assert shapes == ["####....####", "....####...."]


# ------------------------------------------------------- netpbm, the corners


def test_a_comment_may_sit_anywhere_in_the_header():
    """Including between the width and the height, which a split() would miss."""
    data = b"P2\n# a comment\n3\n# another\n1\n# and one more\n255\n0 128 255\n"
    assert decode(data, "c.pgm") == [["#000000", "#808080", "#ffffff"]]


def test_maxval_scales_the_samples():
    """A maxval of 1023 makes each sample two bytes, big-endian."""
    data = b"P5\n2 1\n1023\n" + bytes([0x00, 0x00, 0x03, 0xFF])
    assert decode(data, "w.pgm") == [["#000000", "#ffffff"]]


def test_a_small_maxval_scales_up():
    assert decode(b"P2\n2 1\n3\n0 3\n", "s.pgm") == [["#000000", "#ffffff"]]


def test_whitespace_between_header_and_binary_data_is_one_byte():
    data = b"P6\n1 1\n255\n\xff\x00\x00"
    assert decode(data, "t.ppm") == [["#ff0000"]]


@pytest.mark.parametrize(
    ("data", "because"),
    [
        (b"P6\n", "the header ends before the image does"),
        (b"P6\nwide tall 255\n", "the header is not numbers"),
        (b"P6\n0 4 255\n", "has no pixels"),
        (b"P6\n2 2 0\n", "out of range"),
        (b"P6\n4 4 255\n\x00\x00\x00", "where 48 were declared"),
        (b"P4\n12 2\n\xff", "the pixel data ends early"),
        (b"P3\n4 4\n255\n1 2 3", "samples where 48 were declared"),
        (b"P2\n2 1\n255\nnot numbers", "not a number"),
    ],
    ids=[
        "truncated header",
        "non-numeric header",
        "zero width",
        "zero maxval",
        "truncated binary data",
        "truncated bitmap data",
        "truncated ascii data",
        "non-numeric sample",
    ],
)
def test_a_broken_netpbm_says_what_is_wrong(data, because):
    with pytest.raises(TclError, match=because):
        decode(data, "broken.ppm")


def test_the_error_names_the_file_as_tk_does():
    with pytest.raises(TclError, match=r'image file "broken\.ppm"'):
        decode(b"P6\n", "broken.ppm")


# ---------------------------------------------------- not yet, but by name


# ----------------------------------------------------------------------- png


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    """One PNG chunk, length and CRC included."""
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + zlib.crc32(kind + payload).to_bytes(4, "big")
    )


def build_png(rows_of_rgb, filter_type=0):
    """A PNG with every row using ``filter_type``.

    Written by hand because Pillow chooses filters adaptively, so saving
    through it exercises whichever ones it happens to pick and never proves
    the other four work. Paeth in particular is the one with real arithmetic
    in it, and nothing else will reach it reliably.
    """
    height = len(rows_of_rgb)
    width = len(rows_of_rgb[0])
    step = 3
    stride = width * step
    flat = bytearray()
    for row in rows_of_rgb:
        for pixel in row:
            flat += bytes(pixel)

    filtered = bytearray()
    for y in range(height):
        base = y * stride
        filtered.append(filter_type)
        for x in range(stride):
            value = flat[base + x]
            left = flat[base + x - step] if x >= step else 0
            above = flat[base - stride + x] if y else 0
            corner = flat[base - stride + x - step] if y and x >= step else 0
            if filter_type == 1:
                value -= left
            elif filter_type == 2:
                value -= above
            elif filter_type == 3:
                value -= (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - corner
                candidates = (
                    (abs(estimate - left), left),
                    (abs(estimate - above), above),
                    (abs(estimate - corner), corner),
                )
                value -= min(candidates)[1]
            filtered.append(value & 0xFF)

    header = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 0])  # depth 8, colour type 2, no interlace
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(filtered)))
        + png_chunk(b"IEND", b"")
    )


def gradient(width=9, height=7):
    return [
        [
            ((x * 7 + y * 3) % 256, (x * x + y) % 256, (x + y * 11) % 256)
            for x in range(width)
        ]
        for y in range(height)
    ]


@pytest.mark.parametrize(
    ("mode", "colour_type"),
    [("RGB", 2), ("L", 0), ("P", 3), ("RGBA", 6), ("LA", 4)],
    ids=["RGB", "greyscale", "palette", "RGBA", "greyscale+alpha"],
)
def test_every_png_colour_type_matches_pillow(mode, colour_type, tmp_path):
    image = photograph(41, 27).convert(mode)
    path = tmp_path / "shot.png"
    image.save(path)
    assert decode(path.read_bytes(), str(path)) == as_rows(image)


@pytest.mark.parametrize(
    "filter_type", [0, 1, 2, 3, 4], ids=["none", "sub", "up", "average", "paeth"]
)
def test_every_row_filter_is_undone(filter_type):
    """Pillow picks filters adaptively, so these are forced by hand."""
    pixels = gradient()
    data = build_png(pixels, filter_type)
    expected = [["#{:02x}{:02x}{:02x}".format(*p) for p in row] for row in pixels]
    assert decode(data, "f.png") == expected


def test_pixel_data_split_across_several_idat_chunks(tmp_path):
    """Real encoders split IDAT; Pillow does not for an image this small.

    So nothing in this file had more than one IDAT chunk, and keeping only
    the last one instead of concatenating them passed the whole suite.
    """
    pixels = gradient(16, 12)
    whole = build_png(pixels)
    # Pull the single IDAT payload back out and deal it into three chunks.
    at = whole.index(b"IDAT") + 4
    length = int.from_bytes(whole[at - 8 : at - 4], "big")
    payload = whole[at : at + length]
    third = max(1, len(payload) // 3)
    pieces = [payload[:third], payload[third : 2 * third], payload[2 * third :]]
    rebuilt = (
        whole[: at - 8]
        + b"".join(png_chunk(b"IDAT", piece) for piece in pieces if piece)
        + png_chunk(b"IEND", b"")
    )
    assert rebuilt.count(b"IDAT") == 3
    expected = [["#{:02x}{:02x}{:02x}".format(*p) for p in row] for row in pixels]
    assert decode(rebuilt, "split.png") == expected


def test_a_transparent_png_pixel_becomes_a_hole(tmp_path):
    """Below half alpha there is nothing to blend with: a half-cell paints or not."""
    image = PIL.new("RGBA", (3, 1))
    image.putpixel((0, 0), (255, 0, 0, 255))
    image.putpixel((1, 0), (0, 255, 0, 10))
    image.putpixel((2, 0), (0, 0, 255, 200))
    path = tmp_path / "a.png"
    image.save(path)
    assert decode(path.read_bytes(), str(path)) == [["#ff0000", None, "#0000ff"]]


def test_a_palette_png_honours_its_trns_chunk(tmp_path):
    """bits=8 on purpose: with two colours Pillow writes a depth-1 palette,
    and the decode then fails for the depth rather than for the tRNS, which
    is a test that passes for the wrong reason."""
    image = PIL.new("P", (2, 1))
    image.putpalette([255, 0, 0, 0, 0, 255] + [0, 0, 0] * 254)
    image.putpixel((0, 0), 0)
    image.putpixel((1, 0), 1)
    path = tmp_path / "p.png"
    image.save(path, bits=8, transparency=bytes([0, 255]))
    assert decode(path.read_bytes(), str(path)) == [[None, "#0000ff"]]


#: Adam7's seven passes, repeated here rather than imported: a test that
#: shares the table with the code under test cannot catch a wrong table.
ADAM7 = (
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
)


def build_interlaced_png(rows_of_rgb):
    """A real Adam7 PNG.

    Written by hand because Pillow cannot make one: its ``interlace=`` is a
    GIF option and does nothing at all to a PNG. The test this replaces set
    the IHDR byte over progressive data, which was a file no decoder should
    accept and proved only that the flag was being read.

    Pillow *reads* these, so every test below checks the file twice: that
    Pillow agrees it is a valid interlaced PNG, and that we decode it the
    same way. A bug in this encoder shows up as Pillow disagreeing, not as
    a false pass.
    """
    height, width = len(rows_of_rgb), len(rows_of_rgb[0])
    raw = bytearray()
    for x0, y0, dx, dy in ADAM7:
        across = 0 if width <= x0 else (width - x0 + dx - 1) // dx
        down = 0 if height <= y0 else (height - y0 + dy - 1) // dy
        if not across or not down:
            continue
        for row in range(down):
            raw.append(0)  # filter: none
            for column in range(across):
                raw += bytes(rows_of_rgb[y0 + row * dy][x0 + column * dx])
    header = (
        width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 2, 0, 0, 1])
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(bytes(raw)))
        + png_chunk(b"IEND", b"")
    )


@pytest.mark.parametrize(
    ("width", "height"),
    [(1, 1), (2, 2), (3, 5), (5, 3), (7, 7), (8, 8), (9, 3), (16, 16), (41, 27)],
    ids=lambda v: str(v),
)
def test_an_interlaced_png_decodes(width, height):
    """Tk 9.0.2 reads these and now so do we.

    The small sizes are the point. Adam7 spreads an image over seven passes
    on a lattice of eight, so anything under eight pixels leaves some passes
    EMPTY - and a decoder that does not skip them reads the next pass's
    bytes as this one's and every pass after it is wrong.
    """
    pixels = gradient(width, height)
    data = build_interlaced_png(pixels)
    assert data[data.index(b"IHDR") + 4 + 12] == 1, "the file must really be interlaced"

    expected = [["#{:02x}{:02x}{:02x}".format(*p) for p in row] for row in pixels]
    # Pillow first: if it disagrees, the encoder above is wrong and the
    # comparison that follows would be two wrongs agreeing.
    assert as_rows(PIL.open(io.BytesIO(data))) == expected
    assert decode(data, "i.png") == expected


def test_interlaced_and_progressive_give_the_same_picture():
    """The same pixels, stored both ways, must arrive identical."""
    pixels = gradient(23, 17)
    assert decode(build_interlaced_png(pixels), "i.png") == decode(
        build_png(pixels), "p.png"
    )


def test_an_interlaced_png_that_ends_early_says_so():
    pixels = gradient(16, 16)
    whole = build_interlaced_png(pixels)
    at = whole.index(b"IDAT") + 4
    length = int.from_bytes(whole[at - 8 : at - 4], "big")
    payload = zlib.decompress(whole[at : at + length])
    truncated = (
        b"\x89PNG\r\n\x1a\n"
        + whole[8 : at - 8]
        + png_chunk(b"IDAT", zlib.compress(payload[: len(payload) // 2]))
        + png_chunk(b"IEND", b"")
    )
    with pytest.raises(TclError, match=r"bytes of pixel data where .* were declared"):
        decode(truncated, "short.png")


def test_an_impossible_interlace_method_is_refused():
    header = (4).to_bytes(4, "big") + (4).to_bytes(4, "big") + bytes([8, 2, 0, 0, 7])
    data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(b"\x00" * 16))
        + png_chunk(b"IEND", b"")
    )
    with pytest.raises(TclError, match="interlace method 7 is not one"):
        decode(data, "odd.png")


def test_a_sixteen_bit_png_is_refused_by_name(tmp_path):
    path = tmp_path / "deep.png"
    PIL.new("I;16", (4, 4)).save(path)
    with pytest.raises(TclError, match="bit depth of 16 is not supported"):
        decode(path.read_bytes(), str(path))


@pytest.mark.parametrize(
    ("data", "because"),
    [
        (b"\x89PNG\r\n\x1a\n", "there is no IHDR chunk"),
        (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(
                b"IHDR",
                (4).to_bytes(4, "big")
                + (4).to_bytes(4, "big")
                + bytes([8, 2, 0, 0, 0]),
            ),
            "there is no IDAT chunk",
        ),
        (
            b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", b"\x00" * 5),
            "IHDR chunk is too short",
        ),
        (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(
                b"IHDR",
                (2).to_bytes(4, "big")
                + (2).to_bytes(4, "big")
                + bytes([8, 2, 0, 0, 0]),
            )
            + png_chunk(b"IDAT", b"not deflate data"),
            "will not inflate",
        ),
        (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(
                b"IHDR",
                (2).to_bytes(4, "big")
                + (2).to_bytes(4, "big")
                + bytes([8, 9, 0, 0, 0]),
            )
            + png_chunk(b"IDAT", zlib.compress(b"\x00\x00")),
            "colour type 9 is not a colour type",
        ),
        (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(
                b"IHDR",
                (2).to_bytes(4, "big")
                + (2).to_bytes(4, "big")
                + bytes([8, 2, 0, 0, 0]),
            )
            + png_chunk(b"IDAT", zlib.compress(b"\x00\x01\x02")),
            "where 14 were declared",
        ),
    ],
    ids=[
        "no IHDR",
        "no IDAT",
        "short IHDR",
        "bad deflate",
        "bad colour type",
        "short pixel data",
    ],
)
def test_a_broken_png_says_what_is_wrong(data, because):
    with pytest.raises(TclError, match=because):
        decode(data, "broken.png")


def test_a_bad_filter_byte_is_named():
    pixels = [[(1, 2, 3)]]
    data = build_png(pixels, 0)
    # Reach into the IDAT and set an impossible filter byte.
    broken = bytearray(zlib.compress(b"\x09" + bytes([1, 2, 3])))
    rebuilt = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(
            b"IHDR",
            (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0]),
        )
        + png_chunk(b"IDAT", bytes(broken))
        + png_chunk(b"IEND", b"")
    )
    assert data  # the well-formed one still builds
    with pytest.raises(TclError, match="filter 9, which is not a filter"):
        decode(rebuilt, "f.png")


# ----------------------------------------------------------------------- gif


def save_gif(image, **options):
    """A GIF as bytes, with what Pillow reads back out of it.

    Read back rather than compared to the original, because GIF is limited
    to 256 colours and Pillow quantises on the way in: comparing against the
    source image would be asserting that we made the same quantising
    decisions, which is not the claim.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="GIF", **options)
    data = buffer.getvalue()
    return data, as_rows(PIL.open(io.BytesIO(data)))


def test_a_gif_matches_pillow():
    data, expected = save_gif(photograph(41, 27))
    assert data[:6] in (b"GIF87a", b"GIF89a")
    assert decode(data, "t.gif") == expected


def test_an_interlaced_gif_is_put_back_in_order():
    """Four passes of rows. Unlike PNG's Adam7 this is cheap, so it is done."""
    data, expected = save_gif(photograph(41, 27), interlace=True)
    assert decode(data, "i.gif") == expected


def test_a_gif_large_enough_to_grow_the_lzw_table():
    """200x140 runs the code width up and makes the encoder emit clears.

    A small image never leaves the starting width, so nothing smaller than
    this exercises the table growing or resetting at all.
    """
    data, expected = save_gif(photograph(200, 140))
    assert decode(data, "big.gif") == expected


def test_a_one_pixel_gif():
    data, expected = save_gif(PIL.new("RGB", (1, 1), (255, 0, 0)))
    assert decode(data, "dot.gif") == expected


def test_a_transparent_gif_index_becomes_a_hole():
    image = PIL.new("P", (3, 1))
    image.putpalette([255, 0, 0, 0, 255, 0, 0, 0, 255] + [0, 0, 0] * 253)
    image.putpixel((0, 0), 0)
    image.putpixel((1, 0), 1)
    image.putpixel((2, 0), 2)
    buffer = io.BytesIO()
    image.save(buffer, format="GIF", transparency=1)
    assert decode(buffer.getvalue(), "t.gif") == [["#ff0000", None, "#0000ff"]]


def test_a_gif_with_a_local_colour_table():
    """A frame may carry its own palette instead of using the global one."""
    header = (
        b"GIF89a"
        + (2).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + bytes([0x80, 0, 0])  # a global table, 2 entries
        + bytes([0, 0, 0, 255, 255, 255])
    )
    # An image descriptor that declares its own two-entry table, red and blue.
    descriptor = (
        bytes([0x2C])
        + (0).to_bytes(2, "little")
        + (0).to_bytes(2, "little")
        + (2).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + bytes([0x80])  # local table flag, 2 entries
        + bytes([255, 0, 0, 0, 0, 255])
    )
    # Two pixels, indices 0 and 1. Minimum code size 2, so clear is 4 and
    # end is 5, and the codes 4, 0, 1, 5 pack three bits at a time,
    # least significant first, into 0x44 0x0a.
    body = bytes([2, 2, 0x44, 0x0A, 0]) + bytes([0x3B])
    assert decode(header + descriptor + body, "local.gif") == [["#ff0000", "#0000ff"]]


def test_a_graphic_control_block_without_the_transparency_flag():
    """Byte 4 of the block is only an index when bit 0 of byte 1 says so.

    Every other GIF here that carries a graphic control block has
    transparency switched on, so ignoring the flag entirely passed the whole
    suite - and would turn colour zero into a hole in any GIF that stores a
    delay but no transparency, which is most animations.
    """
    header = (
        b"GIF89a"
        + (2).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + bytes([0x80, 0, 0])
        + bytes([0, 0, 0, 255, 255, 255])
    )
    # Graphic control: flags 0x00 - no transparency - but byte 4 is still 0,
    # which is a perfectly good index into the table.
    control = bytes([0x21, 0xF9, 4, 0x00, 0, 0, 0, 0])
    descriptor = (
        bytes([0x2C])
        + (0).to_bytes(2, "little")
        + (0).to_bytes(2, "little")
        + (2).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + bytes([0])
    )
    body = bytes([2, 2, 0x44, 0x0A, 0]) + bytes([0x3B])
    assert decode(header + control + descriptor + body, "gce.gif") == [
        ["#000000", "#ffffff"]
    ]


def test_extension_blocks_are_walked_past():
    """A comment between the header and the image must not stop the read."""
    data, expected = save_gif(photograph(8, 6), comment=b"hello from the test")
    assert b"hello from the test" in data
    assert decode(data, "c.gif") == expected


@pytest.mark.parametrize(
    ("data", "because"),
    [
        (b"GIF89a", "ends inside its header"),
        (
            b"GIF89a" + bytes([1, 0, 1, 0, 0, 0, 0]) + bytes([0x3B]),
            "no image in this file",
        ),
        (
            b"GIF89a"
            + bytes([1, 0, 1, 0, 0x80, 0, 0])
            + bytes([0, 0, 0, 255, 255, 255])
            + bytes([0x55]),
            "is not a block this reads",
        ),
        (
            b"GIF89a"
            + bytes([1, 0, 1, 0, 0x80, 0, 0])
            + bytes([0, 0, 0, 255, 255, 255])
            + bytes([0x2C])
            + (0).to_bytes(2, "little")
            + (0).to_bytes(2, "little")
            + (0).to_bytes(2, "little")
            + (0).to_bytes(2, "little")
            + bytes([0])
            + bytes([2, 0, 0x3B]),
            "has no pixels",
        ),
        (
            b"GIF89a"
            + bytes([2, 0, 1, 0, 0x80, 0, 0])
            + bytes([0, 0, 0, 255, 255, 255])
            + bytes([0x2C])
            + (0).to_bytes(2, "little")
            + (0).to_bytes(2, "little")
            + (2).to_bytes(2, "little")
            + (1).to_bytes(2, "little")
            + bytes([0])
            + bytes([2, 0, 0x3B]),
            "pixels where 2 were declared",
        ),
    ],
    ids=[
        "truncated header",
        "trailer with no image",
        "unknown block",
        "zero size",
        "too few pixels",
    ],
)
def test_a_broken_gif_says_what_is_wrong(data, because):
    with pytest.raises(TclError, match=because):
        decode(data, "broken.gif")


def test_an_impossible_lzw_code_size_is_refused():
    from tkcurses._core.imagefiles import _gif_lzw

    with pytest.raises(TclError, match="minimum code size of 1 is impossible"):
        _gif_lzw(b"\x00", 1, 4, "x.gif")


def test_lzw_handles_a_code_defined_by_the_run_that_uses_it():
    """The KwKwK case: an encoder may name a sequence as it defines it.

    Legal, common in runs of one colour, and the usual place a decoder
    written from the description alone goes wrong.
    """
    from tkcurses._core.imagefiles import _gif_lzw

    # minimum 2: clear=4, end=5. Codes 4, 0, 6, 5 - where 6 is defined by
    # the very step that uses it. It expands to [0, 0], so with the single
    # 0 before it the run is three pixels, not four.
    bits = [4, 0, 6, 5]
    stream = bytearray()
    held = width = 0
    bit_count = 0
    width = 3
    for code in bits:
        held |= code << bit_count
        bit_count += width
        while bit_count >= 8:
            stream.append(held & 0xFF)
            held >>= 8
            bit_count -= 8
    if bit_count:
        stream.append(held & 0xFF)
    assert list(_gif_lzw(bytes(stream), 2, 8, "k.gif")) == [0, 0, 0]
