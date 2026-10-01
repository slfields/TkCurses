# Acceptance: the themed core widgets

Ten widgets, and one question: **do they answer?**

Appearance is checkable by a test — the option surface is compared against real
`tkinter.ttk` in `tests/test_ttk_option_surface.py`, widget by widget, and a
gap that nobody owns fails the suite. What a test could not show is whether a
gesture arrives, and that is where this epic lost a widget.

**`ttk.Panedwindow` shipped with a sash that could not be dragged.** It
registered press, motion, release and key handling under the *classic* widget's
name while reporting `TPanedwindow`, so it was offered none of them. The sash
drew perfectly. Its `pane()` and `sashpos()` methods worked when called. The
option surface was right. 4365 tests were green. A hand on the sash would have
found it in seconds.

That is the argument for this scenario, and for running one like it **early**
in a cycle rather than at the end. The dev-cycle skill says so; this is what
ignoring it costs.

The cause is worth knowing because it has now happened five times here.
Binding tags name one class and not a chain: a widget whose `winfo_class()`
answers `TButton` is offered what is bound to `TButton`, and nothing bound to
`Button` reaches it. So a themed widget must install its own bindings under its
own name — and a classic widget that hardcodes its name instead of asking
`winfo_class()` leaves every subclass with none. Both directions have bitten
this project: `Spinbox`/`Entry`, `OptionMenu`/`Menubutton` and
`ScrolledText`/`Text` from the subclass side, then `Button` and eight more from
the base side.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 40
```

The scenario exits on **Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-01 |
| Result | **Accepted.** Run by the author; terminal and size not recorded. |

The boxes above are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them individually would claim a
record that was not taken. Three faults were found and fixed between the first
run and the acceptance — they are listed at the end.

## Does it answer?

The line near the bottom names the last widget that responded. Use each one and
watch it change. **A widget that draws correctly and reports nothing is the
failure this scenario exists to catch.**

- [ ] **ttk.Button** — click it, and separately reach it with `Tab` and press
      `space`. Both must report
- [ ] **ttk.Checkbutton** — click it; the box fills and empties
- [ ] **ttk.Radiobutton** — pick each of the two; choosing one unchooses the
      other, because they share a variable rather than because anything copies
- [ ] **ttk.Menubutton** — open it and choose an entry
- [ ] **ttk.Entry** — type into it. An entry that takes keys and does nothing
      with them looks identical until you try
- [ ] **ttk.Spinbox** — step it with its arrows and with `Up`/`Down`
- [ ] **ttk.Scrollbar** — drag it
- [ ] **ttk.Panedwindow** — **drag the sash.** The panes either side must
      resize. This is the one that was broken
- [ ] `Tab` all the way round — every themed widget takes focus in turn and
      none of them swallows the traversal

## The classic column is the control

Each themed widget has its classic counterpart beside it. They are there to be
compared, not decorated.

- [ ] `Ctrl-R` restyles every themed class — the **left** column changes and
      the **right** column does not. Both changing means the style is not
      scoped to the themed classes; neither changing means nothing reaches the
      style database at all
- [ ] `Ctrl-B` puts it back
- [ ] `Ctrl-T` cycles the theme, and the themed widgets follow it while the
      classic ones stay put. Under `rounded` a themed button's corners are
      `╭ ╮ ╰ ╯` and the classic one beside it keeps `┌ ┐ └ ┘`; under `ascii`
      they are `+`. **This is the item that failed on the first run** — see
      below
- [ ] Under every theme, go round the widgets again. **One that works under one
      theme and not another is not themed**, it is coincidentally styled

## Frames

- [ ] **ttk.Frame** draws a border from the theme
- [ ] **ttk.Labelframe** puts its caption in the border rather than above it
- [ ] Both follow `Ctrl-T`

## Afterwards

- [ ] Escape leaves cleanly, terminal usable, no `reset` needed
- [ ] Resize the terminal — nothing overlaps or loses a border

---

## What has been found here

**In the widgets.** Two, and the scenario found the second one the first time a
person ran it, which is the best argument for it that could be made.

`ttk.Panedwindow`'s dead sash, above — found while building `3h5.4`, not by this
scenario, because this scenario was written last.

**Nothing here was drawn from the theme** (`TkCurses-5vu`, fixed). `Ctrl-T`
changed the label and not one glyph on screen; measured across all four themes
the border glyphs were byte-identical, while scenario 34 under the same key
gained `+` and `|`. Frame, Labelframe, Button, Checkbutton, Radiobutton,
Menubutton, Entry, Spinbox and Scrollbar inherited the classic widget's drawing
entirely. The epic set out to give them "an appearance resolved from the style
database", and they had a class name and an option list instead.

Fixed in one place rather than nine: every one of them paints through
`_Drawable._draw_border`, which now asks an overridable `_border_style()`, and
the themed mixin answers with the theme's glyph set. The relief still decides
the weight — bold for `raised`, dim for `sunken` — because a glyph set does not
carry that, and `flat` still draws nothing, since a theme must not put a box
around a widget that asked for none.

The automated test for that claim was worthless and is worth recording as such:
it asserted the theme **label** changed, which is the scenario's own Label
widget. It passed throughout, so the gap reached a person rather than being
caught here. It now reads the drawn border glyphs.

**`Ctrl-R` recoloured nothing** — the same gap one layer over, reported on the
second run. The glyph fix above settled *which* characters a themed widget
draws; the colours still came from the classic `_background_attribute`, which
reads the widget's own options and never the style database. So
`Style.configure("TButton", background="blue")` reached nothing. The themed
mixin now resolves colours through `_themed_attribute`, which keeps the right
precedence: a widget handed `foreground=` directly still wins.

**The scrollbar drew seven of its nine rows** — reported on the third run, along
with the two observations that pinned it: the eighth row still answered clicks,
and a restyle showed blue two rows past the last glyph. A vertical scrollbar is
one cell *wide*, so `_border_drawn` is False while `_bordered` is True;
`_length()` deducted two rows for a border that `_redraw` inset by nothing. The
existing scrollbar tests could not have found it — their fixture is
`relief="flat"`, "with no border to complicate it". Eight other `_bordered`
measurements are now filed for audit against what they actually paint.

**And the scrollbar's thumb not moving was this scenario's fault, not the
widget's.** A scrollbar is a remote control: it asks its command to scroll
something, and the thing scrolled calls `set()` back. The command was wired to
the report line and nothing else, so the thumb correctly never moved — measured
against real ttk, which behaves identically. It is now wired to a Listbox of
thirty items, so dragging scrolls the list and the thumb follows it.

**In the scenario**, both by driving it before handing it over:

- Every bordered widget is three rows tall and they were placed two rows apart,
  so each one ate the previous one's bottom border — the checkbutton sat on the
  button's. The same fault was reported by hand against UAT 38's status line,
  which is twice now, and it is invisible until something is actually drawn.
- The first attempt to drive a click found nothing responding, themed *and*
  classic. The scenario was fine: sending press and release back to back makes
  both escape sequences land in one read, and ncurses holds the release until
  something else arrives. `tests/test_button_tty.py` records this, with a drain
  between the two. Reading that first would have saved the detour.

**Driven mechanically**, so it is on the record rather than resting on a tick:
`tests/test_uat_scenarios_tty.py` clicks the themed button, reaches it with
`Tab` and `space`, works the theme and restyle keys, and **drags the sash and
asserts where it ends up** — not merely that a handler fired, since a handler
that fires and moves nothing would satisfy that. Reintroducing the binding bug
makes the sash test time out, which is how it was checked to be worth having.
