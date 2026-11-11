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

"""Which options change what a widget draws, measured.

The API reference shows a sample for every option that visibly changes a
widget (TkCurses-imii.5). "Visibly" is measured here rather than judged:
each widget is drawn in a pseudo-terminal - the test harness - once
without the option and once with it, under the state the option shows in
(focused for ``highlight*``, selected for ``select*``, disabled for
``disabled*``, and so on), and the two screens are compared cell by cell,
colour and attributes included.

Run from the repository root::

    python3 tests/support/record_visible_options.py

The themed widgets are measured too, under ``ttk.Button`` and so on, but
only for the options Tk's own ttk widget has - ``tk_ttk_options.json``,
recorded from Tk by ``record_tk_ttk_options.py``, which are also all
TkCurses's take. An option Tk has and TkCurses lacks is ``missing``.

It writes ``visible_options.json`` beside itself, which
``tests/test_docstrings.py`` holds the documentation to. Each option is one
of ``visible`` (with the value and state that showed it), ``invisible``
(every value tried drew the same screen), ``behaviour`` (it takes a
callback, a variable or a widget: what it does is not a picture),
``refused`` (every value tried was an error) or ``unsettled`` (the screen
did not hold still long enough to compare, which the convention treats as
visible). Every try is drawn between two baselines, and counts only if
they agree.

``invisible`` means no difference under the states tried, not that the
option draws nothing: ``overrelief`` needs the mouse over the widget,
which this cannot do. Say "not drawn" in a docstring only once it has
been seen. Run it three times after a change here; the result should
not move.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests.support.terminal import TerminalHarness  # noqa: E402

OUT = Path(__file__).with_name("visible_options.json")
TK_TTK = Path(__file__).with_name("tk_ttk_options.json")
COLS, ROWS = 50, 16

#: How each widget is made, and what it is given to show.
BASES = {
    "Button": ("tk.Button(root, **{'text': 'Sample', **kw})", ""),
    "Checkbutton": ("tk.Checkbutton(root, **{'text': 'Sample', **kw})", ""),
    "Radiobutton": ("tk.Radiobutton(root, **{'text': 'Sample', 'value': 1, **kw})", ""),
    "Label": ("tk.Label(root, **{'text': 'Sample', **kw})", ""),
    "Message": (
        "tk.Message(root, **{'text': 'A longer message that the widget wraps', **kw})",
        "",
    ),
    "Menubutton": ("tk.Menubutton(root, **{'text': 'Sample', **kw})", ""),
    "OptionMenu": (
        "tk.OptionMenu(root, tk.StringVar(root, 'one'), 'one', 'two')",
        "w.configure(**kw)",
    ),
    "Entry": ("tk.Entry(root, **kw)", "w.insert(0, 'Sample text')"),
    "Spinbox": ("tk.Spinbox(root, **{'from_': 0, 'to': 10, **kw})", ""),
    "Scale": ("tk.Scale(root, **{'from_': 0, 'to': 10, **kw})", ""),
    "Scrollbar": ("tk.Scrollbar(root, **kw)", "w.set(0.2, 0.5)"),
    "Listbox": (
        "tk.Listbox(root, **{'height': 4, **kw})",
        "[w.insert('end', f'Item {n}') for n in range(6)]",
    ),
    "Text": (
        "tk.Text(root, **{'width': 24, 'height': 4, **kw})",
        "w.insert('1.0', 'Sample text\\nsecond\\tline\\n3.14\\tnumber')",
    ),
    "Canvas": (
        "tk.Canvas(root, **{'width': 20, 'height': 5, **kw})",
        "w.create_rectangle(2, 2, 12, 7); w.create_text(15, 4, text='Hi')",
    ),
    "Frame": ("tk.Frame(root, **{'width': 12, 'height': 4, **kw})", ""),
    "LabelFrame": (
        "tk.LabelFrame(root, **{'text': 'Group', **kw})",
        "tk.Label(w, text='inside').pack()",
    ),
    "PanedWindow": (
        "tk.PanedWindow(root, **kw)",
        "w.add(tk.Label(w, text='left')); w.add(tk.Label(w, text='right'))",
    ),
    "ttk.Button": ("ttk.Button(root, **{'text': 'Sample', **kw})", ""),
    "ttk.Checkbutton": ("ttk.Checkbutton(root, **{'text': 'Sample', **kw})", ""),
    "ttk.Radiobutton": (
        "ttk.Radiobutton(root, **{'text': 'Sample', 'value': 1, **kw})",
        "",
    ),
    "ttk.Label": ("ttk.Label(root, **{'text': 'Sample', **kw})", ""),
    "ttk.Menubutton": ("ttk.Menubutton(root, **{'text': 'Sample', **kw})", ""),
    "ttk.OptionMenu": (
        "ttk.OptionMenu(root, tk.StringVar(root), 'one', 'one', 'two')",
        "w.configure(**kw)",
    ),
    "ttk.Entry": ("ttk.Entry(root, **kw)", "w.insert(0, 'Sample text')"),
    "ttk.Combobox": (
        "ttk.Combobox(root, **{'values': ('one', 'two'), **kw})",
        "w.insert(0, 'Sample text')",
    ),
    "ttk.Spinbox": (
        "ttk.Spinbox(root, **{'from_': 0, 'to': 10, **kw})",
        "w.insert(0, '3')",
    ),
    "ttk.Scale": ("ttk.Scale(root, **{'from_': 0, 'to': 10, 'value': 3, **kw})", ""),
    "ttk.LabeledScale": ("ttk.LabeledScale(root, **kw)", ""),
    "ttk.Progressbar": ("ttk.Progressbar(root, **{'value': 40, **kw})", ""),
    "ttk.Scrollbar": ("ttk.Scrollbar(root, **kw)", "w.set(0.2, 0.5)"),
    "ttk.Separator": ("ttk.Separator(root, **kw)", "FILL"),
    "ttk.Sizegrip": ("ttk.Sizegrip(root, **kw)", ""),
    "ttk.Frame": ("ttk.Frame(root, **{'width': 12, 'height': 4, **kw})", ""),
    "ttk.Labelframe": (
        "ttk.Labelframe(root, **{'text': 'Group', **kw})",
        "ttk.Label(w, text='inside').pack()",
    ),
    "ttk.Panedwindow": (
        "ttk.Panedwindow(root, **{'orient': 'horizontal', **kw})",
        "w.add(ttk.Label(w, text='left')); w.add(ttk.Label(w, text='right'))",
    ),
    "ttk.Notebook": (
        "ttk.Notebook(root, **kw)",
        "w.pack(padx=1, pady=1);"
        " w.add(ttk.Label(w, text='first page'), text='One');"
        " w.add(ttk.Label(w, text='second'), text='Two')",
    ),
    "ttk.Treeview": (
        "ttk.Treeview(root, **{'columns': ('size',), 'height': 4, **kw})",
        "w.pack(padx=1, pady=1);"
        " w.heading('#0', text='Name'); w.heading('size', text='Size');"
        " top = w.insert('', 'end', text='Folder', open=True);"
        " w.insert(top, 'end', text='File', values=('3',));"
        " w.insert('', 'end', text='Other', values=('9',))",
    ),
    # A menu dropped down, which is where nearly all of its options show; a
    # menu bar draws only its colours and font.
    "Menu": (
        "tk.Menu(root, **kw)",
        "w.add_command(label='Open'); w.add_command(label='Save');"
        " w.add_checkbutton(label='Wrap'); w.invoke(2); w.post(2, 1)",
    ),
}

#: Options whose value is a callback, a variable or a widget.
BEHAVIOUR = {
    "command", "variable", "textvariable", "listvariable", "validatecommand",
    "invalidcommand", "xscrollcommand", "yscrollcommand", "postcommand",
    "tearoffcommand", "menu", "labelwidget",
    # Values compared with the variable's. One can look visible - an onvalue
    # equal to the variable's current value shows the button selected - but
    # what changed is the state, not how a state is drawn.
    "onvalue", "offvalue", "value", "tristatevalue",
}  # fmt: skip

#: Except where the value is what the widget draws: a themed Scale's slider
#: and a Progressbar's bar.
DRAWN_VALUES = {("ttk.Scale", "value"), ("ttk.Progressbar", "value")}

#: Values for an option whose meaning, and so whose values, depend on the
#: widget.
WIDGET_VALUES: dict[tuple[str, str], list[object]] = {
    ("ttk.Treeview", "show"): ["tree", "headings"],
    ("ttk.Treeview", "columns"): [("size", "kind"), ()],
    ("ttk.Treeview", "displaycolumns"): [(), "#all"],
    ("ttk.Treeview", "titlecolumns"): [1],
    ("ttk.Treeview", "titleitems"): [1],
    ("ttk.Progressbar", "mode"): ["indeterminate"],
    ("ttk.Progressbar", "maximum"): [50, 200],
    ("ttk.Progressbar", "value"): [70, 0],
    ("ttk.Scale", "value"): [8, 0],
    ("ttk.Progressbar", "length"): [5, 30],
    ("ttk.Scale", "length"): [5, 30],
}

#: The state an option shows in, by its name; anything else is drawn plain.
SETUPS = {
    "disabled": (
        "w.entryconfigure(0, state='disabled') if w.winfo_class() == 'Menu'"
        " else w.configure(state='disabled')"
    ),
    "readonly": "w.configure(state='readonly')",
    "active": (
        "w.activate(0) if w.winfo_class() == 'Menu' else"
        " w.activate('slider') if w.winfo_class() == 'Scrollbar' else"
        " w.configure(state='active') if 'state' in w.keys() and"
        " w.winfo_class() in ('Button', 'Checkbutton', 'Radiobutton',"
        " 'Menubutton', 'Label', 'Scale') else None"
    ),
    "focus": "w.focus_force()",
    "selected": (
        "(w.select_range(0, 'end') if hasattr(w, 'select_range') else"
        " w.selection_set(0) if w.winfo_class() == 'Listbox' else"
        " w.tag_add('sel', '1.0', '1.6') if w.winfo_class() == 'Text' else"
        " w.select() if hasattr(w, 'select') else None); w.focus_force()"
    ),
    "empty": "w.delete(0, 'end') if hasattr(w, 'delete') else None",
    # Selected, and the focus somewhere else.
    "unfocused": (
        "w.select_range(0, 'end') if hasattr(w, 'select_range') else"
        " w.tag_add('sel', '1.0', '1.6') if w.winfo_class() == 'Text' else"
        " w.selection_set(0) if w.winfo_class() == 'Listbox' else None"
    ),
    # Turned on, without the focus markers selecting it would bring.
    "on": "w.select()",
    # A variable holding neither value: Tk's third state.
    "tristate": "w.setvar(w.cget('variable'), w.cget('tristatevalue'))",
}


def setup_for(option: str) -> str:
    if option.startswith("disabled"):
        return "disabled"
    if option.startswith("readonly"):
        return "readonly"
    if option.startswith("active"):
        return "active"
    if option.startswith(("highlight", "insert")) or option == "blockcursor":
        return "focus"
    if option == "inactiveselectbackground":
        return "unfocused"
    if option == "tristateimage":
        return "tristate"
    if option == "selectimage":
        return "on"
    if option.startswith("select") and option != "selectmode":
        return "selected"
    if option.startswith("placeholder"):
        return "empty"
    return "plain"


BOOLEANS = {
    "indicatoron", "showvalue", "showhandle", "opaqueresize", "exportselection",
    "setgrid", "takefocus", "undo", "autoseparators", "blockcursor", "jump",
    "container", "tearoff", "striped", "tile",
}  # fmt: skip

#: Content an option needs before it can show: alignment needs room to move
#: in, and justification needs lines of different lengths. Given to the
#: baseline as well, so only the option itself differs.
NEEDS = {
    "anchor": {"width": 20, "height": 3},
    "justify": {"text": "Sample\na wider line"},
    "wraplength": {"text": "a longer line of text to wrap"},
    "labelanchor": {"width": 20, "height": 4},
    "placeholderforeground": {"placeholder": "Type here"},
    "compound": {"image": "IMAGE"},
    "wrap": {"width": 8},
    "spacing2": {"width": 8},
    # An option that applies only in combination with another.
    "selectimage": {"image": "IMAGE"},
    "tristateimage": {"image": "IMAGE"},
    # Checkbutton and Radiobutton have no border by default here.
    "offrelief": {"indicatoron": 0, "borderwidth": 1},
    "tabstyle": {"tabs": "3"},
    # A background image needs a window bigger than itself to be centred
    # or tiled in, and tiling needs the image.
    "backgroundimage": {"width": 10, "height": 4},
    "tile": {"backgroundimage": "IMAGE", "width": 10, "height": 4},
}

COLOURS = ("red",)
RELIEFS = ("groove", "sunken", "raised", "flat")


def candidates(option: str, default: object) -> list[object]:
    """Values to try, each different from the default where it can be."""
    name = option
    if name.endswith(("background", "foreground", "color", "colour")) or name in (
        "bg", "fg", "troughcolor", "selectcolor",
    ):  # fmt: skip
        values: list[object] = list(COLOURS)
    elif name.endswith("relief"):
        values = list(RELIEFS)
    elif name in ("anchor", "labelanchor"):
        values = ["e", "s", "nw"]
    elif name == "justify":
        values = ["right", "center"]
    elif name == "orient":
        values = ["horizontal", "vertical"]
    elif name == "state":
        values = ["disabled", "active", "readonly"]
    elif name in ("text", "label", "title", "placeholder"):
        values = ["Changed"]
    elif name == "underline":
        values = [0, 2]
    elif name == "font":
        values = ["TkDefaultFont 10 bold", "TkFixedFont 10 underline"]
    elif name in ("image", "backgroundimage"):
        values = ["IMAGE"]
    elif name in ("selectimage", "tristateimage"):
        values = ["IMAGE2"]
    elif name == "compound":
        values = ["left", "top"]
    elif name == "bitmap":
        values = ["info", "gray50"]
    elif name == "show":
        values = ["*"]
    elif name == "selectmode":
        values = ["extended", "single"]
    elif name == "activestyle":
        values = ["underline", "none", "dotbox"]
    elif name == "wrap":
        values = ["none", "word", "char", 1, 0]
    elif name == "tabs":
        values = ["4", "4 right"]
    elif name == "tabstyle":
        values = ["wordprocessor", "tabular"]
    elif name == "direction":
        values = ["right", "above", "left", "flush"]
    elif name == "values":
        values = ["a b c"]
    elif name == "format":
        values = ["%05.1f"]
    elif name in ("from", "to", "increment", "resolution", "tickinterval",
                  "bigincrement"):  # fmt: skip
        values = [2, 0.5, 5]
    elif name in BOOLEANS:
        values = [0, 1]
    elif name == "insertunfocussed":
        values = ["none", "hollow", "solid"]
    elif name == "cursor" or name.endswith("cursor"):
        values = ["hand2"]
    elif name == "type":
        values = ["normal", "tearoff"]
    elif name in ("class",):
        values = ["Special"]
    elif name == "style":
        # A style derived from the widget's own, made by the program.
        values = ["SAMPLE_STYLE"]
    elif name == "scrollregion":
        values = ["0 0 40 20"]
    elif name in ("offset",):
        values = ["2,2"]
    elif name in ("tile", "colormap", "visual"):
        return []
    elif name in BOOLEANS:
        values = [0, 1]
    else:
        values = [0, 3, 9]
    return [v for v in values if str(v) != str(default)] or values


PROGRAM = r"""
import json, sys, time, traceback
import tkcurses as tk
from tkcurses import ttk
root = tk.Tk()
spec = json.loads(open(sys.argv[1]).read())
# A themed widget's "style" is tried as a style of its own class that
# changes the colours, so that a style it takes is a style that shows.
probe = eval(spec["make"], {"tk": tk, "ttk": ttk, "root": root, "kw": {}})
sample_style = "Sample." + probe.winfo_class()
ttk.Style(root).configure(
    sample_style, foreground="red", background="blue", fieldbackground="blue"
)
probe.destroy()
image = tk.PhotoImage(master=root, data=["#.#", ".#."], palette={"#": "cyan"})
image2 = tk.PhotoImage(master=root, data=["##.", ".##"], palette={"#": "red"})
state = {"step": -1}

