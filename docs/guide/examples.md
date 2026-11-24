# Examples

Sixteen complete programs, each a single file in the
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

## A calculator

Buttons in a grid, each kind in its own colours - digits, operators,
clear and equals - with another colour under the mouse. The rows and
columns all have weight, so the keys grow with the window. Click the keys
or type: the digits and `+ - * /`, Return for the answer, Escape to clear
and BackSpace to take back a digit. The screen is taken after typing
`12+30*2`; the line above the number is the sum so far.

```{tkcurses-example} examples/calculator.py
:size: 30x14
:keys: ["12+30*2"]
```

The window's own `background` shows in the gaps between the keys, and
its `padx` and `pady` are the margin round them. The four columns are one `uniform` group, so they stay
the same width even when a long number asks for more room than the window
has; the display is anchored east, so such a number shows its end.

## A text editor

A Text with a scrollbar, a menu bar, a status line, and files: Open and
Save ask for a name with the file dialog, and quitting with changes not
saved asks first. The menus open with F10, or with Alt and the underlined
letter; `bind_accelerators` makes the shortcuts written in the menus work.
The View menu shows a swatch beside each colour - an entry's `image`, with
`compound="left"` - and tears off: its dashed top line leaves a copy on the
screen that stays after a choice, until Escape. The screen is taken after
typing two lines and pressing F10.

```{tkcurses-example} examples/editor.py
:size: 60x14
:keys: ["Dear Ada,", "<Return>", "<Return>", "The engine works.", "<F10>"]
```

Give it a file to open: `python3 examples/editor.py notes.txt`.

## Notes

A list of notes beside the one being edited, with a search that narrows
the list as you type, a menu, a dialog before deleting, and a file the
notes are saved in half a second after the typing stops. The left pane is
packed and the right gridded, inside a PanedWindow.
[A larger program](larger-program.md) builds it a piece at a time. The
screen is taken after writing two notes.

```{tkcurses-example} examples/notes.py
:size: 60x16
:keys: ["Shopping", "<Tab>", "Milk, eggs and bread.", "<Control-n>", "Ideas", "<Tab>", "A guide to TkCurses."]
```

The notes are kept in `notes.json` beside the program; give another file
to keep them there instead: `python3 examples/notes.py ~/notes.json`.

## A table

A Treeview showing columns, sorted by clicking a column's heading - or
pressing 1, 2, 3 or 4 for it - and in reverse by doing it again. The arrows move through the rows, and
Return shows the chosen one below. The screen is taken after sorting by
the number of moons and choosing the third planet.

```{tkcurses-example} examples/table.py
:size: 52x14
:keys: ["3", "<Down>", "<Down>", "<Return>"]
```

## Layouts

The three geometry managers in one window. The window itself is packed -
a title along the top, a status bar along the bottom, and a PanedWindow
given what is left. The PanedWindow's left pane is packed, its right pane
gridded, and the status bar's three labels are placed by fraction of its
width, at its left edge, its middle and its right edge. Each pane writes
its own size into its heading, so resizing the terminal, or dragging the
sash, shows which widgets take the room.

```{tkcurses-example} examples/layout.py
:size: 60x16
```

The sash moves with the mouse, or with the arrows after one Tab has given
the PanedWindow the focus. The left pane is added with a `width` of 20,
and keeps it as the window grows: a PanedWindow gives the extra room to
its last pane, as Tk's does, unless a pane's `stretch` says otherwise.
In the gridded pane, the column of fields and
the row of the Text have weight 1 and the labels' column has none, so the
fields widen and the labels do not.

## A chart

Rectangles and text on a Canvas, drawn again whenever the window changes
size. Across, a Canvas coordinate is a character cell; down, it is half of
one, which is why the bars can end halfway up a row.

```{tkcurses-example} examples/chart.py
:size: 50x14
```

## A graph

Three curves, each a single line item through a point per column, with
axes, labels and a legend; 1, 2 and 3 hide and show them. Like the chart
it is drawn again whenever the window changes size, and as down is half a
cell, a curve moves in steps of half a row.

```{tkcurses-example} examples/plot.py
:size: 60x16
```

## Shapes

