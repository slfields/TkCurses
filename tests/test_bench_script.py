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

"""tests/support/bench.py, the timing of the library's hot paths.

Not the timings themselves, which belong to the machine: that every
benchmark still runs against the library as it is now - an internal it
reaches for can be renamed under it - and that a comparison marks what it
should.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))
import bench

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.parametrize("name", list(bench.BENCHMARKS))
def test_every_benchmark_runs_against_this_library(name):
    """In its own interpreter, as a comparison runs it: one of them patches
    curses, which must not happen inside the test process."""
    times = bench.in_tree(SRC, name, repeat=1)
    assert isinstance(times, list), times
    assert len(times) == 1
    assert times[0] > 0


def test_a_benchmark_that_cannot_run_says_why(tmp_path):
    """A tree without the library: not timed as whatever else is installed,
    which would compare the library with itself and find no change."""
    said = bench.in_tree(tmp_path, "measuring cells", repeat=1)
    assert isinstance(said, str)
    assert "not from" in said


def fake_timings(monkeypatch, base, here):
    def in_tree(src, name, repeat):
        return [base[name] if src == Path("base") else here[name]] * repeat

    monkeypatch.setattr(bench, "in_tree", in_tree)


def test_a_comparison_marks_only_what_slowed_past_the_threshold(monkeypatch, capsys):
    base = {"decoding a PNG": 1.0, "measuring cells": 1.0}
    fake_timings(monkeypatch, base, {"decoding a PNG": 1.1, "measuring cells": 1.2})
    status = bench._compare(Path("base"), "base", list(base), 3, 2, 0.15)
    out = capsys.readouterr().out
    assert status == 1
    assert "+20.0%  SLOWER" in out
    assert "+10.0%\n" in out
    assert "1 benchmark(s) slower" in out


def test_a_comparison_with_nothing_slower_passes(monkeypatch, capsys):
    base = {"decoding a PNG": 1.0}
    fake_timings(monkeypatch, base, {"decoding a PNG": 0.5})
    assert bench._compare(Path("base"), "base", list(base), 3, 2, 0.15) == 0
    assert "SLOWER" not in capsys.readouterr().out
