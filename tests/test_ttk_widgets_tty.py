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


DOS_BOX = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
ttk.Style(root).theme_use('dos')
ttk.Frame(root, relief='solid', width=8, height=4).place(x=2, y=1)
ttk.Label(root, text='ready').place(x=20, y=0)
root.after(8000, root.quit)
root.mainloop()
"""


def test_the_dos_theme_draws_single_sides_under_double_rails(terminal, tmp_path):
    term = terminal(cols=40, rows=8)
    term.run_source(DOS_BOX, workdir=tmp_path)
    box = {1: "╒══════╕", 2: "│      │", 3: "│      │", 4: "╘══════╛"}

    def drawn(t):
        return all(t.display[row][2:10] == line for row, line in box.items())

    term.wait_for(drawn, message="the dos box")
    for row, line in box.items():
        assert term.display[row][2:10] == line, term.describe()


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


def test_a_click_in_an_editable_comboboxs_text_places_the_cursor(combobox):
    """Tk's ttk::combobox::Press: the text of an editable combobox is an
    entry's, and only the arrow, the border or a read-only combobox opens the
    list. Every click opened it until TkCurses-fgke. The box is at x=2..17,
    rows 2-4: its text is on row 3, the arrow in column 16."""
    combobox.send(b"abcdef")
    combobox.wait_for_text("value='abcdef'")
    combobox.click(5, 3)  # on the 'c'
    combobox.wait_for(lambda t: t.cursor_cell() == (3, 5), message="cursor on c")
    combobox.wait_for_idle()
    assert not any("gamma" in row for row in combobox.display), combobox.describe()


def test_the_arrow_opens_the_list(combobox):
    combobox.click(16, 3)
    combobox.wait_for(
        lambda t: dropdown_values(t) == ["alpha", "beta", "gamma"],
        message="the list, opened by the arrow",
    )


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


TREE_AND_BAR = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
frame = tkcurses.Frame(root)
frame.pack(fill='both', expand=True)
bar = ttk.Scrollbar(frame, orient='vertical')
bar.pack(side='right', fill='y')
tree = ttk.Treeview(frame, show='tree', yscrollcommand=bar.set)
tree.pack(side='left', fill='both', expand=True)
bar.configure(command=tree.yview)
for number in range(30):
    tree.insert('', 'end', text='row %02d' % number)
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def test_a_scrollbar_drives_a_treeview(terminal, tmp_path):
    """The standard pairing works, which is what TkCurses-ale was filed for.

        tree = ttk.Treeview(root, yscrollcommand=bar.set)
        bar = ttk.Scrollbar(root, command=tree.yview)

    The first line raised "unknown option" before this: our Treeview is built on
    Frame, which has no scroll options, so a tree could not be attached to a
    scrollbar at all - the way a tree is used in almost every program that has
    one.

    Driven rather than asserted on numbers, because the two halves can each look
    right alone. A thumb that reports a position while the tree does not move,
    or a tree that scrolls while the thumb sits still, both pass a test of either
    side on its own.

    WAITS FOR THE TREE'S OWN FIRST ROW, not for a sentinel. It used to write
    'ready' at row 13 of 15 and wait for that - inside the area the tree fills,
    so the application's first redraw painted over it. The sentinel was visible
    only between the manual refresh and the first pass of ``mainloop()``: on a
    development machine the harness sampled in between and the test passed six
    times out of six, and on a contended CI runner it did not, and then the wait
    could only fail. It failed Python 3.14 on #118 as "the program exited with
    code 0 while waiting for text 'ready'", which named the quit timer and not
    the cause. A checkpoint has to be something the application itself draws and
    keeps. TkCurses-cvi.
    """
    term = terminal(cols=30, rows=15)
    term.run_source(TREE_AND_BAR, workdir=tmp_path)
    term.wait_for_text("row 00")
    term.wait_for_idle()

    def rows_on_screen():
        return [line for line in term.display if "row " in line]

    def thumb_rows():
        column = next(
            x
            for x in range(term.cols)
            if any(term.char_at(y, x).data == "█" for y in range(term.rows))
        )
        return [y for y in range(term.rows) if term.char_at(y, column).data == "█"]

    first_visible = rows_on_screen()[0]
    thumb_before = thumb_rows()
    assert thumb_before, f"no thumb drawn on the scrollbar\n{term.describe()}"
    assert "row 00" in first_visible, (
        f"the tree did not start at the top: {first_visible!r}"
    )

    # A click low on the trough is a page down, which is the scrollbar asking
    # the tree to move rather than the tree moving itself.
    column = next(
        x
        for x in range(term.cols)
        if any(term.char_at(y, x).data == "█" for y in range(term.rows))
    )
    term.send_mouse(column, max(thumb_before) + 2, action="press")
    term._drain(0.08)
    term.send_mouse(column, max(thumb_before) + 2, action="release")

    # Positive, and never comparing against an empty screen. The first version
    # of this said `"row 00" not in (rows_on_screen() or [""])[0]`, and that
    # fallback made it pass whenever no rows were drawn at all - so disabling
    # yview's moveto and scroll handling left it green. Found by doing exactly
    # that.
    def scrolled_away():
        rows = rows_on_screen()
        return bool(rows) and rows[0] != first_visible

    term.wait_for(
        lambda t: scrolled_away(),
        message="the tree to scroll when the scrollbar is clicked",
    )
    after = rows_on_screen()
    assert after, f"the tree stopped drawing rows entirely\n{term.describe()}"
    assert "row 00" not in after[0], (
        f"the top row is still {after[0]!r} after a page down"
    )
    assert thumb_rows() != thumb_before, (
        "the tree scrolled and the thumb stayed where it was, so the tree is not "
        f"reporting its view back\n{term.describe()}"
    )


BAR_LABEL = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
bar = ttk.Progressbar(root, name='bar', length=20, value=50, text={text!r},
                      anchor={anchor!r}, wraplength={wraplength})
bar.place(x=2, y=2, width=20, height={height})
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


@pytest.mark.parametrize(
    ("anchor", "expected_column"),
    [("w", 2), ("center", 10), ("e", 19)],
)
def test_a_progressbar_draws_its_label_where_the_anchor_says(
    terminal, tmp_path, anchor, expected_column
):
    """On screen, not in the geometry. TkCurses-xe9.1.

    The bar is placed at x=2 and is 20 cells wide, so a three-cell '40%' sits
    at column 2 for 'w', 10 for 'center' and 19 for 'e'.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        BAR_LABEL.format(text="40%", anchor=anchor, wraplength=0, height=1),
        workdir=tmp_path,
    )
    term.wait_for_text("40%")
    term.wait_for_cell(2, expected_column, lambda cell: cell.data == "4")
    assert term.row(2)[expected_column : expected_column + 3] == "40%", (
        f"the label is not at column {expected_column}\n{term.describe()}"
    )


