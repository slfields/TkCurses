# Core concepts

Every TkCurses program, from the four-line greeting in the
[introduction](introduction.md) to a full editor, is built from the same
three ideas: **widgets** arranged in a tree, **geometry managers** that
give each widget its place on the screen, and **events** that the main
loop turns into calls to your code. This page takes them in turn. The
ideas, and the names, are tkinter's, so they carry over unchanged.

## Widgets and the widget tree

### Widgets and options

A widget is one element of the interface. Every one is created the same
way: the class, then the parent it goes inside, then *options* as keyword
arguments. Options set what the widget shows and how.

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

`fg` and `bg` are the foreground (text) and background colours. An option
can be read and changed at any time after the widget exists, and the
screen follows:

```python
status.configure(text="Status: saving")   # change one or more options
status["text"] = "Status: saved"          # the same, one option at a time
print(status.cget("text"))                # read one back
```

Each widget's options are listed in the [API reference](../reference/index.md),
and the options most widgets share - colours, borders, padding, sizes -
are described once, on [Options](../reference/options.md).

### Parents and children

Every widget except the root has a **parent**, given as the first argument
when it is made, and a widget can be the parent of others. So the widgets
of a program form a **tree**, with the root window at the top. A `Frame`
is a widget that shows nothing of its own, made to be a parent: it groups
widgets so that they can be arranged together.

Each widget has a **path name** that spells out its place in the tree, as
a file's path does in a directory tree. The root is `.`, and each widget
below it adds a dot and its own name, which TkCurses makes up -
`!frame`, `!button2` - unless the widget is given one with `name=`. This
program builds a small tree and then shows it, by walking it with
`winfo_children()`:

% expect: .buttons  Frame

```python
import tkcurses as tk

root = tk.Tk()
form = tk.Frame(root, name="form")
form.pack(side="left", anchor="n")
tk.Label(form, text="Name").pack()
tk.Entry(form, name="name", width=12).pack()
buttons = tk.Frame(root, name="buttons")
buttons.pack(side="left", anchor="n")
tk.Button(buttons, text="OK").pack()
tk.Button(buttons, text="Cancel").pack()


def describe(widget, depth=0):
    lines = ["  " * depth + f"{widget}  {widget.winfo_class()}"]
    for child in widget.winfo_children():
        lines += describe(child, depth + 1)
    return lines


tree = tk.Label(root, text="\n".join(describe(root)), justify="left")
tree.pack(side="left", anchor="n")
root.mainloop()
```

It shows:

```text
.  Tk
  .form  Frame
    .form.!label  Label
    .form.name  Entry
  .buttons  Frame
    .buttons.!button  Button
    .buttons.!button2  Button
```

