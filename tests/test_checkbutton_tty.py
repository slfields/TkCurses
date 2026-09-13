"""What a Checkbutton looks like and how it answers a real terminal."""

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


def test_an_unticked_checkbutton_shows_an_empty_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Checkbutton(root, text='Wrap').place(x=2, y=2)"),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")


def test_a_ticked_checkbutton_shows_a_cross(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c = tkcurses.Checkbutton(root, text='Wrap')\nc.place(x=2, y=2)\nc.select()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[x] Wrap")


def test_a_click_ticks_the_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Checkbutton(root, text='Wrap').place(x=2, y=2)"),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")
    # Angle brackets, not square: the click takes the focus as well as
    # ticking the box, and focus is what changes the brackets.
    term.click(3, 2)
    term.wait_for_text("<x> Wrap")


def test_a_second_click_unticks_it(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program("tkcurses.Checkbutton(root, text='Wrap').place(x=2, y=2)"),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")
    term.click(3, 2)
    term.wait_for_text("<x> Wrap")
    term.click(3, 2)
    term.wait_for_text("< > Wrap")


def test_focus_is_visible(terminal, tmp_path):
    """A checkbutton nobody can see the focus on cannot be used by keyboard."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c = tkcurses.Checkbutton(root, text='Wrap')\n"
            "c.place(x=2, y=2)\n"
            "root.after(100, c.focus_set)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")
    term.wait_for_text("< > Wrap")


def test_the_box_does_not_change_width_when_focused(terminal, tmp_path):
    """Angle brackets rather than a marker, so nothing moves under the hand."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c = tkcurses.Checkbutton(root, text='Wrap')\n"
            "c.place(x=2, y=2)\n"
            "def report(row):\n"
            "    root.update_layout()\n"
            "    buffer.write(row, 0, 'w%s=%s' % (row, c.winfo_width()))\n"
            "    root.tk.screen.refresh()\n"
            "report(9)\n"
            "root.after(100, lambda: (c.focus_set(), report(10)))"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("w9=8")
    term.wait_for_text("w10=8")


def test_space_ticks_the_focused_box(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c = tkcurses.Checkbutton(root, text='Wrap')\n"
            "c.place(x=2, y=2)\n"
            "c.focus_set()"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("< > Wrap")
    term.send(b" ")
    term.wait_for_text("<x> Wrap")


def test_two_boxes_over_one_variable_move_together(terminal, tmp_path):
    """The whole reason the value lives in a Variable and not in the widget."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.IntVar(root, 0)\n"
            "tkcurses.Checkbutton(root, text='One', variable=v).place(x=2, y=2)\n"
            "tkcurses.Checkbutton(root, text='Two', variable=v).place(x=2, y=4)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] One")
    term.wait_for_text("[ ] Two")
    # Only the one clicked on has the focus, so only its brackets change;
    # both are ticked, which is the thing being tested.
    term.click(3, 2)
    term.wait_for_text("<x> One")
    term.wait_for_text("[x] Two")


def test_a_label_over_the_same_variable_follows_a_click(terminal, tmp_path):
    """What a person sees in UAT: clicking here changes something over there."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.StringVar(root, 'off')\n"
            "tkcurses.Checkbutton(\n"
            "    root, text='Wrap', variable=v, onvalue='on', offvalue='off'\n"
            ").place(x=2, y=2)\n"
            "tkcurses.Label(root, textvariable=v, width=8).place(x=2, y=5)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("off")
    term.click(3, 2)
    term.wait_for_text("on")


def test_the_third_state_is_drawn(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "v = tkcurses.StringVar(root, 'some')\n"
            "tkcurses.Checkbutton(\n"
            "    root, text='Read-only', variable=v, tristatevalue='some'\n"
            ").place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[-] Read-only")


def test_a_boxless_checkbutton_draws_no_brackets(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Checkbutton(\n"
            "    root, text='Bold', indicatoron=False\n"
            ").place(x=2, y=2)\n"
            "buffer.write(11, 0, 'drawn')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("drawn")
    term.wait_for_idle()
    assert "[" not in "\n".join(term.display)


def test_a_boxless_checkbutton_reverses_while_it_is_on(terminal, tmp_path):
    """With no box the text has to carry the state itself."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "c = tkcurses.Checkbutton(root, text='Bold', indicatoron=False)\n"
            "c.place(x=2, y=2)\n"
            "buffer.write(11, 0, 'drawn')\n"
            "root.after(100, c.select)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("Bold")
    row = next(i for i, line in enumerate(term.display) if "Bold" in line)
    column = term.display[row].index("Bold")
    term.wait_for(
        lambda t: t.attrs_at(row, column)["reverse"], message="the reversed text"
    )


def test_a_disabled_checkbutton_does_not_answer_a_click(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "tkcurses.Checkbutton(\n"
            "    root, text='Wrap', state='disabled'\n"
            ").place(x=2, y=2)"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")
    term.click(3, 2)
    term.wait_for_idle()
    assert "[x]" not in "\n".join(term.display)


def test_checkbuttons_pack_into_a_frame(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        program(
            "f = tkcurses.Frame(root, relief='solid')\n"
            "f.pack(fill='both', expand=True)\n"
            "for word in ('Wrap', 'Bold'):\n"
            "    tkcurses.Checkbutton(f, text=word).pack(anchor='w')"
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("[ ] Wrap")
    term.wait_for_text("[ ] Bold")
