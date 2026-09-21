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

"""The themed widgets on a real terminal.

The claim this cycle makes is that appearance lives in one place and every
widget follows it. That is not something a unit test can show: it has to be
a screen that changes when the database does.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty

THEMED = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
style = ttk.Style(root)
names = list(style.theme_names())

for index in range(3):
    ttk.Separator(root, name='sep%d' % index).place(x=10, y=1 + index, width=20)
bar = ttk.Progressbar(root, name='bar', length=20, value=50)
bar.place(x=10, y=5)
ttk.Sizegrip(root, name='grip').place(x=34, y=7)


def announce():
    buffer.write(0, 0, ('theme=%s' % style.theme_use()).ljust(20))
    root.tk.screen.refresh()


def cycle(event):
    style.theme_use(names[(names.index(style.theme_use()) + 1) % len(names)])
    announce()


def fill(event):
    bar.configure(value=100)
    root.tk.screen.refresh()


root.bind('<Key-n>', cycle)
root.bind('<Key-f>', fill)
root.update_layout()
announce()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.fixture
def themed(terminal, tmp_path):
    term = terminal(cols=56, rows=10)
    term.run_source(THEMED, workdir=tmp_path)
    term.wait_for_text("theme=default")
    term.wait_for_idle()
    return term


def separator_row(term):
    """The first separator's row, as the characters it was drawn with."""
    return term.display[1][10:30]


def test_the_separators_draw_with_the_default_theme(themed):
    assert separator_row(themed) == "─" * 20, themed.describe()


def test_switching_the_theme_redraws_what_is_already_on_screen(themed):
    """The claim the whole cycle rests on, and the thing a unit test cannot
    show: appearance lives in one place, and changing it changes what is
    already drawn. A theme that only took effect on the next repaint would
    be a theme nobody could demonstrate.
    """
    themed.send(b"n")
    themed.wait_for_text("theme=ascii")
    themed.wait_for_idle()
    assert separator_row(themed) == "-" * 20, themed.describe()


def test_every_theme_draws_its_own_rail(themed):
    seen = {}
    for _ in range(6):
        name = themed.row(0).strip().split("=")[1]
        seen[name] = separator_row(themed)[0]
        themed.send(b"n")
        themed.wait_for_idle()
    assert seen["default"] == "─"
    assert seen["ascii"] == "-"
    assert seen["dos"] == "═"
    assert seen["double"] == "═"
    assert seen["minimal"] == " "


def test_one_theme_change_reaches_every_widget_of_a_class(themed):
    """Three separators, one theme_use, all three follow."""
    themed.send(b"n")
    themed.wait_for_text("theme=ascii")
    themed.wait_for_idle()
    for row in (1, 2, 3):
        assert themed.display[row][10:30] == "-" * 20, themed.describe()


def test_a_progressbar_shows_how_far_along_it_is(themed):
    row = themed.display[5][10:30]
    assert row.count("█") == 10, themed.describe()
    assert row.count("░") == 10, themed.describe()


def test_a_progressbar_fills_when_its_value_does(themed):
    themed.send(b"f")
    themed.wait_for(
        lambda t: t.display[5][10:30].count("█") == 20,
        message="the bar to fill",
    )


def test_the_sizegrip_marks_the_corner(themed):
    assert "◢" in "\n".join(themed.display), themed.describe()


RESTYLE = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
style = ttk.Style(root)
bars = [ttk.Progressbar(root, name='b%d' % i, length=18, value=60) for i in range(3)]
for index, bar in enumerate(bars):
    bar.place(x=8, y=1 + index)


def restyle(event):
    style.configure('TProgressbar', foreground='green')
    style.map('TProgressbar', foreground=[('disabled', 'red')])
    buffer.write(0, 0, 'restyled  ')
    root.tk.screen.refresh()


def disable(event):
    bars[1].state(['disabled'])
    bars[1]._redraw()
    buffer.write(0, 0, 'disabled  ')
    root.tk.screen.refresh()


root.bind('<Key-r>', restyle)
root.bind('<Key-d>', disable)
buffer.write(0, 0, 'plain     ')
root.update_layout()
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


@pytest.fixture
def bars(terminal, tmp_path):
    term = terminal(cols=40, rows=6)
    term.run_source(RESTYLE, workdir=tmp_path)
    term.wait_for_text("plain")
    term.wait_for_idle()
    return term


