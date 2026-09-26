# Acceptance: undo, search, and where a character is

Three groups of `Text` methods that the automated suite can check for
correctness and cannot check for *usability*. That distinction is the whole
reason this checklist exists.

An undo stack that groups wrongly is correct edit by edit: every character
goes on and comes off in the right order, and no test of a single edit can
tell that anything is wrong. It is only maddening to **use** — undo becomes
backspace with extra steps, and taking back a sentence means holding Ctrl-Z
down and watching it crawl. So what is being judged below is the *grouping*,
which only a person typing can see.

Searching has the same shape. `search()` wraps, because Tk wraps: with no
`stopindex` a forward search runs off the end and round to the beginning.
Every property of that is testable and none of them answer the real question,
which is whether a person pressing Return repeatedly feels like they are
walking through the matches or like the search has lost its place.

And the geometry — `dlineinfo()` and `bbox()` — is the part that would
otherwise be taken on trust. The suite asserts they agree with
`_index_at_cell`, so a click and a bbox cannot drift apart. What it cannot
assert is that either of them agrees with **the cursor you can see**.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 38
```

From anywhere else: `python3 /path/to/TkCurses/uat 38`. The scenario exits on
**Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |
| Result | |

---

## Undo and redo

Type in the box. `Ctrl-Z` undoes, `Ctrl-Y` redoes.

- [ ] Type a whole word, then press `Ctrl-Z` **once** — the whole word goes,
      not the last letter
- [ ] Type a word, press `Ctrl-Y` — it comes back
- [ ] Type `one`, press Left or click elsewhere, type `two`, then `Ctrl-Z`
      once — only `two` goes. Moving the cursor ends a run
- [ ] Type a word, press Backspace a few times, then `Ctrl-Z` once — the
      deleting is undone and the typing is still there. Switching between
      typing and deleting ends a run too
- [ ] Press `Ctrl-R` to load the paragraph, then `Ctrl-Z` once — **the whole
      paragraph goes in one step**, not line by line
- [ ] Press `Ctrl-Z` with nothing left to undo — the line under the box says
      `nothing to undo`. It should say so rather than doing nothing silently,
      and rather than ending the scenario
- [ ] Undo something, then type a character, then press `Ctrl-Y` — it says
      `nothing to redo`. A new edit throws away what was undone, which is
      what Tk does
- [ ] `modified=` on the status line goes to 1 on the first edit and stays
      there

## Autoseparators

`Ctrl-T` turns `-autoseparators` off and on; the status line says which it is
and counts the undo groups, so the option can be watched rather than inferred.

- [ ] With `autosep=on`, type a word — `undo groups` goes to 1 and **stays at
      1** while you keep typing. A run of typing is one group
- [ ] Still on: move the cursor, type again — the count goes to 2. Changing
      what you are doing ends a run
- [ ] Still on: type, then press Backspace a few times — the count goes up
      again. Switching from typing to deleting ends a run too
- [ ] Press `Ctrl-T`. The line underneath says autoseparators is off and
      `autosep=OFF` appears on the status line
- [ ] With it off, type, move the cursor, type again — **the count stops
      rising**. Everything from here is one group
- [ ] With it off, press `Ctrl-Z` once — the lot goes back in one step. This
      is correct, and it is what the option exists to prevent
- [ ] Press `Ctrl-T` again and the counting resumes

## Search

`Ctrl-F` moves to the Find box. Type something and press `Return`.

**Not `Tab`.** Tab types a tab here, as it does in tkinter — see below.

- [ ] Press `Ctrl-R` first so there is something to find, then search for
      `dog` — the cursor moves to the match and the view scrolls to it if
      it was off screen
- [ ] The line underneath reports where it landed, how many characters
      matched, and how many matches there are altogether
- [ ] Press `Return` again — it goes to the **next** match, not back to the
      same one
- [ ] Keep pressing `Return` past the last match — **it wraps to the first**
      and the reported index goes back up the document. This is correct;
      Tk wraps
- [ ] Search for something that is not there — it says so, and the cursor
      does not move
- [ ] Search with the box empty — it says `nothing to find`

## Where the cursor is

The status line reports `insert`, the `bbox` cell, and the `dlineinfo` row,
all for the insert cursor, updated as it moves.

- [ ] Move the cursor with the arrow keys — **the reported cell is the cell
      the cursor is drawn in**. Count across and down from the top-left of
      the box if it is not obvious
- [ ] Put the cursor at the end of a long line that has wrapped — the
      reported row is the row on screen, not the logical line
- [ ] `dlineinfo`'s `width` is the length of that display row, not the width
      of the box
- [ ] Scroll down with `Ctrl-R` loaded until the cursor's line leaves the
      top of the view, then press Up until it comes back — nothing reports a
      nonsensical cell on the way
- [ ] Press End on a line long enough to run off the right-hand edge — the
      view scrolls sideways and the reported cell keeps up

## Afterwards

- [ ] Press `Tab` in the editor — **a tab goes into the text** and the focus
      stays put. `insert` on the status line advances by one
- [ ] Type some characters after that tab — **they appear immediately after
      the cursor**, not several columns to the right of it. The tab occupies
      one cell and the `bbox` cell on the status line is where the character
      really is
- [ ] **A tab does not indent to a tab stop yet.** It is drawn as a single
      space, so it looks like one. That is a stopgap, not the finished
      behaviour — tab stops are **TkCurses-wy7**, and until then the rule
      being kept is only that the display never disagrees with the widget's
      own arithmetic
- [ ] Escape leaves cleanly, terminal usable, no `reset` needed

---

## What has been found here

Two faults in the **scenario**, found on its first run by the person it was
written for, before any of the widget behaviour was in question:

- The status line was placed on the Entry's bottom border and painted it out.
  An Entry is three rows tall — border, text, border — and the layout had
  been written as though it were two.
- `-autoseparators` was set once and never exercised. The scenario claimed to
  be the acceptance for undo grouping while giving no way to see grouping
  happen or to compare it against the option being off. `Ctrl-T` and the
  group count are the fix.

Three more were caught *before* that, during implementation, by measuring
real tkinter rather than assuming:

- Three programmatic `insert()` calls with `-autoseparators true` are **one**
  undo group, not three. Separators come from the key bindings, not from the
  widget command, which is the opposite of what the option name suggests.
  (`Ctrl-R` loads its paragraph with one `insert()`, so it is one group
  however long the paragraph is — that is the same rule, seen from the
  checklist's side.)
- An empty search pattern returns the index it started at. It matches neither
  nothing nor everything.
- `<<Modified>>` fires on a **change of the flag**, not on every edit. It had
  been firing on every edit, so a handler that saved on it was saving far
  more often than tkinter would.

## Found by this checklist

The status was one line and ran to **98 of 100 columns** with the paragraph
loaded — and `undo groups` lost its number off the right edge, which is the
one figure the autoseparators section asks you to watch. At 80 columns, the
common terminal, far more went. Split across two lines, with a test at 80
columns because that is the width that actually hurt.


Running the Tab item above found a real bug, in every widget rather than just
this one. A raw tab reached curses, which expanded it to a tab stop, while
every column calculation in the library counted it as one character — so a
`Text` drew the character after a tab six columns right of where `bbox` said
it was, a `Label` lost whatever followed a tab, and an `Entry` pushed text
across its own box. Fixed in `_one_cell_each`; **TkCurses-zrm**.

## A divergence this scenario has to work around

TkCurses puts focus traversal on the `all` tag, so **Tab moves the focus out
of a `Text` by default**. tkinter does not: Tk binds `<Tab>` in a Text to
insert a tab and keep the focus, and puts traversal on `<Control-Tab>`.

The default is defensible — a terminal cannot reliably send Control-Tab, so a
keyboard-only user would be stuck in the first `Text` they reached — but it is
the wrong default for anything pretending to be an editor. The first version
of this scenario used `Tab` to reach the Find box and so quietly disagreed
with tkinter about what Tab does, which is exactly the sort of thing an
acceptance scenario should not be teaching.

The architecture already allows for it: traversal is on `all`, the last tag
consulted, so a widget that wants Tab binds it and returns `"break"`. This
scenario does that, and uses `Ctrl-F` for the Find box. **TkCurses-87e**
tracks whether the library default should change.
