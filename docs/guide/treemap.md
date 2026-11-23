# Treemaps

`TreeMap` draws named values as rectangles, each as large as its share
of the whole: where a server's memory goes, what fills a disk, which
parts of a budget are largest. Related items sit together in a group,
in shades of the group's colour.

It is a **TkCurses widget**, after Kibana's treemap charts. Neither
tkinter nor Tk has a treemap, so a program that uses one runs on
TkCurses only, and it is imported from a module of its own:

```python
import tkcurses as tk
from tkcurses.treemap import TreeMap
```

In every other way it is a widget like the rest. It is placed with
`pack`, `grid` or `place`, and takes its options when it is made or later
from `configure`. A bad value raises `TclError` and changes nothing. Its
items are added and changed as a `ttk.Treeview`'s are. The
[reference](../reference/exclusive/treemap.md) describes every option and
method, each option with a picture.

The two programs below are in the
[`examples`](https://github.com/slfields/TkCurses/tree/master/examples)
directory. Each picture was taken by running the program while this
documentation was built.

## Groups, values and the legend

`insert` adds an item and returns its identifier, as a Treeview's does.
An item at the top level with items of its own is a *group*: its size is
the sum of theirs, and their tiles are drawn inside its own, under a
header with its name. A treemap has these two levels and no more. An
item's `value` is its size, a number not below zero; an item of zero
takes no room.

Tiles are laid out largest first, each as near square to the eye as the
squarified algorithm makes them in a terminal's tall cells. Each tile
says its name and, by default, its share as a percentage; with
`values="value"` it says the number itself, in `units`, and with
`"none"` nothing. Text too long for its tile is cut with `…`, or left
out when too little would be left.

The legend, on the right by default, names each group in its colour.
`legendposition` moves it to any side, and `nestedlegend` lists each
group's items under it. An item's `description` is written in the legend
under its name, and nowhere else: a place to say what a group is
without crowding its tile.

This program shows a server's memory. Press **v** to step the values,
**p** to move the legend and **n** to list each group's items in it.

```{tkcurses-example} examples/services.py
:size: 60x16
```

The bottom row is the *readout*. With nothing focused it says the total;
it also counts the items too small to have even one cell, which are left
out of the picture rather than drawn wrongly.

## Acting on what is chosen

A treemap takes the keyboard focus. The arrow keys move it from tile to
tile, the focused tile drawn reversed, and the readout names it, with
its value and its share of everything and of its group. **Space**, or a
click, selects it and sends `<<TreeMapSelect>>`; `selection()` says which
item it was. **Return** on a group, or a double-click, *zooms in*: the
group's items fill the treemap, and `<<TreeMapZoom>>` is sent. **Escape**
zooms back out.

To act on some items only, give them `tags` and bind to a tag, as in a
Treeview: `tag_bind("disk", "<<TreeMapSelect>>", check)` calls `check`
only when an item tagged `disk` is chosen. A tag on one item alone acts
on that item alone.

This program says what each choice was, checks the disk of the two
databases, and flushes the cache. Click a tile, or use the arrows and
**Space**; **Return** on a group zooms in.

```{tkcurses-example} examples/actions.py
:size: 60x14
:keys: ["<Right>", "<Right>", " "]
```

The [reference](../reference/exclusive/treemap.md) has the options this
page leaves out: `labels`, `percentdecimals` and the number formats for
the text on tiles; `outline` and `colors` for how tiles are told apart;
`legend`, `legendsize` and `legendlines` for the legend; `readout`; and
`width` and `height`, which each take cells or a percentage of the
terminal.
