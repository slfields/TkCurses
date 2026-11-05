# TkCurses

**Graphical-style user interfaces that run in a terminal.**

TkCurses gives Python programs windows, buttons, text fields, lists, menus
and dialogs, drawn with text in any terminal: over SSH, on a server with no
display, in a container. It speaks the API of
[tkinter](https://docs.python.org/3/library/tkinter.html), Python's standard
GUI toolkit, so a program written for one reads naturally in the other. You
do not need to know tkinter to use it.

```python
import tkcurses as tk

root = tk.Tk()
tk.Label(root, text="Hello from the terminal").pack()
tk.Button(root, text="Quit", command=root.destroy).pack()
root.mainloop()
```

:::{note}
This documentation is being written. The guides and the API reference arrive
over the coming releases; the [changelog](about/changelog.md) lists what the
library already does.
:::

```{toctree}
:caption: Guides
:maxdepth: 2

guide/index
```

```{toctree}
:caption: Reference
:maxdepth: 2

reference/index
```

```{toctree}
:caption: About
:maxdepth: 1

about/changelog
about/license
about/notices
```
