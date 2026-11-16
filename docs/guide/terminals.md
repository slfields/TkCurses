# Terminals

A TkCurses program draws in whatever terminal it is started from, and
terminals differ: in how many colours they show, which keys they can send,
whether they report the mouse, and whether they will set the clipboard.
This guide says what TkCurses needs from a terminal, what it finds out for
itself, and what to do when a terminal falls short.

## What a terminal needs

- **A `TERM` that can move the cursor.** TkCurses learns what the terminal
  can do from the terminfo entry `TERM` names, as every curses program
  does. Anything descended from xterm or VT100 will do, and so will the
  Linux console. `TERM=dumb` cannot position the cursor, so nothing could be
  drawn there: `Tk()` refuses it with a `TclError` that says so, as tkinter's
  does for a display it cannot reach.
- **A UTF-8 locale.** Borders are drawn with box-drawing characters, and
  text is whatever Unicode the program shows. Under `LC_ALL=C`, an accented
  letter comes out as `�` and the lines of a box as `^`, and TkCurses says
  so on the way out, naming the variable to change. Set it to `C.UTF-8`,
  or any `.UTF-8` locale. (`LANG=C` on its own is fine: Python turns it
  into `C.UTF-8` when it starts.)
  A terminal whose font has no box-drawing characters can have boxes,
  arrows and bars drawn in plain ASCII instead, with
  `TKCURSES_DISPLAY_UNICODE=0`.
- **Linux or macOS.** Windows' own Python has no `termios`; under WSL,
  TkCurses runs as on Linux.

TkCurses is developed in GNOME's Ptyxis and tested against an emulation of
`xterm-256color`. Any terminal that implements xterm's escape sequences -
kitty, foot, WezTerm, Alacritty, Konsole, GNOME Terminal, iTerm2, xterm
itself - and tmux and GNU screen inside one are expected to work, within the
limits below.

## Colours

There are four kinds of terminal, by how many colours they show, and
TkCurses reads which kind it is in from `TERM`:

| `TERM`, for example | Colours | `winfo_colordepth()` |
|---|---|---|
| `vt100` | none | 0 |
| `xterm`, `linux` | 8 | 8 |
| `xterm-16color` | 16 | 16 |
| `xterm-256color`, `screen-256color`, `tmux-256color` | 256 | 256 |
| `xterm-direct` | 16 million | 16777216 |

Every colour a program asks for is drawn as the nearest one the terminal
has. With 256 that is usually close. With 8 it can be far - `SteelBlue` is
drawn grey - and with none, colours are left out and only bold, underline
and reverse video remain. So a design that tells things apart only by
colour will lose the difference on some terminals; give them a word or a
mark as well.

Most terminals today show 16 million colours, and many still say
`TERM=xterm-256color`. TkCurses believes `TERM`: `COLORTERM=truecolor`,
which such terminals also set, is used only for pictures, which are drawn
past curses in full colour when it is set. To see how a program looks on a
basic terminal, run it with a smaller `TERM`:

```console
$ TERM=xterm python3 app.py
```

or keep `TERM` and set `TKCURSES_DISPLAY_COLOR_MODE` to `8`, `16` or
`256`. It only ever takes colours away: on a terminal with 8, asking for
256 still gets 8. Set to `truecolor`, it draws pictures in full colour as
`COLORTERM=truecolor` does, for a terminal that does not say so.

## Size and resizing

The root window is always the whole terminal. When the terminal is
resized, the root is resized with it, `<Configure>` is delivered as it is
in tkinter - once when the root first appears, so a binding learns the
starting size too - and `pack`, `grid` and `place` lay the window out again. A
`Toplevel` is kept wholly on the screen, moved in if the terminal shrinks
past it.

% expect: columns by

```python
import tkcurses as tk

root = tk.Tk()
size = tk.Label(root)
size.pack(expand=True)


def show():
    size.config(text=f"{root.winfo_width()} columns by {root.winfo_height()} rows")


root.bind("<Configure>", lambda event: show() if event.widget is root else None)
root.mainloop()
```

Resize the terminal and the label follows. A layout built from `pack` and
`grid` with `expand` and `sticky` makes use of a larger terminal and
squeezes into a smaller one; one made of fixed sizes is cut off at the
edge.

## The keyboard

A terminal sends a program bytes, not keys, and some keys a desktop tells
apart arrive as the same bytes:

- **Tab, Ctrl-I and Ctrl-Tab** are all the same byte. A Text keeps Tab to
  indent, as Tk's does, and Tk's way out of it, Ctrl-Tab, cannot be sent.
  So **F6 and Shift-F6** move the focus to the next and previous widget
  from anywhere, a Text included.
- **Control with Shift**, and **Control with Return**, mostly arrive as
  the key without Shift or Control. Bind `<Control-s>`, not
  `<Control-S>`.
- **Alt** arrives as Escape followed by the key. TkCurses reads the pair
  back as Alt, so `<Alt-...>` bindings work. That depends on the terminal
  sending Alt as Escape, which almost all do by default; one set to "Meta
  sets the eighth bit" sends something else.
- **Escape on its own** is told apart from the start of a longer sequence
  by waiting 25 milliseconds for more. Over a slow connection a sequence
  can be split, and arrow keys arrive as Escape and letters; set
  `TKCURSES_INPUT_ESCAPE_DELAY` to more, in milliseconds.
- **A paste** arrives as bytes too, the same as typing it. TkCurses asks
  the terminal to mark the start and end of what is pasted (bracketed
  paste), which almost every terminal does. One that does not understand
  the request may show `200~` and `201~` around every paste; set
  `TKCURSES_INPUT_BRACKETED_PASTE=0` for it.

Some keys never reach the program because something else takes them first:

- **The terminal's own shortcuts**: many terminals keep Ctrl-Shift-C and
  Ctrl-Shift-V for copy and paste, F11 for full screen, and GNOME Terminal
  keeps F10 for its menu. A menu bar also opens with Alt and its
  underlined letter, which is why every menu should have an `underline`.
- **The window manager's**: Alt-Tab, Alt with an arrow on some desktops,
  and whatever else yours binds.
- **The terminal driver's**: Ctrl-C, Ctrl-Z and Ctrl-\\ interrupt, suspend
  and quit the program, unless it binds them, in which case it gets them
  as keys. Ctrl-S and Ctrl-Q, which once paused output, are handed to the
  program like any other key.

To see what a particular key arrives as, bind `<Key>` and show
`event.keysym`.

## The mouse

TkCurses turns on mouse reporting when it starts, and clicks, drags,
double and triple clicks and the wheel are delivered as in tkinter. A
terminal that does not report the mouse leaves the program usable from the
keyboard alone.

- **While a program has the mouse, the terminal's own selection moves to
  Shift.** Shift-drag selects text on the screen for the terminal to copy,
  as it would in any program that uses the mouse.
- **That is why Alt-click does what Shift-click does.** GNOME Terminal,
  Ptyxis and other VTE terminals keep every Shift-click and never send it,
  so Alt-click extends a selection in an Entry or Text as Shift-click does
  in Tk. In a terminal that does send Shift-click, both work.
- **The pointer is reported only while a button is held**, which is enough
  for clicks and drags. `TKCURSES_MOUSE_REPORT_HOVER=1` asks for every
  movement, at the cost of a report for every cell the pointer crosses and
  of the terminal's own selection while it is on.
  `TKCURSES_MOUSE_REPORT_MOTION=0` turns off reports of drags as well.
- **Double clicks** are two clicks within 200 milliseconds on the same
  cell. `TKCURSES_MOUSE_CLICK_INTERVAL` sets a longer time, up to 1000.
- **`TKCURSES_MOUSE_ENABLED=0` leaves the mouse to the terminal**, whose
  own selection then works without Shift. The program is used from the
  keyboard.
- **Inside tmux**, the mouse reaches a program only with `set -g mouse on`
  in tmux's configuration.

## The clipboard

Within a program, `clipboard_append` and `clipboard_get` work as in
tkinter, as do Ctrl-C and Ctrl-X on a selection in an Entry or Text, and
Ctrl-V. Reaching other applications' clipboard takes one of two routes,
chosen when the program starts:

- **The terminal**, with the OSC 52 escape sequence: the program asks the
  terminal to set the clipboard. This works over SSH, which is its point,
  but only in terminals that offer it - kitty, foot, WezTerm, xterm with
  `allowWindowOps`, and tmux among them. TkCurses asks the terminal whether
  it does before using it. GNOME Terminal and Ptyxis do not, on purpose.
  The terminal can only be told what to copy, never asked what it holds,
  so pasting from another application this way is not possible.
- **The desktop's clipboard program**: `wl-copy` and `wl-paste` on
  Wayland, `xclip` or `xsel` on X11. This works in any terminal, copies and
  pastes, but only on the machine the desktop is on, so it is not used over
  SSH. Install one of them to make copying work in GNOME Terminal.

