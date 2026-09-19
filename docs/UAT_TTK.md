# Acceptance: themed widgets

ttk is not a second set of widgets that happen to look different. It is the
same widgets with their appearance lifted out into a database that can be
changed from one place, and a state model the appearance is resolved
against.

So the question this round asks is not "does the progress bar fill". It is
**can you change how every widget of a class looks without touching any of
them** — and that is not something a test can answer, because the answer is
a screen that changed.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 33
```

From anywhere else: `python3 /path/to/TkCurses/uat 33`. **Escape** quits.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## The one that matters most

**Press `r` and watch three bars change together.** You will not have
touched any of them individually. The call names the *class*,
`TProgressbar`, and every bar that did not ask for something else follows.

If that works, the rest of this page is detail. If it does not, nothing else
here is worth checking.

> This did not work at first, twice. `Style.configure` changed the database
> and nothing already drawn moved, because a widget resolves its appearance
> when it paints — and the same was true of `theme_use`. A style that only
> takes effect on the next keypress is one nobody can demonstrate. Both now
> repaint; that is what these keys are checking.

---

## 33. The style engine

`python3 -m uat 33` · `r` restyle · `t` next theme · `d`/`a` disable or
activate · `s` own style · `g` sweep · `w` resizable window · `z` put it all
back

### Restyling a class

- [ ] `r` turns **all three** bars green at once
- [ ] Line 2 shows `TProgressbar foreground='green'` — the value came from
      the database, not from any widget
- [ ] `z` puts them all back to plain

### States — `d` and `a`

- [ ] `d` turns **only bar two** red. The other two are untouched, because
      that colour came from a `map` and a map is per widget-state, not per
      class
- [ ] `a` turns bar two yellow instead
- [ ] Line 2 reports `bar two state=('disabled',)` and then `('active',)`
- [ ] The keys are exclusive on purpose. Setting `active` while `disabled`
      is still on would change nothing, because the map lists `disabled`
      first and **the first matching entry wins** — correct, and baffling to
      watch, so the scenario clears one when it sets the other

### A style of its own — `s`

- [ ] Press `z` first, then `s`: bar two goes magenta, the others stay plain
- [ ] Bar two still has the **class's trough** — it took only the colour its
      own style set, and everything else from `TProgressbar`. That is a
      dotted style name inheriting, and it is the whole reason
      `Danger.TProgressbar` is spelled that way
- [ ] Line 3 shows `bar two style=Danger.TProgressbar`

### Themes — `t`

- [ ] The sample box changes character set: `┌─┬─┐` by default, then `+-+-+`,
      `╔═╦═╗`, `╭─┬─╮`, `╔═╦═╗` again for double, and blanks for minimal
- [ ] **The two horizontal rules change with it.** They are `Separator`
      widgets, and they are drawn with the theme's rail — so a separator
      matches the box beside it rather than merely resembling it
- [ ] Six themes, and `t` cycles back to the first
- [ ] Line 2 names the theme in use

> The themes are not tkinter's. Real ttk has `clam`, `alt`, `default` and
> `classic`, which describe bevels and shading a character grid cannot show.
> What varies here is which glyphs a border uses, so the themes are glyph
> sets. `default` is in both lists and means the same thing in both.

### Resizing a window — `w`

- [ ] `w` opens a window with a grip in its corner
- [ ] **Drag the `◢` and the window resizes**, following the pointer, and the
      grip stays in the corner it moved to
- [ ] `w` again closes it

> The first version of this widget said a grip could never resize anything,
> because "a terminal window is resized by the terminal". That conflated two
> windows. It is true of the **root**, whose size is the terminal's. It is
> not true of a `Toplevel`, which is the library's own window with a
> geometry and a place in the z-order — and dragging its corner is a real
> operation. `wm_resizable` is honoured per axis, so a window locked across
> grows only downwards.

### The bars themselves

- [ ] Three determinate bars at different values, each filled in proportion
- [ ] `g` starts the fourth sweeping, and the block **bounces** — out to the
      far end and back, not jumping to the start
- [ ] `g` again stops it, and the bar goes to **empty**, not to where it was.
      `stop()` resets the value; it is not a pause, and Tk's does the same
- [ ] The grip `◢` marks the bottom-right corner

---

## Known, and deliberate

- [ ] **The sample box is drawn from labels, not from a bordered widget.**
      The widgets that will draw boxes — Notebook, Treeview — are the next
      round's work. What the box shows is the character set they will use
- [ ] **The grip at the bottom of the main screen is a mark, not a handle**,
      and only because it sits on the **root** window — whose size really is
      the terminal's, which nothing an application draws can change

---

## And the thing that would be worst

- [ ] After every key, the scenario still answers the keyboard, and Escape
      still leaves you a working prompt
