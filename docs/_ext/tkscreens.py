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

"""Sample output in the documentation: an example, run, and its screen.

Decided with the user (TkCurses-imii.16): every widget, and every option
that visibly changes one, shows what it draws. The docstring holds only
the example, in a ``Sample output:`` section, so ``help()`` in a terminal
reads as code; the build runs it in a pseudo-terminal - the test suite's
own harness - and puts an SVG of the screen beside it. A picture made
that way cannot go stale, and an example that stops working fails the
build, which runs with warnings as errors.

An example is the body of a program. It runs after::

    import tkcurses as tk
    from tkcurses import ttk
    root = tk.Tk()

and before ``root.mainloop()``, in a terminal of 40 by 10 cells, and the
picture is cropped to what it drew. A first line ``# size: 60x15`` asks
for another size and is not shown. The same examples are written as
``{tkcurses-sample}`` blocks on Markdown pages.

A whole program, from ``examples/``, is shown by ``{tkcurses-example}``,
which runs the file as it is - its own imports and its own ``mainloop`` -
and can press keys before the picture is taken, so a screen can show a
menu open or a form filled in.

Screens are cached under the doctree directory by the example, its size
and the library's source, so an unchanged example is not run again and
any change to the library runs them all.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from docutils import nodes
from docutils.parsers.rst import Directive

if TYPE_CHECKING:
    from sphinx.application import Sphinx

ROOT = Path(__file__).resolve().parents[2]

PRELUDE = "import tkcurses as tk\nfrom tkcurses import ttk\nroot = tk.Tk()\n"
SECTION = "Sample output:"
#: ``Sample output:``, or ``Sample output (relief):`` for an option's sample -
#: ``Sample output (from, to):`` for one that shows several.
SECTION_LINE = re.compile(r"Sample output(?: \((\w+(?:, \w+)*)\))?:")
SIZE = re.compile(r"#\s*size:\s*(\d+)\s*x\s*(\d+)\s*$")
DEFAULT_SIZE = (40, 10)

#: Bumped when the drawing changes, so cached screens are drawn again.
RENDERER_VERSION = "7"

CELL_WIDTH = 8.4
CELL_HEIGHT = 17
MARGIN = 12
FONT = (
    "'DejaVu Sans Mono', 'Noto Sans Mono', Menlo, Consolas, "
    "'Liberation Mono', monospace"
)

#: The colours pyte names, as xterm draws them. Anything else pyte reports
#: is already a hex triple, for the 256-colour and direct-colour codes.
PALETTE = {
    "black": "000000",
    "red": "cd0000",
    "green": "00cd00",
    "brown": "cdcd00",
    "blue": "0000ee",
    "magenta": "cd00cd",
    "cyan": "00cdcd",
    "white": "e5e5e5",
    "brightblack": "7f7f7f",
    "brightred": "ff0000",
    "brightgreen": "00ff00",
    "brightbrown": "ffff00",
    "brightblue": "5c5cff",
    "brightmagenta": "ff00ff",
    "brightcyan": "00ffff",
    "brightwhite": "ffffff",
}
# TkCurses paints its widgets' default background black, so a terminal's
# own default background is drawn the same: a lighter one would outline
# every widget in a box that no real terminal shows.
DEFAULT_FG = "e5e5e5"
DEFAULT_BG = "000000"


class SampleError(Exception):
    """An example did not run, or drew nothing."""


def split_size(code: str) -> tuple[str, tuple[int, int]]:
    """The example without its ``# size:`` line, and the size it asks for."""
    lines = code.strip("\n").splitlines()
    if lines and (match := SIZE.match(lines[0].strip())):
        return "\n".join(lines[1:]), (int(match[1]), int(match[2]))
    return "\n".join(lines), DEFAULT_SIZE


def program(code: str) -> str:
    return PRELUDE + code.rstrip() + "\nroot.mainloop()\n"


# -- the screen ---------------------------------------------------------------


