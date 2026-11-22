# Acceptance: treemaps, pass 1

`Treemap` is a widget only TkCurses has, after Kibana's treemap charts.
What it should look like is what
[ARCHITECTURE.md](../ARCHITECTURE.md#treemap) designs. The automated tests
check that tiles cover their area exactly, that labels fit, and which
colour lands in which cell. They cannot tell whether a tile *looks*
square in your font, whether two shades are told apart on your
terminal, or whether a layout reads well. This checklist is for those.

This is the first of two passes, run as soon as tiles draw. The second,
after the legend and the keys exist, checks those.

**How to run**, from the repository root:

```bash
python3 -m uat 52                     # your terminal as it is
TERM=xterm python3 -m uat 52          # eight colours
TERM=vt100 python3 -m uat 52          # no colour
```

Escape ends it. Use a terminal at least 80×24. Line 4 of the screen says
which colours TkCurses found, and the options in force.

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