The label showing the tree is not in it, because it was made after the
tree was described. The tree is shown in a label rather than printed
because, as [Porting](porting.md#output-and-errors) explains, `print()`
in a TkCurses program writes over the screen.

`str(widget)` is the path name, `widget.winfo_parent()` the parent's,
`widget.winfo_children()` the children in the order they were made, and
`root.nametowidget(".form.name")` finds a widget from its path.

### What the tree decides

The tree is more than bookkeeping. Where a widget sits in it decides:

- **Where it can appear.** A widget is shown only inside its parent's area.
  Moving a frame moves everything in it, and hiding a frame hides
  everything in it.
- **How long it lives.** `destroy()` removes a widget *and everything
  below it*, so `root.destroy()` ends the program, and a dialog's frame
  takes its fields with it.
- **What is in front.** A child is drawn in front of its parent, and of
  two siblings the one made later is in front where they overlap.
- **The order Tab follows.** Tab moves the keyboard focus through the
  widgets that take it in the order they were made, walking the tree
  parent before children. To change the order, change the order the
  widgets are made in - [A larger program](larger-program.md) does.

## Geometry management

A widget's **geometry** is its size and its position in its parent. A
widget does not choose its own. It *requests* a size, from what it has to
show - a label wants room for its text, a list for the lines its `height`
asks for - and the **geometry manager** of its parent decides what it
actually gets, from the requests of all the widgets in that parent and the
room the parent has. `winfo_reqwidth()` answers what a widget asked for,
and `winfo_width()` what it was given.

A widget appears only once a geometry manager has been told to manage it,
by calling one of three methods on it: `pack`, `grid` or `place`. Each
manager has its own way of deciding, and each suits a different kind of
layout. Sizes and positions are counted in character **cells** - one
column of one row - rather than the pixels a desktop toolkit counts in.

### pack: against the sides

`pack` takes the widgets in the order they were packed, and puts each one
against a side of the space that is still free: the top, unless `side`
says otherwise. Whatever is left after each is the space the next one is
packed into. This program packs five labels, one against each side and the
last into the middle:

% expect: 5 the rest

```python
import tkcurses as tk

root = tk.Tk()
tk.Label(root, text="1 top", bg="navy").pack(side="top", fill="x")
tk.Label(root, text="2 bottom", bg="dark green").pack(side="bottom", fill="x")
tk.Label(root, text="3 left", bg="dark red").pack(side="left", fill="y")
tk.Label(root, text="4 right", bg="purple").pack(side="right", fill="y")
tk.Label(root, text="5 the rest", bg="gray30").pack(fill="both", expand=True)
root.mainloop()
```

Three options do most of the work:

- **`side`** - `"top"`, `"bottom"`, `"left"` or `"right"`: which edge of
  the free space the widget goes against.
- **`fill`** - `"x"`, `"y"` or `"both"`: stretch the widget across the
  space it was given, rather than leave it at the size it asked for.
- **`expand=True`** - give the widget a share of any room left over once
  every widget has what it asked for. Without it, extra room is left
  empty.

Order matters twice over. The first widget packed against the top is the
topmost; and when there is not enough room, the widgets packed *last* are
the ones squeezed. `pack` suits rows, columns, and a window that is a
toolbar, a status line and a big area in between.

### grid: rows and columns

`grid` puts widgets in the cells of a table, by `row` and `column`. It is
the natural choice for a form, where labels and fields have to line up.

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

- **`sticky`** says which edges of its cell a widget clings to, by compass
  point: `"w"` keeps a label against the west (left) edge, and `"ew"`
  stretches a field from east to west. `"nsew"` fills the cell.
- **`columnconfigure(1, weight=1)`** gives column 1 any spare width, so the
  fields grow with the terminal and the labels do not. `rowconfigure` does
  the same for rows. A column or row with no weight keeps the size its
  widest widget asked for.
- **`columnspan`** and **`rowspan`** let one widget cover several cells.

### place: exact positions

`place` puts a widget at a position you give, either in cells (`x`, `y`)
or as a fraction of the parent's size (`relx`, `rely`, from 0 to 1), and
`anchor` says which point of the widget is put there. `relwidth` and
`relheight` size it as a fraction of the parent too.

% expect: bottom right

```python
import tkcurses as tk

root = tk.Tk()
board = tk.Frame(root, bg="gray20")
board.pack(fill="both", expand=True)
tk.Label(board, text="top left").place(x=0, y=0)
tk.Label(board, text="centre").place(relx=0.5, rely=0.5, anchor="center")
tk.Label(board, text="bottom right").place(relx=1, rely=1, anchor="se")
tk.Label(board, text="a third wide", bg="navy").place(relx=0, rely=0.25, relwidth=0.33)
root.mainloop()
```

`place` takes no notice of other widgets, so placed widgets can overlap.
That makes it the wrong tool for most layouts and the right one for an
overlay, such as a badge in a corner.

### One manager to a container

The widgets inside one container are all arranged by one manager: you can
pack some widgets into a frame and grid others into a *different* frame,
but not pack and grid widgets in the same one. The two would each try to
size the container to suit their own widgets, forever, so tkinter and
TkCurses both refuse, with an error saying which manager is already there.
Mixing managers is done with frames: grid a form inside a frame, and pack
that frame among the others. [Layouts](examples.md#layouts) in the
examples does exactly that, with all three.

In tkinter, `place` may share a container with `pack` or `grid`, which is
how a badge is put over packed content. TkCurses does not allow that yet,
so give placed widgets a frame of their own, as above.

### When the terminal changes size

The root window is the whole terminal, so when the terminal is resized, so
is the root - and every manager lays its widgets out again, all the way
down the tree. Nothing has to be written for that to happen. What the
program decides is *who gets the difference*: the widgets packed with
`expand=True`, the grid rows and columns with a `weight`, and the widgets
placed with `relx`, `relwidth` and the rest. The rest keep the size they
asked for. A program that wants to know binds `<Configure>`, the event a
widget is sent when its size changes; [Terminals](terminals.md#size-and-resizing)
shows one.

A container normally takes the size its children ask for - it
*propagates* their requests to its own manager. `pack_propagate(False)` or
`grid_propagate(False)` on a container stops that, so that a `width` and
`height` given to the container are kept whatever is inside.

## Events, callbacks and the main loop

### The loop

`mainloop()` runs until the root window is destroyed. It goes round the
same few steps again and again:

```text
mainloop
 ├─ run the work queued with after_idle()
 ├─ run the after() timers that are due
 ├─ wait for input - a key, a click, the terminal resized - but no longer
 │  than until the next timer is due
 │   └─ deliver it as an event: run the bindings and commands for it
 ├─ lay out again whatever changed size or position
 └─ draw whatever changed
```

Two things follow from that, and both matter.

- **Your code runs inside the loop.** Every callback is called from one of
  those steps, and the loop does nothing else until it returns. A callback
  that takes a second - that sleeps, or waits for the network - freezes
  the whole program for that second: no keys are read and nothing is
  drawn.
- **Changes are drawn when the callback returns, not as it makes them.** A
  callback can change a dozen widgets and the screen shows the result once,
  in the "draw" step. That is why a loop in a callback that updates a label
  each time round shows only the last value.

### Commands

The simplest connection between an event and your code is a widget's
`command` option. A `Button` calls it when pressed. Pass the function
itself - `command=add_one`, not `command=add_one()`, which would call it
once, immediately, and pass what it returned.

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

`Checkbutton`, `Radiobutton`, `Scale`, `Spinbox` and the menu entries take
a `command` too, called when the user changes them.

### Variables

A *variable* holds a value, keeps every widget attached to it showing that
value, and can call your code whenever the value changes - which makes it
a kind of event too. `StringVar` holds text; `IntVar`, `DoubleVar` and
`BooleanVar` hold the other kinds.

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

### Bindings and the event object

For everything else there is `bind`, which connects an **event** to a
function on one widget. The event is named in angle brackets, and the
function is called with an **event object** describing what happened.

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

Some of the events a program binds most:

| Event | Happens when |
|---|---|
| `<Key>` | Any key is pressed. |
| `<Return>`, `<Escape>`, `<Up>`, `<F1>`, `<a>` | That one key is pressed. |
| `<Control-s>`, `<Alt-x>` | A key is pressed with Ctrl, or Alt. |
| `<Button-1>`, `<Double-Button-1>` | The left mouse button is clicked, or double-clicked. |
| `<B1-Motion>` | The mouse is moved with the left button held: a drag. |
| `<FocusIn>`, `<FocusOut>` | The widget gains, or loses, the keyboard focus. |
| `<Configure>` | The widget changes size or position. |
| `<<ListboxSelect>>` | A *virtual event*, in double brackets, that a widget sends - here, when the user chooses in a list. |

And some of what the event object carries:

| Attribute | What it is |
|---|---|
| `event.widget` | The widget the event happened to. |
| `event.keysym` | The key's name: `"a"`, `"Return"`, `"Up"`. |
| `event.char` | The character the key types, or `""` for a key that types none. |
| `event.x`, `event.y` | Where the mouse was, in cells from the widget's top-left corner. |
| `event.width`, `event.height` | For `<Configure>`, the new size. |

### Where a binding lives, and "break"

A binding can be made at four levels, and an event runs the bindings at
each level in turn:

1. **the widget** - `field.bind(...)`;
2. **its class** - the behaviour every `Entry` has, which is how typing
   into a field puts the characters there;
3. **its window** - `root.bind(...)` hears events for every widget in the
   window, which is why the key program above binds on `root`;
4. **everything** - `bind_all(...)`.

`widget.bindtags()` lists the four for a widget. A function bound at one
level can stop the levels after it by returning the string `"break"`.
Because the widget's own bindings come before its class's, that is how a
program changes what a widget does with a key. This field takes digits
only - everything else that would type a character is stopped before the
`Entry` class can insert it:

% expect: Age, in digits:

```python
import tkcurses as tk

root = tk.Tk()
tk.Label(root, text="Age, in digits:").pack()
age = tk.Entry(root, width=6)
age.pack()

def digits_only(event):
    if event.char.isprintable() and event.char and not event.char.isdigit():
        return "break"

age.bind("<Key>", digits_only)
age.focus_set()
root.mainloop()
```

Keys that type nothing - BackSpace, the arrows, Tab - have no printable
`char`, so they pass and keep working.

### Later, and every so often

To run something later, or repeatedly, ask `after` to call it in a number
of milliseconds. A function that schedules itself again keeps going:

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

`after` answers an id, and `after_cancel(id)` takes back a call that has
not happened yet - the way to put off a save until the user stops typing,
as [A larger program](larger-program.md) does. `after_idle` runs something
as soon as the loop has nothing else to do.

`after` is also how to wait without freezing. Instead of sleeping in a
callback for a second and then doing something, schedule the something for
a second's time and return.

## Where next

**[Common widgets](widgets.md)** goes through the widgets you will use
most, what each is for, and ends with a small complete application.