def capture(
    code: str, size: tuple[int, int], keys: tuple[str, ...] = (), *, whole: bool = False
) -> list[list[Any]]:
    """Run the example in a pseudo-terminal and return its cells, settled.

    ``whole`` runs ``code`` as a complete program rather than an example's
    body; ``keys`` are pressed, in order, once it has drawn.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support.terminal import TerminalHarness, TerminalTimeout

    cols, rows = size
    term = TerminalHarness(cols, rows)
    try:
        term.run_source(code if whole else program(code))
        try:
            term.wait_for(
                lambda t: any(line.strip() for line in t.display),
                message="the example to draw something",
            )
            term.wait_for_idle(0.3)
            for key in keys:
                term.send_keys(key)
                term.wait_for_idle(0.3)
        except TerminalTimeout as error:
            raise SampleError(f"{error}\n{term.stderr}") from None
        if term.exit_status is not None or term.stderr.strip():
            # It drew, then failed. An exception in a callback is printed and
            # the program carries on, as tkinter's rule is, so it shows only
            # on stderr - and a picture of what was drawn first would hide it.
            raise SampleError(f"the example failed\n{term.stderr}")
        # pyte has no field for dim, which TkCurses uses - a sunken border
        # is dim where a raised one is bold - so the harness's own record of
        # it goes in alongside.
        return [
            [
                SimpleNamespace(
                    **term.char_at(r, c)._asdict(),
                    dim=term.attrs_at(r, c)["dim"],
                )
                for c in range(cols)
            ]
            for r in range(rows)
        ]
    finally:
        term.close()


def _colour(name: str, default: str) -> str:
    if name == "default":
        return default
    return PALETTE.get(name, name)


def _mix(a: str, b: str) -> str:
    """Halfway from one hex colour to another, as a terminal draws dim."""
    return "".join(
        f"{(int(a[i : i + 2], 16) + int(b[i : i + 2], 16)) // 2:02x}" for i in (0, 2, 4)
    )


def _style(cell: Any) -> tuple[str, str, bool, bool]:
    name = cell.fg
    if cell.bold and name in PALETTE and not name.startswith("bright"):
        # Bold is bright, as xterm draws a named colour by default.
        name = "bright" + name
    fg = _colour(name, DEFAULT_FG)
    bg = _colour(cell.bg, DEFAULT_BG)
    if cell.reverse:
        fg, bg = bg, fg
    if getattr(cell, "dim", False):
        fg = _mix(fg, bg)
    return fg, bg, bool(cell.bold), bool(cell.underscore)


def _blank(cell: Any) -> bool:
    """Whether the example left the cell alone - not merely painted it black,
    which a widget's own background is."""
    return cell.data in ("", " ") and cell.bg == "default" and not cell.reverse


def crop(cells: list[list[Any]]) -> list[list[Any]]:
    """The cells the example drew on, and no more: the picture adds its own
    margin, the same on every side, whether or not the terminal had room."""
    used = [
        (r, c)
        for r, row in enumerate(cells)
        for c, cell in enumerate(row)
        if not _blank(cell)
    ]
    if not used:
        raise SampleError("the example drew nothing")
    top = min(r for r, _ in used)
    bottom = max(r for r, _ in used)
    left = min(c for _, c in used)
    right = max(c for _, c in used)
    return [row[left : right + 1] for row in cells[top : bottom + 1]]


#: Box-drawing characters, drawn as lines rather than left to the reader's
#: font, which may not have them or may not join them up: for each, the
#: arms it has - up, down, left, right - and the weight of each.
_L, _H, _D = 1, 2, 3  # light, heavy, double
_BOX: dict[str, tuple[int, int, int, int]] = {}


def _arms(chars: str, up: int, down: int, left: int, right: int) -> None:
    for ch in chars:
        _BOX[ch] = (up, down, left, right)


for _w, _set in ((_L, "─│┌┐└┘├┤┬┴┼"), (_H, "━┃┏┓┗┛┣┫┳┻╋"), (_D, "═║╔╗╚╝╠╣╦╩╬")):
    h, v, tl, tr, bl, br, lt, rt, tt, bt, x = _set
    _arms(h, 0, 0, _w, _w)
    _arms(v, _w, _w, 0, 0)
    _arms(tl, 0, _w, 0, _w)
    _arms(tr, 0, _w, _w, 0)
    _arms(bl, _w, 0, 0, _w)
    _arms(br, _w, 0, _w, 0)
    _arms(lt, _w, _w, 0, _w)
    _arms(rt, _w, _w, _w, 0)
    _arms(tt, 0, _w, _w, _w)
    _arms(bt, _w, 0, _w, _w)
    _arms(x, _w, _w, _w, _w)
# Rounded corners join as the square ones do.
_arms("╭", 0, _L, 0, _L)
_arms("╮", 0, _L, _L, 0)
_arms("╰", _L, 0, 0, _L)
_arms("╯", _L, 0, _L, 0)