def build(kw, setup):
    for child in root.winfo_children():
        child.destroy()
    root.configure(menu="")
    images = {"IMAGE": image, "IMAGE2": image2, "SAMPLE_STYLE": sample_style}
    kw = {k: images.get(v, v) if isinstance(v, str) else v for k, v in kw.items()}
    w = eval(spec["make"], {"tk": tk, "ttk": ttk, "root": root, "kw": kw})
    if spec["after"] == "FILL":
        w.pack(padx=1, pady=1, fill="x")
    elif spec["after"]:
        exec(spec["after"], {"tk": tk, "ttk": ttk, "root": root, "w": w, "kw": kw})
    if w.winfo_class() != "Menu" and not w.winfo_manager():
        w.pack(padx=1, pady=1)
    if setup:
        exec(setup, {"w": w})

def poll():
    try:
        step = int(open(spec["control"]).read() or -1)
    except ValueError:
        step = -1
    if step != state["step"]:
        state["step"] = step
        if step >= len(spec["variants"]):
            root.destroy()
            return
        kw, setup = spec["variants"][step]
        try:
            build(kw, setup)
            result = "ok"
        except Exception as error:
            result = "error: " + str(error).splitlines()[0][:200]
        def ack():
            open(spec["ack"], "w").write(f"{step} {result}")
        root.after(80, ack)
    root.after(15, poll)