def test_a_progressbar_label_is_drawn_over_the_bar_not_beside_it(terminal, tmp_path):
    """The one place this departs from Tk, and it has to be visible.

    Tk grows the widget to the font's height and draws the bar inside that band
    with the label on top. A cell cannot hold a block glyph and a letter at
    once, so the label replaces the glyphs it covers - and the glyphs either
    side of it must still be there, which is what makes it a bar with a label
    rather than a label on its own.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        BAR_LABEL.format(text="40%", anchor="center", wraplength=0, height=1),
        workdir=tmp_path,
    )
    term.wait_for_text("40%")
    term.wait_for_cell(2, 2, lambda cell: cell.data.strip() != "")
    row = term.row(2)
    assert row[10:13] == "40%", f"the label is missing\n{term.describe()}"
    assert row[2:10].strip(), f"the bar vanished to the left of the label\n{row!r}"
    assert row[13:22].strip(), f"the bar vanished to the right of the label\n{row!r}"


def test_a_progressbar_wraps_its_label_when_wraplength_asks(terminal, tmp_path):
    """wraplength is in cells here, as every screen distance in this library is.

    Measured on Tk 9.0.2: a wraplength shorter than the text really does wrap
    and really does grow the widget - 100x21 pixels became 100x249 at
    wraplength 30. So it is honoured rather than accepted and ignored, and a
    bar given the rows shows the wrapped lines.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        BAR_LABEL.format(text="one two three", anchor="nw", wraplength=7, height=3),
        workdir=tmp_path,
    )
    term.wait_for_text("one two")
    term.wait_for_cell(3, 2, lambda cell: cell.data == "t")
    assert term.row(2)[2:9] == "one two", term.describe()
    assert term.row(3)[2:7] == "three", term.describe()


