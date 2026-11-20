# TkCurses widgets

Widgets that only TkCurses has. Neither tkinter nor Tk has anything like
them, so a program that uses one runs on TkCurses only, and each is
imported from a module of its own rather than from `tkcurses`:

```python
import tkcurses as tk
from tkcurses.bargraph import BarGraph
```

Each one is marked **TkCurses extension** throughout. Otherwise it is
documented, and behaves, as the classic widgets do: it is placed with
`pack`, `grid` or `place`, it takes options at creation and from
`configure`, and a bad option raises `TclError` and changes nothing.

```{toctree}
:maxdepth: 1

bargraph
```