#: Block characters, drawn as rectangles: the part of the cell each fills,
#: as fractions (left, top, width, height).
_BLOCKS = {
    "█": (0, 0, 1, 1),
    "▀": (0, 0, 1, 0.5),
    "▄": (0, 0.5, 1, 0.5),
    "▌": (0, 0, 0.5, 1),
    "▐": (0.5, 0, 0.5, 1),
}


Segment = tuple[float, float, float, float, float, str]


def _box_segments(
    ch: str, x: float, y: float, colour: str, bold: bool = False
) -> list[Segment]:
    up, down, left, right = _BOX[ch]
    cx, cy = x + CELL_WIDTH / 2, y + CELL_HEIGHT / 2
    out: list[Segment] = []
    for weight, (x1, y1, x2, y2) in (
        (up, (cx, y, cx, cy)),
        (down, (cx, cy, cx, y + CELL_HEIGHT)),
        (left, (x, cy, cx, cy)),
        (right, (cx, cy, x + CELL_WIDTH, cy)),
    ):
        if not weight:
            continue
        vertical = x1 == x2
        # A bold border is drawn heavier, as a terminal's bold font draws it;
        # a raised relief is one.
        stroke = (2.2 if weight == _H else 1.1) * (1.6 if bold else 1.0)
        for offset in (-1.5, 1.5) if weight == _D else (0.0,):
            dx, dy = (offset, 0.0) if vertical else (0.0, offset)
            out.append((x1 + dx, y1 + dy, x2 + dx, y2 + dy, stroke, colour))
    return out


def _lines(segments: list[Segment]) -> list[str]:
    """The segments as lines, each run of touching ones joined into one,
    so a border is a single stroke rather than a seam at every cell."""
    groups: dict[tuple[bool, float, float, str], list[tuple[float, float]]] = {}
    for x1, y1, x2, y2, weight, colour in segments:
        if x1 == x2:
            groups.setdefault((True, x1, weight, colour), []).append((y1, y2))
        else:
            groups.setdefault((False, y1, weight, colour), []).append((x1, x2))
    out = []
    for (vertical, at, weight, colour), spans in sorted(groups.items()):
        merged: list[list[float]] = []
        for a, b in sorted(spans):
            if merged and a <= merged[-1][1] + 0.01:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            x1, y1, x2, y2 = (at, a, at, b) if vertical else (a, at, b, at)
            out.append(
                f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" '
                f'stroke="#{colour}" stroke-width="{weight:g}" '
                f'stroke-linecap="square"/>'
            )
    return out


def _text(word: list[str], column: int, y: float, style: Any) -> str:
    fg, bold, under, italic, strike = style
    attrs = ' font-weight="bold"' if bold else ""
    attrs += ' font-style="italic"' if italic else ""
    decorations = ["underline"] * under + ["line-through"] * strike
    if decorations:
        attrs += f' text-decoration="{" ".join(decorations)}"'
    text = html.escape("".join(word), quote=False)
    return (
        f'<text x="{column * CELL_WIDTH:g}" y="{y + CELL_HEIGHT * 0.76:g}" '
        f'fill="#{fg}" textLength="{len(word) * CELL_WIDTH:g}"{attrs}>{text}</text>'
    )


