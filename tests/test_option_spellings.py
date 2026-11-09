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

"""How an option may be spelled, compared against real tkinter.

Two mechanisms wear the same clothes and are not the same thing, which is the
confusion TkCurses-y5q was about:

* **Tcl synonyms** - ``bg``, ``fg``, ``bd``. Tk defines these itself. They are
  keys of the widget's own option list and ``cget`` takes them.
* **Python-keyword workarounds** - ``from_``. ``from`` is a reserved word, so
  tkinter lets a *keyword argument* carry one trailing underscore and strips it
  (``Misc._options``: ``if k[-1] == '_': k = k[:-1]``). The option itself is
  still ``from``: it is not in the key set under any other name, and
  ``cget("from_")`` raises.

This library stored the workaround spelling as the canonical name, so
``w.configure()["from"]`` raised KeyError here and worked in tkinter. Every
expectation below is measured against the real toolkit in the same run rather
than written down from the manual.
"""

from __future__ import annotations

import tkinter
from tkinter import ttk as real_ttk
from types import SimpleNamespace

import pytest

import tkcurses
from tkcurses import ttk
from tkcurses._core.geometry import Rect
from tkcurses._core.panels import PanelStack

#: Widgets with a range, ours beside the real one. Progressbar is deliberately
#: absent: measured, neither ttk.Progressbar nor ttk.LabeledScale has a -from
#: at all, which corrects TkCurses-y5q's own list of what to rename.
RANGED = {
    "Scale": (lambda root: tkcurses.Scale(root, name="s"), tkinter.Scale),
    "Spinbox": (lambda root: tkcurses.Spinbox(root, name="s"), tkinter.Spinbox),
    "ttk.Scale": (lambda root: ttk.Scale(root, name="s"), real_ttk.Scale),
    "ttk.Spinbox": (lambda root: ttk.Spinbox(root, name="s"), real_ttk.Spinbox),
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
    root.tk.panels = PanelStack(
        window_factory=lambda rect: SimpleNamespace(rect=rect), panel_factory=None
    )
    root._rect = Rect(0, 0, 80, 24)
    root._mapped = True
    return root


@pytest.mark.parametrize("name", list(RANGED))
def test_the_range_option_is_reported_as_tkinter_reports_it(name, our_root, real_root):
    """The acceptance for TkCurses-y5q, taken from the real toolkit.

    Not "we report 'from'" but "we report whatever tkinter reports", so the
    test cannot drift from the thing it is comparing against.
    """
    ours = RANGED[name][0](our_root)
    theirs = RANGED[name][1](real_root)
    theirs_keys = {key for key in theirs.configure() if "from" in key}
    ours_keys = {key for key in ours.configure() if "from" in key}
    assert ours_keys == theirs_keys, (
        f"{name} reports {sorted(ours_keys)} where tkinter reports "
        f"{sorted(theirs_keys)}"
    )


@pytest.mark.parametrize("name", list(RANGED))
def test_cget_takes_the_canonical_name_and_refuses_the_keyword_form(
    name, our_root, real_root
):
    """``cget`` is a string lookup, not a keyword, so no underscore is stripped.

    Measured: ``cget("from_")`` raises ``unknown option "-from_"`` in tkinter.
    Before this it answered here, which made ``from_`` look like a synonym.
    """
    ours = RANGED[name][0](our_root)
    theirs = RANGED[name][1](real_root)
    assert ours.cget("from") == pytest.approx(float(theirs.cget("from")))
    with pytest.raises(tkinter.TclError):
        theirs.cget("from_")
    with pytest.raises(tkcurses.TclError):
        ours.cget("from_")


@pytest.mark.parametrize("name", list(RANGED))
@pytest.mark.parametrize("spelling", ["from", "from_"])
def test_both_spellings_work_as_a_keyword(name, spelling, our_root):
    """The underscore is stripped on the keyword path, and only there.

    Both forms have to reach the option: ``from_=2`` is what a Python caller
    can type, and ``**{"from": 2}`` is what a dict of options read back out of
    a widget gives you - which is the case that made the old spelling look
    harmless, because a round trip through ``configure()`` was self-consistent.
    """
    make = RANGED[name][0]
    widget = make(our_root)
    widget.configure(**{spelling: 2, "to": 10})
    assert widget.cget("from") == pytest.approx(2)


@pytest.mark.parametrize("spelling", ["from", "from_"])
def test_the_keyword_reaches_the_range_and_not_just_the_option(spelling, our_root):
    """Renaming a dict key is not the same as rewiring what reads it.

    A Scale starts at the low end of its range, so this fails if the option is
    stored under one name and read under another - which no type checker would
    have caught.
    """
    scale = tkcurses.Scale(our_root, name="s", to=9, **{spelling: 3})
    assert scale.get() == pytest.approx(3)


def test_a_tcl_synonym_is_not_the_same_thing_as_a_keyword_workaround(
    our_root, real_root
):
    """``bg`` survives ``cget``; ``from_`` does not. That asymmetry is Tk's.

    Pinned because the two were held in one table here, which is what let
    ``cget("from_")`` answer. The key-set half of the ``bg`` story is a
    separate gap - TkCurses-bv0 - and this test deliberately checks only what
    ``cget`` does, so it passes before and after that one is fixed.
    """
    theirs = tkinter.Scale(real_root, bg="red")
    ours = tkcurses.Scale(our_root, name="s", bg="red")
    assert theirs.cget("bg") == theirs.cget("background")
    assert ours.cget("bg") == ours.cget("background")
    with pytest.raises(tkinter.TclError):
        theirs.cget("from_")
    with pytest.raises(tkcurses.TclError):
        ours.cget("from_")


@pytest.mark.parametrize("name", ["Progressbar", "LabeledScale"])
def test_the_widgets_without_a_range_have_no_from_option(name, our_root, real_root):
    """Correcting TkCurses-y5q's own list, which named Progressbar as needing
    the rename. Measured: it has no ``-from`` in either library."""
    theirs = getattr(real_ttk, name)(real_root)
    ours = getattr(ttk, name)(our_root, name="w")
    assert not [key for key in theirs.configure() if "from" in key]
    assert not [key for key in ours.configure() if "from" in key]


# ------------------------------------------------------- the Tcl synonyms
#
# Enumerated from the real toolkit rather than listed here, by the shape of the
# configure() entry: a synonym's is a 2-tuple (synonym, real name) where a real
# option's is a 5-tuple (name, dbName, dbClass, default, current). So this
# cannot fall behind a Tk release, and it corrected a guess - the issue that
# started it supposed Tk defined activebackground/activebg, and there is no
# activebg. Tk 9.0.2 defines exactly six: bd, bg, bgimg, fg, invcmd, vcmd.

#: Synonyms whose target option this library does not have yet, so the synonym
#: cannot be offered either: naming it would resolve to an option not in the
#: spec and still raise, just more confusingly. A gap recorded with the id that
#: will close it, never a skipped widget.
UNSUPPORTED_SYNONYM_TARGETS = {
    "backgroundimage": "TkCurses-yi4: Frame and Toplevel lack -backgroundimage",
}

PAIRED = {
    "Entry": (tkinter.Entry, lambda root: tkcurses.Entry(root, name="w")),
    "Spinbox": (tkinter.Spinbox, lambda root: tkcurses.Spinbox(root, name="w")),
    "Frame": (tkinter.Frame, lambda root: tkcurses.Frame(root, name="w")),
    "Label": (tkinter.Label, lambda root: tkcurses.Label(root, name="w")),
    "Button": (tkinter.Button, lambda root: tkcurses.Button(root, name="w")),
}


def synonyms_of(widget) -> dict[str, str]:
    """The Tcl synonyms a real widget declares, shortest name to real name."""
    return {
        entry[0]: entry[1].lstrip("-")
        for entry in widget.configure().values()
        if len(entry) == 2
    }


@pytest.mark.parametrize("name", list(PAIRED))
def test_we_offer_every_synonym_tk_offers(name, our_root, real_root):
    """``tkcurses.Entry(vcmd=f)`` raised where tkinter accepted it.

    vcmd and invcmd are the spellings tkinter's own documentation uses for
    entry validation, so a program copied out of it failed here on its first
    line. TkCurses-oe5.
    """
    real_cls, make_ours = PAIRED[name]
    theirs = real_cls(real_root)
    ours = make_ours(our_root)
    expected = {
        short: target
        for short, target in synonyms_of(theirs).items()
        if target not in UNSUPPORTED_SYNONYM_TARGETS
    }
    assert expected, f"no synonyms measured for {name}, so this proves nothing"
    missing = [
        short
        for short, target in expected.items()
        if target in ours.configure() and short not in ours._option_synonyms
    ]
    assert not missing, f"{name} does not offer {missing}, which tkinter does"


@pytest.mark.parametrize("name", list(PAIRED))
def test_every_synonym_we_offer_reaches_its_option(name, our_root):
    """A synonym has to resolve, not merely be accepted and dropped."""
    ours = PAIRED[name][1](our_root)
    for short, target in ours._option_synonyms.items():
        if target not in ours.configure():
            continue
        ours.configure(**{short: ours.cget(target)})
        assert ours.cget(short) == ours.cget(target), (
            f"{name}'s {short!r} does not read back as {target!r}"
        )


def test_the_validation_synonyms_reach_the_validator(our_root):
    """Not just stored under the right key - actually wired to validation.

    The point of the synonym is that a tutorial's ``vcmd=`` works, and a
    tutorial's next line types into the entry.
    """
    seen = []
    entry = tkcurses.Entry(
        our_root,
        name="w",
        validate="key",
        vcmd=lambda proposed: seen.append(proposed) or False,
        invcmd=lambda: seen.append("refused"),
    )
    entry.insert(0, "x")
    assert seen == ["x", "refused"], f"vcmd and invcmd did not reach validation: {seen}"
    assert entry.get() == "", "the edit was not refused"


@pytest.mark.parametrize(
    "name", ["Entry", "Spinbox", "Combobox", "Label", "Frame", "Button"]
)
def test_a_themed_widget_offers_no_synonyms_at_all(name, our_root, real_root):
    """Measured: ttk has none, and that is not an accident of this library.

    ``ttk.Label`` has ``background`` and refuses ``bg``; ``ttk.Entry`` has
    ``validatecommand`` and refuses ``vcmd``. Tk's synonyms live in the classic
    widgets' option tables. Every themed widget here is built on a classic one,
    so this had to be declared rather than inherited - and until it was,
    ``ttk.Label(bg="red")`` was accepted here and raises in tkinter.
    """
    theirs = getattr(real_ttk, name)(real_root)
    ours = getattr(ttk, name)(our_root, name="w")
    assert synonyms_of(theirs) == {}, f"real ttk.{name} grew a synonym"
    assert ours._option_synonyms == {}, f"our ttk.{name} offers synonyms"
    for short in ("bg", "fg", "bd", "vcmd"):
        with pytest.raises(tkinter.TclError):
            getattr(real_ttk, name)(real_root, **{short: "red"})
        with pytest.raises(tkcurses.TclError):
            getattr(ttk, name)(our_root, name=f"x{short}", **{short: "red"})


# justify, measured on Tk 9.0.2 on every widget that has it: "middle" and
# "CENTER" are bad, "c" reads back "center", and "" is ambiguous - except on
# the ttk label family, where "" is unset. Only Listbox checked it here.

JUSTIFIED = [
    "Label", "Button", "Entry", "Message", "Spinbox", "Checkbutton",
    "Radiobutton", "Menubutton", "Listbox",
    "ttk.Label", "ttk.Button", "ttk.Entry", "ttk.Combobox", "ttk.Spinbox",
    "ttk.Checkbutton", "ttk.Radiobutton", "ttk.Menubutton", "ttk.Progressbar",
]  # fmt: skip
LABEL_FAMILY = {"ttk.Label", "ttk.Button", "ttk.Checkbutton", "ttk.Radiobutton",
                "ttk.Menubutton", "ttk.Progressbar"}  # fmt: skip


def _justified(name):
    import tkcurses
    from tkcurses import ttk

    module, _, cls = name.rpartition(".")
    return getattr(ttk if module else tkcurses, cls)


@pytest.mark.parametrize("name", JUSTIFIED)
def test_justify_is_checked_as_tk_checks_it(name):
    import tkcurses

    root = tkcurses.Misc()
    widget_class = _justified(name)
    for bad in ("middle", "CENTER"):
        with pytest.raises(tkcurses.TclError, match=f'bad justification "{bad}"'):
            widget_class(root, justify=bad)
    assert widget_class(root, justify="c").cget("justify") == "center"
    widget = widget_class(root)
    with pytest.raises(tkcurses.TclError, match="bad justification"):
        widget.configure(justify="middle")
    if name in LABEL_FAMILY:
        assert widget_class(root, justify="").cget("justify") == ""
    else:
        with pytest.raises(tkcurses.TclError, match='ambiguous justification ""'):
            widget_class(root, justify="")
