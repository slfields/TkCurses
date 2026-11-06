# Introduction

This guide is for anyone who has written some Python and wants a program
with an interface: buttons, fields to type into, lists to choose from. It
assumes nothing about tkinter or any other toolkit. By the end you will
have written a small, complete application.

## What TkCurses is

Most programs that run in a terminal talk to you in lines of text: they
print, you type, they print again. A program with a *user interface*
instead puts things on the screen that stay there - a field you can type
into, a button you can press, a list you can scroll through - and reacts
to whatever you do to them, in whatever order you do it.

A **GUI toolkit** is a library that provides those things. Python ships
with one called *tkinter*, which draws them in windows on a desktop.
TkCurses provides the same things, with the same names and the same way of
using them, but draws them with text inside the terminal you are already
in. That means a TkCurses program also works over SSH, on a server with no
desktop, and in a container.

Because the two speak the same language, everything you learn here also
applies to tkinter, and a great deal written about tkinter applies here.

## Before you start

You need Python 3.10 or later on Linux or macOS, and a terminal. Install
TkCurses with `pip`:

```bash
pip install "tkcurses @ git+https://github.com/slfields/TkCurses@v0.3.0rc1"
```

Every example below is a complete program. Save it to a file, say
`hello.py`, and run it with `python3 hello.py` from a terminal. Press
**Ctrl-C** to close any of them.

## Your first program

% expect: Hello from the terminal

```python
import tkcurses as tk

root = tk.Tk()
greeting = tk.Label(root, text="Hello from the terminal")
greeting.pack()
root.mainloop()
```

Four things happen here, and every TkCurses program does all four.

1. **`import tkcurses as tk`** brings in the library under the short name
   `tk`. Programs written for tkinter say `import tkinter as tk`, which is
   why the examples use the same name.
2. **`root = tk.Tk()`** creates the *root window*. In TkCurses it is the
   whole terminal screen, and everything else goes inside it.