def svg(cells: list[list[Any]], title: str) -> str:
    """The cells as an SVG.

    Each character is placed on its own cell, so the grid holds whatever
    font the reader has; box-drawing and block characters are drawn as
    lines and rectangles, so borders join up even in a font without them.
    """
    rows, cols = len(cells), len(cells[0])
    pad = MARGIN
    width, height = cols * CELL_WIDTH + 2 * pad, rows * CELL_HEIGHT + 2 * pad
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="tkcurses-sample" '
        f'role="img" viewBox="{-pad:g} {-pad:g} {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}" '
        f'font-family="{FONT}" font-size="14">',
        f"<title>{html.escape(title)}</title>",
        f'<rect x="{-pad:g}" y="{-pad:g}" width="{width:g}" height="{height:g}" '
        f'fill="#{DEFAULT_BG}"/>',
    ]
    for r, row in enumerate(cells):
        y = r * CELL_HEIGHT
        c = 0
        while c < cols:
            bg = _style(row[c])[1]
            end = c
            while end < cols and _style(row[end])[1] == bg:
                end += 1
            if bg != DEFAULT_BG:
                out.append(
                    f'<rect x="{c * CELL_WIDTH:g}" y="{y:g}" '
                    f'width="{(end - c) * CELL_WIDTH:g}" height="{CELL_HEIGHT}" '
                    f'fill="#{bg}"/>'
                )
            c = end
    segments: list[Segment] = []
    for r, row in enumerate(cells):
        y = r * CELL_HEIGHT
        word: list[str] = []
        start = 0
        style: tuple[str, bool, bool, bool, bool] | None = None
        for c, cell in enumerate([*row, None]):
            ch = " " if cell is None else (cell.data or " ")
            fg, _, bold, under = _style(cell) if cell is not None else ("", 0, 0, 0)
            x = c * CELL_WIDTH
            plain = cell is not None and ch not in _BOX and ch not in _BLOCKS
            here = (
                fg,
                bool(bold),
                bool(under),
                bool(getattr(cell, "italics", False)),
                bool(getattr(cell, "strikethrough", False)),
            )
            # A word ends at a space, at a drawn character and at a change of
            # style; each is anchored to its own first cell, so a font whose
            # advance is not quite the cell's drifts by a word at most.
            if word and (not plain or ch == " " or here != style):
                out.append(_text(word, start, y, style))
                word = []
            if cell is None:
                break
            if ch in _BOX:
                segments.extend(_box_segments(ch, x, y, fg, bool(bold)))
            elif ch in _BLOCKS:
                left, top, w, h = _BLOCKS[ch]
                out.append(
                    f'<rect x="{x + left * CELL_WIDTH:g}" '
                    f'y="{y + top * CELL_HEIGHT:g}" width="{w * CELL_WIDTH:g}" '
                    f'height="{h * CELL_HEIGHT:g}" fill="#{fg}"/>'
                )
            elif ch != " ":
                if not word:
                    start, style = c, here
                word.append(ch)
    out.extend(_lines(segments))
    out.append("</svg>")
    return "\n".join(out)


# -- caching ------------------------------------------------------------------

_LIBRARY: list[str] = []


