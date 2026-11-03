# Acceptance: how classic widgets look

Three questions, from `TkCurses-gm66.2`, `.3` and `.4`:

- **Do Tk's insertion-cursor options reach the terminal's own cursor?**
- **Are selections drawn in the colours a program gives them?**
- **Are active, disabled and readonly widgets drawn in theirs?**

Until this cycle every one of these options was refused, and a tkinter program
that passed one stopped at that line. Each still defaults to `""` here, where
Tk's defaults are real colours, so a program that sets none should look
exactly as it did before. This scenario sets them all.

```bash
cd /path/to/TkCurses
python3 -m uat 48
```

**The readout** shows the fields' state, whether the buttons are active, how
the Text's selection looks without the focus, and which widget has the focus.
Use these keys:

- **Tab** or **F8** moves the focus. **F8** also leaves the Text, where Tab
  types a tab.
- Clicking a field also gives it the focus.
- **F5** steps the fields through normal, disabled and readonly.
- **F6** makes the buttons and the scale active, and makes them normal again.
- **F7** switches the Text's unfocused selection between green and hidden.
- **Escape** quits.

A terminal may keep some function keys for itself, such as GNOME Terminal's
F10 or a desktop's F11. The four used here are usually free.

**Run it in at least two terminals.** A terminal that does not understand a
cursor-shape or cursor-colour request ignores it, so one terminal cannot
settle the cursor questions on its own.

| | First terminal | Second terminal |
|---|---|---|
| Terminal and version | GNOME Terminal | not run |
| `$TERM` | | |
| Size | | |
| Date | 2026-11-02 | |
| Result | **Accepted.** Run by the author: "This appears to be working as expected". | |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. What was driven mechanically, and so is on the record, is the
scenario 48 tests in `tests/test_uat_scenarios_tty.py`.

**Still open:** only one terminal is recorded. The cursor requests have not
been seen on a terminal other than GNOME Terminal, so one that ignores them,
or draws them differently, is unconfirmed. Run it in a second terminal and
fill in the second column.

## The insertion cursor

The cursor is the terminal's own, as you have it set up. A field that sets
none of these options asks for nothing. A field that sets one asks the
terminal for the nearest shape or colour it has.

Move the focus down the left-hand column, from a to e.

**A blink that stops after about ten seconds is the terminal, not the
scenario.** GNOME Terminal, like other GTK and VTE terminals, follows GTK's
cursor-blink timeout and stops blinking after 10 seconds without input. kitty
has `cursor_stop_blinking_after` for the same thing. Seen in the first run,
on every field, the plain one included, and at the shell prompt with no
scenario running. The plain field asks the terminal for nothing, which is
what rules the scenario out. A key press starts the blink again. Judge
"blinks" and "does not blink" in the first few seconds after the focus
arrives.


- [ ] **a, plain**: your own cursor, its usual shape, colour and blink
- [ ] **b, `insertwidth=1`**: a **bar** that blinks. *Tk draws a 1-pixel bar.
      A cell has no width to give, so any width other than Tk's default of 2
      asks for a bar*
- [ ] **c, `insertofftime=0`**: a bar that **does not blink**
- [ ] **d, `insertbackground=#ff8000`**: an **orange** cursor, in your usual
      shape
- [ ] **e, `blockcursor=1`**: a **block** over the character, blinking
- [ ] Back to **a**: your own cursor returns, in its own shape and colour, and
      not the shape or colour the last field asked for
- [ ] **Escape**, then type at the shell prompt: the shell's cursor is as it
      was before the scenario started

## Selections

The first five characters of fields a, b and d are selected. "south" is
selected in the list, and "block" in the Text.

- [ ] The selected characters are **black on cyan**, not reversed
- [ ] "south" is black on cyan, between its ▶ ◀ markers
- [ ] Give the Text the focus: "block" is black on cyan. Move the focus away:
      it turns **black on green**, its `inactiveselectbackground`
- [ ] **F7**, with the focus elsewhere: "block" shows **no selection at all**.
      *Tk's manual: an empty `inactiveselectbackground` hides the selection
      while the widget has no focus*
- [ ] Give the Text the focus again: "block" is selected again, in cyan
- [ ] **F7** again, then focus elsewhere: green again

## Disabled and readonly

- [ ] **F5**, `fields: disabled`: the four fields and the spinbox are
      **yellow on blue**, not dimmed
- [ ] The list's items are **yellow**, not dimmed
- [ ] The Text is **dimmed**. *It has no disabled colours, in Tk or here*
- [ ] **F5**, `fields: readonly`: the fields and the spinbox are on
      **magenta**, in their normal text colour. The list and the Text are
      back to normal. *Neither has a readonly state*
- [ ] The spinbox's ▲▼ are on **green** in every state, its
      `buttonbackground`
- [ ] **F5**: everything is back to normal

## Active, and the indicator colours

- [ ] The ticked check box's **[x]** and the chosen radio button's **(•)** are
      on **green**, their `selectcolor`. So are the unticked indicators: Tk
      paints the indicator in `selectcolor` whatever its state
- [ ] "no indicator, on" has **green** behind it, edge to edge. Click it
      off: the green goes. *Without an indicator, Tk uses `selectcolor` as the
      whole button's background while it is on*
- [ ] **F6**, `buttons: active`: the check and radio buttons and "Press me"
      are **yellow on red**, border included, and not reversed
- [ ] The scale's handle is on **red**
- [ ] **F6** again: all normal
- [ ] Hold the mouse down on **Press me**: yellow on red until you let go.
      *Tk only presses an active button*
- [ ] The scale's trough is **blue**, and its handle is not. Drag the handle:
      it is on red while you drag

## Where a cell cannot match Tk

These differences are expected. Note any others under *Faults found*:

- Tk draws its own cursor; here it is the terminal's. `insertontime`,
  `insertborderwidth` and `insertunfocussed` are stored and change nothing,
  and the blink rate is the terminal's.
- Tk's colour defaults are greys. Here each is the terminal's own, so
  without these options set, a selection or an active widget is reversed and
  a disabled one is dimmed, as before.
- Tk activates a button or scale when the pointer moves over it. Nothing is
  activated by hovering here, so F6 stands in for it.
- `selectborderwidth` draws nothing. A cell has no 3-D edge.

## Faults found by running it

None. The cursor that stopped blinking after about ten seconds was GNOME
Terminal's own timeout, described under *The insertion cursor*, and not a
fault.
