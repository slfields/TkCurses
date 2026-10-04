# Acceptance: views, selections and columns

One question, five times over: **when something moved, did the right thing
move — and did everything else stay put?**

Fourteen pull requests (#119–#132) merged after the last checklist here
changed, and none had a person look at it. Several change what a person sees:
an Entry's view no longer chases its cursor, edits from code carry the
selection along instead of dropping it, a Listbox scrolls sideways, a Treeview's
columns fill its width, and ttk's `validate()` sets an `invalid` state. Each was
measured against Tk 9.0.2 and is pinned by tests. A test can say the numbers
agree with Tk. It cannot say whether a person watching can tell what happened.
`TkCurses-w1h`.

**The readout under the title is the instrument.** After every event it
reports where the entry's view starts, where its cursor is and what is
selected, how far the list has scrolled, the tree's column widths, and whether
the check field is invalid. Most of the boxes below are about reading it while
watching the widget it describes.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 42
```

**Escape** exits and **Ctrl-R** puts everything back. It wants a terminal at
least **90 columns by 23 rows**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-04 |
| Result | **Accepted.** Run by the author: "uat now passes", after the `validate()` repaint fault below was fixed. Terminal and size not recorded. The regression pass over 17, 22, 34 and 41 was not reported. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. This matches `UAT_ENTRY_VALIDATION.md` and
`UAT_TTK_CORE_WIDGETS.md`.

## The entry and its view (`TkCurses-i8s`)

The six buttons down the middle act on the entry at the top left, from code.

- [ ] Press **fill**. The entry shows `0123456789abcdefghijklmnopqr`, its
      **start**, though the cursor is at the end. The readout says
      `first shown 0  cursor 36`. *Tk does exactly this: a program's insert
      does not scroll. This used to show the end.*
- [ ] The scrollbar under it shows a thumb that **does not fill** the trough,
      at the left end
- [ ] Click the scrollbar's right arrow a few times. The text slides left and
      `first shown` rises, but **`cursor` does not change**
- [ ] Drag the thumb. Same: the view moves, the cursor stays
- [ ] Click into the entry and press **End**. Now the view follows the cursor,
      because a key did it. Typing past the right edge keeps the cursor in
      view too

## Edits around a selection (`TkCurses-61v`, `TkCurses-bfy`)

Press **Ctrl-R** and **fill** first.

- [ ] **select 2-8** highlights `234567`, and the readout says `selection 2-8`
- [ ] **insert XY@0** puts `XY` at the front. The highlight **stays on the same
      letters**, `234567`, and the readout says `selection 4-10`. *It used to
      vanish*
- [ ] **delete 0-2** takes `XY` off again. Still `234567`, `selection 2-8`
- [ ] **adjust 12** stretches the selection's nearer end to 12:
      `selection 2-12`, and **the cursor does not move**. *`selection_adjust`
      used to be `selection_to` under another name*
- [ ] **xview 5** scrolls the entry. `first shown 5`, and the selection and
      the cursor are unchanged
- [ ] Click into the entry, press **Home**, then **Left**. The cursor stays at
      the start. *Left at the start used to jump near the end*
      (`TkCurses-11m`)

## The list, sideways (`TkCurses-019`)

- [ ] The list's items are wider than the list, and its scrollbar's thumb
      shows that
- [ ] Click the right arrow. Every row shifts left together, and the readout's
      `first column` rises by one per click
- [ ] Drag the thumb to the right end. The longest item's end is in view, and
      no further

## The tree's columns (`TkCurses-a01`, `TkCurses-67u`)

- [ ] The three columns **fill the tree** to its right border. The readout
      says `14/5/11 of 34`. *They used to stop at 20 cells and leave the
      rest blank*
- [ ] Press **narrower**. `name` and `kind` shrink, and **`size` stays 5**,
      because it is the one built with `stretch=False`
- [ ] Press **wider** to go back. The same two grow, `size` still 5
- [ ] `build` is drawn in **cyan** and `big.iso` in **red**: row tags, which
      did nothing before #121

## The check field and `validate()` (`TkCurses-52q`)

The field's style maps ttk's `invalid` state to red. The default theme draws
nothing for it, so without the map there would be nothing to see.

- [ ] Type `a` into the check field. **Nothing happens yet**, because its mode
      is `none`
- [ ] Press **validate()**. The field turns **red**, and the readout says
      `check: invalid`. *validate() runs under every mode, `none` included*
- [ ] Clear the field, type `7`, press **validate()** again. The red goes and
      the readout says `check: valid`

## Housekeeping

- [ ] **Ctrl-R** puts every widget back: entry empty, list at the left, tree
      34 wide, check field plain
- [ ] Resize the terminal, smaller and then larger. Nothing overlaps, and the
      readout stays under the title

## Also run, as a regression pass

These scenarios touch the same code, and their checklists already say what
passing means:

- **17** (`docs/UAT_INTERACTIVE.md`): typing, cursor keys and the narrow
  field, plus its new Left-at-the-start item
- **22**: the spinbox's arrows and stepping
- **34** (`docs/UAT_TTK.md`): the Treeview's columns now fill it
- **41** (`docs/UAT_ENTRY_VALIDATION.md`): its entries are classic `tk.Entry`,
  whose validation rules are unchanged by `TkCurses-4ag`; this checks that

## Found while running it

- **Treeview tags drew the wrong colour** (`TkCurses-mur`). Found by this
  scenario's own tty test on its first run: `build`, tagged cyan, was red.
  A tag's colour pair was OR'd onto the row's, making a third pair. Every
  tagged row on a colour terminal had been wrong since #121.
- **`validate()` turned the field red one keystroke late, and never turned it
  back** (`TkCurses-b9q`). Found by a person running the checklist. Typing `a`
  and pressing `validate()` left the field plain; erasing the `a` turned it red;
  typing `7` and validating again left it red. `ttk.Widget.state()` changed the
  flags and repainted nothing, so what showed was always the state as of the
  last edit. Every themed widget had it, for every flag. The tty test passed
  throughout, because it checked the readout's `check: invalid` (the state)
  rather than the field's colour (what this checklist promises). It now checks
  the colour. So do the selection and list tests, which had the same blind
  spot, checking the readout's numbers rather than the highlight and the rows.
