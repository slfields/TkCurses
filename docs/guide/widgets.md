# Common widgets

TkCurses has every widget tkinter has. This page is about the ones nearly
every program uses: what each is for, how they are usually combined, and a
short program for each group. It ends with a small complete application
that puts several of them together. Every widget's full list of options and
methods is in the [API reference](../reference/index.md).

## The widgets at a glance

| Widget | What it is for |
|---|---|
| `Label` | Text, or a picture, that the user reads. |
| `Button` | Something the user presses to make something happen. |
| `Entry` | A one-line field to type into. |
| `Text` | Many lines of text to read or edit, with colours and styles. |
| `Checkbutton` | A choice that is on or off. |
| `Radiobutton` | One choice from a few, shown all at once. |
| `Spinbox` | A number, or one of a list, stepped up and down. |
| `Scale` | A number chosen by sliding. |
| `Listbox` | A list of lines to choose one or several from. |
| `ttk.Combobox` | One choice from a list that drops down. |
| `ttk.Treeview` | A table, or a tree of rows that open and close. |
| `ttk.Progressbar` | How far through something a program is. |
| `Scrollbar` | Scrolls a `Listbox`, `Text`, `Canvas` or `Treeview` that does not fit. |
| `Frame`, `LabelFrame` | A container that groups other widgets, plain or with a titled border. |
| `ttk.Notebook` | Pages of widgets, one shown at a time, chosen by tabs. |
| `PanedWindow` | Two or more panes side by side, with a divider the user can move. |
| `Menu` | A menu bar, and the menus that drop down from it. |
| `Canvas` | A surface to draw lines, shapes and text on. |

## Classic and themed widgets

There are two sets of widgets, as in tkinter. The **classic** ones are in
`tkcurses` itself: `tk.Button`, `tk.Entry`. The **themed** ones are in
`tkcurses.ttk`, and are drawn by a *style* that can be changed for every
widget of a kind at once, rather than one widget at a time. Most widgets
come in both sets, and a few are themed only - `Combobox`, `Notebook`,
`Treeview`, `Progressbar`.

The two mix freely in one program, and the examples here use whichever is
simpler. The one thing to know is that in tkinter the themed widgets take
their colours from the style and refuse options like `bg` and `fg`.
TkCurses accepts them, but a program that uses them then runs only on
TkCurses; [`ttk`](../reference/ttk/index.md) in the reference explains
styles.

## Getting input

A form for printing something, with one widget of each common kind. Each
control is attached to a variable, and every variable calls `show`
whenever it changes, so the line at the bottom follows every change.

% expect: 1 x A4, mono, both sides, for Ada

```python
import tkcurses as tk
from tkcurses import ttk

root = tk.Tk()
name = tk.StringVar(value="Ada")
copies = tk.IntVar(value=1)
duplex = tk.BooleanVar(value=True)
colour = tk.StringVar(value="mono")
paper = tk.StringVar(value="A4")

form = tk.Frame(root)
form.pack(fill="x")
form.columnconfigure(1, weight=1)
tk.Label(form, text="Name").grid(row=0, column=0, sticky="w")
tk.Entry(form, textvariable=name).grid(row=0, column=1, sticky="ew")
tk.Label(form, text="Copies").grid(row=1, column=0, sticky="w")
tk.Spinbox(form, from_=1, to=99, textvariable=copies, width=4).grid(
    row=1, column=1, sticky="w"
)
tk.Label(form, text="Paper").grid(row=2, column=0, sticky="w")
ttk.Combobox(
    form, textvariable=paper, values=["A4", "Letter", "Legal"],
    state="readonly", width=8,
).grid(row=2, column=1, sticky="w")

tk.Checkbutton(root, text="Both sides", variable=duplex).pack(anchor="w")
for value in ("mono", "colour"):
    tk.Radiobutton(root, text=value.title(), variable=colour, value=value).pack(
        anchor="w"
    )

summary = tk.Label(root, anchor="w")
summary.pack(fill="x")

def show(*args):
    sides = "both sides" if duplex.get() else "one side"
    summary.configure(
        text=f"{copies.get()} x {paper.get()}, {colour.get()}, {sides}, for {name.get()}"
    )

for variable in (name, copies, duplex, colour, paper):
    variable.trace_add("write", show)
show()
root.mainloop()
```

- **`Entry`** holds one line. Attach it to a `StringVar` with
  `textvariable`, or use its own `get()`, `insert()` and `delete()`. An
  entry for a password takes `show="*"`.
- **`Spinbox`** steps through numbers from `from_` to `to` with the arrow
  keys or by clicking its arrows, or through `values=[...]`. The trailing
  underscore in `from_` is because `from` is a Python keyword.
- **`ttk.Combobox`** drops a list down for one choice. With
  `state="readonly"` only the listed values can be chosen; without it the
  user may type something else.
- **`Checkbutton`** sets its variable to on or off - `True` or `False` for
  a `BooleanVar`.
- **`Radiobutton`s** that share a variable are one group: choosing one sets
  the variable to its `value`, and the others show as not chosen.

