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

"""The docstrings keep the API reference's convention (TkCurses-imii.3).

The reference is autodoc on the docstrings, so a docstring is a page a
user reads. What it must say is in ``tests/support/docsurface.py``; what
it applies to is found from tkinter itself, so a method added to match
tkinter is held to it without anyone listing it.

The breaches that were there when the convention was written down are
recorded, and these tests let that record shrink and never grow: a new
breach fails, and so does a fixed one still listed, so the fix cannot
quietly come undone later.
"""

from __future__ import annotations

import inspect
import json
import sys

import pytest

from tests.support import docsurface
from tests.support.docsurface import class_key

RULES = (
    "undocumented",
    "tracker_ids",
    "private_names",
    "unmarked_extensions",
    "unlisted_borrowed",
    "no_sample",
    "unmeasured_options",
    "unsampled_options",
    "undescribed_options",
)


@pytest.fixture(scope="module")
def found() -> dict[str, set[str]]:
    return docsurface.violations()


@pytest.fixture(scope="module")
def debt() -> dict[str, set[str]]:
    recorded = json.loads(docsurface.DEBT.read_text())
    return {rule: set(recorded.get(rule, [])) for rule in RULES}


@pytest.mark.parametrize("rule", RULES)
def test_no_new_breaches(rule, found, debt):
    new = sorted(found[rule] - debt[rule])
    assert not new, (
        f"{rule}: these break the docstring convention "
        f"(tests/support/docsurface.py says what it is): {new}"
    )


@pytest.mark.parametrize("rule", RULES)
def test_a_fixed_breach_leaves_the_record(rule, found, debt):
    fixed = sorted(debt[rule] - found[rule])
    assert not fixed, (
        f"{rule}: these keep the convention now, so take them out of "
        f"docstring_debt.json - python3 tests/support/docsurface.py --write: {fixed}"
    )


def test_the_surface_is_tkinters():
    """The comparison finds what it should, so an empty result means the
    docstrings are right rather than that it looked at nothing."""
    keys = {item.key for item in docsurface.tkinter_surface()}
    assert len(keys) > 500
    for expected in (
        "tkcurses.Button",
        "tkcurses.Misc.after",
        "tkcurses.ttk.Treeview.insert",
        "tkcurses.messagebox.showinfo",
    ):
        assert expected in keys, expected


def test_extensions_are_found():
    keys = {item.key for item in docsurface.extensions()}
    assert "tkcurses.Misc.winfo_colordepth" in keys
    assert "tkcurses.ttk.Theme" in keys
    # Another name for a standard class is not an extension.
    assert "tkcurses.TkCursesError" not in keys
    # Nor is a method another tkinter class has; that is a difference.
    assert not any(key.endswith(".select") for key in keys)


@pytest.mark.parametrize(("where", "added"), sorted(docsurface.LATER_TKINTER.items()))
def test_a_later_tkinter_method_is_tkinters(where, added):
    """Each name the oldest Pythons' tkinter lacks is on the newer one's."""
    import tkinter

    if sys.version_info < added:
        pytest.skip(f"tkinter has it from Python {added[0]}.{added[1]}")
    cls, name = where
    assert hasattr(getattr(tkinter, cls), name)


def test_the_widgets_are_what_has_a_sample():
    import tkcurses
    import tkcurses.ttk

    widgets = docsurface.widget_classes()
    assert tkcurses.Button in widgets
    assert tkcurses.ttk.Treeview in widgets
    assert tkcurses.Widget not in widgets
    assert tkcurses.Tk not in widgets


def test_borrowed_methods_are_found():
    import tkcurses.ttk

    borrowed = docsurface.borrowed_methods()
    assert "select" in borrowed[tkcurses.ttk.Checkbutton]


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        ("Summary.\n\nDifferences from tkinter:\n    Cells.\n", "    Cells."),
        (
            "Summary.\n\nDifferences from tkinter:\n    A.\n    B.\nArgs:\n",
            "    A.\n    B.",
        ),
        ("Summary. Differences from tkinter: inline.\n", None),
    ],
)
def test_a_section_is_a_napoleon_section(doc, expected):
    assert docsurface.section(inspect.cleandoc(doc), "Differences from tkinter:") == (
        expected
    )


def test_the_options_page_samples_are_found():
    """A heading naming two options gives both their sample; a heading
    with no sample under it gives none."""
    sampled = docsurface.options_page_samples()
    assert {"background", "relief", "padx", "pady"} <= sampled
    assert "cursor" not in sampled


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        ("Sample output (relief):\n    x\n", ["relief"]),
        ("Sample output (from, to):\n    x\n", ["from, to"]),
        ("Sample output:\n    x\n", []),
    ],
)
def test_a_sample_names_its_options(doc, expected):
    assert docsurface.NAMED_SAMPLE.findall(doc) == expected


