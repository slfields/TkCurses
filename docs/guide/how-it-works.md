# How TkCurses works

You do not need any of this to write a program. It is here for the
curious, for anyone deciding whether TkCurses suits a job, and for anyone
about to read its source. It follows what happens between a key being
pressed and the screen changing, layer by layer.

The full record of the design - every decision, and the measurements of
Tk's own behaviour that most of them rest on - is
[ARCHITECTURE.md](https://github.com/slfields/TkCurses/blob/master/ARCHITECTURE.md)
in the repository. It is written for the people who maintain TkCurses,
and it is long; the section names below say where to look in it.

## The layers

```text
 your program              tkinter's API: Tk, Button, pack, bind, after
     │
 widgets                   one Python object per widget, in a tree;
     │                     each knows its options and how to draw itself
 geometry managers         pack, grid, place, and the paned window,
     │                     deciding each widget's rectangle of cells
 panels and windows        a curses window per widget, on a panel,
     │                     stacked in the order of the tree
 the screen                one buffer of cells, compared with what the
     │                     terminal already shows
 curses                    the escape sequences for this terminal
     │
 the terminal
```

Nothing above "curses" uses Tk or Tcl: the widgets are written in Python,
from Tk's manual pages and from measurements of what Tk actually does, so
that a program behaves the same in both. Nothing below "widgets" is
visible to a program, except through `tkcurses.curses` and
`tkcurses.panel`, which offer the standard library's interfaces on top of
the same screen.

## One pass of the loop

`mainloop()` repeats one pass until the root window is destroyed. Each pass
does five things, in an order chosen so that each step sees the results of
the ones before it:

1. **Idle work** - whatever was queued with `after_idle`.
2. **Timers** - every `after` call whose time has come.
3. **Input** - wait for the terminal to send something, but only until the
   next timer is due, so that the program uses no processor while it waits
   and still runs its timers on time. Whatever arrives is turned into
   events and delivered.
4. **Layout** - every geometry manager whose widgets changed is run again,
   from the root down.
5. **Drawing** - every widget whose appearance changed draws itself, and
   the screen sends the terminal what is different.

Layout comes after everything that might change it and before anything is
drawn, so that a widget is never drawn at a size it is about to stop
having. ARCHITECTURE.md: *Component Interactions*.

## From bytes to events

A terminal does not send keys; it sends bytes. A letter is its own byte,
but an arrow key is a short *escape sequence* - `Escape [ A` for Up - and
so are function keys, keys pressed with Ctrl or Alt, mouse clicks, and
pasted text. The input layer reads the bytes, recognises the sequences,
and turns each into the event tkinter would have delivered: a `<Key>`
with its `keysym` and `char`, a `<Button-1>` at a cell, a `<Configure>`
when the terminal reports a new size.

Some keys a desktop tells apart arrive as the same bytes - Tab and Ctrl-I,
for one - and some never arrive at all, because the terminal or the
desktop keeps them. [Terminals](terminals.md#the-keyboard) lists them.
ARCHITECTURE.md: *Input Handling Architecture*.

An event is then delivered as in Tk: to the widget with the keyboard focus
for a key, or the widget under the pointer for a click, running its
bindings level by level - widget, class, window, everything - until one
returns `"break"`. The class bindings are what make an `Entry` insert what
is typed, and they follow Tk's own library scripts, which is why editing
keys, selection and scrolling behave as they do in Tk.

## From widgets to cells

Each widget draws into a **curses window** of its own, the size of the
rectangle its geometry manager gave it, and each window sits on a
**panel**. The panels are kept in the order of the widget tree, every
child in front of the widget it is inside. Where windows overlap - a
dropped-down menu over a form, a dialog over everything - the one in front
is what shows, and when it goes, what was underneath is still there to be
shown again.

A widget draws only when something about it changes: an option, its text,
its size, its focus. The windows are then copied, back to front, into one
buffer of cells for the whole screen, and only the cells that differ from
what the terminal already shows are sent to it. So typing a letter in a
field sends the terminal a few bytes, not a screen.
ARCHITECTURE.md: *Widget Window Lifecycle* and *Window Content Areas*.

## Colours, characters and pictures

A colour named by a program is turned into red, green and blue values by
the same table of names X11 and Tk use, and then into the nearest colour
the terminal has - from 16 million on a true-colour terminal down to none.
curses draws a cell's colours as a numbered *pair* of foreground and
background, and a terminal has a few hundred pairs at most, so pairs are
handed out as colours are used, and the table is rebuilt between frames if
a program uses them all up. ARCHITECTURE.md: *Runtime Configuration*, for
how the colour depth is chosen.

Characters are written as Unicode. Borders, arrows and marks come from a
small set of symbols that has a plain ASCII form of each, for a terminal
whose font lacks them. The Canvas and PhotoImage draw with the half-block
characters `▀` and `▄`, which split a cell into a top and a bottom half
that can be coloured separately - two "pixels" to a cell, one above the
other. On a terminal that says it shows true colour, pictures are written
past curses in their full colours, since curses' pairs could not hold them.

## The terminal, borrowed and returned

When the first `Tk()` is made, TkCurses switches the terminal to the
*alternate screen* - the one full-screen programs use, so that the shell's
scrollback is left alone - hides the cursor, turns on mouse reporting, and
reads keys as they are pressed rather than a line at a time. All of it is
undone when the program ends, however it ends: the window closed, Ctrl-C,
or an uncaught exception, whose traceback is printed afterwards, where it
can be read. ARCHITECTURE.md: *Leaving, and giving the terminal back*.

## Where it differs from tkinter, and why

TkCurses aims to behave exactly as tkinter does, and where it cannot, the
reason is nearly always that a terminal is not a desktop:

- **Cells, not pixels.** Every size and position is in cells, a fixed
  font, and no font sizes.
- **One screen, one window manager.** The root window is the terminal.
  Other windows - `Toplevel`s and dialogs - are drawn inside it, and
  TkCurses itself moves and stacks them, as a desktop's window manager
  would. ARCHITECTURE.md: *Window Management*.
- **The terminal decides the colours and keys** that a program can have.

Each difference is stated in the reference, under *Differences from
tkinter*, on the class or method concerned, and
[Porting a tkinter program](porting.md) collects the ones that matter
when bringing a program over.
