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

"""The documentation's sample outputs: docs/_ext/tkscreens.py.

An example in a docstring is run at build time and its screen drawn as
SVG (TkCurses-imii.16). These hold the pieces to what a reader is
promised: the picture is the screen, cropped to what was drawn, borders
join up, text is escaped, an unchanged example is not run again while a
changed library runs them all, and an example that fails fails the
build rather than showing an empty or half-drawn picture.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# The extension is Sphinx's, and only the documentation toolchain installs
# Sphinx: ci.yml's test jobs do not, docs.yml - which runs on every pull
# request - does, and runs these.
pytest.importorskip("docutils")
pytest.importorskip("sphinx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "_ext"))

import tkscreens  # noqa: E402


def cell(data=" ", fg="default", bg="default", *, bold=False, reverse=False):
    return SimpleNamespace(
        data=data, fg=fg, bg=bg, bold=bold, underscore=False, reverse=reverse
    )


def grid(*rows: str, **style):
    return [[cell(ch, **style) for ch in row] for row in rows]


# -- the example --------------------------------------------------------------


def test_the_default_size():
    assert tkscreens.split_size("tk.Label(root).pack()") == (
        "tk.Label(root).pack()",
        (40, 10),
    )


def test_a_size_line_is_used_and_not_shown():
    body, size = tkscreens.split_size("# size: 60x15\ntk.Label(root).pack()\n")
    assert (body, size) == ("tk.Label(root).pack()", (60, 15))


def test_the_program_wraps_the_example():
    source = tkscreens.program("tk.Label(root).pack()")
    assert source.startswith("import tkcurses as tk\nfrom tkcurses import ttk\n")
    assert source.endswith("tk.Label(root).pack()\nroot.mainloop()\n")


def test_a_section_becomes_a_heading_and_the_directive():
    lines = [
        "A button.",
        "",
        "Sample output:",
        "    for n in range(2):",
        "",
        "        tk.Button(root).pack()",
        "",
        "Args:",
        "    x: A thing.",
    ]
    tkscreens.expand_sections(lines)
    assert lines == [
        "A button.",
        "",
        ".. rubric:: Sample output",
        "",
        ".. tkcurses-sample::",
        "",
        "    for n in range(2):",
        "",
        "        tk.Button(root).pack()",
        "",
        "",
        "Args:",
        "    x: A thing.",
    ]


def test_a_named_sample_is_headed_with_its_option():
    lines = ["Sample output (relief):", "    tk.Button(root, relief='groove').pack()"]
    tkscreens.expand_sections(lines)
    assert lines[0] == ".. rubric:: Sample output: relief"
    assert "    tk.Button(root, relief='groove').pack()" in lines


def test_a_sample_may_name_several_options():
    lines = ["Sample output (from, to):", "    tk.Scale(root, from_=5, to=1).pack()"]
    tkscreens.expand_sections(lines)
    assert lines[0] == ".. rubric:: Sample output: from, to"


def test_every_section_becomes_one():
    lines = ["Sample output:", "    a()", "Sample output (x):", "    b()"]
    tkscreens.expand_sections(lines)
    assert lines.count(".. tkcurses-sample::") == 2
    assert "    a()" in lines
    assert "    b()" in lines


# -- the picture --------------------------------------------------------------


def test_crop_keeps_what_was_drawn_and_nothing_else():
    cells = grid("      ", "  ab  ", "      ")
    assert [[c.data for c in row] for row in tkscreens.crop(cells)] == [["a", "b"]]


def test_a_painted_blank_counts_as_drawn():
    """A widget's black background is part of it, though the terminal's
    default background is drawn black too."""
    cells = grid("    ", "    ")
    cells[1][3] = cell(" ", bg="black")
    assert len(tkscreens.crop(cells)[0]) == 1


def test_nothing_drawn_is_an_error():
    with pytest.raises(tkscreens.SampleError):
        tkscreens.crop(grid("   ", "   "))


def test_text_is_escaped():
    out = tkscreens.svg(grid("<b>&"), "t")
    assert "&lt;b&gt;&amp;" in out
    assert "<b>" not in out.split("</title>", 1)[1]


def test_colours_are_xterms_and_hex_passes_through():
    out = tkscreens.svg([[cell("a", fg="brown", bg="005faf")]], "t")
    assert 'fill="#cdcd00"' in out
    assert 'fill="#005faf"' in out


def test_reverse_swaps_the_colours():
    out = tkscreens.svg([[cell("a", fg="red", bg="blue", reverse=True)]], "t")
    assert re.search(r'<rect x="0"[^>]*fill="#cd0000"', out)
    assert re.search(r'<text[^>]*fill="#0000ee"', out)


def test_dim_is_halfway_to_the_background():
    """A sunken border is dim in TkCurses; pyte has no field for it."""
    dim = cell("a", fg="white")
    dim.dim = True
    assert re.search(r'<text[^>]*fill="#727272"', tkscreens.svg([[dim]], "t"))


def test_a_bold_border_is_heavier_and_brighter():
    """A raised border is bold: drawn heavier, and bright as xterm draws it."""
    plain = tkscreens.svg(grid("──", fg="white"), "t")
    bold = tkscreens.svg(grid("──", fg="white", bold=True), "t")
    assert 'stroke-width="1.1"' in plain and 'stroke="#e5e5e5"' in plain
    assert 'stroke-width="1.76"' in bold and 'stroke="#ffffff"' in bold


@pytest.mark.tty
def test_raised_and_sunken_are_told_apart():
    picture = tkscreens.render(
        'tk.Button(root, text="r", relief="raised").pack(side="left")\n'
        'tk.Button(root, text="s", relief="sunken").pack(side="left")'
    )
    widths = set(re.findall(r'stroke-width="([\d.]+)"', picture))
    colours = set(re.findall(r'<line[^>]*stroke="#(\w+)"', picture))
    # Raised: heavier and bright. Sunken: dim, halfway to the background.
    assert widths == {"1.76", "1.1"}
    assert colours == {"ffffff", "727272"}


def test_bold_is_bold():
    assert 'font-weight="bold"' in tkscreens.svg([[cell("a", bold=True)]], "t")


def test_italic_and_overstrike_are_kept():
    """A font's style is all a terminal keeps of it, so the picture shows
    each one the terminal does."""
    styled = cell("a")
    styled.italics, styled.strikethrough, styled.underscore = True, True, True
    out = tkscreens.svg([[styled]], "t")
    assert 'font-style="italic"' in out
    assert 'text-decoration="underline line-through"' in out


def test_a_box_is_four_lines():
    """Box-drawing characters are drawn, not left to the reader's font, and
    each side of a box is one stroke rather than a seam at every cell."""
    out = tkscreens.svg(grid("┌──┐", "│  │", "└──┘"), "t")
    assert out.count("<line ") == 4
    assert "<text" not in out


def test_a_double_line_is_two_strokes():
    out = tkscreens.svg(grid("═══"), "t")
    assert out.count("<line ") == 2


def test_a_full_block_is_a_rectangle():
    out = tkscreens.svg(grid("█"), "t")
    assert "<text" not in out
    assert out.count("<rect ") == 2  # the background, and the block


def test_a_word_is_anchored_to_its_own_cell():
    out = tkscreens.svg(grid("ab  cd"), "t")
    xs = re.findall(r'<text x="([\d.]+)"', out)
    assert [float(x) for x in xs] == [0, 4 * tkscreens.CELL_WIDTH]


# -- running it ---------------------------------------------------------------


@pytest.mark.tty
def test_an_example_is_drawn():
    picture = tkscreens.render('tk.Button(root, text="Save").pack()')
    assert ">Save</text>" in picture
    assert picture.count("<line ") == 4


@pytest.mark.tty
def test_an_unchanged_example_is_not_run_again(tmp_path, monkeypatch):
    first = tkscreens.render('tk.Label(root, text="Hi").pack()', tmp_path)

    def must_not_run(*args):
        raise AssertionError("ran again")

    monkeypatch.setattr(tkscreens, "capture", must_not_run)
    assert tkscreens.render('tk.Label(root, text="Hi").pack()', tmp_path) == first


@pytest.mark.tty
def test_a_changed_library_runs_it_again(tmp_path, monkeypatch):
    tkscreens.render('tk.Label(root, text="Hi").pack()', tmp_path)
    monkeypatch.setattr(tkscreens, "_LIBRARY", ["a different library"])
    runs = []
    real = tkscreens.capture

    def counted(*args):
        runs.append(args)
        return real(*args)

    monkeypatch.setattr(tkscreens, "capture", counted)
    tkscreens.render('tk.Label(root, text="Hi").pack()', tmp_path)
    assert len(runs) == 1


@pytest.mark.tty
def test_an_example_that_raises_is_an_error():
    with pytest.raises(tkscreens.SampleError, match="NameError"):
        tkscreens.render("tk.Label(root, text=undefined).pack()")


@pytest.mark.tty
def test_an_example_that_fails_after_drawing_is_an_error():
    with pytest.raises(tkscreens.SampleError, match="ZeroDivisionError"):
        tkscreens.render(
            'tk.Label(root, text="Hi").pack()\nroot.after(50, lambda: 1 / 0)'
        )


def _build(tmp_path: Path, page: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "conf.py").write_text(
        f"import sys\nsys.path.insert(0, {str(ROOT / 'docs' / '_ext')!r})\n"
        "extensions = ['myst_parser', 'tkscreens']\n"
    )
    (tmp_path / "index.md").write_text(page)
    return subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-b", "html", ".", "_build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


@pytest.mark.tty
def test_a_page_shows_the_code_and_the_screen(tmp_path):
    result = _build(
        tmp_path, '# P\n\n```{tkcurses-sample}\ntk.Label(root, text="Hi").pack()\n```\n'
    )
    assert result.returncode == 0, result.stderr
    page = (tmp_path / "_build" / "index.html").read_text()
    assert 'class="tkcurses-sample-screen"' in page
    assert ">Hi</text>" in page
    assert "highlight-python" in page


@pytest.mark.tty
def test_a_broken_example_fails_the_build(tmp_path):
    result = _build(
        tmp_path, "# P\n\n```{tkcurses-sample}\ntk.Label(root, text=nope).pack()\n```\n"
    )
    assert result.returncode != 0
    assert "sample output failed" in result.stderr


@pytest.mark.tty
def test_an_example_that_complains_after_drawing_is_an_error():
    """Anything on stderr fails it, though the screen looks complete: a
    warning is a sign the example is wrong, and a picture would hide it."""
    with pytest.raises(tkscreens.SampleError, match="something is off"):
        tkscreens.render(
            "import sys\n"
            'tk.Label(root, text="Hi").pack()\n'
            'root.after(50, lambda: print("something is off", file=sys.stderr))'
        )


# -- whole programs -------------------------------------------------------------


def test_a_program_is_shown_without_its_licence_notice():
    source = "# TkCurses - a notice\n# SPDX-License-Identifier: GPL-3.0-only\n\n" + (
        '"""What it does."""\n\nimport tkcurses as tk\n# a comment kept\n'
    )
    assert tkscreens.shown(source) == (
        '"""What it does."""\n\nimport tkcurses as tk\n# a comment kept\n'
    )


def test_an_example_s_size_and_keys_are_read():
    assert tkscreens._size_option("60x15") == (60, 15)
    assert tkscreens._keys_option('["abc", "<Return>"]') == ("abc", "<Return>")
    with pytest.raises(ValueError, match="columns x rows"):
        tkscreens._size_option("wide")
    with pytest.raises(ValueError, match="JSON list"):
        tkscreens._keys_option('"<Return>"')


@pytest.mark.tty
def test_a_program_is_drawn_after_its_keys(tmp_path):
    picture = tkscreens.render_example(
        ROOT / "examples" / "todo.py", (40, 14), ("Buy bread", "<Return>")
    )
    words = " ".join(re.findall(r">([^<]+)</text>", picture))
    assert "Buy bread" in words
    assert "3 tasks, 0 done" in words


@pytest.mark.tty
def test_a_program_is_run_again_only_when_its_keys_change(tmp_path, monkeypatch):
    path = ROOT / "examples" / "hello.py"
    first = tkscreens.render_example(path, (40, 6), (), tmp_path)
    runs = []
    real = tkscreens.capture

    def counted(*args, **kwargs):
        runs.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(tkscreens, "capture", counted)
    assert tkscreens.render_example(path, (40, 6), (), tmp_path) == first
    assert runs == []
    tkscreens.render_example(path, (40, 6), ("<Tab>",), tmp_path)
    assert len(runs) == 1


@pytest.mark.tty
def test_a_page_shows_a_program_its_screen_and_its_file(tmp_path):
    result = _build(
        tmp_path, "# P\n\n```{tkcurses-example} examples/hello.py\n:size: 40x6\n```\n"
    )
    assert result.returncode == 0, result.stderr
    page = (tmp_path / "_build" / "index.html").read_text()
    assert 'class="tkcurses-sample-screen"' in page
    assert ">Quit</text>" in page
    assert "blob/master/examples/hello.py" in page
    assert "SPDX" not in page


def test_a_missing_program_fails_the_build(tmp_path):
    result = _build(tmp_path, "# P\n\n```{tkcurses-example} examples/nowhere.py\n```\n")
    assert result.returncode != 0
    assert "example examples/nowhere.py not found" in result.stderr
