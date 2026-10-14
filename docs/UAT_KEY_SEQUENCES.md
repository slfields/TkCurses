# Acceptance: key sequences

One question: **do chords such as Ctrl-X Ctrl-S work the way Tk's do?**

Until `TkCurses-jfm` a binding could name only one event. Now
`<Control-x><Control-s>` and `"gg"` bind and fire. The rules are Tk's,
measured in both Tk 8.6 and 9.0 and read from Tk's own source; ARCHITECTURE.md's
"Multi-event sequences" has them, with a table.

**The readout** shows the last key pressed, every chord that has fired, and
which widget has the focus — the chords are bound on `pad`, so `focus:` should
say `pad`. **Ctrl-R** clears the readout and puts the focus back; **Escape**
quits.

```bash
cd /path/to/TkCurses
python3 -m uat 45
```

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-13 |
| Result | **Accepted.** Run by the author: "uat 45 passes". Terminal and size not recorded. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. What was driven mechanically, and so is on the record, is the
scenario 45 tests in `tests/test_uat_scenarios_tty.py`.

## The chords fire

- [ ] **Ctrl-X then Ctrl-S**: `chords:` gains `save`
- [ ] **Ctrl-X then Ctrl-F**: `find`
- [ ] **g then g**: `top` — two plain letters are a chord too
- [ ] **d then d**: `delete line`
- [ ] **Ctrl-S on its own** does nothing to the terminal: it does not freeze.
      *A terminal with flow control on would treat Ctrl-S as "stop output";
      TkCurses turns that off*

## What cancels a chord, and what does not

- [ ] **Ctrl-X, a, Ctrl-S**: nothing fires. Another key in between cancels it
- [ ] **Ctrl-X, a click anywhere, Ctrl-S**: nothing fires. So does a click.
      If `focus:` no longer says `pad` afterwards, press **Ctrl-R**
- [ ] **Ctrl-X, wait ten seconds, Ctrl-S**: `save` fires. *There is no time
      limit, in Tk either*
- [ ] **Ctrl-X, Ctrl-X, Ctrl-S**: nothing fires — and **Ctrl-X three times,
      then Ctrl-S**, does. *That is Tk's own behaviour, odd as it is, measured
      in both Tk 8.6 and 9.0: the second Ctrl-X cancels the first and is used
      up doing it*
- [ ] **g, g, g**: `top` fires once, on the second g; a fourth g fires it
      again. *The g that finishes a chord cannot start the next one -
      measured in both Tks, which fire 1, 1, 2, 2, 3 times for 2 to 6 presses*

## Known, and deliberate

- A chord never spans two widgets, in Tk either: press Ctrl-X in one and
  Ctrl-S in another, and nothing fires. This screen has only the one place
  that takes keys, so it cannot be tried here.
