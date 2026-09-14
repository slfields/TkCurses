# Acceptance: content that outgrows its widget

The earlier checklists ask where things are, whether they answer, and whether
a value is real. These ask what happens when a widget holds more than it can
show — a document longer than its window, a drawing wider than its canvas, a
menu taller than the terminal.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 23          # and 24, 25
```

From anywhere else: `python3 /path/to/TkCurses/uat 23`. Every scenario exits
on **Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## The one that matters most

**Nothing may be lost at an edge.** A document that cannot be scrolled to its
end, a drawing clipped where the widget stops, a menu whose last entries fall
off the screen — each of those is a widget quietly refusing to show you part of
what it holds, and in a terminal there is no scrollbar-by-default and no window
manager to drag things back into view.

## 23. Text

`python3 -m uat 23` · type · arrows, `Home`, `End`, `PgUp`, `PgDn` ·
`Shift`+arrows and dragging to select · `F2` wrap mode, `F3` add a long line,
`F4` tag the word under the cursor

> **Function keys rather than letters**, because a focused Text consumes every
> printable key — which is the correct behaviour and the reason it has them.

- [ ] The cursor is visible, and **only** while the widget has the focus
- [ ] Typing inserts at the cursor and the view follows it
- [ ] `F3` adds a line past the bottom and the view comes with it
- [ ] With `wrap='none'`, `End` on a long line scrolls **sideways** and back
- [ ] `F2` re-flows text that is already in the buffer, all three ways
- [ ] No line ever runs over the widget's border, in any wrap mode
- [ ] Up and Down move by what is on **screen**: on a wrapped line, to the row
      above, not the paragraph above
- [ ] `Shift` with the arrows selects, and a plain arrow drops the selection
- [ ] Dragging with the mouse selects the same range
- [ ] Typing over a selection replaces it
- [ ] The first paragraph shows five tags at once: **bold**, underlined,
      italic, a colour, and a highlight — italic may do nothing on terminals
      that have no italic, which is theirs to decide, not the library's
- [ ] `F4` highlights the word under the cursor, and `F5` clears every
      highlight
- [ ] A tag moves with the text: type in front of a tagged word and the tag
      goes with it
- [ ] `Shift` with the arrows selects
- [ ] Dragging with the mouse selects — the `mouse:` line should show `drag`
      while the button is held. Nothing there means the terminal is not
      reporting motion, which `TKCURSES_MOUSE_REPORT_MOTION=0` would also
      cause
- [ ] The scrollbar's thumb matches where the view actually is
- [ ] `end` reads one line past the last — Tk's rule, not a fault
- [ ] Resizing the terminal re-wraps without losing the cursor

## 24. Canvas

`python3 -m uat 24` · click the shapes · `F2` move the ring, `F3` hide the
box, `F4` raise or lower the ring

- [ ] **The ring is a circle, not a tall ellipse.** This is the whole reason a
      canvas cell is split across the middle: one half-cell is one cell wide
      and half a cell tall, which on a normal terminal is very nearly square
- [ ] The strip near the bottom is one row of cells, each showing **two**
      different colours at once
- [ ] Clicking a shape reports its type and tags, and only the topmost one
      under the pointer answers
- [ ] The one clicked before it goes back to its own colour
- [ ] Clicking a diagonal inside the square reports the **line**; clicking
      the square's own edge reports the rectangle
- [ ] Clicking between the diagonals, inside the unfilled square, reports
      nothing — there is nothing drawn there, which is what Tk does too
- [ ] Clicking empty canvas reports nothing
- [ ] `F2` moves the ring and leaves nothing behind where it was
- [ ] `F3` hides the box completely, and shows it again unchanged
- [ ] `F4` puts the ring in front of and behind the block
- [ ] The `round` label sits on a whole cell row and is drawn over the ring,
      because it was made after it
- [ ] Resizing smaller clips the drawing at the border rather than spilling
      over it, and resizing back brings it all in view

## 25. Menu

`python3 -m uat 25` · click the bar or `F2` · arrows, `Escape` · right-click
anywhere · `F3` for a menu taller than the terminal

- [ ] Clicking `File` posts its dropdown over the window beneath
- [ ] Dismissing it leaves no marks behind
- [ ] Clicking away from an open menu closes it
- [ ] `Escape` closes it too
- [ ] Left and Right walk along the bar with a dropdown open
- [ ] Up and Down move within a dropdown and **skip** the separators and the
      disabled entry — an arrow that appears to do nothing is a bug
- [ ] Right opens the `More` submenu; Left closes it and leaves the parent up
- [ ] Accelerators are right-aligned and do not touch the labels
- [ ] The underlined letter chooses its entry
- [ ] The checkbutton and radiobutton entries show their state, and the radio
      group shows exactly one dot
- [ ] **A popup near the bottom right corner is moved so all of it is on
      screen** — not cut off at the edge
- [ ] **`F3` posts more entries than the terminal has rows**, and the arrows
      scroll through them to `Item 39` rather than stopping at the bottom

---

## What this found

- **The terminal was never asked to report mouse motion, so no drag ever
  happened outside the test harness.** `mousemask` accepts
  `REPORT_MOUSE_POSITION` and reports it granted — but the only thing ncurses
  writes to the terminal is `ESC [ ? 1006 ; 1000 h`: SGR encoding plus
  *normal* tracking, which is press and release and nothing else. Its built-in
  xterm string hard-codes 1000. The application has to set mode 1002 itself,
  and put it back on the way out. Every drag test passed because the harness
  sends motion whether it was asked for or not — the one thing a harness
  cannot check by imitating a terminal is what the terminal was *asked to do*,
  so it now records the bytes the application sends and the tests assert on
  those. **TkCurses-bj4**.

- **Shift with the arrows did not select anything, on any terminal.** ncurses
  decodes a shifted arrow into a key code of its own — Shift-Down is `KEY_SF`,
  Shift-Right is `KEY_SRIGHT` — and nothing mapped any of them, so a shifted
  arrow was indistinguishable from a plain one and keyboard selection was
  unreachable. Reported as a possible GNOME problem; it was not, it was ours.
- **The cursor was drawn on the wrong row at a wrap boundary**, one cell past
  the end of the row above, and painted the first character of the next row
  there as well. A boundary is the end of one display row *and* the start of
  the next; it has to resolve to the later one.
- **`<Key>` does not match a key held with a modifier.** Tk requires a
  pattern's modifiers to be a subset of the event's, so `<Key>` sees
  everything; this library requires them to match exactly. Deliberate once,
  but it disagrees with Tk and it means the obvious "tell me about every key"
  binding stops working the moment Shift is held. **TkCurses-qxl**.

- **Clicking a square raised an exception, and selections never cleared.**
  Two faults from one cause. Hit-testing went by an item's *bounding box*, so
  the diagonals drawn across the square — whose box is the whole square —
  claimed every click inside it; the scenario then asked a line for its
  `outline`, which a line has not got. Items are hit-tested against their real
  ink now, with Tk's `closeenough` tolerance so a one-pixel outline is still
  clickable in a terminal. The scenario picks the right option per item type
  and puts the previous selection back.

- **A magenta triangle rendered white.** Colour in a curses attribute is a
  packed field — `A_COLOR` is `0xff00`, holding the pair's *number* — not a
  flag. Two places OR'd a second pair onto an attribute that already carried
  one, so the two numbers combined into the number of a third, unrelated pair.
  The canvas polygon's 46 solid interior cells came out as a full white block
  with the magenta hidden behind it, which is why only the few cells at its
  edges looked purple. Text tags had the same fault. Every colour test until
  then had used a widget whose base attribute carried no colour of its own,
  so nothing caught it. **TkCurses-ia5**.

- **A dropdown opened from a menubar never closed.** Dismissal walked up to the
  root menu and unposted that — and the root was the bar, which is never itself
  posted, so nothing was dismissed and the menu stayed on screen. Every unit
  test passed, because they all used popups with no parent; three terminal
  tests caught it at once.
- **`see()` moved the view without telling the scrollbar.** The thumb sat at
  the bottom of its trough while the text showed line 1 — the one thing a
  scrollbar exists to report, reporting the opposite of the truth.
- **Word wrapping could draw a row one cell too wide.** A space falling exactly
  at the wrap column was kept on the line, which in a character grid means
  over the border.
- **The insert cursor blanked a character.** `end` is a line past every display
  row and so has none of its own; falling back to the last row put the cursor
  at column 0 and erased the first character of the bottom line.
- **`current` was never implemented.** `tag_bind`'s own docstring promised that
  the item an event reached was the one `find_withtag("current")` names, and
  nothing made that true.
- **Centring a single line of canvas text put it on the wrong row**, by taking
  half the block height off in pixels before converting to cells.
