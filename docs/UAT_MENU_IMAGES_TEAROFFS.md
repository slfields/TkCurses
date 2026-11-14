# Acceptance: menu images and tear-offs

Two questions, from `TkCurses-53hb`: **does a menu entry show its picture
where `compound` puts it**, and **does a menu tear off into a copy that
stays?**

A picture here is half-block pixels, two pixel rows to a cell, so an entry
with a 4x4 picture is two rows tall - and three when the label sits above or
below it. That is how every image draws in a terminal, and the reason a
menu of icons is taller than Tk's.

```bash
cd /path/to/TkCurses
python3 -m uat 50
```

**The readout** says what was chosen last and names every torn-off copy.
**F2** opens Tools, **F3** Colours, **F4** Icons; **Escape** closes a menu or
a torn-off copy; **Ctrl+Q** quits.

| | |
|---|---|
| Terminal | not recorded |
| Size | not recorded |
| Date | 2026-11-14 |
| Result | **Accepted.** Run by the author, dragging a torn-off menu included: "I've approved UAT 50". |

What is driven mechanically is the scenario 50 tests in
`tests/test_uat_scenarios_tty.py`; the boxes below are for a person.

## Pictures

- [ ] **F2**. Tools starts with a **dashed line**, then: **Hammer** with an
      orange square to its left; **Saw** with a cyan square above it;
      **Drill** as a yellow square and **no label** (`compound` `none`, Tk's
      default, shows the picture in the label's place); **Level** with a
      green square to its *right*, and `F9` at the far edge; **Magnet** with
      a grey square after its `[ ]`
- [ ] Each entry is as tall as its picture, and the highlight covers **all
      its rows** as the arrows move
- [ ] Choose **Magnet**. The readout says `Magnet on`; open Tools again and
      its square is **red** - its `selectimage`
- [ ] **F3**. Colours' squares are one row high, so it looks like an
      ordinary menu with a swatch beside each name

## A menu taller than the screen

- [ ] **F4**. Icons has twelve entries of two rows each and does not fit
- [ ] Press **Down** until it scrolls. It moves **a whole entry at a time**,
      and the active entry is never cut in half at the bottom edge
- [ ] **Return** on Brown: the readout says `icon brown`

## Tearing off

- [ ] **F2**, then **Down** onto the dashed line and **Return**. A copy of
      Tools appears **where the menu was**, titled `Tools` in its top border,
      without the dashed line; the readout says `torn off: .tearoff1`
- [ ] Click **Hammer** in the copy: the readout says `Hammer`, and the copy
      **stays**
- [ ] Click anywhere else: the copy stays - it is a window, not a popup
- [ ] **Drag the copy by its title** (the top border): it follows the
      pointer, its pictures with it, and stops at the screen's edges. No
      picture is left behind where it was
- [ ] Choose from it where it now is: the readout follows
- [ ] Click **Pens**, and tear its menu off: the copy is titled `Pens` and
      named `.tearoff2`
- [ ] With a copy focused (click it), **Escape** closes it
- [ ] *A difference from Tk:* Tk's copy is a toplevel your window manager
      moves and closes. Here TkCurses moves it, by its title as it moves a
      Toplevel, and Escape closes it