`Scale` is the remaining one: a number chosen by sliding, from `from_` to
`to`, attached to an `IntVar` or `DoubleVar` with `variable`.

## Lists and tables

A `Listbox` shows lines to choose from. `selectmode="extended"` lets the
user choose several, with Shift and Control as in a file manager, and the
list sends the virtual event `<<ListboxSelect>>` whenever the choice
changes. A `ttk.Treeview` shows rows with several columns, and rows inside
rows if they are given a parent.

% expect: Pick some fruit

```python
import tkcurses as tk
from tkcurses import ttk

root = tk.Tk()
fruit = tk.Listbox(root, height=5, selectmode="extended")
for name in ("apple", "banana", "cherry", "damson", "elderberry", "fig"):
    fruit.insert("end", name)
fruit.pack(fill="x")

table = ttk.Treeview(root, columns=("price",), height=3)
table.heading("#0", text="Fruit")
table.heading("price", text="Price")
for name, price in (("apple", "0.30"), ("banana", "0.25"), ("cherry", "2.10")):
    table.insert("", "end", text=name, values=(price,))
table.pack(fill="x")

chosen = tk.Label(root, text="Pick some fruit")
chosen.pack()

def picked(event):
    names = [fruit.get(index) for index in fruit.curselection()]
    chosen.configure(text=", ".join(names) or "Pick some fruit")

fruit.bind("<<ListboxSelect>>", picked)
root.mainloop()
```

