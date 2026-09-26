# Acceptance: input and what the screen looks like afterwards

The other checklists ask what a widget does. This one asks what the *keyboard*
does, and what is left on screen when something goes wrong — the two areas
where every fault so far has been found by a person at a real terminal rather
than by a test.

That is not an accident. A test harness can only check what the library does
with the bytes a terminal sends it; it cannot check what the library asks the
terminal for, which desktop shortcuts the terminal swallows first, or what a
keyboard layout puts where. Three of the four bugs in this round were reported
by someone running a scenario and noticing.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 27
```

From anywhere else: `python3 /path/to/TkCurses/uat 27`. The scenario exits on
**Escape**.

| | |
|---|---|
| Terminal | |
| Desktop / window manager | |
| Keyboard layout | |
| Size | |
| Date | |

The terminal and the desktop matter more here than anywhere else, so please
fill them in. A key that never arrives is usually the desktop taking it, and
knowing which desktop is most of the answer.

---

## The one that matters most

**One press fires exactly one binding, and it is the most specific one.** Tk
runs at most one script per binding tag: the pattern with a detail beats one
without, and more modifiers beat fewer. If a press with Shift held reaches
`<Key>` while `<Shift-Key>` is bound, or a plain `a` reaches `<Shift-Key>`,
the rule is broken and every application built on it will misbehave in ways
that look random.

---

## 27. Bindings, key names, and repair after a crash

`python3 -m uat 27` · type across the whole keyboard · `Shift` and `Control`
with the arrows · click the button · resize the terminal hard

Each line of history names the binding that fired, the key's name, its
character and the modifiers the terminal reported.

### Which binding wins

- [ ] A plain letter fires `<Key>`
- [ ] `Control` with a letter fires `<Control-Key>`, and the key is named as
      the plain letter — `Control-a` is `a` with Control, not something else
- [ ] `Shift` with an arrow fires `<Shift-Key>`
- [ ] `Control` with an arrow fires `<Control-Key>`
- [ ] `Control` and `Shift` together with an arrow fire
      `<Control-Shift-Key>` — the most specific of the four
- [ ] `Tab`, `Return` and `F1` fire their own bindings rather than `<Key>`,
      because a detail beats a bare pattern
- [ ] **`Escape` still quits**, although `<Key>` is bound across the whole
      keyboard: `<Key-Escape>` is the more specific match

> **Shift over a printable key cannot be seen**, and that is the terminal, not
> the library. A terminal sends `A` for Shift-a and says nothing about Shift,
> so `<Shift-Key>` is reachable only through keys with a shifted code of their
> own — the arrows, `Home`, `End`, `Page Up`, `Page Down`, `Delete`, `Insert`.

### What the key is called

- [ ] Every letter and digit names itself
- [ ] `!`, `@`, `#` and the rest of the shifted number row name themselves
- [ ] Punctuation names itself: `;` reports `;`, not `semicolon` — which is
      what Tk 9.0.2 does, checked against it
- [ ] Pressing `;` fires `<Key-semicolon>`, bound by its **X11 name**, and
      pressing `,` fires `<Key-,>`, bound by the **character** — Tk takes
      either spelling for the same key
- [ ] `Tab`, `Return`, `BackSpace`, `Delete`, `Insert`, `Home`, `End`,
      `Prior`, `Next` and the arrows report their Tk names
- [ ] Every function key your terminal sends reports `F1` … `F12`
- [ ] Nothing reports `keycode-NNN` — that name means the library did not
      recognise the key at all, and is worth reporting with the terminal you
      saw it on

### The keys the terminal would keep for itself

A tty turns `Ctrl-C`, `Ctrl-\` and `Ctrl-Z` into signals — interrupt, quit and
suspend — before any byte reaches the application. Binding one takes it back,
one control character at a time. This scenario binds `Ctrl-C` and `Ctrl-Z` and
deliberately leaves `Ctrl-\` alone, which is the thing to check: an application
gets the key it asked for, and **you keep a way of stopping it**.

- [ ] `Ctrl-C` appears in the history as `<Control-c>` and does **not** end the
      scenario
- [ ] `Ctrl-Z` appears as `<Control-z>` and does **not** suspend it
- [ ] `Ctrl-\` still **quits** — nobody bound it, so the terminal still has it
- [ ] After the scenario exits, the terminal has its interrupt back: run
      anything slow and check `Ctrl-C` stops it
- [ ] `Ctrl-S` and `Ctrl-Q` appear too. They would have been swallowed as flow
      control rather than as signals; the library takes those two back for
      every application, and a terminal where they go missing is worth
      reporting
- [ ] Every other `Ctrl` combination your terminal sends appears, named as the
      plain letter with `Control` held

> **A program that binds none of them keeps all three signals**, which is
> nearly every program — scenario 09 checks that `Ctrl-C` still ends an
> application that has not asked for it. It ends it *cleanly*: the loop
> turns the interrupt into `WM_DELETE_WINDOW`, so the application can save
> or ask first, and gets a quiet exit rather than a traceback if it does
> neither.

### After something goes wrong

- [ ] Clicking the button raises, and the application keeps running
- [ ] **Space and Return still work afterwards**, and reach the log rather
      than pressing the button again — a click must not move the keyboard to
      the button, which would swallow both
- [ ] **The display is untouched** — no traceback on the screen, nothing
      scrolled, the history exactly where it was
- [ ] Pressing keys afterwards still works
- [ ] After **Escape**, every traceback appears at once, one per press, each
      line starting at the left edge
- [ ] The terminal is usable afterwards: prompt back, cursor visible, typing
      echoed

### After a hostile resize

- [ ] Shrink the terminal to a few columns and rows: it neither crashes nor
      draws nonsense
- [ ] Grow it back: the layout is exactly as it was, with **no fragment** of
      any intermediate size left anywhere on screen
- [ ] The instruction lines are full length again, not the clipped versions
      the small terminal held
- [ ] The button is whole, and still raises when clicked

---

## What this found

- **`<Control-c>` could not be bound at all**, though tkinter binds it like
  any other key and it is the standard Copy accelerator. The tty had it as
  SIGINT, and binding it succeeded silently and then never fired — the worst
  shape a failure can take. A binding is now the request: the key is taken
  back from the terminal for as long as something wants it, and given back
  when the binding goes. One control character at a time, so an application
  that wants `Ctrl-C` still answers `Ctrl-\`. **TkCurses-53u**.

- **Clicking a button stole Space and Return.** `_button_press` took the
  focus, and a button binds both keys to invoke itself — so after clicking
  the button that raises, every later Space raised the exception again and
  nothing else saw the key. Checked against Tk 9.0.2: a click gives the focus
  to an entry, spinbox, text or listbox, and never to a button, checkbutton,
  radiobutton, scale or menubutton. **TkCurses-gyo.5**.

- **Control and Alt with an arrow could not be bound at all.** They arrived as
  `keycode-534` and `keycode-535` with no modifiers, so `<Control-Down>` and
  `<Control-Shift-Key>` never fired. ncurses allocates a key code per
  combination at run time from the terminal's extended capabilities and puts
  the modifier in the code's *name* — `kDN5` is Down with Control, `kDN6` with
  Control and Shift — so the name is the only place it survives, and the name
  is now read back. **TkCurses-gyo.3**.
