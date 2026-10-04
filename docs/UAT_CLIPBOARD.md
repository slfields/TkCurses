# Acceptance: copy, cut and paste

One question: **can a person move text from one field to another, and can
they still close the program?**

The clipboard API came with the base class (`TkCurses-lrc.1`), and until
`TkCurses-lw2` no widget used it: there was no key in any field that copied,
cut or pasted. It had no human acceptance at all. This is that acceptance.

**Ctrl-C is the hinge.** It is the program's close gesture, and in the
author's terminal it is also the only one of Tk's copy keys that reaches a
program at all — measured with a key probe: Ctrl-Insert and Ctrl-Shift-V
arrive as nothing, Ctrl-Shift-C arrives as plain Ctrl-C, Alt-W as Escape then
`w`. So **Ctrl-C copies when the focused field has a selection, and closes
the program when it has none.** Most of what follows checks one half or the
other.

**The readout under the title** shows what the clipboard and the PRIMARY
selection hold, after every event. The clipboard is this program's own —
nothing copied here reaches another application yet (`TkCurses-hpr`) — so the
readout is the only place to see a copy before pasting it.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 43
```

**Escape** quits, **Ctrl-R** resets, and so does **Ctrl-C with nothing
selected**. It wants a terminal at least **90 columns by 24 rows**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-04 |
| Result | **Accepted.** Run by the author: "I consider uat 43 as complete, now", after the five faults listed at the end were fixed. Terminal and size not recorded. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. This matches `UAT_VIEWS_AND_SELECTIONS.md` and
`UAT_TTK_CORE_WIDGETS.md`. What was driven mechanically, and therefore is on
the record, is the scenario 43 tests in `tests/test_uat_scenarios_tty.py`.

## Cut and paste

Select by **dragging** with the left button, with **Shift and the arrows**, or
with **Ctrl-/** for everything.

- [ ] **Drag** across `hello` in **source**. It highlights as you drag, the
      cursor follows the pointer, and `PRIMARY` reads `'hello'`. Drag back
      past where you started and the selection turns round. *Entry had no
      drag at all until the first run of this checklist found it*
      (double-click, Shift-click and dragging past the edge are `TkCurses-svtr`)

- [ ] In **source**, press Home, then Shift-Right five times. `hello` is
      highlighted, and the readout's `PRIMARY` reads `'hello'`
- [ ] **Ctrl-X**. The field reads ` world`, and `clipboard` reads `'hello'`
- [ ] Click into **target** and press **Ctrl-V**. `hello` appears there
- [ ] Try **Ctrl-W** to cut and **Ctrl-Y** to paste: the same, by other keys
- [ ] **Shift-Delete** with a selection cuts it, rather than deleting one
      character
- [ ] Paste with something selected: **the selection is replaced** by what
      was pasted, in an entry and in the text. *Classic Tk on Linux keeps the
      selection and inserts at the cursor; this follows ttk, Windows and
      macOS instead - a deliberate departure, chosen on this checklist's
      first run*
- [ ] In **read-only**, select and paste: nothing changes

- [ ] **The cursor is your terminal's own**, blinking (if your terminal
      blinks it) and in your terminal's shape. With `hello` selected and the
      cursor just after it, you can tell the two apart. *It used to be a
      painted reversed cell, the same as a selection - found on this
      checklist's first run*
- [ ] Click from field to field. The cursor goes with the focus, and only the
      focused field ever shows one

- [ ] **One selection at a time.** Select in **source**, then in **read-only**:
      source is no longer selected. Then select in **text**: read-only is no
      longer selected. *All three stayed highlighted at once on this
      checklist's first run; Tk clears the earlier one, measured*

## Ctrl-C: copy, or close

- [ ] Select something in **source** and press **Ctrl-C**. `clipboard` reads
      it, the field is unchanged, and **the program is still running**
- [ ] Press **End**, which drops the selection, and **Ctrl-C** again. The
      program closes, cleanly, with no traceback
- [ ] (If your terminal copies with **Ctrl-Shift-C**: it arrives as Ctrl-C, so
      with a selection it copies here too, and without one it closes)

## The edges

- [ ] **masked**: Ctrl-/ then Ctrl-C. The clipboard reads `'******'` — what
      the field *shows*, not the secret. *Tk does the same*
- [ ] **read-only**: Ctrl-/ then Ctrl-X. The clipboard gets the text, and the
      field **keeps** it: a read-only field copies on cut and refuses the
      delete. Ctrl-V there does nothing
- [ ] **text**: Ctrl-/ then Ctrl-C. The readout shows both lines copied,
      `'line one\nline two'`
- [ ] **The middle button**: select `hello` in source, then middle-click in
      **target**. `hello` goes in where you clicked. *If your terminal pastes
      on the middle button itself, you will see its paste instead — that is
      the terminal, not the program*
- [ ] With the clipboard empty (Ctrl-R), Ctrl-V does nothing, and says nothing

## Your terminal's own keys

These belong to the terminal rather than the program, and are listed so a
surprise is not reported as a fault:

- **Shift-Insert** usually pastes the *system* clipboard as typed text.
  It works, but it is the terminal typing, not this program pasting
- **Ctrl-Insert** and **Ctrl-Shift-V** may do nothing at all here

## Faults found by running it

Each was found by the author running this scenario, and fixed on PR #134
before the acceptance:

1. **Ctrl-Insert and Ctrl-Shift-V did nothing.** The terminal does not pass
   them on, measured with a key probe. Ctrl-C was made to copy when there is a
   selection, the author's choice.
2. **Dragging did not select in an entry.** Entry had no drag; it now follows
   Tk's `tk::EntryMouseSelect`.
3. **The cursor could not be told from a selection.** Both were a reversed
   cell. The cursor is now the terminal's own.
4. **Several fields stayed selected at once.** Tk keeps one selection: taking
   PRIMARY now clears the previous owner, and a Text takes PRIMARY at all.
5. **Paste did not replace the selection.** That is classic Tk's rule on Linux;
   the author chose to replace, as ttk and Windows and macOS do. It is
   recorded in ARCHITECTURE.md as a deliberate departure.