A list counts its lines from 0, and `curselection()` answers the
positions of the chosen ones; `get(index)` answers a line's text. The
[table example](examples.md#a-table) sorts a `Treeview` by a column when
its heading is clicked.

## Text, and scrolling

A `Text` holds as many lines as it is given, and can be edited or, with
`state="disabled"`, only read. **Tags** name ranges of text so that they
can be given colours and styles. A `Scrollbar` is connected to the widget
it scrolls in both directions: the bar's `command` moves the text, and the
text's `yscrollcommand` moves the bar when the text scrolls by itself.

% expect: step 21: failed

```python
import tkcurses as tk

root = tk.Tk()
log = tk.Text(root, wrap="word", height=8)
bar = tk.Scrollbar(root, command=log.yview)
log.configure(yscrollcommand=bar.set)
bar.pack(side="right", fill="y")
log.pack(side="left", fill="both", expand=True)

log.tag_configure("error", foreground="red")
log.tag_configure("heading", foreground="yellow", underline=True)
log.insert("end", "Build log\n", "heading")
for step in range(1, 21):
    log.insert("end", f"step {step}: ok\n")
log.insert("end", "step 21: failed\n", "error")
log.see("end")
log.configure(state="disabled")
root.mainloop()
```

Positions in a `Text` are strings, `"line.column"`, with lines counted
from 1 and columns from 0: `"1.0"` is the start, `"end"` the end, and
`"insert"` wherever the cursor is. `see("end")` scrolls the end into
view. The same scrollbar connection works for a `Listbox`, a `Canvas` and
a `Treeview`, and for sideways scrolling with `xview` and
`xscrollcommand`.

A `Text` can hold widgets and pictures as well as text: `window_create`
puts a widget at an index and `image_create` an image. Each takes one
index and moves with the text, and a line grows to hold the tallest thing
on it. The [recipe card](examples.md#a-recipe-card) has a Spinbox,
Checkbuttons, a button and a picture in its text.

## Grouping: frames, tabs and panes

The containers hold other widgets. A `Frame` is invisible unless it is
given a border or a background; a `LabelFrame` has a border with a title
in it; a `ttk.Notebook` shows one of several pages at a time, chosen by
its tabs.

% expect: Ada Lovelace

```python
import tkcurses as tk
from tkcurses import ttk

root = tk.Tk()
tabs = ttk.Notebook(root)
tabs.pack(fill="both", expand=True)

general = tk.Frame(tabs)
tabs.add(general, text="General")
who = tk.LabelFrame(general, text="Who")
who.pack(fill="x")
tk.Label(who, text="Ada Lovelace").pack(anchor="w")
where = tk.LabelFrame(general, text="Where")
where.pack(fill="x")
tk.Label(where, text="London").pack(anchor="w")

advanced = tk.Frame(tabs)
tabs.add(advanced, text="Advanced")
tk.Label(advanced, text="Nothing to change here").pack()

progress = ttk.Progressbar(root, maximum=100, value=40)
progress.pack(fill="x")
root.mainloop()
```

Each page of a notebook is a widget - usually a frame - whose parent is the
notebook, added with `tabs.add(page, text=...)`. A `PanedWindow` is added
to in the same way, and shows its panes side by side, or one above the
other, with a divider between them that the user can move;
[Layouts](examples.md#layouts) in the examples has one.

The progress bar at the bottom shows `value` out of `maximum`. Set
`value` as work goes on - from an `after` callback, so that the screen is
drawn in between.

## Menus and dialogs

A menu bar is a `Menu` given to the root window as its `menu` option, and
each menu that drops down from it is another `Menu`, added with
`add_cascade`. **F10** opens the menu bar, as does Alt with the letter a
menu's `underline` marks.

% expect: F10 opens the menus

```python
import tkcurses as tk
from tkcurses import messagebox, simpledialog

root = tk.Tk()
shown = tk.Label(root, text="F10 opens the menus")
shown.pack(expand=True)

def rename():
    name = simpledialog.askstring("Rename", "New name:", parent=root)
    if name:
        shown.configure(text=f"Renamed to {name}")

def about():
    messagebox.showinfo("About", "A menu, two dialogs", parent=root)

menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="Rename...", underline=0, command=rename)
file_menu.add_separator()
file_menu.add_command(label="Quit", underline=0, command=root.destroy)
menubar.add_cascade(label="File", underline=0, menu=file_menu)
help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(label="About", underline=0, command=about)
menubar.add_cascade(label="Help", underline=0, menu=help_menu)
root.configure(menu=menubar)
root.mainloop()
```

`tearoff=0` leaves out the dashed line that tkinter puts at the top of a
menu by default. An entry's `accelerator` shows a shortcut beside it, such
as `"Ctrl+S"`; it only shows it, and the shortcut itself is a binding -
the notes program in [A larger program](larger-program.md) makes both.

The **dialogs** ask a question and wait for the answer. Each is one call,
and the program carries on with the answer once the user has given it:

| Call | Asks for |
|---|---|
| `messagebox.showinfo`, `showwarning`, `showerror` | Nothing - a message and an OK button. |
| `messagebox.askyesno`, `askokcancel`, `askyesnocancel` | A decision: `True`, `False`, or `None` for cancel. |
| `simpledialog.askstring`, `askinteger`, `askfloat` | A value, or `None` if cancelled. |
| `filedialog.askopenfilename`, `asksaveasfilename` | A file name, or `""` if cancelled. |
| `colorchooser.askcolor` | A colour. |

## Drawing: Canvas and images

A `Canvas` is a surface to draw on. Each `create_` method adds an *item* -
a line, rectangle, oval, arc, polygon, text, image or bitmap, or a widget
placed with `create_window` - and answers its id, which can later be
moved, changed or deleted. Across the canvas a unit is one cell;
down it, a unit is half a cell, so that shapes come out the right way up
and round things look round.

% expect: drawn in half-cells

```python
import tkcurses as tk

root = tk.Tk()
canvas = tk.Canvas(root, bg="black")
canvas.pack(fill="both", expand=True)
canvas.create_rectangle(2, 2, 16, 10, outline="white", fill="navy")
canvas.create_oval(22, 2, 36, 16, outline="gold", fill="orange")
canvas.create_line(2, 16, 10, 12, 18, 16, fill="lime green")
canvas.create_text(2, 20, text="drawn in half-cells", anchor="w", fill="white")
root.mainloop()
```

Items can be given *tags*, as text can, and bound to: `canvas.tag_bind
("house", "<Button-1>", ...)` hears a click on any item tagged `house`.
A `PhotoImage` reads a PNG, GIF or netpbm file, and is shown in a `Label`
with `image=`, or a `Button`. The [examples](examples.md) have a graph, a
drawing whose shapes can be dragged, and a picture.

## A complete program

Several of those together: a to-do list. Type a task and press Return to
add it; pick one in the list and press **Done** to take it off.

% expect: To do

```python
import tkcurses as tk

root = tk.Tk()
root.title("To do")

tk.Label(root, text="To do", fg="yellow").pack()

entry_row = tk.Frame(root)
entry_row.pack(fill="x")
task = tk.StringVar()
field = tk.Entry(entry_row, textvariable=task)
field.pack(side="left", fill="x", expand=True)

def add(event=None):
    text = task.get().strip()
    if text:
        tasks.insert("end", text)
        task.set("")

tk.Button(entry_row, text="Add", command=add).pack(side="left")
field.bind("<Return>", add)

def done():
    for index in reversed(tasks.curselection()):
        tasks.delete(index)

buttons = tk.Frame(root)
buttons.pack(side="bottom", fill="x")
tk.Button(buttons, text="Done", command=done).pack(side="left")
tk.Button(buttons, text="Quit", command=root.destroy).pack(side="right")

list_row = tk.Frame(root)
list_row.pack(fill="both", expand=True)
tasks = tk.Listbox(list_row)
tasks.pack(side="left", fill="both", expand=True)
bar = tk.Scrollbar(list_row, command=tasks.yview)
bar.pack(side="right", fill="y")
tasks.configure(yscrollcommand=bar.set)

field.focus_set()
root.mainloop()
```

A few things to notice:

- **`expand=True`** gives the list the room left over, so it grows with
  the terminal while the rows of buttons keep their height.
- **The row of buttons is packed before the list**, against the bottom.
  `pack` squeezes whatever was packed last, so in a short terminal the list
  loses a few lines rather than the buttons disappearing.
- **`add` is used twice**: by the button, which calls it with no
  arguments, and by the binding on Return, which passes an event. The
  `event=None` lets one function serve both.
- **Deleting goes from the end backwards**, so that the positions still to
  delete stay where they were.

## Where next

**[A larger program](larger-program.md)** builds a notes application with
a menu, two panes, a search, a dialog and a file, and explains each piece.
