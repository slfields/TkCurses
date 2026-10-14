# Acceptance: menu columns and shortcuts

Two questions, from `TkCurses-aj1.13.1`: **does a menu laid out in columns
behave like Tk's**, and **does one call turn a menu's shortcut text into
working shortcuts?**

The second is not tkinter: Tk draws an accelerator and binds nothing, so
every program binds each key itself and the two can drift apart.
`bind_accelerators()` is a TkCurses addition that binds them from the text.

```bash
cd /path/to/TkCurses
python3 -m uat 46
```

**The readout** says what was chosen last. **F2** opens File, **F3** opens
Colours; **Escape** closes a menu, and quits when none is open.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-10-14 |
| Result | **Accepted.** Run by the author: "It works as you stated", after the three faults below were fixed. Terminal and size not recorded. |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. What was driven mechanically, and so is on the record, is the
scenario 46 tests in `tests/test_uat_scenarios_tty.py`.

## Columns

- [ ] **F3**, or click Colours. Fifteen colours in **three columns** of five,
      Black, Purple and Lime at the top of each
- [ ] Each column is only as wide as its own names need
- [ ] **Click** Teal, in the middle column. The readout says `colour Teal`
- [ ] Open it again and press **Down** six times from the top: past Navy, at
      the foot of the first column, it goes to **Purple**, at the top of the
      next. *Tk's own arrows go by entry, not by column*
- [ ] **Up** from Black wraps to Aqua, the last entry
- [ ] **F3**, then **Escape**: the menu closes and **nothing on the bar is
      left highlighted**. *As in Tk. Colours stayed highlighted, as though the
      arrows would walk the bar, on this checklist's first run*
- [ ] Left and Right do not move between columns: they move along the bar.
      **Left** from Colours opens File in its place. *It closed the menu
      instead, until writing this checklist found it*

## Shortcuts, from the text

With every menu **closed**:

- [ ] **Ctrl+O** — the readout says `Open`
- [ ] **Ctrl+X** then **Ctrl+S** — `Save`. *A two-key shortcut, from the
      text "Ctrl+X Ctrl+S"*
- [ ] **Ctrl+P** — nothing. Print is disabled, and its shortcut with it
- [ ] **F5** and **F6** — `Last file` and `One before`, from the Recent
      submenu
- [ ] Open File and check the shortcuts shown there are the ones that worked
- [ ] With **Colours open**, press **F5**: nothing happens, and the menu stays
      as it was. *An open menu keeps every key, as Tk's does. F5 chose "Last
      file" behind the open menu, and the readout was written over its top
      border, on this checklist's first run*
- [ ] **Ctrl+Q** quits

## Faults found by running it

1. **Left in a dropdown of the menubar closed it**, instead of opening the
   menu to its left. Found writing this checklist.
2. **F5 fired behind an open menu**, and the readout wrote over the menu's
   border. An open menu now keeps every key, as Tk's does; the readout's
   drawing over menus is a limit of the UAT helper, now noted there.
3. **Escape left the bar highlighted**, as though the arrows would walk it.
   It now clears, as Tk's does - the author's choice over keeping it.
