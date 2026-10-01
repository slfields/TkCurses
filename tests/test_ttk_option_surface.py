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

"""Every themed widget's options, against the real tkinter.ttk beside it.

Possible because tkinter is installed and is what every other measurement in
this project has been made against. It turns "does our surface match ttk's"
from a thing to be re-derived by hand into a thing the suite answers.

TWO DIRECTIONS, and they are not equally serious.

**Missing an option ttk has breaks programs.** ``ttk.Progressbar(text=...)``
is valid tkinter and fails here. Those are listed in :data:`KNOWN_GAPS`, each
against the issue that will close it, so the list can only shrink and a NEW
gap fails the suite.

**Accepting an option ttk rejects does not.** Code written for ttk never
passes ``bg``, so a wider surface breaks nothing - and ours does not merely
tolerate them, it honours them: measured, ``ttk.Label(background="red")``
draws red here. That is a deliberate divergence, recorded in
``test_a_themed_widget_is_wider_than_ttk_on_purpose`` rather than left for
someone to find and treat as a bug.
"""

from __future__ import annotations

import pytest

pytest.importorskip("tkinter", reason="the comparison needs real tkinter")

import tkinter
import tkinter.ttk

import tkcurses
import tkcurses.ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

#: The widgets tkcurses.ttk has today. The two it does not are
#: TkCurses-3h5's remaining children.
THEMED = (
    "Label",
    "Scale",
    "Separator",
    "Sizegrip",
    "Progressbar",
    "Combobox",
    "Notebook",
    "Treeview",
    "LabeledScale",
    "Frame",
    "Labelframe",
    "Panedwindow",
    "Button",
    "Checkbutton",
    "Radiobutton",
    "Menubutton",
    "Entry",
    "Spinbox",
    "Scrollbar",
)

#: Options real ttk has that we do not, each with the issue that owns it.
#:
#: It shrank by eight on 2026-10-01 (TkCurses-ale): the scroll and validation
#: callbacks on Entry, Spinbox, Combobox and Treeview are implemented, not
#: merely accepted. The entry that said "a tree cannot take a scrollbar" was
#: the most consequential thing in this list - it meant the standard pairing,
#: ttk.Treeview(yscrollcommand=bar.set) with ttk.Scrollbar(command=tree.yview),
#: raised rather than ran.
#: A gap not listed here is a test failure, which is the point: this list may
#: shrink and must never silently grow.
KNOWN_GAPS: dict[str, dict[str, str]] = {
    "Scale": {"from": "TkCurses-3h5.1 split: we report from_, tkinter reports from"},
    "Progressbar": {
        "anchor": "Tk 9.0 label-over-bar options",
        "font": "Tk 9.0 label-over-bar options",
        "justify": "Tk 9.0 label-over-bar options",
        "text": "Tk 9.0 label-over-bar options",
        "wraplength": "Tk 9.0 label-over-bar options",
        "phase": "ttk::progressbar -phase",
    },
    "Combobox": {
        "placeholder": "Tk 9.0 ghost text",
        "placeholderforeground": "Tk 9.0 ghost text",
    },
    # Entry and Spinbox share these: ttk's Spinbox IS an Entry - measured, its
    # MRO begins Spinbox, Entry, Widget, Entry - so a gap in one is a gap in
    # both, and Combobox above already carries the same four.
    "Entry": {
        "placeholder": "Tk 9.0 ghost text",
        "placeholderforeground": "Tk 9.0 ghost text",
        "exportselection": "TkCurses-163: no widget offers it",
    },
    "Spinbox": {
        "placeholder": "Tk 9.0 ghost text",
        "placeholderforeground": "Tk 9.0 ghost text",
        "exportselection": "TkCurses-163: no widget offers it",
        "from": "TkCurses-y5q: we report from_, tkinter reports from",
    },
    "Treeview": {
        "striped": "Tk 9.0 additions",
        "selecttype": "Tk 9.0 additions",
        "titlecolumns": "Tk 9.0 additions",
        "titleitems": "Tk 9.0 additions",
    },
}


@pytest.fixture(scope="module")
def real_root():
    try:
        root = tkinter.Tk()
    except Exception:  # pragma: no cover - no display
        pytest.skip("no display for real tkinter")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def our_root():
    root = tkcurses.Misc()
    root.tk.panels = PanelStack(window_factory=lambda *a, **k: None, panel_factory=None)
    root._rect = Rect(0, 0, 80, 24)
    root._mapped = True
    return root


def options_of(widget) -> set[str]:
    return set(widget.configure() or {})


@pytest.mark.parametrize("name", THEMED)
def test_we_lack_no_option_ttk_has_beyond_the_known_gaps(name, real_root, our_root):
    """The direction that breaks programs.

    A gap here means valid tkinter code fails against tkcurses. The listed
    ones have issues; anything else is new and wants one.
    """
    theirs = options_of(getattr(tkinter.ttk, name)(real_root))
    ours = options_of(getattr(tkcurses.ttk, name)(our_root))
    unexplained = sorted(theirs - ours - set(KNOWN_GAPS.get(name, {})))
    assert not unexplained, (
        f"ttk.{name} has options we lack and nothing owns: {unexplained}. "
        f"Add them, or list them in KNOWN_GAPS against an issue."
    )


