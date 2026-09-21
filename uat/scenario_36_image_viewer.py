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

"""An image viewer: open a real PNG, GIF, PPM, PGM or XBM and look at it.

What to do: press `o`. The file dialog opens on a directory of images this
scenario writes for itself, so there is always something to open whatever
machine it is run on. Choose one and it is drawn.

The dialog is the other half of what is being shown. It lists **only
openable images**, because `filetypes` now means what it means in Tk - a
type may name several patterns, and the chooser above the filter box
reaches the types after the first. Switch it to `All files` and the text
file appears; switch back and it does not.

What to look for: the status line reports the format, the size in
**pixels**, and the size in **cells**, and the second is always half the
first in height. Images load at their native size, exactly as Tk loads
them - so a big one does not fit, and `f` is what fits it, by subsampling.
That is the viewer's job and not the image's, which is worth knowing before
wondering why a 200-pixel-tall photograph did not shrink itself.

`bad.txt` and `interlaced.png` are in the directory on purpose. Neither
crashes; both say what is wrong, and the second says it by name, because
Tk 9.0.2 reads interlaced PNG and this does not.

What to look for: docs/UAT_IMAGES.md, "UAT: The image viewer", checks 36.1
to 36.4.

Keys: `o` open, `f` fit or actual size, `n` next image in the folder,
`i` information, Escape quits.
"""

from __future__ import annotations

import pathlib
import struct
import tempfile
import zlib

import tkcurses
from tkcurses import filedialog
from uat import _support

TITLE = "36 - an image viewer"

#: What the dialog offers. Several patterns in a type and several types,
#: which is exactly what used to be impossible.
FILETYPES = (
    ("Images", "*.png *.gif *.ppm *.pgm *.xbm"),
    ("PNG", "*.png"),
    ("GIF", "*.gif"),
    ("Netpbm", "*.ppm *.pgm"),
    ("Bitmaps", "*.xbm"),
    ("All files", "*"),
)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    """One PNG chunk, length and CRC included."""
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + zlib.crc32(kind + payload).to_bytes(4, "big")
    )


