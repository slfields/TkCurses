# A larger program

This page builds a notes application of about two hundred lines: a list of
notes on the left, with a search field above it; the chosen note's title
and text on the right, for editing; a menu, keyboard shortcuts, a status
line, and a file the notes are saved in, a moment after you stop typing.

It uses nothing that the [core concepts](concepts.md) and
[common widgets](widgets.md) pages have not introduced. What is new is
the size: with a dozen widgets and as many functions, a program needs an
*organisation*, and that is what this page is really about.

The whole program is `examples/notes.py` in the repository, and its screen
is on the [examples](examples.md#notes) page. Every piece of code below is
taken from that file as it is, so the two cannot differ. Run it with
`python3 notes.py`, or `python3 notes.py ~/my-notes.json` to keep the
notes somewhere other than beside the program.

## The shape of it

The program is in five parts, in this order, and most interface programs
of any size are arranged the same way:

1. **The data** - the notes themselves, as plain Python values, with no
   widgets in sight.
2. **The window** - every widget, made and arranged, but not yet connected
   to anything.
3. **The functions** - what to do when something happens, each one small
   and named for what it does.
4. **The connections** - which events call which functions, gathered in
   one place.
5. **The start** - put the first note on screen, and enter the loop.

Keeping the data apart from the widgets is the important part. The notes
are a list of dictionaries, and the file holds exactly that list. The
widgets only *show* the data: when the user edits, a function copies the
change from the widgets into the data, and when the data changes, a
function copies it back out to the widgets. Nothing else ever looks
inside a widget to find out what the notes are.

## The data

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The data"
:end-before: "# The window"
```

`STORE` is the file. Its contents, if it exists yet, become `notes`. The
next four names are the program's *state*: everything it needs to
remember between one event and the next.

- **`shown`** is which notes the list is showing, in order. When the
  search hides some, line 0 of the list is no longer note 0, and this is
  how to tell which note a line is.
- **`current`** is which note is in the editor, or `None` for none.
- **`loading`** is set while the program itself fills the editor. Filling
  it changes the title and the text, which looks exactly like the user
  typing; this is how the functions that respond to typing tell the
  difference.
- **`pending`** is the id of a save that has been scheduled with `after`
  and not yet made.

Module-level variables like these are the simplest way to hold state in a
short program, and the functions that change them say `global`. A larger
program would usually gather them, and the functions, into a class.

## The window

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The window"
:end-before: "# The left pane"
```

The status line is packed first, against the bottom, so that it keeps its
row whatever happens to the rest. The `PanedWindow` fills everything else
and divides it into two panes with a bar between them, which the user can
move with the mouse, or with Tab and then the arrow keys.

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The left pane"
:end-before: "# The right pane"
```

The left pane is packed: a label and the search field across the top, the
two buttons across the bottom, and the list in everything between. The
comment explains a detail that is easy to get wrong. The keyboard focus
moves through widgets with Tab *in the order they were made*, so the list
is made before the buttons, to be reached first; but the buttons are
*packed* before the list, so that in a short terminal the list is the one
that gives up rows.

`width=1` on the entry and the list looks odd, and is deliberate. Each
widget asks for a width, and with the default an `Entry` asks for twenty
cells. Asking for one leaves the width entirely to the pane, which is what
`fill="x"` wants. `exportselection=False` keeps the list's choice when text
is selected somewhere else; without it, selecting a word in the editor
would unselect the note being edited.

`panes.add` puts the frame into the paned window, starting it 22 cells
wide and never letting it go below 14.

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The right pane"
:end-before: "# Showing the notes"
```

The right pane is gridded, because the title and its label have to sit
side by side above a text that spans their width. Row 1 and column 1 get
the weight, so that when the terminal grows, the text grows and the label
does not. The `Text` and its `Scrollbar` are connected both ways, as on
[Common widgets](widgets.md#text-and-scrolling).

At this point the whole window exists, and none of it does anything.

## The functions

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# Showing the notes"
:end-before: "# Editing"
```

`fill_list` is the one place the list is filled. It works out which notes
match the search, rebuilds the list's lines from them, keeps the current
note chosen if it is still there, and says how many are showing. Every
change that could affect the list calls it, rather than each one patching
the list for itself.

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# Editing"
:end-before: "# The commands"
```

These four move a note between the data and the editor.

- **`open_note`** copies a note *into* the editor, with `loading` set so
  that the changes it makes are not mistaken for typing. `edit_reset`
  empties the undo history, so that Ctrl-Z cannot undo into the previous
  note.
- **`clear_editor`** empties the editor when there is no note to show.
- **`edited`** copies the editor back *into* the note, updates that note's
  line in the list - its title may have changed - and schedules a save.
  If a save was already scheduled, it is cancelled first, so the file is
  written once, half a second after the typing stops, rather than once
  per key.
- **`text_modified`** is how a `Text` says it was changed. It sends
  `<<Modified>>` when its *modified flag* goes from off to on, and not
  again until the flag is cleared, so the function clears it each time.

`save` writes the whole list, and says so on the status line.

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The commands"
:end-before: "# The buttons and the menu"
```

These are what the user's actions run. Each is short, because the work is
done by the functions above.

- **`chosen`** runs when a line of the list is chosen, and opens the note
  that line shows.
- **`new_note`** adds an empty note, clears the search so that the new note
  is not hidden by it, opens it, and puts the cursor in its title.
- **`delete_note`** asks first. `messagebox.askyesno` shows a dialog and
  waits, and the function carries on with the answer: `True` for Yes.
- **`quit_notes`** makes any save still waiting before it closes, so that
  the last few keys typed are not lost.

`new_note` and `quit_notes` take `event=None` because they are called both
by a menu or button, with no arguments, and by a key binding, with an
event.

## The connections

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The buttons and the menu"
:end-before: "# The connections"
```

The buttons and the menu are made last, because their `command` is a
function, and the functions have to exist first. The menu's accelerators,
`Ctrl+N` and `Ctrl+Q`, are only labels; the bindings that make the keys
work are below.

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# The connections"
:end-before: "# Start with"
```

Every way the user can change something, in one list:

- typing in the search field refills the list;
- typing in the title, or in the text, calls `edited`;
- choosing in the list calls `chosen`;
- Ctrl-N and Ctrl-Q are bound on the root, so they work whichever widget
  has the focus;
- **`WM_DELETE_WINDOW`** is the request to close the window. In TkCurses
  that is what Ctrl-C sends, so routing it to `quit_notes` means Ctrl-C
  saves before it closes, too.

## The start

```{literalinclude} ../../examples/notes.py
:language: python
:start-at: "# Start with"
```

With notes, the first is opened and the list is given the focus; without,
a new note is started. Then `mainloop` takes over, and every line above
that runs again runs because the user did something.

## Making it your own

Some changes worth trying, each of which touches only one or two of the
parts:

- **Sort the list by title.** Only `fill_list` decides the order of the
  list; sort `shown` by each note's title there.
- **Show when each note was changed.** Add a `"changed"` key to each note
  in `edited`, using `time.strftime`, and show it on the status line in
  `open_note`.
- **Keep the notes in a class.** Make `notes`, `current` and the rest
  attributes, and the functions methods, and the `global` statements go.
- **Confirm before quitting with an empty title.** `quit_notes` is the one
  place to ask, with `messagebox.askyesno`, as `delete_note` does.

[Common mistakes](mistakes.md) is worth a look before going further, and
the [examples](examples.md) have eleven more complete programs.