@pytest.mark.parametrize("name", THEMED)
def test_every_known_gap_is_still_a_gap(name, real_root, our_root):
    """So the list shrinks when something is fixed rather than going stale.

    The same idea as xfail(strict=True): a gap that has quietly been closed
    should say so, not sit in a list implying work remains.
    """
    gaps = set(KNOWN_GAPS.get(name, {}))
    if not gaps:
        pytest.skip("no gaps recorded for this widget")
    theirs = options_of(getattr(tkinter.ttk, name)(real_root))
    ours = options_of(getattr(tkcurses.ttk, name)(our_root))
    closed = sorted(gaps & ours)
    assert not closed, (
        f"ttk.{name}: {closed} is listed as a gap but we accept it now - "
        f"remove it from KNOWN_GAPS"
    )
    assert gaps <= theirs, (
        f"ttk.{name}: {sorted(gaps - theirs)} is listed as a gap but real ttk "
        f"does not have it either - remove it"
    )


def test_every_themed_widget_answers_to_class_and_style(real_root, our_root):
    """The two options ttk adds to everything, and we lacked one of them."""
    for name in THEMED:
        ours = options_of(getattr(tkcurses.ttk, name)(our_root))
        assert "style" in ours, name
        assert "class" in ours, f"{name} should take -class, as ttk does"


def test_a_themed_widget_is_wider_than_ttk_on_purpose(our_root):
    """The other direction, recorded rather than treated as a defect.

    ttk moves appearance into the style database and drops the classic
    options; we keep them and HONOUR them - measured, a themed Label given
    background="red" draws red. Code written for ttk never passes them, so a
    wider surface breaks nothing, and in a terminal the style database is
    thinner than ttk's so the direct options are worth having.
    """
    label = tkcurses.ttk.Label(our_root)
    assert "background" in options_of(label)
    label.configure(background="red")
    assert label.cget("background") == "red"


# ----------------------------------------------------------------- -class
#
# Measured against real ttk before implementing: the default is "", setting
# it at construction OVERRIDES winfo_class, and configuring it afterwards
# raises "attempt to change read-only option".


def test_class_defaults_to_empty_while_winfo_class_is_the_themed_name(our_root):
    """Both true at once, which is what made this worth measuring: cget is
    empty and winfo_class is TLabel."""
    label = tkcurses.ttk.Label(our_root)
    assert label.cget("class") == ""
    assert label.winfo_class() == "TLabel"


def test_a_given_class_overrides_winfo_class(our_root):
    """What the option is for: the style and the class bindings then resolve
    against the given name instead of the widget's own."""
    label = tkcurses.ttk.Label(our_root, **{"class": "Custom"})
    assert label.cget("class") == "Custom"
    assert label.winfo_class() == "Custom"


def test_class_is_read_only_after_construction(our_root):
    """Tk refuses it, and so must we: the widget's bindings were installed
    under the name it had when it was built, and moving it would leave them
    behind."""
    label = tkcurses.ttk.Label(our_root, **{"class": "Custom"})
    with pytest.raises(tkcurses.TclError, match="read-only"):
        label.configure(**{"class": "Other"})


def test_setting_class_to_what_it_already_is_is_not_a_change(our_root):
    """So a dict of options read back and passed whole does not raise."""
    label = tkcurses.ttk.Label(our_root, **{"class": "Custom"})
    label.configure(**{"class": "Custom"})
    assert label.winfo_class() == "Custom"


# A themed widget that binds under the classic widget's name receives nothing,
# because binding tags name one class and not a chain. It has happened three
# times from the subclass side - Spinbox/Entry, OptionMenu/Menubutton,
# ScrolledText/Text, each recorded in bd memory - and twice from the base side,
# where the classic widget hardcoded its own name: Button, found while writing
# TkCurses-3h5.3, and then Entry, Spinbox, Scrollbar, Text, Canvas, Menu,
# Listbox and PanedWindow, found while writing TkCurses-3h5.4.
#
# ttk.Panedwindow had already shipped with dead sash bindings before this test
# existed. That is what it is for: the fault is invisible from the option
# surface and from anything that does not actually deliver a gesture.


@pytest.mark.parametrize("widget_name", THEMED)
def test_a_themed_widget_binds_under_no_other_widgets_tag(widget_name, our_root):
    """Whatever a themed widget binds, it binds under the name it reports.

    A fresh root per widget, because bound_classes is shared: a tag another
    widget registered would otherwise look like this one's and hide the fault.
    Exactly that masking made a first version of this check pass ttk.Panedwindow
    while its sash bindings were going to "PanedWindow".

    Not every themed widget binds anything - a Label answers no gesture - so
    this asserts the absence of a FOREIGN tag rather than the presence of its
    own. A composite is allowed its children's tags: LabeledScale contains a
    Scale, and that Scale's bindings are legitimately TScale.
    """
    widget = getattr(tkcurses.ttk, widget_name)(our_root, name="w")
    own = widget.winfo_class()
    children = {
        child.winfo_class() for child in getattr(widget, "winfo_children", list)()
    }
    foreign = {
        tag for tag in our_root.tk.bound_classes if tag != own and tag not in children
    }
    assert not foreign, (
        f"ttk.{widget_name} reports {own!r} but registered class bindings under "
        f"{sorted(foreign)} - it will be offered none of them, so every gesture "
        "bound there is dead. The classic widget it is built on is binding "
        "under its own literal name instead of asking winfo_class()."
    )
