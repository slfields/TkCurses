# Acceptance: dialogs

Dialogs are the part of a toolkit a person meets first and judges fastest,
and almost none of what matters about them can be read out of a value. Does
the thing on top have the keyboard? Does Escape do what Escape does
everywhere? Is the box where you can read it? Is the screen underneath the
way you left it? A test can check a return value; only a person can check
that a dialog feels like a dialog.

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat 29          # and 30
```

From anywhere else: `python3 /path/to/TkCurses/uat 29`. Both exit on
**Escape** — when no dialog is up. Scenario 30 browses from whatever
directory you started it in, so start it somewhere with a real tree in it.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | |

---

## The one that matters most

**A dialog must give the keyboard back.** Everything else on this page is a
detail beside it: a modal window that holds the focus after it closes leaves
the application looking wedged with nothing visibly wrong, and a person's
only recourse is to kill it. Every dialog here, closed every way it can be
closed, has to leave the thing underneath working.

---

## 29. Dialogs — what each one answers with

`python3 -m uat 29` · `1`–`8` the message boxes · `s` `i` `f` the prompts ·
`n` a dialog opened from inside another

The top line reports what the call returned **and its Python type**, which is
the thing worth watching: the eight message box functions deliberately do not
agree on one. Three give a string, four a boolean, one a boolean *or* None.

### The answers

- [ ] `1`, `2`, `3` — info, warning and error — each return the *string*
      `'ok'`, not `True`. The type in brackets says `str`
- [ ] `4` askquestion returns `'yes'` or `'no'`, again a string
- [ ] `5`, `6`, `7` return `True` or `False`, and the type says `bool`
- [ ] `8` askyesnocancel returns `True`, `False` **or** `None` — three
      answers, which is why it cannot be a plain boolean
- [ ] Every answer matches the button actually pressed

### Escape, and what a dismissal means

Dismissing a message box is **not** the same as pressing nothing. Each kind
names the answer a dismissal stands for, which is Tk's rule, so a caller
always gets one of that kind's own answers.

- [ ] Escape on `5` askyesno gives `False` — its dismissal is "no"
- [ ] Escape on `8` askyesnocancel gives `None` — its dismissal is "cancel"
- [ ] Escape on `1` showinfo still gives `'ok'` — an ok box has nothing else
      to say
- [ ] Escape on any prompt (`s`, `i`, `f`) gives `None`, which is **not** the
      empty string: somebody who cancelled and somebody who typed nothing
      meant different things

### Prompts, and a value that will not do

- [ ] `s` returns exactly the text typed
- [ ] `i` returns a number, and the type says `int` — not the text of one
- [ ] `f` returns a `float`
- [ ] `i` with letters in it says **"Not an integer"** and the prompt **stays
      up**. Nothing is returned; the top line does not change
- [ ] `i` with `0` says the minimum is 1; with `99` says the maximum is 10
- [ ] Dismiss the warning, correct the value, and it is accepted — the whole
      point of staying up

### Everything else

- [ ] Every dialog is **centred**, and sized to what it holds rather than to
      some default
- [ ] Return presses the default button, which is the one that looks selected
- [ ] Tab walks the buttons, and Return then presses whichever is selected
- [ ] The background text behind the dialog comes back **exactly** as it was
      — no gaps, no leftovers, no shifted rows
- [ ] While a dialog is up, the keys behind it do nothing: press `1` while a
      box is open and no second box appears
- [ ] `n` opens a message box and then, if you answer yes, a prompt *from
      inside it* — which is what a save-before-quit is. Both close cleanly
      and the second one had the keyboard while it was up
- [ ] **After every one of these, the application still answers.** Press
      another key and something happens

---

## 30. Choosers — files, directories and colours

`python3 -m uat 30` · `o` `s` `d` the file dialogs · `l` `w` the older ones ·
`c` the colour chooser

Start this somewhere with a real tree. A file browser checked against three
files in a temporary folder has not been checked.

### The listing

- [ ] Directories on the left, files on the right, the pattern above and the
      chosen path below
- [ ] The listing matches what is really in the directory
- [ ] `..` is **always** the first entry, even in a directory whose name you
      could not type
- [ ] Clicking a file puts its full path in the box at the bottom
- [ ] Clicking a directory and pressing **Filter** moves into it
- [ ] `..` and Filter get you back out, and all the way to `/`
- [ ] A pattern like `*.py` hides files — and **never** hides directories,
      which are how you get anywhere
- [ ] Typing a directory that does not exist and pressing Filter changes
      nothing rather than emptying the lists

### What each one insists on

- [ ] `o` askopenfilename returns the path picked, and `''` — not None — when
      cancelled
- [ ] `l` LoadFileDialog **refuses** a name that is not there: type nonsense,
      press OK, and nothing happens
- [ ] `w` SaveFileDialog asks **"Overwrite existing file?"** for a name that
      exists, and answering Cancel leaves the browser up
- [ ] `w` takes a name that does not exist without asking
- [ ] `d` askdirectory answers with a **directory**: click one in the list
      and press OK, and that is what comes back — not the one you were
      looking at

### The colour chooser

- [ ] Sixteen swatches in two rows, each drawn in its own colour, the top row
      and the bottom row being a colour and its bright form
- [ ] Clicking a swatch answers with that colour and closes
- [ ] Typing `red` answers `#cd0000` — **not** `#ff0000`. That is the red
      your terminal will actually draw, and reporting the request back would
      hide the difference until you wondered why your orange looked like
      mustard
- [ ] Typing `#005f5f` answers `#005f5f` unchanged: you said exactly what you
      meant, and the approximating happens when it is drawn
- [ ] Typing something that is not a colour at all does nothing and does not
      crash
- [ ] Cancelling answers `(None, None)` — a pair, because callers write
      `rgb, name = askcolor()`

### And again, the one that matters

- [ ] After every chooser, by every exit, the application still answers the
      keyboard
