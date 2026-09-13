# Acceptance: widgets that carry a value

The earlier checklists ask where things are and whether they answer. These ask
whether the *value* is real — whether a widget and the variable behind it stay
the same thing when either end of them moves.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 20          # and 21, 22
```

From anywhere else: `python3 /path/to/TkCurses/uat 20`. Every scenario exits
on **Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## The one that matters most

**A variable is not a copy.** Every widget bound to one is a view of the same
value, and so is the line at the top of the screen. If clicking a box moves
one view and not another, the value has been copied somewhere it should have
been shared, and every one of these widgets is lying about what it holds.

## 20. Checkbuttons and radiobuttons

`python3 -m uat 20` · `Tab` and `space` · `s` sets the size from code, `c`
returns the read-only box to its third state, `r` resets everything

- [ ] Clicking a checkbutton ticks it and the line at the top changes with it
- [ ] The second view of the same variable, lower in the box, ticks too
- [ ] The focused widget shows `< >` instead of `[ ]`, and nothing shifts
      sideways when the focus arrives or leaves
- [ ] Tab reaches every checkbutton and radiobutton, and space presses the
      focused one
- [ ] `Wrap lines` reports `'on'` and `'off'`, not `1` and `0` — a widget that
      stores a boolean and hopes for the best gets this wrong
- [ ] `Read-only files` starts as `[-]`, neither ticked nor blank
- [ ] Clicking it from `[-]` turns it **on**, not off
- [ ] `c` puts it back to `[-]`
- [ ] The no-box `Bold` reverses while it is on, and follows the boxed `Bold`
- [ ] Exactly one radiobutton is on at any moment
- [ ] Choosing one turns the previous one off without anything being told to
- [ ] Clicking the one already chosen leaves it chosen, and still reports a
      command in the `last command` line
- [ ] `s` chooses `Large` from code, and both views move
- [ ] `r` returns everything to where it started

## 21. Scales

`python3 -m uat 21` · `Tab` · arrows, `Ctrl`-arrow, `PgUp`/`PgDn`, `Home`,
`End` · click a trough, drag a handle

- [ ] Every scale reaches both of its ends and stops there
- [ ] The arrows move the focused scale by one step
- [ ] `Ctrl`-arrow moves it by a larger step
- [ ] `Home` and `End` go to the two ends in one press
- [ ] Clicking anywhere in a trough moves the handle there
- [ ] Dragging the handle follows the pointer, and dragging past the end
      stops at the end rather than escaping
- [ ] The focused scale shows `[` and `]` at the ends of its trough, and the
      trough does not move when the focus arrives
- [ ] Both `Volume` scales move together — they are one variable
- [ ] The reversed `Bass` scale counts **down** from 10 to 0, left to right
- [ ] `End` on it goes to **0**, because `End` means `to`, not *largest*
- [ ] Its ticks read `10  5  0`, in that order
- [ ] The vertical `Mix` scale shows one decimal, never `0.30000000000000004`
- [ ] `Mix` shows its value beside the handle, and the label to its right
      shows the same number
- [ ] Resizing the terminal keeps every scale inside its box

## 22. Spinboxes, messages and captioned frames

`python3 -m uat 22` · `Tab` · `Up`/`Down` and the arrows · `F2` changes the
message aspect, `F3` moves the captions

> **Function keys rather than letters**, because a focused entry consumes
> every printable key before it can reach an application-wide binding. That
> is correct, and it is the same rule the interactive round wrote down.

- [ ] Every box's caption sits **on** its border, never over its contents
- [ ] `F3` moves all six captions together: top-left, top-centre, then
      bottom-right
- [ ] A caption longer than its box is cut short rather than wrapped or
      drawn over the corner
- [ ] Each spinbox shows a value and a pair of arrows at its right-hand edge
- [ ] `Up` and `Down` step the focused spinbox
- [ ] Clicking the arrows steps it too
- [ ] The arrows stay in the same column as the value changes width
- [ ] The readonly spinbox refuses typing and still steps
- [ ] `0 to 12, wraps` goes from 12 to 0 and back rather than stopping
- [ ] `0.00 by 0.25` shows two decimals throughout, and can be typed into
- [ ] The bordered rectangle inside each of the three lower boxes is the
      **message**; the captioned box around it is a LabelFrame
- [ ] At aspect 100 the block is roughly as tall as it is wide; at 300 it is
      about three times as wide as tall
- [ ] The three aspects stay different from one another
- [ ] `F2` changes the text and all three re-wrap, each keeping its own shape
- [ ] A message too tall for its box keeps its **first** line and loses its
      last — text you cannot start reading is text you cannot read
- [ ] Resizing the terminal re-wraps the messages and keeps every caption on
      its border

---

## What this found

- **A scale's value had nowhere to go.** Room for the number was measured from
  the two ends alone, so a scale from 0 to 1 by 0.1 reserved one cell — enough
  for `0` and `1`, not for the `0.5` it shows everywhere between. On a vertical
  scale the value was then simply never drawn. Measured from the widest
  *reachable* value now.
- **The value was drawn through the label.** Both share the top row of a
  horizontal scale, so a handle at the low end wrote its number over the
  label: `V0lume`. The value is pushed clear of the label instead.
- **A `labelled_box` packed with `fill="x"` collapsed and took its contents
  with it.** The helper turns geometry propagation off — it has to, or the
  title label would shrink the box — so a box given no height of its own has
  none. The whole first section of scenario 21 was invisible until it was
  given one. This is the second time that helper's propagation has eaten a
  scenario; the first was the geometry round's nesting box.
- **The test harness mis-tracked the cursor.** ncurses moves it with back-tab
  (`CSI Z`) when that is the shortest route to a column, and pyte has no
  handler for the sequence, so it drops it and everything written afterwards
  lands a few cells off. It showed up as an unrelated focus test failing one
  run in three with `focus ontwo` on screen — a screen no terminal would ever
  have shown. **TkCurses-gcu**.
- **An entry squeezed to one row rendered nothing at all.** A bordered widget
  too small for its own border draws none — but everything measuring the space
  left inside carried on subtracting an edge that was never there, came out
  with no content area, and drew a blank rectangle. Indistinguishable from a
  widget that had failed to appear, and it is what made a spinbox packed with
  `pady` into a three-row frame simply not exist. Painting and measuring agree
  now, through `_border_drawn`.
- **Text taller than its widget lost its beginning.** A centred block that did
  not fit was clipped at both ends, so a paragraph in a short box started
  mid-sentence. Clamped to the top, the way the column was already clamped to
  the left: losing the end of a paragraph is recoverable, losing its start is
  not.
- **The aspect scenario could not show an aspect.** The three messages filled
  three LabelFrames packed as fixed equal thirds, so the only edges on screen
  belonged to the frames and never moved; changing `aspect` only reshuffled the
  wrapping inside a rectangle that could not change shape. Worse, `F2` set all
  three boxes to the *same* aspect, which made the columns identical and threw
  away the comparison they exist for. Each message now has a border of its own
  and is packed to its own size, so the block it asked for is what you see;
  `F2` cycles the text instead, and the three aspects stay distinct. Reported
  from UAT: "the border for the different windows never change when the aspect
  value is changed".
- **A scenario key that a focused entry ate.** Scenario 22 first used `a` and
  `c`; with the focus in a spinbox neither ever arrived. The interactive round
  had already written this down, which is the argument for reading your own
  checklists.
- **The scale wrote floats into integer variables.** `set()` published the
  raw float, so an `IntVar` ended up holding `6.0` and raised when asked to
  read its own value back — which also silently broke two scales sharing one
  variable, because the failure was swallowed on the way in. The value is
  published as text now, the way Tcl holds it.
