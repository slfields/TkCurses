"""What a Scrollbar looks like beside the thing it scrolls."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


PAIR = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
frame = tkcurses.Frame(root, relief='solid')
frame.pack(fill='both', expand=True)
lb = tkcurses.Listbox(frame, width=16, height=5)
lb.pack(side='left', fill='both')
bar = tkcurses.Scrollbar(frame, command=lb.yview)
bar.pack(side='left', fill='y')
lb.configure(yscrollcommand=bar.set)
lb.insert('end', *['row %d' % n for n in range(20)])
root.update_layout()
root.tk.screen.refresh()
buffer.write(11, 0, 'ready')
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_scrollbar_draws_arrows_and_a_thumb(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    # "ready" is written to the buffer; the widgets' panels are composited by
    # the loop afterwards, so waiting for content rather than for the marker.
    term.wait_for_text("row 0")
    term.wait_for_idle()
    screen = "\n".join(term.display)
    assert "▲" in screen
    assert "▼" in screen
    assert "█" in screen
    assert "░" in screen


def test_scrolling_the_list_moves_the_thumb(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")

    def thumb_rows():
        return [i for i, line in enumerate(term.display) if "█" in line]

    term.wait_for_idle()
    before = thumb_rows()
    assert before, "the thumb should be drawn to begin with"
    term.click(4, 2)
    # End rather than a run of Downs: a few rows of twenty move the thumb by
    # less than a cell, so the assertion would depend on the arithmetic
    # rounding the right way.
    term.send_keys("<End>")
    term.wait_for(lambda t: thumb_rows() != before, message="the thumb to move")


def test_clicking_the_scrollbar_scrolls_the_list(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(PAIR, workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_idle()
    arrow_row = next(i for i, line in enumerate(term.display) if "▼" in line)
    arrow_col = term.display[arrow_row].index("▼")
    for _ in range(3):
        term.click(arrow_col, arrow_row)
    term.wait_for(
        lambda t: "row 0" not in "\n".join(t.display), message="the list to scroll"
    )
