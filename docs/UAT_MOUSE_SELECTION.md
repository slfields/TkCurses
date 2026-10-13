# Acceptance: selecting with the mouse

One question: **can a person select text with the mouse the way they would in
a Tk program** — a word with a double-click, a line or everything with a
triple, more with a shift-click, and further than the widget shows by
dragging past its edge?

Dragging to select came with `TkCurses-lw2`, in UAT 43. The rest is
`TkCurses-svtr`. Every rule here was read from Tk's own bindings and measured
on Tk 9.0.2; ARCHITECTURE.md's "Selecting with the mouse" has the table.

**The readout under the title** says which click was recognised —
`last: double-click on entry` — and what is selected in the focused widget,
with its indices, and where the cursor is. A double-click must land on the
same cell within **200ms**. If yours arrive as two single clicks, run the
scenario with a longer window rather than clicking faster:

```bash
cd /path/to/TkCurses
python3 -m uat 44
TKCURSES_MOUSE_CLICK_INTERVAL=400 python3 -m uat 44   # slower double-clicks
```

**Escape** quits. It wants a terminal at least **90 columns by 24 rows**.

| | |
|---|---|
| Terminal | A VTE terminal (`VTE_VERSION=8401`, `TERM=xterm-256color`), from the mouse probe's log |
| Size | |
| Date | 2026-10-04 |
| Result | **Accepted.** Run by the author: "uat 44 is now complete", after the fault below was fixed. Size not recorded. The Ctrl-click section was added afterwards (`TkCurses-mndh`) and accepted on its own on 2026-10-13: "uat 44 ctrl-click section passes". |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. This matches `UAT_CLIPBOARD.md` and `UAT_VIEWS_AND_SELECTIONS.md`.
What was driven mechanically, and so is on the record, is the scenario 44
tests in `tests/test_uat_scenarios_tty.py`.

## Double-click: a word

A "word" is a run of letters, digits and underscores, **or a run of anything
else** — so a run of spaces, or `, `, is a word too. That is Tk's rule.

- [ ] In **Entry**, double-click `world`. It is selected, the readout says
      `7-12 'world'`, and the cursor is just after it (`cursor: 12`)
- [ ] Double-click the `, ` after `hello`. Both characters are selected
- [ ] Double-click `foo_bar`. The whole of it: an underscore is part of a word
- [ ] Double-click `42`, then the `.`, then the `5`. Three separate words
- [ ] **ttk.Entry**: the same
- [ ] **Spinbox**: double-click `two`. Selected, but the cursor is at its
      **start** (`cursor: 4`), not its end. *Tk's classic Spinbox does that.
      Its own copy of the code also selects nothing when you double-click a
      word's first letter — a Tk defect, measured, and not copied*
- [ ] **ttk.Spinbox**: a double-click selects **everything**, as Tk's does
- [ ] Double-click a spinbox's **up arrow**. It steps twice and selects
      nothing: the text becomes `0`, then `1`. *Stepping from text that is not
      a number starts at `from`, as Tk's does — measured*
- [ ] **text**: double-click `three` on the first line. The cursor goes to its
      **start**
- [ ] In the text, double-click the spaces after `foo` on line 2. The
      selection runs **across the line break** into the spaces before `bar`.
      *A newline is not a word character, so Tk's runs cross lines*

## Triple-click: a line, or everything

- [ ] In **Entry**, triple-click. Everything is selected, the cursor at the end
- [ ] **Spinbox**: everything, the cursor at the **start**
- [ ] **text**: triple-click line 3, `  bar`. The line is selected **and its
      newline** — the readout shows `'  bar\n'`

## Dragging after a double- or triple-click

- [ ] In the text, double-click `two` and, **still holding the second click**,
      drag right. The selection grows a **whole word** at a time
- [ ] Triple-click a line and drag down. It grows a **whole line** at a time
- [ ] In **Entry**, double-click `world` and drag down over **ttk.Entry**. It is
      still Entry's selection that grows; nothing happens in ttk.Entry. *The
      drag after a double-click used to go to whatever was under the pointer*

## Shift-click or Alt-click: more

**In GNOME Terminal, Ptyxis and every other VTE terminal, use Alt-click.**
VTE keeps every Shift-click for its own text selection and never sends one to
a program, even one that has asked for the mouse. A raw probe in the author's
terminal recorded plain, Ctrl- and Alt-clicks and not one Shift-click — found
on this checklist's first run. Alt-click does here exactly what Shift-click
does, in every terminal; in one that passes Shift-click on (xterm, kitty),
both work. The readout says `alt-click` or `shift-click`.

- [ ] In **Entry**, drag over `world`, then Alt-click on `baz`. The selection
      runs from `world` to `baz`, and **the cursor stays** where the drag left
      it. Alt-click back on `hello`: the far end stays put, the near one moves
- [ ] In **ttk.Entry**, do the same. This time **the cursor moves** to where you
      clicked. *ttk's rule differs from classic Tk's; both are measured*
- [ ] Click somewhere with nothing selected, then Alt-click elsewhere. The
      text between the two is selected
- [ ] In the **text**, drag over `two`, then Alt-click in `four`. It extends
      from `two` to the click
- [ ] In the **text**, double-click `two`, then double-Alt-click in `four`.
      It extends by whole words

## Ctrl-click: move the cursor, keep the selection

*Added after the acceptance above, with `TkCurses-mndh`, and accepted
separately on 2026-10-13.* Tk's classic
Entry, Spinbox and Text bind Ctrl-click to move the cursor without touching
the selection — and without taking the focus. ttk binds nothing to it, so in
a ttk widget a Ctrl-click is an ordinary click. VTE terminals do pass
Ctrl-clicks on (measured).

- [ ] In **Entry**, drag over `world`, then Ctrl-click on `hello`. `world` is
      still selected, and the readout's `cursor:` moves to where you clicked
- [ ] Click into **ttk.Entry**, then Ctrl-click in **Entry**. The focus stays in
      ttk.Entry — the readout's `focus:` does not change
- [ ] In **ttk.Entry**, select something and Ctrl-click. The selection goes,
      as an ordinary click's would: *ttk binds no Ctrl-click*
- [ ] In the **text**, drag over `two`, then Ctrl-click in `four`. `two` stays
      selected and the cursor moves
- [ ] In the **text**, Ctrl-double-click a word. **Nothing** is selected:
      *Tk binds that to nothing, on purpose*

## Dragging past the edge: autoscroll

- [ ] In **narrow**, press near the start and drag **off its right end** —
      into the gap beside it — then **hold still**. The field keeps
      scrolling and the selection keeps growing, with no further movement
- [ ] Come back inside. It stops. Go out again, then let go of the button. It
      stops
- [ ] In the **text**, drag **below** it and hold. It scrolls down, selecting
      as it goes. **Farther below scrolls faster**
- [ ] Drag above it: it scrolls back up
- [ ] Line 5 of the text is wider than the box. Drag along it and off the
      **left** edge, after scrolling right, and it scrolls back left

A widget against the edge of the terminal cannot be dragged past that edge:
the terminal reports the pointer only inside itself. The layout leaves room
past each one on purpose.

## Faults found by running it

1. **No shift-click item worked**; everything else did. The terminal never
   sends a Shift-click: a raw probe recorded plain, Ctrl- and Alt-clicks and
   not one Shift-click, which is how every VTE terminal behaves. Alt-click was
   made to do what Shift-click does, the author's choice, and this checklist
   rewritten to use it. Recorded in ARCHITECTURE.md as a departure from Tk.