A scene of rectangles, ovals, polygons, a line and text on a Canvas, with
a pond that is an arc cut off by its chord and a cloud that is a
PhotoImage. Each movable shape's items share a tag, so `move` takes the
house - walls, roof and door - as one. Tab chooses a shape and the arrows
move it, or drag one with the mouse. The Reset button is a widget placed on
the canvas with `create_window`, and puts every shape back with `moveto`. The screen is taken after choosing the house and
moving it four cells right.

```{tkcurses-example} examples/shapes.py
:size: 40x14
:keys: ["<Tab>", "<Right>", "<Right>", "<Right>", "<Right>"]
```

The mouse handlers turn the event's position into canvas coordinates with
`canvasx` and `canvasy`, as a Tk program does; here that also turns a row
into the half-row a canvas counts in.

## A recipe card

A Text holding more than text: the bowl is a PhotoImage embedded with
`image_create`, and the Spinbox, the Checkbuttons and the button at the end
are widgets embedded with `window_create`. Each takes one index in the text
and moves with it, as a character would, and a line grows to hold the
tallest thing on it. The Spinbox has the focus, and Up and Down change the
number of people: each quantity is a tagged range, rewritten with `replace`.
Ticking an ingredient greys its line with a tag. The text is read-only, so
the quantities are written with it turned on for a moment. The screen is
taken after asking for five people.

```{tkcurses-example} examples/recipe.py
:size: 60x24
:keys: ["<Up>"]
```

## A picture

The Mandelbrot set, computed into a PhotoImage with `put` and shown in a
Label, at the size of the window: a pixel is one column wide and half a
row tall. + and - zoom, and the arrows move about.

```{tkcurses-example} examples/picture.py
:size: 60x16
```

Give it a PNG, GIF or PPM file and it shows that instead:
`python3 examples/picture.py photo.png`. The program works out the
largest size that keeps the picture's proportions, `resize` resamples it
to that, and `fit_pairs` reduces its colours, only if it has to, to the
colour pairs the terminal has left. A program need not do that last step:
a picture drawn through curses is fitted when it is drawn, and the call is
there to show the choice being made.

## Wallpaper

A Frame's `backgroundimage`: a small pattern drawn into a PhotoImage with
`put`, repeated across the inside of the frame's border while `tile` is on
and centred once while it is off. The label in the corner is the frame's
child, so it is drawn in front of the pattern. Colours puts new colours
into the same image, and the frame repaints itself to follow.

```{tkcurses-example} examples/wallpaper.py
:size: 64x18
```

## A mark book

A Treeview with `selecttype="cell"`, which selects cells instead of rows:
a click takes one, the arrow keys move from cell to cell, Control-click
adds or removes one, and Shift-click takes the rectangle from the last
one chosen. The line underneath adds up the marks each time
`<<TreeviewSelect>>` arrives. Row and Column select a whole row or column
as a rectangle between two corners.

tkinter has no methods for the cell selection, so the program reaches Tk's
`cellselection` command through `tree.tk.call`, as a tkinter program must.
Change the imports to tkinter's and the sizes from characters to pixels,
and it runs under tkinter too.

```{tkcurses-example} examples/marks.py
:size: 60x14
```

## A scrolled pad

A curses program, with nothing of tkinter in it: `tkcurses.curses` runs
it. A pad holds two hundred lines and `refresh` shows the part of it that
fits under the title, moved by the arrow keys, Page Up and Down, Home and
End. Change the import to `import curses` and the standard library runs it
the same way.

```{tkcurses-example} examples/scroller.py
:size: 44x12
:keys: ["<Down>", "<Down>"]
```

## Bar graphs

Three more programs are about `BarGraph`, a widget only TkCurses has:
bars and series, values that change, and axes and number formats. They
are on [their own page](bargraph.md), with what each shows.

## Treemaps

Three more are about `TreeMap`, also a widget only TkCurses has: groups,
values and the legend, acting on what is chosen, and a disk's usage
that follows the disk. They are on
[their own page](treemap.md).

## Line and area charts

Three more are about `XYChart`, also a widget only TkCurses has: a day
of response times with a target and a crosshair, live traffic as
stacked areas the chart fetches itself, and sensors that miss readings. They are on
[their own page](xychart.md).
