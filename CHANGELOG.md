# Changelog

All notable changes to TkCurses. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions are
[PEP 440](https://peps.python.org/pep-0440/), taken from git tags.

## [Unreleased]

### Added
- Text's `edit`, `count`, `dump`, `replace`, `tag_bind` and `tag_unbind`,
  `scan_mark` and `scan_dragto`, `yview_pickplace` and `debug`, measured
  against Tk 9.0.2. Tag bindings follow Tk's rules: the tags under the
  pointer hear its events and its crossings, a key goes to the tags at the
  cursor when the pointer is on none, and a click on tagged text reaches
  them in a terminal without hover reporting. `replace` is one step for
  undo and keeps the cursor where Tk keeps it.
- The rest of the Canvas's item methods, measured against Tk 9.0.2:
  `find` and `addtag` with Tk's search commands, `find_above`,
  `find_below`, `find_enclosed` and the `addtag_*` family; `halo` and
  `start` on `find_closest`; `moveto` and `scale`; editing a text item with
  `insert`, `dchars`, `icursor`, `index` and `focus`, and the `select_*`
  methods, its selection drawn in `selectforeground` and
  `selectbackground` and its insertion cursor as the terminal's cursor;
  `insert` and `dchars` on a line's or polygon's points; and `scan_mark`
  and `scan_dragto`. `postscript` raises: a terminal has no PostScript.
- `Listbox.itemconfigure` and `itemcget`: a row's own `background`,
  `foreground`, `selectbackground` and `selectforeground`, drawn over the
  list's and kept with the row as others are inserted or deleted.
- `Spinbox.selection`, `selection_element` - the arrow drawn pressed,
  which a press now names as in Tk - and `scan`, `scan_mark` and
  `scan_dragto` on Entry and Spinbox, dragging the view ten times as far,
  as Tk's do.
- Menu entries take the options Tk gives them: their own `background`,
  `foreground`, `activebackground` and `activeforeground`, drawn over the
  menu's; `selectcolor`, `indicatoron` and `selectimage` on the check and
  radio kinds; `hidemargin`, `font`, `image`, `bitmap` and `compound`. A
  separator takes `background` and refuses the rest, as in Tk.
- `bitmap` on Button, Checkbutton, Label, Menubutton, OptionMenu and
  Radiobutton: Tk's ten built-in names, each drawn as one character
  (`info` as ℹ, `warning` as ⚠, `error` as ✖, the grays as shades), and
  `@file` drawn as the XBM file's bits. `dialog.Dialog` shows its bitmap
  beside the message, as Tk's dialog does.
- `<Enter>` and `<Leave>` are delivered to widgets, made from clicks and
  drags as X11 makes them under the implicit grab: a click is a visit, and
  a held press tells the widget pressed when the pointer leaves it and
  comes back. A Button dragged off is drawn released until the pointer
  returns, as in Tk, and `overrelief` and the active colours show while it
  is held. With `TKCURSES_MOUSE_REPORT_HOVER=1` the pointer is followed
  everywhere.
- A `textvariable` or `variable` given a name binds to the variable of that
  name, as in Tk: `setvar`, every `Variable` of that name and the widget
  see each other's writes. Traces are kept by name, so a trace added through
  one `Variable` fires for writes through another and through `setvar`, and
  `getvar` fires read traces. A classic widget creates a missing variable
  from itself, as Tk's do; a themed one leaves it unset. A Listbox bound by
  name now hears writes made elsewhere.
- `wm_manage` makes a Frame, LabelFrame or forgotten Toplevel a window of
  its own, keeping its children and bindings, and `wm_forget` hands it
  back to be packed, gridded or placed, as in Tk. They raised `TclError`.

### Changed
- `Canvas.focus()` is the canvas's own `focus`, as in tkinter: it names the
  text item with the insertion cursor, and no longer gives the canvas the
  keyboard focus. Use `focus_set()` for that.
- `Canvas.find_overlapping` and `find_closest` pass over hidden items, as
  Tk does.
- `getvar` of a variable that was never set raises `TclError` (`can't read
  "name": no such variable`), as tkinter does; it returned `None`.

### Fixed
- `Text.insert` reads Tk's `chars tagList chars tagList ...`: it took every
  argument after the text for a tag name, so `insert("1.0", "a", "t1",
  "b", "t2")` inserted only `a`. A tag list given, even an empty one, now
  replaces the tags the text would take from either side, a tag list may be
  a string of names separated by spaces, and text inserted at `end` with a
  tag list is tagged where it went rather than a character on.
- A `Menubutton` is flat by default, as in Tk; an `OptionMenu` is raised
  and two wide, as tkinter makes it. The themed Frame, Label and
  Labelframe answer `cget("relief")` with `""`, the theme's, as Tk does,
  and are drawn as before.
- `ttk.Spinbox` steps on `<<Increment>>` and `<<Decrement>>`, which Up,
  Down and its arrows generate, as in Tk, so a program can generate them
  or bind them. Its `from`, `to` and `increment` read back as written -
  `from_=10` is 10, not 10.0.
- A border 0 wide is not drawn, whatever the relief, as in Tk, and every
  classic widget's `borderwidth` defaults to Tk's - 1 on most, 2 on a
  LabelFrame - where it was 0 with the box drawn by the relief alone. The
  boxes look as they did; `bd=0` now takes one away, and
  `cget("borderwidth")` answers what Tk does. A Frame or Canvas given a
  relief needs a `borderwidth` too, as in Tk. A Toplevel keeps its frame.
- A value Tk refuses for an option is refused here too, with Tk's message,
  where it used to be stored and ignored: `relief`, `borderwidth`,
  `highlightthickness`, `anchor`, `compound`, `state`, `orient`,
  `underline`, `wrap`, `padding` and the rest, on the classic and the
  themed widgets alike, by their own rules. A program passing nonsense is
  told so at once.
- `askopenfilenames` and `askopenfiles` can choose several files: the
  chooser's file list takes an extended selection - Shift or Control with
  a click, Shift with Up and Down - and OK answers all of them. They
  chose one at most.
- The option database matches an option by Tk's database name or class -
  `*Button.highlightThickness` or `*Button.HighlightThickness` - as Tk
  does, and no longer by the all-lowercase spelling Tk ignores.
  `option_get(name, className)` takes the option's name and class as in
  tkinter, and gives `""` when nothing matches.
- Canvas is flat by default, as in Tk, so it fills its space with no box
  around it; it was sunken. Pass `relief="sunken"` for the old look.
- Spinbox: a `from` above `to` is swapped, as Tk swaps it, rather than
  counting down. Numbers are shown in Tk's own format - an increment of
  0.5 shows `1.0`, `1.5`, `2.0` rather than `1`, `1.5`, `2` - and a step
  that would pass an end stops on it rather than doing nothing. ttk.Spinbox
  follows ttk's own rules for both, which differ.
- The root window sends `<Configure>` with its size, then `<Map>`, when
  it first appears, as Tk does, so a `<Configure>` binding learns the
  starting size without waiting for a resize. A root withdrawn at start
  sends them when it is first shown.
- `tkcurses.curses`: `setscrreg()` sets the rows `scroll()` moves, and a
  newline or a wrap on the bottom row of that region scrolls it, so a
  header and footer stay put around a scrolling log. Text written by
  `addstr`, `addnstr` and `addch` now wraps onto the next row and honours
  a newline - clearing the rest of the row - as curses does, and running
  off the bottom without `scrollok` raises `curses.error` as curses does.
- ttk.Checkbutton and ttk.Radiobutton report `selected` while on, and
  `alternate` while their variable does not exist - as one made without a
  variable does until it is first set - so `instate()` and a style map see
  them, and the indicator is drawn from those flags as a theme draws it.
  A ttk.Checkbutton over an empty variable is off; it was drawn `[-]`.
- `justify` is checked on every widget that has it, as Tk checks it:
  `"middle"` is refused, `"c"` reads back `"center"`, and `""` is refused
  except on the ttk label family and ttk.Progressbar, where it means unset.
  Only Listbox checked it.
- `font.Font` refuses an option a font does not have when it is made, as
  Tk does - `Font(weight="bold", colour=1)` was accepted - and `cget`,
  `configure`, `actual` and `metrics` refuse one with Tk's own message,
  `bad option "-colour": must be -family, -size, ...`.
- Ctrl-C in a dialog opened inside `mainloop()` cancels it, as Escape
  does and as it already did before `mainloop()`; it closed the whole
  application, and the dialog answered as if refused. A second Ctrl-C
  closes the application. A modal window that binds no Escape is closed
  instead, and with text selected in the dialog Ctrl-C copies it.
- A Canvas rectangle or oval with no outline fills up to but not including
  its far corner, `x2` and `y2`, as Tk's does; it filled one pixel further
  each way. One with an outline is unchanged: Tk draws the outline on `x2`
  and `y2`.

## [0.3.0rc3] - 2026-11-08

The third release candidate. The themed widgets now take Tk's ttk options
and refuse the classic ones, as tkinter's do: a program that gave a ttk
widget `relief`, `background` or another classic option will now fail here
as it would on tkinter, and should set its appearance through a style.

Wide characters - CJK, fullwidth letters, most emoji - take two cells
everywhere: entries, Text, Listbox, the menus, the Treeview, the Canvas and
the `curses` compatibility module, which now draws as ncurses does. A
Listbox, Treeview or Notebook given no size asks for the room its contents
need, a Treeview heading runs its command, and Ctrl-C is answered between
callbacks - cancelling a dialog shown before `mainloop()` as Escape does -
rather than raised in the middle of one.

### Changed
- The ttk widgets refuse the classic widgets' options, as Tk's do:
  `ttk.Button(relief="flat")`, `cget("troughcolor")` on a ttk.Scrollbar
  and the rest raise `unknown option`, and `keys()` and `configure()` list
  Tk's ttk options alone. They were accepted - 335 names across the twenty
  themed widgets - so a program that used one ran here and failed on
  tkinter. Give a themed widget's appearance through its style.

### Fixed
- Padding set on the root window or a Toplevel while the program runs
  moves their children at once; it waited for the terminal to be resized.
  A negative `padx` or `pady` reads back as 0 on every widget, as in Tk
  (`""` on a Message), and one that is not a distance is refused when it
  is set rather than breaking the layout later.
- `pack` and `grid` are accepted inside a PanedWindow that has panes, as in
  Tk, laying their children out over the panes. A pane's `winfo_manager()`
  is `panedwindow`, as Tk's is, and `""` after `forget`; adding a packed
  widget as a pane takes it out of pack, and packing a pane takes it out of
  the panes.
- A Canvas `scrollregion` that is not four distances - `0`, three numbers,
  `"a b c d"` - is refused when it is set, with Tk's message; it was
  stored and then raised at the first layout.
- `justify="right"` and `"center"` place the text in an Entry, Spinbox,
  `ttk.Entry`, `ttk.Spinbox` and `ttk.Combobox`, as in Tk, while all of it
  fits; it was always drawn from the left. A click, `index("@x")` and
  `bbox` follow it. While the field has the focus, one cell at the right is
  kept for the insertion cursor.
- A themed widget refuses `configure(class_=...)` after it is made, with
  Tk's "attempt to change read-only option", even to the class it already
  has; it took the new class and lost its class's bindings and style.
- `update_idletasks()` lays widgets out and redraws, as in Tk, so
  `winfo_width()` after it gives the width a widget will have, and a label
  changed before a long computation shows the change while it runs. So does
  `update()` called on a widget other than the root.
- `padding` enlarges a themed Label, Button, Checkbutton, Radiobutton and
  Menubutton and moves their text in from it, as in Tk; it was honoured
  only by the themed containers.
- Ctrl-C is answered between callbacks rather than raised in the middle of
  one. A callback running when it arrived was cut short - a poll that
  rescheduled itself with `after` simply stopped - while the program went
  on. A second Ctrl-C while a callback has not returned still interrupts
  it, and a program's own SIGINT handler is left alone.
- Wide characters - CJK, fullwidth letters, most emoji - take two cells and
  combining marks none, as on the terminal, in labels, buttons, check and
  radio buttons, menubuttons and messages: their size, wrapping, anchoring,
  justification and underline. Nothing is drawn past a widget's edge, and
  a wide character the edge cuts in half leaves a blank.
- Entry, Spinbox and the ttk entries measure wide characters in cells: the
  insertion cursor sits on the character it is at, a click on either half of
  an ideograph lands on it, a selection covers both its cells, and the view
  and a scrollbar's fractions count cells.
- Listbox, Scale, Menu, the menubar, ttk.Notebook, ttk.Treeview, Canvas
  text, LabelFrame and Message measure wide characters in cells: a Listbox
  keeps its border, a Scale's value no longer overwrites its label, a menu's
  accelerators are whole, a tab is as wide as its label, and Canvas text is
  centred where it should be. `font.Font.measure` counts cells too.
- A ttk.Treeview cell is cut at its column's edge. Text longer than its
  column pushed the columns after it out of line under their headings.
- Text measures wide characters in cells: a row of ideographs wraps at
  half as many characters, one that would straddle the edge starts the
  next row, a combining mark stays with its letter, tags colour both cells
  of a wide character, and `bbox`, clicks, Up and Down and numeric tabs
  count cells.
- A Listbox with a `width` or `height` of zero or less is as wide as its
  widest item and as tall as its items, as listbox(n) says, and follows
  them as they change. It asked for no room and drew an empty box.
- A ttk.Treeview asks for its shown columns side by side and `height`
  rows under its heading, with its border, as Tk's does. It asked for no
  width, so a packed tree drew nothing.
- Clicking a ttk.Treeview heading runs its `command`, when the button is
  released over the heading it was pressed on, as Tk's does. It was
  stored and never called. The table example sorts by its headings.
- The `curses` compatibility module measures text in cells, as curses
  does: an ideograph moves the cursor two cells and a combining mark
  none, `insstr` shifts the line by the cells it inserts, and wide text
  is drawn whole rather than overwritten by what follows it.
- Ctrl-C in a dialog shown before `mainloop()` cancels it, as Escape
  does. It printed a KeyboardInterrupt traceback.
- A ttk.Notebook asks for its largest page shown, its border and its tab
  row, as Tk's does, or for `width` and `height` as its page area. It
  asked for nothing, so one packed without `fill` drew nothing. Its page
  is placed inside the border once rather than twice, a cell further in
  and two smaller each way than the frame drawn round it.

## [0.3.0rc2] - 2026-11-07

The second release candidate. Grid and PanedWindow layout now follow Tk's
own arithmetic, ported from its C sources and checked against Tk 9.0.2 on
random layouts: a program that relied on a PanedWindow sharing extra room
between its panes, or on a uniform grid group overflowing, will now lay
out as it would in Tk. Five other departures from Tk found while writing
the examples are fixed too.

The documentation gained a four-part tutorial, a porting guide, a guide to
terminals, a configuration reference and a compatibility matrix, with
eleven example programs; every program in them is run on each
documentation build. The configuration settings for colour depth, box
drawing and the mouse now take effect, nine that did nothing are removed,
and the menu bar can be reached from the keyboard.

### Added
- A guide to porting a tkinter program: sizes in cells, windows, fonts,
  colours, the keyboard, the mouse, output and errors, with programs that
  are run against the library on every documentation build.
- A compatibility matrix in the reference: every class, method and function
  of tkinter's, and whether TkCurses has it, generated on every
  documentation build so it cannot drift.
- A guide to terminals: what TkCurses needs from one, colour depth,
  resizing, the keys a terminal cannot send, the mouse, the clipboard,
  Unicode, suspending and restoring, and the settings that take effect.
- Six example programs in `examples/` - a form, a to-do list, a text
  editor, a table and a chart among them - on a page of the documentation
  that shows each one's screen, taken by running it when the documentation
  is built.
- A configuration reference: every setting, its environment variable, its
  values and default, and the settings that were removed, generated from
  the code on every documentation build.
- Five more example programs: a calculator in colour, a window laid out
  with pack, grid and place together that follows a resize, a line graph
  and a scene of shapes on a Canvas, and a picture - the Mandelbrot set,
  or an image file - fitted to the window.
- A tutorial in four parts: an introduction that explains what TkCurses is
  and what it is built on - event-driven programs, tkinter, curses and
  panels, Unicode, colour and graphics - then the core concepts of the
  widget tree, geometry management and events, the common widgets, and a
  notes application built a piece at a time. With them, pages of common
  mistakes, how TkCurses works, and a glossary; and the notes application
  as a twelfth example program.

### Changed
- The `dos` theme has a look of its own: double lines across and single
  lines down (`╒═╕`), as DOS programs framed their windows. It drew
  exactly what `double` draws.
- An unknown colour name is refused when it is set, with Tk's
  `unknown color name "x"`, for every widget colour option, a Text tag's
  colours and a Canvas item's `fill` and `outline`. `darkyellow`, which Tk
  does not have, and a name with a space at either end are now refused too.

### Removed
- Nine configuration settings that were accepted and did nothing:
  `[display] refresh_interval`, `[input] poll_timeout` and `keypad`, the
  whole `[accessibility]` section (`high_contrast`, `min_click_interval`,
  `screen_reader`) and the whole `[debug]` section (`enabled`, `log_file`,
  `log_level`), with their `TKCURSES_*` variables. A program that still
  sets one is told so when it ends.

### Fixed
- A PanedWindow's panes are sized by Tk's own arithmetic, from
  `tkPanedWindow.c`. A pane starts at its `width` or what its child asks
  for, and room beyond that goes to the last pane rather than being shared;
  the new `stretch` pane option (`always`, `first`, `last`, `middle`,
  `never`) changes who takes it. A pane's `width` is kept through a
  resize, and moving a sash sets every pane's `width`, as Tk's does. 200
  paned windows recorded from Tk 9.0.2 are matched sash for sash.
- Grid rows and columns are sized by Tk's own arithmetic, from
  `tkGrid.c`. A `uniform` group under a spanning widget no longer grows
  past its container; spare room lands on the later lines, as in Tk; a
  line's `pad` is added to its largest child rather than on top of its
  `minsize`; and a weight-0 line in a `uniform` group counts as weight 1.
  150 grids recorded from Tk 9.0.2 are matched cell for cell.
- Text too wide for a Label, Button, Checkbutton or Radiobutton is cut
  where its `anchor` puts it, as in Tk: anchored `e`, the end shows. The
  start always showed. Themed widgets show the start, as Tk's do.
- `place` shares a container with `pack` or `grid`, as in Tk, so a badge
  can sit over packed content. Moving a widget between `place` and `pack`
  in one container takes it out of the other, a forget from a manager not
  laying the widget out leaves it alone, and a container whose last packed
  child was forgotten can be gridded. The error for mixing `pack` and
  `grid` is Tk 9's.
- The root window and a Toplevel paint their `background` behind their
  widgets, as Tk's do. It was accepted and nothing was drawn.
- Tab into an Entry, Spinbox, or a themed entry, spinbox or editable
  combobox selects what is in it, with the cursor at the end, so typing
  replaces it, as in Tk. Typing went in front of the old text. Moving the
  focus with Tab or F6 sends `<<TraverseOut>>` and `<<TraverseIn>>`, as
  Tk's does.
- `Canvas.canvasx` and `canvasy` take a position in the canvas's window,
  as `event.x` and `event.y` are, as Tk's do. They took a position on the
  screen, so `canvas.canvasx(event.x)` was right only for a canvas at the
  screen's top-left corner, and a click on an item in any other canvas
  could reach the wrong item.
- `TKCURSES_DISPLAY_COLOR_MODE` (`[display] color_mode`) takes effect: `8`,
  `16` or `256` draws with no more colours than that, and `truecolor` draws
  pictures in full colour as `COLORTERM=truecolor` does. It was read and
  ignored.
- `TKCURSES_DISPLAY_UNICODE=0` (`[display] unicode_borders`) draws boxes,
  arrows and bars in ASCII, for a terminal without box-drawing characters.
  It was read and ignored.
- `TKCURSES_MOUSE_ENABLED=0` (`[mouse] enabled`) leaves the mouse to the
  terminal. It was read and ignored.
- A configuration value that cannot be read, or is out of range, is
  reported on the terminal when the program ends. It was corrected without
  a word.
- The porting guide offered `TKCURSES_DISPLAY_COLOR_MODE`, which then did
  nothing. It now says to set `TERM`, and the terminal guide covers both.
- The menu bar can be reached from the keyboard, as in Tk: F10 opens the
  first menu, and Alt with an underlined letter opens that menu, runs that
  command or posts that Menubutton. Only the mouse reached it before.
- Alt with a key, which a terminal sends as Escape and the key, arrives as
  that key with Alt held, so `<Alt-...>` bindings fire. It arrived as an
  Escape and then the key.
- An Alt letter is no longer typed into an Entry, Spinbox or Text, as Tk's
  bindings ignore it there.
- Every colour name Tk knows is known: its whole table of 665, read as Tk
  reads them, `SteelBlue`, `steel blue` and `gray90` among them. There were
  28, and any other name broke the window's layout when it was drawn.
- An exception in a callback no longer wipes the widgets off the screen. The
  screen was repainted after it, but only the cells beneath the widgets, so
  every widget vanished until the program ended. A curses window refreshed
  after `clearok(True)` in a program that also has widgets did the same.

## [0.3.0rc1] - 2026-11-05

The first release candidate, and the first release since TkCurses was rebuilt
against [ARCHITECTURE.md](https://github.com/slfields/TkCurses/blob/v0.3.0rc1/ARCHITECTURE.md). Behaviour is measured against
Tk 9.0.2, and where Tk's manual is silent or wrong the measurement is recorded
in ARCHITECTURE.md.

### Added

#### Foundations
- `Misc`, `Wm`, `Tk` and `Toplevel`, with the event loop, timers (`after`),
  `winfo_*` and `wm_*`, and the variable classes with `trace`.
- Geometry managers `pack`, `grid` and `place`, with Tk's size negotiation and
  propagation, and per-side `padx`/`pady`.
- Window management without a window manager: windows stay inside the
  terminal, can be dragged by their title and raised, and carry menubars.
- A widget shows only inside its master, as X clips a window by its parent.

#### Classic widgets
- `Frame`, `Label`, `Button`, `Checkbutton`, `Radiobutton`, `Entry`,
  `Spinbox`, `Scale`, `Scrollbar`, `Listbox`, `Text`, `Canvas`, `Menu`,
  `Menubutton`, `OptionMenu`, `Message`, `LabelFrame` and `PanedWindow`.
- Tk 9.0's options across them: reliefs, state and selection colours, focus
  highlight rings, insertion-cursor options shown with the terminal's own
  cursor, `-placeholder`, validation on every condition Tk has, and
  `configure("option")` answering Tk's five-tuple.
- `Text`: tags with gravity, marks, search, undo and redo grouped as Tk groups
  them, tab stops including numeric alignment, peers with `-startline` and
  `-endline`, and paging and views as Tk scrolls them.
- `Listbox`: Tk's selection modes, keys, drag and `exportselection`.
- `Menu`: accelerators bound from their shortcut text, and `-columnbreak`.

#### Themed widgets (`tkcurses.ttk`)
- The themed core widgets, plus `Notebook`, `Combobox`, `Treeview`,
  `Progressbar`, `Separator`, `Sizegrip` and `LabeledScale`, with `Style` and
  themes.
- `-padding`, pane weights, and `identify()` answering the style element.
- `from tkcurses.ttk import *` gives everything `from tkinter.ttk import *`
  does, `setup_master` and `tclobjs_to_py` included.
- `Treeview`: tags, striping, the identify family, `bbox`, column stretch,
  `-displaycolumns`, `-titleitems` and `-titlecolumns`, and sideways scrolling.

#### Input
- Tk's binding rules, multi-event sequences (`<Control-x><Control-s>`),
  virtual events including the navigation and `<<Undo>>`/`<<Redo>>` events,
  and `event_generate` with `keysym`, `button` and `state` as Tk takes them.
- The mouse: clicks, double and triple clicks, shift- and control-clicks,
  drags with autoscroll, the wheel, and auto-repeat while a button is held.
- F6 and Shift-F6 move the focus. Ctrl-C copies a selection, and otherwise
  asks the application to close instead of killing it.

#### Display
- Colour at whatever depth the terminal has, from 8 colours through 256 to
  direct colour.
- `PhotoImage` and `BitmapImage`, reading PNG (interlaced too), GIF, netpbm and
  XBM, with averaging, dithering, perceptual colour matching and exact colour
  past curses' 255-pair ceiling.
- A screen that repairs itself after a resize. The terminal is restored
  however a program exits.

#### Everything else
- tkinter's module-level names: `mainloop`, `TkVersion`, `TclVersion`,
  `EventType`, `getint`, `getdouble`, `getboolean`, `image_names`,
  `image_types` and the file-handler masks. `from tkcurses import *` gives
  everything `from tkinter import *` does except `Tcl` and `CallWrapper`.
- Dialogs: `messagebox`, `filedialog`, `simpledialog`, `colorchooser`,
  `dialog`, `commondialog`, `scrolledtext` and `dnd`.
- The clipboard, and the system clipboard through OSC 52 or the desktop's own
  tool. `PRIMARY` within the application.
- `tkcurses.curses` and `tkcurses.panel`: the curses API on the same screen,
  so curses windows and widgets can share a program.
- Configuration from an INI file and `TKCURSES_*` environment variables.
- `tkcurses-demo`.

### Changed
- A new `Spinbox()` starts empty, as Tk's does, rather than at `0`.
  Configuring `values`, `from` or `to` sets its text as Tk's does, and a
  `ttk.Spinbox` never fills itself in.
- `Event.type` is an `EventType`, as tkinter's is: `event.type ==
  EventType.KeyPress` holds for a key, and `str(event.type)` is `"2"`. It was
  a string such as `"Key"`.
- The version comes from git, so every commit has its own and
  `pip install -U git+https://github.com/slfields/TkCurses` upgrades. Before
  this, every commit was 0.1.0 and an upgrade never replaced anything.
- Development Status is 4 - Beta.
- A pushed `v*` tag builds, checks and publishes a GitHub release. TkCurses is
  not published to PyPI.

### Known gaps
- Some Tk 9.0 options are still refused by some classic and themed widgets.
- Not yet implemented: the Canvas tag, find and transform methods; `Text.dump`,
  `Text.count`, embedded windows and `tag_bind`; tear-off menus; the `Wm` icon
  family; the `busy` family; `scan_mark`/`scan_dragto`; the geometry
  managers' method aliases (`bbox`, `slaves`, `propagate` and the rest);
  screen-distance suffixes such as `2c`.
- `tkinter.Tcl()` and `CallWrapper`: there is no Tcl interpreter here for
  them to work with.
- The option database matches an option's own name rather than Tk's database
  name and class (`highlightThickness`, `HighlightThickness`), so an option
  file written for Tk may not apply.
- Invalid option values are stored instead of refused: Tk raises `TclError`
  for 571 measured cases, booleans and `justify` among them, that are
  accepted here.
- `ttk.Checkbutton` over an empty variable draws the alternate indicator but
  does not report the `alternate` state.
- `<Enter>` and `<Leave>` are not delivered when the pointer crosses a widget.
- POSIX only: Windows cannot import it. Tested on Linux; macOS is untested.

## [0.2.0] - 2026-01-18

Phase 2 of the original codebase: the base widget classes, `Tk` and `Toplevel`,
the variable classes and the panel stack. Superseded by the rebuild; it has no
`Entry` or `Text`.

[Unreleased]: https://github.com/slfields/TkCurses/compare/v0.3.0rc3...HEAD
[0.3.0rc3]: https://github.com/slfields/TkCurses/compare/v0.3.0rc2...v0.3.0rc3
[0.3.0rc2]: https://github.com/slfields/TkCurses/compare/v0.3.0rc1...v0.3.0rc2
[0.3.0rc1]: https://github.com/slfields/TkCurses/compare/v0.2.0...v0.3.0rc1
[0.2.0]: https://github.com/slfields/TkCurses/releases/tag/v0.2.0
