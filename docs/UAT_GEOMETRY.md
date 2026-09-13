# Acceptance: geometry managers

The layout is checked automatically by property-based tests — no overlap, no
escaping the container, no negative sizes, idempotence. What those cannot tell
you is whether a layout *looks* like what you asked for: whether `fill` and
`expand` do visibly different things, whether `sticky` without a weight is
doing nothing for the right reason, whether a resize leaves the screen tidy.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 10          # and 11, 12, 13
```

From anywhere else: `python3 /path/to/TkCurses/uat 10`. Every scenario exits
on **Escape**.

> **What you are looking at.** No widget can draw itself yet — `Frame` and
> `Label` belong to the next cycle. Each scenario outlines its widgets in the
> widget's *own* window, at the rectangle the real geometry manager gave it.
> The boxes are therefore honest about position and size, but a real widget
> will draw its own. When Frame lands these scenarios should be rewritten to
> use it.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## 10. Pack — sides, fill and expand

`python3 -m uat 10` · `1`–`4` sides, `f` fill, `e` expand, `r` reset

- [ ] Boxes stack against the chosen side in the order A, B, C
- [ ] `left` and `right` put them side by side, not stacked
- [ ] `fill=x` stretches a box across its slice; `fill=y` down it
- [ ] Without `expand`, the boxes keep their own size and leave a gap
- [ ] With `expand`, the boxes share the leftover space evenly
- [ ] `expand` without `fill` moves the boxes apart without stretching them
- [ ] Nothing is drawn over the two instruction lines at the top

## 11. Grid — weight, sticky and span

`python3 -m uat 11` · `w` weight, `n` none, `s` sticky, `p` span

A and B sit side by side, C and D beneath them, E under those in the left
column.

- [ ] The four boxes form a tidy two-by-two; rows and columns line up
- [ ] With `n` (no weight) the boxes stay their natural size **whatever
      sticky says** — this is correct, not a bug
- [ ] With `w` the cells grow to fill the screen
- [ ] With weight, `ew` stretches a box across its cell and `e` pushes it to
      the right-hand edge without stretching
- [ ] `nsew` fills the cell in both directions
- [ ] `p` gives E two columns. With no sticky it **centres** across them
      rather than widening — also correct, for the same reason. Press `s`
      until sticky is `ew` and it stretches across both
- [ ] Nothing overlaps at any combination

## 12. Place — absolute, relative, anchor

`python3 -m uat 12` · `a` absolute, `r` relative, `m` mixed, `c` anchor

- [ ] `a` puts the box at a fixed cell position and it stays there when the
      terminal is resized
- [ ] `r` keeps the box centred proportionally as the terminal is resized
- [ ] `m` keeps a two-cell margin on both sides at every width
- [ ] `c` moves the box around the anchor point rather than moving the point
- [ ] The reported geometry on line 3 matches where the box actually is

## 13. Layout under resize

`python3 -m uat 13` · `d` nests a pair inside B, then resize the terminal

A and B share the screen one above the other. `d` puts two more boxes *inside*
B, side by side — B stays where it is and keeps its outline, with **1** and
**2** within it. They are numbered rather than lettered because they belong to
B; a C and D would suggest two more siblings.

- [ ] The boxes follow the new size immediately
- [ ] `d` leaves B in place and visibly containing 1 and 2 — B is not replaced
- [ ] 1 and 2 resize along with B and stay inside its outline
- [ ] Nothing is drawn outside the screen
- [ ] Make the terminal very small — a few cells — and check it neither
      crashes nor draws nonsense
- [ ] Make it large again and check the layout recovers exactly

> **Known and already filed:** shrinking a long way can leave fragments of the
> previous layout on screen until you grow the terminal back. That is
> **TkCurses-by3**, not a new fault.

---

## What this found

Running these for the first time turned up three bugs that every automated
test had missed, because each one asked the library for coordinates and got
the right answer while the screen showed something else:

- A panel was positioned with the widget's **master-relative** rect as though
  it were a screen position. Correct for a toplevel, whose master is at the
  origin; wrong for everything nested inside one.
- Resizing a container did not lay its children out again. Propagation travels
  upward — what a widget *needs* — and nothing carried the other direction,
  what it was actually *given*.
- A container's panel could be created after its children's and sit in front
  of them, hiding them behind an empty window, because panel z-order followed
  creation order rather than tree order.

All three now have regression tests in `tests/test_widget_lifecycle.py`.
