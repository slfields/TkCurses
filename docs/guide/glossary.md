# Glossary

The words these guides use, in the sense they use them. Most are
tkinter's own, and mean the same there.

```{glossary}
binding
  A connection between an {term}`event` and a function, made with `bind`.
  The function is called with an {term}`event object` each time the event
  happens. See [Core concepts](concepts.md#bindings-and-the-event-object).

callback
  A function you write for the {term}`main loop` to call when something
  happens: a button's `command`, a {term}`binding`'s function, a function
  given to `after`.

cell
  One character position on the terminal's screen: one column of one row.
  TkCurses measures every size and position in cells.

child
  A widget made inside another, which is its {term}`parent`.

class binding
  A {term}`binding` shared by every widget of one class, which gives the
  class its behaviour: the `Entry` class's bindings are what insert typed
  characters.

colour depth
  How many colours a terminal can show: none, 8, 16, 256, or 16 million
  ("true colour"). See [Terminals](terminals.md#colours).

command
  The option, on a `Button` and several other widgets, naming the
  {term}`callback` to run when the widget is used.

container
  A widget that holds others: the root window, a `Frame`, a `LabelFrame`,
  a `Toplevel`, a notebook's page.

curses
  The library terminal programs use to draw anywhere on the screen without
  knowing which terminal they are in. TkCurses draws through it.

event
  Something that happens and that a program can respond to: a key pressed,
  a click, a widget resized, the focus moving. Named in angle brackets:
  `<Return>`, `<Button-1>`.

event object
  What a {term}`binding`'s function is called with, describing the
  {term}`event`: which widget, which key, where the mouse was.

focus
  The widget that keys go to. Tab and Shift-Tab move it, and
  `focus_set()` puts it on a widget.

geometry
  A widget's size and position in its {term}`parent`.

geometry manager
  What decides a widget's {term}`geometry`, from the size it asks for and
  the room its parent has: `pack`, `grid` or `place`. A widget is not shown
  until one manages it.

main loop
  The loop `mainloop()` runs, which waits for {term}`event`s, calls the
  {term}`callback`s for them, and redraws what changed. A program's own code
  runs inside it, so a slow callback stops everything.

option
  A setting of a widget, given as a keyword argument when it is made or
  later with `configure`: `text`, `bg`, `width`, `command`.

panel
  A curses window that is kept in a stack with others, so that where they
  overlap, the one nearer the top is seen. TkCurses puts every widget's
  window on one.

parent
  The widget, or window, that another is made inside: the first argument
  when a widget is made. Also called its *master*.

path name
  A widget's name in the {term}`widget tree`, such as `.form.name`: the
  root is `.`, and each widget below adds a dot and its own name.

root window
  The window made by `Tk()`, at the top of the {term}`widget tree`. In
  TkCurses it is the whole terminal.

tag
  A name given to a range of text in a `Text`, or to items on a `Canvas`,
  so that they can be styled, found or bound to together.

themed widget
  A widget from `tkcurses.ttk`, drawn by a style that can be changed for
  every widget of its kind at once.

Unicode
  The standard that numbers every character of every writing system. Text
  in TkCurses is Unicode, and so are the box-drawing and block characters
  it draws with. Terminals receive it as UTF-8.

variable
  A `StringVar`, `IntVar`, `DoubleVar` or `BooleanVar`: a value that
  widgets can show and change, and that can call a function whenever it
  changes.

virtual event
  An {term}`event` that a widget sends to say something meaningful
  happened, rather than a key or click as such. Named in double brackets:
  `<<ListboxSelect>>`, `<<Modified>>`.

widget
  One element of the interface: a label, button, field, list, frame.

widget tree
  All of a program's widgets, arranged by which is inside which, with the
  {term}`root window` at the top.
```
