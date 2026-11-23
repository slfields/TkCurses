# TreeMap

A treemap: named values drawn as rectangles, each as large as its share,
in two levels - groups and the items in them - with a legend, the keys
and the mouse. The [treemap guide](../../guide/treemap.md) shows it at
work in two programs.

```{eval-rst}
.. automodule:: tkcurses.treemap

.. autoclass:: tkcurses.treemap.TreeMap
   :members: insert, item, delete, move, get_children, parent, index, exists,
      focus, selection, selection_set, zoom, identify, tag_has, tag_bind,
      configure, destroy

.. autodata:: tkcurses.treemap.SELECT_EVENT

.. autodata:: tkcurses.treemap.ZOOM_EVENT

.. autodata:: tkcurses.treemap.PATH_SEPARATOR

.. autodata:: tkcurses.treemap.NATURAL_SIZE
```
