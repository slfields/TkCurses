# Line and area charts

`XYChart` draws series of numbers against numbers or times: response
times through a day, requests a second as they come in, a thermometer's
readings with the hours it missed. Each series is a line, or an area
filled down to the one beneath it.

It is a **TkCurses widget**, after Kibana's line and area charts.
Neither tkinter nor Tk has a chart, so a program that uses one runs on
TkCurses only, and it is imported from a module of its own:

```python
import tkcurses as tk
from tkcurses.xychart import XYChart
```

In every other way it is a widget like the rest. It is placed with
`pack`, `grid` or `place`, and takes its options when it is made or
later from `configure`. A bad value raises `TclError` and changes
nothing. It is also a `Canvas`: a program can draw its own items on it,
and they stay on top of the chart. The
[reference](../reference/exclusive/xychart.md) describes every option
and method, each option with a picture.

The three programs below are in the
[`examples`](https://github.com/slfields/TkCurses/tree/master/examples)
directory. Each picture was taken by running the program while this
documentation was built.

## Times, references and the crosshair

`add_series(name, points)` adds a series: a list of `(x, y)` pairs,
where x is a number or a `datetime` and y a number, or `None` for a
value that is missing. Every series in a chart has the same kind of x.
With times, the axis is labelled with the clock, and the row under it
says the date.

`reference_add` draws a line across the chart at a value - a target, a
limit - or, with `axis="x"`, down it at an x. A `band` shades a range as
well: here, the hour after a deploy.

The chart takes the keyboard focus. The left and right arrows move a
*crosshair* from x to x, Home and End to the first and last, and a
click puts it at the x nearest the mouse; Escape takes it away. The
bottom row, the *readout*, writes each series' value at the crosshair
in its colour. `<<XYChartCursor>>` is sent whenever the crosshair
moves, and `cursor()` says where it is: this program uses them to say
whether the slowest requests were over the target.

```{tkcurses-example} examples/latency.py
:size: 72x20
:keys: ["<End>", "<Left>", "<Left>", "<Left>"]
```

The legend, at the bottom here, names each series in its colour, with
any of sixteen statistics - here the highest value. A click on an
entry hides its series, and another shows it again; that sends
`<<XYChartLegend>>`, and `legend_focus()` names the series.

## Areas, stacked and live

A series with `kind="area"` is filled. Areas are stacked by default,
each on the one before, so the top line is the total. With
`stackmode="percentage"` each is its share of the total, and with
`"unstacked"` each is filled from zero on its own.

Data that keeps coming is the program's to fetch, on its own timer:
`append` adds a point to a series, and `set_series` replaces them all,
here to drop the oldest. However many changes come at once, the chart
draws once the program is idle, so nothing flickers. Press **s** to step
the stacking.

```{tkcurses-example} examples/traffic.py
:size: 60x16
:live: 3
```

## Missing values

A missing value is `None`. By default it is left as a gap; `missing`
can instead set it to zero, join the values either side straight, hold
the last value, or take the next. `endvalues` does the same for the
missing values before the first and after the last, and `dottedgaps`
dots whatever was filled in, so no one takes it for a reading.

The legend's statistics are of what each line draws: as **m** fills
the gaps, the count of values goes up. Press **m** to step `missing`
and **d** to dot what it fills. The picture shows `linear`, dotted.

```{tkcurses-example} examples/sensors.py
:size: 60x16
:keys: ["m", "m", "d"]
```

The [reference](../reference/exclusive/xychart.md) has the options this
page leaves out: `interpolation` and `points` for how values are
joined; `scaletype` and `bounds` for the value axis; `xlabel`, `ylabel`,
`gridlines` and the number formats for the axes; `legendposition`,
`legendsize` and `legendlines` for the legend; `readout`; and `width`
and `height`, which each take cells or a percentage of the terminal.
