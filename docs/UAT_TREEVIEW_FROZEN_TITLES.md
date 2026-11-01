# Acceptance: a Treeview's frozen rows and columns

Two questions, from `TkCurses-xe9.6`: **does a Treeview scroll sideways now**,
and **do `-titlecolumns` and `-titleitems` keep their rows and columns in place
while the rest scroll, as Tk 9.0's do?**

Until this cycle a tree never scrolled sideways. Its columns were clipped at
the right-hand edge, and nothing could reach them.

```bash
cd /path/to/TkCurses
python3 -m uat 47
```

**The readout** shows the two counts, both views as fractions, and the cell
last clicked. **c** and **i** freeze one more column or row, **C** and **I**
one fewer. **<** and **>** scroll sideways a page at a time, as well as the
bottom scrollbar. **Escape** quits.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-11-01 |
| Result | **Accepted.** Run by the author: "this appears to function as expected". Terminal and size not recorded. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. What was driven mechanically, and so is on the record, is the
scenario 47 tests in `tests/test_uat_scenarios_tty.py`.

**Still open:** the comparison with Tk at the end of this checklist, which asks
what Tk draws where the frozen part meets the scrolling part. No answer was
recorded, so this library's choice to draw nothing there is unconfirmed.

## Sideways

With nothing frozen (`titlecolumns=0 titleitems=0`):

- [ ] The tree is wider than the window: **Outer**, the last column, cannot be
      seen, and the bottom scrollbar's thumb is shorter than its trough
- [ ] **>**, or drag the bottom thumb right: the headings and the rows move
      **together**, and Outer comes into view. *It was clipped and unreachable
      before*
- [ ] The tree column, **Region**, scrolls away like any other
- [ ] Scrolled sideways, **click a Group's ▸ or ▾** where it is now drawn: the
      branch opens or closes. Click where it was before scrolling: nothing
      opens
- [ ] The readout's `xview` follows the thumb, and reaches `1.00`

## Frozen columns

- [ ] **c**: `titlecolumns=1`. Scroll sideways: **Region stays**, and the
      other columns pass **under** it from the right
- [ ] The bottom thumb is now **shorter**: it measures only the columns that
      scroll. *Tk's fractions leave the frozen ones out, measured*
- [ ] **c** again: Region and North both stay
- [ ] Click a cell in a frozen column, then one beside it in the scrolling
      part: the readout names the column under the pointer each time, `#0`,
      `#1` and so on, by what is **drawn** there
- [ ] Press **c** until every column is frozen: nothing scrolls, and the
      thumb fills its trough

## Frozen rows

- [ ] **i**, **i**: `titleitems=2`. **Group 0** and **Item 0.0** stay at the
      top
- [ ] Scroll down with the right-hand scrollbar, or Down through the rows:
      the rest pass under those two
- [ ] The right-hand thumb measures only the rows that scroll
- [ ] Close Group 0 (click its ▾): the frozen rows are now **Group 0 and
      Group 1**. *The count is of rows as displayed, not of items*
- [ ] Press **i** until the titles fill the tree: they stop at its bottom
      border, and nothing scrolls

## Both together

- [ ] Freeze two columns and two rows and scroll both ways: the top-left
      block never moves, the frozen rows scroll sideways with the columns, and
      the frozen columns scroll up and down with the rows

## Compare with Tk: the edge between frozen and scrolling

Tk's documentation does not say whether it draws anything where the frozen
part meets the scrolling part, and the API cannot tell. This library draws
nothing there. **Run this beside the scenario**, under a desktop, and say
what Tk shows at that edge: a line, a shade, or nothing.

```python
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
tree = ttk.Treeview(root, columns=tuple("abcdefgh"), titlecolumns=2, titleitems=2)
for c in ("#0",) + tuple("abcdefgh"):
    tree.column(c, width=90, stretch=False)
    tree.heading(c, text=c)
for n in range(40):
    tree.insert("", "end", text=f"row {n}", values=[f"{c}{n}" for c in "abcdefgh"])
across = ttk.Scrollbar(root, orient="horizontal", command=tree.xview)
tree.configure(xscrollcommand=across.set)
tree.pack(fill="both", expand=True)
across.pack(fill="x")
root.geometry("500x300")
root.mainloop()
```

- [ ] Tk draws at the column edge: ______
- [ ] Tk draws at the row edge: ______

## Faults found by running it

None yet.
