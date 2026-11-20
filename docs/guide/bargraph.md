# Bar graphs

`BarGraph` draws bars in a terminal, an eighth of a character cell at a
time: a few figures side by side, meters that follow a value as it
changes, a short history.

It is a **TkCurses widget**. Neither tkinter nor Tk has a bar graph, so a
program that uses one runs on TkCurses only, and it is imported from a
module of its own:

```python
import tkcurses as tk
from tkcurses.bargraph import BarGraph
```

In every other way it is a widget like the rest. It is placed with
`pack`, `grid` or `place`, and takes its options when it is made or later
from `configure`. A bad value raises `TclError` and changes nothing. The
[reference](../reference/exclusive/bargraph.md) describes every option,
each with a picture.

The three programs below are in the
[`examples`](https://github.com/slfields/TkCurses/tree/master/examples)
directory. Each picture was taken by running the program while this
documentation was built.

## Bars and series

A graph has `segments` bars, and each bar holds `series` values, one per
colour in `colors`. `set_all` gives every bar its values at once, a list
of lists; `set` replaces one bar's; `get` reads one bar's back.

The series in a bar are `stacked` end to end by default, so the bar is
as long as their total. With `mode="overlay"` each is drawn from zero,
behind the shorter ones, so the longest decides the bar's length.
`orient="horizontal"` lays the bars down. `labels` names each bar, and
`label` with `borderwidth=1` puts the whole graph in a titled box.

This program shows four quarters of three products' sales. Press **m**
to switch stacked and overlay, and **o** to turn the graph on its side.

```{tkcurses-example} examples/bars.py
:size: 60x16
```

Bars lying down are given a `thickness` of two rows rather than four. By
default a bar is drawn to `scale="100%"`, the whole length the graph has,
and `thickness` is then the least a bar is across: rows to spare go to
the bars, so they may differ by one.

## Live values

A graph can fetch its own values. `source` is a function of no arguments
that returns what `set_all` takes, and the graph calls it every
`refreshinterval` milliseconds. Values that come from somewhere else are
given to the graph with `set_all` or `set` whenever they arrive; it draws
at most once each `refreshinterval`, however often they change.

`thresholds` recolour the part of a bar beyond a level, here yellow above
70% and red above 90%. `peakholdtime` leaves a mark at the highest value
a bar reached for that many milliseconds after it falls. `readout` writes
each bar's value beside it.

With `maximum="auto"` the scale follows the values. It grows the moment a
value would not fit, and shrinks only once the values have stayed under
a lower round number for `autoscaledelay` milliseconds - and then only as
far as they needed in that time - so a graph that keeps changing does not
keep jumping. The request history below, the last three seconds, grows
for each burst and shrinks back in steps once the burst has passed.

```{tkcurses-example} examples/meters.py
:size: 60x20
:live: 9
```

## Axes, numbers and colours

`axis` draws a value axis with tick labels; `ticks` puts the ticks where
a list says, and `gridlines` draws a dim line across the graph at each.
`markers` draws a line at a level of its own, such as a limit. `baseline`
draws a line along the bars' zero edge.

A log scale, `scaletype="log"`, gives each power of `logbase` the same
length, so values from milliseconds to minutes fit on one graph. It cannot
stack series - equal lengths on it are equal ratios, not equal amounts -
so give it one series or `mode="overlay"`. `minimum` is where the bars
start, here at 1 ms.

Numbers on the axis and in the readout are written in `units`, after the
number or, with `unitplacement="prefix"`, before it. `digits` sets how
many significant digits they keep. `unitscale` chooses how a large or
small number is shortened: by thousands (`"si"`, the default), by 1024s
for bytes (`"binary"`), or into the largest unit of time it reaches
(`"time"`, where `units` names the unit the values are in).

`colormode="gradient"` shades each bar by how far along the scale it
reaches, from `gradientstart` at zero to the series colour at the
maximum: smoothly on a truecolor terminal, in bands at 256 colours, and
not at all with fewer.

```{tkcurses-example} examples/scales.py
:size: 80x24
```

The [reference](../reference/exclusive/bargraph.md) has the options this
page leaves out: `labelanchor` and `labelwidth` for the labels, `gap` and
`thickness` for spacing, `readoutformat`, `decimals` and `rounding` for
the numbers, and `axislabel` for naming the axis.
