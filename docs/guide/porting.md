# Porting a tkinter program

TkCurses has tkinter's classes, methods and options, so most of porting a
program is changing its imports. What remains comes from the terminal
itself: it is a grid of character cells with one font, it has no window
manager, and it may not have a mouse. This guide goes through each of
those in turn, saying what changes and what to do about it.

It assumes you know tkinter. If you do not, start with the
[Introduction](introduction.md).

## Change the imports

Import `tkcurses` wherever the program imports `tkinter`. The submodules
have the same names:

```python
import tkcurses as tk                       # was: import tkinter as tk
from tkcurses import ttk, messagebox        # was: from tkinter import ttk, messagebox
from tkcurses import filedialog, font       # was: from tkinter import filedialog, font
```

`from tkcurses import *` works as `from tkinter import *` does. Programs
written against `tkinter.ttk`, `tkinter.simpledialog`, `tkinter.colorchooser`,
`tkinter.scrolledtext` and the rest change the same way; the
[API reference](../reference/index.md) lists every module.

A program that should run under either library can choose at start-up:

```python
try:
    import tkcurses as tk
except ImportError:
    import tkinter as tk
```

## Sizes are in cells

Everywhere tkinter measures in pixels, TkCurses measures in **character
cells**: one column of one row of the terminal. A number keeps its meaning
as a count, and that count is now of cells. So a size written for a desktop
is much too big in a terminal:

- `Frame(width=300, height=200)` asks for 300 columns by 200 rows, and is
  cut off at the edge of the screen.
- `Button(padx=10)` puts ten *columns* each side of the text: a button
  reading "OK" is 28 cells wide.
- A distance with a unit is converted as if a cell were a tenth of an inch
  across: `winfo_pixels("1i")` is 10, `"2c"` is 8 and `"72p"` is 10.

Dividing a pixel size by about eight across and sixteen down - the size of
one cell of a typical terminal font - gives a size of the same proportion.
Padding of a few pixels becomes 0 or 1. Better still, let the geometry
manager size things: a layout built with `pack` and `grid` and few fixed
sizes ports with no changes at all.

This is a typical tkinter program, sized in pixels:

```python
import tkinter as tk

root = tk.Tk()
root.title("Converter")
root.geometry("360x140")
tk.Label(root, text="Miles", font=("Helvetica", 14)).grid(row=0, column=0, padx=12, pady=8)
miles = tk.Entry(root, width=12)
miles.grid(row=0, column=1, padx=12)
answer = tk.Label(root, text="0 km", width=20)
answer.grid(row=1, column=0, columnspan=2, pady=8)
tk.Button(root, text="Convert", padx=20,
          command=lambda: answer.config(text=f"{float(miles.get()) * 1.609:.1f} km")
          ).grid(row=2, column=0, columnspan=2)
root.mainloop()
```

And here it is ported. Only the import and the pixel sizes change; the
`geometry` call can stay, because the root window is always the whole
terminal and the call is ignored, and so can the font, whose family and
size make no difference:

% expect: Convert

```python
import tkcurses as tk

root = tk.Tk()
root.title("Converter")
root.geometry("360x140")
tk.Label(root, text="Miles", font=("Helvetica", 14)).grid(row=0, column=0, padx=1, pady=1)
miles = tk.Entry(root, width=12)
miles.grid(row=0, column=1, padx=1)
answer = tk.Label(root, text="0 km", width=20)
answer.grid(row=1, column=0, columnspan=2)
tk.Button(root, text="Convert", padx=1,
          command=lambda: answer.config(text=f"{float(miles.get()) * 1.609:.1f} km")
          ).grid(row=2, column=0, columnspan=2)
miles.focus_set()
root.mainloop()
```

Type a number, press **Tab** to reach the button, and **Return** to press
it.

## Windows

The terminal is one screen, and there is no window manager to arrange
windows on it.

- **The root window is the whole terminal**, always. `root.geometry()` is
  accepted and changes nothing; when the terminal is resized, the root is
  resized with it.
- **A `Toplevel` is drawn as a box with its title in the top edge**, at the
  size and place its geometry gives - `"20x5+10+4"` is 20 columns by 5 rows
  at column 10, row 4 - and in front of the root.
- **The icon family of `wm` is missing**: `iconbitmap`, `iconphoto`,
  `iconname`, `aspect` and `group`. `attributes()` knows only `-topmost`
  and `-fullscreen`. A program that sets an icon has to stop doing so, or
  catch the `AttributeError`.

## Fonts

A terminal has one font in one size. Of a font, TkCurses uses only its
style: **bold**, *italic* and underline become the terminal's own
attributes, where it has them. A family and a size are accepted and make no
difference, so a program's fonts need not change. A `Font` measures in
cells: `measure()` is the length of the text and `metrics("linespace")` is
1.

## Colours

Every colour name Tk knows works, read as Tk reads it - `"SteelBlue"`,
`"steel blue"` and `"gray90"` - as do `"#rrggbb"` and the other hex forms.
A name Tk does not know is refused with Tk's own `TclError` when it is set.