`TKCURSES_CLIPBOARD_SYSTEM` chooses: `auto` (the default, as above),
`osc52`, `command`, or `off` to keep the clipboard inside the program. A
copy that could not leave is reported once, on standard error, when the
program ends.

Selected text goes the same way to the desktop's *primary selection*, which
a middle click pastes in other applications, as it would from a Tk program
on X11. It is sent once the selection stops changing, not on every movement
of the mouse. `TKCURSES_CLIPBOARD_PRIMARY=0` keeps it inside: on GNOME,
`wl-copy` may show a window of its own for a moment each time.

% expect: Copy

```python
import tkcurses as tk

root = tk.Tk()
code = tk.Entry(root, width=20)
code.insert(0, "TK-4471")
code.pack()
status = tk.Label(root, text="")


def copy():
    root.clipboard_clear()
    root.clipboard_append(code.get())
    status.config(text=f"Copied {root.clipboard_get()}")


tk.Button(root, text="Copy", command=copy).pack()
status.pack()
root.mainloop()
```

## Unicode

Text is Unicode throughout, and anything the terminal's font can draw can
be shown. Chinese, Japanese and Korean characters and most emoji take two
cells of the screen, and an accent written as a separate combining
character takes none. Every widget measures text that way: it is sized,
wrapped and aligned by the cells it takes, and a cursor and a click land
on the right character.

## Leaving, and getting the terminal back

A program changes the terminal while it runs: it switches to the alternate
screen, hides the cursor, turns on mouse reporting and reads keys one at a
time. All of it is undone when the program ends, however it ends -
`destroy()`, `quit()` and falling off the end, Ctrl-C, or an uncaught
exception, whose traceback is printed after the terminal is restored so
that it can be read.

**Ctrl-Z** suspends the program, as in any terminal program: the shell
comes back as it was, without mouse reports or marked pastes, and `fg`
brings the program back, redrawn, with the keyboard and the mouse working
as before. A program that binds `<Control-z>` gets the key
instead, and so does a Text with `undo=True` while it has the focus, which
undoes.

If a program is killed with `kill -9`, nothing can restore the terminal.
Type `reset` and press Return, even if you cannot see what you type.

## Settings

Each of the settings above is an environment variable, set for one run
(the [configuration reference](../reference/configuration.md) describes
every setting in full):

```console
$ TKCURSES_MOUSE_CLICK_INTERVAL=400 python3 app.py
```

or the same setting in a file, `~/.config/tkcurses/tkcurses.ini` for one
user (under `$XDG_CONFIG_HOME` if that is set) or
`/etc/tkcurses/tkcurses.ini` for everyone. An environment variable wins
over the user's file, and the user's file over the system's:

```ini
[mouse]
click_interval = 400

[input]
escape_delay = 100

[clipboard]
system = command
```

| Environment variable | In the file | Default |
|---|---|---|
| `TKCURSES_DISPLAY_COLOR_MODE` | `[display] color_mode` | `auto` |
| `TKCURSES_DISPLAY_UNICODE` | `[display] unicode_borders` | on |
| `TKCURSES_INPUT_ESCAPE_DELAY` | `[input] escape_delay` | 25 |
| `TKCURSES_INPUT_BRACKETED_PASTE` | `[input] bracketed_paste` | on |
| `TKCURSES_MOUSE_ENABLED` | `[mouse] enabled` | on |
| `TKCURSES_MOUSE_CLICK_INTERVAL` | `[mouse] click_interval` | 200 |
| `TKCURSES_MOUSE_REPORT_MOTION` | `[mouse] report_motion` | on |
| `TKCURSES_MOUSE_REPORT_HOVER` | `[mouse] report_hover` | off |
| `TKCURSES_CLIPBOARD_SYSTEM` | `[clipboard] system` | `auto` |
| `TKCURSES_CLIPBOARD_PRIMARY` | `[clipboard] primary` | on |
| `TKCURSES_DISPLAY_DIRECT_IMAGES` | `[display] direct_images` | on |

`TKCURSES_DISPLAY_DIRECT_IMAGES=0` draws pictures through curses' own
colours rather than past them, for a terminal that shows them wrongly.
A value that cannot be read is ignored and the default used, and a number
out of range is brought within it, so a mistyped setting never stops a
program from starting. Each is reported when the program ends, once the
terminal is back, as is a setting that earlier versions accepted and that
no longer does anything.
