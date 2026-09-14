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
      above, not the paragraph above — this is Tk's behaviour, checked against
      Tk 9.0.2, not a shortcut
- [ ] Home and End likewise go to the start and end of the **row**, not of the
      paragraph
- [ ] `Control-Home` and `Control-End` reach the two ends of the whole document
- [ ] `Control-Left` and `Control-Right` walk word by word, landing on each
      word's start rather than alternating between its two ends
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
- [ ] `Ctrl+N`, `Ctrl+O` and `Ctrl+Q` all work from anywhere — including
      `Ctrl+Q`, which a tty normally swallows as flow control
- [ ] `Ctrl+C` still interrupts the scenario, as it always did
- [ ] The checkbutton and radiobutton entries show their state, and the radio
      group shows exactly one dot
- [ ] **A popup near the bottom right corner is moved so all of it is on
      screen** — not cut off at the edge
- [ ] **`F3` posts more entries than the terminal has rows**, and the arrows
      scroll through them to `Item 39` rather than stopping at the bottom

## 26. Menubuttons, option menus and panes

`python3 -m uat 26` · click `File` and the option menu · drag the sashes ·
`Tab` to a pane and use the arrows · `F2` add a pane, `F3` remove one, `F4`
turn it on its side

- [ ] `File` posts a menu, and choosing an entry closes it and reports the
      choice
- [ ] The option menu shows the current size, and choosing a different one
      changes what the button says
- [ ] Both are clickable *and* reachable by Tab and Return
- [ ] Dragging a sash moves the boundary between two panes and leaves the
      others alone
- [ ] **A sash you have dragged stays where you put it** when a pane is added
      or the terminal is resized — that is the difference between a paned
      window and a row of packed frames
- [ ] A pane never shrinks below its minimum, however hard the sash is pushed
- [ ] The widths at the top always add up to the window, sashes included
- [ ] `Tab` reaches a paned window and the arrows move its sash
- [ ] The nested vertical panes work the same way inside the horizontal ones
- [ ] `F4` turns the whole thing on its side and the panes come with it
- [ ] Shrinking the terminal squeezes the panes rather than losing them

---

## What this found

- **A pane was laid out and never mapped**, so the panes were in exactly the
  right places and nothing at all was drawn. A geometry manager does two
  things beyond deciding where a child goes: it claims the child, and it maps
  it so there is a window to draw into.
- **The sashes were drawn before the layout knew where they were.** A window
  is painted when it is allocated, which is before its own manager has worked
  anything out — so they were drawn at position zero, underneath the first
  pane.
- **A menu posted off the screen.** `Menu.post` allocated screen coordinates
  as if they were relative to the master. That is the same thing only when the
  master is the root, which every menu so far had been; an OptionMenu makes
  its menu a child of the button, as tkinter does.
- **Every OptionMenu was inert.** Binding tags name one class, not a chain, so
  bindings registered under the literal `"Menubutton"` matched nothing on an
  `OptionMenu`. Spinbox meets the same trap with Entry and says so in a
  comment — which did not stop it being walked into a second time.
- **Two guesses about OptionMenu were wrong**, and driving a real
  `tkinter.OptionMenu` corrected both: building one does *not* write the
  variable, so an empty one shows nothing until something is chosen; and its
  entries are commands, not radiobuttons.

- **Control-Q and Control-S never reached the application.** They are XON and
  XOFF: the line discipline uses them to pause and resume output and passes
  neither on, so a menu offering a `Ctrl+Q` accelerator was offering a key
  nothing could ever receive. Cleared by hand rather than with curses' `raw()`,
  which would also have stopped `Ctrl+C` raising an interrupt — far too much
  to give up for two keys — and put back on the way out, so the next program
  in that terminal can still be paused.
- **An accelerator binds nothing, in Tk or here.** Reported as GNOME Terminal
  intercepting `Ctrl+N`; it was not — the key arrived perfectly and there was
  simply nothing bound to it. Checked against Tk 9.0.2, where an accelerator
  alone fires no command either: it draws the text, and the application binds
  the key. Scenario 25 now does, which is the pattern to copy.

- **Home and End moved by paragraph, where Tk moves by display row.** Asked
  whether Down landing on the next row of the same paragraph was correct, the
  question was settled by driving a real `tkinter.Text` and reading the
  answers back: Down was right, and Home and End were not. `Control-Home`,
  `Control-End` and word motion on `Control-Left`/`Right` were missing
  entirely. The numbers Tk 9.0.2 gave are now expectations in the suite, so
  "this is what Tk does" is a recorded fact rather than a claim in a comment.

- **Dragging never selected anything, on any real terminal.** Three separate
  faults, found one at a time because each hid the next:

  1. **The terminal was never asked to report motion.** `mousemask` accepts
  `REPORT_MOUSE_POSITION` and reports it granted — but the only thing ncurses
  writes to the terminal is `ESC [ ? 1006 ; 1000 h`: SGR encoding plus
  *normal* tracking, which is press and release and nothing else. Its built-in
  xterm string hard-codes 1000. The application has to set mode 1002 itself,
  and put it back on the way out. Every drag test passed because the harness
  sends motion whether it was asked for or not — the one thing a harness
  cannot check by imitating a terminal is what the terminal was *asked to do*,
  so it now records the bytes the application sends and the tests assert on
  those. **TkCurses-bj4**.

  2. **A drag reported with the button bit set read as a press.** The decoder
     checked the button masks before deciding whether a report was motion, so
     on an ncurses build that sets both, every step of a drag re-anchored the
     selection at the pointer — selecting nothing, while press and release
     worked perfectly.

  3. **The mode string could be lost on its way out.** Written through
     ncurses' output buffer it was at the mercy of when that buffer was
     flushed; it goes straight to the terminal now, after the screen is
     flushed, and once more from the first turn of the main loop. Which of
     those two mattered is not known — the fault was never reproducible here,
     and both were needed before drags worked on the reporting terminal.

  The lesson for the next one of these: the harness imitates a terminal, so it
  can only ever check what the application *does with* what a terminal sends.
  It cannot check what the application asks a terminal for, which is why
  scenario 23 now prints the raw curses report and the mode requested.

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
