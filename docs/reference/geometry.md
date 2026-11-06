# Geometry managers

A widget appears once a geometry manager has placed it in its parent. Every
widget has the three managers' methods - `pack`, `grid` and `place` - and
a parent's children may use only one of `pack` and `grid` between them.

```{eval-rst}
.. autoclass:: tkcurses.Pack
   :members:

.. autoclass:: tkcurses.Grid
   :members:

.. autoclass:: tkcurses.Place
   :members:
```
