# Acceptance: how classic widgets behave

Four questions, from `TkCurses-gm66.5`, `.6`, `.8` and `.9`:

- **Is each relief its own box, and does a part held down sink?**
- **Does holding a mouse button down repeat, as it does in Tk?**
- **Does a Text's line spacing put blank rows where Tk puts space?**
- **Do a paned window's sash options and its proxy behave as Tk's?**

Until this cycle every option here was refused, and a tkinter program that
passed one stopped at that line.

```bash
cd /path/to/TkCurses
python3 -m uat 49
```

**The readout** counts the held button's firings, shows the scale's value,
the list's top item, and whether the scrollbar jumps; then the Text's spacing,
how many undo steps it holds, and whether the paned window is opaque. Use these
keys:

- **F5** turns the scrollbar's `jump` on and off.
- **F6** turns the Text's spacing off and on.
- **F7** turns the paned window's `opaqueresize` off and on.
- **F8** undoes one step in the Text. *A Text here has no undo key of its own
  yet, `TkCurses-sjot`; F8 stands in for Tk's Ctrl-Z.*
- **F9** moves the focus.
- **Escape** quits.

| | First terminal | Second terminal |
|---|---|---|
| Terminal and version | GNOME Terminal | not run |
| `$TERM` | | |
| Size | | |
| Date | 2026-11-03 | |
| Result | **Accepted.** Run by the author, after the sash fix below: "All the tests in uat 49 pass". | |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. What was driven mechanically, and so is on the record, is the
scenario 49 tests in `tests/test_uat_scenarios_tty.py`.

## Reliefs

The top row is six Labels, each `borderwidth=1` in one relief, and a
Checkbutton with no indicator.

- [ ] **flat**: no box at all, only the word
- [ ] **raised**: a box drawn **bold**
- [ ] **sunken**: a box drawn **dim**
- [ ] **solid**: a plain box, neither bold nor dim
- [ ] **ridge**: a **double** line all round
- [ ] **groove**: double along the top and bottom, single at the sides
- [ ] **toggle**, off: a groove box, its `offrelief`. Click it: a **dim**
      box, sunken, as Tk draws an indicatorless button that is on. Click
      again: groove again
- [ ] The Spinbox's **▲** is dim and its ▼ is not: `buttonuprelief=sunken`

## Holding a button down

Each repeats only after a pause, its `repeatdelay`, then every
`repeatinterval`, and stops when you let go.

- [ ] **Spinbox ▲**, held: the value goes up once, pauses a little under half
      a second, then counts up about ten a second. Let go: it stops.
      **▼** counts down the same way
- [ ] A **click** on ▲ steps it once
- [ ] **Hold me**, held: `held button` counts up after half a second, about
      ten a second. Let go: it stops, and does not add one more
- [ ] A **click** on Hold me adds exactly one
- [ ] The **scale's trough**, held to the right of the handle: one step at
      once, then after a pause it keeps stepping. **It goes past the pointer**
      and on to the end if held long enough. *Tk's does the same, measured:
      `tk::ScaleIncrement` never asks where the pointer is*
- [ ] **Middle-click** in the trough: the handle jumps to the click
- [ ] The handle is **three cells** long (`sliderlength=3`). Drag it: it is
      **dim** while held, and not once let go
- [ ] The **scrollbar's ▼**, held: the list scrolls one item, pauses, then
      keeps scrolling. **▲** scrolls back the same way
- [ ] Held in the scrollbar's **trough** below the thumb: it pages down, and
      keeps paging
- [ ] Drag the **thumb**, `jump: off`: the list scrolls as you drag
- [ ] **F5**, `jump: on`, and drag the thumb again: the thumb moves and **the
      list waits** until you let go, then jumps there

## Text spacing and undo

The Text has `spacing1=1` and `spacing2=1`: a blank row above each line, and
one between the rows of a line that wraps. Its first line wraps once.

- [ ] A **blank row** above "Blank rows above each line…"
- [ ] A **blank row** between that line's two rows, before "between wrapped
      rows."
- [ ] A **blank row** above "A second line."
- [ ] **F6**, `spacing: off`: the three lines close up, one under the other.
      **F6** again: the blank rows come back
- [ ] Click in a blank row: the cursor goes to the line it belongs to
- [ ] Up and Down **skip** the blank rows
- [ ] Type a letter, Backspace, another letter, Backspace, another: `undo
      groups` counts up and **stops at 3 of 3** (`maxundo=3`)
- [ ] **F8** three times: each undoes one step, and the fourth does nothing.
      The text the scenario started with cannot be undone

## The paned window

Two panes, `left` and `right`, with `sashpad=1`.

- [ ] There is a **blank cell either side** of the sash line
- [ ] The **handle** ┃ is one row down from the top of the sash, beside the
      words, not in the middle. *Tk's `handlepad` places it from the top*
- [ ] Drag the sash, `opaqueresize: on`: the panes follow the pointer
- [ ] Drag it as far as it goes either way: it **stops** with the narrow
      pane's word still inside the box. *Each pane has a `minsize`*
- [ ] **F7**, `opaqueresize: off`, and drag again: **a second line** follows
      the pointer over the panes, and **the panes stay** where they were
- [ ] Let go: the sash and the panes jump to where the line was, and the
      line is gone
- [ ] Drag from the **blank cell** beside the sash: it moves too. *Measured
      in Tk: the padding is part of the sash*

## Where a cell cannot match Tk

These differences are expected. Note any others under *Faults found*:

- Tk's reliefs are 3-D edges; here a relief is a box style, and only a whole
  widget can wear one. A part one cell deep - an arrow, a handle, an entry,
  the proxy - shows only `sunken`, as dim.
- Spacing is whole rows; Tk's is pixels.
- A sash is never less than one cell wide. `proxyborderwidth` draws nothing,
  and `sashcursor` changes nothing: a terminal has no pointer shapes.
- Nothing is activated by hovering, so `overrelief` shows only while a
  button is held down over it.

## Faults found by running it

- **The first run, by the author:** dragging the sash to the right drew
  `right` past the paned window's border. The scenario's fault, not the
  library's: the panes had no `minsize`, so a pane could narrow past its own
  label, and a child is not yet clipped to its container (`TkCurses-wbov`).
  Each pane now has a `minsize` that fits its word.
