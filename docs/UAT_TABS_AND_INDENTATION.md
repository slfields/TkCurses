# Acceptance: tab stops and indentation

Tab stops are a claim about **columns**, and indents are a claim about **where
text wraps**. The suite can check both against numbers; it cannot check that
they look right, and one of them is invisible in any single row.

That one is the narrowing. The difference between indenting text and merely
shifting it is that an indent makes the rows it indents **narrower**, so the
paragraph breaks sooner. No single row shows that — you have to see the
paragraph change shape. An implementation that moved the text without
narrowing it would pass every automated test written against one row.

The case to start from is the ordinary one: **the indent at the start of a
paragraph**, first line in, the rest flush left. That is `Ctrl-P` here, and it
is what most people mean by indentation. Its mirror image, the hanging indent,
is the same two options with their values swapped — so checking the pair
together is what catches them being confused.

The ruler along the top of this scenario is what makes the rest checkable by
eye. It is drawn in the editor's own coordinates, so a stop at column 10 puts
text under the `1` of `10`.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 39
```

From anywhere else: `python3 /path/to/TkCurses/uat 39`. The scenario exits on
**Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |
| Result | |

---

## Tab stops against the ruler

Press `Ctrl-R` for the sample. `Ctrl-T` cycles the settings; the line under the
box says which one is active.

- [ ] **Default** — the table's three columns start at 0, 8 and 16. Read them
      off the ruler, not by counting spaces
- [ ] The columns are straight down the four rows of the table
- [ ] **`4` + wordprocessor** — columns every four: 0, 8, 12
- [ ] **`4` + tabular**, the next setting, is **different** — `Qty` sits one
      space after `Widget` instead of on a column. This is correct: the first
      tab is assigned to stop 4, the text has already passed it, and Tk's
      documented fallback is a single space. Uniform spacing needs the style
      as well as the stop, which is what the previous setting shows
- [ ] **`10 right`** — the first column's text **ends** at 10 rather than
      starting there
- [ ] **`12 center`** — the text straddles 12, with roughly as much to the
      left as the right
- [ ] **`8 left 16 right 26 center`** — three stops, three different
      behaviours on one line
- [ ] Press `Tab` inside the table — a tab goes in and the text after it jumps
      to the next stop, rather than moving one column

## Indentation

`Ctrl-P` first-line, `Ctrl-G` hanging, `Ctrl-B` block, `Ctrl-E` right margin,
`Ctrl-N` none. All of them apply to the paragraph only.

`Ctrl-P` is the one to start with: it is what "indentation" means to most
people — the indent at the **start of a paragraph**, with the rest of it flush
left, the way a paragraph is set in a book. It and the hanging indent are the
same two options with their values swapped, which is why they sit next to each
other: an implementation that confused `lmargin1` with `lmargin2` would look
plausible under either key alone and be wrong under one of them.

- [ ] `Ctrl-P` — **the first line moves in and the rest stay flush left**
- [ ] `Ctrl-P`: the paragraph **re-breaks**. The first row is narrower now, so
      it ends sooner and the words shuffle down. That is the indent doing its
      job rather than just sitting there
- [ ] `Ctrl-G` — the exact opposite: the **first row stays** at the left and
      the rest move in
- [ ] Alternate `Ctrl-P` and `Ctrl-G` — they must not look the same, and
      neither should look like `Ctrl-B`
- [ ] `Ctrl-B` — **every** row of the paragraph moves in, including the first
- [ ] `Ctrl-G`: the indented rows also **end sooner** than the first one.
      This is the point of the whole cycle — an indent narrows, it does not
      just shift
- [ ] Press `Ctrl-N` then `Ctrl-G` again and watch the paragraph **re-break**.
      The number of rows it needs can change, because the rows got narrower
- [ ] `Ctrl-E` — rows end sooner and **none of them move**. A right margin
      narrows from the other side
- [ ] `Ctrl-N` — everything goes back
- [ ] **Blank lines inside the indented block are indented too.** This looks
      wrong and is right: Tk does the same, measured — an empty line reports
      the full margin from both `bbox` and `dlineinfo`. The margin applies
      where the *tag* applies, and a blank line inside the tag is inside it. A
      line at the left edge means the tag does not cover it, not that it is
      blank
- [ ] Through all of it, **the table above keeps its columns exactly where
      they were**. Indenting the paragraph must not move the table, because
      tab stops are measured from the widget and not from where a line starts

## Where the cursor is

The bottom line reports `insert`, the `bbox` cell and the `dlineinfo` row.

- [ ] Move the cursor through a tab with the arrow keys — the reported cell is
      the cell the cursor is drawn in, including inside the gap a tab spans
- [ ] Click in the middle of a tab's gap — the cursor lands at one end of it
      rather than somewhere unrelated, and the report agrees
- [ ] Put the cursor on an indented row — the reported cell accounts for the
      indent
- [ ] `dlineinfo`'s `x` is the indent and its `width` is the **text**, not the
      text plus the indent

## Afterwards

- [ ] Escape leaves cleanly, terminal usable, no `reset` needed
- [ ] Resize the terminal — the ruler still lines up with the text under it

---

## What has been found here

Two faults in the **scenario**, both caught by driving it before handing it
over:

- The indent keys raised `TypeError` — `tag_configure(..., lmargin1=0,
  **options)` is a duplicate keyword the moment `options` names `lmargin1`,
  which is exactly what the block-indent key does. The screen went blank. The
  traceback was readable and the terminal came back intact, which is the
  earlier work on leaving cleanly doing its job.
- A setting labelled "every 4 columns" did not give a column every four,
  because the default `tabular` style assigns the first tab to stop 4 and the
  text had already passed it. The label was wrong rather than the code. It is
  now two adjacent settings that differ only in style, so the difference is
  the thing being shown rather than a surprise.

Reported and checked, and **not** a fault: blank lines inside an indented
block are indented. That looks wrong, and Tk does exactly the same — measured
side by side, 5/5, empty line and whitespace-only line included. The account
that says Tk collapses a blank line to `x = 0` is incorrect, and so is the
"visual pop" it predicts: a line at the left edge is a line the tag does not
cover, and typing into it does not move it, because the tag still does not
cover it.

Faults found during implementation, all by measuring real tkinter first
rather than assuming:

- **Tab stops are absolute from the widget's left edge**, not from where a
  line's text starts. Measuring from the text start is the natural
  implementation and would have destroyed the one thing tab stops are for.
- **Centre alignment rounds up**: a run of three against a stop at 10 starts
  at 8, not 9.
- **Extrapolation repeats the last interval**, and a lone stop is its own
  interval.
- Resolving margins per row cost a Text repaint 31.6ms against a 25ms budget.
  The common case — no tag sets a margin — is now free.
