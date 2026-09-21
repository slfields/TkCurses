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
activate · `s` own style · `g` sweep · `w` a window to drag and resize ·
`b` a borderless one · `z` put it all back

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

### Moving a window — `w` and `b`

Row 2 of the screen reports `window=` and `borderless=` as `+x+y`, so a
window's position can be read rather than guessed.

There is no window manager in a terminal, so **TkCurses is one**, and this is
the half of that job it does itself. See ARCHITECTURE.md, "Window
Management".

- [ ] With `w` open, **drag its title row** — the top border, where the title
      is — and the window follows the pointer
- [ ] **The window arrives with everything in it** — the text and the `◢`
      travel with the border, and nothing is left behind at the old position.
      This failed the first time it was tried: the window moved and turned up
      empty (`TkCurses-bk8`)
- [ ] **The grip still resizes** after the window has been moved
- [ ] The column of the title you grabbed **stays under the pointer**. It
      moves by the distance travelled, not to the position arrived at, so the
      window does not jump so its corner meets the cursor
- [ ] **Drag the window's body** — anywhere below the title row — and it does
      **not** move. The title row is the handle, and everything else belongs
      to whatever widget is there
- [ ] Drag it **hard against an edge** and it stops at the edge rather than
      going off the screen. `window=` stops changing
- [ ] With another window behind it, **pressing the title raises it** to the
      front before the drag begins

Then the other half, which is the application's rather than the library's:

- [ ] `b` opens a **borderless** window, lower right, with no border and no
      title
- [ ] **Press it anywhere and drag** — it moves. Not because the library
      moved it, but because the scenario binds `<Button-1>` and `<B1-Motion>`
      itself, in the textbook tkinter way and with no TkCurses-specific code
- [ ] `b` again closes it

> This is the whole rule in one screen: **decoration decides who drags.** A
> decorated window is moved by TkCurses from its title row, because that is
> the window manager's job and there is no window manager. A borderless one
> has nothing to grab, so it is the program's to move — exactly as on a
> desktop, where `overrideredirect(True)` means the same thing. If the
> borderless window moves when the ordinary window's *body* does not, both
> halves are behaving.

> **Not checked here:** a window that has been dragged fires no
> `<Configure>` (`TkCurses-b5o`), so an application doing its own dragging
> has to read `winfo_x()`/`winfo_y()` rather than hear about the move. The
> scenario does exactly that.

### The bars themselves

- [ ] Three determinate bars at different values, each filled in proportion
- [ ] `g` starts the fourth sweeping, and the block **bounces** — out to the
      far end and back, not jumping to the start
- [ ] `g` again stops it, and the block goes back to **the start**, not
      staying where it had swept to. `stop()` resets the value to zero; it is
      not a pause, and Tk's does the same — measured, a running bar reads 30
      and reads 0 after `stop()`
- [ ] Back at the start the block is still **drawn**, six cells of it. An
      indeterminate bar at zero is a block at the left, not an empty trough —
      emptying is what a *determinate* bar at zero does, and the two modes
      differ here on purpose
- [ ] The grip `◢` marks the bottom-right corner

---

## 34. The widgets you operate

`python3 -m uat 34` · **^T** next theme · **^R** restyle every class ·
**^B** back to default · Escape quits. Everything else is the mouse and the
arrow keys, on the widgets themselves.

> The control keys are deliberate. This screen has a combobox on it, and a
> combobox is an Entry underneath — a plain `t` would land in the field
> whenever it had the focus. Scenario 33 has no text field and uses plain
> letters.

Scenario 33 asked whether appearance lives in one place. This one asks
whether the widgets built on it behave like the tkinter widgets they claim
to be, which only a hand can answer.

### Combobox

- [ ] Clicking it drops a **bordered** list of four values, as Tk's popdown
      is bordered
- [ ] Clicking a value puts it in the field, and line 1 shows
      `combobox='...'`
- [ ] **Escape closes the list and changes nothing**
- [ ] **A click anywhere else closes it** too — including a second click on
      the combobox, which never sees that click: the list holds the grab
- [ ] **Type into it.** It is an Entry underneath, and a combobox that took
      keys and did nothing with them would look identical until you tried.
      It did exactly that at first (the fifth time a widget reported a class
      nothing was bound to)
- [ ] The Down arrow opens the list

### Notebook

- [ ] **It looks like a notebook**: a box per tab standing on the page
      frame, and the selected tab **open at the bottom** so that it and its
      page are one space rather than two things near each other. That shape
      is what makes the widget recognisable, and the first version did not
      have it — the tabs were drawn into the frame's top line, which cost a
      row less and read as a row of words

```
 ┌─────┐┌─────┐┌───────┐
 │ One ││ Two ││ Three │
┌┘     └┴─────┴┴───────┴─────┐
│                            │
│  page one                  │
└────────────────────────────┘
```

- [ ] Three tabs, the selected one marked — a mark rather than a colour, so
      it reads on a terminal with none
- [ ] **Switch tabs several times and watch the frame.** The right and
      bottom border must stay drawn. Selecting the second tab used to eat
      both, and they stayed eaten whichever tab was chosen afterwards
- [ ] **Go to tab 2, then back to tab 1.** Its contents must still be there.
      They were not: a page shown, hidden and shown again came back below
      the notebook's own panel, which drew its blank background over it
- [ ] Clicking a tab shows its page; Left and Right move between them
- [ ] **Exactly one page is on screen.** Two at once is the failure worth
      watching for: it is what the widget did first, because a container
      taken off screen used to leave its children behind (`TkCurses-mlw`)

### Treeview

- [ ] `documents` starts open, `pictures` closed
- [ ] **A closed branch hides its rows entirely** rather than marking them
- [ ] Clicking the `▸` opens a branch; clicking the row selects it, and
      line 2 names the selection
- [ ] Children are **indented** under their parent
- [ ] The `Size` values line up under the `Size` heading. They did not at
      first: the widget drew its heading three rows low and its last row on
      top of its own bottom border, which only shows when the widget is not
      at the origin — the unit tests were happy and this screen was not
- [ ] **Click a row, then use Up and Down.** They move the selection. They
      did nothing at first: `Treeview.focus` is the *row* the keyboard is
      on, shadowing `Misc.focus`, so clicking set the row and never gave the
      widget the keyboard
- [ ] Tab reaches the tree, which is focusable — a Frame is not, and it
      inherited that

### LabeledScale

- [ ] Clicking along the trough moves the handle
- [ ] **The number above it follows.** They share a variable; nothing copies
      one to the other
- [ ] A scale drawn as a trough at all is worth noting — it drew nothing
      until it was told `orient="horizontal"`, because the *classic* Scale
      defaults to vertical where `ttk.Scale` defaults to horizontal

### OptionMenu

- [ ] The button shows the current value
- [ ] Clicking posts the menu — **upwards**, if there is no room below it
- [ ] The entries carry radiobutton markers `( )` and `(•)`, not plain
      labels. ttk builds radiobutton entries where the classic widget builds
      commands; both are in this library, each matching its own original
- [ ] Choosing one changes the button and line 1's `option='...'`

### Under another theme, and restyled

- [ ] **^T** changes the theme, and every widget above redraws in it —
      borders, rails and markers. A widget that only looks right in one
      theme is not themed
- [ ] Operate each widget again under the new theme. Everything above should
      still hold
- [ ] **^R** paints five different widget classes at once from the style
      database, while they are on screen
- [ ] **^B** puts the theme and the styles back

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