What is drawn is the nearest colour the terminal can show. Terminals
range from 8 colours to 16 million, and TkCurses finds out which it is
talking to from `TERM`; `winfo_colordepth()` says what it found. Run a
program with `TERM=xterm` to see it as an eight-colour terminal draws it -
[Terminals](terminals.md) has the others. On a basic terminal a colour can change a long way: with eight colours,
`SteelBlue` is drawn grey. A design that tells things apart only by colour,
or by close shades, may lose the difference there.

% expect: depth

```python
import tkcurses as tk

root = tk.Tk()
for name in ("SteelBlue", "light goldenrod yellow", "gray90", "#cd5c5c"):
    tk.Label(root, text=name, bg=name, fg="black").pack(fill="x")
tk.Label(root, text=f"This terminal has a colour depth of {root.winfo_colordepth()}").pack()
root.mainloop()
```

## The keyboard

A terminal user may have no mouse, so everything should be reachable from
the keyboard. Most of that is already done for you, as it is in Tk:

- **Tab and Shift-Tab** move the focus between widgets. A Text keeps Tab
  for itself, as Tk's does; **F6 and Shift-F6** move the focus from
  anywhere.
- **A menu bar** opens with **F10**, or with **Alt** and the letter its
  `underline` marks; inside a menu, the arrows move, Return chooses and
  Escape closes. Some terminals keep F10 for themselves - GNOME Terminal
  opens its own menu - so give every menu an `underline`.
- **Return and space** press a focused button.

Some keys cannot reach a program the way they reach one on a desktop
([Terminals](terminals.md) has the whole list):

- **Ctrl-C, Ctrl-Z and Ctrl-\\** close, suspend and quit the program, as
  in any terminal program, **unless the program binds them**: a binding for
  `<Control-c>` gets the key, and the program keeps running. Without a
  binding, Ctrl-C closes it cleanly. A suspended program comes back with
  `fg`, redrawn.
- **Alt** arrives from a terminal as Escape followed by the key, and is
  read as Alt, so `<Alt-...>` bindings work. A terminal set to send Alt
  some other way may not deliver it.
- **Control with Shift**, and Control with Tab or Return, cannot be told
  apart from the same key without Shift or Control in most terminals.
  Choose plain Control-letter or function-key shortcuts.

`Menu.bind_accelerators()`, a TkCurses addition, binds every entry's
`accelerator` text to the entry, so a shortcut written once in the menu
works:

% expect: Not saved

```python
import tkcurses as tk

root = tk.Tk()
status = tk.Label(root, text="Not saved")
bar = tk.Menu(root)
files = tk.Menu(bar, tearoff=0)
files.add_command(label="Save", underline=0, accelerator="Ctrl+S",
                  command=lambda: status.config(text="Saved"))
files.add_command(label="Quit", underline=0, command=root.destroy)
bar.add_cascade(label="File", menu=files, underline=0)
root.config(menu=bar)
files.bind_accelerators()
status.pack()
root.mainloop()
```

Press **Ctrl-S** to save, or **Alt-F** then **S** to choose Save from the
menu.

## The mouse

TkCurses uses the mouse when the terminal reports one, and works without
it. Clicks, double and triple clicks, drags and the wheel are delivered as
in tkinter. Two things are different:

- **The pointer's position is reported only while a button is held**,
  because that is all most terminals are asked for. Setting
  `TKCURSES_MOUSE_REPORT_HOVER=1` asks for every movement, for a terminal
  that can keep up.
- **`<Enter>` and `<Leave>` are not delivered** when the pointer crosses a
  widget, so a hover effect or tooltip built on them does not appear.

## Output and errors

The program's screen *is* the terminal, so anything written to it directly
lands on top of the widgets:

- **`print()` writes over the display**, wherever the cursor happens to
  be. Show messages in a widget, or write them to a file - the `logging`
  module, pointed at a file, is the usual way.
- **A traceback from a callback** is held back while the program runs and
  printed when it ends, unless standard error is redirected, in which case
  it is written at once: run with `2>errors.log` to watch them as they
  happen. The program carries on, as tkinter's does.

% expect: Started

```python
import logging

import tkcurses as tk

logging.basicConfig(filename="app.log", level=logging.INFO)

root = tk.Tk()
status = tk.Label(root, text="Started")
status.pack()

def press():
    logging.info("pressed")
    status.config(text="Pressed - see app.log")

tk.Button(root, text="Press", command=press).pack()
root.mainloop()
```

## Images

`PhotoImage` reads PNG, GIF and the netpbm formats, and `BitmapImage`
reads XBM, as Tk's do. A picture is drawn with block characters at two
pixels to a cell, one above the other, so a 64 by 64 image takes 64 columns
and 32 rows; `subsample` makes it smaller. See [Images](../reference/images.md).

## What is not there

A few parts of tkinter have nothing behind them here: `tkinter.Tcl()` and
anything that evaluates Tcl, the Canvas transform family, embedded windows
in a Text, and tear-off menus. The [README](https://github.com/slfields/TkCurses#known-gaps)
lists what is still missing. Calling one raises an error rather than
quietly doing nothing.

TkCurses runs on Linux, and should on macOS. **It does not run on
Windows**, whose Python has no `termios`; it may under WSL.