def test_every_classic_option_was_measured():
    """The measurement is of every option the widget takes: an option
    added since is not silently left without a sample."""
    import json

    import tkcurses

    measured = json.loads(docsurface.VISIBLE.read_text())
    classic = {k: v for k, v in measured.items() if not k.startswith("ttk.")}
    assert classic
    for name, options in classic.items():
        assert set(options) == docsurface.widget_options(getattr(tkcurses, name))


def test_every_themed_widget_was_measured_against_tks_options():
    """Each themed widget is measured for the options Tk's has - not every
    option it accepts here, which includes the classic widget's."""
    import json

    from tkcurses import ttk

    measured = json.loads(docsurface.VISIBLE.read_text())
    tk_has = json.loads(docsurface.TK_TTK_OPTIONS.read_text())
    themed = {k[4:]: v for k, v in measured.items() if k.startswith("ttk.")}
    assert set(themed) == set(tk_has)
    assert {class_key(c) for c in docsurface.widget_classes()} >= {
        f"tkcurses.ttk.{name}" for name in tk_has
    }
    for name, options in themed.items():
        assert set(options) == set(tk_has[name])
        for option, entry in options.items():
            accepted = option in docsurface.widget_options(getattr(ttk, name))
            assert (entry["kind"] == "missing") is not accepted, (name, option)


def test_the_themed_option_rules(tmp_path, monkeypatch):
    """A themed widget is held to Tk's options: one it inherits from the
    classic widget is not asked for, one Tk has and it lacks must still be
    described, and the themed options are sampled on the options page."""
    import json

    from tkcurses import ttk

    measured = json.loads(docsurface.VISIBLE.read_text())
    bar = dict(measured["ttk.Progressbar"])
    fake = tmp_path / "visible.json"
    fake.write_text(json.dumps({"ttk.Progressbar": bar}))
    monkeypatch.setattr(docsurface, "VISIBLE", fake)
    monkeypatch.setattr(ttk.Progressbar, "__doc__", "A bar, with a length.")

    found = docsurface.violations()
    assert bar["phase"] == {"kind": "missing"}
    assert "tkcurses.ttk.Progressbar:phase" in found["undescribed_options"]
    assert "tkcurses.ttk.Progressbar:length" not in found["undescribed_options"]
    assert "tkcurses.ttk.Progressbar:length" in found["unsampled_options"]
    assert "tkcurses.ttk.Progressbar:style" not in found["unsampled_options"]
    assert not found["unmeasured_options"]
    # Inherited from the classic Frame, which tkinter's Progressbar lacks.
    assert "relief" in docsurface.widget_options(ttk.Progressbar)
    assert not any(":relief" in key for rule in found.values() for key in rule)


def test_the_option_rules_catch_what_they_are_for(tmp_path, monkeypatch):
    """Each option rule fires on its own fault: an option not measured, a
    measured one not named in the docstring, and one that shows - or would
    not hold still to tell - without a sample."""
    import json

    import tkcurses

    measured = json.loads(docsurface.VISIBLE.read_text())
    scale = dict(measured["Scale"])
    del scale["digits"]
    scale["sliderlength"] = {"kind": "unsettled"}
    fake = tmp_path / "visible.json"
    fake.write_text(json.dumps({"Scale": scale}))
    monkeypatch.setattr(docsurface, "VISIBLE", fake)
    monkeypatch.setattr(tkcurses.Scale, "__doc__", "A scale, with a resolution.")

    found = docsurface.violations()
    assert "tkcurses.Scale:digits" in found["unmeasured_options"]
    assert "tkcurses.Scale:showvalue" in found["undescribed_options"]
    assert "tkcurses.Scale:resolution" not in found["undescribed_options"]
    assert "tkcurses.Scale:sliderlength" in found["unsampled_options"]
    # A shared option is sampled on the options page, not in the class.
    assert "tkcurses.Scale:relief" not in found["unsampled_options"]


@pytest.mark.parametrize(
    ("doc", "private"),
    [
        ("Calls _draw.", True),
        ("Reads self._rect.", True),
        ("See :func:`~tkcurses._core.canvas.compose`.", True),
        ("Like tkinter's _tkinter module.", False),
        ("A snake_case name.", False),
        ("Dunder: __init__.", False),
    ],
)
def test_a_private_name_is_found_however_it_is_reached(doc, private):
    assert bool(docsurface.PRIVATE_NAME.search(doc)) is private
