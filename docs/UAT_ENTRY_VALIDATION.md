# Acceptance: Entry validation

Five entries, and one question: **can you tell what happened?**

Validation's whole job is to refuse things. Whether it refuses the right things
is settled by tests — 4,694 of them, agreeing with real Tcl/Tk 9.0.2 scenario
for scenario across all three of Tk's validation conditions. What a test cannot
show is whether a person watching the screen can tell a refusal from a bug, or
notice when validation has **switched itself off**.

That last one is not hypothetical, and it is not a defect here. Tk disables
validation outright in three circumstances, and leaves it disabled:

- a validator that raises
- a validator that edits the entry it is being asked about
- a `textvariable` written with a value the validator refuses

The first two are Tk's recursion guard — a validator calling `insert` on its own
entry would call itself forever — and the third is Tk admitting it cannot refuse
what the variable already holds. In a GUI there is at least a widget to inspect.
In a terminal there is nothing: the entry simply stops refusing things, and every
later keystroke is accepted. **The mode column under the title is
the only thing that says so**, which is why most of this checklist is about
reading it.

Validation had no acceptance coverage at all before this. Across forty scenarios
and fourteen checklists, the word "valid" did not appear once. `TkCurses-wkd`.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 41
```

The scenario exits on **Escape**, and `Ctrl-R` puts every entry back — needed,
because most of what it demonstrates is one-way.

It wants a terminal **at least 20 rows** tall: one row of title, three of
readout, fifteen of entries and one of footer.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-02 |
| Result | **Accepted.** Run by the author; terminal and size not recorded. Two faults were found between the first run and the acceptance — they are listed at the end. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole — "I think uat 41 works as expected, now" — rather than item by item, and
ticking them individually would claim a record that was not taken. This matches
how `UAT_TTK_CORE_WIDGETS.md` records its own.

## The edit condition

- [ ] **digits only** — click into it and type `x`. Nothing appears in the
      field, and `last:` reads `REFUSED 'x'`
- [ ] Type `7`. It appears
- [ ] Press **insert 'x'**. This edits the entry from code rather than from the
      keyboard, and it must be refused the same way — the field still reads `7`.
      *This is the one nobody could watch before: `insert()` did not validate at
      all, so a program could put text into a validated entry that its own
      validator would have rejected (`TkCurses-tvj`)*
- [ ] Press **insert '7'**. The field reads `77`

## The state gate

- [ ] **readonly** — press **insert '9'**. Nothing happens. `-state` gates the
      widget commands too, which is Tk's documented contract, and this library
      used to let the insert through
- [ ] Try typing into it directly. Nothing
- [ ] Click into it, or reach it with `Tab`. **Its border brightens**: a locked
      field still shows that it has the keyboard. There is deliberately no
      insertion cursor — Tk's manual says readonly draws none "even if the input
      focus is in the widget" — so the border is the whole signal
- [ ] Move the focus away again. The border dims, and only the newly focused
      field is bright

## The focus condition

- [ ] **focusout** — click into it and type letters. They are accepted. *The
      focus modes do not gate edits; only `key` and `all` do*
- [ ] Now leave the field, with `Tab`, `F6`, or by clicking elsewhere.
      `last:` reads `REFUSED` …
- [ ] **… and the letters are still there.** A focus validator is advisory —
      there is no proposed value to reject, only the value already in the field.
      **If the text were reverted, that would be the bug**
- [ ] The mode column still reads `onfocus=focusout`. A clean refusal does not
      switch validation off

## Validation switching itself off

This is the section to leave the scenario remembering.

- [ ] Read the mode column. Every entry shows the mode it was built with
- [ ] **validator raises** — click into it and type anything. The validator
      fails
- [ ] The mode column now reads **`broken=NONE!`**. That entry will accept
      anything from here on
- [ ] Type several more characters into it. They are all accepted, and nothing
      else on screen has changed. *That is the hazard: an application whose
      validation has quietly stopped looks exactly like one whose validation is
      passing*
- [ ] Press **set variable** on the **forced (variable)** entry. The value
      `xyz` lands **even though the validator refuses it** — a forced validation
      cannot say no — and the mode column reads `forced=NONE!`
- [ ] Note that no complaint was printed for that one. Measured on real Tk: a
      forced refusal runs no `invalidcommand`. Unlike every other refusal here,
      it is silent by design

## Housekeeping

- [ ] Press `Ctrl-R`. Every mode goes back to what it started as and every field
      empties
- [ ] Resize the terminal, smaller and then larger — nothing overlaps or loses
      a border, the mode readout stays under the title, and there is exactly one
      copy of it
- [ ] `Escape` exits cleanly, with no traceback

## Faults found while building this

Both were found by driving the scenario in a pty, and both were invisible to its
smoke test, which checks that the title appears.

**The five entries were placed two rows apart.** A bordered widget is three rows
tall, so every entry's bottom border was painted over by the next one's top.
This is already written down as a finding from UAT 40 — see
`UAT_TTK_CORE_WIDGETS.md` — and it happened again anyway in a brand-new
scenario, which says something about how much good a finding does when it is
recorded in prose and not in a test.

**The mode readout lagged by one event.** It was drawn from inside the
validation callback, and the mode this scenario exists to display is changed by
the machinery *after* that callback returns — a validator that raises is still
looking at `validate="key"` at the moment it raises. So the column showed
`broken=key` forever: the one failure worth seeing, made invisible by the very
thing built to show it. Now deferred to an idle callback.

**The readout did not survive a resize.** It was written at `screen.height - 4`,
and the support screen replays each line at the row it was written at — so after
a shrink those rows no longer existed and the column disappeared for good. This
checklist claimed it followed the bottom of the screen before anyone had tried
it; resizing a pty from 28 rows to 24 showed otherwise. It now sits at fixed
rows under the title, where a resize cannot strand it.

All three are pinned by tty tests in `tests/test_uat_scenarios_tty.py`, so the
hand-driving that found them does not have to be repeated to keep them fixed —
which is the whole difference between a finding and a fix. The two-rows-apart
fault was *already* written down from UAT 40 and recurred anyway.

## Found by running it

Two more, reported from the first real run of this scenario.

**`insert '9'` overlapped the bottom of `insert 'x'`.** The two-rows-apart fault
for the third time, now in a single button: a multi-edit aborted on its last
assertion, the repair was applied to the other half only, and nothing re-checked
the first. It is no longer pinned by coordinates — a test now counts box corners
per column and fails when one opens without closing, which catches the whole
class rather than this instance.

**A focused readonly entry looked exactly like an unfocused one.** This was the
library, not the scenario. Tk signals focus on an entry twice over: the insertion
cursor, which readonly suppresses by documented design, and the
`-highlightthickness` ring, which does not care about the state. TkCurses drops
the ring as an X11 option with no cell equivalent and had put nothing in its
place, so copying Tk's cursor rule faithfully removed the only remaining signal.
A focused entry now draws its border bold, in every state. Pinned for `normal`,
`readonly` and `disabled`, together with a test that a locked entry still shows
no cursor — so the fix cannot later be "improved" into breaking the other half.
