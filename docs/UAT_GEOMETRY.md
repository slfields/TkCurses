# Acceptance: geometry managers

The layout is checked automatically by property-based tests — no overlap, no
escaping the container, no negative sizes, idempotence. What those cannot tell
you is whether a layout *looks* like what you asked for: whether `fill` and
`expand` do visibly different things, whether `sticky` without a weight is
doing nothing for the right reason, whether a resize leaves the screen tidy.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 10          # and 11, 12, 13, 28
```

From anywhere else: `python3 /path/to/TkCurses/uat 10`. Every scenario exits
on **Escape**.

> **What you are looking at.** Real widgets, since `Frame` and `Label` landed:
> every box is a `Frame` with a `solid` relief and a `Label` inside naming it.
> The drawing helper these scenarios used to need is gone.

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

## 28. Geometry options — change one, keep the rest

`python3 -m uat 28` · `p` pack side · `g` grid column · `x` place x ·
`w` place width · `a` one-sided pad · `e` push them past the edges ·
`f` forget all three · `r` reset

Three strips, one per manager, each with a box in it. The line above each
strip is what the manager reports — `pack_info()`, `grid_info()`,
`place_info()` — so what it believes can be read against where the box is.

> **What this is for.** The fault it checks was invisible to anyone reading
> the call: `pack_configure(fill='x')` looks like it changes the fill, and what
> it used to do was reset the side, the padding and the anchor too. `w`, which
> asks the placed box only to get *wider*, also sent it to the corner.

- [ ] `p` changes `side` from `left` to `right` and back — the pack box moves
      to the other edge, and `fill`, `padx` and `anchor` are unchanged on the
      line and on screen
- [ ] `g` moves the grid box between column 3 and column 1 — it lines up with
      the numbered markers below it, and `row`, `sticky` and `padx` do not move
- [ ] `x` moves the placed box sideways and leaves its `y` and `width` alone
- [ ] `w` makes the placed box **wider without moving it** — the left edge
      stays where it was
- [ ] Each line agrees with the box under it, every time
- [ ] `r` puts all three back exactly as they started

### A pad on one side only

`a` gives the pack and grid boxes Tk's two-value pad, `padx=(0, 6)`: no
pad on the left, six cells on the right. `a` again goes back to `padx=2`,
which pads both sides by two. Read back as Tk 9.0.2 does.

- [ ] Both lines report `padx=(0, 6)` — the pair, not `0`, `6` or `(0, 0)`
- [ ] The pack box moves **two cells left**, to the strip's left edge, and
      nothing else about it changes
- [ ] The grid box moves **two cells left** within column 3, and the `3` and
      `4` markers move **right** — column 3 is two cells wider, for the extra
      pad on its right, and the `3` stays centred in it. Measured the same
      way round in Tk 9.0.2
- [ ] `a` again reports `padx=2` on both lines and puts both boxes back

### Where the defaults do come back, correctly

`f` forgets all three widgets and adds them again with no options at all.
Forgetting is what discards a widget's options in Tk, so the defaults here are
the right answer and **not** a fault. Checked against Tk 9.0.2.

- [ ] After `f`: pack reports `side='top'`, `fill='none'`, `padx=0`,
      `anchor='center'`, and the box sits centred at the top of its strip
- [ ] After `f`: grid reports `row=0`, `column=0`, `sticky=''`, `padx=0`, and
      the box sits above the column markers rather than on top of them
- [ ] After `f`: place reports `x=0`, `y=0`, no width, `anchor='nw'`
- [ ] `r` afterwards brings the starting options back

### Where the screen edge cuts a widget in half

`e` pushes all three boxes hard against an edge. A widget the edge cuts can
only have a window holding the part that fits — curses refuses one that runs
off the screen — so the drawing has to **stop** at the edge.

> **A box with no right-hand edge is correct** for a box that continues off
> the screen. The same box with its border running on into the line below is
> the fault: that is the overflow being wrapped instead of dropped.

- [ ] After `e`, the pack box sits against the right edge **whole** — it fits,
      so it keeps both of its sides
- [ ] After `e`, the grid box runs off the right: a top edge, a left edge, a
      bottom edge, and **no right edge and no corners** on that side
- [ ] After `e`, the placed box does the same
- [ ] **Nothing wraps.** No row holds the tail of the row above it, and the
      report lines and the column markers are exactly where they were
- [ ] `r` brings all three back whole
- [ ] Now shrink the terminal, narrower and shorter, a few cells at a time.
      Every box is cut off cleanly at whichever edge reaches it, and the ones
      that no longer fit at all simply are not drawn
- [ ] Grow it back and all three are whole again, with nothing left behind

> **Known and already filed:** the shared border and label writers clip, and
> the per-widget content writers — `Text`, `Listbox`, `Canvas`, `Scale`,
> `Scrollbar`, `Menu`, `Entry` — do not yet, so one of those cut in half can
> still wrap a row of its own content. **TkCurses-4jd.5**.

## 13. Layout under resize

`python3 -m uat 13` · `d` nests a pair inside B, then resize the terminal

A and B share the screen one above the other. `d` puts two more frames *inside*
B, side by side — B stays where it is and keeps its border, with **1** and
**2** within it. They are numbered rather than lettered because they belong to
B; a C and D would suggest two more siblings.

On a short terminal the nested pair has no room for its own labels. Grow the
window until 1 and 2 are readable; that they vanish first and come back is
itself worth watching.

- [ ] The boxes follow the new size immediately
- [ ] `d` leaves B in place and visibly containing 1 and 2 — B is not replaced
- [ ] 1 and 2 resize along with B and stay inside its outline
- [ ] Nothing is drawn outside the screen
- [ ] Make the terminal very small — a few cells — and check it neither
      crashes nor draws nonsense
- [ ] Make it large again and check the layout recovers exactly

> **Known and already filed:** a widget the screen edge cuts in half draws all
> of itself into the smaller window it was given, so the overflow wraps onto
> the next row instead of being dropped — a box border that runs on into the
> line below. That is **TkCurses-4jd.3**, not a new fault. A box that should
> be off screen being drawn anyway was **TkCurses-pxk**, and fragments of the
> previous layout surviving a shrink were **TkCurses-by3**; both are fixed.

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

## 14. Label — wrapping, justify and anchor

`python3 -m uat 14` · `w` wrap width, `j` justify, `a` anchor

Three labels: prose in a frame that grows to fit it, one long unbroken word,
and a fixed twelve-cell frame holding text far too wide for it.

- [ ] `w` cycles the wrap width and the prose re-wraps at word boundaries
- [ ] With no wrap the prose is one long line, clipped at the frame's edge
- [ ] `j` visibly moves the wrapped lines relative to **each other**
- [ ] `a` moves the whole block within its frame — a different thing from
      `j`, and both are needed to see the difference
- [ ] The long word is broken mid-word rather than overflowing its frame
- [ ] The narrow frame shows the **beginning** of its text, cut at the right
      edge — not the end pushed against the far side
- [ ] Nothing is ever drawn outside a frame's border

---

## What this found, second time round

Rewriting these to use real widgets turned up three more things, after the
three the stand-in version found:

- A container's requested size was being overwritten by **placed** children,
  which make no claim on it. Whether a manager sizes its container is now a
  property of the manager rather than an assumption in the engine.
- `Label` justified its text **after** clipping it, so a label too narrow for
  its text showed the end hard against the far edge with the beginning cut
  off. Justification is measured from the real line length now.
- A helper that decorated a frame by *placing* a label in it made that frame a
  place container, and TkCurses then allowed one manager per container — so nothing
  could be packed inside it afterwards and the nesting scenario silently
  refused to nest.
