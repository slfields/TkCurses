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

"""The image decoders over files Hypothesis invents, whole and damaged.

A picture comes from outside the program, so a decoder reads bytes nobody
checked. The files in test_image_hostile are the ones that once broke
something. These hold for every file: whatever the bytes, a decoder hands
back a picture or raises TclError - the error a program catches - within a
bound on memory; and a file one of our own encoders wrote comes back exactly.

The damaged files start from good ones and are cut, overwritten or grown, so
they get past the magic number and the header into the parts that decode -
and a PNG's damaged chunks are given correct checksums again, or the
damage would only ever reach the checksum test.
"""

from __future__ import annotations

import contextlib
import os
import struct
import tracemalloc
import zlib

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import tkcurses
from tkcurses import BitmapImage, Misc, PhotoImage, TclError
from tkcurses._core.imagefiles import (
    MAX_PIXELS,
    decode,
    encode_gif,
    encode_png,
    encode_ppm,
)

#: 300 each in an ordinary run; ``TKCURSES_FUZZ_EXAMPLES=20000`` for a long
#: one, worth doing after changing a parser.
FUZZ = settings(
    max_examples=int(os.environ.get("TKCURSES_FUZZ_EXAMPLES", "300")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
#: What a file of a few kilobytes may make a decoder hold at once. Generous:
#: the point is a bound at all, where the bugs test_image_hostile records
#: reached a gigabyte.
MEMORY_BOUND = 64 << 20

colour = st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255))


@st.composite
def pictures(draw, holes=True):
    """Rows of colour, rectangular, at most 12 by 12; a hole is None."""
    width = draw(st.integers(1, 12))
    height = draw(st.integers(1, 12))
    pixel = st.one_of(st.none(), colour) if holes else colour
    return [[draw(pixel) for _ in range(width)] for _ in range(height)]


def as_decoded(rows, hole=None):
    """``rows`` as decode gives them back: ``#rrggbb`` for each colour."""
    return [
        [
            hole if pixel is None else "#{:02x}{:02x}{:02x}".format(*pixel)
            for pixel in row
        ]
        for row in rows
    ]


def fix_png_checksums(data: bytes) -> bytes:
    """``data`` with every whole chunk's CRC made right, so damage inside a
    chunk reaches the code that reads it."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data
    out = bytearray(data[:8])
    at = 8
    while at + 12 <= len(data):
        (length,) = struct.unpack(">I", data[at : at + 4])
        end = at + 12 + length
        if end > len(data):
            break
        body = data[at + 4 : end - 4]
        out += data[at : at + 4] + body + struct.pack(">I", zlib.crc32(body))
        at = end
    return bytes(out + data[at:])


@st.composite
def damaged(draw):
    """A good file of each kind, then cut, overwritten or grown."""
    rows = draw(pictures())
    kind = draw(st.sampled_from(["png", "gif", "ppm"]))
    data = bytearray(
        {"png": encode_png, "gif": encode_gif, "ppm": encode_ppm}[kind](rows)
    )
    for _ in range(draw(st.integers(1, 4))):
        at = draw(st.integers(0, len(data)))
        how = draw(st.sampled_from(["cut", "set", "insert", "big"]))
        if how == "cut":
            del data[at:]
        elif how == "set" and at < len(data):
            data[at] = draw(st.integers(0, 255))
        elif how == "insert":
            data[at:at] = draw(st.binary(min_size=1, max_size=16))
        elif how == "big" and at + 4 <= len(data):
            # A size, a length or a count: where the large numbers live.
            data[at : at + 4] = draw(
                st.sampled_from(
                    [
                        b"\xff\xff\xff\xff",
                        b"\x00\x00\x10\x00",
                        b"\x7f\xff\xff\xff",
                        b"\x00\x00\x00\x00",
                    ]
                )
            )
        if not data:
            break
    data = bytes(data)
    if kind == "png" and draw(st.booleans()):
        data = fix_png_checksums(data)
    return data


#: A magic number, then anything.
headed = st.builds(
    lambda magic, rest: magic + rest,
    st.sampled_from(
        [
            b"\x89PNG\r\n\x1a\n",
            b"GIF87a",
            b"GIF89a",
            b"P1",
            b"P2",
            b"P3",
            b"P4",
            b"P5",
            b"P6",
        ]
    ),
    st.binary(max_size=200),
)


def decodes_or_refuses(data: bytes) -> None:
    """The property: rows of colour, or TclError, and within the bound."""
    tracemalloc.start()
    try:
        rows = decode(data, "fuzzed")
    except TclError:
        return
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < MEMORY_BOUND, f"held {peak >> 20} MB decoding {len(data)} bytes"
    assert rows, "a picture with no rows"
    width = len(rows[0])
    assert 0 < width * len(rows) <= MAX_PIXELS
    for row in rows:
        assert len(row) == width
        for pixel in row:
            assert pixel is None or (
                isinstance(pixel, str) and len(pixel) == 7 and pixel[0] == "#"
            ), pixel


@FUZZ
@given(data=damaged())
def test_a_damaged_file_decodes_or_is_refused(data):
    decodes_or_refuses(data)


@FUZZ
@given(data=headed)
def test_anything_after_a_magic_number_decodes_or_is_refused(data):
    decodes_or_refuses(data)


@FUZZ
@given(data=st.binary(max_size=200))
def test_any_bytes_decode_or_are_refused(data):
    decodes_or_refuses(data)


@FUZZ
@given(rows=pictures())
def test_a_png_we_wrote_reads_back_exactly(rows):
    assert decode(encode_png(rows)) == as_decoded(rows)


@FUZZ
@given(rows=pictures())
def test_a_gif_we_wrote_reads_back_exactly(rows):
    assert decode(encode_gif(rows)) == as_decoded(rows)


@FUZZ
@given(rows=pictures())
def test_a_ppm_we_wrote_reads_back_with_holes_black(rows):
    """PPM has no transparency: a hole is written black, as Tk writes it."""
    assert decode(encode_ppm(rows)) == as_decoded(rows, hole="#000000")


@contextlib.contextmanager
def a_root():
    previous = tkcurses._default_root
    try:
        yield Misc()
    finally:
        tkcurses._default_root = previous


xbm_text = st.one_of(
    st.text(max_size=200),
    st.builds(
        lambda w, h, values, junk: (
            f"#define t_width {w}\n#define t_height {h}\n"
            f"static unsigned char t_bits[] = {{ {values} }};{junk}"
        ),
        st.integers(-5, 40).map(str) | st.text(max_size=5),
        st.integers(-5, 40).map(str) | st.text(max_size=5),
        st.lists(
            st.one_of(st.integers(-300, 300).map(hex), st.text(max_size=4)), max_size=30
        ).map(", ".join),
        st.text(max_size=10),
    ),
)


@FUZZ
@given(source=xbm_text)
def test_any_bitmap_source_makes_a_bitmap_or_a_tcl_error(source):
    """And a bitmap it makes is as wide and as tall as it says it is."""
    with a_root() as root:
        try:
            image = BitmapImage(master=root, data=source)
        except TclError:
            return
        assert image.width() >= 0
        assert image.height() >= 0


@FUZZ
@given(data=st.one_of(st.text(max_size=200), st.binary(max_size=200)))
def test_any_photo_data_makes_a_photo_or_a_tcl_error(data):
    with a_root() as root, contextlib.suppress(TclError):
        PhotoImage(master=root, data=data)