root.after(15, poll)
root.mainloop()
"""


def _cell(term: TerminalHarness, row: int, column: int) -> tuple[object, ...]:
    """A cell as it looks. Dim counts only where there is a character to
    dim: the harness keeps its dim mark on a cell that has since been
    erased, and a dim space looks like any other space - it made sixteen
    options look as if each left something behind."""
    char = term.char_at(row, column)
    dim = term.attrs_at(row, column)["dim"] and char.data.strip() != ""
    return (*tuple(char), dim)


def measure(widget: str) -> dict[str, object]:
    """Every option of one widget, measured."""
    import tkcurses
    from tkcurses import ttk

    make, after = BASES[widget]
    themed = widget.startswith("ttk.")
    cls = getattr(ttk, widget[4:]) if themed else getattr(tkcurses, widget)
    options: dict[str, object] = {}
    for klass in reversed(cls.__mro__):
        options.update(vars(klass).get("_widget_options", {}) or {})
    result: dict[str, object] = {}
    if themed:
        tk_has = set(json.loads(TK_TTK.read_text())[widget[4:]])
        for option in sorted(tk_has - set(options)):
            result[option] = {"kind": "missing"}
        options = {k: v for k, v in options.items() if k in tk_has}
    else:
        # Less any a classic widget keeps from its base and refuses, as
        # LabelFrame does Frame's backgroundimage and tile.
        public = set(cls._public_options())
        options = {k: v for k, v in options.items() if k in public}
    variants: list[tuple[dict[str, object], str]] = []
    plan: dict[str, list[tuple[int, int, object, str]]] = {}
    for option in sorted(options):
        if option in BEHAVIOUR and (widget, option) not in DRAWN_VALUES:
            result[option] = {"kind": "behaviour"}
            continue
        values = WIDGET_VALUES.get((widget, option)) or candidates(
            option, options[option]
        )
        if not values:
            result[option] = {"kind": "behaviour"}
            continue
        setup = setup_for(option)
        needs = {k: v for k, v in NEEDS.get(option, {}).items() if k in options}
        if option == "justify" and widget in ("Entry", "Spinbox"):
            needs = {}
        for value in values:
            # The screen it is compared with is drawn immediately before it,
            # not once for the whole run: rebuilding a widget many times over
            # moves things a single early baseline would not show - the
            # focus, most of all - and every option then looked visible.
            key = "from_" if option == "from" else option
            # And drawn again after it: the try counts only if the two agree,
            # so a widget still settling when sampled cannot pass for an
            # option that changed it. Measured: Scrollbar's highlightcolor,
            # highlightthickness and repeatinterval each came out visible in
            # one run of three before this.
            base = len(variants)
            variants.append((dict(needs), SETUPS.get(setup, "")))
            variants.append(({**needs, key: value}, SETUPS.get(setup, "")))
            variants.append((dict(needs), SETUPS.get(setup, "")))
            plan.setdefault(option, []).append((base, base + 1, value, setup))

    with tempfile.TemporaryDirectory() as tmp:
        control, ack, spec_file = (Path(tmp) / n for n in ("c", "a", "s"))
        control.write_text("")
        spec_file.write_text(
            json.dumps(
                {
                    "make": make,
                    "after": after,
                    "variants": variants,
                    "control": str(control),
                    "ack": str(ack),
                }
            )
        )
        program = Path(tmp) / "measure.py"
        program.write_text(PROGRAM)
        term = TerminalHarness(COLS, ROWS, timeout=20)
        screens: list[object] = []
        outcomes: list[str] = []
        try:
            term.run([sys.executable, str(program), str(spec_file)])
            for step in range(len(variants)):
                control.write_text(str(step))
                deadline = time.monotonic() + 10
                while True:
                    term.wait_for_idle(0.02, timeout=10)
                    text = ack.read_text() if ack.exists() else ""
                    if text.startswith(f"{step} "):
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"{widget}: step {step} never drew")
                    time.sleep(0.01)
                term.wait_for_idle(0.15, timeout=10)
                outcomes.append(text.split(" ", 1)[1])
                screens.append(
                    [[_cell(term, r, c) for c in range(COLS)] for r in range(ROWS)]
                )
            control.write_text(str(len(variants)))
            term.wait_for_exit(timeout=10)
        finally:
            term.close()
        if term.stderr.strip():
            raise RuntimeError(f"{widget}:\n{term.stderr}")

    for option, tries in plan.items():
        refused = []
        found = None
        unsettled = 0
        for base, index, value, setup in tries:
            if outcomes[index] != "ok":
                refused.append(f"{value!r}: {outcomes[index]}")
                continue
            if screens[base] != screens[base + 2]:
                unsettled += 1
                if os.environ.get("RECORD_DEBUG"):
                    a, b = screens[base], screens[base + 2]
                    cells = [
                        (r, c, a[r][c], b[r][c])
                        for r in range(ROWS)
                        for c in range(COLS)
                        if a[r][c] != b[r][c]
                    ]
                    print(widget, option, value, len(cells), cells[:3])
                continue
            if screens[index] != screens[base]:
                found = {"kind": "visible", "value": value, "state": setup}
                break
        if found:
            result[option] = found
        elif len(refused) == len(tries):
            result[option] = {"kind": "refused", "tried": refused}
        elif unsettled + len(refused) == len(tries):
            result[option] = {"kind": "unsettled"}
        else:
            result[option] = {
                "kind": "invisible",
                "tried": [t[2] for t in tries],
                "state": tries[0][3],
            }
    return result


def main() -> None:
    os.environ.setdefault("TKCURSES_TEST_TIMEOUT_SCALE", "2")
    widgets = sys.argv[1:] or sorted(BASES)
    with ThreadPoolExecutor(max_workers=6) as pool:
        measured = dict(zip(widgets, pool.map(measure, widgets), strict=True))
    if sys.argv[1:]:
        print(json.dumps(measured, indent=1))
        return
    OUT.write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")
    for widget, options in measured.items():
        kinds: dict[str, int] = {}
        for entry in options.values():
            kind = entry["kind"]  # type: ignore[index]
            kinds[kind] = kinds.get(kind, 0) + 1
        print(widget, kinds)


if __name__ == "__main__":
    main()
