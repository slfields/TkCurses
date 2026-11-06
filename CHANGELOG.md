# Changelog

All notable changes to TkCurses. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions are
[PEP 440](https://peps.python.org/pep-0440/), taken from git tags.

## [Unreleased]

### Changed
- An unknown colour name is refused when it is set, with Tk's
  `unknown color name "x"`, for every widget colour option, a Text tag's
  colours and a Canvas item's `fill` and `outline`. `darkyellow`, which Tk
  does not have, and a name with a space at either end are now refused too.

### Fixed
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

[Unreleased]: https://github.com/slfields/TkCurses/compare/v0.3.0rc1...HEAD
[0.3.0rc1]: https://github.com/slfields/TkCurses/compare/v0.2.0...v0.3.0rc1
[0.2.0]: https://github.com/slfields/TkCurses/releases/tag/v0.2.0