def test_a_vertical_progressbar_draws_no_label(terminal, tmp_path):
    """Measured: giving a vertical bar text leaves its requested size identical,
    so Tk draws nothing. Inventing a sideways label would be worse than
    matching that."""
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
bar = ttk.Progressbar(root, name='bar', length=6, value=50, text='40%',
                      orient='vertical')
bar.place(x=2, y=2, width=1, height=6)
tkcurses.Label(root, name='mark', text='drawn').place(x=10, y=1)
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("drawn")
    term.wait_for_idle()
    # Every cell of the bar's own column, not the whole string: the bar is one
    # cell wide, so a label drawn into it would show as a single letter and
    # looking for "40%" would miss it. Mutation found that - removing the
    # vertical guard left the first version of this test passing.
    column = [term.char_at(row, 2).data for row in range(2, 8)]
    assert not any(ch.isalnum() for ch in column), (
        f"a vertical bar drew part of its label: {column!r}\n{term.describe()}"
    )
    assert any(ch.strip() for ch in column), (
        f"the vertical bar drew nothing at all: {column!r}\n{term.describe()}"
    )


def test_a_label_wider_than_the_bar_does_not_spill_onto_the_next_row(
    terminal, tmp_path
):
    """Measured on Tk 9.0.2: a label far wider than ``length`` left the bar's
    requested width at ``length``, so it is clipped rather than stretching the
    widget.

    The clipping itself belongs to _write_line, which documents why it must
    exist - curses wraps an over-wide write onto the following row instead of
    dropping it. This checks the behaviour rather than the place, so it holds
    whichever of the two does the cutting.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        BAR_LABEL.format(
            text="a label far wider than twenty cells",
            anchor="w",
            wraplength=0,
            height=1,
        ),
        workdir=tmp_path,
    )
    term.wait_for_text("a label")
    term.wait_for_cell(2, 2, lambda cell: cell.data == "a")
    assert term.row(3).strip() == "", (
        f"the label spilled onto the row below\n{term.describe()}"
    )
    assert term.row(2)[22:].strip() == "", (
        f"the label ran past the bar's own width\n{term.describe()}"
    )


@pytest.mark.parametrize(
    ("anchor", "expected_row"),
    [("nw", 2), ("w", 3), ("sw", 4)],
)
def test_the_anchor_places_the_label_vertically_too(
    terminal, tmp_path, anchor, expected_row
):
    """A bar is one row by default, but nothing stops it being placed taller -
    and then the anchor's vertical half has to mean something.

    Added because mutation found it missing: setting the top row to a constant
    zero left every other label test passing, since they all use a one-row bar
    or a top-anchored one. The bar here is three rows tall at y=2, so 'nw' puts
    the label on row 2, 'w' centres it on row 3 and 'sw' drops it to row 4.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(
        BAR_LABEL.format(text="40%", anchor=anchor, wraplength=0, height=3),
        workdir=tmp_path,
    )
    term.wait_for_text("40%")
    term.wait_for_cell(expected_row, 2, lambda cell: cell.data == "4")
    assert term.row(expected_row)[2:5] == "40%", (
        f"anchor={anchor!r} did not put the label on row {expected_row}"
        f"\n{term.describe()}"
    )


def test_a_right_anchored_label_wider_than_the_bar_still_appears(terminal, tmp_path):
    """It must not vanish, which is what an unclamped column would do.

    With anchor='e' and a label wider than the bar, the anchor's arithmetic puts
    the start at a negative column - and _write_line refuses a write that starts
    off the left edge, so the label disappears entirely rather than being
    clipped. Mutation found it: dropping the max(0, ...) left every other test
    passing.

    WHICH END survives the clip is not pinned here: this library shows the head
    of the string and Tk, anchoring the right edge, would show the tail. That is
    noted on TkCurses-xe9.1 as an unmeasured corner rather than decided quietly.
    """
    term = terminal(cols=40, rows=10)
    term.run_source(
        BAR_LABEL.format(
            text="a label far wider than twenty cells",
            anchor="e",
            wraplength=0,
            height=1,
        ),
        workdir=tmp_path,
    )
    # A LETTER, not merely ink: the bar's own glyphs keep the row non-blank
    # whether the label is drawn or not, so "something is here" cannot tell the
    # two apart. The first version of this asserted exactly that and the
    # mutation walked straight through it - the fourth time on this one issue
    # that an assertion was weaker than it looked.
    term.wait_for(
        lambda t: any(ch.isalpha() for ch in t.row(2)[2:22]),
        message="the clipped label to appear somewhere in the bar",
    )
    assert any(ch.isalpha() for ch in term.row(2)[2:22]), (
        f"the label vanished instead of being clipped\n{term.describe()}"
    )


