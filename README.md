# TkCurses

A tkinter-compatible API layer that renders to curses.

TkCurses mirrors tkinter's module structure, classes, and method signatures, but
translates widget calls into `curses` and `curses.panel` operations. Familiar
tkinter-style code runs entirely in a terminal — no Tk, no Tcl, no X11 or
Wayland, no graphical display of any kind.

```python
import tkcurses as tk

root = tk.Tk()
tk.Label(root, text="Hello, terminal").pack()
tk.Button(root, text="Quit", command=root.destroy).pack()
root.mainloop()
```

**Status: release candidate.** The first release candidate is
[`v0.3.0rc1`](https://github.com/slfields/TkCurses/releases). The classic and
themed widget sets, the dialogs and the curses module are in, and are measured
against Tk 9.0.2 rather than written from its manual. What is still missing is
listed [below](#known-gaps). See [CHANGELOG.md](CHANGELOG.md) for what each
release contains.

## Porting a tkinter program

Change the import, and nothing else:

```python
import tkcurses as tk                     # was: import tkinter as tk
from tkcurses import ttk, messagebox      # was: from tkinter import ttk, messagebox
```

Widgets are laid out in character cells, so a size given in pixels to tkinter
is a size in cells here: a `Frame(width=40, height=10)` is 40 columns by 10
rows.

## What is there

- **Classic widgets:** `Tk`, `Toplevel`, `Frame`, `Label`, `Button`,
  `Checkbutton`, `Radiobutton`, `Entry`, `Spinbox`, `Scale`, `Scrollbar`,
  `Listbox`, `Text` (with peers, tags, marks, undo and search), `Canvas`,
  `Menu`, `Menubutton`, `OptionMenu`, `Message`, `LabelFrame` and
  `PanedWindow`.
- **Themed widgets (`tkcurses.ttk`):** the themed counterparts of the classic
  set, plus `Notebook`, `Combobox`, `Treeview`, `Progressbar`, `Separator`,
  `Sizegrip` and `LabeledScale`, with `Style` and themes.
- **Geometry managers:** `pack`, `grid` and `place`, with Tk's negotiation and
  propagation.
- **Events and bindings:** Tk's binding rules, multi-event sequences
  (`<Control-x><Control-s>`), virtual events, `event_generate`, focus
  traversal, and the mouse - clicks, double and triple clicks, drags and the
  wheel - in terminals that report it.
- **Dialogs:** `messagebox`, `filedialog`, `simpledialog`, `colorchooser`,
  `dialog`, `commondialog`, `scrolledtext` and `dnd`.
- **Colour and images:** whatever colour depth the terminal has, from 8
  colours to direct colour; `PhotoImage` and `BitmapImage`, reading PNG, GIF,
  netpbm and XBM.
- **Clipboard:** inside the application, and out to the desktop through OSC 52
  or the desktop's own clipboard tool.
- **`tkcurses.curses` and `tkcurses.panel`:** the curses API drawn on the same
  screen, so one program can mix curses windows and tkinter widgets.

## Known gaps

Missing pieces are tracked as issues. The larger ones:

- Some of Tk 9.0's options are refused by some widgets, both classic and
  themed. Unknown options raise `TclError`, as Tk's do.
- Some methods are missing: the Canvas tag and transform family, `Text.dump`,
  `Text.count` and embedded windows, tear-off menus, the `Wm` icon family, the
  `busy` family, and the geometry managers' method aliases.
- tkinter's module-level `mainloop`, `TkVersion`, `TclVersion`, `EventType`,
  `getint`/`getdouble`/`getboolean`, `image_names` and `image_types` do not
  exist yet. Use `root.mainloop()`.
- `<Enter>` and `<Leave>` are not delivered when the pointer crosses a widget.

## Requirements

- Python 3.10 or later; every release is tested on 3.10 to 3.14.
- A POSIX system: Linux, where every release is tested. It should work on macOS,
  but it is not tested there. **It does not work on Windows**, where Python has
  no `termios`. It may work under WSL.
- A terminal with curses. A mouse and colour are used when the terminal offers
  them, and are not required.

There are no runtime dependencies beyond the standard library.

## Installation

The release candidate:

```bash
pip install "tkcurses @ git+https://github.com/slfields/TkCurses@v0.3.0rc1"
```

Or download the wheel attached to the
[release](https://github.com/slfields/TkCurses/releases) and
`pip install` it. TkCurses is not on PyPI.

The latest development version, which `-U` keeps up to date - every commit
has its own version, taken from git:

```bash
pip install -U git+https://github.com/slfields/TkCurses
```

Then try the demo:

```bash
tkcurses-demo
```

## Configuration

Optional. An INI file, `~/.config/tkcurses/tkcurses.ini` (or under
`$XDG_CONFIG_HOME`), with `/etc/tkcurses/tkcurses.ini` read first, and
`TKCURSES_*` environment variables over both. It holds the colour depth, the
escape delay, mouse reporting, Unicode or ASCII borders, the clipboard route and
debug logging. Every setting is in [ARCHITECTURE.md](ARCHITECTURE.md) under
*Runtime Configuration*.

## Development

```bash
pip install -e ".[dev]"
ruff check .            # lint
ruff format --check .   # formatting
mypy                    # type-check (strict)
pytest -n 4             # the full suite, in parallel
pytest -m "not tty"     # skip the tests that drive a real pty
```

Widgets are verified by rendering them in a real pseudo-terminal and asserting
against the emulated screen, rather than by manual inspection. Tests marked
`tty` fork a pty, run the application under it, and read the resulting
character grid back through [pyte](https://github.com/selectel/pyte). What a
test cannot see is checked by a person: the scenarios under `uat/`, with their
checklists in `docs/UAT_*.md`.

Releases are cut by pushing a `v*` tag, which runs the release workflow. See
[CLAUDE.md](CLAUDE.md).

## Documentation

[ARCHITECTURE.md](ARCHITECTURE.md) is the specification of record: module
mapping, class hierarchy, rendering rules, input handling, configuration, and a
complete tkinter-to-TkCurses API reference.

## Acknowledgements

TkCurses is an independent reimplementation, and it stands on others' work:

- **Tcl and Tk**, by the Regents of the University of California, Sun
  Microsystems, Scriptics, ActiveState, Apple and many others. Tk is the
  behaviour TkCurses is measured against, and where its documentation is
  silent the rules were read from Tk's and Tcl's own library scripts and
  followed. Used under the Tcl/Tk licence.
- **tkinter**, part of CPython, by the Python Software Foundation and its
  contributors. TkCurses reimplements its interface so that tkinter programs
  run unchanged, and two modules (`dnd`, `simpledialog`) adapt code from it.
  Used under the Python Software Foundation License Version 2.
- **chafa**, by Hans Petter Jansson, read as a reference for the image and
  colour path. No code was taken from it.

The Tcl/Tk and PSF licences are permissive and compatible with the GPL. Their
full texts, and what was taken from each and how, are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), which is also shipped in
every built package.

## Author

Scott L. Fields.

## License

Copyright (C) 2026 Scott L. Fields.

TkCurses is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License **version 3** as published by the Free
Software Foundation.

It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details, in
[LICENSE](LICENSE) or at <https://www.gnu.org/licenses/gpl-3.0.html>.

`GPL-3.0-only`, not `-or-later`: every source file carries the notice in that
form, and `tkcurses.NOTICE` is the short version for a program to show when it
starts.
