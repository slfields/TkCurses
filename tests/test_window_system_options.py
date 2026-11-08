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

"""The window-system options on Frame, LabelFrame, Toplevel and the root,
and ``setgrid`` on Listbox and Text. TkCurses-gm66.7.

Every rule here was measured on Tk 9.0.2. None of these options means anything
in a terminal, so each is checked as Tk checks it, kept and answered, and -
the part that is real - the ones Tk fixes at creation refuse ``configure``
afterwards.
"""

from __future__ import annotations

import pytest

from tkcurses import Frame, LabelFrame, Listbox, Misc, TclError, Text, Tk, Toplevel, ttk

VISUAL_LIST = (
    "class must be best, directcolor, grayscale, greyscale, pseudocolor, "
    "staticcolor, staticgray, staticgrey, truecolor, or default"
)


@pytest.fixture
def root():
    return Misc()


@pytest.fixture
def tk_root():
    window = Tk(useTk=False)
    yield window
    window.destroy()


CONTAINERS = [Frame, LabelFrame, Toplevel]


# ------------------------------------------------------------------ defaults


@pytest.mark.parametrize("widget", CONTAINERS)
@pytest.mark.parametrize(
    ("name", "value"), [("colormap", ""), ("container", 0), ("visual", "")]
)
def test_the_defaults(root, widget, name, value):
    assert widget(root).cget(name) == value


@pytest.mark.parametrize(
    ("widget", "expected"),
    [(Frame, "Frame"), (LabelFrame, "Labelframe"), (Toplevel, "Toplevel")],
)
def test_class_reads_back_as_tk_names_it(root, widget, expected):
    made = widget(root)
    assert made.cget("class") == expected == made.winfo_class()


def test_a_subclass_answers_its_own_name(root):
    """As every subclass here does: simpledialog.Dialog binds under it."""

    class Panel(LabelFrame):
        pass

    assert Panel(root).winfo_class() == "Panel"


@pytest.mark.parametrize("widget", [Frame, Toplevel])
def test_tile_defaults_off(root, widget):
    assert widget(root).cget("tile") == 0


def test_toplevel_screen_and_use_default_empty(root):
    window = Toplevel(root)
    assert (window.cget("screen"), window.cget("use")) == ("", "")


def test_the_roots(tk_root):
    expected = {
        "class": "Tk",
        "colormap": "",
        "container": 0,
        "height": 0,
        "screen": "",
        "use": "",
        "visual": "",
        "width": 0,
    }
    assert {name: tk_root.cget(name) for name in expected} == expected


def test_the_roots_class_is_its_class_name():
    window = Tk(useTk=False, className="Editor")
    try:
        assert window.cget("class") == "Editor" == window.winfo_class()
    finally:
        window.destroy()


@pytest.mark.parametrize("widget", [Listbox, Text])
def test_setgrid_defaults_off(root, widget):
    assert widget(root).cget("setgrid") == 0


# --------------------------------------------------------------------- class


@pytest.mark.parametrize("widget", CONTAINERS)
def test_class_by_keyword(root, widget):
    made = widget(root, class_="Mine")
    assert made.winfo_class() == "Mine" == made.cget("class")


@pytest.mark.parametrize("widget", CONTAINERS)
def test_class_by_option(root, widget):
    """``{"class": ...}`` is the option itself, and names the class too."""
    made = widget(root, **{"class": "Mine"})
    assert made.winfo_class() == "Mine"
    made = widget(root, {"class": "Other"})
    assert made.winfo_class() == "Other"


def test_the_keyword_wins_over_the_option(root):
    assert Frame(root, {"class": "Other"}, class_="Mine").winfo_class() == "Mine"


def test_the_option_in_kw_wins_over_cnf(root):
    """As every option does: the keywords are laid over ``cnf``."""
    assert Frame(root, {"class": "Other"}, **{"class": "Mine"}).winfo_class() == "Mine"


def test_the_callers_cnf_is_left_alone(root):
    cnf = {"class": "Mine", "width": 3}
    Frame(root, cnf)
    assert cnf == {"class": "Mine", "width": 3}


# ------------------------------------------------------- fixed at creation

FIXED = [
    (Frame, "class", "X"),
    (Frame, "colormap", "new"),
    (Frame, "container", 1),
    (Frame, "visual", "best"),
    (LabelFrame, "class", "X"),
    (LabelFrame, "visual", "best"),
    (Toplevel, "class", "X"),
    (Toplevel, "screen", ":0"),
    (Toplevel, "use", ""),
    (Toplevel, "colormap", "new"),
]


@pytest.mark.parametrize(("widget", "name", "value"), FIXED)
def test_configure_refuses_one_fixed_at_creation(root, widget, name, value):
    made = widget(root)
    with pytest.raises(TclError, match=f"can't modify -{name} option after widget"):
        made.configure(**{name: value})


@pytest.mark.parametrize("name", ["colormap", "container", "visual"])
def test_even_with_the_value_it_has(root, name):
    """Measured: configure(colormap="") on a Frame with "" is refused."""
    made = Frame(root)
    with pytest.raises(TclError, match="can't modify"):
        made.configure(**{name: made.cget(name)})


