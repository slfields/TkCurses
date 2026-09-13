"""What a Menu looks like and how it answers a real terminal."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tty


MENUBAR = """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
wrap = tkcurses.IntVar(root, 1)
size = tkcurses.StringVar(root, 'medium')

bar = tkcurses.Menu(root)
files = tkcurses.Menu(bar)
files.add_command(label='New', accelerator='Ctrl+N', underline=0)
files.add_command(label='Open...', accelerator='Ctrl+O', underline=0)
files.add_separator()
files.add_command(
    label='Quit', accelerator='Ctrl+Q', underline=0,
    command=lambda: (buffer.write(15, 0, 'quit chosen'), root.tk.screen.refresh()),
)
bar.add_cascade(label='File', menu=files, underline=0)

view = tkcurses.Menu(bar)
view.add_checkbutton(label='Wrap lines', variable=wrap)
view.add_separator()
for word in ('small', 'medium', 'large'):
    view.add_radiobutton(label=word.title(), variable=size, value=word)
deeper = tkcurses.Menu(view)
deeper.add_command(label='Deeper one')
view.add_cascade(label='More', menu=deeper)
bar.add_cascade(label='View', menu=view, underline=0)

root.configure(menu=bar)
tkcurses.Label(root, text='window contents').pack(pady=1)
root.update_layout()
root.tk.screen.refresh()
root.after(5000, root.quit)
root.mainloop()
"""


def test_a_menubar_is_drawn_across_the_top(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    assert "File" in term.display[0]
    assert "View" in term.display[0]


def test_the_window_contents_start_below_the_bar(terminal, tmp_path):
    """The bar's row is not the children's to use."""
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("window contents")
    row = next(i for i, line in enumerate(term.display) if "window contents" in line)
    assert row > 0


def test_clicking_the_bar_posts_the_dropdown(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Open...")


def test_a_dropdown_shows_its_accelerators_on_the_right(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Ctrl+N")
    row = next(i for i, line in enumerate(term.display) if "New" in line)
    assert term.display[row].index("Ctrl+N") > term.display[row].index("New")


def test_a_dropdown_covers_the_window_beneath_it(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("window contents")
    term.click(2, 0)
    term.wait_for_text("Open...")
    term.wait_for_idle()
    row = next(i for i, line in enumerate(term.display) if "Open..." in line)
    assert "window" not in term.display[row][:20]


def test_escape_dismisses_a_dropdown(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Open...")
    term.send_keys("<Escape>")
    term.wait_for(
        lambda t: "Open..." not in "\n".join(t.display), message="it to close"
    )


def test_clicking_away_dismisses_a_dropdown(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Open...")
    term.click(45, 12)
    term.wait_for(
        lambda t: "Open..." not in "\n".join(t.display), message="it to close"
    )


def test_choosing_an_entry_runs_it_and_closes_the_menu(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Quit")
    row = next(i for i, line in enumerate(term.display) if "Quit" in line)
    term.click(3, row)
    term.wait_for_text("quit chosen")
    term.wait_for_idle()
    assert "Ctrl+Q" not in "\n".join(term.display)


def test_right_moves_along_the_bar(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Open...")
    term.send_keys("<Right>")
    term.wait_for_text("Wrap lines")


def test_the_arrows_move_the_highlight(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("New")
    row = next(i for i, line in enumerate(term.display) if "New" in line)
    column = term.display[row].index("New")
    term.send_keys("<Down>")
    term.wait_for(
        lambda t: t.attrs_at(row, column)["reverse"], message="the active entry"
    )


def test_a_checkbutton_entry_shows_its_state(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("View")
    term.click(9, 0)
    term.wait_for_text("[x] Wrap lines")


def test_a_radiobutton_group_shows_one_choice(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("View")
    term.click(9, 0)
    term.wait_for_text("(•) Medium")
    term.wait_for_idle()
    display = "\n".join(term.display)
    assert "( ) Small" in display
    assert "( ) Large" in display


def test_choosing_a_radiobutton_moves_the_dot(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("View")
    term.click(9, 0)
    term.wait_for_text("( ) Large")
    row = next(i for i, line in enumerate(term.display) if "Large" in line)
    term.click(12, row)
    term.wait_for(
        lambda t: "Large" not in "\n".join(t.display), message="the menu to close"
    )
    term.click(9, 0)
    term.wait_for_text("(•) Large")


def test_a_cascade_shows_an_arrow_and_opens_beside_itself(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("View")
    term.click(9, 0)
    term.wait_for_text("More")
    row = next(i for i, line in enumerate(term.display) if "More" in line)
    assert "▸" in term.display[row]
    term.click(12, row)
    term.wait_for_text("Deeper one")


def test_a_mnemonic_chooses_an_entry(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.click(2, 0)
    term.wait_for_text("Quit")
    term.send(b"q")
    term.wait_for_text("quit chosen")


def test_a_popup_is_posted_where_it_is_asked(terminal, tmp_path):
    term = terminal(cols=40, rows=14)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
popup = tkcurses.Menu(root)
popup.add_command(label='Cut')
popup.add_command(label='Copy')
popup.add_command(label='Paste')
root.bind('<Button-3>', lambda e: popup.tk_popup(e.x_root, e.y_root))
buffer.write(13, 0, 'ready')
root.tk.screen.refresh()
root.after(5000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_mouse(4, 3, button=3, action="press")
    term._drain(0.08)
    term.send_mouse(4, 3, button=3, action="release")
    term.wait_for_text("Copy")
    row = next(i for i, line in enumerate(term.display) if "Cut" in line)
    assert row >= 3


def test_a_popup_near_an_edge_is_flipped_rather_than_cut_off(terminal, tmp_path):
    """A menu clipped at the screen edge cannot be read or reached."""
    term = terminal(cols=40, rows=14)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
popup = tkcurses.Menu(root)
for word in ('Cut', 'Copy', 'Paste', 'Delete', 'Select all'):
    popup.add_command(label=word)
root.bind('<Button-3>', lambda e: popup.tk_popup(e.x_root, e.y_root))
buffer.write(13, 0, 'ready')
root.tk.screen.refresh()
root.after(5000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("ready")
    term.send_mouse(38, 12, button=3, action="press")
    term._drain(0.08)
    term.send_mouse(38, 12, button=3, action="release")
    term.wait_for_text("Select all")
    term.wait_for_idle()
    # Every entry is on screen: none of them ran off the right or the bottom.
    for word in ("Cut", "Copy", "Paste", "Delete", "Select all"):
        assert word in "\n".join(term.display)


def test_a_menu_taller_than_the_screen_scrolls(terminal, tmp_path):
    term = terminal(cols=40, rows=12)
    term.run_source(
        """
import tkcurses

root = tkcurses.Tk()
buffer = root.tk.screen.buffer
popup = tkcurses.Menu(root)
for n in range(40):
    popup.add_command(label='Item %02d' % n)
popup.post(0, 0)
root.after(5000, root.quit)
root.mainloop()
""",
        workdir=tmp_path,
    )
    term.wait_for_text("Item 00")
    term.send_keys("<End>")
    term.wait_for_text("Item 39")
    term.wait_for_idle()
    assert "Item 00" not in "\n".join(term.display)


def test_a_menu_survives_the_terminal_shrinking(terminal, tmp_path):
    term = terminal(cols=52, rows=16)
    term.run_source(MENUBAR, workdir=tmp_path)
    term.wait_for_text("File")
    term.resize(cols=30, rows=10)
    term.wait_for_text("File")
    assert "Traceback" not in term.stderr