3. **`tk.Label(root, ...)`** creates a *widget*: one element of the
   interface, here a piece of text. The first argument says which window
   or widget it goes inside - its *parent*. Then **`.pack()`** puts it on
   the screen. A widget that has not been packed, or placed some other way
   (see [Arranging widgets](#arranging-widgets)), exists but is not shown.
4. **`root.mainloop()`** hands control to TkCurses. From here on it draws
   the screen, waits for keys and mouse clicks, and calls your code when
   something happens. It returns when the root window is closed.

That last step is the big difference from a program that prints and reads.
You do not write a loop asking "what did the user do?". You describe the
interface, say which of your functions to run for which events, and let
`mainloop` do the asking.

## Widgets and options

Every widget is created the same way: the class, the parent, then
*options* as keyword arguments. Options set what the widget shows and how.

% expect: Status: ready

```python
import tkcurses as tk

root = tk.Tk()
title = tk.Label(root, text="Inventory", fg="yellow")
title.pack()
status = tk.Label(root, text="Status: ready", fg="black", bg="green")
status.pack()
root.mainloop()
```

`fg` and `bg` are the foreground (text) and background colours. Colours
are shown as well as your terminal allows, and a terminal with no colour
shows the text without them.

An option can be read and changed after the widget exists:

```python
status.configure(text="Status: saving")   # change one or more options
status["text"] = "Status: saved"          # the same, one option at a time
print(status.cget("text"))                # read one back
```

The widgets you will use most are:

| Widget | What it is |
|---|---|
| `Label` | Text that the user reads. |
| `Button` | Text the user presses to make something happen. |
| `Entry` | A one-line field the user types into. |
| `Text` | A multi-line field, an editor. |
| `Checkbutton` | A box that is ticked or not. |
| `Radiobutton` | One of a group of choices, of which only one is chosen. |
| `Listbox` | A list of lines the user picks from. |
| `Scrollbar` | Scrolls a `Listbox`, `Text` or `Canvas` that does not fit. |
| `Frame` | An empty area that holds other widgets, to group them. |
| `Menu` | A menu bar, or a menu that drops down from one. |

The [API reference](../reference/index.md) lists them all, with every
option each one takes.

## Making something happen

A `Button` takes a `command` option: a function for TkCurses to call when
the button is pressed. Pass the function itself - `command=add_one`, not
`command=add_one()`, which would call it once immediately and pass what it
returned.

% expect: Pressed 0 times

```python
import tkcurses as tk

presses = 0

def add_one():
    global presses
    presses += 1
    counter.configure(text=f"Pressed {presses} times")

root = tk.Tk()
counter = tk.Label(root, text="Pressed 0 times")
counter.pack()
tk.Button(root, text="Press me", command=add_one).pack()
tk.Button(root, text="Quit", command=root.destroy).pack()
root.mainloop()
```

A button is pressed by clicking it, if your terminal sends mouse clicks,
or by moving to it with **Tab** and pressing **Return** or the **space
bar**. Tab moves the *keyboard focus* - which widget your keys go to -
forward through the widgets, and **Shift-Tab** moves it back.

`root.destroy` closes the root window, which ends `mainloop` and with it
the program. The Quit button runs it directly, because it is already a
function.

## Variables

Reading a field's contents and writing them back by hand gets tedious.
A *variable* holds a value and keeps every widget attached to it showing
that value. `StringVar` holds text; `IntVar`, `DoubleVar` and `BooleanVar`
hold the other kinds.

% expect: Hello, stranger

```python
import tkcurses as tk

root = tk.Tk()
name = tk.StringVar(value="stranger")
message = tk.StringVar()

def greet(*args):
    message.set(f"Hello, {name.get()}")

name.trace_add("write", greet)
greet()

tk.Label(root, text="Your name:").pack()
field = tk.Entry(root, textvariable=name)
field.pack()
tk.Label(root, textvariable=message).pack()
field.focus_set()
root.mainloop()
```

The `Entry` and the variable `name` are connected by
`textvariable=name`: whatever is typed into the field is in `name`, and
`name.set(...)` would change what the field shows. `trace_add("write",
greet)` asks for `greet` to be called whenever `name` changes, so the
second label follows along as you type. `focus_set()` puts the keyboard
focus in the field to start with.

## Arranging widgets

Something has to decide where each widget goes and how big it is. That is
the job of a *geometry manager*, and there are three. Each widget is
arranged by one of them, chosen by calling its method.

**`pack`** stacks widgets against a side of their parent, top to bottom
unless you say otherwise. It is the simplest, and fine for a column or a
row of widgets.

```python
toolbar = tk.Frame(root)
toolbar.pack(side="top", fill="x")      # a strip across the top
tk.Button(toolbar, text="Open").pack(side="left")
tk.Button(toolbar, text="Save").pack(side="left")
```

`fill="x"` stretches a widget across the space it was given; `side="left"`
lines the buttons up in a row inside the frame.

**`grid`** puts widgets in rows and columns, like a table. It is the
natural choice for a form.

% expect: Email

```python
import tkcurses as tk

root = tk.Tk()
form = tk.Frame(root)
form.pack(fill="x")
for row, label in enumerate(["Name", "Email", "Phone"]):
    tk.Label(form, text=label).grid(row=row, column=0, sticky="w")
    tk.Entry(form).grid(row=row, column=1, sticky="ew")
form.columnconfigure(1, weight=1)
root.mainloop()
```

`sticky="w"` keeps a label against the west (left) edge of its cell, and
`"ew"` stretches a field from east to west. `columnconfigure(1, weight=1)`
gives column 1 any spare width, so the fields grow with the terminal and
the labels do not.

**`place`** puts a widget at an exact position, which is rarely what you
want and occasionally exactly that.

Sizes and positions are counted in character cells - one column of one
row of the terminal - rather than the pixels a desktop toolkit counts in.

## Events

`command` covers buttons. For everything else, `bind` connects an *event*
to a function: a key, a mouse click, the focus arriving. The event is
named in angle brackets, and the function receives an *event object*
saying what happened.

% expect: Press a key

```python
import tkcurses as tk

root = tk.Tk()
shown = tk.Label(root, text="Press a key")
shown.pack()

def on_key(event):
    shown.configure(text=f"You pressed {event.keysym}")

root.bind("<Key>", on_key)
root.bind("<Escape>", lambda event: root.destroy())
root.mainloop()
```

`<Key>` is any key, `<Escape>` is one key, and `<Control-s>` would be
Ctrl and S together. A binding on `root` hears keys whichever widget has
the focus.

To run something later, or every so often, ask `after` to call it in a
number of milliseconds. A function that schedules itself again keeps going:

% expect: Seconds:

```python
import tkcurses as tk

root = tk.Tk()
seconds = tk.IntVar(value=0)
tk.Label(root, text="Seconds:").pack(side="left")
tk.Label(root, textvariable=seconds).pack(side="left")

def tick():
    seconds.set(seconds.get() + 1)
    root.after(1000, tick)

root.after(1000, tick)
root.mainloop()
```

Your functions run inside `mainloop`, which cannot redraw the screen or
read keys until they return. Keep them quick: a function that sleeps or
waits on the network freezes the interface while it does. `after` is how
to wait without freezing.

## A complete program

Everything so far, put together: a to-do list. Type a task and press
Return to add it; pick one in the list and press **Done** to take it off.

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

A few things are new:

- **`expand=True`** gives a widget a share of any space left over, so the
  list grows to fill the terminal while the rows of buttons keep their
  height.
- **The row of buttons is packed before the list**, against the bottom.
  `pack` hands out space in the order widgets were packed, so in a short
  terminal whatever is packed last is what gets squeezed - and a list that
  loses a few lines is better than buttons that disappear.
- **The scrollbar and the list are connected both ways.** `command=
  tasks.yview` lets the scrollbar move the list; `yscrollcommand=bar.set`
  lets the list tell the scrollbar where it is, when it scrolls by itself.
- **`add` is used twice**: by the button, which calls it with no
  arguments, and by the binding on Return, which passes an event. The
  `event=None` lets one function serve both.
- **`curselection()`** answers the positions of the chosen lines.
  Deleting from the end backwards keeps the positions still to delete
  where they were.

## Where next

- The **themed widgets** in `tkcurses.ttk` are a second, more modern set
  of the same widgets, and add a few more: tabs (`Notebook`), a drop-down
  list (`Combobox`), a tree and table (`Treeview`) and a progress bar.
- **Dialogs** ask a question and wait for the answer:
  `tkcurses.messagebox.askyesno("Quit?", "Really quit?")` is one line.
- The [API reference](../reference/index.md) has every class, option and
  method.

Any tkinter tutorial or book will also serve. Where TkCurses behaves
differently from tkinter, the reference says so on the class or method
concerned - most often because a terminal is not a desktop: it counts in
cells rather than pixels, it has one screen rather than many windows, and
it can only show the colours and characters the terminal has.
