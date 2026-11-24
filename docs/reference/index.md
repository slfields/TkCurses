# API reference

```{toctree}
:hidden:

core/index
options
hidden-fields
widgets/index
ttk/index
exclusive/index
geometry
images
dialogs/index
modules/index
configuration
tkcurses-cfg
compatibility
```

Every class and function TkCurses provides: [the application and what
every widget has](core/index.md), the [standard options](options.md),
[hidden fields](hidden-fields.md) for passwords, the
[classic widgets](widgets/index.md), the
[themed widgets](ttk/index.md), the
[widgets only TkCurses has](exclusive/index.md), the
[geometry managers](geometry.md), [images](images.md),
[dialogs](dialogs/index.md) and [the other modules](modules/index.md),
among them `curses` and `panel`. [Configuration](configuration.md) lists
the settings a user can change without changing a program,
[`tkcurses-cfg`](tkcurses-cfg.md) is the command that shows and changes
them, and
[compatibility with tkinter](compatibility.md)
lists every class and method of tkinter's and whether TkCurses has it.

A method tkinter gives two names, such as `wm_title` and `title`, is
described once, under the first, and says what else it is called.

## How to read it

TkCurses follows tkinter's API, so most of what it provides is documented
the way tkinter's is: what a class or method does and what it takes. Three
headings mark where it is not the same.

**Differences from tkinter** says where TkCurses behaves differently from
tkinter and Tk. Most come from the terminal: it counts in character cells
rather than pixels, it has one screen rather than many windows, and it can
show only the colours and characters the terminal has. A themed (`ttk`)
widget that has a method only the classic widget has in tkinter lists it
here as well, so a program that relies on it knows it will not run on
tkinter.

**TkCurses extension** marks API that tkinter does not have at all - the
`tkcurses.curses` and `tkcurses.panel` modules, the
[widgets only TkCurses has](exclusive/index.md) such as `BarGraph`, `TreeMap` and `XYChart`, and a
few methods such as `winfo_colordepth`. A program that uses one runs only
on TkCurses.

**Differences from curses** is the same as the first heading for those
two modules, which follow the standard library's `curses` and
`curses.panel` rather than tkinter.

Anything without one of these headings behaves as tkinter's does, and tkinter's
own documentation also applies to it.

A widget's own options are listed under **Options**. The options many
widgets share - colours, borders, fonts - are described once, on
[Standard options](options.md), and each widget lists which of them it
takes.

**Sample output** shows an example and the screen it draws. Every widget
has one, and so does every option that changes how a widget looks: on the
widget's page as **Sample output: relief**, say, or on the standard
options page for a shared one. Each example is the body of a program that
starts with

```python
import tkcurses as tk
from tkcurses import ttk
root = tk.Tk()
```

and ends with `root.mainloop()`. The pictures are made by running the
examples in a terminal each time this documentation is built, so they show
what the version you are reading draws:

```{tkcurses-sample}
tk.Label(root, text="Name:").pack(side="left")
tk.Entry(root, width=16).pack(side="left")
tk.Button(root, text="OK").pack(side="left")
```

A terminal shows the colours it has, so yours may differ in shade from
these, which are drawn with xterm's.
