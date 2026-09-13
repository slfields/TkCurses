"""What a Listbox looks like and how it answers a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


def program(body: str) -> str:
    return f"""
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
{body}
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


LIST = (
    "lb = tkcurses.Listbox(root, width=16, height=5)\n"
    "lb.place(x=1, y=1)\n"
    "lb.insert('end', 'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta')\n"
)


def test_a_listbox_shows_its_items(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST), workdir=tmp_path)
    term.wait_for_text("alpha")
    term.wait_for_text("beta")


def test_only_as_many_items_as_fit_are_shown(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "buffer.write(10, 0, 'ready')"), workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()
    assert "zeta" not in "\n".join(term.display)


def test_the_selected_item_is_marked(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "lb.selection_set(1)"), workdir=tmp_path)
    term.wait_for(lambda t: "▶" in "\n".join(t.display), message="the marker")
    row = next(i for i, line in enumerate(term.display) if "▶" in line)
    assert "beta" in term.display[row]
    assert "◀" in term.display[row]


def test_the_arrows_move_the_selection(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(LIST + "lb.focus_set()\nlb.selection_set(0)\nlb.activate(0)"),
        workdir=tmp_path,
    )
    term.wait_for(lambda t: "▶" in "\n".join(t.display), message="the marker")
    term.send_keys("<Down>")
    term.wait_for(
        lambda t: any("▶" in line and "beta" in line for line in t.display),
        message="the selection on beta",
    )


def test_scrolling_past_the_bottom_brings_later_items_in(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "lb.focus_set()\nlb.activate(0)"), workdir=tmp_path)
    term.wait_for_text("alpha")
    for _ in range(6):
        term.send_keys("<Down>")
    term.wait_for_text("zeta")


def test_clicking_selects_the_row_under_the_pointer(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(program(LIST + "buffer.write(10, 0, 'ready')"), workdir=tmp_path)
    term.wait_for_text("ready")
    # Row 2 on screen is the second item: the box starts at y=1 and has a border.
    term.click(4, 3)
    term.wait_for(
        lambda t: any("▶" in line and "beta" in line for line in t.display),
        message="beta selected",
    )


def test_a_selection_change_fires_the_virtual_event(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            LIST + "def chose(event):\n"
            "    buffer.write(11, 0, 'chose %s' % (lb.curselection(),))\n"
            "    root.tk.screen.refresh()\n"
            "lb.bind('<<ListboxSelect>>', chose)\n"
            "buffer.write(10, 0, 'ready')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.click(4, 2)
    term.wait_for_text("chose (0,)")


def test_a_listbox_packs_with_the_other_widgets(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "tkcurses.Label(f, text='Pick one').pack(side='top')\n"
            "lb = tkcurses.Listbox(f, width=14, height=4)\n"
            "lb.pack(side='top')\n"
            "lb.insert('end', 'one', 'two', 'three')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Pick one")
    term.wait_for_text("three")