STRIPED = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, name='tv', columns=('a',), show='headings',
                    striped={striped})
tree.place(x=1, y=1, width=24, height=7)
for n in range(5):
    tree.insert('', 'end', values=('row %d' % n,))
root.update_layout()
root.tk.screen.refresh()
root.after(4000, root.quit)
root.mainloop()
"""


def _row_banding(term):
    """Which of the tree's drawn rows are dim, found rather than hardcoded.

    The rows are located by the text in them: the first version of these tests
    assumed they began at screen row 2 and they begin at 3 - a border, then the
    heading - and only four of the five fit. The striped test failed honestly;
    the UNSTRIPED one passed, because "no row is dim" is satisfied by reading
    blank cells. Finding the rows is what makes both of them mean something.
    """
    banding = []
    for row, line in enumerate(term.display):
        column = line.find("row ")
        if column >= 0:
            banding.append(
                (line[column:].split()[1], term.attrs_at(row, column)["dim"])
            )
    return banding


def test_a_striped_treeview_tints_alternate_rows_on_screen(terminal, tmp_path):
    """TkCurses-xe9.4, checked where it matters.

    Odd rows of what is on screen are dim, so the banding does not crawl as the
    tree scrolls.
    """
    term = terminal(cols=40, rows=12)
    term.run_source(STRIPED.format(striped=1), workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_text("row 3")
    term.wait_for_idle()
    banding = _row_banding(term)
    assert len(banding) >= 4, f"only found {banding}\n{term.describe()}"
    assert [dim for _label, dim in banding] == [
        offset % 2 == 1 for offset in range(len(banding))
    ], f"the stripe does not alternate: {banding}\n{term.describe()}"


def test_an_unstriped_treeview_tints_nothing(terminal, tmp_path):
    """The control. Without it the test above would pass on a tree that drew
    every row dim - and this one has to find the rows too, or it passes by
    reading blank cells."""
    term = terminal(cols=40, rows=12)
    term.run_source(STRIPED.format(striped=0), workdir=tmp_path)
    term.wait_for_text("row 0")
    term.wait_for_text("row 3")
    term.wait_for_idle()
    banding = _row_banding(term)
    assert len(banding) >= 4, f"only found {banding}\n{term.describe()}"
    assert not any(dim for _label, dim in banding), (
        f"rows were tinted with striped off: {banding}\n{term.describe()}"
    )


# ------------------------------- Treeview scrolled sideways (TkCurses-xe9.6)

WIDE_TREE = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, columns=("a", "b", "c"), height=3)
tree.column("#0", width=8, stretch=False)
for name in ("a", "b", "c"):
    tree.column(name, width=7, stretch=False)
tree.heading("#0", text="Name")
tree.heading("a", text="Alpha")
tree.heading("b", text="Beta")
tree.heading("c", text="Omega")
tree.insert("", "end", text="first", values=("a1", "b1", "zz9"))
tree.place(x=0, y=0, width=22, height=6)
root.bind("x", lambda event: tree.xview_moveto(1.0))
root.after(8000, root.quit)
root.mainloop()
"""


def test_scrolling_sideways_brings_the_last_column_into_view(terminal, tmp_path):
    """The heading and the row move together, and the tree column goes."""
    term = terminal(cols=30, rows=8)
    term.run_source(WIDE_TREE, workdir=tmp_path)
    term.wait_for(
        lambda t: "Name" in t.row(1) and "Omega" not in t.row(1),
        message="the tree drawn at the left",
    )
    term.send_keys("x")
    term.wait_for(
        lambda t: "Omega" in t.row(1) and "Name" not in t.row(1) and "zz9" in t.row(2),
        message="the heading and the row scrolled to the last column",
    )
    assert _column_of(term, 1, "Omega") == _column_of(term, 2, "zz9"), "\n".join(
        term.display
    )


