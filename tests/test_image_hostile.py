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

"""Image files built to hurt: each was carried out against the decoder
before it was fixed, and each test fails without its fix.

A file is not trusted. Before these: a 66-byte interlaced PNG made the
decoder allocate a gigabyte, a PNG of zeros inflated without limit, a GIF's
LZW stream ran on far past its declared size, and truncated or malformed
files raised IndexError, ValueError or UnicodeDecodeError past a program
that catches TclError. Memory is measured with tracemalloc, which sees
every bytearray and list the decoder makes.
"""

from __future__ import annotations

import struct
import tracemalloc
import zlib

import pytest

import tkcurses
from tkcurses import BitmapImage, Misc, PhotoImage, TclError
from tkcurses._core.imagefiles import MAX_PIXELS, _gif_lzw, decode

MB = 1 << 20


@pytest.fixture
def root():
    previous = tkcurses._default_root
    yield Misc()
    tkcurses._default_root = previous


def chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def png(
    width: int, height: int, idat: bytes, *, colour: int = 6, interlace: int = 0
) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, interlace)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def peak_during(action) -> int:
    """The most memory ``action`` held at once, whatever it raised."""
    tracemalloc.start()
    try:
        action()
    except TclError:
        pass
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return peak


# --------------------------------------------------------------- the budget


@pytest.mark.parametrize("interlace", [0, 1])
def test_a_tiny_png_cannot_ask_for_gigabytes(interlace):
    hostile = png(16384, 16384, zlib.compress(b"\0"), interlace=interlace)
    assert len(hostile) < 100
    with pytest.raises(TclError, match="larger than this reads"):
        decode(hostile, "huge.png")
    assert peak_during(lambda: decode(hostile, "huge.png")) < MB


def test_an_interlaced_png_within_the_budget_allocates_nothing_before_its_data():
    """At the limit, the header is allowed - and a stream too short for it
    is refused before the image is laid out, not after."""
    hostile = png(4096, 4096, zlib.compress(b"\0"), interlace=1)
    with pytest.raises(TclError, match="were declared"):
        decode(hostile, "short.png")
    assert peak_during(lambda: decode(hostile, "short.png")) < MB


def test_the_budget_is_width_times_height():
    assert MAX_PIXELS == 4096 * 4096
    for width, height in ((4097, 4096), (MAX_PIXELS + 1, 1), (1, MAX_PIXELS + 1)):
        with pytest.raises(TclError, match="larger than this reads"):
            decode(png(width, height, zlib.compress(b"\0")), "x.png")


def test_a_large_netpbm_header_is_refused_by_the_same_budget():
    with pytest.raises(TclError, match="larger than this reads"):
        decode(b"P6 100000 100000 255\n\0\0\0", "x.ppm")


# ---------------------------------------------------------- inflating


def test_a_png_inflates_no_further_than_its_header_declares():
    """A 1x1 image whose data inflates to 64 MB of zeros: one pixel, and
    the rest is never inflated."""
    bomb = png(1, 1, zlib.compress(b"\0" * (64 * MB), 9), colour=2)
    assert len(bomb) < 100_000
    assert decode(bomb, "bomb.png") == [["#000000"]]
    assert peak_during(lambda: decode(bomb, "bomb.png")) < 2 * MB


def test_lzw_stops_at_the_declared_size():
    # minimum 2: codes 4 (clear), 0, 6, 5 (end). Code 6 is defined by the
    # step that uses it and expands to two pixels, so the run is three -
    # one more than the two declared here.
    stream = bytearray()
    held = count = 0
    for code in (4, 0, 6, 5):
        held |= code << count
        count += 3
        while count >= 8:
            stream.append(held & 0xFF)
            held >>= 8
            count -= 8
    if count:
        stream.append(held & 0xFF)
    assert list(_gif_lzw(bytes(stream), 2, 2, "k.gif")) == [0, 0]


def test_a_large_gif_header_is_refused_before_decoding():
    gif = (
        b"GIF89a"
        + struct.pack("<HHBBB", 65535, 2000, 0x80, 0, 0)
        + b"\0\0\0\xff\xff\xff"
        + b"\x2c"
        + struct.pack("<HHHHB", 0, 0, 65535, 2000, 0)
        + b"\x02\x02\x4c\x01\x00\x3b"
    )
    with pytest.raises(TclError, match="larger than this reads"):
        decode(gif, "huge.gif")


# --------------------------------------------- one exception, TclError

GIF_HEADER = b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\0\0\0\xff\xff\xff"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(GIF_HEADER + b"\x21", id="ends after an extension marker"),
        pytest.param(GIF_HEADER + b"\x21\xf9\x01\x01\x00", id="short graphic control"),
        pytest.param(GIF_HEADER + b"\x2c\0\0\0\0\x01", id="ends inside a descriptor"),
        pytest.param(
            GIF_HEADER + b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0),
            id="ends before its pixel data",
        ),
    ],
)
def test_a_truncated_gif_is_a_tcl_error(data):
    with pytest.raises(TclError):
        decode(data, "bad.gif")


def test_a_photo_from_a_hostile_file_raises_only_tcl_error(root, tmp_path):
    for name, data in (
        ("huge.png", png(100000, 100000, zlib.compress(b"\0"), interlace=1)),
        ("bad.gif", GIF_HEADER + b"\x21"),
    ):
        (tmp_path / name).write_bytes(data)
        with pytest.raises(TclError):
            PhotoImage(master=root, file=str(tmp_path / name))


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(
            b"#define a_width x\n#define a_height 1\nstatic char a[] = {0};", id="width"
        ),
        pytest.param(
            b"#define a_width 1\n#define a_height " + b"9" * 5000 + b"\n{0}", id="huge"
        ),
        pytest.param(b"\xff\xfe#define a_width 1", id="not utf-8"),
    ],
)
def test_a_malformed_bitmap_file_is_a_format_error(root, tmp_path, content):
    path = tmp_path / "bad.xbm"
    path.write_bytes(content)
    with pytest.raises(TclError, match="format error in bitmap data"):
        BitmapImage(master=root, file=str(path))
