# XYChart

A line and area chart: series of numbers against numbers or times, as
lines, areas stacked or not, with axes, reference lines, a legend with
statistics, and a crosshair the keys and the mouse move. It is a
Canvas, so a program can draw on it too.

```{eval-rst}
.. automodule:: tkcurses.xychart

.. autoclass:: tkcurses.xychart.XYChart
   :members: add_series, set_series, append, delete_series, series,
      series_points, series_cget, series_configure, reference_add,
      reference_delete, references, cursor, legend_focus, configure,
      destroy

.. autodata:: tkcurses.xychart.CURSOR_EVENT

.. autodata:: tkcurses.xychart.LEGEND_EVENT

.. autodata:: tkcurses.xychart.NATURAL_SIZE
```
