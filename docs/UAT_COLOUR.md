# Acceptance: colour

Whether a colour looks right is a question only a person looking at it can
answer, and the answer is different on every terminal. This is the one part
of the library that genuinely cannot be checked any other way: the test suite
can prove that `#ff8000` resolved to colour 208, and only an eye can say
whether 208 looks like orange on the screen in front of you.

Four terminals matter, and all four are on any machine that has ncurses. Run
the same scenario under each and compare:

```bash
cd /path/to/TkCurses
TERM=xterm           python3 -m uat 31     # eight colours
TERM=xterm-16color   python3 -m uat 31     # sixteen
TERM=xterm-256color  python3 -m uat 31     # 256
TERM=xterm-direct    python3 -m uat 31     # 24-bit
```

> `xterm-direct` is the only one the automated tests cannot cover. In direct
> mode ncurses emits the colon-form escape (`ESC[38:2::r:g:bm`), which the
> test emulator does not parse and prints as text; real terminals handle it.
> So this tier is checked by eye here and nowhere else — worth a careful look.

From anywhere else: `TERM=xterm python3 /path/to/TkCurses/uat 31`. **Escape**
quits.

> Setting `TERM` this way tells ncurses to use less than your terminal really
> has, which is exactly the point — it is how one machine shows all three
> tiers. It does not change what your terminal emulator can do.

| | |
|---|---|
| Terminal | |
| `tput colors` | |
| `echo $COLORTERM` | |
| Size | |
| Date | |

---

## The one that matters most

**Line 2 has to be right.** It is the library's own answer to "how many
colours has this terminal got", and everything below it follows from it. If
it disagrees with `tput colors` in the same shell, stop: nothing further down
the page means anything, and that is the bug worth reporting.

---

## 31. The tier, the ramps and the backgrounds

`python3 -m uat 31` · `c` opens the colour chooser

### What it says about your terminal

- [ ] Line 2 names a tier — `NONE`, `BASIC`, `BRIGHT`, `EXTENDED` or
      `DIRECT` — and a count beside it
- [ ] That count matches `tput colors` run in the same shell
- [ ] Line 3 repeats the terminfo numbers it came from, so a wrong answer can
      be reported as numbers rather than as "the colours look wrong"
- [ ] Under `TERM=xterm` it says **BASIC (8)**; under `xterm-16color`,
      **BRIGHT (16)**; under `xterm-256color`, **EXTENDED (256)**; under
      `xterm-direct`, **DIRECT (16777216)**
- [ ] If line 4 shows `COLORTERM=truecolor`, the tier is still whatever
      terminfo said. That variable promises your *emulator* understands
      24-bit escape sequences; it promises nothing about the curses library
      in the middle, and acting on it would send colour numbers no curses
      expects

### The ramps

Four strips: a grey, then red, green and blue. Each is thirty-two steps of
the same smooth gradient, handed to the library to render however it can.

- [ ] In direct colour the ramps are genuinely smooth — every step of the
      thirty-two is its own colour, because there is no palette to round to
- [ ] At 256 the grey ramp is close to smooth — two dozen distinguishable
      greys rather than a gradient, but visibly a gradient's worth
- [ ] At 16 it is four bands: black, dark grey, light grey, white
- [ ] At 8 it is two: black and white. That is not a fault, it is eight
      colours
- [ ] The red, green and blue ramps band the same way, and each one is
      recognisably *that colour* getting brighter rather than drifting
      towards grey or yellow
- [ ] At 16 the blue ramp has one band fewer than red and green. That is the
      palette's shape: its blue is `#0000ee` and its bright blue is
      `#5c5cff`, so pure blue never reaches the bright one

### The backgrounds — the bug this began with

Two rows of eight blocks: the same eight hues as a dark background, then as
a bright one.

- [ ] At **8 colours the two rows look identical**, and that is correct. The
      only way to be bright there is `A_BOLD`, which brightens a foreground
      and has never done anything at all to a background
- [ ] At **16 and above the two rows differ**, block for block. This is the
      whole point of the tier work: a bright background is unreachable at
      eight and reachable above it
- [ ] Every block is solid, with no stray characters in it

### The chooser — `c`

The same question asked as a dialog, and it is shaped like Tk's: three colour
bars, three numeric entries, a `Selection:` box and a panel showing the
colour chosen.

- [ ] **The bars have as many steps as the terminal has intensities.** Two
      at 8 colours, three at 16, six at 256. Count them on each terminal —
      that is the thing this cycle exists to fix
- [ ] No two steps of a bar look the same as each other (except the blue bar
      at 16 colours, for the palette reason above)
- [ ] Each bar is **that channel alone**, black to full, and **does not
      change** when you move another channel. Tk repaints the other two
      strips as you move one; that is a live preview worth having on an X
      display and destructive here, because a bar has two to six steps and
      with the other channels mid-way the whole of it collapses to a single
      colour at 8 and 16. The panel shows the colour being built instead
- [ ] The `▲` under each bar sits under the step the channel is on
- [ ] Clicking a step sets that channel; **dragging along a bar** follows the
      pointer continuously
- [ ] Typing a number into a channel entry and pressing **Return** moves that
      bar. Out of range clamps to 0 or 255; nonsense becomes 0
- [ ] There is a **panel** under the `Selection:` box, a block several rows
      tall painted in the colour chosen — this is what answers "what have I
      actually picked", which three numbers do not
- [ ] The panel follows every change: a bar click, a channel entry, a typed
      selection
- [ ] Typing `#ff8000` into `Selection:` and pressing Return moves all three
      markers and the panel
- [ ] Typing `red` there works too — Tk hands whatever is typed to
      `winfo_rgb`, and so does this. What neither has, and neither should, is
      a list of colour names to pick from
- [ ] Typing something that is not a colour puts the old value back and does
      not crash
- [ ] **OK** answers with the colour shown, including one typed and not yet
      applied with Return
- [ ] **Cancel** and **Escape** both answer `(None, None)` — a pair, because
      callers write `rgb, name = askcolor()`
- [ ] After the chooser closes, the scenario still answers the keyboard

---

## Elsewhere

The scrollbar thumb was fixed in the same cycle and is checked where the
scrollbars are — **UAT 18** and **UAT 30**:

- [ ] A scrollbar thumb can be **picked up and dragged**, not only clicked
- [ ] The view follows the pointer: wherever within the thumb you grabbed it
      stays under your finger, rather than the thumb jumping so its top is
      where you clicked
- [ ] Pressing the thumb and letting go without moving scrolls **nothing**
- [ ] Clicking the trough still pages, and the arrows still step
