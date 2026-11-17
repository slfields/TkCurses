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

**The readout under the title** shows what this program's clipboard and
PRIMARY selection hold after every event, and on its second line **how the
clipboard reaches the rest of your desktop** — see "Reaching other
applications" below.

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
| Result | **Accepted.** Run by the author: "I consider uat 43 as complete, now", after the five faults listed at the end were fixed. Terminal and size not recorded. "Reaching other applications" was added afterwards (`TkCurses-hpr`) and accepted on its own on 2026-10-13: "That works". Whether `wl-copy` flickers on GNOME was not reported either way. "Middle-click paste in other applications" (`TkCurses-r1k1`) accepted on 2026-11-14: "I don't notice any flicker for loss of focus when using middle click paste." |

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

## Reaching other applications

*Added after the acceptance above, with `TkCurses-hpr`, and accepted
separately on 2026-10-13.* A copy here can now
leave the program, and a copy made elsewhere can be pasted in. There are two
routes, chosen when the program starts, and the readout's `system:` names the
one in use:

- **OSC 52** — the terminal sets the clipboard. Chosen when the terminal says
  it can. **Yours cannot**: Ptyxis and GNOME Terminal are VTE, which declines
  OSC 52 on security grounds, and a raw probe in your terminal confirmed it.
  kitty, foot and WezTerm can.
- **The desktop's clipboard tool** — `wl-copy` and `wl-paste` on Wayland,
  `xclip` or `xsel` on X11. Works in any terminal, VTE included, on the
  machine the desktop is on (not over SSH). It is **not installed yet**:

```bash
sudo dnf install wl-clipboard
```

Before installing it:

- [ ] The readout says `system: no OSC 52, and wl-copy not installed
      (wl-clipboard)`
- [ ] Copy something with **Ctrl-C** and quit with **Escape**. Once the screen
      is back, one line says the copy **stayed inside this program**, and why

After installing it:

- [ ] The readout says `system: the desktop's wl-copy`
- [ ] Select `hello` in **source** and press **Ctrl-C**. Paste into another
      application — a text editor, a browser's address bar. `hello` arrives
- [ ] Copy some text in another application, click into **target** here and
      press **Ctrl-V**. That text arrives
- [ ] Quit. **No** "stayed inside" line this time
- [ ] Watch, while copying and pasting, whether anything **flickers** or a
      window briefly appears: GNOME does not give clipboard tools a way to
      work unseen, and `wl-clipboard` may briefly show a window of its own to
      reach it. *Not measured yet - this checklist is where it would be*

Middle-click paste in other applications, with `wl-clipboard` installed
(*added by the terminal-environment cycle, `TkCurses-r1k1`*). Selecting is
enough here, with no Ctrl-C: a Tk program on X11 does the same.

- [ ] Drag across `hello` in **source** and let go. Wait half a second, then
      **middle-click** in another application's text field. `hello` arrives
- [ ] Select something else in **source** and middle-click elsewhere again.
      The new selection arrives, not the old one
- [ ] The clipboard is untouched by that: **Ctrl-V** in another application
      still pastes what was last copied with Ctrl-C
- [ ] Watch while you drag out a selection and let go: does anything
      **flicker**, does a window appear, does the terminal lose focus for a
      moment? GNOME gives `wl-copy` no way to set a selection unseen, so it
      may. *Run by the author on GNOME, 2026-11-14: no flicker and no loss
      of focus*
- [ ] Run it as `TKCURSES_CLIPBOARD_PRIMARY=0 python3 -m uat 43`. Selecting
      and middle-clicking elsewhere pastes whatever was there before

The setting, either way:

- [ ] Run it as `TKCURSES_CLIPBOARD_SYSTEM=off python3 -m uat 43`. The
      readout says `turned off`, a copy stays inside, and quitting says
      **nothing** — you asked for it
- [ ] *Optional*, in **foot** or **kitty** (`sudo dnf install foot`): the
      readout says `OSC 52 - the terminal says it has it`, and a copy here
      pastes elsewhere

## Pasting with the terminal's own paste

Added for `TkCurses-tcbj.22`, after the acceptance above, and not yet run.
Your terminal's paste - Ctrl-Shift-V, Shift-Insert, the middle button, or
its menu - does not reach the program as a paste at all: the terminal types
what it holds. TkCurses now asks the terminal to mark the start and end
(bracketed paste), and puts the whole of it in as one piece. For each,
first copy something **in another window** - this page will do.

- [ ] Copy two lines, and paste them into **text** with your terminal's
      paste. Both lines appear as two lines, the cursor after them, and
      nothing else - no `200~`, no `~`
- [ ] Paste the same two lines into **target**. They arrive on one line,
      the line break a space
- [ ] Copy a line with a tab in it (from a Makefile, say) and paste it into
      **text**: the tab is kept
- [ ] Select a word in **target** and paste: the word is replaced
- [ ] Paste into **read-only**: nothing changes
- [ ] **Ctrl-Z**. The shell comes back, and pasting at its prompt shows no
      `200~` around what you pasted. `fg`, and the program is back, redrawn;
      a paste into **text** still arrives as above, and dragging in
      **source** still selects
- [ ] Quit, then run `cat` at the prompt and paste. What appears is what
      you copied, with no `^[[200~` in front of it. Ctrl-D ends `cat`
- [ ] Run it as `TKCURSES_INPUT_BRACKETED_PASTE=0 python3 -m uat 43`. A paste
      into **text** is typed, as before this change

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
