# Examples

Six complete programs, each a single file in the
[`examples`](https://github.com/slfields/TkCurses/tree/master/examples)
directory. Run one from a checkout with:

```console
$ python3 examples/editor.py
```

Every picture on this page is the program's own screen, taken when the
documentation was built by running the file in a terminal and pressing the
keys the caption names. If a change to TkCurses altered what a program
draws, the picture changed with it; if it broke the program, the
documentation would not build.

The files carry the licence notice that every file of TkCurses does; the
page leaves it out.

## Hello

The smallest program: a window with a label and a button. Tab reaches the
button and Return presses it, or click it.

```{tkcurses-example} examples/hello.py
:size: 40x6
```

## A form

Labelled fields laid out with `grid`, a read-only Combobox, radio buttons,
a check box, and a check before the form is accepted. The screen is
taken after typing a name, an email address and pressing **Create**.

```{tkcurses-example} examples/form.py
:size: 50x20
:keys: ["Ada Lovelace", "<Tab>", "ada@example.org", "<Tab>", "<Tab>", "<Tab>", "<Tab>", "<Tab>", "<Tab>", "<Return>"]
```

Tab and Shift-Tab move through the fields in the order they were made,
each radio button and the check box a stop of its own, as in Tk; space
chooses the one with the focus.

## A to-do list

A Listbox and an Entry, with keys bound on each: Return adds the task
typed, and in the list space marks a task done and Delete removes it. The
screen is taken after adding a task and marking another done.

```{tkcurses-example} examples/todo.py
:size: 40x14
:keys: ["Buy bread", "<Return>", "<Tab>", "<Down>", " "]
```

## A text editor

A Text with a scrollbar, a menu bar, a status line, and files: Open and
Save ask for a name with the file dialog, and quitting with changes not
saved asks first. The menus open with F10, or with Alt and the underlined
letter; `bind_accelerators` makes the shortcuts written in the menus work.
The screen is taken after typing two lines and pressing F10.

```{tkcurses-example} examples/editor.py
:size: 60x14
:keys: ["Dear Ada,", "<Return>", "<Return>", "The engine works.", "<F10>"]
```

Give it a file to open: `python3 examples/editor.py notes.txt`.

## A table

A Treeview showing columns, sorted by pressing 1, 2, 3 or 4 for a column -
and in reverse by pressing it again. The arrows move through the rows, and
Return shows the chosen one below. The screen is taken after sorting by
the number of moons and choosing the third planet.

```{tkcurses-example} examples/table.py
:size: 52x14
:keys: ["3", "<Down>", "<Down>", "<Return>"]
```

## A chart

Rectangles and text on a Canvas, drawn again whenever the window changes
size. Across, a Canvas coordinate is a character cell; down, it is half of
one, which is why the bars can end halfway up a row.

```{tkcurses-example} examples/chart.py
:size: 50x14
```
