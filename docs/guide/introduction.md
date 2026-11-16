# Introduction

This guide is for anyone who has written some Python and wants a program
with an interface: buttons, fields to type into, lists to choose from. It
assumes nothing about tkinter or any other toolkit. It is the first of a
short series:

1. **Introduction** - this page: what TkCurses is, what it is built on,
   and a first program.
2. **[Core concepts](concepts.md)** - the three ideas every program rests
   on: the widget tree, geometry management, and events.
3. **[Common widgets](widgets.md)** - the widgets you will use most, and
   what each is for.
4. **[A larger program](larger-program.md)** - a notes application, built
   and explained a piece at a time.

[Common mistakes](mistakes.md) lists the ones nearly everybody makes once,
and the [glossary](glossary.md) defines the words these pages use.

## What TkCurses is

### Programs that wait to be told

Most programs that run in a terminal talk to you in lines of text: they
print, you type, they print again. The program is in charge. It decides
what to ask and in what order, and it stops and waits at each `input()`
until you answer.

A program with a *user interface* turns that around. It puts things on the
screen that stay there - a field you can type into, a button you can
press, a list you can scroll through - and then waits for *you*. You might
type in the field, or press the button first, or scroll the list and
change your mind. The program does not know which, and does not ask. It
says in advance what should happen *if* each thing is done, and responds to
whatever is done, in whatever order.

That arrangement has a name, **event-driven programming**, and three parts
make it work:

- **Widgets** are the things on the screen: a label, a button, a field, a
  list. A program builds its interface by making widgets and putting them
  inside one another, so that the whole screen is a tree of them.
- **Geometry managers** decide where each widget goes and how big it is,
  and decide again whenever there is more or less room.
- **The event loop** waits for something to happen - a key, a click, the
  terminal being resized, a timer running out - and calls the function the
  program said to call for it. Those functions are *callbacks*: you write
  them, and the loop calls them back.

So a program's own code runs in two phases. First it builds the interface
and connects callbacks to events. Then it hands control to the loop, and
from then on its code runs only when the loop calls a callback. The
[core concepts](concepts.md) page takes each of the three in turn.

### tkinter

A **GUI toolkit** is a library that provides widgets, geometry managers and
an event loop. Python ships with one, **tkinter**, which is Python's
interface to the Tk toolkit and draws its widgets in windows on a desktop.
Python's own documentation for it is the place to start, and the
introduction there points to the tutorials and reference it trusts:

