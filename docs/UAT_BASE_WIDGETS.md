# Acceptance: base widget system

The automated suite drives a real pseudo-terminal and asserts on what reaches
it, which settles whether the right characters land in the right cells. It
cannot tell you that a window looks wrong, that a resize leaves the display
confused, or that Ctrl-C hands back a terminal you can still type in. This
checklist is for those questions.

**How to run**

`uat/` is a development tool at the repository root, not part of the installed
package, so Python finds it only when the root is where you are:

```bash
cd /path/to/TkCurses
python3 -m uat            # list the scenarios
python3 -m uat 3          # run the third
```

From anywhere else, give the path instead — the runner puts itself on the
path when invoked this way:

```bash
python3 /path/to/TkCurses/uat
python3 /path/to/TkCurses/uat 3
```

Each scenario also runs on its own from the repository root, for example
`python3 -m uat.scenario_03_stacking`, which is the form the list prints.
Every scenario exits on **Escape**.

> `python3` is spelled out because plenty of systems have no `python` at all.
> Use whichever name is your Python 3 interpreter.

**Before you start**, note the terminal you are using and its size — behaviour
differs between emulators, and a failure is much easier to chase with that
written down.

| | |
|---|---|
| Terminal | |
| Size | |
| Date / version | |

---

## The one that matters most

If you only check one thing, check this: **after every scenario ends, however
it ends, the terminal must still work.** Prompt back, cursor visible, typing
echoed, no stuck raw mode. A curses program that gets this wrong leaves the
user with a shell they have to `reset` or close. Scenario 9 exercises all four
ways out deliberately; the others should be checked for it in passing.

---

## 1. Root window

`python3 -m uat 1`

Watch the screen come up, then press Escape.

- [ ] The terminal clears and the title line is readable
- [ ] After Escape the prompt is back
- [ ] The cursor is visible again
- [ ] What you type appears

## 2. A window above the root

`python3 -m uat 2`

- [ ] A box is drawn in single lines, not letters like `lqqqk`
- [ ] Its title is centred on the top edge
- [ ] Background text is visible around it, and not through it
- [ ] The border is unbroken at all four corners

## 3. Stacking

`python3 -m uat 3`

Press `1` and `2` to raise each window.

- [ ] The raised window's border is unbroken
- [ ] It covers the other where they overlap
- [ ] Pressing the same key twice changes nothing
- [ ] Nothing of the covered window shows through

## 4. Window manager

`python3 -m uat 4`

Press `m` move, `h` hide, `s` show, `f` fullscreen, `r` restore.

- [ ] The window moves in whole cells with no smearing or leftovers
- [ ] Hiding leaves the text behind it intact
- [ ] Showing brings it back where it was
- [ ] Fullscreen fills the terminal exactly, to all four edges
- [ ] Restore returns it to its original size and position

## 5. Terminal resize

`python3 -m uat 5`

Drag the terminal's edge, or resize the pane.

- [ ] The reported size follows the real one
- [ ] The count of resizes increases once per resize, not several times
- [ ] The window stays inside the screen
- [ ] Nothing is left drawn outside the new bounds
- [ ] Making the terminal *smaller than the window* clamps it rather than
      drawing off the edge

## 6. Keyboard and mouse

`python3 -m uat 6`

Type letters, arrows, function keys, modified keys. Click and drag.

- [ ] Every key pressed is named, and the name matches the key
- [ ] Arrows report `Up`/`Down`/`Left`/`Right`, not escape sequences
- [ ] Modifiers show in `state` when held
- [ ] Mouse positions match where you clicked
- [ ] A drag reports motion between press and release

> Known gap: punctuation reports the character (`+`) rather than the X11
> keysym name (`plus`) that tkinter uses. Tracked as **TkCurses-82n**.

## 7. Timers and idling

`python3 -m uat 7`

Leave it alone for half a minute, then type.

- [ ] The clock ticks about once a second without you touching anything
- [ ] Idle CPU is negligible — check with `top` in another pane
- [ ] Typing is answered immediately while the clock is running

## 8. Variables and traces

`python3 -m uat 8`

Press `+`, `-`, `r`.

- [ ] Both lines update together
- [ ] The trace fires exactly once per change, not twice or none
- [ ] The value the trace sees is the new one, not the old

## 9. Failure modes

`python3 -m uat 9`

Run it four times, ending it differently each time: `q`, `c`, `x`, and Ctrl-C.

- [ ] `q` — quits cleanly, terminal usable
- [ ] `c` — the callback raises and **the application keeps running**
- [ ] the traceback reads normally: every line starts at the left edge, not
      stepping further right down the screen
- [ ] the traceback lands on top of the display and is *not* cleaned up
      afterwards — expected for now, tracked as **TkCurses-k0k**
- [ ] `x` — the application ends, terminal usable
- [ ] Ctrl-C — the application ends, terminal usable
- [ ] After all four: prompt back, cursor visible, typing echoed, no `reset`
      needed

---

## What this cannot cover yet

There are no widgets to look at. Nothing renders a label, a button, or a focus
ring, so these scenarios judge windows, input, timers and shutdown — not
appearance. Two things deliberately left out until the widget set exists:

- **Focus is invisible.** Tab traversal works and `focus_get()` is correct, but
  nothing draws which widget has focus, so there is nothing for a person to
  accept.
- **Instructions are drawn through internal API.** The scenarios write to the
  screen buffer directly because there is no public way to put a character on
  screen yet. When `Label` lands they should be rewritten to use it, which
  would make them exercise the real thing.
