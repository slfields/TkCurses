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

## License

GPL-3.0-only. See [LICENSE](LICENSE).