def test_class_by_its_keyword_spelling_too(root):
    with pytest.raises(TclError, match="can't modify -class option"):
        Frame(root).configure(class_="X")


@pytest.mark.parametrize(
    "name", ["class", "colormap", "container", "screen", "use", "visual"]
)
def test_the_root_refuses_each(tk_root, name):
    with pytest.raises(TclError, match=f"can't modify -{name} option"):
        tk_root.configure(**{name: tk_root.cget(name)})


@pytest.mark.parametrize("widget", [Frame, Toplevel])
def test_tile_may_change(root, widget):
    made = widget(root)
    made.configure(tile="yes")
    assert made.cget("tile") == 1


def test_a_refused_configure_changes_nothing_else(root):
    made = Frame(root, width=3)
    with pytest.raises(TclError):
        made.configure(width=5, visual="best")
    assert made.cget("width") == 3


THEMED = [
    name
    for name in ttk.__all__
    if isinstance(getattr(ttk, name), type)
    and issubclass(getattr(ttk, name), ttk.Widget)
    and name not in ("Widget", "OptionMenu")
]


def test_ttk_keeps_its_own_class_rule(root):
    """ttk's -class is "" by default, and the class is its own."""
    frame = ttk.Frame(root)
    assert frame.cget("class") == ""
    assert ttk.Labelframe(root).winfo_class() == "TLabelframe"


@pytest.mark.parametrize("name", THEMED)
@pytest.mark.parametrize(
    "change",
    [
        lambda widget: widget.configure(class_="Other"),
        lambda widget: widget.configure({"class": "Other"}),
        lambda widget: widget.configure(class_=widget.cget("class")),
        lambda widget: widget.__setitem__("class", "Other"),
    ],
    ids=["keyword", "dict", "unchanged", "item"],
)
def test_a_themed_widget_refuses_any_class_change(root, name, change):
    """Measured on Tk 9.0.2, on every themed widget: configuring -class
    after the widget is made is refused, even to the value it has, however
    it is spelled."""
    widget = getattr(ttk, name)(root)
    before = widget.winfo_class()
    with pytest.raises(TclError, match=r"^attempt to change read-only option$"):
        change(widget)
    assert widget.winfo_class() == before


# ------------------------------------------------------------------- values


@pytest.mark.parametrize(
    "value", ["truecolor 24", "tru", "b", "best -1", ".", "default", "grey", "staticg"]
)
def test_a_visual_tk_takes(root, value):
    assert Frame(root, visual=value).cget("visual") == value


@pytest.mark.parametrize("value", ["s", "d", "TrueColor", " truecolor", "default 24"])
def test_a_visual_tk_refuses(root, value):
    with pytest.raises(TclError) as caught:
        Frame(root, visual=value)
    assert (
        str(caught.value)
        == f'unknown or ambiguous visual name "{value}": {VISUAL_LIST}'
    )


def test_a_visuals_depth_is_an_integer(root):
    with pytest.raises(TclError, match='expected integer but got "x"'):
        Frame(root, visual="truecolor x")


@pytest.mark.parametrize("value", ["", "new", "."])
def test_a_colormap_tk_takes(root, value):
    assert Frame(root, colormap=value).cget("colormap") == value


def test_a_colormap_may_name_another_window(root):
    other = Frame(root, name="other")
    assert Frame(root, colormap=other._w).cget("colormap") == other._w


@pytest.mark.parametrize("value", ["NEW", ".nowhere"])
def test_a_colormap_naming_no_window(root, value):
    with pytest.raises(TclError, match=f'bad window path name "{value}"'):
        Frame(root, colormap=value)


@pytest.mark.parametrize("name", ["container", "tile"])
def test_booleans(root, name):
    assert Frame(root, **{name: "yes"}).cget(name) == 1
    with pytest.raises(TclError, match='expected boolean value but got "maybe"'):
        Frame(root, **{name: "maybe"})


@pytest.mark.parametrize("widget", [Listbox, Text])
def test_setgrid_is_a_boolean(root, widget):
    assert widget(root, setgrid=1).cget("setgrid") == 1
    with pytest.raises(TclError, match='expected boolean value but got "maybe"'):
        widget(root, setgrid="maybe")


def test_use_takes_only_nothing(root):
    """A terminal has no window to embed in. Measured: Tk refuses one that
    does not exist this way."""
    assert Toplevel(root, use="").cget("use") == ""
    with pytest.raises(TclError, match='couldn\'t create child of window "0x1"'):
        Toplevel(root, use="0x1")


def test_screen_is_kept(root):
    assert Toplevel(root, screen=":0").cget("screen") == ":0"


def test_the_roots_width_and_height(tk_root):
    """Measured: -5 reads back 0, and "x" is refused."""
    tk_root.configure(width=300, height=200)
    assert (tk_root.cget("width"), tk_root.cget("height")) == (300, 200)
    tk_root.configure(width=-5)
    assert tk_root.cget("width") == 0
    with pytest.raises(TclError, match='expected screen distance but got "x"'):
        tk_root.configure(height="x")
