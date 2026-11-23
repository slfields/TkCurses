# Acceptance: treemaps

`Treemap` is a widget only TkCurses has, after Kibana's treemap charts.
What it should look like is what
[ARCHITECTURE.md](../ARCHITECTURE.md#treemap) designs. The automated tests
check that tiles cover their area exactly, that labels fit, and which
colour lands in which cell. They cannot tell whether a tile *looks*
square in your font, whether two shades are told apart on your
terminal, or whether a layout reads well. This checklist is for those.

There are two passes over the same scenario. **Pass 1**, run as soon as
tiles drew, checks the tiles. **Pass 2** checks the legend, item
descriptions, the keys and the mouse, and sizes given as a share of the
screen.

**How to run**, from the repository root:

```bash
python3 -m uat 52                     # your terminal as it is
TERM=xterm python3 -m uat 52          # eight colours
TERM=vt100 python3 -m uat 52          # no colour
```

Escape ends it. Use a terminal at least 80×24. Line 4 of the screen says
which colours TkCurses found and the options in force, line 5 the
legend's options and the size, and line 6 what is selected and zoomed.

| | |
|---|---|
| Terminal and font | |
| Size | |
| Colours (`tput colors`, and whether `COLORTERM` says truecolor) | |
| Date / version | |

---

## The one that matters most

After each run, **the terminal still works**: prompt back, cursor
visible, typing echoed.

## 52. Square to the eye

`python3 -m uat 52`, then **n** for 24 items.

- [ ] Most tiles look **near square, or a little wider than tall**, in
      your font. A tile is laid out as if a cell were twice as tall as it
      is wide; if your font's cells are much nearer square, tiles look
      tall and thin, and that is worth writing down with the font's name
- [ ] Larger values have larger tiles, laid from the top left: in each
      group the largest is at its top left, the smallest towards its
      bottom right
- [ ] No gap and no overlap anywhere: every cell of the treemap belongs
      to one tile or one header
- [ ] **Resize** the terminal narrower and wider. The treemap lays out
      again to fill it, and nothing is left behind where a tile was
- [ ] **n** again comes back to the services

## 52. Shades

At 256 colours or truecolor, with `outline=auto`.

- [ ] Each group is **one colour**: web green, db red, cache blue (with
      24 items: a green, b red, c blue, d yellow). The header row is the
      colour itself, in bold
- [ ] Inside a group, **no two tiles side by side have the same shade**.
      You can tell where each child ends without a line between them
- [ ] Text on each tile is **readable**: black on green, yellow and
      cyan; white on red, blue and magenta
- [ ] If a group's children run together, so two neighbours look the
      same to you, write down which and the terminal. The widget counts
      shades the terminal's palette rounds together, and outlines such a
      group by itself; it cannot know what your eyes see

## 52. Outlines

- [ ] Press **o**: `outline=on`. Lines now divide every tile, and groups
      from each other. Where lines meet they **join** - `┬`, `├`, `┼`,
      `┤`, `┴` - with no gap and no doubled line
- [ ] **o** again: `outline=off`. No lines anywhere, even where shades
      are close. **o** once more is back to `auto`
- [ ] `TERM=xterm python3 -m uat 52` (line 4 says `colours 8`). Each
      group's children are **outlined in black lines on the group's
      colour**; groups are told apart by colour alone, with no line
      between them
- [ ] `TERM=vt100 python3 -m uat 52` (`colours none`). **Everything** is
      outlined and nothing is coloured. Group headers are bold. You can
      still read which tile is which

## 52. Labels and values

- [ ] Each tile's name is on its top row and its share on the row under
      it: `nginx`, `38.82%`. A group's header holds both: `web 64.71%`
- [ ] A name too long for its tile ends in `…` and stays inside it. A
      value that does not fit is **left out, never cut**: no `16.4` for
      `16.47%`
- [ ] In a tile one row high, name and value share the row when both
      fit, and the value goes when they do not
- [ ] **v** steps through `value` (the numbers: `330`, `170`), `none`
      (names only) and back to `percent`
- [ ] **l** takes the names away, leaving the values on the top row; **l**
      again brings them back

## 52. Changes and small tiles

- [ ] Hold **+**: nginx grows, the percentages change, and the layout
      follows **at once**, with no flicker or half-drawn frame. Hold
      **-** to shrink it; at 0 it takes no room at all
- [ ] Press **t**: an item of 0.5 is added, too small for a cell. Nothing
      new is drawn, and the bottom line says `total 850.5 · 1 too small
      to show`. **t** again takes it away, and the count goes
- [ ] The bottom line always says the total, in the same number format
      as the values

---

# Pass 2: the legend, the keys and the size

`python3 -m uat 52` again, at 256 colours or truecolor. Start from the
services each time unless a step says otherwise.

## 52. The legend

- [ ] On the right, beside the tiles, a `│` and then one entry per
      top-level item, **largest first**: `██ web`, `██ db`, `██ cache`.
      Each swatch is **its group's colour**: green, red, blue
- [ ] The legend **never covers a tile**; the tiles are narrower to make
      room, and the bottom row runs the whole width under both
- [ ] **g** steps line 5's `legend=` through `show`, `hide` and `auto`.
      `hide` takes it away and the tiles fill the width; `auto` and `show`
      bring it back
- [ ] Make the terminal **narrow**, about 30 columns. The legend goes
      before the tiles get too small to read, and comes back when it is
      wider
- [ ] **TERM=vt100** (no colour): the tiles are boxed in lines, and there
      is **one** line between them and the legend, not two side by side

## 52. Position and size

- [ ] **p** moves it **left** (its line now on its right), **top** (a `─`
      under it, entries across in columns), **bottom** (a `─` above it,
      over the bottom row), and back to **right**
- [ ] At the top or bottom it takes **at most a third** of the height;
      what does not fit ends with a `+N more` line
- [ ] **s** steps `size=` through `small`, `medium`, `large`, `xlarge`
      and `auto`. Each is wider than the one before; `auto` is as wide as
      its longest entry needs, but never more than a third of the treemap.
      Names too long for `small` end in `…`

## 52. Nested entries, wrapping and descriptions

- [ ] **e** (`nested=1`): each group's children are listed under it,
      **indented two cells**, each swatch the shade its tile has
- [ ] **d** (`desc=1`): a description appears **under** web, db and
      cache, and under nginx when nested, **lined up with the name**, not
      the swatch. The **name is bold and the description plain**, so the
      two are told apart at a glance. It appears **nowhere else**: not in
      any tile, not on the bottom row, even with nginx focused
- [ ] With **w** at `lines=1`, the long description of web ends in `…`.
      **w** to `lines=2`: it wraps onto a second line. A name too long for
      its line wraps the same way, at a space where there is one
- [ ] **s** to `small` with descriptions on: the **names stay** and the
      descriptions are cut first, before entries go to `+N more`
- [ ] **n** for 24 items, with **d** on: the groups a, b, c and d keep
      their descriptions

## 52. Keys, focus and selection

- [ ] Press **Right**. The largest tile is **focused**: its name reversed,
      or its header if it is a group's. Its **legend entry's name is
      reversed too**, but not its swatch
- [ ] The bottom row names the focused item: `web › nginx   330   38.82%
      of all   60.00% of web`
- [ ] The **arrows** move to the next tile that way on the same level, and
      the **opposite arrow comes back** to where it was
- [ ] **Space** selects the focused item: a `●` before its name, line 6
      counts one more `TreemapSelect`
- [ ] **Return** on a group **zooms in**: its children fill the treemap,
      line 6 says `zoom web` and counts a `TreemapZoom`, and the legend
      now lists the **children**. **Escape** zooms back out, one more
      `TreemapZoom`, with the focus on the group
- [ ] Not zoomed, with the focus on a **child** (click nginx), **Escape**
      moves it to the group. With the focus on a top-level item, Escape
      ends the scenario

## 52. The mouse

- [ ] **Click** a tile: it is focused and selected (`●`, one more
      `TreemapSelect`). A click on a group's header is the group
- [ ] **Double-click** a tile in a group: the group zooms in
- [ ] **Click a legend entry**: that item is **focused but not selected**
      (no `●`, the count unchanged); the bottom row names it. With **t**
      the tiny item has no tile, yet clicking its legend entry names it on
      the bottom row

## 52. Size

- [ ] **z** (`size: 50% x 50%`): the treemap is **half the screen wide
      and half as tall**, at the top left of the area, legend included
- [ ] **Resize** the terminal wider and taller. It stays **half** of the
      new size; the instructions on line 5 still say `50% x 50%`
- [ ] **z** (`60 x 50%`): **60 columns** whatever the terminal's width,
      and half its height. Resizing changes only the height
- [ ] **z** (`width 30`): 30 columns and **12 rows**; it does not vanish,
      as it would have before this pass
- [ ] **z** once more fills the area again