def _column_of(term, row, text):
    return term.row(row).index(text)


TITLED_TREE = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, titleitems=10)
for n in range(20):
    tree.insert("", "end", text="row%d" % n)
tree.place(x=0, y=0, width=20, height=7)
root.after(8000, root.quit)
root.mainloop()
"""


def test_titles_that_overflow_stop_at_the_border(terminal, tmp_path):
    """Four rows of room and ten titles: the fifth must not cover the border."""
    term = terminal(cols=30, rows=10)
    term.run_source(TITLED_TREE, workdir=tmp_path)
    term.wait_for(
        lambda t: "row3" in t.row(5) and t.row(6)[1:5] not in ("", "    "),
        message="four title rows, then the bottom border",
    )
    assert "row4" not in term.row(6), "\n".join(term.display)


# ------------------------------------ Treeview's mouse wheel (TkCurses-94fn)

WHEELED_TREE = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tree = ttk.Treeview(root, columns=("a", "b", "c"))
tree.column("#0", width=8, stretch=False)
for name in ("a", "b", "c"):
    tree.column(name, width=7, stretch=False)
tree.heading("#0", text="ABCDEFGH")
for n in range(20):
    tree.insert("", "end", text="row%d" % n)
tree.place(x=0, y=0, width=22, height=7)
root.after(8000, root.quit)
root.mainloop()
"""


def test_the_wheel_scrolls_a_tree_both_ways(terminal, tmp_path):
    """Down three rows a notch, and with Shift three cells sideways."""
    term = terminal(cols=30, rows=10)
    term.run_source(WHEELED_TREE, workdir=tmp_path)
    term.wait_for(
        lambda t: "ABCDEFGH" in t.row(1) and "row0" in t.row(2),
        message="the tree at the top left",
    )
    term.send_mouse(3, 3, button=5)
    term.wait_for(
        lambda t: "row3" in t.row(2) and "ABCDEFGH" in t.row(1),
        message="three rows down, nothing sideways",
    )
    term.send_mouse(3, 3, button=5, shift=True)
    term.wait_for(
        lambda t: t.row(1)[1:6] == "DEFGH" and "w3" in t.row(2),
        message="three cells sideways, nothing down",
    )


def test_a_packed_treeview_with_no_size_draws(terminal, tmp_path):
    """It asked for no width and drew nothing; it now asks for its columns
    and rows as Tk's does."""
    source = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
tv = ttk.Treeview(root, height=2)
tv.heading('#0', text='Name')
tv.insert('', 'end', text='Alpha')
tv.pack()
root.after(4000, root.quit)
root.mainloop()
"""
    term = terminal(cols=40, rows=12)
    term.run_source(source, workdir=tmp_path)
    # Both in one wait: the heading arriving does not promise the row has.
    term.wait_for(
        lambda t: (
            any("Name" in line for line in t.display)
            and any("Alpha" in line for line in t.display)
        ),
        message="the heading and the row",
    )


def test_a_notebook_packed_plainly_draws_its_tabs_and_page(terminal, tmp_path):
    """It asked for no size and drew nothing, tabs included."""
    source = """
import tkcurses
from tkcurses import ttk

root = tkcurses.Tk()
book = ttk.Notebook(root)
book.add(ttk.Label(book, text='first page'), text='One')
book.add(ttk.Label(book, text='page'), text='Two')
book.pack()
root.after(4000, root.quit)
root.mainloop()
"""
    term = terminal(cols=40, rows=12)
    term.run_source(source, workdir=tmp_path)
    term.wait_for(
        lambda t: (
            any("One" in line and "Two" in line for line in t.display)
            and any("first page" in line for line in t.display)
        ),
        message="the tabs and the page",
    )
    # The page fills the frame under the tabs: on the row right below its
    # top edge, from border to border. It was placed a cell further in and
    # two smaller each way, which at this size left it no rows at all.
    top = next(r for r, line in enumerate(term.display) if "┌┘" in line)
    page = term.display[top + 1].strip()
    assert page.startswith("│") and page.endswith("│"), term.describe()
    assert "first page" in page, term.describe()
