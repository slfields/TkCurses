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

"""Time the library's hot paths, and compare a change against its base.

The suite holds performance by counting work - the lines a keystroke lays
out, the cells a redraw asks for - which is stable on a shared runner and
right for a gate. A count does not see a slower path that does the same
amount of work, so this times them instead. It is not a gate: a timing
belongs to the machine it was taken on, and is compared only with another
taken there, in the same run.

    python3 tests/support/bench.py                  # this tree
    python3 tests/support/bench.py --compare origin/master

``--compare`` checks the other ref out into a temporary worktree and times
both trees alternately, so a machine that slows down partway through slows
both alike. It reports each benchmark's median against the base's and
marks one that is slower by more than ``--threshold``. Each measurement
runs in a fresh interpreter with that tree's ``src`` first on the path.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- the paths
#
# Each returns the action to time; whatever it builds first is not timed.
# None of them needs a terminal.


def _text_widget(lines: int) -> Any:
    from types import SimpleNamespace

    from tkcurses import Misc, Text
    from tkcurses._core.geometry import Rect
    from tkcurses._core.panels import PanelStack

    root = Misc()
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 60, 20)
    root._mapped = True
    text = Text(root, width=40, height=10)
    text._allocate(Rect(0, 0, 42, 12))
    text._map()
    text.insert("1.0", "a line of text, with some words in it\n" * lines)
    text.mark_set("insert", f"{lines // 2}.5")
    text._display_lines()
    return text


def typing_into_a_long_text() -> Callable[[], None]:
    """Twenty keys typed into the middle of a Text of 5,000 lines."""
    from tkcurses._core.events import KeyEvent

    text = _text_widget(5000)

    def run() -> None:
        for _ in range(20):
            text._handle(KeyEvent(keysym="x", char="x"))
            text._display_lines()

    return run


def tagging_every_line() -> Callable[[], None]:
    """A tag added to each of 3,000 lines, then removed."""
    text = _text_widget(3000)

    def run() -> None:
        for line in range(1, 3001):
            text.tag_add("mark", f"{line}.0", f"{line}.4")
        text.tag_remove("mark", "1.0", "end")

    return run


def _picture(size: int) -> list[list[tuple[int, int, int] | None]]:
    return [
        [((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256) for x in range(size)]
        for y in range(size)
    ]


def decoding_a_png() -> Callable[[], None]:
    """A 200 by 200 PNG."""
    from tkcurses._core.imagefiles import decode, encode_png

    data = encode_png(_picture(200))

    def run() -> None:
        decode(data)

    return run


def decoding_a_gif() -> Callable[[], None]:
    """A 200 by 200 GIF of under 256 colours."""
    from tkcurses._core.imagefiles import decode, encode_gif

    rows = [
        [((x // 16) * 16, (y // 16) * 16, 64) for x in range(200)] for y in range(200)
    ]
    data = encode_gif(rows)  # type: ignore[arg-type]

    def run() -> None:
        decode(data)

    return run


def reading_typed_text() -> Callable[[], None]:
    """20,000 bytes of typing, a fifth of it outside ASCII, read as keys."""
    import curses
    import threading

    from tkcurses._core.dispatcher import CursesDispatcher
    from tkcurses._core.input import InputHandler

    for name in ("noecho", "cbreak", "doupdate"):
        setattr(curses, name, lambda: None)
    curses.mousemask = lambda mask: (mask, 0)
    curses.mouseinterval = lambda ms: None
    InputHandler._write_to_terminal = staticmethod(lambda data: True)  # type: ignore[method-assign]
    sent = ("typing é and 界 " * 1200).encode()[:20000]

    class Terminal:
        def __init__(self) -> None:
            self.codes: list[int] = []

        def keypad(self, value: bool) -> None: ...

        def nodelay(self, value: bool) -> None: ...

        def getch(self) -> int:
            return self.codes.pop() if self.codes else curses.ERR

    terminal = Terminal()
    handler = InputHandler(
        terminal,
        dispatcher=CursesDispatcher(owner_thread_id=threading.get_ident()),
    )
    handler.wait_for_input = lambda timeout_ms=50, **kw: False  # type: ignore[method-assign]

    def run() -> None:
        terminal.codes = list(reversed(sent))
        while terminal.codes:
            handler.poll()

    return run


def measuring_cells() -> Callable[[], None]:
    """Cell widths of 50,000 characters of mixed scripts, and clipping."""
    from tkcurses._core.cells import cells, clip_cells

    line = "plain 界 wide é accent ́ emoji \U0001f600 " * 1500

    def run() -> None:
        cells(line)
        clip_cells(line, 30_000)

    return run


BENCHMARKS: dict[str, Callable[[], Callable[[], None]]] = {
    "typing into a long Text": typing_into_a_long_text,
    "tagging every line": tagging_every_line,
    "decoding a PNG": decoding_a_png,
    "decoding a GIF": decoding_a_gif,
    "reading typed text": reading_typed_text,
    "measuring cells": measuring_cells,
}


# ------------------------------------------------------------- measuring


def measure(name: str, repeat: int) -> list[float]:
    """Seconds for each of ``repeat`` runs of one benchmark, after one
    that warms caches and is thrown away."""
    action = BENCHMARKS[name]()
    action()
    times = []
    for _ in range(repeat):
        began = time.perf_counter()
        action()
        times.append(time.perf_counter() - began)
    return times


def in_tree(src: Path, name: str, repeat: int) -> list[float] | str:
    """Measure ``name`` in a fresh interpreter importing the library from
    ``src``. A string, saying why, if that tree cannot run it."""
    env = dict(os.environ, PYTHONPATH=str(src), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, __file__, "--measure", name, "--repeat", str(repeat)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        lines = done.stderr.strip().splitlines()
        return lines[-1] if lines else f"exit status {done.returncode}"
    answer = json.loads(done.stdout)
    # A tree without the module falls through to whatever else is on the
    # path - an editable install of another checkout, most likely - and a
    # comparison would then time the wrong library and report no change.
    if not Path(answer["library"]).resolve().is_relative_to(src.resolve()):
        return f"imported tkcurses from {answer['library']}, not from {src}"
    times: list[float] = answer["times"]
    return times


def ms(seconds: float) -> str:
    return f"{seconds * 1000:9.2f} ms"


def report_one(src: Path, names: list[str], repeat: int) -> int:
    print(f"{'benchmark':28} {'median':>12} {'fastest':>12}")
    for name in names:
        times = in_tree(src, name, repeat)
        if isinstance(times, str):
            print(f"{name:28} failed: {times}")
            continue
        print(f"{name:28} {ms(statistics.median(times))} {ms(min(times))}")
    return 0


def compare(
    base: str, names: list[str], repeat: int, rounds: int, threshold: float
) -> int:
    """Time this tree and ``base`` alternately; 1 if any is slower than
    ``threshold`` allows."""
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch) / "base"
        subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "worktree",
                "add",
                "-q",
                "--detach",
                str(tree),
                base,
            ],
            check=True,
        )
        try:
            return _compare(tree / "src", base, names, repeat, rounds, threshold)
        finally:
            subprocess.run(
                ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(tree)],
                check=False,
            )


def _compare(
    base_src: Path,
    base: str,
    names: list[str],
    repeat: int,
    rounds: int,
    threshold: float,
) -> int:
    here = ROOT / "src"
    slower = 0
    print(f"{'benchmark':28} {base:>12} {'this tree':>12} {'change':>8}")
    for name in names:
        ours: list[float] = []
        theirs: list[float] = []
        failed = ""
        for _ in range(rounds):
            for src, into in ((base_src, theirs), (here, ours)):
                times = in_tree(src, name, repeat)
                if isinstance(times, str):
                    failed = f"{'base' if src == base_src else 'this tree'}: {times}"
                    break
                into.extend(times)
            if failed:
                break
        if failed:
            print(f"{name:28} not compared, {failed}")
            continue
        was, now = statistics.median(theirs), statistics.median(ours)
        change = now / was - 1
        flag = ""
        if change > threshold:
            flag = "  SLOWER"
            slower += 1
        print(f"{name:28} {ms(was)} {ms(now)} {change:+8.1%}{flag}")
    if slower:
        print(
            f"\n{slower} benchmark(s) slower than {base} by more than {threshold:.0%}."
        )
    return 1 if slower else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--compare", metavar="REF", help="time against this git ref too"
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=list(BENCHMARKS),
        help="this benchmark (repeatable)",
    )
    parser.add_argument(
        "--repeat", type=int, default=7, help="timed runs per measurement"
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="alternations with --compare"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.15, help="slowdown to mark"
    )
    parser.add_argument("--measure", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.measure:
        times = measure(args.measure, args.repeat)
        import tkcurses

        print(json.dumps({"library": tkcurses.__file__, "times": times}))
        return 0
    names = args.only or list(BENCHMARKS)
    if args.compare:
        return compare(args.compare, names, args.repeat, args.rounds, args.threshold)
    return report_one(ROOT / "src", names, args.repeat)


if __name__ == "__main__":
    sys.exit(main())