def library_fingerprint() -> str:
    """A hash of the library's source: any change draws every screen again."""
    if not _LIBRARY:
        digest = hashlib.sha256()
        for path in sorted((ROOT / "src" / "tkcurses").rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
        _LIBRARY.append(digest.hexdigest())
    return _LIBRARY[0]


def render(code: str, cache: Path | None = None) -> str:
    """The example's screen as SVG, from the cache when it is there."""
    body, size = split_size(code)
    key = hashlib.sha256(
        "\0".join((RENDERER_VERSION, library_fingerprint(), f"{size}", body)).encode()
    ).hexdigest()
    if cache is not None and (cache / f"{key}.svg").exists():
        return (cache / f"{key}.svg").read_text()
    picture = svg(crop(capture(body, size)), _summary(body))
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{key}.svg").write_text(picture)
    return picture


def _summary(body: str) -> str:
    return "What this draws: " + " ".join(body.split())[:200]


def render_example(
    path: Path, size: tuple[int, int], keys: tuple[str, ...], cache: Path | None = None
) -> str:
    """A whole program's screen, after ``keys``, as SVG."""
    source = path.read_text()
    key = hashlib.sha256(
        "\0".join(
            (
                RENDERER_VERSION,
                library_fingerprint(),
                f"{size}",
                json.dumps(keys),
                source,
            )
        ).encode()
    ).hexdigest()
    if cache is not None and (cache / f"{key}.svg").exists():
        return (cache / f"{key}.svg").read_text()
    title = f"What {path.name} draws" + (f" after {' '.join(keys)}" if keys else "")
    picture = svg(crop(capture(source, size, keys, whole=True)), title)
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{key}.svg").write_text(picture)
    return picture


def shown(source: str) -> str:
    """A program as the page shows it: without the licence notice it opens
    with, which the file itself keeps."""
    lines = source.splitlines()
    while lines and (lines[0].startswith("#") or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines) + "\n"


# -- Sphinx -------------------------------------------------------------------


class SampleDirective(Directive):
    """``.. tkcurses-sample::`` - the example as code, then its screen."""

    has_content = True

    def run(self) -> list[nodes.Node]:
        code = "\n".join(self.content)
        body, _ = split_size(code)
        env = self.state.document.settings.env
        cache = Path(env.app.doctreedir) / "tkscreens"
        literal = nodes.literal_block(body, body, language="python")
        try:
            picture = render(code, cache)
        except SampleError as error:
            return [
                literal,
                self.state.document.reporter.warning(
                    f"sample output failed: {error}", line=self.lineno
                ),
            ]
        figure = nodes.raw(
            "",
            f'<div class="tkcurses-sample-screen">{picture}</div>',
            format="html",
        )
        container = nodes.container(classes=["tkcurses-sample"])
        container += [literal, figure]
        return [container]


def _size_option(text: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", text)
    if not match:
        raise ValueError(f"a size is columns x rows, like 60x15, not {text!r}")
    return int(match[1]), int(match[2])


def _keys_option(text: str) -> tuple[str, ...]:
    keys = json.loads(text)
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError('keys are a JSON list of strings, like ["abc", "<Return>"]')
    return tuple(keys)


class ExampleDirective(Directive):
    """``.. tkcurses-example:: examples/name.py`` - a whole program, its
    screen, and a link to the file.

    ``:size: 60x15`` sets the terminal (40x10 otherwise), and ``:keys:`` is a
    JSON list of what to press first: literal text and ``<Name>`` keys, as
    the test harness's ``send_keys`` takes them.
    """

    required_arguments = 1
    has_content = False
    option_spec = {"size": _size_option, "keys": _keys_option}  # noqa: RUF012

    def run(self) -> list[nodes.Node]:
        relative = self.arguments[0]
        path = ROOT / relative
        env = self.state.document.settings.env
        if not path.is_file():
            return [
                self.state.document.reporter.warning(
                    f"example {relative} not found", line=self.lineno
                )
            ]
        env.note_dependency(str(path))
        source = path.read_text()
        literal = nodes.literal_block(shown(source), shown(source), language="python")
        link = nodes.paragraph()
        link += nodes.reference(
            relative,
            relative,
            refuri=f"https://github.com/slfields/TkCurses/blob/master/{relative}",
        )
        cache = Path(env.app.doctreedir) / "tkscreens"
        try:
            picture = render_example(
                path,
                self.options.get("size", DEFAULT_SIZE),
                self.options.get("keys", ()),
                cache,
            )
        except SampleError as error:
            return [
                literal,
                self.state.document.reporter.warning(
                    f"example {relative} failed: {error}", line=self.lineno
                ),
            ]
        figure = nodes.raw(
            "",
            f'<div class="tkcurses-sample-screen">{picture}</div>',
            format="html",
        )
        container = nodes.container(classes=["tkcurses-sample"])
        container += [figure, link, literal]
        return [container]


def expand_sections(lines: list[str]) -> None:
    """Turn each ``Sample output:`` section into a heading and the directive,
    in place, before napoleon reads the docstring.

    ``Sample output (relief):`` names the option the sample shows, and is
    headed "Sample output: relief"; ``(from, to)`` names several. The body is already indented under the
    section header, which is the indentation the directive needs, so it
    moves across unchanged.
    """
    index = 0
    while index < len(lines):
        line = lines[index]
        match = SECTION_LINE.fullmatch(line.strip())
        if not match:
            index += 1
            continue
        indent = len(line) - len(line.lstrip())
        end = index + 1
        while end < len(lines) and (
            not lines[end].strip()
            or len(lines[end]) - len(lines[end].lstrip()) > indent
        ):
            end += 1
        while end > index + 1 and not lines[end - 1].strip():
            end -= 1
        body = lines[index + 1 : end]
        pad = " " * indent
        title = "Sample output" + (f": {match[1]}" if match[1] else "")
        replacement = [
            f"{pad}.. rubric:: {title}",
            "",
            f"{pad}.. tkcurses-sample::",
            "",
            *body,
            "",
        ]
        lines[index:end] = replacement
        index += len(replacement)


def _process_docstring(*args: Any) -> None:
    # Sphinx passes (app, what, name, obj, options, lines); only the lines
    # matter, and they are changed in place.
    expand_sections(args[-1])


def setup(app: Sphinx) -> dict[str, Any]:
    # Its docstring hook is an autodoc event, which does not exist until
    # autodoc is loaded.
    app.setup_extension("sphinx.ext.autodoc")
    app.add_directive("tkcurses-sample", SampleDirective)
    app.add_directive("tkcurses-example", ExampleDirective)
    # A page whose own text is unchanged still draws differently when the
    # library or the renderer does. A config value Sphinx compares between
    # builds, rebuild="env", makes it read every page again when either
    # changes, as a fresh build would.
    app.add_config_value(
        "tkscreens_fingerprint",
        f"{RENDERER_VERSION}:{library_fingerprint()}",
        "env",
    )
    # Before napoleon's own handler, which runs at the default 500.
    app.connect("autodoc-process-docstring", _process_docstring, priority=400)
    app.add_css_file("tkscreens.css")
    return {"version": RENDERER_VERSION, "parallel_read_safe": True}