- [tkinter - Python interface to Tcl/Tk](https://docs.python.org/3/library/tkinter.html),
  the standard library's documentation;
- [tkinter.ttk](https://docs.python.org/3/library/tkinter.ttk.html), the
  themed widgets;
- [TkDocs](https://tkdocs.com/tutorial/), a tutorial that covers tkinter
  thoroughly and is kept up to date;
- [Tk's own manual pages](https://www.tcl-lang.org/man/tcl9.0/TkCmd/contents.html),
  which are what tkinter's behaviour is ultimately defined by.

**TkCurses is tkinter for the terminal.** It has the same modules, classes,
methods and options, used the same way, but it draws with text in the
terminal you are already in rather than in a window on a desktop. Because
the two speak the same language, everything you learn here applies to
tkinter, and almost everything written about tkinter applies here. Where
TkCurses differs, because a terminal is not a desktop, the reference says
so on the class or method concerned.

It also means a TkCurses program runs where a desktop program cannot: over
SSH, on a server with no display, in a container, or on the Linux console.

### curses

A terminal shows a grid of character **cells**, typically 80 or more
across and 24 or more down, each holding one character in one colour. A
program that only prints adds lines at the bottom. A program that draws
*anywhere* on that grid - an editor, a file manager, `top` - sends the
terminal escape sequences that move the cursor, set colours and clear
parts of the screen, and those sequences differ from one terminal to the
next.

**curses** is the library that hides the differences. It reads what the
terminal can do from the terminfo database, keeps a copy of what the screen
should look like, and sends only the changes. Its usual implementation is
[ncurses](https://invisible-island.net/ncurses/), and Python's standard
library wraps it as the [`curses`](https://docs.python.org/3/library/curses.html)
module; the [Curses Programming with Python](https://docs.python.org/3/howto/curses.html)
HOWTO introduces it. A curses program works in *windows* - rectangles of
cells it can write into and then copy to the screen.

**Panels** are curses' answer to windows that overlap. Each window can be
put on a panel, the panels are kept in a stack, and
[`curses.panel`](https://docs.python.org/3/library/curses.panel.html)
draws them back to front, so that the one on top is the one you see where
they overlap. Moving a panel to the top is how a menu drops down over a
form or a dialog appears over everything else.

TkCurses is built on both. Every widget draws into a curses window of its
own, each window sits on a panel, and the panels are stacked in the order
of the widget tree, children in front of the widget they are inside. You
never handle the windows or panels yourself - the widgets do - but they
are why a dropped-down menu covers what is under it and leaves it intact
when it goes. A program written for curses itself can use
`tkcurses.curses` and `tkcurses.panel`, which offer the standard modules'
interfaces on top of the same machinery, and can even share the screen
with widgets. [How TkCurses works](how-it-works.md) follows a key press
and a redraw through these layers.

### Unicode

**Unicode** is the standard that gives every character in every writing
system a number, and **UTF-8** is the way of writing those numbers as
bytes that terminals and files on Linux and macOS use. TkCurses relies on
it in two ways:

- **Your text is Unicode.** A label, an entry or a text widget can hold
  `"Zoë"`, `"Ελληνικά"` or `"→ ✓"`, and shows them as long as the
  terminal's font has them.
- **Its drawing is Unicode.** Borders are box-drawing characters (`┌─┐`),
  radio buttons and arrows are symbols (`•`, `▲`, `▾`), and pictures and charts
  are made of block characters (`▀`, `▄`, `█`). A terminal running in a
  UTF-8 locale shows them all.

Two things follow. The terminal must be using UTF-8 - nearly every one
does, and [Terminals](terminals.md#what-a-terminal-needs) says how to
check and what to do if not, including drawing in plain ASCII instead. And
a cell holds one character, but not every character fits in one: most
Chinese, Japanese and Korean characters and many emoji are drawn two cells
wide, which [Terminals](terminals.md#unicode) explains.

### Colour and graphics

A terminal shows a fixed number of colours, and which number depends on
the terminal: none, 8, 16, 256, or the 16 million of "true colour". A
program asks for colours by name (`"tomato"`, `"navy"`) or as `"#rrggbb"`,
exactly as in tkinter, and TkCurses draws each as the nearest colour the
terminal has. So a program can be written once and still look right on a
basic terminal - as long as it never tells things apart by colour alone.
[Terminals](terminals.md#colours) lists the kinds and how to try a program
on each.

There are no pixels, only cells, so graphics are drawn with characters.
The **Canvas** draws lines, rectangles, ovals, polygons and text, and to
make curves smoother it counts half a cell as its unit down the screen,
using the half-block characters `▀` and `▄`. A **PhotoImage** reads PNG,
GIF and netpbm files and draws two pixels to a cell, one above the other,
in the colours the terminal has - or in full colour on a terminal that
says it offers it. The [examples](examples.md) include a graph, a drawing
you can move things around in, and a picture.

## Before you start

You need Python 3.11 or later on Linux or macOS, and a terminal. Install
TkCurses with `pip`:

```bash
pip install git+https://github.com/slfields/TkCurses
```

To install a particular release instead, add its tag - the
[releases](https://github.com/slfields/TkCurses/releases) list them:
`pip install "tkcurses @ git+https://github.com/slfields/TkCurses@<tag>"`.

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
   or widget it goes inside - its *parent*. Then **`.pack()`** asks a
   geometry manager to put it on the screen. A widget that no geometry
   manager has been asked to show exists, but is not shown.
4. **`root.mainloop()`** hands control to the event loop. From here on it
   draws the screen, waits for keys and mouse clicks, and calls your code
   when something happens. It returns when the root window is closed.

Those are the three parts from above, in miniature: a widget in a tree
(the label, inside the root), a geometry manager (`pack`), and the event
loop (`mainloop`). This program has no callbacks, so the only event it
answers is Ctrl-C.

## Where next

**[Core concepts](concepts.md)** takes the three parts one at a time,
with a program for each.
