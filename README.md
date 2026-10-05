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

> **Status: pre-alpha, under active rebuild.** The public API is being
> implemented against [ARCHITECTURE.md](ARCHITECTURE.md); most widgets are not
> yet available.

## Requirements

- Python 3.10+
- A POSIX terminal with `curses` (standard library on Linux and macOS; Windows
  needs `windows-curses`)

## Installation

```bash
pip install -e ".[dev]"
```

## Development

```bash
ruff check .        # lint
mypy                # type-check (strict)
pytest              # test
pytest -m "not tty" # skip tests that drive a real pty
```

Widgets are verified by rendering them in a real pseudo-terminal and asserting
against the emulated screen, rather than by manual inspection. Tests marked
`tty` fork a pty, run the application under it, and read the resulting
character grid back through [pyte](https://github.com/selectel/pyte).

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