def colours(term):
    """The foreground of each of the three bars."""
    return [term.attrs_at(row, 9)["fg"] for row in (1, 2, 3)]


def test_one_configure_reaches_every_widget_of_the_class(bars):
    """The claim the cycle rests on, on a screen: one call naming a class,
    and three widgets nobody touched individually change together.

    This needed Style.configure to repaint. It did not at first - the
    database changed and nothing already drawn moved, because a widget
    resolves its appearance when it paints.
    """
    assert colours(bars) == ["white"] * 3
    bars.send(b"r")
    bars.wait_for_text("restyled")
    bars.wait_for_idle()
    assert colours(bars) == ["green"] * 3, bars.describe()


def test_a_mapped_state_reaches_only_the_widget_in_it(bars):
    """The other half: a map entry is per widget, not per class."""
    bars.send(b"r")
    bars.wait_for_text("restyled")
    bars.wait_for_idle()
    bars.send(b"d")
    bars.wait_for_text("disabled")
    bars.wait_for_idle()
    assert colours(bars) == ["green", "red", "green"], bars.describe()


GRIP = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
top = tkcurses.Toplevel(root)
top.geometry('20x6+3+2')
{lock}
tkcurses.Label(top, text='window').place(x=1, y=1)
ttk.Sizegrip(top, name='grip').place(relx=1.0, x=-1, rely=1.0, y=-1)
root.update_layout()
buffer.write(0, 0, 'ready')
root.tk.screen.refresh()
root.after(8000, root.quit)
root.mainloop()
"""


def window_size(term):
    """The drawn window's size, read off the screen.

    Read rather than reported, because a programmatic geometry() does not
    fire <Configure> here - TkCurses-b5o, found while writing this - so a
    program cannot tell you its own new size as it changes. What a person
    sees is the better assertion anyway.
    """
    rows = [
        index for index, line in enumerate(term.display) if "┌" in line or "└" in line
    ]
    top_row = term.display[rows[0]]
    return (
        top_row.index("┐") - top_row.index("┌") + 1,
        rows[-1] - rows[0] + 1,
    )


def drag_the_grip(term, across, down):
    """Press the grip and pull it, as a hand would."""
    row = next(index for index, line in enumerate(term.display) if "◢" in line)
    column = term.display[row].index("◢")
    term.send_mouse(column, row, action="press")
    term._drain(0.08)
    for step in range(1, max(abs(across), abs(down)) + 1):
        term.send_mouse(
            column + min(step, across), row + min(step, down), action="move"
        )
        term._drain(0.05)
    term.send_mouse(column + across, row + down, action="release")
    term._drain(0.08)
    term.wait_for_idle()


def grip_window(terminal, tmp_path, lock=""):
    term = terminal(cols=50, rows=16)
    term.run_source(GRIP.format(lock=lock), workdir=tmp_path)
    term.wait_for_text("ready")
    term.wait_for_idle()
    assert window_size(term) == (20, 6), term.describe()
    return term


def test_dragging_the_grip_resizes_the_window(terminal, tmp_path):
    """The thing the first version of this widget said was impossible.

    It is not. A Toplevel here is the library's own window - it has a
    geometry, a place in the z-order, and it redraws when it changes size -
    so dragging its corner is a real operation. Only the root is different,
    because the root's size is the terminal's.
    """
    term = grip_window(terminal, tmp_path)
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (28, 10), term.describe()


def test_the_grip_stays_in_the_corner_it_moved(terminal, tmp_path):
    term = grip_window(terminal, tmp_path)
    drag_the_grip(term, 8, 4)
    row = next(index for index, line in enumerate(term.display) if "◢" in line)
    bottom = max(index for index, line in enumerate(term.display) if "└" in line)
    assert row == bottom - 1, term.describe()


def test_a_window_locked_across_grows_only_downwards(terminal, tmp_path):
    """wm_resizable is honoured per axis, as Tk honours it."""
    term = grip_window(terminal, tmp_path, lock="top.wm_resizable(False, True)")
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (20, 10), term.describe()


def test_a_locked_window_does_not_move_at_all(terminal, tmp_path):
    term = grip_window(terminal, tmp_path, lock="top.wm_resizable(False, False)")
    drag_the_grip(term, 8, 4)
    assert window_size(term) == (20, 6), term.describe()


# ======================================================================
# Combobox
# ======================================================================

COMBOBOX = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

box = ttk.Combobox(root, name='cb', values=['alpha', 'beta', 'gamma'])
box.place(x=2, y=2, width=16)
picked = []


def report(event=None):
    buffer.write(0, 0, ('value=%r picked=%s' % (box.get(), picked)).ljust(44))
    root.tk.screen.refresh()


box.bind('<<ComboboxSelected>>', lambda event: (picked.append(box.get()), report()))
# After the editing binding rather than before it: a widget binding runs
# ahead of the class tag, so reporting here directly would print the text as
# it was before the key landed.
box.bind('<Any-Key>', lambda event: root.after(0, report), add='+')
box.focus_set()
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""

#: Where the dropdown's values land: the combobox occupies rows 2-4 and the
#: list is bordered, as Tk's popdown is, so the first value is on row 6.
#: Named for its widget, because this module holds several widgets' row
#: constants and a bare FIRST_ROW silently shadowed another one - every
#: combobox test then measured the treeview's rows.
COMBO_FIRST_ROW = 6


@pytest.fixture
def combobox(terminal, tmp_path):
    term = terminal(cols=46, rows=16)
    term.run_source(COMBOBOX, workdir=tmp_path)
    term.wait_for_text("value=''")
    term.wait_for_idle()
    return term


def dropdown_values(term, count=3):
    """The dropdown's values, read from inside its border.

    Stripping whitespace alone stopped being enough when the list gained a
    border, as Tk's popdown has: the box characters come back with the text.
    """
    rows = term.display[COMBO_FIRST_ROW : COMBO_FIRST_ROW + count]
    return [row.strip().strip("│").strip() for row in rows]


def test_a_combobox_draws_an_arrow(combobox):
    """The mark that says there is a list behind it, where ttk draws a
    downarrow."""
    assert any("▾" in row for row in combobox.display), combobox.describe()


def test_clicking_opens_the_list(combobox):
    combobox.click(4, 2)
    combobox.wait_for_idle()

    assert dropdown_values(combobox) == ["alpha", "beta", "gamma"], combobox.describe()


def test_clicking_again_closes_it(combobox):
    combobox.click(4, 2)
    combobox.wait_for_idle()
    combobox.click(4, 2)
    combobox.wait_for_idle()

    assert not any("gamma" in row for row in combobox.display), combobox.describe()


def test_picking_a_row_takes_its_value(combobox):
    """And the row picked is the row under the pointer - which it was not
    until TkCurses-9hr, when nearest() wanted a screen row and every click
    answered with the first item.
    """
    combobox.click(4, 2)
    combobox.wait_for_idle()

    combobox.click(4, COMBO_FIRST_ROW + 1)

    combobox.wait_for_text("value='beta'")


def test_picking_fires_the_selected_event(combobox):
    """The gesture that does fire it, where set() and current() do not."""
    combobox.click(4, 2)
    combobox.wait_for_idle()

    combobox.click(4, COMBO_FIRST_ROW)

    combobox.wait_for_text("picked=['alpha']")


def test_picking_closes_the_list(combobox):
    combobox.click(4, 2)
    combobox.wait_for_idle()
    combobox.click(4, COMBO_FIRST_ROW)
    combobox.wait_for_text("value='alpha'")
    combobox.wait_for_idle()

    assert not any("gamma" in row for row in combobox.display), combobox.describe()


def test_escape_closes_the_list_without_choosing(combobox):
    combobox.click(4, 2)
    combobox.wait_for_idle()

    combobox.send(b"\x1b")
    combobox.wait_for_idle()

    assert not any("gamma" in row for row in combobox.display), combobox.describe()
    assert "value=''" in combobox.row(0), combobox.describe()


def test_the_down_key_opens_the_list(combobox):
    # The application cursor-key form. curses turns keypad mode on, so a
    # terminal sends ESC O B rather than ESC [ B - measured: ESC [ B arrives
    # as three separate keys, Escape then '[' then 'B', and two of them land
    # in the field as text.
    combobox.send(b"\x1bOB")
    combobox.wait_for_idle()

    assert dropdown_values(combobox) == ["alpha", "beta", "gamma"], combobox.describe()


def test_a_combobox_can_be_typed_into(combobox):
    """Regression. A combobox reports TCombobox, so nothing bound to Entry
    reaches it - and it took every keystroke and did nothing with them, the
    text never changing. Entry's editing keys are registered again under
    TCombobox; this is the check that they arrived.
    """
    combobox.send(b"hi")

    combobox.wait_for_text("value='hi'")


def test_clicking_outside_the_list_closes_it_without_choosing(combobox):
    """The dropdown holds the grab, so a click anywhere else is routed to it
    rather than to whatever was under the pointer. That is what lets a
    second click on the combobox close the list - the combobox never sees
    that click.
    """
    combobox.click(4, 2)
    combobox.wait_for_idle()

    combobox.click(40, 14)
    combobox.wait_for_idle()

    assert not any("gamma" in row for row in combobox.display), combobox.describe()
    assert "value=''" in combobox.row(0), combobox.describe()


# ======================================================================
# Notebook
# ======================================================================

NOTEBOOK = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

book = ttk.Notebook(root, name='nb')
book.place(x=1, y=2, width=34, height=11)
for index, word in enumerate(('One', 'Two', 'Three')):
    page = tkcurses.Frame(book, name='p%d' % index)
    tkcurses.Label(page, text='PAGE-%s' % word.upper(), anchor='w').place(
        x=1, y=1, width=14)
    book.add(page, text=word)


def report(event=None):
    buffer.write(0, 0, ('current=%d' % book.index('current')).ljust(30))
    root.tk.screen.refresh()


book.bind('<<NotebookTabChanged>>', report)
book.focus_set()
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""

#: The strip is three rows: the tops of the tab boxes, their labels, and the
#: page frame's top edge that the selected tab opens into. The notebook is
#: placed at y=2, so those are rows 2, 3 and 4.
STRIP = 2
TAB_LABELS = STRIP + 1
FRAME_TOP = STRIP + 2


@pytest.fixture
def notebook(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(NOTEBOOK, workdir=tmp_path)
    term.wait_for_text("current=0")
    term.wait_for_idle()
    return term


def pages_on_screen(term):
    """Which pages are drawn. Should always be exactly one."""
    return [
        word
        for word in ("PAGE-ONE", "PAGE-TWO", "PAGE-THREE")
        if any(word in row for row in term.display)
    ]


def test_the_tab_strip_names_every_page(notebook):
    strip = notebook.display[TAB_LABELS]
    assert "One" in strip and "Two" in strip and "Three" in strip


def test_the_tabs_are_boxes_standing_on_the_frame(notebook):
    """The shape that makes it read as a notebook rather than a row of
    words on a line: a box per tab, and the page frame beneath them.
    """
    assert notebook.display[STRIP].strip().startswith("┌"), notebook.describe()
    assert notebook.display[TAB_LABELS].strip().startswith("│"), notebook.describe()
    assert notebook.display[FRAME_TOP].strip().startswith("┌"), notebook.describe()


def test_the_selected_tab_is_open_into_its_page(notebook):
    """Tk's mark for "this one", and the only one that does not depend on
    colour: the selected tab has no bottom edge, so it and its page are one
    space rather than two things near each other.
    """
    frame = notebook.display[FRAME_TOP]
    first = notebook.display[TAB_LABELS].index("One")

    # Under the first tab's label, the frame row is open - spaces, not rule.
    assert frame[first] == " ", notebook.describe()
    # Under a tab that is not selected, it is not.
    third = notebook.display[TAB_LABELS].index("Three")
    assert frame[third] == "─", notebook.describe()


def test_only_one_page_is_drawn(notebook):
    """Regression, TkCurses-mlw.

    Unmapping a container hid its own panel and left every widget inside it
    exactly where it was, so the notebook drew two pages at once - the
    selected one and whatever had been put away last. It took three goes to
    find, because the page frames had no window of their own by then: their
    labels did, handed out by a later layout pass that never asked whether
    the container could be seen.
    """
    assert pages_on_screen(notebook) == ["PAGE-ONE"], notebook.describe()


def test_the_border_survives_every_tab_switch(notebook):
    """Regression, reported from a UAT run: selecting the second tab ate the
    right and bottom border, and it stayed eaten whichever tab was chosen
    afterwards.

    The page was being placed with arithmetic on the notebook's own rect,
    read in ``_settle`` - which runs before the notebook has been laid out,
    so the width was zero and the page was placed zero cells wide. The
    layout engine resolves ``relwidth`` at the moment it knows the answer;
    ``_settle`` does not know it yet.
    """

    # Derived from the strip rather than written down: the notebook is
    # placed at x=1 and 34 wide, so its right edge is column 34, and a
    # hard-coded column is one fixture change away from testing nothing.
    right_edge = notebook.display[FRAME_TOP].rstrip().rindex("┐")
    bottom_row = STRIP + 10

    def intact():
        rows = notebook.display
        bottom = rows[bottom_row].strip()
        right = [rows[row][right_edge] for row in range(FRAME_TOP + 1, bottom_row)]
        return bottom.startswith("└") and bottom.endswith("┘") and set(right) == {"│"}

    assert intact(), notebook.describe()

    for column in (12, 3, 20, 12, 3):
        notebook.click(column, TAB_LABELS)
        notebook.wait_for_idle()
        assert intact(), notebook.describe()


def test_clicking_a_tab_shows_its_page(notebook):
    notebook.click(12, TAB_LABELS)

    notebook.wait_for_text("current=1")
    notebook.wait_for_idle()
    assert pages_on_screen(notebook) == ["PAGE-TWO"], notebook.describe()


def test_the_right_key_moves_to_the_next_tab(notebook):
    # ESC O C, the application cursor-key form - see the Combobox note.
    notebook.send(b"\x1bOC")

    notebook.wait_for_text("current=1")
    notebook.wait_for_idle()
    assert pages_on_screen(notebook) == ["PAGE-TWO"], notebook.describe()


def test_the_left_key_moves_back(notebook):
    notebook.send(b"\x1bOC")
    notebook.wait_for_text("current=1")
    notebook.wait_for_idle()

    notebook.send(b"\x1bOD")

    notebook.wait_for_text("current=0")


def test_choosing_another_tab_moves_the_opening(notebook):
    """The label row does not change when a tab is chosen - the labels are
    the same - so what has to move is the opening in the frame beneath them.
    """
    before = notebook.display[FRAME_TOP]

    notebook.click(12, TAB_LABELS)
    notebook.wait_for_text("current=1")
    notebook.wait_for_idle()

    assert notebook.display[FRAME_TOP] != before, notebook.describe()


# ======================================================================
# Treeview
# ======================================================================

TREEVIEW = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

tv = ttk.Treeview(root, name='tv', columns=('size',))
tv.place(x=1, y=2, width=36, height=9)
tv.heading('#0', text='Name')
tv.heading('size', text='Size')
tv.column('size', width=6)
alpha = tv.insert('', 'end', text='Alpha', values=('10',))
tv.insert(alpha, 'end', text='Child-A', values=('1',))
tv.insert(alpha, 'end', text='Child-B', values=('2',))
tv.insert('', 'end', text='Beta', values=('20',))


def report(event=None):
    buffer.write(0, 0, ('sel=%s' % [tv.item(i, 'text') for i in tv.selection()]).ljust(40))
    root.tk.screen.refresh()


tv.bind('<<TreeviewSelect>>', report)
tv.focus_set()
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""

#: The treeview is placed at y=2 and draws a border, so the heading row is 3
#: and the first item row is 4.
HEADING_ROW = 3
TREE_FIRST_ROW = 4


@pytest.fixture
def treeview(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(TREEVIEW, workdir=tmp_path)
    term.wait_for_text("sel=[]")
    term.wait_for_idle()
    return term


def test_the_headings_are_drawn(treeview):
    row = treeview.display[HEADING_ROW]
    assert "Name" in row and "Size" in row, treeview.describe()


def test_a_closed_branch_hides_its_children(treeview):
    assert not any("Child-A" in row for row in treeview.display), treeview.describe()


def test_a_branch_is_marked_as_openable(treeview):
    assert "▸" in treeview.display[TREE_FIRST_ROW], treeview.describe()


def test_clicking_the_marker_opens_the_branch(treeview):
    treeview.click(2, TREE_FIRST_ROW)
    treeview.wait_for_idle()

    assert "▾" in treeview.display[TREE_FIRST_ROW], treeview.describe()
    assert any("Child-A" in row for row in treeview.display), treeview.describe()


def test_the_children_are_indented(treeview):
    treeview.click(2, TREE_FIRST_ROW)
    treeview.wait_for_idle()

    parent = treeview.display[TREE_FIRST_ROW].index("Alpha")
    child = treeview.display[TREE_FIRST_ROW + 1].index("Child-A")
    assert child > parent, treeview.describe()


def test_the_columns_line_up_under_their_headings(treeview):
    """The tree column is padded to its width, or every row starts its
    values wherever its own text happened to end.
    """
    heading = treeview.display[HEADING_ROW].index("Size")
    value = treeview.display[TREE_FIRST_ROW].index("10")
    assert value == heading, treeview.describe()


def test_clicking_a_row_selects_it(treeview):
    treeview.click(2, TREE_FIRST_ROW)
    treeview.wait_for_idle()

    treeview.click(8, TREE_FIRST_ROW + 1)

    treeview.wait_for_text("sel=['Child-A']")


def test_the_down_key_moves_the_selection(treeview):
    treeview.click(8, TREE_FIRST_ROW)
    treeview.wait_for_text("sel=['Alpha']")
    treeview.wait_for_idle()

    treeview.send(b"\x1bOB")

    treeview.wait_for_text("sel=['Beta']")


# ======================================================================
# LabeledScale
# ======================================================================

LABELED = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

widget = ttk.LabeledScale(root, from_=0, to=10)
widget.place(x=2, y=3, width=20, height=2)


def report(event=None):
    buffer.write(0, 0, ('value=%s' % widget.value).ljust(30))
    root.tk.screen.refresh()


# Reported from the variable both halves share, which is the only thing
# that knows the value has moved - the label is told by the same trace.
widget._variable.trace_add('write', lambda *_: report())
widget.scale.focus_set()
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""

#: The label is on the first of the widget's two rows, the scale below it.
LABEL_ROW = 3
SCALE_ROW = 4


@pytest.fixture
def labeled(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(LABELED, workdir=tmp_path)
    term.wait_for_text("value=0")
    term.wait_for_idle()
    return term


def test_both_halves_are_drawn(labeled):
    assert "0" in labeled.display[LABEL_ROW], labeled.describe()
    assert labeled.display[SCALE_ROW].strip(), labeled.describe()


def test_dragging_the_scale_moves_the_label(labeled):
    """The claim the widget exists to make, on a real screen: the number
    beside the scale is the scale's, and it follows.
    """
    labeled.click(18, SCALE_ROW)

    labeled.wait_for(lambda t: "value=0" not in t.row(0), message="the value to move")
    labeled.wait_for_idle()
    shown = labeled.row(0).split("=")[1].strip()
    assert shown in labeled.display[LABEL_ROW], labeled.describe()


# ======================================================================
# OptionMenu
# ======================================================================

OPTIONS = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
buffer = root.tk.screen.buffer

chosen = tkcurses.StringVar(root)
picked = []
def chose(value):
    # Reported from here as well as from the trace: the variable is written
    # first and the command runs after it, so a screen painted by the trace
    # alone shows the value already moved and the command not yet called.
    picked.append(value)
    report()


widget = ttk.OptionMenu(
    root, chosen, 'beta', 'alpha', 'beta', 'gamma',
    name='om', command=chose)
widget.place(x=2, y=2, width=16)


def report(*args):
    buffer.write(0, 0, ('value=%r picked=%s' % (chosen.get(), picked)).ljust(44))
    root.tk.screen.refresh()


chosen.trace_add('write', report)
widget.focus_set()
root.update_layout()
report()
root.after(8000, root.quit)
root.mainloop()
"""

#: The row the button's text lands on: placed at y=2, with a border.
BUTTON_ROW = 3


@pytest.fixture
def options(terminal, tmp_path):
    term = terminal(cols=44, rows=14)
    term.run_source(OPTIONS, workdir=tmp_path)
    term.wait_for_text("value='beta'")
    term.wait_for_idle()
    return term


def test_the_button_shows_the_current_value(options):
    assert "beta" in options.display[BUTTON_ROW], options.describe()


def test_clicking_posts_the_menu(options):
    options.click(4, BUTTON_ROW)
    options.wait_for_idle()

    assert any("alpha" in row for row in options.display), options.describe()
    assert any("gamma" in row for row in options.display), options.describe()


def test_choosing_an_entry_changes_the_button_and_calls_the_command(options):
    options.click(4, BUTTON_ROW)
    options.wait_for_idle()
    row = next(index for index, line in enumerate(options.display) if "gamma" in line)

    options.click(6, row)

    options.wait_for_text("value='gamma'")
    options.wait_for_idle()
    assert "picked=['gamma']" in options.row(0), options.describe()
    assert "gamma" in options.display[BUTTON_ROW], options.describe()