def _png(path, width, height, pixels, interlaced=False):
    """A PNG written by hand, so the scenario needs no encoder installed."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        for x in range(width):
            raw += bytes(pixels(x, y))
    header = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 1 if interlaced else 0])
    )
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(raw)))
        + _chunk(b"IEND", b"")
    )


def _gif(path, width, height, palette, indices):
    """A GIF written by hand, uncompressed-style LZW: clear, literals, end."""
    minimum = 7  # a code size well above the palette we actually use
    clear, end = 1 << minimum, (1 << minimum) + 1
    width_bits = minimum + 1
    # A clear code every so often, because a decoder widens its codes as its
    # table fills and this encoder never does. Without them the two disagree
    # about the width partway through and the last pixel goes missing, which
    # is exactly how this was found: 383 pixels where 384 were declared.
    room = (1 << width_bits) - (clear + 2)
    codes: list[int] = [clear]
    since = 0
    for index in indices:
        if since >= room - 1:
            codes.append(clear)
            since = 0
        codes.append(index)
        since += 1
    codes.append(end)
    stream, held, count = bytearray(), 0, 0
    for code in codes:
        held |= code << count
        count += width_bits
        while count >= 8:
            stream.append(held & 0xFF)
            held >>= 8
            count -= 8
    if count:
        stream.append(held & 0xFF)
    blocks = bytearray()
    for start in range(0, len(stream), 255):
        piece = stream[start : start + 255]
        blocks.append(len(piece))
        blocks += piece
    blocks.append(0)
    table = bytearray()
    for entry in palette:
        table += bytes(entry)
    table += bytes(3 * (256 - len(palette)))
    path.write_bytes(
        b"GIF89a"
        + struct.pack("<HH", width, height)
        + bytes([0xF7, 0, 0])  # global table, 256 entries
        + bytes(table)
        + bytes([0x2C])
        + struct.pack("<HHHH", 0, 0, width, height)
        + bytes([0, minimum])
        + bytes(blocks)
        + bytes([0x3B])
    )


def make_images(folder):
    """Write one of everything, so the viewer always has something to open."""

    def wheel(x, y, w, h):
        return ((x * 255) // max(w - 1, 1), (y * 255) // max(h - 1, 1), 128)

    _png(folder / "gradient.png", 48, 32, lambda x, y: wheel(x, y, 48, 32))
    _png(folder / "interlaced.png", 16, 16, lambda x, y: wheel(x, y, 16, 16), True)
    _png(folder / "big.png", 160, 120, lambda x, y: wheel(x, y, 160, 120))

    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    _gif(
        folder / "blocks.gif",
        24,
        16,
        palette,
        [((x // 6) + (y // 4)) % 4 for y in range(16) for x in range(24)],
    )

    body = bytearray()
    for y in range(24):
        for x in range(36):
            body += bytes(wheel(x, y, 36, 24))
    (folder / "colour.ppm").write_bytes(b"P6\n36 24\n255\n" + bytes(body))

    grey = bytearray()
    for _y in range(20):
        for x in range(40):
            grey.append((x * 255) // 39)
    (folder / "ramp.pgm").write_bytes(b"P5\n40 20\n255\n" + bytes(grey))

    (folder / "arrow.xbm").write_text(
        "#define arrow_width 16\n"
        "#define arrow_height 12\n"
        "static char arrow_bits[] = {\n"
        "0x00,0x01,0x00,0x03,0x00,0x07,0x00,0x0f,\n"
        "0xff,0x1f,0xff,0x3f,0xff,0x3f,0xff,0x1f,\n"
        "0x00,0x0f,0x00,0x07,0x00,0x03,0x00,0x01};\n"
    )

    (folder / "bad.txt").write_text("I am not an image, and I will say so.\n")
    return folder


def build(root, screen):
    folder = make_images(pathlib.Path(tempfile.mkdtemp(prefix="tkcurses-images-")))
    state = {
        "image": None,
        "path": "",
        "fit": True,
        "note": "press o to open one",
        "shown": None,
    }

    screen.line(0, f" {TITLE} ")
    screen.footer(" o open  f fit/actual  n next  i info  Escape quits ")

    area = _support.content_area(root, top=4, bottom=2)
    canvas = tkcurses.Label(area, name="view", anchor="nw", image="")
    canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)

    def report():
        picture = state["image"]
        if picture is None:
            screen.line(1, f"  {state['note']}")
            screen.line(2, f"  images in {folder}")
            screen.line(3, "")
            return
        shown = state["shown"] or picture
        screen.line(
            1,
            f"  {pathlib.Path(state['path']).name}"
            f"   {picture.width()}x{picture.height()} pixels"
            f"   = {picture.width()}x{picture.cell_height()} cells",
        )
        screen.line(
            2,
            f"  showing {shown.width()}x{shown.cell_height()} cells"
            f"   {'fit to window' if state['fit'] else 'actual size'}"
            f"   area {area.winfo_width()}x{area.winfo_height()} cells",
        )
        screen.line(3, f"  {state['note']}")

    def show():
        """Put the image on the label, subsampled if it is being fitted.

        Fitting is the VIEWER's job. An image loads at its native size, the
        way Tk loads one, so a 160x120 PNG is 160 cells across and 60 rows
        down and most of it is off the screen until something shrinks it.
        """
        picture = state["image"]
        if picture is None:
            canvas.configure(image="")
            state["shown"] = None
            return
        shown = picture
        if state["fit"]:
            across = area.winfo_width() or 1
            down = (area.winfo_height() or 1) * 2  # rows are two pixels tall
            factor = 1
            while (
                picture.width() // factor > across or picture.height() // factor > down
            ):
                factor += 1
            if factor > 1:
                # reduce, not subsample. Fitting a photograph is exactly
                # what averaging is for: measured on these images, dropping
                # pixels is 38% to 93% further from a Lanczos reference at
                # every colour depth. subsample stays in the library because
                # it is Tk's and it is exact; it is not what a viewer wants.
                shown = picture.reduce(factor)
        # Held, or an image nothing references is collected and the label
        # draws nothing - the trap UAT 35 demonstrates on purpose.
        state["shown"] = shown
        canvas.configure(image=shown)

    def load(path):
        state["path"] = path
        try:
            # Which class depends on the file, and that is Tk's arrangement
            # rather than a convenience: XBM is BitmapImage's format and
            # PhotoImage will not read it, there or here. A viewer therefore
            # has to look before it chooses, and saying which class it chose
            # is half of what this scenario is for.
            head = pathlib.Path(path).read_bytes()[:64]
            if b"#define" in head:
                state["image"] = tkcurses.BitmapImage(
                    master=root, file=path, foreground="cyan"
                )
            else:
                state["image"] = tkcurses.PhotoImage(master=root, file=path)
            state["note"] = f"opened as {type(state['image']).__name__}"
        except tkcurses.TclError as error:
            state["image"] = None
            # The message, not a traceback. A viewer that dies on a file it
            # cannot read is worse than one that says why.
            state["note"] = str(error)
        show()
        root.update_layout()
        report()
        screen.refresh()

    def open_one(event=None):
        del event
        chosen = filedialog.askopenfilename(
            parent=root,
            title="Open an image",
            initialdir=str(folder),
            filetypes=FILETYPES,
        )
        if chosen:
            load(chosen)
        else:
            state["note"] = "cancelled"
            report()
            screen.refresh()
        return "break"

    def next_one(event=None):
        """Step through the folder, so every format can be seen quickly."""
        del event
        names = sorted(
            entry.name
            for entry in folder.iterdir()
            if entry.suffix.lstrip(".") in ("png", "gif", "ppm", "pgm", "xbm")
        )
        if not names:
            return "break"
        here = pathlib.Path(state["path"]).name
        index = names.index(here) + 1 if here in names else 0
        load(str(folder / names[index % len(names)]))
        return "break"

    def toggle_fit(event=None):
        del event
        state["fit"] = not state["fit"]
        show()
        root.update_layout()
        report()
        screen.refresh()
        return "break"

    def information(event=None):
        del event
        picture = state["image"]
        if picture is None:
            state["note"] = "nothing open"
        else:
            state["note"] = (
                f"type={picture.type()}"
                f"  registry={sorted(root.tk.images)}"
                f"  first pixel={picture.get(0, 0)}"
            )
        report()
        screen.refresh()
        return "break"

    root.bind("<Key-o>", open_one)
    root.bind("<Key-f>", toggle_fit)
    root.bind("<Key-n>", next_one)
    root.bind("<Key-i>", information)

    root.update_layout()
    next_one()


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
