# Acceptance: a curses program on this layer

The library's premise has two halves. A tkinter program runs on it; this
cycle is so that a curses program can too, and so that the two can be the
same program.

A test can prove `newwin` returned a window of the right size. It cannot tell
you whether a curses application someone already has runs on this layer
**without them noticing**, and that is the only claim being made.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 32                                # against tkcurses.curses
TKCURSES_UAT_BACKEND=stdlib python3 -m uat 32    # against the real curses
python3 -m tkcurses                              # both halves in one program
```

From anywhere else: `python3 /path/to/TkCurses/uat 32`. **Escape** quits
everything here.

> The two runs of scenario 32 are the same source file. The only thing that
> changes is which module it imported, and the top line says which one you
> are looking at. **The comparison is the test**: a curses program does not
> know or care which it got, so anywhere the two screens differ, this layer
> is wrong.

| | |
|---|---|
| Terminal | |
| Size | |
| `tput colors` | |
| Date | |

---

## The one that matters most

**Run it both ways and look for a difference.** Everything below is a
prompt for where to look; the assertion is that you cannot tell the two
apart. If you can, that difference is the bug, and the screenshot of both is
the whole report.

---

## 32. The same program, either way

`python3 -m uat 32` · `1` `2` `3` raise · `h` hide the top · `s` show all ·
`m` move the top · Escape quits

### What it says about itself

- [ ] Line 2 names the backend, and matches the way you started it
- [ ] Line 3 reports `has_colors()` and `can_change_color()`, and both runs
      agree
- [ ] Under `TERM=vt100` both say `has_colors=False`. The specification
      originally had this always True; it is not, and a curses program asks
      precisely so it can draw differently

### The window

- [ ] The boxed windows are in the same place on both, the same size, with
      the same characters at the corners
- [ ] The text inside sits at the same offsets
- [ ] The colour line is red-on-black and black-on-green, the same both ways

### The stack — where a panel model earns its keep

- [ ] Three panels overlap, `ONE` at the back and `THREE` in front
- [ ] `1` brings `ONE` to the front, and what it covers is covered the same
      way on both
- [ ] `2` then `3` reorder them, and the two screens still agree
- [ ] `h` hides the top panel and **what was behind it comes back** — the
      lower panel where they overlapped, and the plain background where they
      did not. This is the part that was wrong first time: a hidden panel
      stayed on the screen because nothing put the background back
- [ ] `s` brings them all back
- [ ] `m` moves the top panel, and it leaves nothing behind it — no fragment
      of border, no half a word

### Resizing

- [ ] Resize the terminal and the scenario redraws
- [ ] Do it on both, at the same size, and compare again

---

## The demo — `python3 -m tkcurses`

Widgets on the left, drawn the tkinter way. A curses window on the right,
drawn the curses way. One process, one screen, one refresh. Not two
applications taking turns: `initscr()` attaches to the screen the widgets are
already using.

- [ ] Both halves are on the screen at once
- [ ] The **Press** button still works with a curses window beside it — a
      curses window sharing the screen must not cost the widgets their input
- [ ] Pressing it updates the widget half **and leaves the curses half
      intact**. The widgets own the buffer and draw over anything in it, so
      the curses half has to be put back after every repaint
- [ ] Resize the terminal: both halves come back
- [ ] Escape gives the terminal back, with no traceback and a clean prompt

- [ ] The listbox in the demo has its **right-hand border on every row**.
      It did not when the demo was written — `TkCurses-ego`, fixed since —
      and the same fault was then found in the Spinbox by looking for the
      pattern rather than waiting to see it

---

## And the thing that would be worst

- [ ] After every run, by every exit, **the terminal is usable**. A curses
      program left in raw mode makes the shell unusable, which is the entire
      reason `wrapper()` exists. Press Escape, press Ctrl-C, resize it
      mid-run and then quit — the prompt comes back working every time
