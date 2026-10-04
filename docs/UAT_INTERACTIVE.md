# Acceptance: interactive widgets

The geometry checklists ask whether things are in the right place. These ask
whether they *answer* — whether focus is visible, whether the keyboard reaches
what you think it reaches, and whether a modal dialog really is modal.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 15          # and 16 to 19
```

From anywhere else: `python3 /path/to/TkCurses/uat 15`. Every scenario exits
on **Escape**.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## The one that matters most

**You must be able to tell, at every moment, which widget will answer the next
key.** A terminal has no pointer to follow and no shadow under a focused
control; if the focus is invisible the application cannot be used without a
mouse, and a mouse is the thing a terminal user most often does not have.

## 15. Focus and traversal

`python3 -m uat 15` · `Tab`, `Shift-Tab`, `d` destroys the focused widget

- [ ] Tab moves the focus forwards through the buttons and entries
- [ ] Shift-Tab moves it backwards
- [ ] Tab wraps round at the end rather than stopping
- [ ] The focused widget is always visibly marked — a button by its arrows,
      an entry by its cursor
- [ ] The line at the top names the widget you believe has the focus
- [ ] `d` destroys the focused widget and Tab still works afterwards — the
      focus must not be left pointing at something that no longer exists

## 16. Buttons

`python3 -m uat 16` · click, `Return`, `Space`, `f` flashes

- [ ] Clicking invokes the button and the count rises by exactly **one**
- [ ] Return invokes it once
- [ ] Space invokes it once
- [ ] The button shows itself held down while the mouse button is down
- [ ] The disabled button does nothing for all three gestures
- [ ] Tab skips the disabled button entirely
- [ ] `f` flashes the button and it returns to normal by itself

## 17. Entries

`python3 -m uat 17` · type, edit, `Tab` between fields

- [ ] Typing appears at the cursor
- [ ] Left, Right, Home and End move the cursor
- [ ] Left at the very start of a field leaves the cursor there. It used to
      jump to near the end of the text (`TkCurses-11m`)
- [ ] Backspace and Delete remove the right character
- [ ] Shift with the arrows selects, and typing replaces the selection
- [ ] The cursor is visible in the focused field and **only** in that one
- [ ] Text longer than the narrow field scrolls within it and never spills
      over the border
- [ ] The password field shows stars; the field below it shares the same
      variable and shows what you really typed
- [ ] The read-only field refuses every edit but still lets you move about
      and select in it

## 18. Listboxes

`python3 -m uat 18` · arrows, `Home`/`End`, `PageUp`/`PageDown`, `m` cycles mode

- [ ] The selected rows are marked at both ends
- [ ] **The box is closed on every row.** The right-hand border lines up with
      the corners above and below it, and nothing in the list runs past it.
      This is the check that was missing. The row's end marker used to be
      written with an insert, which shifted each row one cell along and ate
      the listbox's own border — look for **two** upright bars between the
      text and the scrollbar's arrow, not one:

      ```
      wrong:  │ row 00                  │▲│
      right:  │ row 00                 ││▲│
      ```
- [ ] In `browse` the selection follows the arrows
- [ ] In `single` the arrows move an underlined **active** row while the
      selection stays where it was — these are different things
- [ ] In `multiple`, Space toggles rows independently
- [ ] In `extended`, Shift-clicking selects a range
- [ ] Clicking a row selects it; clicking below the last row does nothing
- [ ] The list scrolls when the active row reaches the edge
- [ ] The scrollbar's thumb tracks the view, and clicking its arrows scrolls
- [ ] The thumb can be **picked up and dragged**, not only clicked, and the
      view follows the pointer — wherever within the thumb you grabbed it
      stays under your finger rather than the thumb jumping to meet you
- [ ] Pressing the thumb and letting go without moving scrolls **nothing**
- [ ] Clicking the trough still pages
- [ ] The count on the second line always matches what is marked

## 19. A modal dialog

`python3 -m uat 19` · `F2` opens it, `y`/`n` answer, `Escape` closes it

- [ ] While the dialog is up, **nothing you type reaches the field behind it**
- [ ] The count of what that field holds does not move while the dialog is up
- [ ] After the dialog closes, the field answers the keyboard again
- [ ] Escape closes the dialog through its `WM_DELETE_WINDOW` handler and the
      answer shows as `closed`
- [ ] Escape responds immediately — not after a noticeable pause

> **F2 rather than a letter**, because a focused entry consumes every
> printable key and stops it reaching an application-wide binding. That is
> correct, and it is the same rule the grab applies on a larger scale.

---

## What this found

- **Nothing bound Tab to focus traversal.** `tk_focusNext` had existed since
  the base widget system and no key was ever wired to it, so Tab did nothing
  at all in a running application. It is an `all` binding now, installed by
  `Tk`, so a widget that wants Tab for itself can still take it.
- **A lone Escape took a full second to arrive.** ncurses cannot tell it from
  the start of an escape sequence until ESCDELAY expires, and its default is
  1000ms — which makes the key that cancels things feel broken. Shortened to
  25ms at startup; making it configurable is **TkCurses-dn5**.
- **Tab stopped on frames and labels.** `takefocus` defaulted to true on
  every widget, so the focus landed on things that mark it in no way and
  appeared to vanish every second or third press. It defaults to false now,
  and the widgets that answer the keyboard turn it on for themselves - which
  is how tkinter's decide-by-class default behaves in practice.
- **The test harness sent the wrong bytes for function keys.** It used the
  linux encoding (`CSI 10+n ~`) while telling the child it was an xterm, so
  F1 arrived as `Escape [ 1 1 ~` and only F5 was right by coincidence. Any
  future test of an F-key binding would have quietly exercised nothing.
