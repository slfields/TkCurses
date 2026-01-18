# TkCurses

A tkinter-compatible API layer that renders to curses terminals.

## Overview

TkCurses provides a drop-in replacement for tkinter that renders to terminal-based curses interfaces instead of graphical windows. This allows existing tkinter applications to run in terminal environments with minimal code changes.

## Installation

```bash
pip install tkcurses
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
import tkcurses as tk

root = tk.Tk()
root.title("Hello TkCurses")
root.mainloop()
```

## Features

- Tkinter-compatible API
- Curses-based rendering
- Window management (Tk, Toplevel)
- Variable classes (StringVar, IntVar, DoubleVar, BooleanVar)
- Event binding system
- Focus management
- Clipboard support

## Requirements

- Python 3.10+
- POSIX terminal with curses support

## License

PSF-2.0
