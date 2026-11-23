# TkCurses Architecture

## Overview

**TkCurses** is a tkinter-compatible API layer that translates tkinter widget calls into curses and curses.panel operations for terminal-based rendering. It enables developers to write familiar tkinter-style code that runs entirely in a terminal without any graphical display.

### Core Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Code                              │
│           (tkinter-style: Button, Frame, pack(), etc.)           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TkCurses Layer                              │
│        (Translates tkinter API → curses/panel calls)             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   curses / curses.panel                          │
│              (Terminal rendering backend)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Terminal / TTY                              │
│                   (Text-based display)                           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Goals
- **tkinter API Compatibility**: Mirror tkinter's module structure, classes, and method signatures
- **Terminal Rendering**: All output goes to curses/curses.panel, not Tk/GUI
- **Panel-Based Overlays**: Use curses.panel for window stacking, dialogs, and z-ordering
- **No GUI Dependencies**: Does not use or require Tk, Tcl, or any graphical display
- **Drop-in Potential**: Existing tkinter code can be adapted with minimal changes to run in terminal

### Target Environment
- **Python**: 3.11+
- **Runtime**: Terminal/TTY (no X11/Wayland/GUI required)
- **Core Dependencies**: curses, curses.panel (standard library on Unix)

---

## Design Principles

1. **Structural Parallelism**: Every tkinter module has a corresponding tkcurses module with matching classes/functions
2. **Behavioral Compatibility**: Methods behave like tkinter equivalents within text-mode constraints
3. **Selective Override**: Inherit tkinter logic where possible; override only visual/rendering code
4. **Monospace Rendering**: All output uses fixed-width character cells
5. **Self-Contained Dialogs**: Dialogs render within the character canvas, not as native OS dialogs

---

## Module Mapping

TkCurses mirrors tkinter's 13 modules plus curses-specific additions:

| tkinter Module | tkcurses Module | Purpose |
|----------------|-----------------|---------|
| `__init__.py` | `__init__.py` | Core widgets (Button, Label, Frame, Canvas, Entry, Text, etc.) |
| `__main__.py` | `__main__.py` | Module entry point, demo/test display |
| `colorchooser.py` | `colorchooser.py` | Text-based color selection dialog |
| `commondialog.py` | `commondialog.py` | Base class for text-based dialogs |
| `constants.py` | `constants.py` | Widget constants + curses constants (A_*, KEY_*, ACS_*) |
| `dialog.py` | `dialog.py` | Simple text-based dialog utilities |
| `dnd.py` | `dnd.py` | Drag-and-drop within text canvas |
| `filedialog.py` | `filedialog.py` | Text-based file browser dialog |
| `font.py` | `font.py` | Monospace font management |
| `messagebox.py` | `messagebox.py` | Text-based message/confirmation dialogs |
| `scrolledtext.py` | `scrolledtext.py` | Text widget with scrollbar (character-based) |
| `simpledialog.py` | `simpledialog.py` | Text-based input prompts |
| `ttk.py` | `ttk.py` | Themed text-mode widgets |
| — | `curses.py` | Curses compatibility layer (initscr, getch, etc.) |
| — | `panel.py` | Panel/window stacking (curses.panel equivalent) |

---

## System Components

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Application                              │
│              (tkinter-style or curses-style code)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────────┐
│   tkinter-style API       │   │      curses-style API         │
│  (tkcurses.Button, etc.)  │   │  (tkcurses.curses.initscr)    │
└───────────────────────────┘   └───────────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Widget Layer                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │   Misc     │ │    Wm      │ │   Widget   │ │   Variable   │  │
│  │ (bindings,│ │ (window    │ │ (base for  │ │ (StringVar,  │  │
│  │  focus)   │ │  manager)  │ │  all)      │ │  IntVar)     │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │   Button   │ │   Entry    │ │   Text     │ │   Listbox    │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │   Frame    │ │   Canvas   │ │   Menu     │ │   Scrollbar  │  │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Dialog Layer                                │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐   │
│  │ FileDialog   │ │ MessageBox   │ │     ColorChooser       │   │
│  │ (text-based  │ │ (text-based  │ │   (text-based RGB/     │   │
│  │  file tree)  │ │  buttons)    │ │    palette selector)   │   │
│  └──────────────┘ └──────────────┘ └────────────────────────┘   │
│  ┌──────────────┐ ┌──────────────┐                              │
│  │ SimpleDialog │ │    Dialog    │                              │
│  │ (text input) │ │  (base class)│                              │
│  └──────────────┘ └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Geometry Managers                             │
│         ┌────────────┐ ┌────────────┐ ┌────────────┐            │
│         │    Pack    │ │    Grid    │ │   Place    │            │
│         │ (text-cell │ │ (text-cell │ │ (text-cell │            │
│         │  layout)   │ │  layout)   │ │  coords)   │            │
│         └────────────┘ └────────────┘ └────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Layer                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐   │
│  │ ScreenBuffer │ │ ColorManager │ │   AttributeManager     │   │
│  │ (cell grid,  │ │ (color pairs,│ │   (A_BOLD, A_REVERSE,  │   │
│  │  dirty track)│ │  RGB palette)│ │    text styles)        │   │
│  └──────────────┘ └──────────────┘ └────────────────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐   │
│  │ InputHandler │ │  PanelStack  │ │      CellGeometry      │   │
│  │ (key/mouse   │ │ (z-ordering, │ │   (char dimensions,    │   │
│  │  translation)│ │  visibility) │ │    coordinate math)    │   │
│  └──────────────┘ └──────────────┘ └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Curses Backend                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   CursesScreen                            │   │
│  │  (curses.initscr(), curses.panel for z-ordering,          │   │
│  │   color pairs, ACS characters, input handling)            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Terminal / TTY                                │
│              (Raw terminal via curses library)                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Class Hierarchy

### Core Widget Classes (mirrors tkinter)

```
Misc                              # Event handling, focus, clipboard
├── Wm                            # Window manager (geometry, state)
│
BaseWidget                        # Widget creation, curses window
│
Widget(BaseWidget, Pack, Place, Grid)   # Base for all widgets
├── Button                        # Clickable button [text cell rendering]
├── Canvas                        # Drawing surface [character art]
├── Checkbutton                   # Toggle checkbox [[ ] / [X]]
├── Entry                         # Single-line input [text field]
├── Frame                         # Container [box drawing chars]
├── Label                         # Static text display
├── LabelFrame                    # Labeled container
├── Listbox                       # Scrollable list [line selection]
├── Menu                          # Menu bar/popup [text menu]
├── Menubutton                    # Menu trigger button
├── Message                       # Multi-line message
├── PanedWindow                   # Resizable panes [draggable divider]
├── Radiobutton                   # Radio selection [( ) / (●)]
├── Scale                         # Slider [===●======]
├── Scrollbar                     # Scroll indicator [▲█░░░░▼]
├── Spinbox                       # Numeric input with arrows
└── Text                          # Multi-line text editor

Toplevel(BaseWidget, Wm)          # Top-level window
Tk(Misc, Wm)                      # Main application window

Pack                              # Pack geometry manager
Place                             # Place geometry manager
Grid                              # Grid geometry manager

Variable                          # Observable variable base
├── StringVar
├── IntVar
├── DoubleVar
└── BooleanVar
```

### Dialog Classes

```
commondialog.Dialog               # Base for all dialogs
├── filedialog.FileDialog         # File selection base
│   ├── LoadFileDialog            # Open file (validates existence)
│   └── SaveFileDialog            # Save file (handles overwrite)
├── filedialog.Open               # askopenfilename implementation
├── filedialog.SaveAs             # asksaveasfilename implementation
├── filedialog.Directory          # askdirectory implementation
├── colorchooser.Chooser          # Color selection
├── messagebox.Message            # Message display
└── simpledialog.Dialog           # Custom dialog base
    └── simpledialog._QueryDialog # Input validation
        ├── _QueryString          # askstring
        ├── _QueryInteger         # askinteger
        └── _QueryFloat           # askfloat
```

### TTK Themed Widgets

```
ttk.Widget                        # Themed widget base
├── ttk.Button
├── ttk.Checkbutton
├── ttk.Combobox                  # Dropdown [▼ selection]
├── ttk.Entry
├── ttk.Frame
├── ttk.Label
├── ttk.LabelFrame
├── ttk.Menubutton
├── ttk.Notebook                  # Tabbed interface [Tab1|Tab2|Tab3]
├── ttk.Panedwindow
├── ttk.Progressbar               # Progress [████████░░░░] 67%
├── ttk.Radiobutton
├── ttk.Scale
├── ttk.Scrollbar
├── ttk.Separator                 # Line divider [────────────]
├── ttk.Sizegrip                  # Resize handle [◢]
├── ttk.Spinbox
└── ttk.Treeview                  # Tree/table view [├─ items]

ttk.Style                         # Theme/style configuration
```

---

## Text-Based Widget Rendering

Each widget renders as character cells. Examples:

### Button
```
┌──────────┐     ┌──────────┐
│  Click   │     │▶ Click  ◀│  (focused)
└──────────┘     └──────────┘
```

### Entry
```
Name: [John Doe________]     [John Doe█_______]  (cursor)
```

### Checkbutton / Radiobutton
```
[ ] Unchecked    [X] Checked     ( ) Unselected    (●) Selected
```

### Listbox
```
┌─────────────────┐
│▶ Item 1        ◀│  (selected)
│  Item 2         │
│  Item 3         │
│  Item 4         │
└─────────────────┘
```

### Scale (Slider)
```
Volume: [░░░░░████████░░░░] 65
        Min              Max
```

### Scrollbar
```
▲
█
█
░
░
░
▼
```

### Progressbar
```
Loading: [████████████░░░░░░░░] 60%
```

### Treeview
```
├─ Documents
│  ├─ report.pdf
│  └─ notes.txt
├─ Images
│  └─ photo.jpg
└─ Music
```

### Menu
```
┌─────────────────────┐
│ File   Edit   View  │
├─────────────────────┤
│ New       Ctrl+N    │
│ Open      Ctrl+O    │
│─────────────────────│
│ Exit      Ctrl+Q    │
└─────────────────────┘
```

---

## Window Management

**There is no window manager, so TkCurses is one.** That single fact decides
everything in this section, and it is the one thing about windows that has no
counterpart in tkinter.

### What tkinter does, and why it does not answer this

On Linux, dragging a window is not tkinter's job. Two cases:

| Window | Who moves it |
|--------|--------------|
| Decorated (normal) | **The window manager** — Mutter, KWin, Xfwm. It owns the title bar, intercepts the press, and runs the drag. tkinter is only told the result. |
| `overrideredirect(True)` | **The application.** There is no decoration left to grab, so the program binds `<Button-1>` to record the offset and `<B1-Motion>` to call `geometry()`. This is the standard recipe, not a workaround. |

A terminal has neither a window manager nor decorations that anything else
draws. So **every** TkCurses `Toplevel` is structurally the second case: the
library draws the title, owns the z-order, and receives the press. There is
nobody else to delegate to.

That does not make window dragging an extension to tkinter. It makes
TkCurses play both roles at once — the toolkit *and* the window manager —
and the division below is how it keeps them straight.

### The rule

**Decoration decides who drags.**

- A **decorated** `Toplevel` — the default — is dragged by TkCurses, from its
  title row. This is the library standing in for the window manager, doing
  the job the WM would do on a desktop. An application writes nothing.
- An **`overrideredirect(True)`** `Toplevel` is *not* dragged by TkCurses.
  It has no decoration, so there is nothing to grab, and moving it is the
  application's business — exactly as on a desktop.

The second half is not a limitation, because **the standard tkinter recipe
works here unchanged.** Verified:

```python
win = tkcurses.Toplevel(root)
win.overrideredirect(True)
win.geometry("20x4+3+2")
bar = tkcurses.Label(win, text=" drag me ")
bar.place(x=0, y=0, relwidth=1.0, height=1)

drag = {}
def press(event):
    drag["x"] = event.x_root - win.winfo_x()
    drag["y"] = event.y_root - win.winfo_y()

def motion(event):
    win.geometry(f"20x4+{event.x_root - drag['x']}+{event.y_root - drag['y']}")

bar.bind("<Button-1>", press)
bar.bind("<B1-Motion>", motion)
```

That is a tkinter program, not a TkCurses one, and it moves the window. Code
written for a borderless tkinter window ports without edits.

### The root is not one of them

tkinter has two kinds of top-level window and they part company here, so the
distinction is worth being blunt about:

| | What it is | Moved by | Resized by |
|---|---|---|---|
| `Tk` — the root | **The terminal itself.** Its size is the terminal's size and its position is wherever the user put the terminal. | The user's *desktop* window manager, dragging the terminal emulator. Nothing in TkCurses. | The user, by resizing the terminal. TkCurses is told, via `<Configure>`. |
| `Toplevel` | A window TkCurses draws **inside** the root, out of cells it owns. | TkCurses, or the application — per the rule above. | The application, e.g. by placing a `ttk.Sizegrip`. |

So the root is the exception to everything in this section, and it is the
exception precisely because it is the one window TkCurses did not draw. A
`Toplevel` is ours down to the last cell; the root is a hole in the desktop
that somebody else manages. Anything the library does to move or resize a
window applies to `Toplevel` and stops at the root.

This is also why the earlier sizegrip note reads the way it does: a sizegrip
resizes *its own* window, which is nearly always a `Toplevel` and works; put
one in the root and it has nothing it can do, because no drawing changes how
big a terminal is.

### What the library's own drag must do

- **Handle**: the title row, which is already drawn. Nothing else — a press
  anywhere else belongs to whatever widget is there.
- **Move by distance travelled**, not to the position arrived at, so wherever
  in the title the press landed stays under the pointer. The same rule the
  scrollbar thumb and the sizegrip follow.
- **Raise on press.** Clicking a window to move it and having it stay behind
  another would be surprising, and TkCurses owns the z-order.
- **Clamp to the screen**, via `wm_geometry` — see the invariant below,
  which both paths go through.
- **Never swallow a press an application bound.** Class bindings run after
  widget bindings, so an application that binds the title row itself wins.

### Resizing already follows this rule

`ttk.Sizegrip` is a widget the *application* places, so it works on any
window it is put in — that is the ttk API, and it is the application's
choice — and it works on a `Toplevel` for the same reason dragging does:
TkCurses drew it. The root is the exception, per the table above.

Note the asymmetry, which is correct rather than accidental. Resizing is
exposed as a ttk **widget** because ttk has one; moving is not, because ttk
has no such widget — on a desktop the WM provides it. So resizing is opt-in
per window and moving is a property of decoration.

### Where a window may be

**A `Toplevel` is always wholly inside the terminal.** Not a courtesy applied
when geometry is set — an invariant that holds at every moment, because there
is nowhere for a window to overflow to and because everything else here is
built on it: hit-testing, the grab, centring a dialog on its parent, and any
code that computes from `winfo_x()`.

Three things can break it, and all three go through `Wm._within_screen`:

| | What changes | How the invariant is kept |
|---|---|---|
| `geometry()` | The window's position and size | Clamped on the way in; the position asked for is remembered |
| `minsize()` / `maxsize()` | The window's size, not its position | A window at the edge that grows is moved back inside |
| A terminal resize | **The screen, not the window** | Every window is repositioned into the new screen |

The third is the one that is easy to miss, and it was missed: the clamp used
to live inside `_apply_geometry`, so it held against whatever the terminal
was when geometry was last set and nothing re-established it. A window could
then report a position its own setter, asked for that exact position, would
refuse to produce.

**Why it is repositioned rather than clipped.** A `Toplevel` is both a `Wm`,
which may not overflow the terminal, and a `Misc`, which may and gets clipped
— `place()` is allowed to put a label half off the edge, and Tk clips that
rather than moving it. Both rules are right for what they were written for,
and a resize used to apply the weaker one to windows. The cost was not
cosmetic: a modal window left outside the screen still takes every click
through its grab, so the application stops responding with nothing drawn to
explain it.

**The position survives.** What `geometry()` was last asked for is kept, and a
window displaced by a shrinking terminal returns to it when there is room
again. Otherwise a one-column shrink and back would quietly rearrange the
screen. An explicit `geometry()` call replaces what is remembered — a
position the application named is the one it meant.

The root is exempt, as everywhere else in this section: its size *is* the
terminal's.

### How it is bound

Class bindings on `<Button-1>`, `<B1-Motion>` and `<ButtonRelease-1>`,
installed by `Toplevel` the first time a window of a given class is made —
`_toplevel_press`, `_toplevel_drag`, `_toplevel_release`.

They are registered under **`winfo_class()`, not the literal `"Toplevel"`**,
and that is load-bearing. A `Toplevel` subclass reports its own name from
`winfo_class()`, so a hard-coded tag would bind nothing for
`simpledialog.Dialog` — making every dialog in the library the one kind of
window that could not be moved. Same trap as Spinbox/Entry,
OptionMenu/Menubutton and ScrolledText/Text: bind under the class the widget
actually reports.

Because these are class bindings, widget bindings still run first — an
application that binds `<Button-1>` on its own title row sees the event and
can stop this with `"break"`.

### Known gap

`geometry()` changes a window's size and position and redraws it, but fires
no `<Configure>` (`TkCurses-b5o`). An application doing its own dragging
therefore cannot learn its new position from an event — it has to read
`winfo_x()`/`winfo_y()`. That is a bug rather than a design choice.

## Window Content Areas

When rendering content within curses windows, **borders occupy the outermost cells** on all four sides. All widget rendering code MUST account for this.

### Border Cell Layout

For a window of size `width × height`:

```
Column:   0        1 to width-2       width-1
         ┌─────────────────────────────────┐  Row 0 (top border)
         │                                 │
         │     USABLE CONTENT AREA         │  Rows 1 to height-2
         │     (width-2) × (height-2)      │
         │                                 │
         └─────────────────────────────────┘  Row height-1 (bottom border)
         ^                                 ^
    Col 0 (left)                    Col width-1 (right)
```

### Content Coordinate Rules

| Window Type | Border | Content Origin | Usable Size |
|-------------|--------|----------------|-------------|
| Bordered window | Yes | `(1, 1)` | `(width-2) × (height-2)` |
| Borderless window | No | `(0, 0)` | `width × height` |

### Implementation Requirements

1. **Draw border first**: Call `window.border()` or `window.box()` before writing content
2. **Content at (1,1)**: All text/widget content starts at row 1, column 1
3. **Respect right edge**: Content must not exceed column `width-2`
4. **Respect bottom edge**: Content must not exceed row `height-2`
5. **Subwindows**: Use `derwin(height-2, width-2, 1, 1)` for content subwindows
6. **Write through `BaseWidget._write_line`**, not `addstr` or `insstr` directly.
   It knows the two things curses will not do: it clips a write that would
   run past the right edge, which curses wraps onto the next row instead of
   dropping; and it uses `insstr` for the one cell where `addstr` refuses —
   the window's genuinely last — because filling that would scroll a window
   with nowhere to scroll to.

   **`insstr` inserts.** It shifts the rest of the row one cell right and
   drops the last, so using it anywhere but that last cell throws a cell
   away. Twice now that cell was the widget's own right border: a Listbox
   put its selection marker on with `insstr` at the last *content* column and
   every row lost its border, and a Spinbox did the same with its second
   arrow. Both are `TkCurses-ego`. `_write_line` is the one place that knows
   which cell is which.

### A widget shows only inside its master

X clips every window by its parent's, and Tk inherits it: a label placed 6
wide in a 5-wide frame shows 5 cells, and whatever is beside the frame stays
visible. A widget's window here is the part of it that survives **every
ancestor up to its toplevel**, and the screen (`Misc._visible_rect`,
`TkCurses-wbov`). Before that it was clipped by the screen alone, and a
shrunken ttk.Panedwindow pane's label covered the sash, handle and all.

- **A toplevel is clipped only by the screen**, and its children are clipped
  to the area **inside** its border - that border is the window manager's
  frame, which nothing in the window can cover, and `place(x=0, y=0)` already
  starts inside it. A frame's own border is not protected: as in X, a child
  may cover it.
- **A Menu is not clipped by its master** (`_clipped_by_master = False`). It
  is a toplevel window in Tk, posted against the screen, and an OptionMenu
  makes its menu a child of the button.
- **The window may start inside the widget.** When the left or top of a
  widget is clipped away, `_window_offset` records where its window begins,
  and `_write_line` takes the widget's own coordinates and moves them into
  the window, dropping what falls before its first cell. That applies at the
  screen edge too, which had never shifted the drawing: a label placed at
  `x=-3` showed its *first* five cells. A widget sliding along under its
  container keeps the same window in the same place and is redrawn because
  the offset changed.
- **Geometry is untouched.** `winfo_x`, `winfo_width`, `winfo_ismapped` and
  `winfo_viewable` report what the widget was given; one wholly outside its
  master has no window and is still mapped and viewable.
- **A click on the clipped-off part reaches what is underneath**, and the
  terminal's cursor does not show there.

Measured against Tk 9.0.2 with frames whose size could be read through the
API: a 90-pixel child in a 50-pixel frame, and `winfo containing` at points
over its overflow, which answered `.` between the frames and the sibling
`.!frame2` over it - never the child. A child placed wholly outside its
master answered `winfo ismapped` 1 and `winfo viewable` 1.

### Example: Bordered Toplevel (30×8)

```python
# Window dimensions
win_width, win_height = 30, 8

# Border cells (DO NOT write here)
# - Row 0: columns 0-29 (top border)
# - Row 7: columns 0-29 (bottom border)
# - Column 0: rows 0-7 (left border)
# - Column 29: rows 0-7 (right border)

# Usable content area: 28 columns × 6 rows
# - Rows: 1, 2, 3, 4, 5, 6
# - Columns: 1 through 28

window.border()  # Draw border FIRST
window.addstr(1, 1, "Content starts here")  # Inside border
window.addstr(6, 1, "Last usable row")      # Row height-2
```

### Widget Rendering Implications

All widgets that render borders MUST:
- Calculate usable content area as `(width-2) × (height-2)`
- Offset all content rendering by `(1, 1)`
- Truncate text that would exceed `width-2` characters
- Clip content that would exceed `height-2` rows

This applies to any widget with a `borderwidth` of 1 or more and a relief
that is not flat - Tk's rule, that a border 0 wide is not drawn whatever its
relief (`TkCurses-8b8c`). The defaults are Tk's (1 on most widgets, 2 on a
LabelFrame, 0 on a Frame and a Canvas), so the boxes look as they did. Two
exceptions. A flat border takes no cell: Tk keeps its pixels blank, and
here that would put a blank ring round every Label, whose default is 1. A
Toplevel's frame stands in for the window manager's and keeps the old rule
- any width, or any relief - at a default of 1, not Tk's 0, so
`borderwidth=0` is still how a program asks for a toplevel without one. An
indicatorless Checkbutton or Radiobutton draws its border in its shown
relief, which is sunken while it is on, so it has one at any width of 1 or
more.

---

## Text-Based Dialogs

### MessageBox

```
┌────────────────────────────────┐
│            ⚠ Warning           │
├────────────────────────────────┤
│                                │
│  Are you sure you want to      │
│  delete this file?             │
│                                │
├────────────────────────────────┤
│    [ Yes ]       [ No ]        │
└────────────────────────────────┘
```

### FileDialog

```
┌─ Open File ────────────────────────────────────┐
│ Location: /home/user/documents                 │
├────────────────────────────────────────────────┤
│ ..                                      <DIR>  │
│ ├─ projects/                            <DIR>  │
│ ├─ notes/                               <DIR>  │
│ ├─▶report.pdf                          1.2 MB ◀│
│ └─ readme.txt                           4 KB   │
├────────────────────────────────────────────────┤
│ File name: [report.pdf________________]        │
│ File type: [All Files (*.*) ▼]                 │
├────────────────────────────────────────────────┤
│         [ Open ]         [ Cancel ]            │
└────────────────────────────────────────────────┘
```

### ColorChooser

```
┌─ Select Color ─────────────────────────────────┐
│                                                │
│  Basic Colors:                                 │
│  ┌──┬──┬──┬──┬──┬──┬──┬──┐                    │
│  │██│██│██│██│██│██│██│██│  (color grid)      │
│  ├──┼──┼──┼──┼──┼──┼──┼──┤                    │
│  │██│██│██│██│██│██│██│██│                    │
│  └──┴──┴──┴──┴──┴──┴──┴──┘                    │
│                                                │
│  R: [255___]  G: [128___]  B: [0_____]        │
│                                                │
│  Preview: ████████████                         │
│  Hex: #FF8000                                  │
│                                                │
│         [ OK ]           [ Cancel ]            │
└────────────────────────────────────────────────┘
```

### SimpleDialog (askstring)

```
┌─ Enter Name ───────────────────┐
│                                │
│  Please enter your name:       │
│  [________________________]    │
│                                │
│     [ OK ]     [ Cancel ]      │
└────────────────────────────────┘
```

---

## Component Interactions

### Widget Creation Flow

```
app = tkcurses.Tk()
           │
           ▼
┌──────────────────────────────────────────┐
│  1. Call curses.initscr()                │
│  2. Initialize curses.panel stack        │
│  3. Set up color pairs (curses.init_pair)│
│  4. Configure input (keypad, noecho)     │
│  5. Return Tk-compatible instance        │
└──────────────────────────────────────────┘
           │
           ▼
btn = tkcurses.Button(app, text="Click")
           │
           ▼
┌──────────────────────────────────────────┐
│  1. Create Button widget instance        │
│  2. Register with parent's children      │
│  3. Allocate cell region (on pack/grid)  │
│  4. Render button text to cells          │
└──────────────────────────────────────────┘
           │
           ▼
btn.pack()
           │
           ▼
┌──────────────────────────────────────────┐
│  1. Pack manager calculates cell region  │
│  2. Widget draws to ScreenBuffer         │
│  3. Mark dirty cells                     │
│  4. Schedule refresh                     │
└──────────────────────────────────────────┘
```

### Widget Window Lifecycle

Each widget manages its own curses window wrapped in a panel. The lifecycle includes creation, resizing, and destruction. **Critical**: When a widget shrinks, special handling is required to clear vacated screen areas.

#### Window States

```
┌─────────────────────────────────────────────────────────────────┐
│                    Widget Window Lifecycle                        │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────┐     pack()/grid()/place()     ┌──────────┐
    │  Created │ ──────────────────────────────▶│ Allocated │
    │ (no win) │                                │ (has win) │
    └──────────┘                                └──────────┘
                                                     │
                         ┌───────────────────────────┤
                         │                           │
                         ▼                           ▼
                  ┌────────────┐              ┌────────────┐
                  │   Resize   │              │  Destroy   │
                  │ (grow/shrink)│              │ (cleanup)  │
                  └────────────┘              └────────────┘
```

#### Window Creation (`_create_window`)

Called when widget first receives allocation from geometry manager:

1. Create curses subwindow via `parent_window.subwin(h, w, y, x)`
2. Wrap window in panel via `PanelStack.create_panel(window)`
3. Panel provides z-ordering and visibility management
4. Widget is now ready to render content

#### Window Resize - Growing

When new allocation is **larger** than current:

1. Call `curses_window.resize(new_height, new_width)`
2. Window expands into available space
3. New area is uninitialized (contains garbage)
4. Widget `_draw()` fills the new area with content

#### Window Resize - Shrinking (CRITICAL)

When new allocation is **smaller** than current, the shrinking window leaves "ghost" pixels in the vacated area. The panel system does NOT automatically clear these.

**Required Behavior:**

```
┌──────────────────────────────────────────────────────────────┐
│                   SHRINK HANDLING STRATEGY                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Old allocation: 20x5    New allocation: 10x3                │
│                                                              │
│  ┌────────────────────┐   ┌──────────┐                       │
│  │ Hello World!       │   │ Hello    │░░░░░░░░░░             │
│  │ Line 2             │ → │ Line 2   │░░░░░░░░░░             │
│  │ Line 3             │   │ Line 3   │░░░░░░░░░░             │
│  │ Line 4             │   └──────────┘░░░░░░░░░░             │
│  │ Line 5             │   ░░░░░░░░░░░░░░░░░░░░░░             │
│  └────────────────────┘   ░ = vacated area (ghost pixels)    │
│                                                              │
│  Solution: Replace window instead of resizing                │
│                                                              │
│  1. Store old window dimensions                              │
│  2. Create NEW window at new (smaller) size                  │
│  3. Call panel.replace(new_window) to swap                   │
│  4. Delete old window                                        │
│  5. Parent must redraw its background in vacated area        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Implementation in `_resize_window`:**

```python
def _resize_window(self, height: int, width: int) -> None:
    if self._curses_window is None:
        return

    old_h, old_w = self._curses_window.getmaxyx()

    # Growing: simple resize is sufficient
    if height >= old_h and width >= old_w:
        self._curses_window.resize(height, width)
        return

    # Shrinking: must replace window to avoid ghost pixels
    # 1. Mark parent area as needing redraw
    if self.master and hasattr(self.master, '_curses_window'):
        parent_win = self.master._curses_window
        if parent_win:
            # Touch the area we're vacating
            parent_win.touchwin()

    # 2. Create new smaller window
    new_window = self._create_subwindow(height, width, self._allocated_y, self._allocated_x)

    # 3. Replace panel's window (handles z-order correctly)
    if self._panel:
        self._panel.replace(new_window)

    # 4. Clean up old window
    old_window = self._curses_window
    self._curses_window = new_window
    self._window = new_window
    del old_window
```

#### Parent Responsibility

When a child widget shrinks, the parent MUST redraw its background in the vacated area:

1. **During layout recalculation**: Parent clears its entire content area
2. **Before child resize**: Parent marks vacated region as dirty
3. **After panel.update_panels()**: Exposed parent background becomes visible

#### Window Destruction (`_destroy_window`)

Called when widget is destroyed or unmapped:

1. Hide panel via `panel.hide()`
2. Remove panel from stack via `PanelStack.remove_panel(panel)`
3. Delete curses window
4. Parent redraws exposed area

### Event Handling Flow

```
User presses key or clicks mouse
           │
           ▼
┌──────────────────────────────────────────┐
│  curses.getch() / curses.getmouse()      │
│  captures terminal input                 │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  InputHandler translates key/mouse event │
│  to tkinter-style event object           │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Find widget at cell coordinates         │
│  (using panel stack for z-ordering)      │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Dispatch to widget's event handler      │
│  (Button invokes command callback)       │
└──────────────────────────────────────────┘
```

### Multi-event sequences

`<Control-x><Control-s>`, `<Key-a><Key-b><Key-c>`, and `"ab"` — which Tk reads
as `<Key-a><Key-b>` — bind and fire (`TkCurses-jfm`). Tk's manual says a
sequence matches when "the recent events … match", with Key and Button events
in between preventing it and the rest ignored. That is **not** how Tk behaves,
in 8.6 or 9.0. The rules were measured with `wish8.6` and `wish9.0` — synthetic
key events with real timestamps, which agree in every case — and then **read
from Tk 9.0.2's `generic/tkBind.c`** (`Tk_BindEvent`, `MatchPatterns`, the
promotion lists, Gregor Cramer's 2018–19 rewrite) to explain the surprising
ones. `_core/bindings.py` follows that code:

- An event that matches a sequence's first pattern **promotes** it, bound to
  the event's window; each event that matches the next pattern promotes it a
  level, and the last one fires it. **There is no timeout**: Ctrl-x, any pause,
  Ctrl-s still fires.
- A waiting sequence is **dropped** by an event of the type it waits for with
  another key or button, or the wrong modifiers; by a Key event while it waits
  for a Button, or the reverse; and by **any event in another window** — a
  resize, an `Expose`, a `<Configure>` on another widget cancels it, measured.
  So a sequence never spans two widgets, even through a class tag both share.
- Everything else leaves it waiting: motion, focus, a release, a lone
  modifier key (curses delivers neither of the last two).
- **The quirk.** An event is tried as a fresh start while the entry it is
  dropping is still listed one level in, and a sequence already listed there is
  not promoted again — so the restart is lost. For `<a><b>`, "a a b" does
  **not** fire and "a a a b" does; for `<Control-x><Control-s>`, Ctrl-x Ctrl-x
  Ctrl-s does nothing. A drop further in is on another list: for `<a><b><c>`,
  "a b a b c" fires. Copied, since both Tks do it and an Emacs-style chord
  reads it as "a wrong second key cancels".

| `<a><b>` | fires | `<a><b><c>` | fires |
|---|---|---|---|
| a b | yes | a b c | yes |
| a a b | **no** | a b a b c | **yes** |
| a a a b | yes | a b b c | no |
| a a a a b | no | a a b c | no |
| b a b | yes | | |

**Ranking** is Tk's `IsBetterMatch`: first the click counts of the patterns
that name a key or button, then every pattern's count weighted, then the last
pattern's modifiers. For single patterns that is the order this engine already
had; it also makes a finished `<Control-x><Control-s>` run **instead of**
`<Control-s>`, and `<Key-a><Key-b>` instead of `<Key><Key-b>`, both measured.

**A pattern fires for a click count of at least its own** — Tk's
`patPtr->count <= count`, and its manual: `<Double-Button-1>` "will match each
button press but the first". This required the count exactly, so a third click
fired nothing bound to a double; ttk Spinbox had a duplicate triple-click
binding to make up for it, now gone.

`event_generate` of a sequence raises **"only one event specification
allowed"**, Tk's words. A **virtual** event defined by a sequence —
`event_add("<<Save>>", "<Control-x><Control-s>")` — is accepted and reported by
`event_info` and **never fires**, as in Tk ("virtual events cannot promote").
A key inside a sequence counts as bound for the terminal's signal keys, so
`<Control-c><Control-c>` gets Control-C delivered as a key. Ctrl-S reaches the
program because the input layer turns flow control (`IXON`) off.

### An event's state, and `event_generate`'s options

**`event.state` is Tk's number**, as tkinter reports `%s`: Shift 1, Control
4, Mod1 8, Button1 to Button5 held 256 to 4096 - so `event.state & 4` is
Control here as there. Internally the modifiers keep their own bits (`MOD_*`
in `_core/events.py`, Control 0x02); `_tk_state` and `_modifiers_of`, in
`__init__.py`, translate at the tkinter boundary, and nothing past it reads
ours. They used to be what `event.state` held, so a tkinter program testing
`& 4` for Control found Alt (`TkCurses-vnmk`).

A key from the terminal reports Alt as Mod1, 8, which is how X11 reports a
real Alt. A generated `<Alt-...>` or `<Meta-...>` reports Tk's own masks,
131072 and 65536 - measured on Tk 9.0.2, `event generate . <Alt-KeyPress-a>`
gives `%s` 131072 - and either, or 8, matches an `<Alt-...>` binding:
measured, `state=8` fires one. Lock and Mod2 to Mod5 have no modifier here;
a `state=` carrying them reports them in `%s` and matches nothing on them.

**`keysym=`, `button=` and `state=` choose the bindings**, as Tk's
`-keysym`, `-button` and `-state` do, each **replacing** what the sequence
said rather than adding to it. Measured on Tk 9.0.2 with all of `<Key>`,
`<Key-Up>`, `<Shift-Key-Up>`, `<Control-Key-Up>`, `<Key-b>`, `<Button-1>`,
`<Button-3>` and `<Shift-Button-1>` bound on one Frame:

| generated | runs | `%s` |
|---|---|---|
| `<KeyPress>`, `keysym='Up', state=1` | `<Shift-Key-Up>` | 1 |
| `<Shift-KeyPress-Up>`, `state=0` | `<Key-Up>` | 0 |
| `<Control-KeyPress-Up>`, `state=1` | `<Shift-Key-Up>` | 1 |
| `<KeyPress-a>`, `keysym='b'` | `<Key-b>` | 0 |
| `<ButtonPress-1>`, `button=3` | `<Button-3>` | 0 |
| `<ButtonPress-1>`, `state=1` | `<Shift-Button-1>` | 1 |

A `state` that is not an integer is refused with Tk's *expected integer but
got "x"*; `"1"` is taken. Ours used to copy the three onto the event and
match on the sequence alone, and refused `button=` outright, so tests built
`<Shift-Key-Up>` by hand where a recorder's `-keysym Up -state 1` would do.

### Focus traversal: Tab, and F6 when Tab is spoken for

Traversal lives on the `all` tag — the last tag consulted — so a widget that
wants a traversal key for itself binds it and returns `"break"`. Four keys are
bound there:

| key | |
|---|---|
| `Tab` | focus the next widget |
| `Shift-Tab` (`ISO_Left_Tab`) | focus the previous one |
| `F6` | focus the next widget |
| `Shift-F6` | focus the previous one |

**tkinter does not put traversal on Tab in a `Text`**: Tk binds `<Tab>` there to
insert a tab and keep the focus, and gives traversal to `<Control-Tab>`. That
split is not available in a terminal, and the reason is worth knowing because it
recurs:

- **Tab, `Control-I` and `Control-Tab` are all the byte `0x09`.** Tk's bindings
  rely on X11 keysyms where the three are distinct events. `_core/input.py`
  already refuses to attach Control to code 9 for exactly this reason.
- The CSI encodings that *would* distinguish them are not parsed. Measured:
  `CSI 27;5;9~` (xterm) arrives as `;`, `9`, `~` and `CSI 9;5u` (kitty) as `;`,
  `5`, `u` — so on a terminal with `modifyOtherKeys` or the kitty protocol
  enabled, Control-Tab in a `Text` would type into the document. `TkCurses-99j`
  is the work to parse them.

So `F6` is the escape, with `Shift-F6` to go back, which lets an editor keep Tab
for indentation without trapping a keyboard-only user. The choice is constrained
from three sides:

- **Alt-arrows are out**: i3 and sway bind `Mod1+Left`/`Mod1+Right` to window
  focus by default, so the window manager consumes them first.
- **`Alt-F6` is out**: GNOME reserves it, and `Shift-Alt-F6`, for cycling an
  application's own windows. Hence *plain* F6 and Shift-F6.
- **`F6` is conventional** for "next pane" in GTK and GNOME, and it survives the
  journey — `kf6=\E[17~` arrives as `F6`.

`Shift-F6` is bound as **`<Key-F18>`** as well as `<Shift-Key-F6>`, and the first
is what actually fires: terminfo encodes shifted F1–F12 as F13–F24, so a
terminal whose `kf18` is `\E[17;2~` reports Shift-F6 as a key named `F18` with
no shift bit. `TkCurses-87e`.

#### The rule for a widget that takes a traversal key

**Never consume every way out.** A widget may claim any of the four — an editor
claiming `Tab` for indentation is the reason the other pair exists — but it must
leave at least one route to the next widget, because a terminal application has
no title bar to click out of and may have no mouse at all. Two keys are claimable
and two are the escape; taking both pairs strands the keyboard.

In practice:

```python
# Fine: Tab is spoken for, F6 still traverses.
editor.bind("<Key-Tab>", lambda event: (editor.insert("insert", "\t"), "break")[1])
```

Binding on the widget or its class is what makes this work — traversal is on
`all`, the last tag consulted, so a nearer binding that returns `"break"` wins
without unbinding anything. Returning `"break"` is the whole mechanism: without
it the event continues to `all` and the focus moves as well.

The same obligation applies to a composite widget that forwards keys to a child,
and to any future widget that wants `F6` for itself: claim it, and say in the
widget's own docstring which key still leaves.

**Moving the focus sends `<<TraverseOut>>` and `<<TraverseIn>>`**, as
`tk::TabToWindow` does: the first to the widget being left, the second to
the one reached, after the focus has moved. Tab, Shift-Tab, F6 and Shift-F6
all go through `_move_focus`, so all four send them; `focus_set()` and a
click do not, in Tk or here. What uses them, measured on Tk 9.0 with
`bind_class`: Entry, Spinbox, TEntry and TSpinbox bind `<<TraverseIn>>` to
select everything and put the cursor at the end, so typing replaces what was
there; TCombobox does the same unless it is readonly or disabled
(`ttk::combobox::TraverseIn`). Nothing binds `<<TraverseOut>>`. Before
`TkCurses-h0bj` neither event was sent, and Tab into a filled field left the
cursor where it was, so typing went in front of the old text.

### Input Handling Architecture

Curses input handling requires careful design to capture all events without blocking the application or consuming excessive CPU.

#### Design Challenges

1. **Blocking vs Non-blocking**: `getch()` blocks by default, freezing the event loop
2. **CPU Spinning**: `nodelay(True)` returns immediately but spins at 100% CPU
3. **Mouse Events**: Must be explicitly enabled and decoded
4. **Special Keys**: Function keys, arrows, etc. require `keypad(True)`
5. **Resize Events**: Terminal resize must be detected and handled

#### Solution: Select-Based Event Loop

Use `select.select()` to wait for input with timeout, enabling efficient idle waiting:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Main Event Loop                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  select.select([stdin], [], [], timeout)                         │
│  - Waits efficiently for input (no CPU spin)                     │
│  - Returns when input available OR timeout expires               │
│  - Timeout allows processing after() callbacks                   │
└─────────────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
┌──────────────────────────┐        ┌──────────────────────────┐
│  Input Available         │        │  Timeout (no input)      │
│  - Call getch()          │        │  - Process after() queue │
│  - Handle KEY_MOUSE      │        │  - Process dispatcher    │
│  - Handle KEY_RESIZE     │        │  - Refresh if needed     │
│  - Dispatch to widgets   │        │  - Loop back to select   │
└──────────────────────────┘        └──────────────────────────┘
```

#### Input faster than it is handled

A terminal can send faster than a program handles what it sends: a mouse
dragged over a large screen, a long paste. Three things keep that from
stopping everything else (security review, `TkCurses-tcbj.21`), each measured
in a pseudo-terminal before and after:

- **A pass reads at most `_INPUT_BATCH` (256) events.** `poll()` used to
  read until curses had nothing left, so a flood held the loop in input for
  as long as it lasted: 200,000 drag reports in three seconds ran a 10 ms
  timer **once**, and a key sent after them waited 4.3 s. Now 256 ticks,
  and 0.05 s. When a read stops at the limit the next pass reads again
  without waiting, since what is left may be inside ncurses' own buffer,
  where `select()` cannot see it.
- **A run of motion in one window arrives as its last report**, as in Tk:
  `Tk_QueueWindowEvent` (`tkEvent.c`, Tk 9.0) holds a `MotionNotify` back,
  replaces it with the next one *in the same window*, and sends it on
  before any other event. The window is the widget under the pointer, or
  under a drag the one pressed. A change of modifiers also ends a run,
  standing in for the key event X would put between them. Handler calls in
  the flood above went from 200,000 to 766.
- **A Text repaints once before the screen is shown**, not on each edit.
  Every key used to repaint it twice - the edit, then `see("insert")` - and
  a repaint costs the length of the lines in view: 1000 characters typed
  onto one line took 3.8 s, and 2,001 paints. Tk does the same thing for
  the same reason: `TextChanged` (`tkTextDisp.c`) sets `REDRAW_PENDING`
  and schedules `DisplayText` with `Tcl_DoWhenIdle`. The widget is put in
  `tk.repaint_due`, which `Tk._update_display` empties first; the
  terminal's cursor, which painting places, is read after that. 1000
  characters now take 0.36 s and three paints. What is left is the layout
  of the line, which `see` still works out on every key.

#### InputHandler Implementation

```python
import select
import sys
import curses

class InputHandler:
    """Handles all keyboard and mouse input for TkCurses."""

    def __init__(self, stdscr: curses.window) -> None:
        self._stdscr = stdscr
        self._setup_input()

    def _setup_input(self) -> None:
        """Configure curses for comprehensive input capture."""
        # Enable keypad mode for special keys (arrows, F1-F12, etc.)
        self._stdscr.keypad(True)

        # Enable all mouse events
        curses.mousemask(
            curses.ALL_MOUSE_EVENTS |
            curses.REPORT_MOUSE_POSITION
        )

        # Don't echo input characters
        curses.noecho()

        # React to keys immediately (no line buffering)
        curses.cbreak()

        # Make getch() non-blocking (we use select for waiting)
        self._stdscr.nodelay(True)

    def wait_for_input(self, timeout_ms: int = 50) -> bool:
        """
        Wait for input efficiently without CPU spinning.

        Args:
            timeout_ms: Max wait time in milliseconds

        Returns:
            True if input is available, False if timeout
        """
        timeout_sec = timeout_ms / 1000.0
        readable, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        return bool(readable)

    def get_event(self) -> 'Event | None':
        """
        Get next input event (non-blocking).

        Returns:
            Event object or None if no input available
        """
        ch = self._stdscr.getch()

        if ch == curses.ERR:
            return None  # No input available

        if ch == curses.KEY_MOUSE:
            return self._handle_mouse()

        if ch == curses.KEY_RESIZE:
            return self._handle_resize()

        return self._handle_key(ch)

    # Drag state tracking
    _drag_button: int = 0         # Currently pressed button (0 = none)
    _drag_start: tuple[int, int] = (0, 0)  # Drag start position

    def _handle_mouse(self) -> 'MouseEvent | list[MouseEvent]':
        """Decode mouse event from curses with full state tracking."""
        try:
            id_, x, y, z, bstate = curses.getmouse()
        except curses.error:
            return None

        events = []
        modifiers = self._decode_modifiers(bstate)

        # Check each button for all possible states
        for button in range(1, 6):
            event = self._decode_button_event(button, bstate, x, y, modifiers)
            if event:
                events.append(event)

        # Handle motion during drag
        if not events and self._drag_button != 0:
            events.append(MouseEvent(
                x=x, y=y,
                button=self._drag_button,
                state='drag',
                drag_start=self._drag_start,
                modifiers=modifiers,
            ))

        # Handle pure motion (no button pressed)
        if not events and bstate & curses.REPORT_MOUSE_POSITION:
            events.append(MouseEvent(
                x=x, y=y,
                button=0,
                state='motion',
                modifiers=modifiers,
            ))

        return events[0] if len(events) == 1 else events if events else None

    def _decode_button_event(
        self, button: int, bstate: int, x: int, y: int, modifiers: int
    ) -> 'MouseEvent | None':
        """Decode event for a specific button."""
        # Button mask constants (curses defines BUTTON1-5)
        BUTTON_MASKS = {
            1: {
                'pressed': curses.BUTTON1_PRESSED,
                'released': curses.BUTTON1_RELEASED,
                'clicked': curses.BUTTON1_CLICKED,
                'double': curses.BUTTON1_DOUBLE_CLICKED,
                'triple': curses.BUTTON1_TRIPLE_CLICKED,
            },
            2: {
                'pressed': curses.BUTTON2_PRESSED,
                'released': curses.BUTTON2_RELEASED,
                'clicked': curses.BUTTON2_CLICKED,
                'double': curses.BUTTON2_DOUBLE_CLICKED,
                'triple': curses.BUTTON2_TRIPLE_CLICKED,
            },
            3: {
                'pressed': curses.BUTTON3_PRESSED,
                'released': curses.BUTTON3_RELEASED,
                'clicked': curses.BUTTON3_CLICKED,
                'double': curses.BUTTON3_DOUBLE_CLICKED,
                'triple': curses.BUTTON3_TRIPLE_CLICKED,
            },
            4: {
                'pressed': curses.BUTTON4_PRESSED,
                'released': curses.BUTTON4_RELEASED,
                'clicked': curses.BUTTON4_CLICKED,
                'double': curses.BUTTON4_DOUBLE_CLICKED,
                'triple': curses.BUTTON4_TRIPLE_CLICKED,
            },
            # Button 5 may not be available on all platforms
            5: {
                'pressed': getattr(curses, 'BUTTON5_PRESSED', 0),
                'released': getattr(curses, 'BUTTON5_RELEASED', 0),
                'clicked': getattr(curses, 'BUTTON5_CLICKED', 0),
                'double': getattr(curses, 'BUTTON5_DOUBLE_CLICKED', 0),
                'triple': getattr(curses, 'BUTTON5_TRIPLE_CLICKED', 0),
            },
        }

        masks = BUTTON_MASKS.get(button, {})

        # Check each state in priority order
        for state, mask in masks.items():
            if mask and (bstate & mask):
                event = MouseEvent(
                    x=x, y=y,
                    button=button,
                    state=state,
                    modifiers=modifiers,
                )

                # Track drag state
                if state == 'pressed':
                    self._drag_button = button
                    self._drag_start = (x, y)
                    event.drag_start = self._drag_start
                elif state == 'released':
                    if self._drag_button == button:
                        event.drag_start = self._drag_start
                        event.drag_end = (x, y)
                        self._drag_button = 0

                return event

        return None

    def _decode_modifiers(self, bstate: int) -> int:
        """Extract modifier keys from mouse state."""
        modifiers = 0
        if bstate & curses.BUTTON_SHIFT:
            modifiers |= MOD_SHIFT
        if bstate & curses.BUTTON_CTRL:
            modifiers |= MOD_CTRL
        if bstate & curses.BUTTON_ALT:
            modifiers |= MOD_ALT
        return modifiers

    def _handle_resize(self) -> 'ResizeEvent':
        """Handle terminal resize."""
        curses.update_lines_cols()
        return ResizeEvent(
            width=curses.COLS,
            height=curses.LINES,
        )

    def _handle_key(self, ch: int) -> 'KeyEvent':
        """Translate key code to KeyEvent."""
        return KeyEvent(
            keycode=ch,
            keysym=self._keycode_to_keysym(ch),
            char=chr(ch) if 32 <= ch <= 126 else '',
            modifiers=self._detect_key_modifiers(ch),
        )

    def _detect_key_modifiers(self, ch: int) -> int:
        """Detect modifier keys from key code."""
        modifiers = 0
        # Ctrl+key produces codes 1-26 (Ctrl+A=1, Ctrl+Z=26)
        if 1 <= ch <= 26:
            modifiers |= MOD_CTRL
        # Alt+key often produces escape sequence (handled separately)
        return modifiers

    def _keycode_to_keysym(self, ch: int) -> str:
        """Map curses key code to tkinter-style keysym."""
        KEY_MAP = {
            curses.KEY_UP: 'Up',
            curses.KEY_DOWN: 'Down',
            curses.KEY_LEFT: 'Left',
            curses.KEY_RIGHT: 'Right',
            curses.KEY_HOME: 'Home',
            curses.KEY_END: 'End',
            curses.KEY_PPAGE: 'Prior',      # Page Up
            curses.KEY_NPAGE: 'Next',       # Page Down
            curses.KEY_IC: 'Insert',
            curses.KEY_DC: 'Delete',
            curses.KEY_BACKSPACE: 'BackSpace',
            curses.KEY_ENTER: 'Return',
            10: 'Return',                    # Enter key
            13: 'Return',                    # Carriage return
            27: 'Escape',
            9: 'Tab',
            curses.KEY_BTAB: 'Shift-Tab',
            curses.KEY_F1: 'F1',
            curses.KEY_F2: 'F2',
            curses.KEY_F3: 'F3',
            curses.KEY_F4: 'F4',
            curses.KEY_F5: 'F5',
            curses.KEY_F6: 'F6',
            curses.KEY_F7: 'F7',
            curses.KEY_F8: 'F8',
            curses.KEY_F9: 'F9',
            curses.KEY_F10: 'F10',
            curses.KEY_F11: 'F11',
            curses.KEY_F12: 'F12',
        }
        return KEY_MAP.get(ch, chr(ch) if 32 <= ch <= 126 else f'keycode-{ch}')
```

**One `KEY_MOUSE` can stand for several reports, and all of them are read.**
The sketch above calls `getmouse()` once, and so did the code until
`TkCurses-3uki`. When a press and its release reach the program in one read
(over ssh or tmux, from a quick tap, or from a test harness writing both at
once), ncurses parses both into its own event queue but `getch()` returns
`KEY_MOUSE` only once. The second report then waited, invisible to
`select()`, until the next bytes arrived, and every click after it was one
event behind. Measured on ncurses 6.6 with a bare curses program, no
TkCurses: press and release written together gave one `KEY_MOUSE`, and a
second `getmouse()` straight after returned the release. Three such clicks
on a Button counted 0. `_read_mouse` now drains the queue until `getmouse()`
raises, at most `_MOUSE_QUEUE` (8, ncurses' `EV_MAX`) times, so a
`getmouse()` that never runs dry cannot hold the loop.

#### Alt from a terminal

**A key read straight after an Escape is that key with Alt.** A terminal
sends Alt-e as Escape and then `e`, and ncurses, after waiting `ESCDELAY`
(25 ms here) for a sequence it knows, hands back both - 27, then the `e`
already in its buffer. `InputHandler.poll` reads them as the one key Tk on
X11 reports for Alt-e: keysym `e`, Alt held. An Escape pressed on its own
has nothing behind it and stays Escape; a mouse report or a resize after one
is never Alt. Until `TkCurses-r3og` the two were delivered separately, so no
`<Alt-...>` binding could fire from a real terminal, the menu bar's Alt
letters could not work, and Text's Alt-z redo was bound as the sequence
`<Escape><z>` instead. One cost: a sequence ncurses does not know - an arrow
key in the other cursor mode, say - now arrives as Alt with its first
character, then the rest, where it arrived as Escape and then the rest;
Escape closed whatever dialog or menu was open, Alt with `[` or `O` does
nothing.

#### Characters beyond ASCII

**`getch()` hands a UTF-8 character over a byte at a time**, é as 195
then 169, and `InputHandler._read_char` puts them back together into one
key. Until `TkCurses-w9kd` each byte was a key with no character, so
nothing outside ASCII could be typed into an Entry or a Text at all. The
rest of a character split across reads is waited for for 50 ms, as a late
reply's is. Bytes that make no character - a continuation byte on its own,
a sequence cut short, an overlong form, a surrogate - are given back and
read as the keys with no character they always were. `get_wch()` would
decode for us, but it is a second read path for every key, mouse report
and resize, for the sake of a few lines.

**The keysym is the character itself**, which is what Tk 9.0.2 does and
its manual does not say. Measured by binding names and reading `bind`
back: `<Key-eacute>`, `<Key-U00E9>` and `<Key-é>` all read back as
`<Key-é>`; `<Key-U754C>` as `<Key-界>`; `<Key-EuroSign>` as `<Key-€>`;
`<Key-U0041>` as `A` - the same thing Tk does with `period` and `.`. The
exceptions are the characters that do not print: no-break space stays
`nobreakspace`, and the soft hyphen, X11's `hyphen`, comes back as
`U00AD`. So `canonical_keysym` resolves every Latin-1 name, X11's later
spellings of some of them (`guillemetleft`, `ordmasculine`, `Ooblique`),
`EuroSign` and any `U` + hex to the character, and a binding written any
of those ways meets the typed key. What `event.keysym` is for a key
actually typed under Tk could not be read on the machine measured - an
XWayland display, where `event_generate` with a non-ASCII keysym delivers
`??` - and is taken to be the stored form, as it is for ASCII.
`keysym_num` follows X11: Latin-1 is its code point, anything else its code
point plus 0x1000000.

One difference kept on purpose: a bare `é` as a sequence. Through tkinter,
Tk 9.0.2 stores it as `<Key-Ã><Key-©>`, two keys, one per byte of its
UTF-8, which nothing typed can match. Here it is the one key.

**An Entry or a Text takes any typed character but a control one.** Read
from Tk 9.0.2's scripts, since `event_generate` cannot type these on the
machine measured: `tk::EntryInsert`, `ttk::entry::Insert` and
`tk::TextInsert` insert any `%A` that is not empty, and what keeps Escape,
Return or a Control key out is the class binding of each to `# nothing`.
Until `TkCurses-m5jx` the handlers here asked `str.isprintable()`, which
refuses a no-break space, a soft hyphen and every format character, so
none of them could be typed. They now refuse only C0, DEL and C1. The two
that are typed on purpose draw as what they look like, a space and a
hyphen; any other space draws as spaces.

**What is drawn for a character that does not print is as wide as it is
measured**, by `char_cells`, because the cursor, `bbox`, clipping and a
click are all measured that way. A zero-width format character - a
zero-width space or joiner, a direction mark, a byte-order mark - is drawn
as nothing. It used to be a `?`, one cell: an Entry holding a zero-width
space put its cursor on the last character instead of after it
(`TkCurses-sv3s`). It is not given to the terminal either: a joiner would
make one glyph of two emoji measured as two, and a direction override can
reorder the row. A control character is still a `?`, visible on purpose.

#### Bracketed paste, and handing the terminal back on Ctrl-Z

**A paste is asked to be marked**: `ESC [ ? 2004 h` at start-up, unless
`[input] bracketed_paste` is off, and the terminal then wraps what is
pasted in `ESC [ 200 ~` and `ESC [ 201 ~`. ncurses knows neither, and
hands each over as its bytes; `InputHandler.poll` reads the start marker
after an Escape the way it reads a late reply, and everything to the end
marker becomes one `PasteEvent` - at most 16 MiB of it kept, the rest read
and dropped so that it is not typed, and ended unfinished after half a
second with nothing. Anything ncurses decoded inside a paste is not text:
a resize or mouse report is delivered after it, any other key code
dropped.

**A paste is `<<TerminalPaste>>` to the focus**, through any grab, with
the text in `event.data` - Tk's `%d`, which tkinter's Event lacks and this
one has. Tk has nothing to follow: an X11 paste is a selection a widget
asks for, never keystrokes, so the rules were chosen, with the user, on
`TkCurses-tcbj.22`:

- **Text** replaces the selection and inserts at the insert mark, as its
  `<<Paste>>` does here, all as one undo step - autoseparators held off
  between the delete and the insert, a separator either side, as
  `tk::TextInsert` groups typing over a selection. Line breaks become
  newlines (a terminal sends `\r`; `\r\n` is one break), tabs stay, every
  other control character - C0, DEL and C1 - goes. No auto-indent, no
  Return binding: the text goes in as it was copied. A disabled Text
  takes none of it and its marks stay where they were.
- **The entry family** - Entry, Spinbox, and ttk's Entry, Spinbox and
  Combobox, which all install `_bind_entry_clipboard` - takes it as one
  line: each line break a space, every control gone. The selection is
  replaced and the paste inserted as **one** edit, so a validator is
  called once, with `%d` 1, `%i` where it starts, `%S` the pasted text and
  `%P` the result; the cursor ends after it.
- **Anything else**, with no `<<TerminalPaste>>` binding on any of its
  tags, gets the paste as the keys it would have been, less every control
  character. Removing them is the point: a dialog's focused default
  button bound to Return would otherwise be pressed by a pasted line
  break, and Escape would close it.

**Ctrl-Z is answered by the loop, not by ncurses.** ncurses' own SIGTSTP
handler runs `endwin()` inside the signal and, measured, sends only what
ncurses itself set: `ESC [ ? 1006 ; 1000 l` going, `ESC [ ? 1006 ; 1000 h`
coming back. The motion mode, 1002, which this library sets past ncurses
(see `_enable_motion`), stayed on in the shell, and the return's 1000
replaced it, so after `fg` the mouse clicked but never dragged; 2004
would have stayed on in the shell too. So `Tk` takes SIGTSTP while it
holds the screen - only from the main thread, and only when the handler
there is ncurses' or the default, never a program's own - and the handler
only notes it, as SIGINT's does. Between passes the loop turns both modes
off and gives the tty its own keys back (`InputHandler.pause`), calls
`endwin()`, and stops with the default action; on `fg` it lays the screen
out again at whatever size the terminal now is and sets the modes and
keys again (`resume`). The tty's keys need it because ncurses' return
sets back the terminal state it saved at `initscr()`, from before the
input handler took Control-S and Control-Q.

The pty harness cannot send a real Ctrl-Z to its child: the child leads an
orphaned process group, and the kernel drops a terminal's stop signals to
one. `test_bracketed_paste_tty.py` runs the program under `bash -i`, which
has job control, for the real thing.

#### Modifier Constants

```python
# Modifier key flags (combinable with bitwise OR)
MOD_SHIFT = 0x01
MOD_CTRL  = 0x02
MOD_ALT   = 0x04
MOD_META  = 0x08  # Command key on macOS
```

#### Event Classes

```python
@dataclass
class Event:
    """Base class for all events."""
    type: str
    time: float = field(default_factory=time.time)

@dataclass
class KeyEvent(Event):
    """Keyboard event."""
    type: str = 'key'
    keycode: int = 0          # Raw curses key code
    keysym: str = ''          # Tkinter-style key symbol
    char: str = ''            # Printable character (if any)
    modifiers: int = 0        # Ctrl, Alt, Shift flags

@dataclass
class MouseEvent(Event):
    """Mouse event with full drag support."""
    type: str = 'mouse'
    x: int = 0                # Current column
    y: int = 0                # Current row
    button: int = 0           # 1=left, 2=middle, 3=right, 4=scroll-up, 5=scroll-down
    state: str = 'pressed'    # See MouseState below
    modifiers: int = 0        # Shift, Ctrl, Alt flags
    drag_start: tuple[int, int] | None = None  # (x, y) where drag began
    drag_end: tuple[int, int] | None = None    # (x, y) where drag ended (on release)

@dataclass
class ResizeEvent(Event):
    """Terminal resize event."""
    type: str = 'resize'
    width: int = 0            # New column count
    height: int = 0           # New row count
```

#### Mouse Event States

| State | Description | Curses Source |
|-------|-------------|---------------|
| `pressed` | Button just pressed down | `BUTTONn_PRESSED` |
| `released` | Button just released | `BUTTONn_RELEASED` |
| `clicked` | Quick press and release | `BUTTONn_CLICKED` |
| `double` | Double-click detected | `BUTTONn_DOUBLE_CLICKED` |
| `triple` | Triple-click detected | `BUTTONn_TRIPLE_CLICKED` |
| `drag` | Motion with button held | `REPORT_MOUSE_POSITION` + tracked button |
| `motion` | Motion without button | `REPORT_MOUSE_POSITION` |

#### Drag Event Sequence

A complete drag operation produces this event sequence:

```
1. MouseEvent(state='pressed', button=1, x=10, y=5, drag_start=(10, 5))
   └── User presses left button at (10, 5)

2. MouseEvent(state='drag', button=1, x=15, y=5, drag_start=(10, 5))
   └── User moves mouse while holding button

3. MouseEvent(state='drag', button=1, x=20, y=8, drag_start=(10, 5))
   └── Continued motion...

4. MouseEvent(state='released', button=1, x=25, y=10, drag_start=(10, 5), drag_end=(25, 10))
   └── User releases button, drag_end captured
```

#### Tkinter Event Translation

MouseEvent maps to tkinter event types:

| TkCurses State | tkinter Event Type |
|----------------|-------------------|
| `pressed` | `<ButtonPress-n>` or `<Button-n>` |
| `released` | `<ButtonRelease-n>` |
| `clicked` | `<Button-n>` (synthetic) |
| `double` | `<Double-Button-n>` |
| `triple` | `<Triple-Button-n>` |
| `drag` | `<B1-Motion>`, `<B2-Motion>`, `<B3-Motion>` |
| `motion` | `<Motion>` |

With modifiers:
- `<Shift-Button-1>` → `state='pressed', button=1, modifiers=MOD_SHIFT`
- `<Control-B1-Motion>` → `state='drag', button=1, modifiers=MOD_CTRL`
- `<Alt-ButtonRelease-3>` → `state='released', button=3, modifiers=MOD_ALT`

#### Main Loop Integration

```python
class Tk:
    """Main application class."""

    def mainloop(self) -> None:
        """Run the main event loop."""
        self._running = True
        input_handler = InputHandler(self._stdscr)
        dispatcher = CursesDispatcher.get()

        while self._running:
            # Wait for input efficiently (no CPU spin)
            if input_handler.wait_for_input(timeout_ms=50):
                # Process all available input
                while True:
                    event = input_handler.get_event()
                    if event is None:
                        break
                    self._dispatch_event(event)

            # Process scheduled callbacks (after())
            self._process_after_queue()

            # Process cross-thread curses calls
            dispatcher.process_queue()

            # Refresh screen if needed
            self._refresh_if_dirty()
```

#### Mouse Event Masks

Full mouse support requires enabling all event types:

| Constant | Value | Description |
|----------|-------|-------------|
| **Button 1 (Left)** | | |
| `BUTTON1_PRESSED` | 0x02 | Left button pressed down |
| `BUTTON1_RELEASED` | 0x01 | Left button released |
| `BUTTON1_CLICKED` | 0x04 | Left button click (press+release) |
| `BUTTON1_DOUBLE_CLICKED` | 0x08 | Left button double-click |
| `BUTTON1_TRIPLE_CLICKED` | 0x10 | Left button triple-click |
| **Button 2 (Middle)** | | |
| `BUTTON2_PRESSED` | 0x80 | Middle button pressed |
| `BUTTON2_RELEASED` | 0x40 | Middle button released |
| `BUTTON2_CLICKED` | 0x100 | Middle button click |
| `BUTTON2_DOUBLE_CLICKED` | 0x200 | Middle button double-click |
| `BUTTON2_TRIPLE_CLICKED` | 0x400 | Middle button triple-click |
| **Button 3 (Right)** | | |
| `BUTTON3_PRESSED` | 0x2000 | Right button pressed |
| `BUTTON3_RELEASED` | 0x1000 | Right button released |
| `BUTTON3_CLICKED` | 0x4000 | Right button click |
| `BUTTON3_DOUBLE_CLICKED` | 0x8000 | Right button double-click |
| `BUTTON3_TRIPLE_CLICKED` | 0x10000 | Right button triple-click |
| **Button 4 (Scroll Up)** | | |
| `BUTTON4_PRESSED` | 0x80000 | Scroll up pressed |
| `BUTTON4_RELEASED` | 0x40000 | Scroll up released |
| `BUTTON4_CLICKED` | 0x100000 | Scroll up click |
| `BUTTON4_DOUBLE_CLICKED` | 0x200000 | Scroll up double-click |
| `BUTTON4_TRIPLE_CLICKED` | 0x400000 | Scroll up triple-click |
| **Button 5 (Scroll Down)** | | Platform-dependent |
| `BUTTON5_PRESSED` | varies | Scroll down pressed |
| `BUTTON5_RELEASED` | varies | Scroll down released |
| `BUTTON5_CLICKED` | varies | Scroll down click |
| **Modifiers** | | |
| `BUTTON_SHIFT` | 0x4 | Shift key held during mouse event |
| `BUTTON_CTRL` | 0x2 | Ctrl key held during mouse event |
| `BUTTON_ALT` | 0x1 | Alt key held during mouse event |
| **Special** | | |
| `REPORT_MOUSE_POSITION` | 0x8000000 | Report all mouse motion |
| `ALL_MOUSE_EVENTS` | 0x7ffffff | Enable all mouse events |

#### Mouse Mask Initialization

```python
def _setup_mouse(self) -> None:
    """Enable comprehensive mouse event capture."""
    # Enable all mouse events including motion for drag support
    available, _ = curses.mousemask(
        curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION
    )

    if not available:
        # Fallback: try without motion reporting
        available, _ = curses.mousemask(curses.ALL_MOUSE_EVENTS)

    # Configure click timing (see Mouse Click Timing section)
    curses.mouseinterval(self._mouse_click_interval)

    # Log available mouse support
    self._mouse_available = bool(available)
```

#### Mouse Click Timing

**Critical:** Unlike GUI toolkits, curses does not inherit system-wide double-click timing. The `curses.mouseinterval()` function controls the maximum time (in milliseconds) between clicks for them to be recognized as double or triple clicks.

##### Configuration

```python
class MouseConfig:
    """Mouse behavior configuration."""

    # Time window for multi-click detection (milliseconds)
    # curses.mouseinterval() uses this value
    click_interval: int = 200

    # Recommended ranges:
    #   100-150ms: Fast, responsive (may miss double-clicks)
    #   200-300ms: Balanced (default recommendation)
    #   300-500ms: Accessible (easier double-click, feels sluggish)

class Tk:
    """Main application with configurable mouse timing."""

    # Default click interval (milliseconds)
    _mouse_click_interval: int = 200

    def configure_mouse(self, click_interval: int | None = None) -> None:
        """
        Configure mouse behavior.

        Args:
            click_interval: Max milliseconds between clicks for
                           double/triple click detection (1-1000).
                           None to query current value.

        Returns:
            Current interval if click_interval is None.

        Example:
            app = tkcurses.Tk()
            app.configure_mouse(click_interval=300)  # Slower double-click
        """
        if click_interval is not None:
            # Validate range
            click_interval = max(1, min(1000, click_interval))
            self._mouse_click_interval = click_interval
            # Apply to curses immediately
            curses.mouseinterval(click_interval)
        return self._mouse_click_interval
```

##### How mouseinterval() Works

```
Click 1          Click 2          Click 3
   │                │                │
   ▼                ▼                ▼
───●────────────────●────────────────●───────────────► time
   │◄── interval ──►│◄── interval ──►│

If Click 2 arrives within `interval` ms of Click 1:
  → BUTTON1_DOUBLE_CLICKED event generated

If Click 3 arrives within `interval` ms of Click 2:
  → BUTTON1_TRIPLE_CLICKED event generated

If clicks are too far apart:
  → Separate BUTTON1_CLICKED events generated
```

##### Timing Behavior

| Interval (ms) | Double-Click Window | User Experience |
|---------------|---------------------|-----------------|
| 100 | Very tight | Fast users only, may miss double-clicks |
| 150 | Tight | Responsive, requires quick clicking |
| 200 | **Default** | Balanced for most users |
| 300 | Relaxed | Easier double-click, slight delay feel |
| 400 | Wide | Accessible, noticeable delay |
| 500+ | Very wide | Maximum accessibility, sluggish feel |

##### Querying Current Interval

**Not possible.** Python's `curses.mouseinterval()` returns `None`; unlike the
C API it wraps, it discards the previous interval. Verified against ncurses on
Python 3.14: `mouseinterval(300)`, `mouseinterval(-1)` and a second
`mouseinterval(-1)` all return `None`.

There is therefore no read-then-restore pattern to follow, and no way to
recover the value curses is holding. TkCurses tracks the interval itself, in
`InputHandler.click_interval`, which is the only readable source of truth.

Note that `mouseinterval(0)` disables multi-click detection entirely, so it
must not be used as a query.

---

## Runtime Configuration

TkCurses uses Python's standard INI file format (via `configparser`) for runtime configuration, with system-wide defaults and user-level overrides.

### Configuration Hierarchy

Settings are loaded in order, with later sources overriding earlier ones:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Built-in Defaults (hardcoded in TkCurses)                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. System-wide Config File (/etc/tkcurses/tkcurses.ini)        │
│     - Set by system administrator                                │
│     - Applies to all users on the system                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. User Config File (~/.config/tkcurses/tkcurses.ini)          │
│     - Personal preferences                                       │
│     - Overrides system-wide settings                             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Environment Variables (TKCURSES_*)                          │
│     - Temporary overrides for testing/debugging                  │
│     - Highest priority                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Config File Locations

| Platform | System-wide | User Override |
|----------|-------------|---------------|
| Linux | `/etc/tkcurses/tkcurses.ini` | `$HOME/.config/tkcurses/tkcurses.ini` |
| macOS | `/etc/tkcurses/tkcurses.ini` | `$HOME/.config/tkcurses/tkcurses.ini` |
| FreeBSD | `/etc/tkcurses/tkcurses.ini` | `$HOME/.config/tkcurses/tkcurses.ini` |
| Windows | `%PROGRAMDATA%\tkcurses\tkcurses.ini` | `%LOCALAPPDATA%\tkcurses\tkcurses.ini` |

### Config File Format

```ini
; tkcurses.ini - every setting, at its default.
; Lines starting with ; or # are comments.

[mouse]
; Ask the terminal for the mouse at all. Off leaves it to the terminal,
; whose own selection then works without Shift.
enabled = true
; Double/triple click window, milliseconds. Range 1-1000.
click_interval = 200
; Drags (DEC 1002), and every movement (1003).
report_motion = true
report_hover = false

[display]
; auto, 8, 16, 256 or truecolor. A number is a ceiling; see below.
color_mode = auto
; false draws boxes, arrows and bars in ASCII.
unicode_borders = true
; false sends pictures through curses' colour pairs.
direct_images = true

[input]
; How long to wait after ESC for the rest of a sequence. Range 0-1000.
escape_delay = 25

[clipboard]
; auto, osc52, command or off.
system = auto
; Set the desktop's primary selection, for middle-click paste elsewhere.
primary = true
```

### Configuration Implementation

`_core/config.py` holds the settings as dataclasses and one table,
`SETTINGS`, with a `Setting` row per setting: section, key, kind,
environment variable, range or allowed values, and description. The INI
reader, the environment reader and validation all walk it, so they cannot
disagree. `Tk._start` loads it once and hands each setting to the piece it
governs. A value that cannot be parsed falls back to its default and a
number out of range is clamped, each recorded in `warnings`, because
configuration is read before there is a screen to complain on.

**One parser, two policies.** `Setting.parse` is strict: it returns the
value or raises `InvalidValue`, or `OutOfRange` carrying the clamped number.
The loader is the lenient policy, built by catching those - clamp, or keep
the earlier source's value - and `tkcurses-cfg` is the strict one, refusing
what `parse` refuses. A property test (`tests/test_core_config.py`) holds
the two together over arbitrary text, so the command can never call a value
valid that a program would change, or the reverse (`TkCurses-kge7.1`). A
whole number is `[+-]?[0-9]+` and no wider: `int()` also takes `1_000` and
digits from other scripts, which a config file almost certainly means as a
mistake. Those were accepted before `TkCurses-kge7.1` and now warn.

**`TkCursesConfig.origins` records every source's say**, per setting: the
default first, then each file and the environment in the order read, each
an `Origin` with the raw text, the value it gave (or `None` when the text
was refused) and the problem if any. `source(name)` is the last one that
applied. It is what `tkcurses-cfg` shows as a setting's source chain, and it
is filled by the same `load()` a program runs, so the command describes what
a program would do rather than re-deriving it. It is left out of equality:
two configurations with the same values are equal however they got them.

**Each `Setting`'s description is user-facing text**: the configuration
reference (`docs/reference/configuration.md`) is generated from `SETTINGS`,
the dataclass defaults and `REMOVED` by `docs/_ext/configref.py`, so it
cannot list a setting the code lacks or miss one it has; `tkcurses-cfg`
shows the same text. Notes for whoever maintains a setting go in plain `#`
comments beside its dataclass field. `tests/test_configref.py` wants every
setting described in whole sentences with no tracker IDs or private names.
The descriptions were `#:` comments on the dataclass fields until
`TkCurses-kge7.1`, which a running program could not read.

**Files are read without interpolation.** With `configparser`'s default,
a `%` anywhere in a value raised `InterpolationSyntaxError` from `get()`,
outside the loader's `try`, and the program did not start - the one way a
configuration file could stop one, against the rule above. No setting has a
use for `%(name)s`. `TkCurses-kge7.2`.

**`tkcurses-cfg` edits a file as its lines** (`_cfg/inifile.py`), because
`configparser` writes back a dictionary and drops every comment. Its grammar
is a strict subset of `configparser`'s, chosen so a file it accepts is one a
program reads identically, and a property test holds that against
`configparser` itself over generated files on every Python CI runs
(`tests/test_cfg_inifile.py`). Where `configparser` is lenient in ways that
surprise, the editor refuses the file and names the line instead:

- **an indented line after a setting continues that setting's value** - in
  `configparser` a deeper indent, even after blank lines, is a
  continuation, so `  [display]` under an option is not a section;
- **`[DEFAULT]`'s keys appear in every section that exists**, so
  `enabled = false` there turns the mouse off;
- a header with text after its `]` (`configparser` takes `[mouse] x` as
  `[mouse]`), a key with a space in it, a line with no `=` or `:`;
- **a duplicate section, or a key set twice in a section in any case** -
  `configparser` refuses these too, and the loader then reads *nothing* from
  the file, which is worth a line number rather than a shrug;
- a byte order mark (read as part of the first line) and text that is not
  UTF-8.

A `;` or `#` starts a comment only at the start of a line or after
whitespace, as `configparser` has it: `color_mode=truecolor;x` is the value
`truecolor;x`. An edit replaces only the value's span on its line - key
spelling, spacing, comment and line ending stay - and a new setting takes
the place of a commented-out line for it (`;escape_delay = 25`, as
`tkcurses-cfg init` writes them), else follows the section's last setting,
indented so it neither continues its neighbour nor is continued by the next
line. Every edit is read back before it is returned.

**A save is whole or not at all** (`_cfg/store.py`). A program reads the
file when it starts and takes no lock, so the only safe write is a rename:
the new text goes to a temporary file in the same directory, is synced,
takes the old file's mode (and owner, as root), and replaces it with
`os.replace`; the directory is synced after. Before the swap the old file is
hard-linked to a temporary name and only renamed to `<file>.bak` once the
swap has happened, so a failed save leaves the previous backup too. A copy
stands in where the file system has no hard links (`EPERM`, `ENOTSUP`,
`EMLINK`) and nowhere else - a full disk while linking is a failed save, not
a reason to copy, which the failure-injection tests caught on their first
run. SIGTERM and SIGHUP raise while a save runs, so they back out as
Ctrl-C does, and exit 130. A file its owner made read-only is refused even
though the rename would succeed, since only the directory needs to be
writable for that.

**Saves are serialised by `flock` on `<file>.lock`**, held for the
read-edit-write and never while a person looks at a screen, and waited for
up to `--lock-timeout`. The lock file stays: deleting it would let a
process that opened the old one and one that created a new one both hold
"the" lock. A symbolic link is written through, at its target, with the
lock and backup beside the target, so the link and the real path share one
lock. Measured by mutation: with the `flock` taken out, four processes
adding one to a setting 25 times each do not all succeed, and with an
in-place write instead of the rename, a reader sees a part-written file.

**The command line keeps standard output for what was asked** (`_cfg/cli.py`):
`get` prints a value and nothing else, `--json` prints JSON and nothing
else, and every note, warning and error goes to standard error, flushed
after the output it is about. Argument errors are argparse's exit 2 - a
`--lock-timeout` of `nan`, `inf`, negative or over an hour among them - and
everything a person can get wrong after that has its own status, listed in
`--help`, on the reference page, and held equal by `tests/test_docs_cfg.py`,
which also runs every `console` example on the page in order and compares
its output exactly. The system-wide file is moved somewhere empty for that
run, so the page does not depend on the machine building it.

**The command describes what a program would do, not what the files say**:
`list` and `get` call `TkCursesConfig.load` and read its origins, so a value
clamped, refused or overridden by the environment is shown as a program
gets it. After `set` it says when something else will still win - the
user's file over a `--global` edit, or a variable in this shell - and
after `unset`, what the value now is and where it comes from. It sees only
its own environment, and says so.

**A value of the wrong type or out of range stops an edit; nothing else
does** - an unknown or removed key is reported but left alone. The edit is
still allowed if it is the one that fixes or removes the bad value, so a
broken file can always be repaired through the command (decided with the
user, `TkCurses-kge7`).

**`tkcurses-cfg` is written for being run as root by someone careful,
on paths someone else may control** (`_cfg/safety.py`). The threat is the
classic one for a tool used through `sudo`: a link or directory another
user made, on the way to the file being saved, steering root's write into
a file of their choosing. A security review (`TkCurses-kge7`, at the user's
request) found it real and carried it out against the command before the
fix: a save through a link in a world-writable directory replaced the
file the link named; a link planted as `<file>.lock` made a save create a
file wherever it pointed, as root an `/etc/nologin`; a FIFO given as
`--file` hung `check`; a value's `ESC [2J` reached the terminal raw in
`list --sources` and on the screen; a new file under `umask 0` was mode
666, and every lock was 644, so anyone could hold the system-wide lock.

The rule for writing is `sudoedit`'s and OpenSSH's `StrictModes`:
`trusted_target` walks the path a component at a time, with `lstat`,
following links itself and walking `..` where the link leads, as the
kernel does. Each directory must belong to the runner or root and not be
writable by everyone (sticky excepted), each link must belong to either,
the file must be regular and belong to either; as root, every directory
must be root's and writable by root alone. Nothing on an accepted path can
be changed by anyone else, which is what makes the check good until the
write: there is no gap to race. The one exception is a directory still to
be made in a sticky directory, where anyone may create the name first, so
the path is checked again after making it. Group-writable directories are
allowed for a user who is not root, because with user-private groups that
group is usually the user alone; a user's own files are all such a save
could reach.

Decided, and left: reading follows any link - `list` as root shows on
root's own terminal what root can read anyway - and a lock already
created by someone else in a sticky directory can stop a save there,
which is a refusal, not a write. TkCurses programs read their files as
before; the rules are for the command that writes them. Output is escaped
once, by wrapping standard output and error for the whole command, and on
the screen in the one function that draws text - not at each message,
where the one missed would be the one that mattered. The library's own
warnings were already safe: they quote values with `repr`.

Each fix has a test that fails without it, checked by taking each out in
turn (`tests/test_cfg_safety.py`); root's rules are tested through the
`euid` the check takes, since a test cannot become root.

**The interactive screen is plain curses, not a TkCurses program**
(`_cfg/ui.py`). It is the tool for repairing a configuration that makes
TkCurses programs misbehave, so it reads none of the settings it edits for
its own drawing. Every rule it shows is in `_cfg/session.py`, which has no
curses in it and is tested without a terminal; the screen draws the
session and turns keys into calls. A batch of edits is applied with the
ones that fix a bad value first, so saving a fix together with other
changes is accepted, as the same edits one at a time through `set` would
be.

**The screen's IN EFFECT column runs the real loader.** Each edited file is
written to a private temporary directory and `TkCursesConfig.load` reads
it there, as a program would read the real one; the origins are then
mapped back to the real paths. `ConfigParser.read_string` would have saved
the copy but splits lines only on `\n`, where reading a file splits on
`\r` too, so it would have previewed a different parse of the same text.
`tests/test_cfg_session.py` holds the preview equal, value and source, to
what the loader reads once the edits are saved, over generated edits,
files and environments. Two mutations of the preview fail it.

**A resize is applied wherever the screen reads a key.** `getmaxyx()`
stays at the old size until `resize_term()` is given the size the terminal
reports, the fact TkCurses' own `Screen.handle_resize` is built on; the
first version only redrew, and kept drawing the old layout into a smaller
terminal. The screen polls the files once a second while it waits for a
key, reads a changed one again and keeps the pending edits on top, and
checks again just before saving.

**Warnings are printed when the terminal is given back**, through the same
held-reports path a callback's traceback takes (`Tk._held_reports`). Until
`TkCurses-4j1h` nothing printed them at all: a mistyped setting was
corrected silently and never mentioned.

**Every setting is measured through the terminal, not read back off the
configuration** - `tests/test_config_tty.py`. The configuration once had
eighteen settings, and twelve of them were read, validated and tested while
nothing used them; a test of the parsing passed for every one, and the
porting guide told readers to set one that did nothing. Three were made to
work and nine removed (`TkCurses-4j1h`):

- **`color_mode` is a ceiling, never a floor.** A number caps the depth
  `ColorManager` works to (`ceiling=`), so `8` on xterm-256color draws
  with the basic eight and `winfo_colordepth()` answers 8. It cannot
  raise one: curses refuses a colour number past the `COLORS` it started
  with, so `256` under `TERM=xterm` stays 8. `truecolor` is the other
  thing a user can want from it - pictures written past curses as 24-bit
  escapes, as `COLORTERM=truecolor` does - and a number below 256 outranks
  `COLORTERM`.
- **`unicode_borders` off translates at the two places characters leave
  for the terminal**: `Widget._write_line`, which every widget draws
  through, and `CursesScreen._paint`, which a `tkcurses.curses` window
  inside a running application paints through. `ASCII_GLYPHS` in
  `_core/attributes.py` is one character for one, so nothing a widget
  measured moves. Box pieces are read off their Unicode names - reaching
  sideways and up or down is `+`, only sideways `-`, only up or down `|` -
  which covers every weight, dash and arc without a 128-entry table. It
  also changes a program's own text that uses those characters, which on a
  terminal that cannot draw them is no loss. A standalone
  `tkcurses.curses` program does not read the configuration.
- **`mouse.enabled` off never calls `mousemask`**, so none of 1000, 1002,
  1003 or 1006 is sent.

The nine removed are in `REMOVED`, and a file or environment that still
sets one gets a warning that it no longer has any effect:
`refresh_interval` (the loop redraws when idle, not on a timer),
`poll_timeout` (internal to the loop), `keypad` (off breaks every arrow
key), `high_contrast` and `screen_reader` (nothing behind them),
`min_click_interval` (the same thing as `click_interval`), and the three
`debug` settings (there is no logging to configure).

**The pty harness does not implement REP**, `CSI n b`, which ncurses uses
for a run of one ASCII character when the locale is not UTF-8 - measured,
`-\x1b[19b` for an Entry's top edge under `LANG=C`. A test of ASCII
borders under `LANG=C` sees `+-+` where a terminal draws the whole rail.
`TkCurses-go7y`.

**What the terminal environment is told, and when.** Two conditions used
to fail without a word (`TkCurses-a1nm`):

- **A terminal without `cup`** - `TERM=dumb` - started, ran its main loop,
  drew nothing and exited 0. `Tk()` now raises `TclError` naming `TERM`,
  after giving the terminal back, which is the place tkinter raises
  "couldn't connect to display". `vt100`, `linux`, `screen` and every
  xterm entry have `cup`; measured with `curses.tigetstr("cup")`.
- **A locale that is not UTF-8** is said on stderr once the screen is
  given back, naming the first of `LC_ALL`, `LC_CTYPE` and `LANG` that is
  set, since that is the one the C library obeys. The test is the
  encoding curses itself uses, `stdscr.encoding`. Measured: `LANG=C` alone
  is *not* such a locale by the time curses starts - Python coerces a C
  `LC_CTYPE` to `C.UTF-8` at start-up (PEP 538) and exports it - so only
  `LC_ALL=C`, a non-C non-UTF-8 locale such as `en_GB.iso885915`, or
  `PYTHONCOERCECLOCALE=0` reaches the warning.

**A picture no longer fills the colour-pair table** (`TkCurses-o1x`). The
note on that issue concluded it did not matter from 256 colours up,
because the picture is written past curses there. Measured, it did: the
curses layer written *under* those writes, as the fallback for a terminal
that ignores them, still asked for every combination. A 60x40 picture of
random colours wanted 1179 pairs, filled the table, the table was renewed
once and filled again, and three Labels packed under it drew in `#87005f`
on `#0000ff` instead of the `#d70000` on `#0000d7` asked for. Two answers,
by which layer shows:

- **Written past curses**, the layer underneath is drawn in the eight
  basic colours, `ColorManager.fallback_attribute_for`: at most 64 pairs
  whatever the picture, no fitting, and a lookup per cell once seen.
- **Drawn through curses** - eight or sixteen colours, or
  `TKCURSES_DISPLAY_DIRECT_IMAGES=0` - it is fitted (`_pair_palette`):
  each pixel colour mapped to a stand-in from `PhotoImage.fit_pairs`. The
  budget is what the table has left, less an eighth of the capacity (at
  least 8) for what is drawn after the picture, never below 16 or what is
  left. The mapping is kept on the image, keyed on its change count,
  `ColorManager.generation` (moved whenever the table is emptied) and the
  depth. Measured on `earth.gif` resampled to 160x100: wanted 528, the
  first fit took 271ms and gave 69 colours, and a cached lookup takes
  0.2µs.

**A new or changed picture that does not fit asks for the table to be
emptied before it is fitted** (`ColorManager.ask_for_renewal`). Fitted at
once, it was fitted into what the previous picture had left: the second of
two pictures came out in 24 pairs of the 192 it was built from, where
before any fitting the old picture ran the table dry, the renewal freed its
pairs, and the new one had them all (`test_color_pairs_tty.py`). The
renewal runs at the start of `_update_display`, after the widgets have
drawn, so it lands in the same frame; it is asked once per picture
revision and does not count towards the latch that stops renewing a
screen which really wants more pairs than there are. The cost is a
repaint of everything per change of an over-budget picture drawn through
curses, plus the fit - an animation of one pays both every frame.

**Every other way to show a picture is fitted the same way**
(`TkCurses-o79a`): a Canvas image item, a picture embedded in a Text, and
a window's `backgroundimage`. None of the three has a direct-painted
layer, so each is always drawn through curses, and each was drawing the
picture as it is. Measured with the same 60x40 picture and three Labels
under it: all three left the Labels in `#87005f` on `#0000ff`, the
picture holding 252-254 pairs, where a Label's picture held 169 and left
them their colours. A Canvas puts the stand-ins on its plane, in
`_item_pixels`, so that what is composed from them - including a cell
shared with a line drawn over the picture - asks only for colours the
table has room for. The Text and the background map each cell's two
colours at the point they are written, as `_paint_image` does. Two busy
pictures on one canvas share the table as two Labels would: the first
fitted takes the budget and the second what is left.

### Environment Variables Reference

| Variable | INI Equivalent | Type | Description |
|----------|----------------|------|-------------|
| `TKCURSES_MOUSE_ENABLED` | `[mouse] enabled` | bool | Ask for the mouse at all |
| `TKCURSES_MOUSE_CLICK_INTERVAL` | `[mouse] click_interval` | int | Double-click timing (ms) |
| `TKCURSES_MOUSE_REPORT_MOTION` | `[mouse] report_motion` | bool | Drags (DEC 1002) |
| `TKCURSES_MOUSE_REPORT_HOVER` | `[mouse] report_hover` | bool | Every movement (DEC 1003) |
| `TKCURSES_DISPLAY_COLOR_MODE` | `[display] color_mode` | str | `auto`, `8`, `16`, `256` or `truecolor` |
| `TKCURSES_DISPLAY_UNICODE` | `[display] unicode_borders` | bool | Box drawing, or ASCII |
| `TKCURSES_DISPLAY_DIRECT_IMAGES` | `[display] direct_images` | bool | Pictures past curses' pairs |
| `TKCURSES_INPUT_ESCAPE_DELAY` | `[input] escape_delay` | int | ESC sequence delay (ms) |
| `TKCURSES_CLIPBOARD_SYSTEM` | `[clipboard] system` | str | `auto`, `osc52`, `command` or `off`: how the clipboard reaches other applications |
| `TKCURSES_CLIPBOARD_PRIMARY` | `[clipboard] primary` | bool | Set the desktop's primary selection - middle-click paste - once a selection settles |

### Usage Examples

```bash
# Temporary override for testing
$ TKCURSES_MOUSE_CLICK_INTERVAL=400 python my_app.py

# How it looks with eight colours, and in ASCII
$ TKCURSES_DISPLAY_COLOR_MODE=8 TKCURSES_DISPLAY_UNICODE=0 python my_app.py

# A user config
$ mkdir -p ~/.config/tkcurses
$ cat > ~/.config/tkcurses/tkcurses.ini << 'EOF'
[mouse]
click_interval = 350
EOF
```

### Directory Structure Update

Add configuration module to `_core/`:

```
├── _core/
│   ├── __init__.py
│   ├── config.py            # TkCursesConfig, INI loading
│   ├── dispatcher.py        # CursesDispatcher (thread serialization)
│   ├── screen.py            # CursesScreen wrapper
│   ...
```

---

#### Platform Considerations

| Platform | Notes |
|----------|-------|
| Linux | Full mouse support via GPM or xterm |
| macOS | Mouse support in Terminal.app and iTerm2 |
| Windows | Mouse support via windows-curses |
| SSH | Mouse support depends on terminal emulator |
| tmux/screen | Requires `set -g mouse on` for mouse passthrough |

---

## Leaving, and giving the terminal back

**Starting curses changes the terminal, and a process that exits without
undoing that hands the user a shell they cannot use.** cbreak mode, the
alternate screen, a hidden cursor, sometimes mouse reporting — all of it has
to come back, whichever way the program leaves.

It is not enough to undo them in `destroy()`, because a program is not
obliged to call it. tkinter's documented way to leave a main loop is
`quit()`, after which a great many programs simply fall off the end of the
file. Measured, before this was fixed:

| how the program left | terminal |
|---|---|
| `destroy()` | restored |
| `quit()`, then end of file | **alternate screen and hidden cursor left set** |
| Ctrl-C | **left set**, and a traceback printed onto the alternate screen |
| an uncaught exception | **left set** |

`CursesScreen.start()` therefore registers an `atexit` hook, and `stop()`
unregisters it so an orderly shutdown is not undone twice. `stop()` is
idempotent and swallows curses errors, which is what such a hook needs.

`mainloop()` additionally restores the terminal **before** letting an
exception continue. The ordering is the point: something is about to print
that traceback, and on the alternate screen it would be swapped away unread.

### Ctrl-C asks the application to close

**Ctrl-C raises `WM_DELETE_WINDOW`.** It arrives as a signal only when
nothing has bound `<Control-c>` — see `refresh_signal_keys`, which hands the
key to an application that asks for it and otherwise leaves the tty to make
a signal of it. While `mainloop()` runs, the signal only notes the request
(`Tk._catch_interrupts`), and the loop answers it at the end of a pass by
calling `_close_requested()`, which invokes the protocol handler if there is
one and calls `destroy()` if there is not.

**Answered between callbacks, not raised inside one** (`TkCurses-lppt`).
Python delivers SIGINT as a `KeyboardInterrupt` raised wherever the program
happens to be, and `mainloop()` used to catch it around a pass. A callback
running at that moment was cut off where it stood. Measured with a poll that
sleeps 0.2s and then reschedules itself with `after`: on Ctrl-C with text
selected, the poll stopped at its fourth run, every time out of four, and
the copy it would have shown never reached the screen, while the program
went on running. That was scenario 43 on a contended CI runner, waiting 20
seconds for a clipboard line its dead poll could never redraw. With the
request noted and answered between passes, the same poll goes on (5, 8,
...) and the copy shows. A second Ctrl-C while the first still waits means
the loop is not coming back - a callback that never returns - and is raised
as `KeyboardInterrupt` in it, so a wedged program can still be stopped from
the keyboard; `mainloop()` still catches that one as before. Nothing is
changed outside the main thread or when the program has installed a SIGINT
handler of its own, and Python's handler is put back when the loop ends.

**Before `mainloop()` a Ctrl-C is a `KeyboardInterrupt`**, as in tkinter,
raised in the program's own setup. The tests that sent one as soon as their
first paint appeared painted before the loop started, and on a slow runner
the byte arrived in that gap: exit -2, death by an uncaught interrupt -
reproduced every time with a one-second pause before `mainloop()`, and once
in 25 rounds under CPU load without one. They now start drawing from inside
the loop.

**Except while a dialog waits** (`TkCurses-ubwt`). A dialog called at the
top level of a program - `messagebox.askyesno(...)` before `mainloop()` -
waits in `wait_window`, and Ctrl-C there printed a `KeyboardInterrupt`
traceback from `select()`: measured in `messagebox`, `simpledialog`,
`filedialog`, `colorchooser` and `dialog.Dialog`. Decided with the user:
it cancels the dialog, exactly as Escape does. So `_wait_until`, when no
loop is running, takes Ctrl-C the way `mainloop()` does - noted, answered
between callbacks - and the answer is an Escape key routed as if typed, so
each dialog does what its own Escape binding does. The tests run each
dialog twice, once cancelled by Escape and once by Ctrl-C, and require the
same result.

**And inside `mainloop()`** (`TkCurses-28wi`). There Ctrl-C was answered
as copy-or-close by the dialog's own nested loop, so with nothing selected
it destroyed the application, and the dialog's wait - seeing the root
gone - returned as if refused: a "Save changes?" answered no, and the
program ended. (The issue first read this as "one Ctrl-C leaves the
dialog open"; logging the path showed the close.) Decided with the user,
2026-11-08: Ctrl-C closes the innermost thing. So `_answer_interrupt`
copies if the focused widget has a selection, as everywhere; otherwise,
while any window holds the grab - which is what makes a dialog modal, and
every dialog here takes one - it routes Escape as before mainloop. If
Escape leaves the modal window holding the grab, because it binds no
Escape, the window is closed through its `WM_DELETE_WINDOW` protocol and
destroyed if it has none, so Ctrl-C never does nothing; a grab on the main
window itself is the ordinary close. A second Ctrl-C then reaches the main
window. A program's own `wait_window` on a window without a grab is not a
modal question and still closes the application.

Three behaviours fall out of that, and all three are what a person expects:

| the application | Ctrl-C does |
|---|---|
| binds `<Control-c>` | delivers an ordinary key event; no signal at all |
| has a **selection in the focused Entry or Text** | **copies it**, and nothing closes (`TkCurses-lw2`, below) |
| sets `WM_DELETE_WINDOW` | runs the handler — save, prompt, or decline and carry on |
| does neither | closes the window and exits 0, no traceback |

The handler is caught *inside* the loop rather than around it, so a handler
that decides **not** to close can simply return and the application carries
on — which is how `WM_DELETE_WINDOW` behaves everywhere else in tkinter.

#### Why this diverges from tkinter, on purpose

tkinter's behaviour was measured rather than assumed, on a real X display,
over four scenarios with five repeats of the unhandled case:

| | tkinter | TkCurses |
|---|---|---|
| idle main loop | KeyboardInterrupt after **5.4s** | close request after **0.8s** |
| a repeating `after()` every 50ms | after 0.8s | after 0.8s |
| one `after()` at 2s | after 1.0s | — |
| a bound key, no timer | after 4.5s | — |
| unhandled, five runs | traceback, exit −2, every time | clean exit 0 |
| catchable by the program | yes, around `mainloop()` | yes, via `WM_DELETE_WINDOW` |

The signal fired at 0.8s in every case, so tkinter's figures are the delay
before it was *delivered*: its main loop is Tcl's, running in C, and a
Python signal handler cannot run until Python code does — so an idle tkinter
program sits on the interrupt for seconds. TkCurses waits in `select()`,
which the signal interrupts directly.

So tkinter really does end in a traceback, and TkCurses deliberately does
not. The reason is that **the two are not in the same situation**, and
`wm_protocol`'s own docstring is where that became clear. It used to say
that `WM_DELETE_WINDOW` was the protocol worth having and that *nothing
raised it*: "a terminal offers no close button and no user gesture that
means close this window". The mechanism was right; the gesture had been
missed.

A tkinter program lives **inside a window**. The close button is the user
saying "shut this down"; Ctrl-C comes from a *terminal somewhere else*,
typed by a developer at the shell that launched it, and a traceback is the
right answer to a developer.

A TkCurses program **is the terminal**. There is no close button and there
never will be, and Ctrl-C is not arriving from outside — it is the only
"close this" gesture an end user has. Treating it as a developer's interrupt
would leave the library's own premise unsatisfied: the one protocol worth
having would have nothing that raises it, and a plain application would have
no way out at all. The divergence is in the *delivery*, and it exists to
keep the *semantics* matching: in both libraries, the user's close gesture
runs `WM_DELETE_WINDOW`.

That was not a theoretical gap. The editor scenario — `Tk`, a `Text`, a
`Scrollbar`, no key bindings — had no exit. Ctrl-C printed a traceback, which
is not an exit; it is a crash that happens to stop the program.

#### What is actually going on underneath

Worth recording, because the layers are easy to conflate:

- **SIGINT is signal 2**, and its default action terminates the process. It
  is catchable — unlike SIGKILL — which is the whole reason any of this is
  available to us.
- The terminal driver sends it to the **foreground process group**, not to
  one process, and only because the tty is configured to: the `ISIG` flag
  plus the `VINTR` control character. `claim_signal_keys` changes `VINTR`
  per key rather than clearing `ISIG`, so giving up Ctrl-C does not also
  give up Ctrl-\ — which is what a person reaches for when an application
  stops responding.
- Python installs `default_int_handler`, which raises `KeyboardInterrupt`
  in the main thread. That exception is what `mainloop()` catches; the
  signal itself is never handled by TkCurses.

#### Two corrections recorded

Both nearly sent this the wrong way.

An early single probe of tkinter appeared to show the interrupt being
*ignored entirely*, and on that basis a quiet exit looked like an
improvement rather than a divergence. Four scenarios and five repeats say
otherwise. One measurement of a timing-dependent behaviour was not a
measurement.

Then, knowing tkinter's real behaviour, the first conclusion was "match it,
so there is nothing to change". That treated *identical mechanism* as
*identical meaning*. The question is not what tkinter does with a signal;
it is what the user's close gesture is, and in a terminal that gesture is
Ctrl-C.

#### The terminal still comes back first

Unchanged, and still the reason the section above exists: whatever leaves
the loop, the terminal is restored before anything else runs. An application
that raises out of a `WM_DELETE_WINDOW` handler gets its traceback on a
terminal that works, not on the alternate screen where it would be swapped
away unread.

### A terminal that hangs up ends the program, and its cleanup runs

Closing the terminal's window, or losing the SSH connection it came over,
hangs the terminal up. The program gets SIGHUP, and from then on its
terminal reads end of file. Measured on a pty whose master was closed under
a running `mainloop()`, before this was handled:

- **SIGHUP at its default** killed the process at once. No `finally` block,
  no `atexit` handler and no code after `mainloop()` ran, so nothing a
  program meant to save was saved.
- **SIGHUP ignored**, as under `nohup`, the process never exited. It used
  4.99 s of CPU in 5 s: `select()` reports a hung-up terminal readable for
  ever, `getch()` has nothing, and the loop went round again.

What a hung-up terminal answers, measured in a child that ignored SIGHUP:
`select` readable; `getch()` ERR; `os.read` empty; `tcgetattr`,
`tcgetpgrp` and `write` EIO; `endwin()` ERR.

The author's decision, 2026-11-17: exit with cleanup. While `mainloop()`
runs, and SIGHUP is at its default, the signal only marks the hangup
(`Tk._catch_hangup`, as Ctrl-C is marked), and the loop raises
`SystemExit(129)` at the end of the pass. 129 is 128 + SIGHUP, what a shell
reports for a process the signal killed, so a caller reading the status
sees the same reason as before. `finally`, `atexit` and a program's
`except SystemExit` all run. The terminal is not restored, since there is
none; every write on the way out already tolerated failure.

A program with its own SIGHUP handler, or one that ignores the signal, is
left in charge of it. The loop still notices the hangup, from the terminal:
a wait that reports input followed by a poll that reads none sends it to
`InputHandler.terminal_gone()`, which asks for the terminal's settings and
takes EIO or ENXIO as a hangup. That is one system call, made only on a
pass that was woken and read nothing, so a live terminal pays nothing for
it. A stream that is not a terminal answers differently and is not taken
for one that hung up.

A dialog shown before `mainloop()` waits in passes of its own
(`Misc._wait_until`), which catch SIGHUP as they catch Ctrl-C, so a hangup
there ends the program the same way. Until they did, the default stood and
the hangup was the signal's own kill, measured as the child dying by
signal; ignored or handled, the wait already ended with 129, because its
passes are the loop's and notice the terminal. A program that calls
`update()` in a loop of its own, outside both, keeps the default: catching
the signal on every call would change it for code that never asked.
`tests/test_terminal_hangup_tty.py` holds the three cases, default,
ignored and the program's own handler, under `mainloop()` and under a
dialog's wait before it (`TkCurses-wk51`).

---

## Data Flow

### Copy, cut and paste

**Ctrl-C copies when the focused widget has a selection, and closes the
application otherwise** (`TkCurses-lw2`). That revises the section above, and
it is the author's decision, made on a measurement rather than a guess. A key
probe run in the author's terminal (xterm-256color, truecolor) showed that
**no copy key of Tk's except Ctrl-C reaches a program**:

| key | arrived as | Tk means |
|---|---|---|
| Ctrl-C | the close request | copy |
| Ctrl-X, Ctrl-W, Shift-Delete | keys | cut |
| Ctrl-V, Ctrl-Y | keys | paste |
| Shift-Insert | the system clipboard, **typed in** — the terminal's own paste | paste |
| Ctrl-Insert | **nothing** — the terminal keeps it | copy |
| Ctrl-Shift-C | **plain Ctrl-C** — so it would have closed the app | (terminal copy) |
| Ctrl-Shift-V | nothing | (terminal paste) |
| Alt-W | Escape, then w — Alt is not decoded | copy |
| F16 / F18 / F20 | undecoded escape sequences | copy / paste / cut |
| middle button | button 2, to the program | paste PRIMARY |

So the copy decision is made in the interrupt handler, `_copy_on_interrupt`,
and not by a binding: binding `<Control-c>` takes the key from the tty, and
there would be no close gesture left. With nothing selected, Ctrl-C closes
exactly as before; an application that binds `<Control-c>` still takes it
entirely.

**The virtual events exist from the start**, as Tk defines them in `tk.tcl`,
with Tk's sequences less the ones that cannot arrive: `<<Cut>>` is Ctrl-X,
Ctrl-W and Shift-Delete; `<<Paste>>` Ctrl-V, Ctrl-Y and Shift-Insert;
`<<Copy>>` Ctrl-Insert; `<<SelectAll>>` Ctrl-/ **and Ctrl-_**, because a
terminal sends one byte, 0x1f, for both and it is decoded as underscore;
`<<PasteSelection>>` the middle button's release; `<<Clear>>` nothing;
`<<Undo>>` Ctrl-Z and `<<Redo>>` Ctrl-Shift-Z, less their Lock forms - see
"Undo and redo in a Text".
`event_info("<<Copy>>")` therefore differs from Tk's, which also lists
Control-c, F16 and Meta-w.

The navigation events are defined too, with X11's keys and in `tk.tcl`'s
order (`TkCurses-yu5l`): `<<PrevChar>>`/`<<NextChar>>` Left/Right,
`<<PrevWord>>`/`<<NextWord>>` Control-Left/Right, `<<LineStart>>`/
`<<LineEnd>>` Home/End, `<<PrevLine>>`/`<<NextLine>>` Up/Down,
`<<PrevPara>>`/`<<NextPara>>` Control-Up/Down, and a `Select` form of each
with Shift added. With them, the emacs keys `tk::EventMotifBindings` adds
while `tk_strictMotif` is off, which it is unless a program sets it:
Control-b/f, Control-p/n and Control-a/e (`TkCurses-wmaq`). Not their
`Select` forms, Control-B and the rest - a terminal sends Control-B as the
byte Control-b is. Not `<<SelectNone>>`: its Control-backslash is the tty's
quit key, and a binding on it would take SIGQUIT from the program. Nor
`<<Undo>>`, `<<Redo>>` or `<<ToggleSelection>>`, which nothing here binds
yet. Listbox, Entry, Spinbox, the ttk entries and Text bind the navigation
events as Tk's scripts do - see "Moving with the keyboard"; Scale,
Scrollbar and Menu still bind the keys (`TkCurses-rs2l`).

**A physical binding and a virtual one compete, within a tag** - one runs,
measured on Tk 9.0.2 on one Frame (`TkCurses-hkul`):

| Bound on the tag | Key | Runs |
|---|---|---|
| `<Up>`, `<<PrevLine>>` | Up | `<Up>` |
| `<Key>`, `<<PrevLine>>` | Up | `<<PrevLine>>` |
| `<<PrevLine>>`, `<<SelectPrevLine>>` | Shift-Up | `<<SelectPrevLine>>` |
| `<<PrevLine>>`, `<<PrevPara>>` | Control-Up | `<<PrevPara>>` |
| `<Up>`, `<<SelectPrevLine>>` | Shift-Up | `<<SelectPrevLine>>` |
| `<Shift-Up>`, `<<PrevLine>>` | Shift-Up | `<Shift-Up>` |
| `<Control-v>`, `<<Paste>>` | Control-v | `<Control-v>` |
| two events on F6, both bound | F6 | the one defined first |

So a virtual binding ranks as the most particular of its registered
sequences that the key matched, and a tie goes to the physical binding and
then to the virtual event defined first. On two tags - `<Control-v>` on the
widget, `<<Paste>>` on its class - both run, one per tag. Ours used to treat
the two as separate events and run both on one tag; the docstring that said
so claimed it was Tk's, and nothing had measured it.

**Two physical bindings equally particular: the one registered last runs**,
as `bind(n)` says - "the most recently registered sequence is the winner".
Registered means first bound: binding a sequence again leaves it where it
was. Measured on Tk 9.0.2 on one Frame with Control-Shift-Next, which
`<Shift-Next>` and `<Control-Next>` both match with one modifier each: the
later of the two runs, in either order, and still does after the earlier
is bound again. It is why text.tcl's Control-Shift-Next scrolls sideways.
Ours ran both (`TkCurses-5co5`).

**Entry, its subclasses and Text bind them as Tk's do**, measured on Tk 9.0.2:

- **copy** puts the selection on the clipboard — what is *shown*, so a
  `show="*"` entry copies `*****` — and with nothing selected does nothing;
- **cut** is copy then delete, so a readonly or disabled widget still copies
  and refuses the delete;
- **paste replaces the selection** — a **deliberate departure from classic
  Tk on Linux**, decided by the author after a person running UAT 43
  expected it. Read from Tk 9.0.2's own `text.tcl` (`tk_textPaste`) and
  Entry's `<<Paste>>` binding, and measured with `hello` selected in
  `hello world` and `XX` pasted:

  | | Linux (X11) | Windows, macOS |
  |---|---|---|
  | classic Entry, Text | `helloXX world` — inserts at the cursor, keeps the selection | `XX world` |
  | ttk Entry, Combobox | `XX world` | `XX world` |

  Classic Tk deletes the selection only `if {[tk windowingsystem] ne
  "x11"}`; ttk's `PendingDelete` always does. A terminal is not an X11
  desktop, and replacing is what ttk and two of Tk's three platforms do, so
  every widget here replaces: the cursor goes to the start of the selection,
  the selection is deleted, the clipboard is inserted. Each is a separate,
  validated edit, so a rejected insert leaves the deletion done — as ttk's,
  measured (`123`, `1` selected, `ab` pasted under a digits-only
  `validatecommand`: `23`). A read-only or disabled widget refuses both and
  keeps its selection. With nothing selected, paste inserts at the cursor.
  An empty clipboard pastes nothing. **The middle button never replaces**,
  on any platform — it inserts PRIMARY where it was released;
- **select all** leaves the cursor where it was; **clear** deletes the
  selection; the **middle button** inserts PRIMARY where it was released;
- **dragging** with the left button selects from the press to the pointer,
  either way round, and the cursor follows the pointer — Tk's character-mode
  `tk::EntryMouseSelect`, read from the running interpreter. Entry had no drag
  until a person running UAT 43 tried one; double-click, Shift-click and
  autoscroll are the next section;
- every edit goes through `insert` and `delete`, so validation and the state
  have their say. Shift-Delete is a cut, not a delete — Tk lets the virtual
  event have it — so the key handlers pass it on.

**One selection at a time**, as Tk keeps it. Measured on Tk 9.0.2: with
`exportselection` on, selecting in one widget clears the selection in whichever
widget held PRIMARY before — Entry and Text alike, either way round. A widget
with `exportselection=0` keeps its own and clears nobody's, and copying to the
clipboard clears nothing. `Selections.own` now calls the previous owner's
`lost` callback, which is Tk's `selection own -command` and tkinter's
`selection_own(command=...)`; Entry and Text use it to drop their highlight.
Text's `exportselection`, stored and never read, now takes PRIMARY whenever
its `sel` range is not empty (the Text half of `TkCurses-9e8`). Before this,
several fields stayed highlighted at once, which a person running UAT 43
reported.

**The clipboard reaches other applications** (`TkCurses-hpr`) by one of two
routes, chosen once when the application starts
(`_core/system_clipboard.py`):

- **OSC 52**, `ESC ] 52 ; c ; <base64> BEL`: the terminal sets the
  clipboard. Works over SSH, but only where the terminal implements it, and a
  terminal that does not ignores it silently — so it is not sent on hope. The
  terminal is **asked** first, with XTGETTCAP for `Ms` (the terminfo
  capability tmux decides the same question by), fenced with DA1 so a
  terminal that answers costs a round trip and a silent one at most 0.5s. The
  question is asked **before curses starts**, which would read the answer as
  keystrokes.
- **The desktop's clipboard tool**: `wl-copy`/`wl-paste` on Wayland, `xclip`
  or `xsel` on X11. Works in any terminal, and can read as well as write,
  but only on the machine the desktop is on — over SSH (`SSH_CONNECTION`,
  `SSH_CLIENT`, `SSH_TTY`) it would fill the remote machine's clipboard, so it
  is not used there.

Measured in the author's terminal, Ptyxis (`VTE_VERSION=8401`), with a raw
probe: DA1 answered `ESC[?61;1;21;22;28c`, XTVERSION `VTE(8401)`, and the
`Ms` query **`ESC P 0 + r ESC \`** — an explicit "not a capability I have";
an OSC 52 read was ignored, and an OSC 52 set of both CLIPBOARD and PRIMARY
was ignored too (the paste key still pasted the previous clipboard). VTE —
GNOME Terminal, Ptyxis — does not implement OSC 52, its developers having
declined it on security grounds.

`clipboard.system` (`TKCURSES_CLIPBOARD_SYSTEM`) chooses: **`auto`** writes by
OSC 52 when the terminal says it has it and by the desktop tool otherwise,
and reads through the desktop tool whenever there is one, so Ctrl-V brings in
what another application copied — tkinter's `clipboard_get` answers whichever
application owns the clipboard. `osc52` and `command` force one route; `off`
keeps the clipboard inside. **OSC 52 is never read**: terminals restrict or
prompt for it, for the reason VTE refused the sequence at all.

A copy that cannot leave — no route, or a tool that failed — is **said once,
on stderr, after the screen is given back**: what was copied stayed inside
this program, and why. Not when the person chose `off`. A copy is sent whole
after every `clipboard_append`, because the system clipboard has no append.
**PRIMARY reaches the system once it settles** (`TkCurses-r1k1`), so a
middle click in another application pastes what was selected here, as from
Tk on X11. X11 announces a selection on every change; starting a desktop
tool per mouse report is not worth it, so `Selections.push_primary`, run by
the event loop on every pass, looks at PRIMARY every 250ms
(`PRIMARY_SETTLE`) while something owns it, and sends it when it reads the
same twice running and differs from what was last sent. The route is the
clipboard's: OSC 52 with its `p` target, `wl-copy --primary`,
`xclip -selection primary` or `xsel --primary`. The tool is **not waited
for** (`CommandPush`): it is handed the text, given 200ms to take it, and
left running in its own session; `wl-copy` and `xclip` fork a process to
serve the selection and the one started here ends at once. A push that is
still waiting when the next is made is killed, since its text is stale.

Measured on GNOME Shell 50.4 (Wayland): the compositor offers
`zwp_primary_selection_device_manager_v1` and `wl_data_device_manager` but
no data-control protocol, so `wl-copy` can set a selection only by mapping a
surface of its own and waiting for keyboard focus. Run from a process with
no window, `wl-copy` and `wl-copy --primary` both waited until killed (5s);
from a focused terminal the clipboard route was accepted in UAT 43. From a
focused terminal the primary push is **not seen**: run by the author in UAT
43 on 2026-11-14, middle-click paste in another application worked with "no
flicker or loss of focus". So it is on by default, and
`clipboard.primary` (`TKCURSES_CLIPBOARD_PRIMARY`) turns it off.

The test harness turns the setting **off** for every child, so a test run
never touches a developer's clipboard, and answers DA1 and `Ms` as a real
terminal would — as kitty (`osc52=True`) or as VTE was measured to.

**The insertion cursor is the terminal's own** (`TkCurses-lw2`). Entry and
Text painted it as a reversed cell — the same attribute as a selection, and
never blinking — so a person running UAT 43 could not tell the cursor from
the selected text beside it. Tk draws a distinct, blinking insertion bar; the
terminal has one already. `TerminalCursor` (`_core/screen.py`) shows it at the
focused widget's insert point and hides it everywhere else, so it blinks and
takes whatever shape the person's terminal is set to — the author's choice,
over painting a better imitation:

- it is placed **just before every `doupdate`**, on both flush paths (the
  panel stack and the screen buffer), because curses puts the cursor wherever
  its virtual cursor is at that moment; shown and hidden only on a change;
- the focused widget answers where, through `_insert_cell()`: Entry and Text
  note the cell while drawing, and answer None when unfocused, read-only, or
  scrolled so the insert point is out of view;
- the image overlay (`_core/direct.py`) is written after `doupdate`, so it is
  wrapped in a cursor save and restore (DECSC / DECRC); otherwise the cursor
  would be left wherever the last image cell went.

**Validation takes tkinter's registered form** (`TkCurses-5ufn.2`).
`validatecommand=(root.register(check), "%P")` - a command name and Tk's
percent codes, as a tuple or one string - is called with each code
substituted. Measured on Tk 9.0.2, path by path, and held by
`tests/test_validation_registered.py`, which runs every path on real tkinter
too:

| Path | `%d` | `%i` | `%S` | `%V` |
|------|------|------|------|------|
| `insert`, a typed key | 1 | where | the text inserted | `key` |
| `delete`, Backspace, Delete | 0 | where | the text deleted | `key` |
| focus in / out | -1 | -1 | `""` | `focusin` / `focusout` |
| a `textvariable` write (classic only), `validate()`, a Spinbox arrow | -1 | -1 | `""` | `forced` |

`%s` is the text before the change - for a variable write, before the write,
though the field already holds the new value when the validator runs.
**Typing over a selection is two validations**, a delete and then an insert,
as `tk::EntryInsert` makes them; the insert is tried even when the delete was
refused. Backspace and Delete with a selection used to delete it without
asking the validator at all. `%%` is `%`, and a code Tk does not know is its
own letter. The answer is read as a Tcl boolean: `"no"` and `0` refuse, while
`None`, a raise, or a name nothing registered turns validation off, as Tk
does. `cget("validatecommand")` answers the one string tkinter would have
passed, `"<name> %P"`.

**Busy windows take the pointer and nothing else** (`TkCurses-0ap`). Tk's
`tk busy hold` maps a transparent window over the one held, so every pointer
event meant for it or a descendant lands on the busy window instead. Here the
router drops such an event: in `_route`, when no press is in progress and no
grab elsewhere would take it. A press made before the hold keeps its implicit
grab and gets its release, so a button is never left held down. **Keys are not
stopped**, because Tk's are not: `busy.n` says a widget that already had the
focus "still may receive keyboard events", and Tab can still reach one,
measured on Tk 9.0.2 with an Entry inside a held Frame. A program that wants
the keyboard out too moves the focus, as `examples/form.py` does. Every answer
and refusal of the family - `cannot find busy window`, a hold with a bad
option leaving the window busy all the same - is compared with real tkinter
by `tests/test_busy.py`.

**Screen distances take Tk's units** (`TkCurses-2qo`): `2c`, `1i`, `3m`,
`10p`, at ten cells to the inch - the figure `winfo_fpixels` and `tk scaling`
already used, and an assumption, since a terminal does not say how large its
cells are. One reader, `_core/geometry.distance_in_cells`, serves the widget
options, `pack`, `grid` and `place`, and ttk's `padding`. Measured on Tk
9.0.2 (`Tk_GetPixels`): space may sit before or after the unit, the unit is
lower case only, a hexadecimal number is read whole before any unit
(`0x10c` is 268), and `place` rounds a fraction and keeps a negative
distance. **One difference is kept:** Tk's `cget` answers `2c` as written,
and here the option holds the cells it comes to, because everything that
draws reads a number. ttk's `padding` is kept as written and converted when
drawn.

**The mouse cursor options are checked and kept, and draw nothing**
(`TkCurses-reba`). The pointer belongs to the terminal, but `cursor`,
`buttoncursor` and `sashcursor` are refused as Tk on X11 refuses them, so a
program written here runs under tkinter. Measured on Tk 9.0.2: a name from
the X cursor font, or `none`, case and all - `WATCH`, `pointer` and the
Windows and macOS names the `cursors` manual lists as those platforms' own
are `bad cursor spec` - with up to two colours, each checked (`invalid color
name`); or `@file fg` or `@file mask fg bg`, where both files are read as
XBM (`cleanup reading bitmap file`) and the cursor's own must define a hot
spot (`bad hot spot in bitmap file`). X11 rather than the union of
platforms, because every other measurement in this library is X11's and a
program using a Windows cursor fails under tkinter on Linux too.

**Tk's insertion-cursor options steer it** (`TkCurses-gm66.2`), and only when a
program changes them. Canvas, Entry, Spinbox and Text take `-insertbackground`,
`-insertborderwidth`, `-insertofftime`, `-insertontime` and `-insertwidth`, and
Text also `-blockcursor` and `-insertunfocussed`. They were refused until this.
The values are checked and stored as Tk 9.0.2 does, with its messages:
`insertwidth=-3` reads back 0, `blockcursor="yes"` reads back 1,
`insertunfocussed="h"` reads back `hollow`, `insertofftime="x"` is
`expected integer but got "x"`. The one difference is the colour's default,
`""` for the terminal's own where Tk's is `#000000`.

An option left at Tk's default asks for nothing, so the UAT 43 choice stands:
the person's cursor, as their terminal is set up. One a program changed asks
the terminal for the nearest thing it has, decided with the author:

| Tk asks for | The terminal is asked for |
|---|---|
| `blockcursor=1` on a Text | a block (DECSCUSR 1), steady (2) if it does not blink |
| `insertwidth` other than 2 | a bar (5), steady (6) if it does not blink: Tk's shape at every width, and a cell has no width to give it |
| `insertofftime` 0 or less | a steady cursor, which is what Tk's manual says 0 means; asked alone, a steady **bar**, the cursor Tk would draw |
| `insertbackground` | its colour (OSC 12), as `#rrggbb` |

`insertontime`'s length, the blink's speed and `insertborderwidth`'s 3-D edge
have no request a terminal understands. `insertunfocussed` would need a second
cursor, because the terminal has one and it is where typing goes. All of them
are stored and answered only.

**The request goes with the focus.** `TerminalCursor` sends it when the focused
widget's style changes, never each frame. Focus moving to a widget that asks
nothing sends the resets, DECSCUSR 0 and OSC 112, which are the person's own
settings rather than a guess at them. `CursesScreen.stop` sends them at exit
too, because a cursor shape outlives the program that set it. A terminal that
does not understand a request ignores it. The tests read the bytes the program
writes, since the emulator under the harness keeps no cursor shape:
`tests/test_insert_cursor_tty.py`.

### Selecting with the mouse

Double-, triple- and Shift-clicks, a drag after each, and autoscroll, in Entry,
Spinbox, the ttk entries and Text (`TkCurses-svtr`). Tk's manuals describe none
of it beyond a sentence each, so the rules are **read from Tk's own bindings**
— `bind_class` and the bodies of `tk::EntryMouseSelect`, `tk::TextSelectTo`,
`tk::TextResetAnchor`, the `ttk::entry` procedures and the autoscan ones —
and every selection below **measured on Tk 9.0.2** by calling those procedures
with the pointer just inside a character's left edge, which is where a
terminal cell puts it. Synthetic mouse events do not reach Tk's Entry
bindings in a headless probe, so calling the procedures is the only way to
measure them. (`tkinter.Entry` also has no `bbox`: `e.bbox(i)` is
`grid_bbox`, which answers zeros, and cost a round of wrong measurements.)

**A word is a run of one kind of character**: word characters, or anything
else. So double-clicking the `, ` in `hello, world` selects both characters,
and a run of spaces is a "word". A word character is a letter, a decimal digit
or connector punctuation — Tcl's `\w`, which is **not** Python's `isalnum`
(that takes `²` and `½` and misses `‿`). `_core/editing.is_word_char` was
checked against Tcl's regexp for all 1,114,112 code points with no
difference. Words break on the text the widget **holds**, not what `show=`
displays, as Tk's do.

| | classic Entry | ttk Entry | classic Spinbox | ttk Spinbox | Text |
|---|---|---|---|---|---|
| double-click | the run; cursor after it | the run; cursor after it | the run; cursor **before** it | **everything** | the run, **across lines**; cursor before it |
| triple-click | everything; cursor at end | everything; cursor at end | everything; cursor at **0** | as a double | the line **and its newline**; cursor at line start |
| drag after a double | by words, to the character **before** the pointer | by words, **including** the pointer's | as Entry | — | by words |
| Shift-click | `selection adjust`: nearer end moves, **cursor stays** | extends from the far end, **cursor moves** | as Entry | as ttk Entry | `tk::TextResetAnchor`, then to the pointer |
| Double-/Triple-Shift | extend by words / everything | not bound | as Entry | not bound | extend by words / lines |

The two "drag after a double" rules part company only where the pointer lands
on a word's first letter: from `two`, dragged onto the `t` of `three`, classic
selects `two ` and ttk `two three`.

**Two Tk defects are not copied**, as `edit_undo` is not
(`TkCurses-aah`):

- **classic Spinbox's double-click selects nothing on the first character of
  a run** — at 5, 7, 12 and 13 of `hello, world 42`, measured. Its
  `tk::spinbox::MouseSelect` is an older copy of Entry's code without Entry's
  case for the pointer on the anchor. It uses Entry's rule here, keeping its
  own cursor placement.
- `tk::TextResetAnchor`'s test for "the selection spans few lines" compares
  the first line with the last **plus two**, which always holds — so it
  always decides by character count. That is ported as it is, because it is
  what Tk does and it is not wrong, only not what its author meant.

**The pointer is held to the visible text**, as Tk's `@x` and `@x,y` are. A
pointer dragged past an edge names the edge; without that it named a
character off screen, and keeping the cursor in view jumped the field by the
whole overshoot.

**Autoscroll** is Tk's: while the button is held with the pointer past an edge,
a timer scrolls every 50ms and selects to the pointer, until the pointer comes
back or the button comes up. Motion reports stop when the hand does, so
without the timer a drag held past the edge would scroll once.

- an entry scrolls two characters a tick, either side;
- a Text scrolls **one line more than the pointer is past** the top or bottom
  — Tk's `1 + y - height` is in pixels, a row is the unit here, and one row
  past a Text is about one line of Tk's, so it comes out the same speed; past
  either side, two columns.

A terminal reports the pointer only inside itself, so a widget against the
terminal's edge cannot be dragged past that edge.

**Clicks are counted by `MouseDecoder`**, within `mouse.click_interval`
(200ms; `TKCURSES_MOUSE_CLICK_INTERVAL`, up to 1000), on the same cell. A
double or triple press now **takes the implicit grab** as a single one does
(`Tk._mouse_target`): without it, the drag after a double-click went to
whatever was under the pointer.

**Alt-click extends a selection as Shift-click does — a deliberate
departure.** GNOME Terminal, Ptyxis and every other VTE terminal keep every
Shift-click for their own text selection and never send it to a program, even
one that has turned mouse reporting on. Measured with a raw probe (DECSET
1000/1002/1006, bytes read straight from the terminal) in the author's
terminal, `VTE_VERSION=8401`: plain clicks arrived as `ESC [<0;x;yM`, Ctrl
as `ESC [<16;…`, Alt as `ESC [<8;…`, and Shift-clicks not at all. So every
`Shift-` binding above — single, double and triple — has an `Alt-` twin
(`_EXTEND_MODIFIERS`). Tk binds nothing to Alt-click, so nothing is lost. Ctrl
was the other candidate and is not used: classic Entry, Spinbox and Text bind
Ctrl-click to "move the cursor and leave the selection" (below). In a terminal
that does send Shift-click, both work.

**Ctrl-click moves the cursor and leaves the selection** (`TkCurses-mndh`),
as Tk binds it, read from Tk 9.0.2: classic Entry and Spinbox
`<Control-Button-1>` is `%W icursor @%x`, and Text's is `mark set insert
@%x,%y` with an undo separator when `-autoseparators` is on. Nothing else
moves — not the selection, not its anchor, and not the focus. Text also binds
`<Control-B1-Motion>` and `<Control-Double-Button-1>` to *nothing*, to stop a
plain drag or double-click taking over while Ctrl is held; ours has no
separate drag binding to block, and blocks the double. ttk binds none of
this, so in a ttk entry a Ctrl-click is a plain click. Not copied: in Tk a
Ctrl-*drag* on a classic Entry selects from whatever anchor the last plain
press left, through state its bindings share.

**A longer click sequence outranks more modifiers**, which our binding engine
had the wrong way round. Tk's manual orders specificity as the detail, then
the length of the sequence, then the modifiers; measured with synthetic clicks
on a Frame:

| Held | Bound | Second click fires | Third |
|---|---|---|---|
| Control | `<Control-Button-1>`, `<Double-Button-1>` | `<Double-Button-1>` | |
| Shift | `<Shift-Button-1>`, `<Double-Button-1>` | `<Double-Button-1>` | |
| Shift | the same, and `<Double-Shift-Button-1>` | `<Double-Shift-Button-1>` | |
| Shift | `<Button-1>`, `<Shift-Button-1>`, `<Triple-Button-1>` | `<Shift-Button-1>` | `<Triple-Button-1>` |

Ours fired the modified single click every time. So a Ctrl-double-click on a
classic Entry selects by words, as Tk's does — from the anchor the last
*plain* click left, since the Ctrl press sets none (measured: a plain click at
1, then a Ctrl-double-click at 9, reads `(0, 13)`).

**Combobox follows `ttk::combobox::Press`** (`TkCurses-fgke`), read from Tk
9.0.2: a press is the *entry's* when the combobox is not read-only and the
press lands on its `textarea` element, and is then ttk's entry press, word
select, line select or shift-press; anywhere else — the arrow, the border, or
a read-only combobox — it opens the list. Every click used to open it, so an
editable combobox's text could not be clicked into at all. UAT 34's combobox
is editable, so its "click opens the list" became "click the arrow".

**The ttk `-state` option sets the state flags**, which it did not. Measured
on Tk 9.0.2 on every themed widget that has the option (Entry, Combobox,
Spinbox, Button, Checkbutton, Radiobutton, Label, Scale, Menubutton): setting
it clears `active`, `disabled` and `readonly` and sets the one named —
`normal` sets none — leaving the other flags; the other direction is not
tied, `state(["disabled"])` leaves `cget("state")` alone. Ours stored the
option and left the flags, at construction and on `configure` alike, so
`ttk.Combobox(state="readonly")` — the usual pick-from-a-list combobox — still
took typing, and could not have been told from an editable one here.

### Moving with the keyboard

**Entry, Spinbox, ttk.Entry, ttk.Combobox, ttk.Spinbox and Text bind the
navigation virtual events**, as `entry.tcl`, `spinbox.tcl`, `ttk/entry.tcl`
and `text.tcl` do, and Text also binds Control-Home and Control-End as
themselves (`TkCurses-wmaq`). Each was held to a recording of real Tk:
`tests/support/record_navigation_keys.py` drove Tk 9.0.2 through 1050 random
runs of the arrows, Home and End under every modifier, the events
themselves, and the program moving the cursor and the selection - 150 per
widget, and a Text both unwrapped and wrapped at a word. Ours replays all of
them the same, but for one difference kept on purpose, below. None of the
bindings breaks, so Left in an Entry also reaches the toplevel's bindings and
`all`'s, measured in all five; ours used to stop them.

**Where a word starts and ends** is not `word.tcl`'s rule in Tk 9. `tk.tcl`
defines `tk::endOfWord`, `tk::startOfNextWord` and `tk::startOfPreviousWord`
over `word.tcl` only if they do not exist, and Tk 9.0.2, built with ICU,
makes them in C - `tcl_wordchars` is never even set. Measured over 417
strings (`tests/support/word_boundaries.json`), each is a step over Unicode's
default word boundaries (UAX #29) and sometimes a second, never more:

| Procedure | Answers |
|---|---|
| `endOfWord` | the next boundary, and the one after it unless the first is white space |
| `startOfNextWord` | the next boundary, and the one after it if the first is white space |
| `startOfPreviousWord` | the boundary before, and the one before that if it is white space |

So `foo_bar-baz` is three words, `foo_bar`, `-` and `baz`; `it's`, `3.14`
and `1,000` are one each; a run of spaces is one piece and a tab another;
and from the end of `abc` in `abc  \n  def` the next word starts at the
newline. An answer at the end of the text is no answer: Tk returns `""`, and
the bindings then go to `end` themselves. A double-click is the exception:
`tk::wordBreakBefore` and `tk::wordBreakAfter` are still tk.tcl's, over
`word.tcl`'s runs of `\w` and `\W`, so `it's` is three pieces to a
double-click and one to Control-Right. Recorded beside the others, and
`_core/editing.py`'s `run_start` and `run_end` answer as they do from every
index (`TkCurses-asfo`). `_core/words.py` models the rest; ICU's
dictionary segmentation of Chinese, Japanese and Thai is not, and a run of
those is one word there.

**Classic and ttk extend a selection differently.** A classic entry's
Shift-move is `tk::EntryKeySelect`: with nothing selected, `selection from
insert` then `selection to`; otherwise `selection adjust`, which moves the
nearer end. ttk's is `ttk::entry::ExtendTo`, which keeps whichever end the
cursor is not at. Each is replayed against its own recording.

**A password field moves by word to an end.** With `show` set, Entry and
ttk.Entry go to the start or the end on Control-Left and Control-Right,
because each script checks `winfo class` for its own class. ttk.Combobox
and ttk.Spinbox share the procedure and fail the check, so they move by word
with `show="*"`, measured on `ab cd ef`. Classic Spinbox has no `show`.

**A hidden field keeps its contents out of Python strings.** A `str`
cannot be overwritten, and freeing one does not clear it. Measured on
2026-11-22, before the change: ten characters typed key by key into a
`show="*"` Entry, then `delete(0, "end")`, `destroy()` and
`gc.collect()`, and every readable mapping scanned through
`/proc/self/mem`. The whole password was there twice more than in a run
that typed nothing (the control counts the probe's own search strings).
Typing made it worse than holding one string would: `TextField` rebuilt
its `str` on every insert, and `Entry.insert`, `delete` and the key
bindings each built the *proposed* text for validation on every key, even
with `validate="none"`, so each prefix was a string of its own.

So with `show` set, `TextField` holds a `SecretBuffer`
(`_core/wipeable.py`): one 32-bit code point per character, in memory from
`sodium_malloc` when the system has libsodium, or an anonymous `mmap`
otherwise. It is locked with `mlock` (or `sodium_mlock`), kept out of core
dumps, and zeroed on delete, on growth, when `show` is emptied and on
`destroy()`. The validation text is built only when a validator will read
it. Drawing, motion and word selection read the length or one character
at a time. `Entry.secret()` encodes UTF-8 into a second region of the
same kind and wipes it when the `with` block ends.

After the change, the same scan finds no copy in a string's form while the
entry holds the password, where it used to find one every run; that is
what `tests/test_entry_hidden.py` holds. Freed strings are not compared
after the entry is gone, because whether one survives depends on what the
allocator reuses: the first measurement found two, and a later one on the
same code found none. `get()`, a `textvariable` and validation still hand
out a `str`, as tkinter's API says they must, and
`docs/reference/hidden-fields.md` says so to the programmer.

**Up and Down in a Spinbox step it**, through `<<PrevLine>>` and
`<<NextLine>>` in a classic one (`invoke buttonup`) and as the keys
themselves in a ttk one, where `<<PrevLine>>` is TEntry's binding that does
nothing: `event_generate("<<PrevLine>>")` steps a Spinbox and leaves a
ttk.Spinbox alone. In an Entry the two events do nothing.

**In a Text**, measured, in the order the replay found them:

- **Up and Down keep a column** for as long as the cursor stays where the
  last press left it (`tk::TextUpDownLine`'s `Priv(prevPos)` and
  `Priv(textPosOrig)`, global in Tk and one per Text here), so Down through a
  short line comes back out where it went in.
- **Above the first row is that row's start. Below the last it depends on
  the column**: `9.0 + 1 displaylines` is `10.0`, which is `end`, and
  `9.1 + 1 displaylines` is `9.7`, the last character. A plain Down lands on
  the character either way; Shift-Down from the first column selects the
  final newline as well.
- **End on a row that wraps is that row's last character** - the space a
  word wrap broke at, or the last letter of a word broken across rows -
  because the index after it starts the next row. End at 5.10 in a 16-column
  `fourth_word-joined end` goes to 5.15. At the end of a line it is the end
  of the line, trailing spaces included; ours used to stop before them.
- **Control-Left reads backwards a line at a time** (`tk::TextPrevPos`), and
  hands the word procedure `end`, which in Tk 9's C is the last character and
  not the length: `startOfPreviousWord` on `\nx` answers 0 from `end` and 1
  from 2. So from 7.1, on a line holding `x` below one of spaces, it goes to
  6.3, the end of the line above.
- **Control-Up and Control-Down go by paragraph** - a line following an
  empty one, past its leading blanks (`tk::TextPrevPara`, `tk::TextNextPara`).
  A line of spaces is not empty.
- **Prior and Next go by the view**, not the cursor - see "Paging a Text".

**Kept different on purpose**: classic Tk reports a selection a Shift-move
ran onto its own anchor as present and empty - `sel.first` equal to
`sel.last` - after which BackSpace deletes nothing. Ours has no selection
there (see `TextField.select_to`). The replay compares that step as no
selection, and one run whose later steps follow from it is marked as
expected to differ.

**Index modifiers apply left to right**, measured on Tk 9.0.2:
`3.0 lineend +1c` is `4.0` and `3.2 +1c lineend` is `3.3`. Ours used to take
`linestart`, `lineend`, `wordstart` and `wordend` off the end first, which
refused the first form and would have reversed it - and `text.tcl`'s own
procedures are written that way. Tk tries the whole string as a mark before
splitting it, so a mark may be called `my-mark`, and then `my-mark +1c` is
no index, because the base ends at the first space or sign. Units abbreviate
(`+1c`, `+2 ch`, `- 1 l`), `indices` counts as `chars` here - a buffer holds
no embedded windows - and `any` before a unit changes nothing. `display` is
refused: the buffer does not know how the lines wrap. Ours still accepts a
leading space, which Tk refuses.

### Paging a Text

**Prior and Next are `tk::TextScrollPages`**: scroll the view a page, then
put the cursor where it was on screen, with Shift extending the selection;
Control-Prior and Control-Next scroll sideways a page and leave the cursor
(`TkCurses-5co5`). Held to `tests/support/page_keys.json` - 450 runs
recorded from Tk 9.0.2 of Prior and Next under every modifier, the arrows,
and the program scrolling and moving the cursor, in Texts four and twelve
rows tall and one wrapped at a word, with the view after every step. All of
them replay alike, but for five (below). Getting there took the rest of
this section, each measured:

- **A page is Tk's, measured**: three quarters of the height while a line
  is a quarter of it or more, otherwise the height less two lines - 1, 1,
  2, 3, 3, 4 rows for heights 1 to 6, 8 for 10. Sideways, the width less
  two, and nothing in a Text two wide or less. It is `yview scroll 1 pages`
  itself, so a Scrollbar's trough moves the same. Ours went a whole height.
- **`see` scrolls the least only near the view**: up to `max(3, height //
  3)` rows past it, `max(3, width // 3)` columns sideways. Further, it
  centres - the row `(height + 1) // 2` from the top, the column `width //
  2` from the left - and sideways it never goes past the end of the widest
  row then in view at the right edge (see "A Text's view through an edit"). Measured at heights 1 to 18 and widths 9 to 30. A Text
  one row tall keeps the row in view, where Tk's pixel centring leaves it
  half out. Ours always scrolled the least.
- **An `@x,y` outside the text area is clamped into it**: above it the top
  row's first visible character, whatever `x` is; below it the last row's
  last; beside it the nearest visible column. `TextScrollPages`, for a
  cursor off screen, answers `@[winfo height / 2],0` - an x that is a
  height, in the border above the text - which this rule turns into the top
  row's start. Ours read the line above the top.
- **The last character of a row has a box to the right edge**: the newline,
  or the space a word wrap broke after. It runs from where the character
  is, off the left edge if need be, to that edge; past the edge it is a box
  of no width on it. So a cursor at the end of a long line, scrolled out of
  view to the right, pages to the right edge. Every other character beside
  the view has no box - except a space hanging past the edge of a wrapped
  row, which has one where it would be, with a negative width.
- **Spaces after a word that fills a row hang past the edge**, however
  many: `aaaaaaaaaaaaaaaa   bbb` in sixteen columns is one row to the third
  space, and `alpha beta gamma` in ten is `alpha beta ` and `gamma`. Ours
  moved the word to the next row, to keep the space off the border;
  nothing draws past the edge, so it cannot get there.
- **Past the end of a wrapped row is its last character**, for a click, an
  `@x,y` and Up and Down, not the next row's first.
- **A wrapped Text does not scroll sideways**, by any command.
- **Neither `mark_set("insert")` nor a program's `insert` moves the view**,
  in Tk; the bindings call `see`, typing among them. Ours did both, which
  is also why a page from a cursor the program had put off screen went to
  the wrong place. Programs that relied on it - three of the tty tests -
  now say `see` themselves, as they would have to under Tk.

**The five left are Tk remembering a page.** After `yview scroll 1 pages`
forwards, Tk's `see` reaches one row further up than from the same view
reached a row at a time: from a top of 7.0 in four rows, `see 3.3` puts
3.0 at the top after a page and then three units, and 1.0 after six units.
It lasts until a page back or a `moveto`, and in a wrapped Text a page back
does the same downwards. Something below the row the view shows - a
partly scrolled line, perhaps - that a view kept in rows has nowhere to
hold. The replay marks those five as expected to differ.

### A Text's view through an edit

Tk keeps a Text's view as an index - the start of its top display line -
and works out what to draw from it. Ours kept a row number, so text put in
or taken out above the view slid what it showed (`TkCurses-ntu4`). Now a
hidden mark of each view's own holds the index (`TextBuffer.view_top`, never
in `mark names`) and the row is worked out from it whenever the text or its
layout has changed. Held to 300 runs recorded from Tk 9.0.2
(`tests/support/record_text_view.py` → `text_view.json`), each scrolling a
Text 16 by 4 - one unwrapped, one wrapped at a word - and editing it by
itself and through a peer, with the top and `xview` after every step. All
300 replay. Measured, and each a rule:

- **The mark has left gravity**: text inserted exactly at the top shows
  there; text inserted anywhere before it moves it on, in its own line too
  (a view at 14.8, the second row of its line, is at 14.12 after four
  characters go in at 14.0). A peer's edits and an undo's move it as any
  edit does.
- **A deletion across the top takes it to where the deletion began**, and
  is then its row's start: 9.0 to 12.0 over a view at 11.0 is 9.0; 10.3 to
  11.4 is 10.0.
- **Except a deletion that ends on the top's line, before it, from an
  earlier line**: `DeleteIndexRange`, in `tkText.c` (read in Tk 9.1a1's
  source, after measuring), keeps the line number of the
  deletion's END and takes its character off the top's - the old line
  number, read in the new text. A view at 17.24, less 2.3 to 17.10, is at
  17.14 - a row of whatever is line 17 now - not 2.17 where its text went.
  So a view at 15.8, less 14.0 to 15.0, is at 15.0. It looks like a Tk
  defect, and it is the rule (`_Store._top_after_delete`).
- **A view left short is pulled up to fill, and stays up**: at 31.0 of
  forty lines in four rows, deleting 33.0 to the end shows 29.0, and lines
  added after that leave it there. Tk resets its top index; ours used to
  keep drawing from the row it was clamped to and went back down.
- **Resizing, rewrapping, tag margins and tabs** change the rows and leave
  the top on its line - measured at width 7 (rows above it 27 to 38), tabs
  of 30 (27 to 29) and a margin of 8 (24 to 32). Tag margins change the
  rows without changing the text, so a Text with any recomputes its top
  from the index at every reading rather than when its layout key changes.
- **Sideways, the view goes as far as the widest row on screen**
  (`TkCurses-8tjr`): the end of it at the right edge, margin and tabs
  counted, and `xview` is a fraction of that width - `(0, 1)` when it fits.
  At column 40 of a line of 60, moving to rows 30 wide takes it to 14, and
  to short rows takes it to 0, where it stays when the long line comes
  back. It is bounded whenever the view moves vertically, as Tk's layout
  is, not only when read: by way of the top, a view comes back at 0. A
  wrapped Text, even one with a space hanging past the edge, never scrolls
  sideways and is `(0, 1)`; unwrapped again, it is at 0. Ours bounded it by
  the longest line in the text and kept a wrapped Text's offset.

A row of `spacing1` or `spacing3` is a row of its own here and part of its
line's height in Tk, whose `yview scroll` never stops inside one. A view
that starts in such spacing keeps its place in it, as the text Tk shows
keeps its place.

Left: Tk's `xview moveto` goes to a fraction of a pixel, part way across a
character, which a cell cannot - the recorder moves to 0 and 1 only.

### Undo and redo in a Text

Each recorded edit is two of Tk's undo atoms (`TextPushUndoAction`, in
`tkText.c`): the edit, then `mark set insert` and `see insert` **in the
widget that made it** - before text taken out, after text put back. So
undoing a peer's edit moves the peer's cursor, not this one's. Measured on
Tk 9.0.2: three lines put in at 1.0 with the cursor at 30.0, undone, leave
the cursor and the view at 1.0; `delete 2.0 4.0` undone leaves it at 4.0,
and redone at 2.0.

`edit undo` and `edit redo` answer the ranges they changed, flat, as
`tk::TextUndoRedoProcessMarks` (`text.tcl`) makes them: a left-gravity mark
at each edit's start and a right-gravity one at its end, read once the group
is done, sorted and merged. The merge compares each range by the end it
started with, not one it was extended to, so an edit inside the extension is
answered on its own - kept as the script has it. With `-undo false` both
answer `()`, where tkinter answers `""`.

**Groups.** Tk keeps `-autoseparators` and the kind of the last edit in the
text its peers share (`lastEditMode`): any recorded insert or delete,
programmatic or a peer's, that switches kind starts a new group. text.tcl's
bindings add separators of their own - after Return, not before it; either
side of typing over the selection, which `tk::TextInsert` makes one group
by turning autoseparators off around it; on `tk::TextSetCursor`, a
Control-click and `<<SelectNone>>`. And `tkUndo.c`: `TkUndoApply` puts a
separator on the undo stack before it looks, so even a redo with nothing to
redo ends the group being made; `TkUndoRevert` pops the separator below the
group it takes back and frees it, so with autoseparators off the next edit
**joins the group below** - `x`, a separator, `y`, undo, `z`, and the next
undo takes `z` and `x` together. Ours kept the switch per widget, on the key
paths only, and broke the group before a newline (`TkCurses-hy15`).

**The keys** are tk.tcl's for X11 and text.tcl's bindings: `<<Undo>>` is
Control-z and `<<Redo>>` Control-Shift-z, and a Text binds both, the undo
with a separator either side and neither an error when there is nothing to
do. Measured on Tk 9.0.2, neither Entry nor any ttk entry binds them. Three
things a terminal changes (`TkCurses-5t48`):

- **Control-z is the tty's suspend key.** It is taken from the tty only
  while a Text with `-undo` true has the focus and `<<Undo>>` or `<<Redo>>`
  is on Control-z - the focused widget's `_claimed_signal_keys`, read on
  every focus change, `-undo` change and `event add`/`delete`. Everywhere
  else Control-z still suspends the program.
- **Control-Shift-z is the byte Control-z is**, 0x1A, so it arrives only
  from a terminal that reports modifiers. So the Text also binds
  `<Alt-Key-z>` to redo - a terminal sends Alt-z as Escape and `z`, which the
  input layer reads back as one key with Alt (see "Alt from a terminal"). A
  binding of ours, not one of `<<Redo>>`'s sequences. It was a two-key
  sequence, Escape then `z`, until Alt was read as Alt; that had no time
  limit, so Escape and a later `z` redid too, and now they do not.
- **The Lock forms are left out**: Caps Lock does not change the byte.

**Deliberately unlike Tk**, a disabled Text's undo changes nothing, moves no
cursor and answers `()`; Tk's pops the group while refusing its edits
(`TkCurses-aah`).

Held by a replay of 200 runs recorded from Tk (`tests/test_text_undo.py`).
One thing the recorder has to correct for: Tk centres in pixels, and a
centring `see` leaves the top line part out of the window - the bottom of
the centred line goes to `(dInfoPtr->y + dInfoPtr->maxY + lineHeight)/2`
(`TkTextSetYView`, in `tkTextDisp.c`), which with Tk's 3-pixel inset is
never a line boundary. The next `see` then measures from the pixel: from
16.0 reached by `yview`, `see 23.8` shows 21.0, and from 16.0 reached by
centring, 20.0. A terminal has only the first, so the recorder wraps each
widget's command to follow every `see`, the undo atoms' own included, with
`yview` to the first index on screen (`TkCurses-2sbq`).

### Deleting to the end of a Text

A range from the start of a line through the final newline is whole lines
to Tk's `DeleteIndexRange`: the newline before it goes too, and becomes the
final one, losing its tags. Measured on Tk 9.0.2, `a\nb\nc` less `2.0` to
`end` is `a\n`, a tag over all of it ends at 1.1, and a mark at 2.0 goes to
1.1. Less `2.0` to `3.end` - short of the final newline - it is `a\n\n`;
less `2.1` to `end`, `a\nb\n`; and a range wholly past the end deletes
nothing. Ours left an empty last line, which put a view clamped to the end a
line out (`TkCurses-ydr6`).

### Cell Structure

```python
@dataclass
class Cell:
    char: str = ' '           # Character to display
    fg: str = 'white'         # Foreground color
    bg: str = 'black'         # Background color
    attr: int = A_NORMAL      # Attributes (bold, underline, etc.)
    dirty: bool = False       # Needs redraw
```

### Wide and combining characters

**A character is not a cell** (`TkCurses-2by7`). A terminal gives a CJK
ideograph, a fullwidth letter or most emoji two cells, and a combining mark
or a zero-width character none - it joins the cell before. Measured in the
test harness's terminal (pyte, which follows `wcwidth` as terminals do,
`TERM=xterm-256color`): `Label(text="A日本語B")` drew `A日本`, five cells
allotted for five code points; `x😀y` lost the `y`; `é` written as `e` plus
U+0301 left a blank cell after it.

`_core/cells.py` gives the widths, from Python's own Unicode database by
the rules of Markus Kuhn's `wcwidth` and the `wcwidth` package's refinements
(spacing marks and the Hangul medial and final jamo are 0, regional
indicators 2), so no table of ours goes stale and nothing new is a
dependency. Its tests check each sample against `wcwidth` itself when it is
installed, as it is wherever pyte is. Three helpers do the arithmetic:
`cells` measures, `clip_cells` keeps the start that fits without halving a
wide character, and `skip_cells` drops the start and reports the blank cell
left where a wide character straddled the cut.

What measures in cells so far: `_write_line`, which every widget draws
through - so nothing overruns its window, and a wide character ending in a
window's last cell is inserted where it starts rather than at the last
cell; `clip_text`; `wrap`, `measure` and so `wraplength`; and the Label
family's anchoring, justification, cutting and underline (Label, Button,
Checkbutton, Radiobutton, Menubutton, Message and their themed forms).
So does the `curses` compatibility module (`TkCurses-z9eg`), the one
thing that writes through `ScreenBuffer.write`, which now lays text out
in cells - an ideograph in its first cell and `""` in its second, which the repaint skips; a combining mark joined to the cell
before it, and painted with `addstr`, since `addch` takes one code point -
and `addstr`, `addnstr`, `addch`, `insstr` and `insch` move the cursor and
shift the line by cells. Writing over half of an ideograph follows ncurses,
measured by running one program under both modules in the harness and
comparing the screens (`test_wide_text_draws_the_same_thing_either_way`):
over its first cell, the second is blanked; over its second, the first is
left as it was.

**The widgets that lay out rows and columns of their own**
(`TkCurses-r9k2`): Listbox, Scale's label, Menu and menubar, ttk.Notebook's
tabs, ttk.Treeview, Canvas text, LabelFrame's caption, Message's `aspect`
and `font.Font.measure`. Each measured with `len()`; each now measures with
`cells` and pads with `pad_cells`, which is `str.ljust` in cells and leaves
a space where a wide character would straddle the end. Two consequences
worth knowing:

- A Treeview cell is cut at its column. It was padded with `ljust`, which
  pads and never cuts, so a value longer than its column - ASCII included -
  pushed every column after it out of line under its heading.
- A Notebook's strip and a Canvas's composed cells are built one entry per
  cell. A wide character goes in its first cell and `""` in its second,
  which joins to nothing and which `_write_line` skips, so the terminal's
  own drawing of the character fills it; a combining mark is appended to
  the cell before.

**The entries** (Entry, Spinbox and the ttk entries, `TkCurses-9t4l`).
Indices and the view's first character stay characters, as Tk's API needs;
`TextField` turns them into columns through a `measure` function, which an
entry replaces with one that counts the mask when `show` is set - one
asterisk a character, whatever it hides. A click on either half of a wide
character names it; the cursor stands on the first of its cells; scrolling
to the cursor makes room for both. The view never starts on a combining
mark, which has no cell of its own. `xview`'s fractions and its pages are
cells, as Tk's are pixels - measured on Tk 9.0.2 with `TkFixedFont`, an
ideograph is 13 pixels to a letter's 8 and the fractions follow the pixels,
not the characters. A page that would end inside a wide character goes on
past it; rounding back would leave a page of ideographs one short each
time.

**Text** (`TkCurses-l8w7`). Indices stay characters; rows, columns and
the view are cells. `wrap_spans` breaks a non-ASCII line by a running sum
of cells and a binary search per row, cached by line because a Text lays
out every line on every redraw. A character wider than the whole row
still takes a row of its own: without that the loop never advances, and
when the guard was switched off to check its test, the test session grew
to 10 GB and was killed by the kernel - so the test runs that case in a
child process capped at 512 MB and 20 seconds. A row is drawn from
`textlayout.glyphs`, one entry a cell, with the character each cell shows
beside it; tags are looked up by that character, so a tag colours both
halves of an ideograph, and half of one at a scrolled edge is a blank.
Up and Down keep the column in cells, as Tk keeps the x position, and a
numeric tab aligns on the cells before the point.

### Screen Buffer

```python
class ScreenBuffer:
    cells: list[list[Cell]]   # 2D grid [row][col]
    width: int                # Columns
    height: int               # Rows
    dirty_regions: list[Rect] # Changed areas

    def write(self, row: int, col: int, char: str, attr: int = A_NORMAL) -> None: ...
    def fill(self, rect: Rect, char: str, attr: int = A_NORMAL) -> None: ...
    def get_dirty(self) -> list[Rect]: ...
    def clear_dirty(self) -> None: ...
```

### Container Sizing

A container's **requested** size includes its own border, `padx`/`pady` and
menubar row. The geometry managers report what the *children* need, which is
a content size, and children are laid out in `_content_rect()` — which
subtracts all three. `Misc._outer_size()` adds them back and the layout
engine propagates that.

Without it a bordered container sized to its children clipped them by exactly
its border: a bordered frame holding three stacked rows reported that it
needed three rows, drew a border on the first and last, and showed one.

`_outer_size` asks `_bordered`, never `_border_drawn`. Whether a border is
*drawn* depends on the size the widget already has, so asking that here would
be circular — a frame one row tall draws no border, would ask for no room for
one, and would stay one row tall.

**A container may state its own request** (`TkCurses-bell`). The layout
engine propagates what pack, grid or the panes report; `place` reports
nothing, as in Tk. A ttk.Notebook places its pages, so it asked for
nothing. A container with an `_own_request()` method has that propagated
instead - the Notebook's is its largest page shown, its border and the
tab row - and the engine already lays it out again when a placed page's
request changes, so a page whose size depends on its own children is
counted once that is settled.

### X11 to Curses Color Mapping

TkCurses translates tkinter's X11 color names to curses colors. The
ColorManager handles this mapping and creates curses color pairs.

#### Color Depth

A terminal has one of four amounts of colour, and which one decides how a
colour is resolved. `ColorDepth` names them and `detect_depth()` works out
which is in front of us, from `tigetnum("colors")` and `tigetflag("RGB")`
before a screen is up, and from `curses.COLORS` once `start_color()` has run:

| Tier | Colours | Terminal |
|------|---------|----------|
| `NONE` | none | `vt100`, `dumb` |
| `BASIC` | 8 | `xterm`, `linux` |
| `BRIGHT` | 16 | `xterm-16color` |
| `EXTENDED` | 256 | `xterm-256color`, `screen-256color` |
| `DIRECT` | 2^24 | `xterm-direct` |

An unrecognised count rounds **down** to the tier below it - 88-colour rxvt
is treated as 16 - because asking for a colour the terminal has not got puts
the wrong colour on the screen, while asking for one fewer costs only
accuracy.

`COLORTERM=truecolor` is *not* consulted by `detect_depth()`, for two
reasons that are worth keeping apart.

The mechanical one: it promises that the terminal emulator understands 24-bit
escape sequences, not that ncurses is in direct mode, and acting on it would
send `0xRRGGBB` colour numbers to a curses that expects 0-255.
`truecolor_hinted()` reports it separately, for anything that later writes
escape sequences past curses.

The second is that **honouring it would currently make pictures worse**, not
better — see **Why more colour can mean a worse picture** below. That is the
one that keeps it switched off now that `TkCurses-3g8` has made the effect
measurable, and `TkCurses-bvu` is the work that changes it.

`Misc.winfo_colordepth()` is how a widget asks. It is not tkinter's - X has
no equivalent question, because a display answers `winfo_screendepth()` in
bits per pixel and has the full range either way.

#### Base Color Mapping (8 colors)

| X11 Name | Curses Constant | Value |
|----------|-----------------|-------|
| `black` | `curses.COLOR_BLACK` | 0 |
| `red` | `curses.COLOR_RED` | 1 |
| `green` | `curses.COLOR_GREEN` | 2 |
| `yellow` | `curses.COLOR_YELLOW` | 3 |
| `blue` | `curses.COLOR_BLUE` | 4 |
| `magenta` | `curses.COLOR_MAGENTA` | 5 |
| `cyan` | `curses.COLOR_CYAN` | 6 |
| `white` | `curses.COLOR_WHITE` | 7 |

#### Colour names

**Every name Tk knows is known here, and no other.** The table is Tk's own,
the 665 names in its `xlib/rgb.txt` - the X11 set with Tk's changes, `gray`
the web's 128 and `aqua`, `crimson`, `indigo` and the rest added - in
`_core/x11colors.py`. Until `TkCurses-f760` there were 28, and a name outside
them (`SteelBlue`, `gray90`) was stored unchecked and raised when the widget
was drawn, in the middle of laying the window out: everything packed after
it was never placed.

**How a name is read is not in Tk's manual, and differs by platform.** On
Windows and macOS, Tk's `colorcmp` (`xlib/xcolors.c`) ignores case and allows
a single space only where its own spelling has a capital: `steel blue` and
`light goldenrod yellow`, but not `steelblue `, `steel  blue` or `gray 50`.
On X11, Tk resolves a few web colours itself and asks the X server for the
rest, and the server is stricter: it knows each multi-word name spaced at
every word or at none, and a numbered one only unspaced, so `antique white`
but not `antique White1`. The rule here is `colorcmp`'s. Measured against Tk
9.0.2 under X11, with every name in three cases and a space at every
position, 9,490 spellings: every one X11 accepts is accepted here with the
same RGB, and the 260 partly spaced ones it refuses are accepted, as Tk on
Windows and macOS accepts them. The server also has a few names Tk's table
lacks (`web gray`, `x11 gray`); a program using one runs only on X11 under Tk
too, and they are not here.

**An unknown name is refused when it is set**, `unknown color name "x"`, as
Tk refuses it: every widget colour option, a Text tag's colours and a Canvas
item's `fill` and `outline`. A ttk style is the exception, and that is Tk's
too: `Style.configure` takes any value, and a widget whose style names an
unknown colour is drawn without it - measured, no error at either point.

#### Extended X11 Color Approximations

At `BASIC` these are the named approximations, with brightness carried as an
attribute:

| X11 Name | Maps To | Notes |
|----------|---------|-------|
| `gray`, `grey` | `white` + `A_DIM` | Dimmed white |
| `lightgray`, `lightgrey` | `white` | Standard white |
| `darkgray`, `darkgrey` | `black` + `A_BOLD` | Bright black |
| `orange` | `yellow` | Nearest approximation |
| `pink` | `magenta` | Nearest approximation |
| `purple`, `violet` | `magenta` | Nearest approximation |
| `brown` | `yellow` + `A_DIM` | Dimmed yellow |
| `navy` | `blue` + `A_DIM` | Dimmed blue |
| `lime` | `green` + `A_BOLD` | Bright green |
| `aqua`, `turquoise` | `cyan` | Nearest approximation |
| `maroon` | `red` + `A_DIM` | Dimmed red |
| `olive` | `yellow` + `A_DIM` | Dimmed yellow |
| `teal` | `cyan` + `A_DIM` | Dimmed cyan |
| `silver` | `white` | Standard white |
| `fuchsia` | `magenta` + `A_BOLD` | Bright magenta |

**A_BOLD brightens a foreground and does nothing whatever to a background.**
That is a curses fact, not a TkCurses choice, and it is why brightness stops
being an attribute as soon as there is somewhere better to put it. From
`BRIGHT` up a name is resolved through the RGB it renders as, and `lime`
becomes colour 10 with no attribute - so a bright *background* works, which
at `BASIC` it cannot.

It follows that **a background at `BASIC` must be matched against a smaller
palette** - the eight that need no attribute. Dropping the attribute is not
enough on its own, because the *colour* was chosen on the strength of it.
Measured, the mid grey `#828380` at the centre of a gradient resolved to
black plus `A_BOLD`, meaning grey 127, and arrived behind text as `(0, 0, 0)`
— the single furthest of the eight, when yellow, cyan, magenta and white were
all nearer. Every cell whose lower half was a mid tone painted that half pure
black, so a gradient came out striped. `parse_color(..., background=True)`
is what asks the right question.

**And that correction needs a second one.** Restricting only the background
leaves the two halves of a cell drawing from two different palettes, so the
*same* colour gets two answers depending on which half it lands in:

    #1e5c80  as a foreground -> black + A_BOLD, meaning grey 127
    #1e5c80  as a background -> blue

Two pixels six levels apart in green then come out as grey over blue, and a
smooth gradient is drawn as hard horizontal stripes. This was reported
against `big.png`, and the per-pixel error was not what was wrong - grey over
blue scores *better* than either colour alone. The incoherence was.

So at `BASIC`, when a cell's two halves are closer to each other than to
their own approximations, both are answered from the background's palette:
they agree, the cell is one flat colour, and a smooth region stays smooth. A
cell whose halves genuinely differ keeps its bright foreground, so edges are
untouched.

There is deliberately **no threshold** in that rule. The comparison is made
against the error already being accepted, which scales by itself: at eight
colours almost everything smooth falls below the palette, and at 256 almost
nothing does. Above `BASIC` the rule does not apply at all, because
brightness is a colour number there and both halves already draw from the
same sixteen.

`red` is `#cd0000` at every tier. A better terminal gets closer to what was
asked for; it does not change what was asked for.

#### Hex Color Conversion

A hex colour is matched against the palette the tier has **by perceptual
distance, in DIN99d** - a uniform colour space, meaning one where a straight
line between two colours is proportional to how different they look. That is
precisely the question "which of these is nearest" is asking, and it is not
a question RGB can answer.

This used to be a weighted RGB distance, green counted most and blue least,
as a stand-in for perceived brightness. It is a reasonable guess and it is
measurably not good enough, because it cannot account for the eye's
sensitivity varying across the space. Scored perceptually against the source
over every distinct colour in a picture:

| Picture | Depth | weighted RGB | DIN99d |
|---------|-------|--------------|--------|
| mickey.gif | 8 | 76.38 | **68.72** |
| mickey.gif | 256 | 33.40 | **27.53** |
| earth.gif | 256 | 27.40 | **23.23** |
| gradient.png | 8 | 119.60 | **65.68** |
| gradient.png | 16 | 70.38 | **47.93** |

Better on every picture at every depth. The smooth gradient is the extreme
case - the two metrics disagree there about **two thirds of the time**, and
the perceptual answer is 45% closer at eight colours.

**The visible consequence to know about: `#ff8000` resolves to bright red at
eight and sixteen colours, not to yellow.** Measured, orange is 50.96 from
bright red and 85.31 from yellow, so red is 1.67 times nearer. The old
weights chose yellow because orange's green channel sits half way to
yellow's and green was counted four times over. At 256 the question does not
arise: cube entry 208 really is orange.

sRGB is linearised before any of this (`to_linear`), because sRGB is not
linear in light and a colour space built on the raw bytes is measuring the
wrong thing. The same function is what makes `PhotoImage.reduce()` average
light rather than bytes.

Costs, and how they are paid: the conversion has a cube root, a logarithm
and an `atan2`, so it is cached at both ends - the palettes convert once,
and each distinct colour resolves once. `_nearest_extended` now walks all
256 rather than solving the 6x6x6 cube per channel, because **that shortcut
is only valid for a separable metric and a perceptual one is not**. Measured
on a full-screen photograph: 69ms once for 1250 distinct colours, 1.2ms on
every repaint after.

At `DIRECT` no matching happens at all, so none of this applies:

| Tier | Palette | `#ff8000` resolves to |
|------|---------|----------------------|
| `BASIC` | the 8, brightness as `A_BOLD`/`A_DIM` | colour 1 + bold, bright red |
| `BRIGHT` | the 16 as colour numbers | colour 9, bright red |
| `EXTENDED` | 16 named + 6x6x6 cube + 24 greys | colour 208, `#ff8700` |
| `DIRECT` | none; the number *is* the colour | `0xff8000`, exactly |

As a *background* at `BASIC`, orange is plain red rather than bright red -
the attribute cannot follow it there. See the note under Extended X11 Color
Approximations.

#### The 256-colour palette

`EXTENDED` is built rather than listed: a table of 256 triples is 256 chances
to mistype one, and xterm's own arithmetic is short. Its cube levels are not
evenly spaced, which has to be matched or every dark colour lands a step out:

| Range | Description |
|-------|-------------|
| 0-7 | The 8 base colours |
| 8-15 | Their bright counterparts |
| 16-231 | 6x6x6 RGB cube, levels `(0, 95, 135, 175, 215, 255)` |
| 232-255 | 24 greys |

A colour number resolves back to RGB through the same arithmetic, which is
what lets a pair be compared against a colour that was asked for.

#### Color Pair Management

Curses cannot paint a colour; it paints a **pair**, and a pair is a
*combination* of foreground and background. `ColorManager` allocates them on
demand and caches by `(fg, bg)`.

**There are at most 255 of them, and that is the tightest constraint in the
whole colour system.** Two different numbers describe the supply, and using
the wrong one silently ruins the screen:

| | What it means | Typical value |
|---|---|---|
| `COLOR_PAIRS` | how many pairs the terminal will **create** | 65536 |
| `A_COLOR` | how many an attribute can **name** | 8 bits, so 256 |

`curses.color_pair()` packs the pair number into the `A_COLOR` field, and the
field is eight bits wide, so past 255 **the number wraps rather than
failing**. Measured on `xterm-256color`: `color_pair(256)` is 0 — the
terminal's default colours — `color_pair(257)` is pair 1, and
`color_pair(300)` is pair 44. Cells come out painted in some unrelated pair's
colours while every call reports success: the allocation succeeded,
`init_pair` succeeded, and `exhausted` stayed `False`.

So the ceiling is `min(COLOR_PAIRS, (A_COLOR >> 8) + 1)`, and it is the
second term that binds. This is not a tuning parameter. The pair number is
stored per cell, so pairs cannot be recycled within a frame the way a palette
entry could be.

**The ceiling is Python's, not the terminal's**, which is worth knowing
before anyone tries to raise it. ncurses 6 will create 65536 pairs and has
`init_extended_pair()` for naming them; Python's `curses` does not expose it,
and `curses.color_pair()` packs the number into eight bits. Measured on a
real terminal: `init_pair(300, …)` succeeds, `color_pair(300) >> 8` is 44,
and a cell painted with it shows pair 44's colours.

That limit was the dominant cost when drawing a photograph, and it is why a
renderer that writes its own escape sequences beat this one. chafa has no
pair table at all. Measured at 106x33 cells, scored perceptually against a
Lanczos reference:

| | TkCurses, before | TkCurses, now | chafa |
|---|---|---|---|
| mickey.gif | 35.06, 14 colours | **6.88, 1793 colours** | 11.78, 1778 |
| earth.gif | 62.96, 10 colours | **6.54, 4309 colours** | 7.48, 3785 |

**Images are now written past curses**, in whichever form the terminal
understands — see `_core/direct.py`. Where `COLORTERM` says it takes direct
colour, `ESC[38;2;r;g;b`; where it merely has 256, `ESC[38;5;N` against the
palette. **Both matter**: a palette terminal has no pair ceiling either once
the sequences are written by hand, and going through curses costs it just as
much.

| 106x33, vs Lanczos | TkCurses | chafa |
|---|---|---|
| mickey.gif, 256 | **25.03**, 88 colours | 33.16, 88 colours |
| mickey.gif, truecolor | **6.88**, 1793 colours | 11.78, 1778 |
| earth.gif, 256 | **24.06**, 35 colours | 27.83, 36 colours |
| earth.gif, truecolor | **6.54**, 4309 colours | 7.48, 3785 |

At truecolor the remaining error is the scaler alone: 6.88 is exactly what
`resize()` scores against the same reference before any colour is chosen.

Eight- and sixteen-colour terminals are left to curses, because 8x8 is 64
combinations and there is no ceiling to escape. `TKCURSES_DISPLAY_DIRECT_IMAGES=0`
turns the whole thing off, for a terminal that mis-renders the sequences.

**Two ways the overlay went stale** (`TkCurses-gdvq`), found as three
Checkbutton and Radiobutton options the option recorder could never settle -
`selectimage`, `tristateimage`, `compound` - because its after-baseline
differed from its before-baseline. Measured with `RECORD_DEBUG=1`:

- **A widget gone from the screen kept its cells.** Only drawing cleared a
  widget's entry, and a destroyed or unmapped widget does not draw, so its
  cells were written again over whatever replaced it the next time any
  picture changed - in the record, the rebuilt indicator `[x]` was covered by
  the old widget's glyphs, in `00cdcd` where curses would say `cyan`. The
  panel stack now calls `on_gone` with a panel's owner whenever it hides or
  destroys one, and the painter forgets that owner.
- **A frame that redrew a picture's widget did not repaint the picture.**
  The loop asked only the screen buffer whether anything was painted, and
  widgets draw on panels, so a frame in which curses rewrote a picture's
  cells in its nearest pair colours was taken as quiet, and the exact colours
  were not sent again. `PanelStack.update` now reports whether a window was
  touched or a panel shown, hidden, moved or restacked, and that counts.

`tests/test_widget_images_tty.py::test_a_picture_goes_with_its_widget` and
`::test_a_picture_is_painted_again_when_curses_repaints_it` fail against the
code before this. With both fixed the three options record as visible, three
runs out of three, and `tristateimage` - recorded as invisible - is drawn.

The pair table is still what widgets and text use, and still what an image
falls back on when the terminal has not said it takes direct colour. Its
ceiling has not moved; it just no longer decides what a photograph looks
like.

Running out is handled rather than ignored. `pair_number()` falls back to
`_nearest_pair()` — the closest pair already allocated, by the same weighted
RGB distance used everywhere else — and sets `exhausted`. It used to return
pair 0, which paints the terminal's default colours, so exhaustion turned
parts of a picture into whatever the background happened to be; an
approximate colour is a far better answer than an unrelated one.

That bug is worth remembering for its symptom rather than its cause. It
presented as *"the image is way off at 256 colours and fine at 8"*, which
sounds like a palette problem and is not one: eight colours never needs more
than a few dozen pairs, and an image at 256 runs through the lot.

#### Why more colour can mean a worse picture

**A richer terminal does not automatically produce a better image, and
measurement says it produces a worse one.** This is the counter-intuitive
result that shapes `TkCurses-bvu`, and it follows directly from the ceiling
above.

Quantisation to the 256-colour cube currently keeps us under the ceiling by
accident: it collapses an image's colours *before* the pair table sees them.
Remove it — which is exactly what direct colour does — and nothing collapses,
the table fills, and every cell after the 255th falls back to the nearest
pair already allocated. Measured on `earth.gif` reduced to 53x33 and drawn on
a real terminal, each cell compared against the colour the image asked for:

| Terminal | Inked cells | Distinct pairs | Mean error |
|----------|-------------|----------------|------------|
| 256 colours | 901 | 239 | **8.58** |
| truecolor | 845 | 257 | **20.09** |

Truecolor is worse by more than a factor of two, and draws fewer cells at all.

Pairs also do not scale with colours, so bounding one does not bound the
other by itself: `earth.gif` at full size is 253 colours but **8583** pairs,
because a pair is a combination. What caps pairs for a fitted image is the
cell count, not the palette.

**The decided answer is a collapse step that is chosen rather than
accidental: an image brings its own palette, sized to fit a pair budget, and
the entries of that palette are reproduced exactly.** See **Image colour and
the pair ceiling** under Image Classes for the measurements, and
`TkCurses-bvu` for the work. Until that lands, `detect_depth()` deliberately
ignores `COLORTERM`.

---

## Directory Structure

```
tkcurses/
├── __init__.py              # Core widgets (Tk, Button, Label, Frame, etc.)
├── __main__.py              # Module entry point, demo
├── colorchooser.py          # Text-based Chooser, askcolor()
├── commondialog.py          # Dialog base class
├── constants.py             # Widget + curses constants
├── dialog.py                # Simple dialog utilities
├── dnd.py                   # Drag and drop support
├── filedialog.py            # Text-based file dialogs
├── font.py                  # Font management (monospace)
├── messagebox.py            # Text-based message boxes
├── scrolledtext.py          # ScrolledText widget
├── simpledialog.py          # Text-based input dialogs
├── ttk.py                   # Themed widgets
│
├── curses.py                # Curses compatibility API
├── panel.py                 # Panel/window stacking
│
├── bargraph/                # BarGraph, a TkCurses-only widget
│   ├── __init__.py          # BarGraph: options, timer, painting
│   └── _*.py                # pure: model, scale, layout, render, decor...
│
├── _core/                   # Internal components
│   ├── __init__.py
│   ├── application.py       # Application (per-tree shared state)
│   ├── attributes.py        # Attribute handling (A_BOLD, etc.)
│   ├── bindings.py          # Sequence parsing, BindingTable, virtual events
│   ├── clipboard.py         # Selections (clipboard, PRIMARY)
│   ├── colors.py            # ColorManager (color pair mapping)
│   ├── config.py            # TkCursesConfig (INI file loading)
│   ├── dispatcher.py        # CursesDispatcher (thread serialization)
│   ├── errors.py            # TclError / TkCursesError
│   ├── events.py            # Input event types, keysym translation
│   ├── geometry.py          # Cell geometry calculations
│   ├── input.py             # InputHandler (getch/getmouse)
│   ├── panels.py            # PanelStack (curses.panel wrapper)
│   ├── screen.py            # CursesScreen wrapper
│   └── timers.py            # AfterQueue (after/after_idle)
│
└── py.typed                 # PEP 561 type hint marker
```

---

## Dependencies

### Runtime (Standard Library Only)
| Module | Purpose |
|--------|---------|
| `curses` | Terminal rendering backend, input handling, color pairs |
| `curses.panel` | Window stacking, z-ordering, overlay management |
| `typing` | Type annotations |
| `dataclasses` | Data structures |
| `pathlib` | File dialog path handling |
| `os` | File system operations |
| `collections.deque` | Input event queue |

### Platform Notes for curses
| Platform | Availability |
|----------|--------------|
| Linux/macOS | Built-in with Python |
| Windows | Requires `windows-curses` package for reference testing |

**Note:** TkCurses does not require curses at runtime for end users. The curses module is used during development for:
1. API compatibility verification
2. Constant definitions (A_*, KEY_*, ACS_*, COLOR_*)
3. Panel management patterns
4. Behavioral reference testing

### Development
| Package | Purpose |
|---------|---------|
| `pytest` | Testing |
| `pytest-cov` | Coverage |
| `mypy` | Type checking |
| `ruff` | Linting/formatting |
| `windows-curses` | Windows curses support (dev only) |

---

## Constraints & Limitations

### By Design
1. **Monospace only**: All text uses terminal's fixed-width character cells
2. **No raster graphics**: the finest mark is half a character cell (see **The pixel**), so images and drawings are composed from `▀`, `▄` and `█` rather than rendered
3. **Single root window**: One TkCurses app per process (curses limitation)
4. **Half-cell precision**: a Canvas and an image address half-cells; *widget* geometry is whole cells only

### Thread Safety

**Curses is not thread-safe.** All curses calls must be serialized to the main thread. TkCurses enforces this through a centralized call dispatcher.

#### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Threads                           │
│     (may call widget methods from any thread)                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CursesDispatcher                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  _queue: Queue[Callable]   # Thread-safe call queue     │    │
│  │  _lock: threading.Lock     # Serialization lock         │    │
│  │  _main_thread_id: int      # Validate main thread       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    curses (single-threaded)                      │
│              (all calls execute on main thread)                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

See `src/tkcurses/_core/dispatcher.py` for the authoritative implementation.
Its shape is as sketched above — direct execution on the owning thread, a
queue for every other thread — with six corrections found while building it:

1. **Singleton creation is locked.** An unguarded `if cls._instance is None`
   lets two threads each construct a dispatcher, after which half the
   application serializes against the wrong lock. Creation is double-checked
   under a class-level lock.
2. **The owning thread is the interpreter's main thread**, taken from
   `threading.main_thread()`, not whichever thread happened to call
   `__init__`. Under lazy construction that could be a worker, which would
   then be treated as the screen's owner permanently.
3. **The lock is reentrant.** Compound operations may themselves dispatch; a
   plain `Lock` deadlocks the owner against itself as soon as calls nest.
4. **Outcomes are carried in separate value and error fields**, not inferred
   with `isinstance(result[0], Exception)`. A function that legitimately
   *returns* an exception object must get it back, not have it raised.
5. **Waiting threads are released on shutdown.** `close()` fails every queued
   and incoming call with `DispatcherClosed`. An unbounded `event.wait()`
   would otherwise hang a worker forever once the main loop has stopped,
   including in the window where a close races with a call being queued.
6. **`process_queue()` accepts a batch limit**, so a thread queueing work in
   a tight loop cannot starve input handling, and it rejects callers that do
   not own the screen.
7. **Queueing a call wakes the loop.** The loop sleeps in `select()` on the
   terminal between passes, up to 50 ms when no timer is due, and a call
   queued during that sleep waited for it to end. A widget method from a
   worker makes dozens of curses calls, each a round trip: measured, one
   `Listbox.insert` from a worker took 1.01 s, and a `Label.configure`
   0.2 s. The dispatcher now keeps a pipe, written each time a call is
   queued, which the loop's idle wait also selects on (`wait_for_input(...,
   wake=True)`); the same insert takes 2.7 ms. Only that wait listens: the
   short waits inside reading a key, a late reply or a paste do not, since
   a worker's call ending the 500 ms gap allowed inside a paste would cut
   the paste in two. The pipe is made when the loop first asks for it and
   closed by `close()`, under a lock that `_wake()` also takes, so a late
   wake can never write to a descriptor number the process has reused.
   Found by `tests/integration/test_worker_thread_tty.py`.

#### Usage Pattern

```python
# All curses operations go through dispatcher
dispatcher = CursesDispatcher.get()

# Direct curses call (serialized)
dispatcher.call(curses.addstr, row, col, text, attr)

# Compound operations (held under single lock)
def update_widget():
    stdscr.addstr(0, 0, "Header")
    stdscr.addstr(1, 0, "Content")
    stdscr.refresh()

dispatcher.call(update_widget)
```

#### Rules
1. **Never call curses directly** - always use `CursesDispatcher.call()`
2. **Main loop must call `process_queue()`** - typically in `mainloop()` iteration
3. **Callbacks execute on main thread** - `after()`, `bind()` callbacks are safe
4. **Widget methods may be called from a worker thread.** The method itself
   runs on the worker; each curses call it makes is carried to the main
   thread and waited for. `tests/integration/test_worker_thread_tty.py`
   holds the usual pattern: configure, insert, a variable and `after`
   from a worker while a person types.

### Platform Considerations
1. **Unix/Linux**: Full support via standard curses module
2. **macOS**: Full support via ncurses
3. **Windows**: Requires windows-curses package or WSL
4. **Terminal required**: Must run in a TTY environment (not GUI)

---

## Future Considerations

This list was written before most of it existed, and six of its eight entries
have since shipped. Kept as a record of what was planned, marked with where
it landed, because a list of "future" work that is mostly done is worse than
no list at all — it was still offering 256-colour support and image decoding
as ideas well after both had shipped and been accepted by a person.

| Planned | Where it is |
|---------|-------------|
| Theme system | `ttk.Style`, with `theme_names()` / `theme_use()` |
| Mouse support | `_core/input.py`; modes handled per `TkCurses-gyo` |
| Clipboard | `Misc.clipboard_get` / `clipboard_append` |
| Unicode box drawing | `_core/attributes.py`, the `BorderStyle` table |
| 256-colour | the `EXTENDED` tier; see **X11 to Curses Color Mapping** |
| Image file decoding | `_core/imagefiles.py` — PNG, GIF, netpbm, XBM |

Genuinely still ahead:

1. **Truecolor**, which is not the small remainder of the 256-colour work it
   looks like. It needs an image to bring its own palette first, or it makes
   photographs worse — `TkCurses-bvu`, and **Why more colour can mean a worse
   picture** for why.
2. **Async/await**: integration with an asyncio event loop.
3. **Screen recording**: export UI state as text files.

---

## Coding Standards

### Style
- **PEP 8**: Python style guide
- **PEP 257**: Docstrings for public API
- **Type hints**: Full annotations (PEP 484)
- **Line length**: 88 characters (Black/Ruff)

### Naming
- **Public API**: Match tkinter names exactly (`Button`, `pack`, `configure`)
- **Internal**: Underscore prefix (`_core`, `_renderer`, `_calculate_cells`)
- **Constants**: UPPER_SNAKE_CASE (`A_BOLD`, `KEY_UP`)

### Documentation
- All public methods have docstrings
- Complex rendering logic has inline comments
- Type hints serve as inline documentation

**The example programs are a test of the library as a person uses it.**
`examples/` holds eleven, each on `docs/guide/examples.md` with the screen
the docs build takes by running it, and each driven by
`tests/test_examples.py` the way the page says to use it. Writing them
finds bugs: the first six found a Treeview heading command never called
(`TkCurses-fl9m`, fixed: it runs on release over the heading pressed)
and a Canvas whose default relief was not Tk's (`TkCurses-14tc`, fixed: flat, as Tk's); the next five
(`TkCurses-q6d1`) found these, each measured against Tk 9.0 and filed
rather than fixed alongside:

- the root window never paints its `background` (`TkCurses-0awl`, fixed
  since);
- a Label too narrow for its text shows the start whatever its anchor,
  where Tk keeps the side the anchor names (`TkCurses-tyd9`, fixed since);
- uniform weighted grid columns under a spanning widget grow past their
  master (`TkCurses-xcy3`, fixed since by porting Tk's grid arithmetic);
- a PanedWindow shares extra room between panes and ignores a pane's
  `width`, where Tk's `-stretch last` gives it all to the last
  (`TkCurses-g60s`, fixed since by porting Tk's pane arithmetic);
- `canvasx` and `canvasy` take a screen coordinate where Tk's take a
  window one, so `canvas.canvasx(event.x)` is right only for a canvas at
  the screen's corner (`TkCurses-0n21`, fixed since).

Each example first steered clear in a way a Tk program could equally have
been written, so none depended on a bug staying unfixed. With the five
fixed (`TkCurses-fbrq`) the two that bent are back to what a Tk programmer
would write: the calculator's columns are one `uniform` group and its
display asks for all the room it likes, where it had `width=1` to keep
out of the grid; and the layout's left pane starts at a `width` of its own
and keeps it through a resize, where the panes used to share the room.
The calculator's coloured Frame went too, once the root's own `padx` and
`pady` were seen to work (`TkCurses-00dx`): they always had, and the issue
was filed from a list of the options `Tk` declares itself, without those it
inherits. What did not work was changing them on a running root or
Toplevel, which laid nothing out again until a resize, and a negative one,
kept as given where every Tk widget reads it back as 0 (a Message as `""`).

**The pty harness gives a widened terminal tab stops**, which pyte does
not: it sets a stop every eight columns once, at the starting width.
ncurses moves the cursor with tabs when that is shorter, so after a
resize from 60 columns to 80 a tab from column 56 went to the last column,
the next character wrapped, and the screen scrolled up a row - the layout
example's status bar drew its right-hand label at the start of a line
below it. `_Screen.resize` adds them, as xterm does. Like REP
(`TkCurses-go7y`), a terminal does it and the emulator under the tests
did not.

**The harness scrolls by more than one line**, which pyte did not
(`TkCurses-atf4`). A refresh that finds a run of lines moved up by n uses
terminfo's `indn`, `CSI n S` (and `rin`, `CSI n T`, for down) inside the
scroll region; pyte dropped both, so the lines stayed put and only the new
ones were painted. It surfaced as a Treeview with frozen rows half-redrawn
on a slow CI runner, never locally: there each Down was a refresh of its
own and scrolled one line, by `ind`, which pyte handles. A Listbox scrolled
three units in one callback tore every time. The library was right all
along; a real terminal showed the scroll.

**The harness follows a redefined palette** (`TkCurses-bvu.6`).
`init_color` goes out as OSC 4, `ESC ] 4 ; n ; rgb:RR/GG/BB ST`, and pyte
does not model it: `rgb:FF/66/00` through slot 100 read back as `878700`,
the slot's original colour. `_ByteStream` takes OSC 4 and OSC 104 out of
the stream at their own place in it - holding one split across two reads
- and `_Screen` draws every later SGR naming a redefined slot (30-37,
90-97, `38;5;N` and the backgrounds) as the direct colour it now holds.
Forwards only: a terminal recolours cells already drawn in the slot, but
pyte keeps a cell's colour, not its slot. Nothing in the library redefines
a slot today; images are written as direct colour (`TkCurses-b2b`). This is
what a widget-colour feature built on `init_color` would be tested with.
Measured with ncurses: 500 of its 1000 goes out as `7F`, not `80`.

**The tutorial is four pages read in order, and they are tested as one**
(`TkCurses-5dli`): the introduction, core concepts, common widgets and a
larger program, with common mistakes, how TkCurses works and a glossary
beside them. `tests/test_docs_tutorial.py` runs every complete program on
the first three and the mistakes page, and checks each page names the next.
The larger program is `examples/notes.py`, shown a part at a time with
`literalinclude` and `:start-at:` on its section comments, so the page
cannot quote code the file no longer has - a marker that stops matching
fails the build under `-W`.

Writing it found two departures from Tk, measured on Tk 9.0.2, filed
rather than fixed there, and fixed since (`TkCurses-fbrq`). **Tab into an Entry does not select its text**:
Tk's `tk::TabToWindow` sends `<<TraverseIn>>`, and the Entry class binds
it to select everything and put the cursor at the end, so typing replaces
the field; TkCurses has no `<<TraverseIn>>`, and typing goes in front
(`TkCurses-h0bj`). **`place` cannot share a container with `pack` or
`grid`**: Tk refuses only pack and grid together, and a placed badge over
packed content is accepted; TkCurses keeps one manager per container
(`TkCurses-huq9`). The concepts page said so, and placed in a frame of its
own.

**`tkscreens` runs each example in a fresh temporary directory**, which is
where the harness writes the program file. The notes example keeps its data
beside itself, and with one shared directory a build would load the last
build's notes and draw a different screen.

---

## Complete API Reference

This section provides a comprehensive mapping of all tkinter classes, methods, and functions to their TkCurses equivalents.

### Legend

| Symbol | Meaning |
|--------|---------|
| ✓ | Direct implementation (same signature) |
| ○ | Adapted implementation (text-mode behavior) |
| ◐ | Partial implementation (subset of functionality) |
| ✗ | Not applicable (no text-mode equivalent) |
| ☐ | Not implemented; the Notes column names the issue |

The first three each assert the method exists. **They are checked**, by
`tests/test_method_surface.py`, which reads every row of every table below and
fails if a claim is false.

That check exists because 52 of them were. The whole `ttk.Treeview` identify
family was marked ○, "adapted implementation", while `hasattr` was False for
all six - and this document was the only place anyone would have looked, which
is how the gap survived long enough to be found by accident: a description
of the code that nothing checks drifts from it unnoticed.

`☐` is the row to write when something is not there. The distinction from `✗`
matters: `✗` is a decision that a method has no text-mode meaning, `☐` is work
not yet done, and only one of the two should carry an issue id.

---

## Core Classes

### Misc Class

Base mixin providing common widget functionality.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| **Core** | | |
| `destroy()` | ✓ | Remove widget and children |
| `deletecommand(name)` | ○ | A name `register` made, or a binding's handle |
| **Focus Management** | | |
| `focus_set()` | ○ | Set focus (highlight widget) |
| `focus_force()` | ○ | Force focus |
| `focus_get()` | ✓ | Get focused widget |
| `focus_displayof()` | ○ | Returns self (single display) |
| `focus_lastfor()` | ✓ | Last focused in toplevel |
| `tk_focusFollowsMouse()` | ○ | Enable mouse focus following |
| `tk_focusNext()` | ✓ | Next widget in focus order |
| `tk_focusPrev()` | ✓ | Previous widget in focus order |
| **Event Scheduling** | | |
| `after(ms, func=None, *args)` | ✓ | Schedule callback |
| `after_idle(func, *args)` | ✓ | Schedule when idle |
| `after_cancel(id)` | ✓ | Cancel scheduled callback |
| `after_info(id=None)` | ✓ | Get callback info |
| **Audio** | | |
| `bell(displayof=0)` | ○ | Terminal bell (if supported) |
| **Clipboard** | | |
| `clipboard_get(**kw)` | ✓ | Get clipboard contents |
| `clipboard_clear(**kw)` | ✓ | Clear clipboard |
| `clipboard_append(string, **kw)` | ✓ | Append to clipboard |
| **Grab Management** | | |
| `grab_current()` | ✓ | Get widget with grab |
| `grab_release()` | ✓ | Release grab |
| `grab_set()` | ✓ | Set local grab |
| `grab_set_global()` | ✓ | Set global grab |
| `grab_status()` | ✓ | Get grab status |
| `tk_busy_hold(**kw)` | ○ | The pointer no longer reaches the window or its descendants; keys still do, as in Tk. `cursor` is kept, and nothing is drawn |
| `tk_busy_forget()` | ✓ | |
| `tk_busy_status()` | ✓ | |
| `tk_busy_current(pattern=None)` | ✓ | Glob on path names |
| `tk_busy_cget(option)` | ✓ | |
| `tk_busy_configure(cnf=None, **kw)` | ✓ | Five-tuples, as `configure` |
| **Widget Stacking** | | |
| `lower(belowThis=None)` | ✓ | Lower in stacking order |
| `tkraise(aboveThis=None)` | ✓ | Raise in stacking order |
| **Window Information** | | |
| `winfo_cells()` | ○ | Returns cell count |
| `winfo_children()` | ✓ | Child widgets list |
| `winfo_class()` | ✓ | Widget class name |
| `winfo_containing(rootX, rootY)` | ○ | Widget at cell position |
| `winfo_depth()` | ○ | Returns color depth (simulated) |
| `winfo_exists()` | ✓ | Widget exists check |
| `winfo_geometry()` | ○ | Returns cell geometry "WxH+X+Y" |
| `winfo_height()` | ○ | Height in cells |
| `winfo_width()` | ○ | Width in cells |
| `winfo_id()` | ✓ | Internal widget ID |
| `winfo_ismapped()` | ✓ | Visibility check |
| `winfo_manager()` | ✓ | Geometry manager name |
| `winfo_name()` | ✓ | Widget name; the root's is the application's, `tk` |
| `winfo_parent()` | ✓ | Parent widget path |
| `winfo_reqheight()` | ○ | Requested height in cells |
| `winfo_reqwidth()` | ○ | Requested width in cells |
| `winfo_rgb(color)` | ✓ | Color name to RGB tuple |
| `winfo_rootx()` | ○ | Cell X position |
| `winfo_rooty()` | ○ | Cell Y position |
| `winfo_screenheight()` | ○ | Screen height in cells |
| `winfo_screenwidth()` | ○ | Screen width in cells |
| `winfo_toplevel()` | ✓ | Toplevel ancestor |
| `winfo_viewable()` | ✓ | Visibility check |
| `winfo_x()` | ○ | Cell X offset |
| `winfo_y()` | ○ | Cell Y offset |
| `winfo_fpixels(number)` | ○ | Convert to cells (float) |
| `winfo_pixels(number)` | ○ | Convert to cells (int) |
| `winfo_pointerx()` | ○ | Mouse cell X |
| `winfo_pointery()` | ○ | Mouse cell Y |
| `winfo_pointerxy()` | ○ | Mouse cell (X, Y) |
| `winfo_screen()` | ○ | The terminal's device, `/dev/pts/3`, where Tk names a display |
| `winfo_screencells()` | ○ | As `winfo_cells` |
| `winfo_screendepth()` | ○ | Simulated depth |
| `winfo_screenmmheight()` | ○ | Rows at ten to the inch, as `winfo_fpixels` takes them |
| `winfo_screenmmwidth()` | ○ | Columns at ten to the inch |
| `winfo_screenvisual()` | ○ | As `winfo_visual` |
| `winfo_server()` | ○ | `TkCurses <version> <TERM>` |
| `winfo_visual()` | ○ | `truecolor` for direct colour, `staticcolor` for a palette, `staticgray` for none |
| `winfo_visualid()` | ○ | The one visual's id: its depth, in hex |
| `winfo_visualsavailable(includeids=False)` | ○ | The one visual |
| `winfo_colormapfull()` | ○ | False: a palette is fixed |
| `winfo_vrootheight()` | ○ | Virtual screen cells |
| `winfo_vrootwidth()` | ○ | Virtual screen cells |
| `winfo_vrootx()`, `winfo_vrooty()` | ○ | 0 |
| `winfo_interps(displayof=0)` | ○ | This application alone |
| `winfo_atom(name, displayof=0)` | ✓ | X's 68 predefined atoms by their numbers; new ones from 69 |
| `winfo_atomname(id, displayof=0)` | ✓ | |
| `winfo_pathname(id, displayof=0)` | ✓ | By `winfo_id` |
| `send(interp, cmd, *args)` | ○ | To this application only; any other is Tk's `no application named` |
| `register(func, subst=None, needcleanup=1)` | ✓ | For `validatecommand` with `%` codes, see above |
| `info_patchlevel()` | ✓ | 9.0.2, the Tcl the library follows |
| `tk_setPalette(*args, **kw)` | ○ | Tk 9.0's `palette.tcl`; ttk's default theme is not retinted |
| `tk_bisque()` | ✓ | |
| `tk_strictMotif(boolean=None)` | ○ | Kept and read back; no binding changes |
| **Event Loop** | | |
| `update()` | ✓ | Process pending events |
| `update_idletasks()` | ✓ | Process idle callbacks, then lay out and redraw, as Tk's geometry and display idle handlers do (`TkCurses-q6b1`) |
| `mainloop(n=0)` | ✓ | Enter event loop |
| `quit()` | ✓ | Exit event loop |
| **Binding** | | |
| `bind(sequence=None, func=None, add=None)` | ✓ | Bind event handler |
| `unbind(sequence, funcid=None)` | ✓ | Remove binding |
| `bind_all(sequence=None, func=None, add=None)` | ✓ | Global binding |
| `unbind_all(sequence)` | ✓ | Remove global binding |
| `bind_class(className, sequence=None, func=None)` | ✓ | Class binding |
| `unbind_class(className, sequence)` | ✓ | Remove class binding |
| `bindtags(tagList=None)` | ✓ | Get/set binding tags |
| **Virtual Events** | | |
| `event_add(virtual, *sequences)` | ✓ | Add virtual event |
| `event_delete(virtual, *sequences)` | ✓ | Remove virtual event |
| `event_generate(sequence, **kw)` | ✓ | Generate event |
| `event_info(virtual=None)` | ✓ | Get event info |
| **Wait Operations** | | |
| `wait_variable(name)` | ✓ | Wait for variable change |
| `wait_window(window=None)` | ✓ | Wait for window destroy |
| `wait_visibility(window=None)` | ✓ | Wait for visibility |
| **Configuration** | | |
| `configure(cnf=None, **kw)` | ✓ | Configure widget options |
| `config(cnf=None, **kw)` | ✓ | Alias for configure |
| `cget(key)` | ✓ | Get option value |
| `keys()` | ✓ | List option names |
| **Utility** | | |
| `nametowidget(name)` | ✓ | Path to widget object |
| `getvar(name)` | ✓ | Get Variable value, firing read traces; an unset name is refused, as in Tk |
| `setvar(name, value)` | ✓ | Set Variable value (internal storage) |
| `getint(s)` | ✓ | Parse integer |
| `getdouble(s)` | ✓ | Parse float |

**How an option may be spelled.** Two mechanisms look alike and are not, and
holding them in one table is what made `w.configure()["from"]` raise here while
working in tkinter (`TkCurses-y5q`):

| | example | in `configure()`'s keys | `cget` takes it | keyword takes it |
|---|---|---|---|---|
| **Tcl synonym** | `bg` for `background` | yes | yes | yes |
| **Python-keyword workaround** | `from_` for `from` | **no** | **no** | yes |

Tk defines exactly **six** synonyms, enumerated from the real toolkit across 18
classic widget classes rather than guessed: `bd`, `bg`, `bgimg`, `fg`, `invcmd`
and `vcmd`. (A synonym's `configure()` entry is a 2-tuple `(synonym, real
name)`; a real option's is a 5-tuple. That is how `tests/test_option_spellings.py`
reads the list off tkinter instead of hardcoding it, so it cannot fall behind a
Tk release.) They belong everywhere the long name does. `from_` is not a synonym at all: `from` is a
reserved word, so tkinter lets a *keyword argument* carry one trailing
underscore and strips it (`Misc._options`: `if k[-1] == '_': k = k[:-1]`). The
option stays `from`, and `cget("from_")` raises `unknown option "-from_"` —
measured on Tcl/Tk 9.0.2.

**Synonyms are per widget class, not global.** Measured: `tk.Entry` takes
`vcmd` and `ttk.Entry` refuses it, though both have `validatecommand`; and no
themed widget has a synonym at all — `ttk.Label(bg="red")` raises. A single
global table got both directions wrong, missing `vcmd` on the classic widgets
and offering `bg` on the themed ones. So `_option_synonyms` is a class
attribute: `BaseWidget` declares the standard three, the classic `Entry` adds
the validation pair, and ttk's mixin declares it **empty** — which has to be
said rather than inherited, because every themed widget is built on a classic
one. The most derived declaration wins, and ttk's mixin comes first in every
themed MRO.

**A themed widget takes Tk's ttk options and nothing else**
(`TkCurses-jo7l`). It inherits every classic option from the widget it is
built on, and the drawing reads them - a Notebook's `relief`, a Treeview's
`sunken` border - but measured on Tk 9.0.2, `ttk.Button(overrelief=...)` and
`cget("troughcolor")` on a ttk.Scrollbar are `unknown option`, and `keys()`
lists the ttk options alone: 335 classic names across the twenty themed
widgets. So the option spec keeps them as defaults and `_public_options()`
narrows what a program may name, in `_checked`, `cget`, `keys` and
`configure()`. The names are `ttk._TK_OPTIONS`, recorded from real tkinter
into `tests/support/tk_ttk_options.json`. A themed widget that needs a
classic default other than the classic widget's declares it in its own
`_widget_options` - the constructor would refuse it through `kw`.

`bgimg` was the last synonym offered, with `-backgroundimage` itself
(`TkCurses-yi4`): a synonym for a missing option would only have raised with
a more confusing message. Frame, Toplevel and the root have it; LabelFrame,
built on Frame here, hides it, as Tk's labelframe has neither.

So the underscore is stripped on the keyword path only, in `_keyword_option`,
and `cget` resolves synonyms alone. Widgets with a range — `Scale`, `Spinbox`,
`ttk.Scale`, `ttk.Spinbox` — store `from`. `ttk.Progressbar` and
`ttk.LabeledScale` have no such option in either library, which corrects the
issue's own list of what needed renaming.

**The key set has the synonyms too** (`TkCurses-bv0`). `keys()` and
`configure()` list them, and a widget lists only those whose option it has:
measured on Tk 9.0.2, a Canvas, a Scrollbar and a PanedWindow have `bd` and
`bg` but no `fg`, having no foreground. Two widgets list a synonym's option by
its database name, `("bd", "borderWidth")`, where every other gives
`("bd", "-borderwidth")`: the Canvas and the Scrollbar, still configured
through Tk's older option table. `_synonyms_by_database_name` marks them.
`tests/test_classic_option_surface.py` compares every classic widget's
synonym entries with tkinter's.

**And a classic widget takes no option Tk's refuses** (`TkCurses-x4vz.1`).
Several are built on another here - Message on Label, Spinbox on Entry,
Toplevel and the root on the Frame machinery - and inherited options Tk's
widget of the same kind does not have: measured by comparing `keys()`, 31
across 12 widgets, among them a Frame's `foreground`, an Entry's `padx`, a
Message's `image` and `wraplength`, a Spinbox's `show` and a PanedWindow's
`takefocus`. Each class names them in `_not_tk_options`; the drawing still
reads them as defaults, and `_public_options()` refuses them to a program,
the mechanism the themed widgets already used. The surface test checks both
directions now, so neither can grow back.
| `getboolean(s)` | ✓ | Parse boolean |
| **Option Database** | | |
| `option_add(pattern, value, priority)` | ◐ | Simplified options |
| `option_clear()` | ✓ | Clear options |
| `option_get(name, className)` | ◐ | Get option |
| `option_readfile(fileName, priority)` | ✗ | N/A |
| **Selection** | | |
| `selection_clear(**kw)` | ✓ | Clear selection |
| `selection_get(**kw)` | ✓ | Get selection |
| `selection_handle(command, **kw)` | ✓ | Set selection handler |
| `selection_own(**kw)` | ✓ | Claim selection |
| `selection_own_get(**kw)` | ✓ | Get selection owner |
| **Image** | | |
| `image_names()` | ○ | Names still held; the registry is weak |
| `image_types()` | ✓ | `photo` and `bitmap`, in Tk's order |
| **Grid Manager (from Misc)** | | |
| `grid_anchor(anchor=None)` | ○ | Cell-based anchor |
| `grid_bbox(column, row, col2, row2)` | ○ | Cell bounding box |
| `grid_columnconfigure(index, cnf, **kw)` | ○ | Column cell config |
| `grid_rowconfigure(index, cnf, **kw)` | ○ | Row cell config |
| `grid_location(x, y)` | ○ | Cell at position |
| `grid_propagate(flag)` | ✓ | Size propagation |
| `grid_size()` | ○ | Grid dimensions in cells |
| `grid_slaves(row, column)` | ✓ | Widgets in grid |
| **Pack Manager (from Misc)** | | |
| `pack_propagate(flag)` | ✓ | Size propagation |
| `pack_slaves()` | ✓ | Packed widgets |
| **Place Manager (from Misc)** | | |
| `place_slaves()` | ✓ | Placed widgets |

#### Implementation notes

Where the table above and the implementation need reading together.

- **Shared state.** tkinter keeps bindings, timers, the option database,
  variables and the clipboard in the Tcl interpreter. TkCurses keeps them in an
  `Application` object, one per widget tree, reached through `self.tk` — the
  attribute tkinter code already expects to find a handle on.
- **`bind(sequence)` with no callback** returns the bound callables. tkinter
  returns the Tcl script it would evaluate, which has no meaning without Tcl.
- **`tk.call` serves a few commands, not Tcl.** tkinter programs reach for
  `tk.call` where tkinter has no method, and a handful of commands cover most
  of that. They are served one by one, each measured on Tk 9.0.2 through
  tkinter, answers and refusals alike (`tests/test_tk_call.py`):

  | Command | Answer here |
  |---------|-------------|
  | `info patchlevel`, `info tclversion` | `9.0.2` and `9.0`, the Tcl Tk 9.0.2 ships with |
  | `tk windowingsystem` | `x11`: the keys, the mouse and the virtual events here are Tk's X11 bindings |
  | `tk scaling` | 10/72 - a pixel is a cell, ten to the inch |
  | `tk scaling` *factor* | Read back as Tk reads it, and nothing else changes |
  | *widget* `cget` / `configure` | Tk's dashed names and shapes: `configure -text` is the five-tuple with `-text` first, and a set answers `""` |
  | a Treeview's `cellselection` | See the Treeview section |
  | `image create`, `delete`, `height`, `inuse`, `names`, `type`, `types`, `width` | Over the application's images (`tests/test_image_command.py`). Tk's message-box icons, `::tk::icons::...`, are not among the names |

  `image delete` behaves as Tk's does, measured: the name is gone, a widget
  showing the image keeps the name in its option and its size and draws
  nothing there, and the Python object that made it answers `image "pic" does
  not exist` to `width()`. An image `image create` makes with no name is
  `image1`, Tk's numbering rather than tkinter's `pyimage1`, and it is held
  by the application until deleted: no Python object refers to it, and in Tk
  it would last.

  `tk scaling` follows ScalingCmd in tkCmds.c. Tk keeps no factor: it gives
  the screen a new width in millimetres, rounded and at least one, and reads
  the factor back from that, so 2.0 reads back 1.998 on a real screen and 0,
  -1 or 1e3 all read back the largest value the screen allows. The same
  arithmetic runs here with the terminal's columns as the screen's pixels.
  **It changes nothing else, deliberately:** a program sets it for a dense
  monitor, and a terminal's cells do not shrink, so applying it would only
  make every inch it converted twice as many cells. `winfo_fpixels("1i")` is
  10 whatever it says.

  Anything else raises `TclError` saying TkCurses does not run it, and a
  widget subcommand other than these says to use the method.
- **`configure()` with no arguments** returns every option's five-tuple, as
  tkinter does, and each synonym as `(short, -option)`. It returned the
  current values alone until `TkCurses-bv0`, documented as a difference.

  **`configure("name")` does answer Tk's five-tuple** (`TkCurses-kifn`; it
  crashed on every widget before). The database name and class are Tk's own,
  captured from Tcl/Tk 9.0.2's `configure()` on all forty tkinter and ttk widget
  classes into `tkcurses/_core/option_names.py`. They are not uniform: a ttk
  Entry's `background` is `windowColor`/`WindowColor`, a ttk Label's is
  `frameColor`, and a ttk widget's `class` has no database name at all. The
  default is this library's own, and the last field is `cget`'s answer. Also
  measured: a short spelling answers the **full** entry under the full name
  (`configure("bg")` is `("background", "background", "Background", …)`, not
  the two-tuple `configure()` lists for `bg`), and `configure("-text")` is
  `unknown option "--text"`. `Misc.__init_subclass__` adds the query to every
  class's `configure`, so an override cannot forget it.
  `tests/test_configure_query.py` compares every shared option of every widget
  with the real toolkit when there is a display.

  **An option given as None is ignored** (`TkCurses-bx5b`), as tkinter's
  `Misc._options` ignores it: `configure(text=None)` leaves the text alone,
  and a constructor treats it as not given. Measured on Tk 9.0.2 and true here
  for constructors, `configure`, `w[key] = None`, canvas items, menu entries,
  text tags, panes, tabs, the Treeview's methods, `Style` and the geometry
  managers; it is `_given` in `tkcurses/__init__.py`. A call whose every
  option is None returns None, not the listing an empty call answers — except
  `grid_rowconfigure`/`grid_columnconfigure`, which do answer the listing in
  tkinter. **One deliberate difference:** tkinter's ttk methods that go through
  `_format_optdict` (`item`, `heading`, `column`, `tag_configure`, `tab`,
  `pane`, `Style.configure`) turn a lone None into a *query* of that option, and
  a None beside a real value into a garbled call (`item(i, text=None,
  open=True)` raises `unknown option "1"`). That is an accident nothing can
  rely on, so None is ignored there too. Not covered: `Font`, where tkinter
  sends the string `"None"` to Tk, and `event_generate`, which stringifies it.
- **`update()`** runs pending idle and timer callbacks but does not read input.
  Draining the keyboard from inside a callback is what makes tkinter's
  `update()` reentrant and hazardous; the loop in `Tk` is the only place that
  reads input. `mainloop()` and `quit()` likewise belong to `Tk`; `Misc`
  delegates to the root.
- **`winfo_pixels`/`winfo_fpixels`** measure in cells, at ten columns to the
  inch — the classic teletype metric terminal emulators still approximate.
- **`winfo_rgb`** reports the colour the terminal will actually render, not the
  one that was asked for: echoing the request back would hide the
  approximation, and how close it gets depends on how many colours there are.
- **`winfo_colordepth`** has no tkinter equivalent and is how anything drawing
  a colour ramp asks which of the four tiers it is drawing on.
- **The clipboard reaches the system only by a route a terminal or desktop
  offers.** `CLIPBOARD` and `PRIMARY` are held in the `Application`;
  CLIPBOARD is carried out by OSC 52 or the desktop's clipboard tool where
  one is available, and PRIMARY never is. See "Copy, cut and paste".
- **Multi-event sequences** (`<Control-x><Control-s>`, `"ab"`) bind and fire
  as Tk's do; see "Multi-event sequences" under Event Handling Flow.
- **Making a widget follows tkinter, not Tk, where the two differ.** Tk
  refuses a name already in use with `window name "b" already exists in
  parent`, but no tkinter program sees that: `BaseWidget._setup` destroys the
  widget holding the name first, with its `<Destroy>` and its descendants,
  and the new one takes its place. Measured on Python 3.14 over Tk 9.0.2
  (`TkCurses-use6`). The one path that does reach Tk's refusal is
  `Text.peer_create`, which tkinter hands straight to Tcl.
- **A widget whose option is refused is left as tkinter leaves it.** tkinter
  has already put the object in `master.children` when Tk refuses, and never
  takes it out: `nametowidget` finds it, `winfo_exists` is 0, `winfo_children`
  leaves it out, destroying it only removes it from `children`, and its
  generated name stays used (the next Button is `!button2`). Here every
  widget class's `__init__` is wrapped by `Misc.__init_subclass__` to do the
  same whenever it raises - in `BaseWidget`, or later in the class's own
  `__init__`, where about thirty classes refuse a value such as `width="abc"`
  (`TkCurses-lwoi`; the error type there is `TkCurses-vgkb`).
- **`destroy` takes the widget out of its geometry manager** (`TkCurses-41zl`).
  It did not: a destroyed packed widget kept its space and stayed in
  `pack_slaves`, and the same in grid and place.

---

### Wm Class

Window manager interface for toplevel windows.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `wm_aspect(minN, minD, maxN, maxD)` | ○ | Kept and read back; the window is not held to it. Four integers above zero, or four empty strings to clear |
| `wm_attributes(*args, **kwargs)` | ◐ | Limited attributes |
| `wm_client(name=None)` | ○ | Kept and read back |
| `wm_colormapwindows(*wlist)` | ○ | Kept and read back as widgets; a path naming no window is refused |
| `wm_command(value=None)` | ○ | Kept and read back |
| `wm_deiconify()` | ○ | Show window |
| `wm_focusmodel(model=None)` | ○ | Focus behavior |
| `wm_forget(window)` | ✓ | Unmapped until a geometry manager takes it; the root and non-windows are left alone |
| `wm_frame()` | ○ | Returns self |
| `wm_geometry(newGeometry=None)` | ○ | Cell geometry "WxH+X+Y" (see below) |
| `wm_grid(baseW, baseH, wInc, hInc)` | ○ | Cell grid sizing |
| `wm_group(pathName=None)` | ○ | Kept and read back as a path; a path naming no window is refused |
| `wm_iconbitmap(bitmap, default)` | ○ | Kept and read back; Tk's bitmap names and `@file` only. `default` is refused, as on X11 |
| `wm_iconify()` | ○ | Hide window |
| `wm_iconmask(bitmap=None)` | ○ | Kept and read back, checked as `iconbitmap` |
| `wm_iconname(newName=None)` | ○ | Kept and read back |
| `wm_iconphoto(default, *args)` | ○ | Kept; each image must be a photo image |
| `wm_iconposition(x=None, y=None)` | ○ | Kept and read back; two integers, or two empty strings |
| `wm_iconwindow(pathName=None)` | ○ | Kept and read back as a path |
| `wm_manage(widget)` | ✓ | A classic Frame, LabelFrame or Toplevel becomes a window, centred at its requested size; pack, grid and place refuse it, in Tk's words |
| `wm_maxsize(width, height)` | ○ | Max cell size |
| `wm_minsize(width, height)` | ○ | Min cell size |
| `wm_overrideredirect(boolean)` | ○ | Borderless mode |
| `wm_positionfrom(who=None)` | ○ | Kept and read back; `program` or `user`, abbreviated as Tk allows |
| `wm_protocol(name, func)` | ✓ | Protocol handlers |
| `wm_resizable(width, height)` | ○ | Resize enable |
| `wm_sizefrom(who=None)` | ○ | Kept and read back, as `positionfrom` |
| `wm_state(newstate=None)` | ○ | Window state |
| `wm_title(string=None)` | ○ | Title bar text |
| `wm_transient(master=None)` | ○ | Transient relationship |
| `wm_withdraw()` | ○ | Hide window |

**Convenience Aliases:** In tkinter, `wm_*` methods have short aliases without the `wm_` prefix (e.g., `root.title()` instead of `root.wm_title()`). TkCurses provides these aliases for all implemented Wm methods:

| Alias | Method | Alias | Method |
|-------|--------|-------|--------|
| `geometry` | `wm_geometry` | `protocol` | `wm_protocol` |
| `minsize` | `wm_minsize` | `transient` | `wm_transient` |
| `maxsize` | `wm_maxsize` | `focusmodel` | `wm_focusmodel` |
| `resizable` | `wm_resizable` | `overrideredirect` | `wm_overrideredirect` |
| `title` | `wm_title` | `positionfrom` | `wm_positionfrom` |
| `iconname` | `wm_iconname` | `sizefrom` | `wm_sizefrom` |
| `iconbitmap` | `wm_iconbitmap` | `client` | `wm_client` |
| `state` | `wm_state` | `colormapwindows` | `wm_colormapwindows` |
| `withdraw` | `wm_withdraw` | `command` | `wm_command` |
| `deiconify` | `wm_deiconify` | `frame` | `wm_frame` |
| `iconify` | `wm_iconify` | `group` | `wm_group` |

Every method has its alias, `aspect`, `iconphoto`, `iconposition`,
`iconmask` and `iconwindow` among them.

**The ○ hints with no effect** (`TkCurses-k1i`). These ask a window manager
for something a terminal has none of: an icon, a group leader, a session's
command line, an aspect ratio a compositor would enforce. They are not
missing - each is checked as Tk 9.0.2 on X11 checks it, kept per window, and
read back, so that a program setting one runs unchanged and one reading one
back gets what it set. Nothing on the screen changes. The answers - `''` from
a setter, `None` from an unset `aspect` or `iconposition`, a tuple once set -
and every refusal are held to real tkinter's by `tests/test_wm_hints.py`.

**Geometry Behavior:**

The `wm_geometry()` method handles window size and position using cell coordinates:

| Mode | Behavior |
|------|----------|
| Query (`geometry()`) | Returns current geometry as "WxH+X+Y" string |
| Set (`geometry("WxH+X+Y")`) | Resizes and repositions the window |

**Window Type Considerations:**

| Window Type | Resize | Reposition | Notes |
|-------------|--------|------------|-------|
| `Tk` | No | No | Uses `stdscr`, size determined by terminal |
| `Toplevel` | Yes | Yes | Uses `curses.newwin()`, supports `wresize()` and `mvwin()` |

When setting geometry on a `Toplevel`:
1. Parse the geometry string "WxH+X+Y"
2. Resize the curses window using `wresize(height, width)`
3. Move the window using `mvwin(y, x)`
4. Update the panel stack to reflect changes

> **Constraint:** Window cannot exceed terminal dimensions. Geometry is clamped to available screen size.

---

### Geometry Managers

#### Negotiation

Layout is a conversation before it is a calculation. A widget says how big it
would like to be (`winfo_reqwidth`/`winfo_reqheight`); its container's manager
adds that up across siblings and asks for that much; the container asks its own
manager, up to the toplevel. The agreed sizes then come back down and windows
are moved.

`_core/layout.py` owns that, and two properties of it are deliberate.

**It is queued, not eager.** Packing ten children one at a time would lay the
container out ten times. Containers are marked as needing work and the whole
set is recomputed in one run, which the main loop does after input and before
drawing, so nothing is painted at a size it is about to stop having.

**It is guaranteed to terminate.** A container that resizes to fit its children
changes its own requested size, which asks its parent to recompute, which can
come back around; the previous attempt at this library looped here and
exhausted memory. Three things prevent it now: the walk upward stops at the
first ancestor whose requested size is unchanged, so a change travels only as
far as it changes something; sizes are integers, so they cannot oscillate by
ever-smaller amounts; and a run is bounded, raising `LayoutLoop` rather than
continuing, because a diagnosable error beats a machine that has to be
power-cycled. `LayoutEngine.ancestry()` refuses to walk a cycle for the same
reason.

#### Which managers share a container

A container has three layout slots, not one: `_paned_manager`, for a paned
window's panes; `_layout_manager`, for pack or grid; and `_place_manager`,
for place. The engine runs them in that order, so packed children land over
the panes and placed ones over both. Measured on Tk 9.0.2, which is what
this follows:

- place shares a container with pack or grid, and is never refused - the
  overlay, a badge or a floating button over packed content;
- pack and grid refuse each other only while the other still lays out a
  child: a frame whose last packed child was forgotten takes grid. The error
  is Tk 9's, `cannot use geometry manager "grid" inside ".": pack is already
  managing its content windows`, where 8.6 said `which already has slaves
  managed by pack`;
- `place` on a packed widget in the same container takes it out of pack, and
  `pack` takes it back out of place;
- `pack_forget`, `grid_forget` and `place_forget` leave alone a widget another
  manager lays out;
- a paned window's panes refuse neither pack nor grid (`TkCurses-ect9`). A
  label packed `side="bottom"` into a 300-pixel window holding a pane sits at
  the bottom centre while the pane keeps the whole window. A pane's manager
  reads `panedwindow`, for the themed widget too, and `""` once forgotten;
  `add` takes a packed widget out of pack, and packing a pane takes it out of
  the panes.

Before `TkCurses-huq9` a container had one slot, so place refused a packed
container and pack a placed one, and every forget unmapped the widget
whichever manager it was in; before `TkCurses-ect9` a paned window's layout
held the slot pack and grid need, so both were refused there.

**What the window asks for, with panes and pack both in it, is not Tk's.**
Tk takes whichever manager last asked for a size: a pane needing 50 by 20
with a packed 40 by 10 beside it made the window ask for 40 by 10, and a
pane added after would ask again. Here the window asks for pack's or grid's
size while that manager has a child, and the panes' otherwise - the same
answer for the common order, without keeping a history of requests.

`pack_propagate(False)` stops a container resizing to fit its children: it
keeps the size it was given and its parent is never told. Tk spells the flag
once per manager; there is one container and one setting, so `pack_propagate`,
`grid_propagate` and `propagate` are the same flag.

#### Pack Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `pack_configure(cnf={}, **kw)` | ○ | Cell-based packing |
| `pack(cnf={}, **kw)` | ○ | Alias |
| `pack_forget()` | ✓ | Remove from layout |
| `pack_info()` | ○ | Cell pack info |

**Pack Options Mapping:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `side` | TOP/BOTTOM/LEFT/RIGHT | Same (cell edges) |
| `fill` | NONE/X/Y/BOTH | Same (cell fill) |
| `expand` | bool | Same |
| `anchor` | N/S/E/W/CENTER/etc. | Same (cell anchor) |
| `padx` | pixels, one or two | Cells, one or two |
| `pady` | pixels, one or two | Cells, one or two |
| `ipadx` | pixels | Cells |
| `ipady` | pixels | Cells |

**External padding takes a distance per side; internal padding does not.**
`padx=(0, 1)` pads the right of a widget and not its left, and `padx="0 1"`
spells the same thing in one string. `ipadx` has no two-value form at all:
`ipadx=(2, 8)` is an error where `padx=(2, 8)` is fine. That asymmetry is
Tk's, measured rather than assumed: the same 168-case matrix was run through
`tkinter` and through this library and the answers diffed, error wording
included. `tests/test_pad_options.py` carries that measurement as a table, one
row per form, checked against both managers and both axes. One parser serves both managers -
`parse_pad` and `parse_single_pad` in `_core/geometry.py`, with `Pad` holding
the two sides and deriving the form `pack_info` reads back, so there is no
second copy of the normalisation to keep in step. `TkCurses-l8f`.

#### Grid Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `grid_configure(cnf={}, **kw)` | ○ | Cell-based grid |
| `grid(cnf={}, **kw)` | ○ | Alias |
| `grid_forget()` | ✓ | Remove from grid |
| `grid_remove()` | ✓ | Remove (keep config) |
| `grid_info()` | ○ | Cell grid info |

**Grid Options Mapping:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `row` | int | Same |
| `column` | int | Same |
| `rowspan` | int | Same |
| `columnspan` | int | Same |
| `sticky` | N/S/E/W combinations | Same |
| `padx` | pixels, one or two | Cells, one or two |
| `pady` | pixels, one or two | Cells, one or two |
| `ipadx` | pixels | Cells |
| `ipady` | pixels | Cells |

**Line sizes are Tk's own arithmetic**, ported from `generic/tkGrid.c`:
`ResolveConstraints` for the size the grid asks for and `AdjustOffsets` for
fitting it to the room it gets, then `TkComputeAnchor` for where it sits
(`_core/grid.py`, `_resolve`, `_adjust`, `_origin`). The rules that come
with it, none of them in `grid(n)`:

- `-pad` is added to the largest child wholly in the line, and the line is
  then the larger of that and `-minsize`; an empty line gets no pad;
- a `-uniform` group is evened up before anything else, and a line of
  weight 0 in one counts as weight 1;
- room a spanning child needs beyond its lines' own is shared among them
  by weight, cumulatively and rounded down, so the remainder lands on the
  last - four uniform columns needing 24 under a child needing 25 end at
  6, 12, 18 and 25;
- room to spare in the container is shared the same way, so five rows of
  weight 1 sharing 13 are 2, 3, 2, 3, 3; too little is taken from the
  weighted lines down to their `-minsize`, and past that the grid is cut;
- with no weights, a centred grid larger than its container is cut on
  both sides.

**How it is held to Tk:** `tests/support/record_grid_reference.py` asks real
Tk 9.0.2 to lay out 150 random grids - weights, minsizes, pads, uniform
groups, spans, padding, anchors, containers too big and too small - with
frames sized in pixels standing for cells, and `tests/test_grid_reference.py`
wants every cell's `grid_bbox` the same. Measured before the port, 85 of 400
such grids matched; after, 1200 of 1200 (`TkCurses-xcy3`). Re-record when
the Tk the library follows changes.

**`rowconfigure` and `columnconfigure` take several lines**, as `grid(n)`
says: a list of indices, `all`, or a gridded window for the lines it spans.
What the manual does not say, measured on Tk 9.0.2 through tkinter
(`TkCurses-2lg5`, where a tuple was kept as one index and every layout pass
then raised):

- `all` is every line a gridded child of the container occupies, spans
  included - not every line that has been configured;
- each index is read and given the options in turn, so an error part way
  leaves the lines before it changed: `(9, "foo")` sets column 9 and then
  fails, and `weight=5, bogus=1` sets the first line's weight before
  failing on the option;
- an index is a Tcl integer (`" 3 "`, `"0x3"`, `True`) from 0 to 9999;
  `-1` and `10000` are `"-1" is out of range` when setting, but reading
  either answers the defaults; `foo`, `ALL`, `1.5` and a window that does
  not exist are all `illegal index`; a window gridded elsewhere, or not at
  all, is `not managed by` the container;
- reading takes exactly one integer: a list is `must specify a single
  element on retrieval`, and `all` or a window `expected integer ... (when
  retrieving options only integer indices are allowed)`;
- options are named by any unique prefix; a weight is an integer, and a
  weight or pad below zero is `invalid arg "-weight": should be
  non-negative`, but a negative `minsize` is kept, read back and laid out
  as given: an empty column of minsize -30 is -30 wide, and the next
  column starts at -30, its child cut at the left edge. The port's
  arithmetic does the same in cells. `minsize` and `pad` are distances,
  so `2c` is accepted, as cells.

#### Place Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `place_configure(cnf={}, **kw)` | ○ | Cell-based placement |
| `place(cnf={}, **kw)` | ○ | Alias |
| `place_forget()` | ✓ | Remove from layout |
| `place_info()` | ○ | Cell place info |

**Place Options Mapping:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `x` | pixels | Cells |
| `y` | pixels | Cells |
| `width` | pixels | Cells |
| `height` | pixels | Cells |
| `relx` | 0.0-1.0 | Same (relative) |
| `rely` | 0.0-1.0 | Same (relative) |
| `relwidth` | 0.0-1.0 | Same |
| `relheight` | 0.0-1.0 | Same |
| `anchor` | N/S/E/W/CENTER/etc. | Same |

---

## Widget Classes

### Tk Class

Main application window.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(screenName, baseName, className, useTk, sync, use)` | ○ | Initializes curses screen |
| `destroy()` | ✓ | Destroy application, call curses.endwin() |
| `loadtk()` | ○ | Starts curses if `Tk(useTk=False)` did not |
| `readprofile(baseName, className)` | ◐ | Runs `~/.<className>.py` and `~/.<baseName>.py`; the `.tcl` files are skipped, and `Tk()` never calls it itself |
| `report_callback_exception(exc, val, tb)` | ✓ | Exception handler |

Inherits all methods from `Misc` and `Wm`.

**The root's `background` is painted into the screen buffer**, not into a
window: the root deliberately has none (see "The root is not one of them"),
so the buffer the panels are drawn over is its background. Setting it fills
every cell; setting it back to `''` fills them with black, which is what a
widget with no background paints, rather than the terminal's own default -
curses has already been told about those cells and cannot be told to forget.
A resize paints the cells it adds. The default stays `''` where Tk's is
`SystemButtonFace` (`#d9d9d9` on X11): every widget here defaults to the
terminal's own colours, and a light grey root would paint over a terminal
that a person chose to be dark. `TkCurses-0awl`; before it the option was
taken and kept and painted nothing.

A Toplevel paints its `background` behind its children and under its border,
through its window's `bkgd`, as Tk paints a toplevel's.

---

### Toplevel Class

Secondary top-level window.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Creates cell panel |

Inherits all methods from `BaseWidget` and `Wm`.

---

### Frame Class

Container widget.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Box-drawn frame |

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `background`/`bg` | color | Cell background |
| `borderwidth`/`bd` | pixels | Cells (0 or 1) |
| `relief` | FLAT/RAISED/SUNKEN/etc. | Box drawing style |
| `width` | pixels | Cells |
| `height` | pixels | Cells |
| `padx` | pixels | Cells |
| `pady` | pixels | Cells |

**The window-system options are kept, and the ones Tk fixes stay fixed**
(`TkCurses-gm66.7`). Frame, LabelFrame, Toplevel and the root take `class`,
`colormap`, `container` and `visual`; Toplevel and the root also take `screen`
and `use`; Listbox and Text take `setgrid`. Each is about an X window and changes nothing in a terminal. Each
is checked as Tk 9.0.2 checks it, kept and read back:

| Option | Tk 9.0.2, measured | Here |
|--------|--------------------|------|
| `class` | names the class for bindings and the option database; `cget` answers it; a LabelFrame's is `Labelframe` | the same. `class_=` and `{"class": ...}` both name it, the keyword winning, and a subclass still answers its own name |
| `visual` | a class or a unique prefix (`tru`, `b`; `gray` and `grey` count as one), or a window, then an optional depth; `TrueColor`, `s`, a leading space and `default 24` are `unknown or ambiguous`, `truecolor x` wants an integer | the same checks and messages. Tk then asks the display, and fails with `couldn't find an appropriate visual` if it has none; there is no display here to ask |
| `colormap` | `""`, `new`, or an existing window; `NEW` is `bad window path name` | the same |
| `use` | a window id to embed in; one that does not exist is `couldn't create child of window` | only `""`: a terminal has no window to embed in |
| `screen` | a display; one that cannot be reached is `couldn't connect to display` | kept as given: there is one terminal |
| `container`, `setgrid` | booleans | kept. A terminal is already gridded in characters, so `setgrid` has nothing to change |
| the root's `width`, `height` | a screen distance, -5 reading back 0 | kept: the root is the terminal, whose size is the person's |

**Six cannot change after creation**: `class`, `colormap`, `container`,
`visual`, and on Toplevel and the root `screen` and `use`. Measured,
`configure` refuses each, even with the value it already has: `can't modify
-class option after widget is created`. That is enforced here, through each
class's `_creation_only`. ttk widgets are outside it: ttk's `-class` is `""`
by default and refuses only a *different* value, with `attempt to change
read-only option`.

**`backgroundimage` and `tile` draw** (`TkCurses-yi4`), on Frame, Toplevel and
the root, through the `_Backdrop` mixin; LabelFrame hides both, and `bgimg`,
because Tk's labelframe has none of them. Where the image goes follows
`DrawFrameBackground` in Tk 9.0.2's tkFrame.c, worked in pixels - one column
by half a row, as every image here - and composed in the window's own pixels,
so a centred image landing on an odd pixel row pairs its rows where it lands:

| | Tk 9.0.2 | Here |
|-|----------|------|
| `tile` on | copies from the top left of the inside of the border (highlight ring and `borderwidth`), cut off at its far edges | the same, inside the border drawn (one cell, or none); the highlight ring draws nothing here |
| `tile` off, image fits | centred on the **whole window**, border included: `(width - imagewidth) / 2` | the same |
| `tile` off, image too big | its middle, cut to the inside of the border | the same |
| children | drawn over it | the same: they are panels in front |
| size | the frame asks for none on the image's account | the same |

Measured through tkinter, and not in the manual:

| What | Tk 9.0.2 | Here |
|------|----------|------|
| an image passed as an object | read back as its name, `pyimage1` | the same |
| an unknown name | `image "nosuch" does not exist`, the old value kept | the same, refused in `_checked` before anything is stored |
| the image deleted while shown | every `configure` that sets something is refused with `image "pyimage1" does not exist` and changes nothing, because `ConfigureFrame` calls `Tk_GetImage` each time; `configure(backgroundimage="")` clears it | the same. Asking, `configure("width")`, is not refused |

**The label family's `image` follows the same two rules** (`TkCurses-z748`),
measured on Tk 9.0.2 across Label, Button, Checkbutton, Radiobutton and
Menubutton, classic and themed: a refused name leaves the image the widget
had, and once that image is deleted every `configure` that sets something is
refused until `image` names one that exists, or `""`. `_TextWidget._checked`
does it. One exception, kept: the **classic Menubutton stores the refused
name** - `cget("image")` answers `nosuch` after the error - where every other
widget of the family, `ttk.Menubutton` included, does not
(`_stores_refused_image`).

The root has no curses window: it paints the image into the screen buffer
behind every panel, from the top left corner, as it paints its `background`.
A background image goes through curses' colour pairs only, never the direct
painter a Label's image uses for exact colour: that writes after curses has
finished, over everything, and a background is the one image with windows in
front of it. Filling the screen also found that its last cell, written with
`insch` to keep curses from scrolling, raised `OverflowError` for anything
past ASCII - `insch` takes a chtype - so the corner now takes `insstr` for
those.

---

### LabelFrame Class

Labeled container.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Box with title |

**Additional Options:**

| Option | TkCurses |
|--------|----------|
| `text` | Title in top border |
| `labelanchor` | Title position (n/s/e/w) |
| `labelwidget` | Widget as label |

**`labelwidget`, measured on Tk 9.0.2** (`TkCurses-gm66.10`). The widget is
managed by the frame (`winfo_manager()` is `labelframe`) and drawn on the
border where the anchor puts a text caption, one cell in from the corner as a
caption's text is; `text` is kept and not drawn. It may be the frame's child
or a child of any ancestor - a sibling made *before* the frame is raised above
it, as Tk raises it - and anything else, a toplevel included, is `can't use .x
as label in this frame`. Choosing another lets the first go, unmapped and
managed by nothing. Packing, gridding or placing the label anywhere, or
destroying it, ends it: the option reads `""` and the caption is text again.

A label taller than the border row pushes the children away from that edge
(Tk put a 40-pixel label's first child at 40); here the border stays on the
frame's edge with the label over it, since a terminal border is one row and
cannot run through the middle of a widget.

---

### Label Class

Static text display.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Text cells |

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `text` | string | Direct display |
| `textvariable` | Variable | Same |
| `anchor` | N/S/E/W/CENTER | Cell anchor |
| `justify` | LEFT/CENTER/RIGHT | Text alignment |
| `wraplength` | pixels | Cells (word wrap) |
| `foreground`/`fg` | color | Cell foreground |
| `background`/`bg` | color | Cell background |
| `font` | font | Attribute (bold/underline) |
| `image` | PhotoImage | A pixel plane, composed into cells |
| `bitmap` | bitmap | ○ Tk's ten names as one glyph each; `@file` drawn as its XBM bits |
| `compound` | position | none/left/right/top/bottom/center |
| `width` | chars | Cells |
| `height` | lines | Cells |
| `padx` | pixels | Cells |
| `pady` | pixels | Cells |

**Text wider than the widget is cut where the anchor puts it.** Measured on
Tk 9.0 from screenshots (`magick import -window`), `text="abcdefghij"` in
`width=5`: a classic Label, Button, Checkbutton or Radiobutton shows `fghij`
anchored `e`, `abcde` anchored `w` and `cdefg` centred - `TkComputeAnchor`
gives a negative offset and the window clips it. ttk.Label, ttk.Button and
ttk.Checkbutton show `abcde` whatever the anchor. Message wraps, so never
gets here. `_TextWidget._cells_cut_before` is the one place that decides,
and the underline follows the text, and is not drawn when its letter is
cut. Before `TkCurses-tyd9` every widget showed the start, so a right-hand
display - a calculator's - lost the end of a long number. A centred label
narrower than its text used to show the start too; it shows the middle now.

---

### Button Class

Clickable button widget.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Box-drawn button |
| `flash()` | ○ | Toggle highlight |
| `invoke()` | ✓ | Execute command |

**Rendering:**
```
Normal:    ┌────────┐    Focused:   ┌────────┐
           │  OK    │               │▶ OK   ◀│
           └────────┘               └────────┘

Pressed:   ┌────────┐    Disabled:  ┌────────┐
           │▌ OK   ▐│               │  OK    │ (dim)
           └────────┘               └────────┘
```

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `text` | string | Button label |
| `textvariable` | Variable | Same |
| `command` | callable | Same |
| `state` | NORMAL/ACTIVE/DISABLED | Same (dim for disabled) |
| `width` | chars | Cells |
| `height` | lines | Cells |
| `anchor` | N/S/E/W/CENTER | Text anchor |
| `underline` | int | Underlined char index |
| `default` | NORMAL/ACTIVE/DISABLED | Same |

---

### Checkbutton Class

Toggle checkbox.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `[ ]`/`[X]` display |
| `deselect()` | ✓ | Set to off |
| `flash()` | ○ | Toggle highlight |
| `invoke()` | ✓ | Toggle and execute |
| `select()` | ✓ | Set to on |
| `toggle()` | ✓ | Toggle state |

**Rendering:**
```
Unchecked: [ ] Option    Checked: [X] Option
Focused:   [▶] Option             [X] Option ◀
```

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `text` | string | Label text |
| `variable` | Variable | Same |
| `onvalue` | value | Same |
| `offvalue` | value | Same |
| `command` | callable | Same |
| `indicatoron` | bool | Always True |

---

### Radiobutton Class

Radio selection.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `( )`/`(●)` display |
| `deselect()` | ✓ | Deselect |
| `flash()` | ○ | Toggle highlight |
| `invoke()` | ✓ | Select and execute |
| `select()` | ✓ | Select |

**Rendering:**
```
Unselected: ( ) Option    Selected: (●) Option
Focused:    (▶) Option              (●) Option ◀
```

**The third state, `(-)`** (`TkCurses-gm66.10`). A radiobutton whose variable
holds its `tristatevalue` is drawn as neither chosen nor not. That value
defaults to `""`, so **an empty variable draws every button of its group as
`(-)`** until one is chosen, and `deselect()`, which writes `""`, does the
same. This needed eyes: no Tk call reports what is drawn, and a probe run on
Tk 9.0.2 under GNOME showed an empty variable and a variable equal to
`tristatevalue` both "greyed out and set". It is the well-known look of
radiobuttons over a fresh `StringVar()`.

One departure. Two buttons made with **no** variable share Tk's
`selectedButton`; in Tk the first one showed plain and the second greyed and
set, because the first computes its state before it creates the variable and
is not redrawn when it does. Here the shared variable exists from the start
and both show `(-)`.

**The themed buttons take their third state from the variable's
existence, not its value** (`TkCurses-uz0z`). Measured on Tk 9.0.2:
`ttk.Checkbutton` and `ttk.Radiobutton` set `selected` while the variable
holds the on value, and `alternate` while the variable does not exist - one
made with no variable starts that way, and unsetting it later adds
`alternate` and keeps `selected`. An empty value is plain "off" on both;
there is no `tristatevalue`. A write clears `alternate` and sets `selected`
afresh, and a flag set by hand stays until then. Reading the window's
pixels, the default theme draws `alternate` differently from off on both.
So `_ThemedChoice` keeps the two flags from the variable and draws the
indicator from them, and a button given no variable gets one left unset,
as Tk leaves its own. The issue's example,
`ttk.Checkbutton(variable=StringVar(value=''))`, reported `alternate` in Tk
only because tkinter garbage-collects the inline variable, which unsets it;
here a widget keeps its variable alive. `selectimage` and `tristateimage` replace
`image` in those states, on both check and radio buttons; neither does
anything without an `image`, and neither changes the size, which `image`
alone decides - measured, a larger `selectimage` left the button 8x8.

---

### Entry Class

Single-line text input.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Text field cells |
| `delete(first, last=None)` | ✓ | Delete text |
| `get()` | ✓ | Get text content |
| `icursor(index)` | ○ | Position cursor |
| `index(index)` | ✓ | Get index position |
| `insert(index, string)` | ✓ | Insert text |
| `scan_mark(x)` | ✓ | Scan start, on Entry and Spinbox; TkCurses-5kg |
| `scan_dragto(x)` | ✓ | Ten times the drag, as `EntryScanTo`; TkCurses-5kg |
| `selection_adjust(index)` | ✓ | Adjust selection |
| `selection_clear()` | ✓ | Clear selection |
| `selection_from(index)` | ✓ | Selection start |
| `selection_present()` | ✓ | Has selection? |
| `selection_range(start, end)` | ✓ | Set selection |
| `selection_to(index)` | ✓ | Selection end |

**Rendering:**
```
Normal:    [John Doe________]
Cursor:    [John Doe█_______]
Selection: [John ███________]
```

**A negative index is 0**, as in Tk, for every method that takes one —
measured on 9.0.2, `index(-1)` and `index(-99)` answer 0 and `delete(-2)`
removes the first character. This counted negatives from the end until
`TkCurses-11m`, and because cursor motion goes through the same clamp, Left at
the start of a field jumped to its far end.

**The view and the cursor are independent**, as of `TkCurses-i8s`. The manual
says only that `xview` "adjusts the view"; what follows was measured on Tk 9.0.2
with a 5-wide `tk.Entry` holding `a`–`z`, cursor at 3, and is matched here:

- `xview moveto f` shows character `f × length` first, **halves rounded up**
  (2.5 → 3, 4.5 → 5 — not Python's `round`). `scroll n units` moves n
  characters; `scroll n pages` moves `n × max(1, width − 2)`: 1 at widths 1–3,
  3 at 5, 6 at 8. A bare index is shown first.
- Every form stops at `length − width`, so the last character sits at the right
  edge, and text shorter than the field never scrolls.
- **None of them moves the cursor or the selection.** They used to move the
  cursor, which also dropped the selection.
- Only the **bindings** bring the cursor into view (Tk's `see insert`), after a
  keystroke or a click. A program's `insert`, `delete`, `icursor`,
  `selection_to`, `set` or textvariable write leaves the view alone: a long
  value inserted into an empty entry shows its *start*. Every redraw used to
  scroll to the cursor, which undid every `xview`.
- Text inserted strictly before the view moves it along, so the same characters
  stay on screen (view 10, insert 2 at 0 → 12); inserted exactly at it, it
  stays. A delete moves it back by the run's length, or to the start of the run
  if it was inside it. When the text no longer reaches the right edge, the draw
  pulls the view back (view 10, delete 12 to the end → 7).

**One deliberate difference:** Tk's cursor is a line *between* characters,
ours occupies a cell. So while the cursor is at the very end, the view may sit
one past `length − width`, leaving that cell for it. Otherwise a cursor typed to
the end of a full field would be drawn off its edge.

**Insert and delete carry the selection**, as of `TkCurses-61v`: they used to
drop it. Measured on Tk 9.0.2 with 2–5 selected in `abcdefgh`:

| Edit | Selection after |
|------|-----------------|
| insert 2 chars at 0, 1 or 2 (at or before its start) | 4–7 |
| insert at 3 or 4 (inside it) | 2–7 |
| insert at 5 or later (at or after its end) | 2–5 |
| delete 1–3 (across its start) | 1–3 |
| delete 3–4 (inside it) | 2–4 |
| delete 4–6 (across its end) | 2–4 |
| delete 2–5, 1–6 or 0–8 (all of it) | none |

So text inserted exactly at either end lands *outside* the selection. The
selection **anchor** moves with the text too, and outlives the selection: after
`selection_from(2)`, `selection_to(5)` and `delete(2, 5)`, a `selection_to(4)`
reads 2–4. An anchor sitting exactly on an insertion point moves only if the
selection starts there. With nothing selected, a Shift-arrow starts afresh at
the cursor, whatever anchor an edit left.

**The selection commands, as Tk's behave** (`TkCurses-bfy`). The manual
describes each in a sentence; these are the measurements behind them, on Tk
9.0.2 with `abcdefghij` and the cursor at 5. **None of them moves the cursor**,
and until `TkCurses-bfy` all three of ours did.

- `selection_from(i)` sets the anchor and nothing else; a selection already
  there stays. Ours used to clear it.
- `selection_to(i)` selects from the anchor to `i`.
- `selection_range(a, b)` **leaves the anchor**: range 2–6, then
  `selection_to(8)`, reads 0–8. A backwards or empty range clears the
  selection rather than being turned round.
- The anchor starts at 0. A click sets it to where it lands, as `selection
  from` does. `selection_clear`, a plain arrow and a delete of the whole
  selection all keep it. Replacing the text does **not** clamp it: anchor at 6,
  the text set to `abc`, six characters inserted at 3, then `selection_to(0)`,
  reads 0–9.
- `selection_adjust(i)` is **not** `selection_to`, which ours aliased it to.
  It moves the nearer end of the selection, making the far end the anchor,
  split at Tk's midpoint. On 2–6: `adjust(3)` → 3–6, `adjust(5)` → 2–5,
  `adjust(8)` → 2–8, `adjust(1)` → 1–6. The exact middle, `adjust(4)`, keeps
  whatever anchor there was, so it reads 0–4. With nothing selected it is
  `selection_to`. Shift-arrow with a selection present is an adjust: range 2–4,
  cursor 5, Shift-Right reads 2–6.
- One difference, deliberate: `selection_to` onto the anchor leaves Tk
  reporting an *empty* selection as present (`sel.first` equal to `sel.last`).
  Here nothing is selected.

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `width` | chars | Cells |
| `textvariable` | Variable | Same |
| `show` | char | Password mask |
| `state` | NORMAL/DISABLED/READONLY | Same |
| `justify` | LEFT/CENTER/RIGHT | Text alignment |
| `insertwidth` | pixels | Changed from 2, asks the terminal for a bar cursor (see "The insertion cursor is the terminal's own") |
| `exportselection` | puts the selection on PRIMARY | Same, against the in-process PRIMARY |
| `placeholder` | ghost text in an empty field | Same |
| `placeholderforeground` | its colour | Honoured; **dim** when unset (see below) |
| `highlightthickness` | focus ring, pixels | Accepted and answered, draws no ring; a focused entry draws its **border** bold, at any thickness |
| `validate` | validation condition | Same: `none`, `key`, `focus`, `focusin`, `focusout`, `all` |
| `validatecommand` | registered command | Callable given the proposed text |
| `invalidcommand` | registered command | Callable given the refused text, or nothing |

**Where Tk's documentation is silent, this file carries the measurement.**
`-placeholder` and `-placeholderforeground` arrived in Tk 9.0 and are documented
*nowhere*: they appear in the standard-options list of `entry(n)`,
`ttk_entry(n)` and `ttk_combobox(n)`, and no `.OP` entry describes them in any
of those, nor in `options(n)` or `ttk_widget(n)`. So there is no upstream page
to point a reader at, and a measurement that lives only in a commit message is
a measurement nobody will find. The rule below was taken off a real screen —
the behaviour cannot be read through the API at all, because `bbox()` reports
the index rather than the drawn text and the style layout has no placeholder
element to inspect.

**The placeholder is drawn if and only if the contents are empty.** Nothing
else gates it:

- **Focus does not hide it.** A focused empty field keeps the ghost text, with
  the insertion cursor before its first character.
- **`disabled` and `readonly` keep it too** — the opposite of the insertion
  cursor, which those states suppress.
- **It is not masked by `-show`.** A field with `show="*"` and a placeholder
  shows the placeholder as plain text, not as asterisks. `-show` hides
  *contents*, and there are none; so the placeholder short-circuits the mask
  rather than passing through it. This is the one that would have been got
  wrong — both live in `Entry._displayed()`.
- **It is never content.** `get()`, the `textvariable`, `index("end")` and the
  selection all behave as empty, and it cannot be selected by triple-click or
  `Control-a`.

It is a *standard* option, so the whole entry family has it — `tk.Entry`,
`ttk.Entry`, `ttk.Combobox` and `ttk.Spinbox` — not just the themed ones.

One deliberate divergence: with `placeholderforeground` unset, this draws the
ghost text **dim**. Tk leaves it in the ordinary foreground, which a GUI gets
away with because its placeholder is a different shade anyway. In a terminal
that would make ghost text indistinguishable from real content, so a field
would read as full while `get()` answers `""`. Dim is the terminal's own idiom
for "this is not your text". `TkCurses-xe9.3`.

**The selection is exported by being answered, not by being copied.** With
`-exportselection` true, a widget that makes a selection claims PRIMARY and
registers a handler; `Selections.resolve` asks that handler at the moment
PRIMARY is read. This is X11's own design, which tkinter exposes as
`selection_handle`, and taking it rather than copying the text is what makes
three of the four behaviours measured on Tcl/Tk 9.0.2 need no bookkeeping at
all: clearing the selection makes PRIMARY stop existing, selecting again makes
it exist, and an edit that moves the selection has to be noticed by nobody. The
fourth — that turning the option off drops PRIMARY immediately, with the
widget's own selection untouched — is the one explicit branch.

Ownership is claimed when a selection is *made*, never at construction: in Tk,
creating a second entry does not take PRIMARY from the first, and the widget
that selected most recently owns it.

An empty selection must read as "doesn't exist" rather than as the empty
string, so the handler raises. A caller needs to tell "nothing is selected"
from "an empty string was selected", which is why tkinter raises too.

PRIMARY's data does not leave the process (CLIPBOARD's can — see "Copy, cut
and paste"), but the per-widget option is meaningful without it. Text and
Listbox have it too, each on its own selection model: `TkCurses-163`,
`TkCurses-9e8`.

**A focused entry shows it in its border, in every state.** Tk signals the
focus on an entry two ways: the insertion cursor, and the
`-highlightthickness` ring. Only the first depends on the state — Tk's manual
says `readonly` draws "no insertion cursor ... even if the input focus is in the
widget" — so in Tk a locked field is still visibly focused, by its ring. This
library draws no ring, and for a while had nothing in its place: copying Tk's cursor rule faithfully left a
focused readonly entry indistinguishable from an unfocused one. `BorderStyle.attr`
carries it now, and `relief="flat"` still draws nothing, which matches a Tk ring
of zero thickness. Reported from UAT 41; the cursor half is pinned by its own
test so the two cannot be confused again.

**The ring's options are accepted, and draw nothing** (`TkCurses-gm66.1`).
`-highlightthickness`, `-highlightcolor` and `-highlightbackground` were
refused as X11 options with no cell equivalent, which stopped a tkinter program
at the line — and they are among the options tkinter code passes most, usually
`highlightthickness=0` on a Canvas, Frame or Button to hide X11's ring for
looks. Every classic widget takes them now, as Tk 9.0.2 does, with Tk's
default thickness (1 on Button, Canvas, Checkbutton, Entry, Listbox,
Radiobutton, Scale, Spinbox and Text; 0 elsewhere and on the root) and `""` for
the colours, as every colour here defaults. Menu and PanedWindow take them too,
where Tk refuses them — the harmless direction, since no Tk program passes them.

**None of them changes the focus cue.** Each widget that takes the focus shows
it with a sign one cell wide: ▶ ◀ around a Button, an underline on a
Checkbutton, Radiobutton, Menubutton or the active Listbox row, the bold border
described above on an Entry or Spinbox, a reversed sash, `[` `]` at the ends of
a Scale's trough. Following Tk literally — a thickness of 0 shows no focus —
would let a program that removed X11's ring for looks remove the only sign in a
terminal of where the keyboard is. Decided with the author;
`tests/test_button_tty.py` and `tests/test_entry_tty.py` pin the cue at
thickness 0.

**Tk's selection colours are taken, and a selection nobody coloured stays
reversed** (`TkCurses-gm66.3`). `-selectbackground`, `-selectforeground` and
`-selectborderwidth` on Entry, Spinbox, Listbox, Text and Canvas, and
`-inactiveselectbackground` on Text. Given either colour, a selection is drawn
in it, the widget's own colour standing in for the other, as a Text tag's do.
Given neither, or on a terminal with no colour, it is reversed as before.
`-selectborderwidth` is stored and answered only: a cell has no 3-D edge.
Measured on Tk 9.0.2, where the manual says nothing:

| What | Tk 9.0.2 | Here |
|------|----------|------|
| Colour defaults | `#c3c3c3` on `#000000` | `""`, the terminal's own: reversed |
| `-selectborderwidth` default | 1 on a Canvas, 0 elsewhere | the same |
| `-selectbackground ""` | refused, `unknown color name ""` | accepted, as every colour here |
| `-selectforeground ""` | accepted | accepted |
| `-selectborderwidth -3` / `2.7` | 0 / 2.7 | 0 / 3 (whole cells) |
| Text's select options and its `sel` tag's | one setting: configuring either changes what the other reads back, `-selectborderwidth` with the tag's `-borderwidth` too | the same for the colours; a tag here has no `-borderwidth` |

**`-inactiveselectbackground ""` hides an unfocused selection, and its default
does not.** Tk's manual: if it is empty, "no selection is shown when the window
does not have the focus". Tk's default is the same grey as the active colour,
so a selection normally stays visible; here every colour defaults to `""`,
which would have hidden every unfocused selection. The default is therefore a
`""` that can be told apart from one a program gives (`_TerminalsOwn`): it
reads back and compares as `""`, keeps the focused look, and survives
`configure(x=cget(x))`. A colour given draws the unfocused selection on it, as
in Tk. Decided with the author.

**Tk's state and part colours are taken, and a state nobody coloured looks as
it did** (`TkCurses-gm66.4`). Thirty-seven options on eleven widgets. Tk's
defaults are real colours (`#ececec`, `#a3a3a3`, `#d9d9d9`, `#b3b3b3`); here
each is `""`, so an active widget is still reversed and a disabled one still
dimmed until a program gives a colour, which is then drawn *instead* -
`BaseWidget._in_state`. A colour given on a terminal with no colour is not
drawn, and the old look stays. Given one colour of a pair, the widget's own
stands in for the other.

| Option | Drawn here as |
|--------|---------------|
| `activebackground`, `activeforeground` (Label, Button, Checkbutton, Radiobutton, Menubutton, OptionMenu) | the whole widget, border included, while `state` is `active` or the button is held down |
| `disabledforeground` (the same, Listbox, Entry, Spinbox) | the text while `disabled` |
| `disabledbackground`, `readonlybackground` (Entry, Spinbox) | the field in that state |
| `selectcolor` (Checkbutton, Radiobutton) | the indicator's background; with `indicatoron` off, the whole widget's while it is on |
| `activebackground`, `activeforeground`, `disabledforeground` (Menu) | the active entry, in the bar and in a posted menu; a disabled entry's text |
| `selectcolor` (Menu) | the tick or bullet of a chosen check or radio entry - the mark, not the brackets |
| `troughcolor` (Scale, Scrollbar) | the empty trough cells; the handle and thumb keep the widget's own |
| `activebackground` (Scrollbar) | the element `activate()` names |
| `activebackground` (Scale) | the handle, while `state` is `active` or it is dragged |
| `buttonbackground` (Spinbox) | the arrows |
| `activebackground` (Spinbox) | stored only: an arrow is not drawn held down |

**Active is what Tk would have made active, so far as a terminal sees it.** A
button held down is active: Tk only presses an active button, the pointer
being over it, and `tk::ButtonInvoke` sets `active` for its flash when Space
presses one. The pointer is seen only from a press to its release (see "Enter
and Leave" below), so a button is active while it is held over, and hovering
alone activates nothing; a program's `state="active"` and a Scrollbar's
`activate()` are honoured as given.

As everywhere here, `""` is accepted for each, where Tk refuses it for
`activebackground`, `troughcolor`, `buttonbackground` and, on a Menu, for
`activeforeground` and `selectcolor`. A menu *entry's* own colours are a
separate surface, still refused: `TkCurses-g373`.

**Tk's extra reliefs are taken; a whole widget's is a box, a part's shows only
when sunken** (`TkCurses-gm66.5`). Fourteen options on seven widgets. A relief
here is a box style (`style_for_relief`), and a box costs a cell on every
side, so only a whole widget can wear one. A slider, an arrow, a scrollbar
element or a menu entry is one cell deep, with no edge to draw a relief on.
Those show the one relief Tk's own bindings put on a part while it is held,
`sunken`, dim, as a sunken border is (`_part_relief`); any other relief draws
the part as it was.

| Option | Here |
|--------|------|
| `overrelief` (Button, Checkbutton, Radiobutton) | copied into `relief` by `<Enter>` and back by `<Leave>`, as `tk::ButtonEnter` / `tk::ButtonLeave` do on X11, along with `state` `active` / `normal`; the box changes with it |
| `offrelief` (Checkbutton, Radiobutton) | with `indicatoron` off, the box while off; `sunken` while on (`TkpDisplayButton`) |
| `sliderlength` (Scale) | the handle's length in cells |
| `sliderrelief` (Scale) | the handle, dim while sunken; a press on the handle sinks it, `raised` to `sunken` and `ridge` to `groove` (`tk::ScaleButtonDown`), and the release restores it |
| `activerelief` (Scrollbar) | the active element, dim while sunken; a press sinks it and the release restores it (`tk::ScrollButtonDown` / `ScrollButtonUp`) |
| `buttonuprelief`, `buttondownrelief` (Spinbox) | stored only. `DisplayEntry` in Tk 9.0.2's tkEntry.c draws each arrow raised, and sunken while it is the selection element; the code that would draw these two is under `#if 0`. So does this, dim while sunken (`TkCurses-gbzu`) |
| `activerelief` (Menu) | the active entry, dim while sunken |
| `activeborderwidth` (Menu), `elementborderwidth` (Scrollbar) | stored only: an entry or an element is one row |
| `buttoncursor` (Spinbox) | stored only, as `cursor` is: a terminal has no pointer shapes |

Measured on Tk 9.0.2, where the manual is silent:

| What | Tk 9.0.2 | Here |
|------|----------|------|
| A relief's spelling | a unique prefix (`fl`, `gr`), case-sensitive, no spaces: `bad relief "RAISED"`, `ambiguous relief "s"` | the same, and the same messages |
| `""` for a relief | refused as `ambiguous`, except `overrelief`, whose `""` means none and whose message adds `or ""` | the same |
| `sliderlength -5`, `activeborderwidth -2` | kept, read back negative | the same; drawn as one cell |
| `elementborderwidth` | default `""`; any negative reads back `""` | the same |
| `sliderlength` default | 30 pixels, against a `length` of 100 | 1 cell, the handle as it was, against a `length` of 20 |
| `offrelief` default; Checkbutton `relief` and `borderwidth` | `raised`; `flat` and 1 | `raised`; `flat` and 0 |

**The relief Tk draws on an indicatorless button is not its `relief`.**
`TkpDisplayButton` (`unix/tkUnixButton.c`) draws one that is on sunken, and
one that is off in `offrelief` - unless `relief` equals `overrelief`, which is
how it knows the pointer is over it, since the `<Enter>` binding copied one
into the other. The manual describes the result (a toolbar button: flat,
raised under the pointer, sunken while on) and not the comparison. Here that
decides the box's *style* only: whether there is a box at all is still
`relief` and `borderwidth`, so turning a button on or off never changes its
size. Tk's default border of 1 is 0 here, so the box appears only when a
program gives one.

**A long handle travels the trough less its own length.** Its middle cell is
where the value is - what `coords` reports and where ticks and the shown value
go - and both ends of the scale are reached with the handle still whole. A
handle longer than the trough is cut to it; one below 1 is 1. With more
places than values, or fewer, a drag sets the value nearest its place, as it
always has.

**What is not done.** Tk sinks a Button's `relief` while it is held
(`tk::ButtonDown`); a press here is drawn by its ▌ ▐ markers, so a held button
keeps its relief, and `<Enter>` while held does not sink it either - though a
held button dragged off loses its markers, as Tk's loses its sunken relief
(`tk::ButtonLeave`), and gets them back on `<Enter>`. Tk's
`tk::CheckEnter` also blends `selectcolor` with `activebackground` under the
pointer; that is not done. `overrelief` shows from the press to the release,
the only time the pointer is known to be over it. The ttk widgets built on
these keep ttk's bindings, which have no overrelief.

**Enter and Leave** (`TkCurses-70gx`). A terminal reports the pointer only
while a button is held, unless hover reporting (DEC 1003) is on, and it is
off by default: it sends a report for every cell crossed and takes the
terminal's own selection away. So `Tk._route` makes the crossings from the
reports there are, as X11 makes them under the implicit grab:

- a press first leaves the widget the pointer was last known over and
  enters the one pressed - `<Enter>` before `<ButtonPress>`, Tk's order;
- while held, only the widget pressed is told the pointer left it or came
  back; nothing else is entered, as nothing else would be under the grab;
- a release ends the visit with `<Leave>`, because nothing will report the
  pointer going and a widget must not stay active under a pointer long
  gone. With hover reporting on, the release enters whatever is under the
  pointer instead, as X11's ungrab does, and motion is followed from there.

Widgets outside a `grab_set` hear no crossings, as they hear no presses.
Only the widget under the pointer is told, not its ancestors: Tk's virtual
crossings (`NotifyVirtual`) are not made, though a binding on a toplevel
still sees each child's through the binding tags.

**A held mouse button repeats, as Tk's bindings repeat it** (`TkCurses-gm66.6`).
A terminal reports a press and, much later, a release, with nothing between;
the repeat is the application's own timer, one for the whole application as
Tk's `Priv(afterId)` is, stopped by the release (`tk::CancelRepeat`).

| Widget | Held down | Defaults |
|--------|-----------|----------|
| Button | invokes again after `repeatdelay`, then every `repeatinterval`, while the pointer is over it; the release does not invoke a press that has repeated (`tk::ButtonAutoInvoke`, `tk::ButtonUp`) | 0, 0: no repeat |
| Scale | a trough steps one `resolution` towards the click, and again (`tk::ScaleIncrement`) | 300, 100 |
| Scrollbar | an arrow scrolls a unit and the trough a page, and again; the trough goes on paging after the thumb passes the pointer, as Tk's does (`tk::ScrollSelect`) | 300, 100 |
| Spinbox | an arrow steps, and again; a press that is not held steps when it is **released** (`tk::spinbox::ButtonUp`) | 400, 100 |

Measured on Tk 9.0.2: the timings are integers, `" 7 "` read as 7 and `2.5`
or `""` refused, and a negative one is kept; `-jump` is a boolean. Tk's
Scrollbar reads all three back as strings (`'300'`, `'0'`); here they are
numbers, as every other widget's are.

**Two gestures changed to Tk's.** A classic Scale's trough used to jump the
handle to the click. In Tk it steps, and steps again while held - which is the
only thing `repeatdelay` and `repeatinterval` mean on a Scale - so it does that
here now, and only the handle drags, from where it was taken hold of rather
than jumping its middle to the pointer (`Priv(deltaX)`). The jump is on
button 2, as `tk::ScaleButton2Down` has it. And a classic Spinbox's arrow used
to step on the press; Tk steps on the release, or not at all if the press has
already repeated, so a click still steps once and a hold does not step one
extra time. Decided with the author.

**A held trough steps past the pointer, as Tk's does.** `tk::ScaleIncrement`
and `tk::ScrollSelect` never ask where the pointer is: they repeat the
direction of the first press until the release. Measured on Tk 9.0.2, a
Scale from 0 to 100 held over the value 20 had stepped to 56 after six
seconds. Most toolkits stop when the handle reaches the pointer; a person
expected that in UAT 21, and the author chose to keep Tk's behaviour.

**`-jump`** holds a Scrollbar's drag: the thumb follows the pointer and the
command is called once, with `moveto`, at the release (`tk::ScrollDrag`,
`tk::ScrollEndDrag`). Without it the drag scrolls as it goes, as before.

**A release that never arrives cannot repeat for ever.** ncurses drops mouse
reports it is not drained fast enough for (`_arm_press_recovery`), and a held
press is indistinguishable from one whose release was lost. A Button that
repeats is not given the 700 ms recovery, which would put it back up in the
middle of a hold; instead a second press anywhere, which cannot happen while
the first is still down, stops the repeat and puts the held button up
(`Tk._release_lost`).

**Where this stops short of Tk.** A repeat interval of 0 ends the repeat:
Tk's Scale and Scrollbar schedule the next step at 0 ms for ever. Tk's Scale
skips a step to catch up after a slow `command`; here the after-queue starts
counting once the command has returned. Tk cancels a Spinbox's repeat when a
held pointer comes back over it (`<B1-Enter>`), and that binding is not made
here.

**The ttk widgets repeat as ttk's scripts do** (`TkCurses-1wos`), through
`ttk::Repeatedly`: the action at once, again after 300 ms, then every 100 ms
- ttk/utils.tcl's `Repeat(delay)` and `Repeat(interval)`, fixed, with no
option to change them - until the release (`ttk::CancelRepeat`). A ttk
Scrollbar repeats its arrows by units and its trough by pages
(`ttk::scrollbar::Press`); a ttk Spinbox generates `<<Increment>>` or
`<<Decrement>>` on the press and again while held (`ttk::spinbox::Press`),
and a disabled one does nothing. A ttk Scale no longer jumps on button 1:
`ttk::scale::Press` steps a trough press by 1 - not `-resolution` -
towards the value under the pointer, the direction settled at the press,
and a press on the slider drags it centred on the pointer
(`ttk::scale::Drag` sets `[$w get $x $y]`, with no lead kept). Buttons 2 and
3 jump (`ttk::scale::Jump`). Measured on Tk 9.0.2: a ttk Scale from 0 to 100
at 50, pressed on the trough beyond the slider, reads 51 at once and 53 after
450 ms, and from 100 to 0 the same press reads 49 then 47. A ttk Button does
not repeat. `tests/test_auto_repeat.py` holds these.

**Validation gates `insert` and `delete`, not only keystrokes.** `-validate`
is a condition, and the two that name an edit - `key` and `all` - apply to a
programmatic edit exactly as to a typed one. So does `-state`: a `readonly` or
`disabled` entry ignores `insert` and `delete` outright, and a program that
needs to fill a locked entry writes its `textvariable`. Both were measured on
Tcl/Tk 9.0.2 by running the same 25 scenarios through `tkinter` and through
this library and diffing the text, the callbacks and the option afterwards.
`TkCurses-tvj`.

Two rules in that table are not guessable and carry the design:

- **An edit that changes nothing runs no callback.** Inserting `""`, deleting
  an empty range, deleting past the end - Tk's validator never sees any of
  them.
- **A validator that edits the entry, or that raises, turns validation off.**
  That is Tk's recursion guard, and this library needs it for the same reason:
  once programmatic edits are validated, a validator calling `insert` on the
  entry it is validating calls itself forever. Tk cuts the loop by setting
  `-validate` to `none` and leaving it there — the nested edit lands, the edit
  being validated is discarded, and the application has to put validation
  back. An exception from the validator is the same case (Tcl cannot read a
  missing return as a boolean) and notably does **not** run `invalidcommand`.
  An `invalidcommand` that edits the entry also turns validation off; one that
  merely raises does not.

**Tk has three validation conditions, and all three are here.** `-validate`
names which of them apply, and they are not variations on one thing — each has
its own trigger, its own idea of what a refusal means, and its own answer when
a callback misbehaves. The table is measured, 31 scenarios diffed against
`tkinter`:

| condition | fires when | a refusal means | modes that ask for it |
|-----------|-----------|-----------------|----------------------|
| edit | `insert`, `delete`, a keystroke | the edit is discarded; `invalidcommand` runs | `key`, `all` |
| focus | the focus arrives or leaves | nothing is undone; `invalidcommand` runs | `focus`, `focusin`, `focusout`, `all` |
| forced | the `textvariable` is written, or first attached | nothing can be undone; **validation is turned off** and `invalidcommand` stays **silent** | every mode but `none` |

Three consequences worth having in mind:

- **The focus condition gates nothing.** There is no proposed value to refuse,
  only the value already in the field, so a refusal is advisory. A validator
  that wants to reject what it sees has to change the text itself.
- **The forced condition cannot say no.** The variable already holds the value
  by the time the validator is asked, so Tk resolves the contradiction by
  disabling validation instead — and uniquely, runs no `invalidcommand`.
- **It fires on attachment too**, at construction and through `configure()`, so
  a widget given a variable it would refuse starts with validation already off.

The recursion guard is per *episode*, not per condition: any edit attempted from
inside any validation callback is itself an edit, hits the in-progress flag, and
that is what disables validation. Which is why a validator editing a `key`-mode
entry is cut off while the same validator on a `focusout`-mode entry is not —
under `focusout` the nested edit is not validated, so there is no loop to cut.
Falling out of one rule rather than two special cases is the point.

One divergence, the single disagreement in those 31 scenarios: a validator that
edits the entry while being asked about a variable write. Tk abandons the whole
update and leaves the widget holding the old text while the variable holds the
new — a widget out of step with its own `textvariable`. Here both the write and
the edit land. `TkCurses-doh` records it, with the measurement.

**`justify` places a text only while it fits** (`TkCurses-2431`). Tk's
`EntryComputeGeometry` starts a text no wider than the field at the left
edge, flush with the right one, or at half the room left over, and one
wider than the field at the left, scrolling as a left-justified one does.
Measured on Tk 9.0.2 with `bbox`: `Sample` in a field 20 wide starts at
character 14 right-justified and 7 centred, the same in `tk.Entry`,
`tk.Spinbox`, `ttk.Entry`, `ttk.Spinbox` and `ttk.Combobox` - the spinbox
arrows and the combobox's are outside the field. The one place this departs
is the insertion cursor: Tk's is a line on the edge after the last
character, ours a cell, so a right-justified text with the cursor at its end
would put the cursor off the field. While the field has the focus and can
be edited, one cell is kept free for it at the right, whether the cursor is
at the end or not, so the text does not jump a cell as the cursor moves
away from the end; it moves one cell when the focus comes or goes instead.
The same offset is applied to the selection, the cursor, `bbox`, `@x` and
clicks, in `Entry._shift`.

---

### Text Class

Multi-line text editor.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Scrollable text area |
| `bbox(index)` | ○ | Cell bounding box |
| `compare(index1, op, index2)` | ✓ | Compare indices |
| `count(index1, index2, *options, return_ints=False)` | ○ | Tk's options; pixels are cells; shaped as tkinter shapes it (TkCurses-mzj) |
| `debug(boolean=None)` | ○ | One flag for every Text, as Tk's; checks nothing |
| `delete(index1, index2=None)` | ✓ | Delete text |
| `dlineinfo(index)` | ○ | Display line info |
| `dump(index1, index2=None, command=None, **kw)` | ○ | Text, marks, toggles, windows and images in Tk's order |
| `edit(*args)` | ✓ | Tk's `edit` subcommands, `canundo` and `canredo` included |
| `edit_modified(arg=None)` | ✓ | Modified flag |
| `edit_redo()` | ✓ | Redo edit |
| `edit_reset()` | ✓ | Clear undo stack |
| `edit_separator()` | ✓ | Undo separator |
| `edit_undo()` | ✓ | Undo edit |
| `get(index1, index2=None)` | ✓ | Get text |
| `image_cget(index, option)` | ✓ | Embedded image's option |
| `image_configure(index, **kw)` | ✓ | Embedded image's options |
| `image_create(index, **kw)` | ✓ | Embed an image; answers its unique name |
| `image_names()` | ✓ | Embedded images' names |
| `index(index)` | ✓ | Parse index |
| `insert(index, chars, *args)` | ✓ | Text and tag-list pairs, as Tk takes them |
| `mark_gravity(markName, direction)` | ✓ | Mark gravity |
| `mark_names()` | ✓ | List marks |
| `mark_set(markName, index)` | ✓ | Set mark |
| `mark_unset(*markNames)` | ✓ | Delete marks |
| `mark_next(index)` | ✓ | Next mark |
| `mark_previous(index)` | ✓ | Previous mark |
| `peer_create(newPathName, cnf={}, **kw)` | ✓ | A Text at that path, sharing the contents; TkCurses-gm66.13 |
| `peer_names()` | ✓ | The other peers' paths, oldest first |
| `replace(index1, index2, chars, *args)` | ✓ | One undo step; the cursor kept as tkText.c keeps it |
| `scan_mark(x, y)` | ○ | In cells |
| `scan_dragto(x, y, gain=10)` | ○ | tkTextDisp.c's arithmetic, in cells |
| `search(pattern, index, **kw)` | ✓ | Find text |
| `see(index)` | ○ | Scroll to index |
| `yview_pickplace(*what)` | ✓ | As `see`, vertically; a whole number is a line put at the top |
| `yview(*args)` | ✓ | `moveto`, `scroll`, and Tk's older index and `-pickplace` forms; TkCurses-lg0p |
| `tag_add(tagName, index1, *args)` | ✓ | Add tag |
| `tag_unbind(tagName, sequence, funcid=None)` | ✓ | Unbind tag |
| `tag_bind(tagName, sequence, func, add=None)` | ✓ | TkTextBindProc's rules; peers share them |
| `tag_cget(tagName, option)` | ✓ | Get tag option |
| `tag_configure(tagName, **kw)` | ○ | Configure tag (attrs) |
| `tag_delete(*tagNames)` | ✓ | Delete tags |
| `tag_lower(tagName, belowThis)` | ✓ | Lower tag |
| `tag_names(index=None)` | ✓ | List tags |
| `tag_nextrange(tagName, index1, index2)` | ✓ | Next range |
| `tag_prevrange(tagName, index1, index2)` | ✓ | Previous range |
| `tag_raise(tagName, aboveThis)` | ✓ | Raise tag |
| `tag_ranges(tagName)` | ✓ | Tag ranges |
| `tag_remove(tagName, index1, index2)` | ✓ | Remove tag |
| `window_cget(index, option)` | ✓ | Embedded window's option |
| `window_configure(index, **kw)` | ✓ | Embedded window's options |
| `window_create(index, **kw)` | ○ | Embed a widget; shown only in the text that made it, not its peers |
| `window_names()` | ✓ | Embedded windows' paths |

**`yview`'s older form counts lines from 0** (`TkCurses-lg0p`). text(n)
keeps `yview ?-pickplace? lineNum|index` for old programs without saying
what a bare number means. tkTextDisp.c's `TkTextYviewCmd` tries it as a
whole number first and makes a B-tree line of it, so it counts from 0:
measured on Tk 9.0.2, `yview 3` shows line 4 at the top, `0` and `-1`
line 1, and `0x3` line 4. Only when it is no whole number is it an index
(`2.5` is the index 2.5), whose display line goes to the top - or, with
`-pickplace`, into view as `see` puts it. A whole number goes to the top
even with `-pickplace`. Past the end, the view stays as full as `end`
leaves it.

**Tag bindings follow tkTextTag.c's TkTextBindProc** (`TkCurses-mzj`), read
in Tk's C and measured on Tk 9.0.2 with generated events. They run before the
widget's own bindings, from the widget's event handler. The tags an event
reaches are those of the character under the pointer **as of the last pick**,
lowest priority first; with none there, a key event reaches the tags at
`insert`. A pick happens on Motion, Enter, Leave and a button's release,
never while a button is held (Tk's simulated grab), and finds no tags past
the end of a row. When the picked tags change, the ones left hear `<Leave>`
and the ones reached `<Enter>`. The order is fixed at the pick: TagBindEvent
does not sort again, so a `tag_raise` shows at the next one. Without hover
reporting a terminal reports no motion between clicks, so the pick comes from
the `<Enter>` before each click and is cleared by the `<Leave>` after it
(`TkCurses-70gx`), which is enough for a link. Tk also re-picks after an
edit moves the text under a still pointer; nothing here does.

**`dump` lists marks at one index in an order of its own.** Measured, Tk's
order at one index is tag-offs, tag-ons, marks, then text. Tag-offs come in
the order the tags were made and tag-ons the other way round. Marks follow
the order Tk's B-tree segments happen to hold them: newest set first, a
left-gravity mark ahead, but edits can reorder them. Here it is that rule,
always. A tag already on at the first index is not reported; one that stops
there is.

**`insert` reads Tk's `chars ?tagList chars tagList ...?`** (`TkCurses-mzj`).
It took every argument after the first as a tag name for the first text until
then, so `insert("1.0", "a", "t1", "b", "t2")` inserted only `a`, with three
tags. A tag list given, even `()`, replaces the tags the text would inherit
from both sides; measured, `insert("1.1", "W", ())` between two tagged
characters leaves `W` untagged. Text given a list at `end` was tagged a
newline too far.

**A disabled Text refuses edits from code too** (`TkCurses-aah`), as the
manual says: "no insertions or deletions are allowed". Measured on Tk 9.0.2,
`insert` and `delete` are ignored **silently**: nothing is raised and the
modified flag does not move. Tags, marks and the selection still change. (Tk's
`image_create` and `window_create` still embed while disabled, and so do
ours.) Ours used to accept both edits from
code, and a test asserted it, unmeasured. Fill a read-only display with
tkinter's idiom: `state="normal"`, insert, `state="disabled"`.

**Undo while disabled departs from Tk, deliberately.** Tk's disabled
`edit_undo` changes nothing in the text but still pops the undo group, so the
history stops describing the text: re-enable and redo, and `hello world`
became `hello world world`. Here a disabled undo or redo moves nothing, the
stack included. An empty stack still raises `nothing to undo`, as Tk's does
whatever the state.

**Line spacing is whole blank rows** (`TkCurses-gm66.8`). Tk's `-spacing1`,
`-spacing2` and `-spacing3` are pixels above each line, between the rows of a
wrapped one, and below each; here each unit is a row, as every other distance
here is a cell. Measured on Tk 9.0.2, with a 19-pixel font:

- `-spacing2` is split, the larger half above each continuation row and the
  rest below the row before it: 3 pixels gave line heights of 25 (5 + 19 + 1)
  and 28 (2 + 19 + 7). So a `spacing2` of one row goes above the continuation,
  none below.
- A click in the spacing answers the line it belongs to: with `-spacing1` and
  `-spacing3` of 16, every y from 2 to 40 gave `1.0`. Up and Down skip it.
- `yview` counts it, since Tk's fractions are of pixels.

Two departures. `dlineinfo` still answers a height of 1, the text row alone,
where Tk's includes the spacing. And nothing is drawn on a spacing row, a
tag's background included; the tag options `-spacing1/2/3` are still refused.

**`-maxundo` counts groups, oldest dropped first.** Measured: `-maxundo 2`
over four separated inserts undoes two and leaves `ab`; lowering it to 2 over
five groups drops the oldest three at once; 0 and -1 both keep everything.
A group counts once however many edits it holds.

**Peers share one store, and each Text is a view of it** (`TkCurses-gm66.13`).
`_core/textbuffer.py` keeps the string, marks, tags and undo stack in a
`_Store`; a `TextBuffer` is one widget's window onto it, renumbered so its
first line is `1.0`. The manual lists what a peer keeps to itself - `sel`,
`insert`, `current`, embedded windows, its configuration - and the view keeps
the three marks and the tag in the store under names of its own, so every
edit moves them with everything else. Tag *styles* and their order, the
modified flag and the undo stack are shared; `sel`'s style is not. Measured on
Tk 9.0.2, over a Text holding ten lines, with a peer over lines 3 to 6:

- `peer create` returns nothing and makes no Python object, so the peer here
  is an ordinary `Text` registered at the path, reachable by `nametowidget`.
  It takes `-startline`, `-endline`, `-undo`, `-maxundo` and `-autoseparators`
  from its creator and every other option from the defaults. `peer names`
  leaves out the widget asked.
- **Undo and `<<Modified>>`.** One stack: undo in either takes back an edit
  made through the other. `-undo` reads back per widget, but whichever peer
  set it last decides whether edits are recorded. `<<Modified>>` reaches
  every peer, the edited one first.
- **`-endline` is exclusive**, and both take 1 to one past the last line;
  0, negatives and anything further read back `""`, no limit. A start after
  the end is `-startline must be less than or equal to -endline` and changes
  neither.
- **The range moves with edits.** Both edges are marks with left gravity: a
  line inserted at the start edge (3.0) is inside and moves `-endline` to 7,
  one inserted at the end edge (6.0) is outside. An edge an edit leaves part
  way along a line snaps to that line's start: deleting `2.2`-`3.0` gives
  `-startline 2` and a first line `liline3`; deleting `5.2`-`6.0` gives
  `-endline 5`, without the joined line.
- Indices clamp to the window (`99.0`, `end+5l` and `2.0+20c` are all `4.0`),
  `search` sees only it, and `tag ranges` cuts at its edges. A shared mark
  outside it is listed by `mark names` but is `bad text index`. A peer's own
  `insert` is never outside: when the window moves above it, it is *moved* to
  the end of the window's last line, and below it, to `1.0` - moved, so a
  window that moves back finds it there and not where it was.
- `insert` set to `end` is held before the final newline, in any Text; this
  used to leave it after it, at `3.0` for two lines where Tk says `2.3`.
  `current` may sit at `end`.
- A window of no lines - `-startline` equal to `-endline`, or every line
  deleted through another peer - holds nothing: `end` is `1.0` and `get 1.0
  end` is empty. Deleting everything *in* a peer leaves one empty line, since
  it cannot remove the newline that ends its last.

Two departures. **An empty shell takes no text here.** Tk inserts it into the
store at the shell's position, where the shell itself cannot show it - a
program typing into what it sees as an empty widget then edits a line in
someone else's view. And **`tag.first`, `tag.last` and `tag nextrange` agree
with `tag ranges`.** In Tk they do not for a tag that crosses the end edge.
Over the peer above, a tag on store lines 5.1 to 8.0 has `tag ranges`,
`nextrange` and `prevrange` all 3.1 to 4.0, while `w.last` is 3.1. A tag over
the whole store has `tag ranges` 1.0 to 4.0, while `t.last` is 1.0 and there
is no `nextrange` from 1.0 at all. A tag inside the window has no such
disagreement. Tk's answers there contradict its own ranges, so the ranges win.

#### A bad index

Every one is a `TclError`, as tkinter's is; it used to be a `ValueError`,
which a program catching `TclError` crashed on (`TkCurses-g7nf`). Measured
through tkinter over Tk 9.0.2, the message quotes **the whole index as
given**, whichever part is wrong: `nomark+1c`, `1.0 +3 bogus`, `5.x`,
`end-1c+`, `@a,b`, `@3`, `@0,0 +zc` are each `bad text index "<that>"`, never
a message about the modifier or the mark alone. One case is named instead:
`t.first` for a tag that exists and covers nothing is `text doesn't contain
any characters tagged with "t"`, and for a tag never made it is `bad text
index "t.first"` - so a tag made by `tag_configure` alone is known to the
buffer from then on. The others: `bad comparison operator "<>": must be <,
<=, ==, >=, >, or !=`, `bad mark gravity "up": must be left or right`, `there
is no mark named "nomark"`.

**Embedded windows and images** (`TkCurses-r0gw`). Each stands in the text
as one character from the last private-use plane (U+100000 on), unique and
never reused, so that it is one index as Tk's segment is and every index,
mark and tag rule already in the buffer applies to it unchanged. Those
characters are never text: `get`, `search` and `count -chars` pass over
them, `dump` reports them as `window` or `image`, and `_core/cells.py`'s
`char_cells` asks the object how wide it is - a window's requested width or
an image's, plus `padx` either side - ahead of its cache, since a window's
width changes. A display row holding one gets blank rows above and below
it, encoded as spacing rows are (a negative line number), so a line grows
to its tallest object; `align` decides how many go above. Images are drawn
on the half-cell plane after the rows; windows are laid out by the
`EmbedLayout` the Canvas uses, the Text answering `_embedded_rect`.

Measured on Tk 9.0.2, and followed:

- `window_create` answers nothing; `image_create` answers the name, which
  is `name` or the image's, then `#1`, `#2` for one already in the text.
- Creating at `end` puts it before the final newline. `index(path)` and
  `index(name)` work, with modifiers.
- `count -indices` and `-xpixels` count it; `-chars` does not. A search
  for `cd` matches across a window between them; the regexp `c.d` does
  not.
- The window must be the text's child or a child of one of its
  ancestors: `can't embed .x in .t` otherwise, and for a toplevel or the
  text itself.
- Deleting its index destroys the window. Embedding it again, or packing
  it, leaves its old annotation holding `window ""`.
- **Creating one is not an undo step, but it joins the history.**
  Undoing the insertion it landed in removes it too, which destroys the
  window; undoing a deletion brings the text back without it. Here the
  undo and redo stacks are rebased when one is created (`_Store._rebase`),
  as if its character had always been part of the edit it fell in; after
  any edit, a character whose object is gone is taken out again,
  unrecorded (`_Store.tidy`).
- A line holding a widget taller than the text is that tall, with the
  text in the middle for `center`.

Kept from Tk, though it looks odd: a window scrolled partly out of view is
placed at full size and only clipped by the text's own window, so it can
cover the text's border. tkTextWind.c's `TkTextEmbWinDisplayProc` does the
same, and X clips a child only to its parent.

Not followed: Tk shows a window in one peer at a time, whichever displayed
it last. Peers here share the index and draw a blank where the window is;
only the text that created it lays it out. tkinter could not measure peer
display, and one window cannot be in two places in a terminal either.

---

### Listbox Class

Scrollable selection list.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Text list with box |
| `activate(index)` | ✓ | Highlight item; does not scroll, as in Tk |
| `bbox(index)` | ○ | Cell bounding box |
| `curselection()` | ✓ | Selected indices |
| `delete(first, last=None)` | ✓ | Delete items |
| `get(first, last=None)` | ✓ | Get items |
| `index(index)` | ✓ | Parse index |
| `insert(index, *elements)` | ✓ | Insert items |
| `nearest(y)` | ✓ | Nearest visible item |
| `scan_mark(x, y)` | ○ | In cells |
| `scan_dragto(x, y)` | ○ | Tk's `ListboxScanTo`, in cells: a row of drag is ten items; measured against Tk 9.0.2 with a fixed font. No class binding: the middle button pastes here |
| `see(index)` | ✓ | Scroll to item: to the edge if near, else centred |
| `selection_anchor(index)` | ✓ | Set anchor |
| `selection_clear(first, last=None)` | ✓ | Clear selection |
| `selection_includes(index)` | ✓ | Check selection |
| `selection_set(first, last=None)` | ✓ | Set selection |
| `size()` | ✓ | Item count |
| `itemcget(index, option)` | ✓ | An item's own colour, `""` where it has none |
| `itemconfigure(index, **kw)` | ✓ | `background`, `foreground`, `selectbackground`, `selectforeground`, kept with the item as rows come and go; TkCurses-5kg |

**It scrolls sideways, as of `TkCurses-019`** — `xview` and `-xscrollcommand`
were missing outright, so a horizontal scrollbar could not be attached at all.
The view is counted in characters and shared by every row. Measured on Tk 9.0.2
with a 10-wide listbox and a 30-character item, and matched here:

- `xview()` is the offset, and the offset plus the width, each over the
  **widest** item: `(0.0, 0.333…)`.
- a unit is one character; a **page is the width less two**, never under one
  (8 at width 10, 18 at 20, 1 at 3).
- `moveto` **rounds** to the nearest character, **halves up** (2.5 → 3, not
  Python's 2; `TkCurses-5e0`), and every form clamps so the
  widest item's end is as far as it goes.
- the offset is **not** re-clamped when items go: scroll one right, delete the
  wide item, and Tk answers `(0.2, 1.0)` over a 5-character remainder.

The named forms — `xview_moveto`, `xview_scroll`, `yview_moveto`,
`yview_scroll` — come from public `XView` and `YView` mixins, as in tkinter,
shared by Entry (and so Spinbox and the ttk entries), Text, Canvas, Listbox
and ttk.Treeview. They were per-widget copies on Text and Canvas and missing
everywhere else.

Vertical `moveto` on Listbox and ttk.Treeview **rounds** to the nearest row,
halves up: on 30 rows, 2.3, 2.5 and 2.7 rows put row 2, 3 and 3 at the top,
measured on Tk 9.0.2. Both used to truncate (`TkCurses-md5`). Text does not
round: Tk's Text scrolls by pixels and puts the part-shown line first, which
truncating already matches.

**Rendering:**
```
┌─────────────────┐
│▶ Item 1        ◀│  (selected)
│  Item 2         │
│  Item 3         │▒ (scrollbar)
│  Item 4         │▒
└─────────────────┘
```

**`justify` and `listvariable`, measured on Tk 9.0.2** (`TkCurses-gm66.10`).
`justify` aligns each item within the wider of the widest item and the
window - with a 30-character item in a 20-character list, right-justified
`ab` sat at the 30th, not the 20th - so the horizontal view moves every row
together. It takes a prefix (`cent` is `center`); `C` is `bad justification`
and `""` `ambiguous justification`. `justify` is checked on Listbox only so
far (`TkCurses-a2sg`).

`listvariable` holds the items as a Tcl list, read by `_tcl_list` with Tcl's
braces, quotes and one-letter backslash sequences. A variable that exists
gives the list its items; a name that does not is made, holding them. Every
`insert` and `delete` writes it back as a tuple, so a `StringVar` over it
reads as Python shows a tuple, `"('a', 'b')"`, exactly as tkinter's does.
Writing it replaces the items: the selection past the new end goes for good,
the active index stays, and a value that is not a list is refused with `can't
set "PY_VAR0": invalid listvar value` and the variable put back.

One departure: attaching a shorter variable drops the selection past the new
end. Tk keeps those indices hidden instead - `curselection()` leaves them
out - and appending items brings them back selected while inserting before
them does not, which is how its selection table happens to move rather than
a rule.

**`-selectmode` belongs to the bindings, not to the widget command**
(`TkCurses-xk41`). The manual says what each mode allows a *user* to do and
is silent on the commands; measured on Tk 9.0.2:

- `selection_set` only ever adds, in every mode: `selection_set(1, 4)` then
  `selection_set(0)` is `(0, 1, 2, 3, 4)` in browse and single too. Ours
  used to replace the selection in those two.
- `selection_clear(first)` clears `first` alone; ours used to clear every
  item when `first` was 0. Either command takes a range backwards
  (`4, 1`) or past the ends.
- Neither command sends `<<ListboxSelect>>`. Only a gesture does - once per
  gesture, through `tk::FireListboxSelectEvent`, whether or not it changed
  anything: a second click on the one selected item sends it again. Ours
  used to send one from each command, so a browse-mode click sent two.

What a gesture does is `listbox.tcl`'s, transcribed procedure by procedure:
a click or space is `tk::ListboxBeginSelect` (toggle in multiple, otherwise
make it the whole selection and the anchor); Control-click is
`tk::ListboxBeginToggle` and Shift-click `tk::ListboxBeginExtend`, both
doing nothing outside extended mode; Up and Down are `tk::ListboxUpDown`,
which takes the selection along in browse **and extended** (ours used to in
browse only). Shift-click runs the extended branch of `tk::ListboxMotion`:
the range from the anchor is replaced rather than added to, and moving its
end back over items a Control-click had kept gives them back. Ours used to
toggle on a plain click in extended mode and had no Control-click at all.

The state Tk keeps for that in the global `Priv(listboxPrev)` and
`Priv(listboxSelection)` is kept per Listbox here. Tk's is shared by every
listbox, but in the one interleaving measured - click and Control-click in
one list, a click in another, then Shift-click back in the first, with
`exportselection` off - the result was the same as without the other click,
`(1, 3, 4, 5)`. With `exportselection` on, Tk's default, the click in the
other list takes PRIMARY and clears the first one's selection, so the
Shift-click finds no selected anchor and begins afresh: `(5,)`, here as in
Tk.

**`exportselection`** (`TkCurses-9e8`), measured on Tk 9.0.2 with tkinter.
It differs from Entry's in two places, marked:

- selecting takes PRIMARY, which reads as the selected items **one per
  line** - `two\nfour` - and follows them as they change: delete the first
  of two selected and it reads as the second.
- clearing the selection keeps PRIMARY, which then reads as nothing - it
  raises.
- losing it - to an Entry, a Text, another Listbox - clears the selection
  and sends `<<ListboxSelect>>`, even when nothing was selected and **even
  while disabled**, where nothing else changes the selection.
- turning the option on exports what is selected at once. Turning it off
  **keeps PRIMARY**, which then reads as nothing, and a later loss leaves
  the selection alone. Entry gives PRIMARY up at once.
- with it off nothing is taken, and the list's selection survives others
  taking PRIMARY.

The Combobox popdown and the file dialog's two lists turn it off, as
`combobox.tcl` and tkinter's `FileDialog` do: choosing from them must not
take PRIMARY from an entry.

**The rest of `listbox.tcl`** (`TkCurses-cpk9`), each key, button and
virtual event bound as Tk binds it and named beside the code:

| Key | Tk does |
|-----|---------|
| Up, Down | `tk::ListboxUpDown`: move active, `see` it, take the selection along in browse and extended |
| Shift-Up, Shift-Down | `tk::ListboxExtendUpDown`: extended only, run the range to the new active item |
| Left, Right | `xview scroll ∓1 units` |
| Control-Left, -Right, -Prior, -Next | `xview scroll ∓1 pages` |
| Prior, Next | `yview scroll ∓1 pages`, then activate the top row; **select nothing**, in any mode |
| Home, End | `xview moveto 0` / `1` - sideways only |
| Control-Home, -End | activate, `see`, and select the first / last item, whatever the mode |
| Control-Shift-Home, -End | `tk::ListboxDataExtend`: extended runs the range, multiple only moves |
| space, Select, `<<Invoke>>` | `tk::ListboxBeginSelect` on the active item |
| `<<Copy>>` | the selection to the clipboard, if this list owns PRIMARY |
| Control-Shift-space, Shift-Select | `tk::ListboxBeginExtend` on the active item |
| Escape | `tk::ListboxCancel`: extended only, put back what the range replaced |
| `<<SelectAll>>` | everything; in single and browse, the active item alone |
| `<<SelectNone>>` | clear, except in browse |

Each is bound as listbox.tcl binds it - Up as `<<PrevLine>>`, Home as
`<<LineStart>>`, Control-Left as `<<PrevWord>>`, Control-Home as itself -
and the matcher chooses as Tk's does, measured on Tk 9.0.2: Control-Up runs
`<<PrevLine>>` because nothing binds `<<PrevPara>>`, Shift-Home runs
`<<LineStart>>`, Shift-space runs space's. A program can `event_add`
Control-p to `<<PrevLine>>` and the list follows, or `event_generate` one.
Nothing breaks: a handled key still reaches the toplevel's bindings and `all`'s, as
it does in Tk. Ours used to stop the keys it handled, which would have taken
Escape from a dialog whose list had the focus.

`<<SelectNone>>` is bound but has no key. Tk gives it Control-backslash,
which a tty turns into SIGQUIT, and binding it here would take the quit key
from every program with a Listbox; a program may `event_add` it.

Measured on Tk 9.0.2: with `<<LineStart>>` deleted, Home does nothing; an
unexported list's `<<Copy>>` leaves the clipboard alone.

The mouse: a press is `tk::ListboxBeginSelect`, the release activates the
item under the pointer, and a drag is `tk::ListboxMotion` - the selection
follows in browse, the range is re-run in extended, nothing happens in the
other two. A double-click is listbox.tcl's empty script: the second click
does nothing. Held outside the list, `tk::ListboxAutoScan` scrolls at once
and then every 50ms, a row above or below, else two columns beside. A
click below the last item selects the last item, as `index @x,y` is the
nearest one; ours used to select nothing.

`nearest` and `@x,y` clamp to the **visible** rows before the items:
measured on Tk 9.0.2, a pointer below a four-row list scrolled to 2 is item
5, not the last. That is what a drag held past the edge selects to.

**`activate` does not scroll; `see` centres** - measured on Tk 9.0.2 over
every top row and index on 20 items at heights 1 to 9, 3360 cases. The
bindings call `see` after `activate`; a program that calls `activate` alone
keeps its view, where ours used to scroll to it. `see` brings an item no
more than a third of the height out of view to the nearest edge and centres
one further away: on four rows from the top, `see(5)` puts 4 at the top,
not 2. Ours used to scroll as little as possible. A vertical page is the
height less two, never under one, as the horizontal page is; ours was the
whole height.

**A disabled Listbox** (`TkCurses-46ap`), measured on Tk 9.0.2: `insert`,
`delete`, `selection set`, `selection clear`, `selection anchor` and
`activate` are refused, silently. `curselection`, `selection includes`,
`get`, `see` and `yview` still work, and writing the `listvariable` still
replaces the items. The bindings still run - the view scrolls - but nothing
they would change can be, and no `<<ListboxSelect>>` is sent. A click does
not take the focus. The selection is kept and **not drawn**: `listbox(n)`
says so, and a screen capture confirmed it - a red `selectbackground` covered
3040 pixels of the selected row, and none once the list was disabled.

**Inserting and deleting move the anchor, the active item and the view**
(`TkCurses-ofko`). The anchor and active rules were measured on Tk 9.0.2
over every position, anchor and active item on lists of 0, 1 and 5 - 756
inserts and 769 deletes, all matching; the top-row rule was fitted to the
recorded sequences below, which it matches:

- insert `k` at `i`: the anchor moves on by `k` if `i <= anchor`; the active
  item likewise, then is kept on an item. So eight items inserted into a new
  list leave the active item at 7 and the anchor at **8**, past the end - Tk
  keeps the one on an item and not the other.
- delete `f..l` (with `l` cut to the last item; nothing if `f > l`): an
  anchor at or past `f` moves back by the count, never before `f`; an active
  item past `l` moves back, and one inside the range goes to `f`, kept on an
  item.
- the top row follows the same way: items inserted strictly above it push it
  down, and a delete at or above it pulls it back, never before `f`.
- `selection anchor` and `activate` clamp to an item: `anchor 10` on three
  items is 2.

Ours left the anchor alone on both and moved the active item only on insert.

`tests/support/record_listbox_gestures.py` records 613 sequences from real
Tk - clicks, double-clicks, drags, keys with every modifier listbox.tcl
binds and a few it does not, virtual events, the widget commands, insert,
delete and the state - with the selection, the event count, the active and
anchor indices, the top row, the columns scrolled off and the size after
every step. `tests/test_listbox.py` replays them. Two notes for whoever
re-records: the X keymap here has no keycode for `Select`, so Tk receives a
synthesised one as `??` and it cannot be measured; and Tk reads a second
press as a double only within 5 pixels of the first with no key event
between, so a "double-click" on another row is a plain click - the replay
follows that rule.

---

### Scrollbar Class

Scroll control widget.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `▲█░░▼` display |
| `activate(element=None)` | ○ | `arrow1`, `slider` or `arrow2`, drawn in `-activebackground` and `-activerelief` |
| `delta(deltax, deltay)` | ○ | Calculate delta |
| `fraction(x, y)` | ○ | Position fraction |
| `identify(x, y)` | ○ | Element at cell |
| `get()` | ✓ | Get scroll position |
| `set(first, last)` | ○ | Set scroll position |

**Mouse behaviour** follows Tk's `scrlbar.tcl`, which binds three things:
`<Button-1>` pages for a press on the trough, steps for a press on an arrow,
and for a press on the thumb *does nothing at all* except remember where the
press landed and where the view was; `<B1-Motion>` moves the view to that
remembered position plus `delta()` of the distance travelled, so the view
follows the pointer rather than jumping to it; `<ButtonRelease-1>` forgets
the drag. The implicit grab is what makes a drag that wanders off the bar
still arrive - with coordinates outside it, which is what the arithmetic
wants.

**Hover** follows `scrlbar.tcl` too (`TkCurses-mvvv`): `<Enter>` and
`<Motion>` run `activate [identify %x %y]`, `<Leave>` activates nothing, and
the release activates whatever is under the pointer (`tk::ScrollButtonUp`).
The press does not, and while it is held neither motion nor `<Leave>`
changes anything - Tk's `<B1-Motion>` and empty `<B1-Leave>` take those. Under
`tk_strictMotif` `<Enter>` puts `-activebackground` aside for `-background`
and `<Leave>` restores it. Measured on Tk 9.0.2 with `event_generate`; the
sequence is in `tests/test_scrollbar.py`. A pointer moving with no button
held reaches a widget only when the terminal is asked to report it -
`[mouse] report_hover`, off by default - so otherwise the hover shows only
what a press and release pass through.

**Keys** follow `scrlbar.tcl`, which binds the navigation virtual events
rather than the keys (`TkCurses-rs2l`). `<<PrevLine>>`/`<<NextLine>>` scroll a
unit and `<<PrevPara>>`/`<<NextPara>>` a page, on a vertical scrollbar only;
`<<PrevChar>>`/`<<NextChar>>` and `<<PrevWord>>`/`<<NextWord>>` the same on a
horizontal one; `<Prior>`/`<Next>` a page and `<<LineStart>>`/`<<LineEnd>>`
`moveto 0`/`1` on either. None breaks. Measured on Tk 9.0.2 by generating each
key on a focused scrollbar and logging its `-command`; the table is in
`tests/test_navigation_bindings.py`. ttk's scrollbar binds no keys.

**One difference: Tab passes a classic scrollbar by.** Tk's `-takefocus`
defaults to `""`, and `tk::FocusOK` then accepts any widget whose class
bindings mention `Key` - which the `<Key-Prior>` binding does, so in Tk Tab
stops on every classic scrollbar (measured: `tk_focusNext` of an Entry before
one is the scrollbar). Here `takefocus` defaults to false, so the keys answer
only once a program gives a scrollbar the focus or sets `takefocus`.

**Rendering:**
```
Vertical:    Horizontal:
    ▲        ◄██░░░░░░░░►
    █
    █
    ░
    ░
    ▼
```

---

### Scale Class

Slider control.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `[░░░████░░░]` |
| `get()` | ✓ | Get current value |
| `set(value)` | ✓ | Set value |
| `coords(value=None)` | ○ | Cell position |
| `identify(x, y)` | ○ | Element at cell |

**Keys** follow `scale.tcl` and `ttk/scale.tcl`, which bind the navigation
virtual events (`TkCurses-rs2l`). Line and character events step, paragraph
and word events take a big step, and `<<LineStart>>`/`<<LineEnd>>` set
`-from`/`-to`. **The orientation does not matter**: Up and Left both step
towards `-from`, Down and Right towards `-to`, on a vertical scale and a
horizontal one, and a reversed scale steps the other way. The classic step is
`tk::ScaleIncrement`'s - `-resolution`, or `-bigincrement` (a tenth of the
range when 0, never below the resolution); ttk's is `ttk::scale::Increment`'s,
1 and 10, whatever the range. `<Prior>` and `<Next>` are bound by neither
script and do nothing; nothing breaks, so the key reaches `all`. A disabled
scale does not move. Measured on Tk 9.0.2 with a scale from 0 to 100 at 50,
one key generated each; `tests/test_navigation_bindings.py` holds the table.

**Rendering:**
```
Horizontal: 0 [░░░░████████░░░░] 100
Vertical:   100
             ░
             █
             █
             ░
             0
```

---

### Spinbox Class

Entry with increment/decrement.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `[value ▲▼]` |
| `bbox(index)` | ☐ | Cell bounding box - not implemented; TkCurses-5kg |
| `delete(first, last=None)` | ✓ | Delete text |
| `get()` | ✓ | Get value |
| `icursor(index)` | ○ | Position cursor |
| `identify(x, y)` | ○ | Element at cell |
| `index(index)` | ✓ | Parse index |
| `insert(index, s)` | ✓ | Insert text |
| `invoke(element)` | ✓ | Invoke button |
| `selection_*()` | ✓ | Selection methods |

**Rendering:**
```
[  42  ][▲]
        [▼]
```

**What `-values`, `-from` and `-to` put in the field is not in the manual**,
and it was measured on Tk 9.0.2 through tkinter (`TkCurses-fdl9`).
Construction counts as the first configure, starting from no values and a
range of 0 to 0. The rule:

- **`-values` given and not empty: the first value.** That holds even when the
  list is the same one and the field held another of its values. An empty
  list falls through to the range.
- **Otherwise, with no values, `-from` ≠ `-to` and either of them changed:**
  the number the text starts with, as `sscanf("%g")` reads it (`" 5"` and
  `"5abc"` are 5), is clamped to the range and written in the spinbox's
  format (`%05.2f` makes `05.00`). Text that does not start with a number
  becomes `-from`.

So `Spinbox()` starts **empty**. `Spinbox(to=10)` starts at `0`. Setting
`-increment` alone changes nothing. `-state` and the validator do not stop
it, and a `-textvariable` is overwritten and written to:
`Spinbox(textvariable=StringVar(value="x"), to=10)` holds `0`, and so does
the variable. `tests/test_spinbox.py` has the measured table.

**The range, the step and the format, measured on Tk 9.0.2**
(`TkCurses-fdl9.1`, `TkCurses-fdl9.2`). The classic spinbox swaps a `-from`
above `-to`: `Spinbox(from_=10, to=0)` reports 0.0 and 10.0 and counts up.
A step follows tkEntry.c's `SpinboxInvoke`: from the number the text starts
with, stopping on an end it would pass (9.9 up by 0.3 to 10 is `10.0`) or,
with `-wrap`, going to the other end; text with no number goes to `-from`;
an empty range does not move. Numbers are written in tkEntry.c's
`ComputeFormat`, which is not documented: `%.Nf` with enough decimals for
multiples of the increment, counted from the most significant digit of the
range, and `%.(N-1)e` when that is shorter - 0.5 shows `1.0`, `1.5`;
0.001 to 1000 shows `0.000`; 1e-8 to 1e-6 shows `0.00e+00`. Because each
step reads the text it shows, 1.5 from 0 goes `0`, `2`, `4`.

ttk's is the script's (`ttk::spinbox::Spin`, `Adjust`, `FormatValue`), and
differs: the range is kept as given, `-from` is the bottom and `-to` the top
whichever is larger - with 10 and 0, both arrows take `5` to `10` - an empty
range is not refused, and the format is `%.Nf` from the first significant
digit of an increment below 1, else `%.0f`, so a value set to `1` steps
`1.5`, `2.0`. `tests/test_spinbox.py` holds both tables.

---

### Menu Class

Menu bar and popup menus.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Text menu box |
| `tk_popup(x, y, entry="")` | ○ | Show at cell pos |
| `activate(index)` | ○ | Highlight item |
| `add(itemType, cnf={}, **kw)` | ✓ | Add item |
| `add_cascade(**kw)` | ✓ | Add submenu |
| `add_checkbutton(**kw)` | ✓ | Add checkbutton |
| `add_command(**kw)` | ✓ | Add command |
| `add_radiobutton(**kw)` | ✓ | Add radiobutton |
| `add_separator()` | ✓ | Add separator line |
| `insert(index, itemType, **kw)` | ✓ | Insert item |
| `insert_cascade(index, **kw)` | ✓ | Insert submenu |
| `insert_checkbutton(index, **kw)` | ✓ | Insert checkbutton |
| `insert_command(index, **kw)` | ✓ | Insert command |
| `insert_radiobutton(index, **kw)` | ✓ | Insert radiobutton |
| `insert_separator(index)` | ✓ | Insert separator |
| `delete(index1, index2=None)` | ✓ | Delete items |
| `entrycget(index, option)` | ✓ | Get entry option |
| `entryconfigure(index, **kw)` | ✓ | Configure entry |
| `index(index)` | ✓ | Parse index |
| `invoke(index)` | ✓ | Invoke item |
| `post(x, y)` | ○ | Show at cell pos |
| `type(index)` | ✓ | Get item type |
| `unpost()` | ✓ | Hide menu |
| `xposition(index)` | ✓ | Where the entry's column starts, in cells (TkCurses-aj1.13.1) |
| `yposition(index)` | ○ | Cell Y position; within its column |
| `bind_accelerators(target=None)` | ✓ | **Not tkinter API** - binds each entry's accelerator text |

**Rendering:**
```
┌──────────────────────┐
│ New           Ctrl+N │
│ Open          Ctrl+O │
│──────────────────────│
│ Save          Ctrl+S │
│ Save As...           │
│──────────────────────│
│ Exit          Ctrl+Q │
└──────────────────────┘
```

**`-columnbreak`** lays a menu out in columns (`TkCurses-aj1.13.1`). Measured
on Tk 9.0.2 with `xposition`, `yposition` and the `@x,y` index:

- an entry with `-columnbreak` starts a new column **at the top**, beside the
  column before; the rest go below the entry before them;
- **each column is as wide as its own** labels and accelerators need — a
  column of short entries stays narrow beside a wide one (65 px between 166
  and 116, measured) — and the menu is as tall as its tallest column;
- every kind but a **separator**, which Tk refuses it on ("unknown option");
- `@x,y` picks by column, and `@y` alone reads the first one.

**Closing a dropdown of the menubar clears the bar's highlight**, as Tk's
`MenuUnpost` does (`$parent activate {}`, read from Tk 9.0.2); the focus goes
back where it was. The bar is never posted, so the clean-up that a posted
parent gets never ran for it, and the entry stayed highlighted after Escape —
looking like a keyboard mode the bar was not in. **An open menu keeps every
key**, as Tk's Menu class does (`<KeyPress>` … `break`): a key it had no use
for used to go on to `bind_all` shortcuts behind it. **Left in a dropdown of
the menubar** opens the menu to its left, where it closed the dropdown; only
a submenu closes back to its parent. All three found running UAT 46.

**An entry with an image is as tall as its image** (`TkCurses-z3zs`). An
image is half-block pixels, two pixel rows to a cell, so a 16x16 icon makes an
8-row entry; `compound` `top` or `bottom` adds the label's row. Measured on
Tk 9.0.2: `-compound` defaults to `none`, which shows the image in place of
the label; a missing image is `image "x" does not exist` and a bad compound
`bad compound "x": must be bottom, center, left, none, right, or top`; and
`yposition` moves each later entry down by the one before - a 16x40 image
makes its entry 45 pixels where a plain one is 24, and with `-compound top`
66. Here every row-per-entry assumption became a row-per-height one:
`lay_out` stacks entries by height, `yposition`, hit-testing and where a
cascade opens read those rows, and a menu too tall for the screen scrolls by
rows so the whole active entry shows (`visible_window` with `heights`). A
menubar draws only labels.

**The arrows are the navigation events** (`TkCurses-rs2l`). menu.tcl binds
`tk::MenuUpArrow` and the rest to `<<PrevLine>>`, `<<NextLine>>`,
`<<PrevChar>>` and `<<NextChar>>`, so Control-p and Control-n move through a
menu too, a key `event_add`ed to one of them does, and an arrow
`event_delete`d from its event does nothing. Those four bindings do not break
in Tk; here they do, keeping the rule above that an open menu keeps every key.

**A window's `-menu` is a widget, a path name, or `""` for none.** The manual
says only that it names a menu to use as the menubar. Measured on Tk 9.0.2:
`""` is the default `cget("menu")` answers and how a program removes a bar,
and the menu itself survives; a path name works as well as the widget; and the
name is **not checked when it is set** — `.nosuch`, or a Frame's path, is
stored as given and shows no bar. Here `""` used to crash
(`TkCurses-un8i`), and replacing or removing a bar left the old one drawn and
live while the children got its row back. Now the old bar is unmapped and
stops being a menubar. `menu=None` changes nothing, as with every option
given as `None` (see "An option given as None" under the deliberate
differences).

**The menu bar is reached from the keyboard as Tk's X11 bindings reach it**
(`TkCurses-r3og`): `menu.tcl` binds `<F10>` to `tk::FirstMenu` and
`<Alt-Key>` to `tk::TraverseToMenu` on `all`, and neither was here, so only
the mouse reached a menu bar. Measured on Tk 9.0.2 under X11, and followed:
F10 opens the first menu with its first entry that can be chosen active;
Alt and a letter, either case, opens the menu that letter is underlined in,
or runs a command entry on the bar, or posts a Menubutton so underlined,
passing over disabled ones (`tk::MenuFind`); Escape closes it and the focus
goes back where it was. When the bar's first entry is a command, F10 only
makes it active and gives the bar the focus (`tk::MenuFirstEntry`). The
editing widgets bind `<Alt-Key>` to nothing in Tk (`entry.tcl`,
`text.tcl`, `spinbox.tcl`, `ttk/entry.tcl`), so an Alt letter is not typed
and still reaches `all`; here they typed it. GNOME Terminal keeps F10 for
its own menu, which is why the Alt letters matter more.

Tk's keyboard traversal ignores columns (`menu.tcl`, `MenuNextEntry`): Up and
Down go by index and wrap, so Down from a column's foot is the next column's
top; Left and Right still move between menus. A menu in columns **does not
scroll** — a column is how a long menu was made short — where a single
column scrolls as before.

```
┌─────────────────────────┐
│ Black   Purple  Lime    │
│ Maroon  Teal    Yellow  │
│ Green   Silver  Blue    │
└─────────────────────────┘
```

**`bind_accelerators()`** — **not tkinter API**, a TkCurses addition like
`winfo_colordepth`. Tk's `-accelerator` is display only: its manual says the
option "does not actually set the corresponding binding (which can be achieved
using the bind command)". So an application writes every shortcut twice, as
text and as a binding, and the two drift. `menu.bind_accelerators()` reads
each entry's text, in its submenus too, and binds it:

- the text is read as people write it (`_core/menus.accelerator_sequence`):
  `Ctrl+O`, `Ctrl-O`, `Control+O`, `^S`, `Alt`/`Option`, `Meta`, `Shift`,
  `F1`–`F24`, `Del`, `PgUp`, `Esc`, `Enter` and the rest, punctuation
  (`Ctrl++`, `Ctrl+,`), and **chords** — `Ctrl+X Ctrl+S`, `Ctrl+K, Ctrl+C`
  (a comma with a space after it separates keys; one without is the key);
- a letter is the key, not the character — `Ctrl+O` is the o key — and
  `Shift+O` the O. A terminal sends Ctrl+Shift+O as it sends Ctrl+O, so that
  one can be bound but not told apart here;
- **all or nothing**: every accelerator is read before anything is bound,
  and one that cannot be read raises `ValueError` naming its entry;
- bindings are **added**, never replacing the application's own; by default
  through `bind_all`, or on a `target`;
- each runs its entry by **what it is**, not its index, so entries inserted
  later do not move a shortcut onto another; a deleted entry's shortcut does
  nothing, and a disabled one's does nothing, as choosing it would.

**`font`, `type` and `tearoffcommand`** (`TkCurses-gm66.10`). `font` styles
the labels as every widget's font does here: bold, italic, underline. `type`
is `menubar`, `normal` or `tearoff`, or a prefix (`m` is `menubar`), and
`""` is `ambiguous type`; it is checked and kept, and changes nothing here.
`tearoffcommand` is called when the menu is torn off, below.

**Tear-off menus** (`TkCurses-1k8x`). Measured on Tk 9.0.2, and held by
`tests/test_menu_tearoff.py` comparing call by call: `-tearoff` defaults to
false (8.6's was true); the tear-off entry is index 0, of type `tearoff`,
with `-background` and `-state` and nothing else; an insert at 0 goes after
it, `delete 0` leaves it, `add tearoff` is refused, and turning the option
on and off adds and removes it. Invoking it is `tk::TearOffMenu`: a copy
made by `tk::MenuDup` - every option, every entry, type `tearoff` - named
`tearoffN` in the nearest toplevel, posted where the menu was, titled by
`-title`, else the Menubutton's text or the active label of the parent menu,
else its own name; `-tearoffcommand` gets both names, and the widget's
`invoke` returns the copy's. The copy keeps its tear-off entry at 0 with no
height (`yposition 0` equals `yposition 1`), and `tk::MenuNextEntry` skips
it. Here the copy is a Menu taking no grab, with the title in its border; a
choice leaves it up, and Escape destroys it because there is no window
manager to close it. A press raises it and takes the focus, and a press on
its title row drags it, kept on the screen, as `_toplevel_press` drags a
Toplevel - the author's request on running UAT 50. Moving it showed that a
Menu never cleared the cells the painter writes past curses, so its
pictures stayed where it had been; it clears them on every redraw now, as
Label does. Tk's `clone` also copies cascade submenus; here the
copy's cascades open the originals.

---

### Menubutton Class

Menu trigger button.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `[Menu ▼]` |

---

### OptionMenu Class

Dropdown selection.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master, variable, value, *values, **kw)` | ○ | Dropdown list |
| `destroy()` | ✓ | Destroy widget |
| `__getitem__(name)` | ✓ | Get menu |

**Rendering:**
```
Closed:    [Option 1    ▼]
Open:      [Option 1    ▼]
           │ Option 1    │
           │ Option 2    │
           │ Option 3    │
           └─────────────┘
```

---

## The pixel

**One pixel is one cell wide and half a cell tall.** Everything in the
library that claims to draw in pixels means this one, and there is only one
of them.

A character cell is about twice as tall as it is wide. A surface that treated
one cell as one unit would draw every circle as a tall ellipse, so the plane
is divided across the middle instead: `▀` is the upper pixel, `▄` the lower,
`█` both. Each half is very nearly square, so a circle comes out round.

Quadrant glyphs (`▖▗▘▝▚▞▙▟`) would give four pixels per cell rather than two.
They are not used, and the reason is the same one: a quadrant is half as wide
as it is tall, so the extra resolution would be bought by making every shape
wrong again. Resolution was traded for aspect ratio deliberately.

`tkcurses._core.canvas` owns this. Rasterising and compositing are kept
apart: the rasterisers turn geometry into a set of pixels, and `compose()`
folds each pair of pixel rows into one cell — a glyph and up to two colours.
Neither touches curses, so the awkward cases (an oval one pixel tall, two
colours meeting inside a single cell) can be exercised directly.

**Two coordinate systems meet wherever this plane is exposed, and confusing
them is the only real hazard.** Widget dimensions — `width`, `height`,
geometry, padding — are in **cells**, like every other widget in the library.
Content coordinates on a pixel surface are in **pixels**. A canvas 40 cells
by 10 is a plane 40 pixels by 20.

Text is the one thing that cannot live on the plane, because a glyph occupies
a whole cell. A text item snaps to the nearest cell row and, while it is on
top, nothing else can share those cells.

Both pixel surfaces — Canvas and the image classes — are the same plane, in
the same units, composed by the same function. That is what lets an image be
drawn onto a canvas at all.

---

#### Why not finer sub-cells

Unicode offers quadrants (2x2 per cell) and sextants (2x3), and a renderer
like chafa matches an 8x8 block against a whole symbol set. **The half-cell
plane is kept, and measured rather than assumed.**

Each plane rendering the same picture into the same 106x33 cells, two colours
per cell, scored perceptually against one common reference at 8x8 sub-cell
resolution:

| | mickey.gif (cartoon) | earth.gif (photograph) |
|---|---|---|
| half blocks, 1x2 | 21.24 | 13.92 |
| quadrants, 2x2 | 18.54 (+12.7%) | 13.75 (+1.3%) |
| sextants, 2x3 | 17.78 (+16.3%) | 14.15 (**−1.6%**) |
| chafa-like, 8x8 | 16.95 (+20.2%) | 17.27 (**−24.0%**) |

**A finer plane helps hard-edged art and hurts a photograph**, which is the
opposite of the intuition that more detail is better. The reason is that a
cell still has only two colours however many sub-pixels it is cut into: six
sub-pixels sharing two colours forces each one further from its true value
than two sub-pixels sharing two colours. A cartoon's cells are mostly one
flat colour meeting another, so the extra positions pay; a photograph's cells
are gradients, so they do not.

So the gain is around 16% on cartoons and nothing on photographs, against:
a pixel that is no longer square-ish (a quadrant is half as wide as tall,
which squashes a circle — see **The pixel**), a plane no longer shared with
Canvas, a symbol search per cell per frame, and a font that may not have the
glyphs. Declined on that basis. `TkCurses-58f`.

The model used for the 8x8 row is an idealisation — two colours per cell
chosen as the extremes along the cell's widest axis — rather than chafa's
actual symbol matching, so it flatters that row if anything.

### Canvas Class

A drawing surface, measured in half-cells. See **The pixel** above: item
coordinates are in pixels, `width` and `height` are in cells.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Pixel plane; `width`/`height` in cells |
| `addtag(tag, method, *args)` | ✓ | Any search `find` takes (TkCurses-7jv) |
| `addtag_above(newtag, tagOrId)` | ✓ | Tag above |
| `addtag_all(newtag)` | ✓ | Tag all |
| `addtag_below(newtag, tagOrId)` | ✓ | Tag below |
| `addtag_closest(newtag, x, y, halo=None, start=None)` | ○ | As `find_closest` |
| `addtag_enclosed(newtag, x1, y1, x2, y2)` | ✓ | Tag enclosed |
| `addtag_overlapping(newtag, x1, y1, x2, y2)` | ✓ | Tag overlapping |
| `addtag_withtag(newtag, tagOrId)` | ✓ | Tag with tag |
| `bbox(tagOrId=None)` | ○ | Bounding box, in pixels |
| `canvasx(screenx, gridspacing=None)` | ○ | Window column to canvas pixel, as `event.x` is; `gridspacing` ignored (TkCurses-0n21) |
| `canvasy(screeny, gridspacing=None)` | ○ | Window row to canvas pixel (its upper half) |
| `coords(tagOrId, *args)` | ○ | Get/set coords, in pixels |
| `create_arc(...)` | ○ | Rasterised; `start`, `extent` and `style` as Tk reads them |
| `create_bitmap(...)` | ○ | `@file` drawn as pixels; a built-in name is one cell's glyph |
| `create_image(...)` | ○ | On the half-cell plane, one image pixel a canvas pixel; follows its image |
| `create_line(...)` | ○ | Rasterised to pixels |
| `create_oval(...)` | ○ | Rasterised; round, not elliptical |
| `create_polygon(...)` | ○ | Rasterised to pixels |
| `create_rectangle(...)` | ○ | Rasterised to pixels |
| `create_text(...)` | ○ | Snaps to a cell row; a glyph is a whole cell |
| `create_window(...)` | ○ | The canvas manages the widget; `width`/`height` in pixels; top snaps to a row |
| `dchars(tagOrId, first, last=None)` | ✓ | Characters of a text item, points of a line or polygon |
| `delete(tagOrId)` | ✓ | Delete item |
| `dtag(tagOrId, tagToDelete=None)` | ✓ | Remove tag |
| `find(method, *args)` | ✓ | Tk's search commands, refused in Tk's words |
| `find_above(tagOrId)` | ✓ | Above the topmost item named |
| `find_all()` | ✓ | Find all |
| `find_below(tagOrId)` | ✓ | Below the lowest item named |
| `find_closest(x, y, halo=None, start=None)` | ○ | Distance to the extent, not the ink; `start` goes round as Tk's does |
| `find_enclosed(x1, y1, x2, y2)` | ✓ | Whole extent inside, edges included |
| `find_overlapping(x1, y1, x2, y2)` | ○ | Extent meets the area; hidden items passed over |
| `find_withtag(tagOrId)` | ✓ | Find with tag |
| `focus(tagOrId=None)` | ✓ | The text item with the insertion cursor, shown as the terminal's cursor |
| `gettags(tagOrId)` | ✓ | Get tags |
| `icursor(tagOrId, index)` | ✓ | One cursor per text item, as Tk keeps |
| `index(tagOrId, index)` | ✓ | Number, `end`, `insert`, `sel.first`, `sel.last`, `@x,y` |
| `insert(tagOrId, index, string)` | ✓ | Text, or a line's or polygon's points |
| `itemcget(tagOrId, option)` | ✓ | Get option |
| `itemconfigure(tagOrId, **kw)` | ○ | Configure (limited) |
| `move(tagOrId, dx, dy)` | ○ | Move by cells |
| `moveto(tagOrId, x='', y='')` | ✓ | The lowest item's extent to the point, the rest with it |
| `postscript(**kw)` | ✗ | Raises: a terminal canvas has no PostScript |
| `scale(tagOrId, xo, yo, xs, ys)` | ○ | Coordinates scale and round to pixels; text keeps its size, as in Tk |
| `scan_mark(x, y)`, `scan_dragto(x, y, gain=10)` | ○ | Tk's arithmetic; a row of `y` is two units |
| `select_*()` | ✓ | Tk's anchor rules; drawn in `selectforeground`/`selectbackground` |
| `tag_bind(tagOrId, sequence, func)` | ✓ | Bind event |
| `tag_unbind(tagOrId, sequence, funcid)` | ✓ | Unbind event |
| `tag_lower(tagOrId, belowThis)` | ✓ | Lower item |
| `tag_raise(tagOrId, aboveThis)` | ✓ | Raise item |
| `type(tagOrId)` | ✓ | Get item type |

**A window item makes the canvas a geometry manager** (`TkCurses-aj1.16.1`),
as it is in Tk (tkCanvWind.c registers one called `canvas`). Here that is a
fourth layout beside a container's main manager, place's and a paned window's
panes: `_core/embed.py`'s `EmbedLayout`, which the engine applies last and
which keeps no options - it asks the canvas for each window's rectangle, and
the canvas answers from the item's point, `anchor`, `width` and `height` and
the view. A redraw compares those rectangles with the last ones applied and
queues a layout only on a change, so moving, scrolling and a window's own
new request all reach it without a redraw ever laying out twice. The same
layout lays out a Text's embedded windows; see the Text class.

Measured on Tk 9.0.2 and kept: a window wholly out of view, or whose item is
hidden, is unmapped rather than clipped to nothing, as `DisplayWinItem`
does; a second item given the window takes it, and the first reads back
`window ""`; packing, gridding or placing it takes it from its item; deleting
the item unmaps it and leaves it with no manager; destroying it empties the
item, whose bbox goes back to Tk's single pixel. The window must be a child
of the canvas or of one of its ancestors, and not a toplevel or the canvas,
else `can't use .x in a window item of this canvas`. Not kept: `width` and
`height` are canvas pixels, so `height` counts half-rows, and the window's
top snaps to a whole row, because a widget is drawn in cells.

**Scrolling options, measured on Tk 9.0.2** (`TkCurses-gm66.10`).
`xscrollincrement` and `yscrollincrement` are the unit `scroll N units` moves
by, and the view only ever rests on a multiple of one: with 30, `moveto` 47
pixels landed on 60. At 0, Tk's default, a unit is a cell - two pixels down,
one across - as before; a vertical view still rests on a whole cell.
`confine` (default on) keeps the view inside the scroll region; off, it went
50 pixels above the top for 5 units and to twice the region's height for
`moveto 2`, and turning it back on pulls the view inside at once. `offset`,
the stipple origin, is checked (`x,y`, `#x,y` or an anchor) and kept: there
are no stipples to align.

**Where a rectangle or oval stops: canvas(n) is right only without an
outline** (`TkCurses-swxf`). The manual says a rectangle includes "its upper
and left edges but not its lower or right edges", and an oval the same.
Measured on Tk 9.0 by reading a Tk window's own pixels (`import -window`
on its `winfo_id`, XGetImage through Xwayland - a root-window grab fails
under Wayland), `create_rectangle(10, 10, 16, 14)`:

| | columns | rows |
|---|---|---|
| fill, `outline=""` | 10-15 | 10-13 |
| fill and outline | 10-16 | 10-14 |
| outline only | 10-16 | 10-14 |

So the fill stops before x2 and y2, as `XFillRectangle` and `XFillArc` do
given the width `x2 - x1`, and a one-pixel outline is drawn on them. Ovals
measure identically. TkCurses filled through x2 and y2 in both cases; now
an outline-less fill stops short and an outlined shape is unchanged.

---

### PanedWindow Class

Resizable paned container.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Paned container |
| `add(child, **kw)` | ✓ | Add pane |
| `remove(child)` | ✓ | Remove pane |
| `forget(child)` | ✓ | Alias for remove |
| `identify(x, y)` | ○ | Identify at cell |
| `proxy(*args)` | ○ | Tk's `proxy coord`, `forget` and `place` |
| `proxy_coord()` | ○ | Where it was last placed, kept after `proxy_forget`, as in Tk |
| `proxy_forget()` | ○ | Takes the proxy panel down |
| `proxy_place(x, y)` | ○ | Along the panes, nought to the far side less the sash; across, the border |
| `sash(*args)` | ○ | Tk's `sash coord`, `dragto`, `mark` and `place`, refusals in Tk's words |
| `sash_coord(index)` | ○ | Sash cell coords; an index that is not a sash is Tk's `invalid sash index` |
| `sash_mark(index)` | ○ | The mark `sash("mark", index, x, y)` set; `dragto` moves by the distance from it, from where the sash is, and leaves it |
| `sash_place(index, x, y)` | ○ | Place sash; pins every pane's `width`, as Tk's `MoveSash` |
| `panecget(child, option)` | ✓ | Get pane option |
| `paneconfigure(child, **kw)` | ✓ | Configure pane |
| `panes()` | ✓ | List panes |

**Rendering:**
```
Horizontal:          Vertical:
┌────────┬────────┐  ┌─────────────────┐
│ Pane 1 │ Pane 2 │  │     Pane 1      │
│        │        │  ├─────────────────┤
│        │        │  │     Pane 2      │
└────────┴────────┘  └─────────────────┘
         ║ (sash)            ═ (sash)
```

**The sash, its handle and its proxy, as Tk's** (`TkCurses-gm66.9`). Measured
on Tk 9.0.2, with each pixel a cell here:

- **A sash's span** is `sashwidth`, or `handlesize` when a handle is shown and
  that is wider, with `sashpad` either side. Sashwidth 4 under handlesize 8
  put the second pane 8 past the first, and 18 with sashpad 5. Every cell of
  the span, padding included, answers `identify` as the sash.
- **`sash_coord` names the drawn line**, not the span: a 4-pixel sash under an
  8-pixel handle after a 100-pixel pane is at 102, and `sash_place` at 150
  reads back 150.
- **The handle is `handlepad` from the sash's start**, `handlesize` long and
  wide, centred across. It used to be drawn in the middle of the sash; the
  author chose Tk's placement, so every handle moved to one cell from the top
  or left. A label on that row of a pane narrower than the label covers it,
  because a child is not yet clipped to its container (`TkCurses-wbov`).
- **`width` and `height`** replace what the panes ask for, either alone; `""`
  hands the question back. 300 over two 100-pixel panes asked for 300.
- **`opaqueresize` off** leaves the panes alone during a drag and moves a proxy
  line instead, placing the sash there on the release, as
  `tk::panedwindow::DragSash` and `ReleaseSash` do. Tk raises a window for its
  proxy; the panes here are panels above the paned window's own, so the proxy
  is a panel too, drawn as the sash in `proxybackground`.

**Pane sizes are Tk's arithmetic** (`TkCurses-g60s`), from
`generic/tkPanedWindow.c`: `ArrangePanes` for the sizes, `MoveSash` for a
sash moved, `ComputeGeometry` for what the window asks for. They used to be
our own - every change shared evenly, a `width` ignored once laid out - and
`examples/layout.py` found it: Tk gave two panes of 50 with minsizes 120
and 200 in 600 pixels 120 and 475, and put all of a resize in the second.
Held to Tk differentially, as the grid is: random windows, horizontal and
vertical, with minsizes, `stretch`, `width`, then resized, reconfigured and
sashes placed, every sash and the requested length compared. 1200 of 1200
agree; 200 are in `tests/support/paned_reference.json`, replayed by
`tests/test_paned_reference.py`. What the manual does not say:

- **A pane has two sizes.** `width` is the option; `paneWidth`, which Tk
  never shows, is the size the pane had when it was added (its `width`
  then, or what its child asked for, raised to its `minsize` for good).
  Layout uses `width` when it is set and `paneWidth` otherwise, but the
  *requested* size is always `paneWidth`: `paneconfigure(a, width=6)` on a
  pane added at 19 leaves the window asking for 19.
- **`stretch` shares by size, not evenly**: each stretchable pane takes
  its size over the stretchable total of the spare room, truncated, and the
  last stretchable pane any remainder. With none stretchable, a shortfall
  comes out of the others from the first; a pane the edge cuts off is
  unmapped.
- **Moving a sash pins every pane**: `MoveSash` first sets each pane's
  `width` to its size on screen, then moves the room, taking it from the
  panes beyond in turn as each reaches its minsize. So after one
  `sash_place` every `panecget(..., "width")` has a number, a resize goes
  wholly to the last pane, and the window asks for what the panes add up
  to. **A sash placed where it already is pins nothing** - `MoveSash`
  returns at a distance of 0 first.
- **Before the window is mapped a sash place is unreliable in Tk**: the
  sash positions it measures from have not been worked out. Measured, a
  sash placed at 180 before the first update, or from `after_idle`, was at
  120 (both panes at their minsize), at 100 (no minsize, panes asking 50),
  or at 180 (a pane given `width=300`, which `panecget` then still
  reported). Not copied: here the panes' own sizes stand in until then. A
  program that wants a starting split gives a pane a `width`, as
  `examples/layout.py` does, and that works the same in both.

The themed `ttk.Panedwindow` keeps its own arithmetic, by `weight`
(`distribute`); a pane with a weight is not a classic pane.

Where cells cannot follow. A sash, and so a span, is never less than one
cell: Tk takes `sashwidth 0` and a negative `sashpad`, which would leave
nothing here to see or grab. `sashrelief` and `proxyrelief` show only
`sunken`, dim, as every one-cell part's relief does (`_part_relief`);
`proxyborderwidth` has no edge to draw in. `sashcursor` is kept and read back:
a terminal shows no pointer shape.

**`sash` and `proxy`, the commands** (`TkCurses-xy2`), follow
`PanedWindowSashCommand` and `PanedWindowProxyCommand` in tkPanedWindow.c,
and `tests/test_panedwindow_sash_proxy.py` holds them to real Tk in what
does not depend on the unit: every refusal, the marks, how far a drag moves
a sash. Measured on Tk 9.0.2: `sash dragto` moves the sash by the pointer's
distance from the mark *from where the sash is now* and never moves the
mark, so two drags to the same place move it twice (100, 110, 130 for
marks at 50 and drags to 60 then 70); `proxy place` keeps only the
coordinate along the panes, clamped between nought and the width less the
border and the sash, and puts the other at the border; `proxy forget` hides
it and `proxy coord` still answers where it was. Setting either answers
`()`, as tkinter's `_getints(...) or ()` makes of Tk's empty result, and
`identify` off a sash is Tk's `""`.

---

### Message Class

Multi-line text display.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Word-wrapped text |

---

## What an option value is

Tk checks an option's value against a *kind*, and every refusal is a
`TclError` with Tk's words - not the `ValueError` from an `int()` deep in a
widget's sizing that it used to be (`TkCurses-vgkb`). The kinds are
`_OPTION_VALUES` for options that mean the same in every widget, and each
class's `_value_checks` for those that do not, merged down the class's MRO.

**The same name is a different kind in different widgets**, and nothing in
the manuals says which; each row was measured through tkinter over Tk 9.0.2.

| Kind | Refusal | Where |
|------|---------|-------|
| integer | `expected integer but got "2.5"` | `width` of Button, Label, Checkbutton, Radiobutton, Menubutton, Entry, Spinbox, Listbox, Text, ttk Entry/Combobox/Spinbox; `height` of the classic labels, Listbox, ttk Panedwindow (and its `width`); Scale `digits` |
| screen distance | `expected screen distance but got "abc"` | `width` of Canvas, Frame, LabelFrame, Toplevel, Scale, Scrollbar, Message, ttk Frame/Labelframe/Notebook; Text `height`/`padx`/`pady`; ttk Treeview `height`; `length` of Scale, ttk Scale, ttk Progressbar |
| distance or `""` | `expected screen distance or "" but got "abc"` | Message `padx`/`pady`, ttk Label `wraplength`, Scrollbar `elementborderwidth`, `winfo_fpixels` |
| floating point | `expected floating-point number but got "abc"` | `from`/`to`/`resolution`/`tickinterval` of Scale, `from`/`to`/`increment` of Spinbox, their ttk forms |
| not checked | - | `width` of ttk Button, Checkbutton, Label, Menubutton, Radiobutton: `"abc"` is kept and read back, and the label is sized by its text |

So `Button(width=2.5)` is refused while `Frame(width=2.5)` is taken, and
`ttk.Label(width="abc")` is taken while `ttk.Entry(width="abc")` is not.

**A number is whatever Tcl 9 reads as one**, and Python's own parsers each
disagree with it somewhere, so `_tcl_number` reads it the way Tcl does.
Measured across all four kinds alike:

- `0x10`, `0o17`, `0b11` are 16, 15, 3, in any case (`0X10`); a width takes
  them.
- An underscore may stand **between** digits, any number of them: `1_0` and
  `1__0` are 10, `0x1_0` is 16; `_1` and `1_` are not numbers.
- Surrounding spaces are fine (`" 7 "`); only ASCII digits count, so the
  Arabic-Indic `١` is not one.
- `1e2`, `3.` and `.5` are doubles: a distance or a float takes them, an
  integer refuses them. `inf` and `Infinity` are doubles too; a distance reads
  one back as 0.
- `nan` is refused by each kind in its own words: a distance says `expected
  screen distance`, while a float and a boolean say `floating point value is
  Not a Number`.
- `True` reads back `1`, not `True`.

**A boolean option takes any number**, nonzero true: `undo=2.5`,
`undo=0x10`, `undo="1_0"` are all 1 and `undo="0.0"` is 0. tkinter's own
`getboolean()` refuses every one of those, so an option's check
(`_tcl_boolean`) is not `getboolean`, which stays as tkinter has it.

**`-tabs`** is refused in four sentences: a stop that is no distance is
`expected screen distance but got "abc"` - and so is an alignment word with no
stop before it, `left` alone - while after a stop a non-distance is `bad tab
alignment "bogus": must be left, right, center, or numeric`. Then `tab stop
"-3" is not at a positive distance` and `tabs must be monotonically
increasing, but "3" is smaller than or equal to the previous tab`.

**A variable option given a name** (`textvariable=5`) binds the widget to the
variable of that name, as Tk binds it to the Tcl global (`TkCurses-4v9f`).
What makes that work is where the traces live: by name, in
`Application.variable_traces` beside the values in `Application.variables`,
as Tcl keeps them - not on each `Variable` object, as they were. So
`setvar`, every `Variable` of that name, and every widget bound to it fire
and hear the same traces, and `getvar` fires the read traces. Measured on
Tk 9.0.2 through tkinter, and held by `tests/test_variable_names.py`:

- A name binds both ways: `setvar("g", "x")` reaches a Label bound to `g`,
  and so does `StringVar(name="g").set`.
- A **classic** widget bound to a variable that does not exist creates it
  from itself: a Label, Button, Menubutton or Message from its text, an
  Entry empty, a Spinbox at `from`, a Checkbutton at its offvalue (`0`), a
  Radiobutton empty, a Scale at its value. A **themed** widget does not:
  the name stays unset and reads as empty, which is why a `ttk.Checkbutton`
  without a variable starts `alternate`.
- A widget's own trace is not listed by `trace_info()`: Tk's are C-level,
  out of `trace info`'s sight.
- tkinter's `Variable.__del__` unsets the variable, and a widget bound to it
  puts it straight back; a Label keeps its variable after every `StringVar`
  of that name is collected. Here a collected `Variable` takes only the
  traces it added, and the value goes only when no trace is left on the
  name - the same result without the round trip.
- `getvar` of a name nothing set is `can't read "g": no such variable`.

The name given reads back from `cget` as an object equal to the name, as
tkinter's `parsedVarName` does; it never creates or unsets the variable.

Of the same sweep, 571 values Tk refuses were stored here (`TkCurses-m595`).
All are refused now, with Tk's message, but `Spinbox`'s `buttoncursor`,
which needs Tk's table of cursor names (`TkCurses-reba`). The rules were
measured, not read: a two-choice message is "a or b", without the comma; a
classic Scrollbar's `orient` takes `""` as horizontal and says
"orientation"; a Canvas's `state` takes `""` and says "bad state value";
`underline` does arithmetic (`3+1` is 4), keeps `end-1` as written and turns
a negative into `""`; a themed widget takes `""` for a relief, a border
width and a compound, keeps `state` unchecked, and checks `padding` - up to
four distances - only on Frame, Labelframe and Notebook, the label family's
taking anything. `tests/test_option_refusals.py` holds the edges, and
`tests/test_option_values_against_tk.py` now also asserts this direction
against real tkinter, where there is a display. The options Tk has that we
do not are `TkCurses-zkks`.

---

## Variable Classes

### Variable Base Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master, value, name)` | ✓ | Create variable |
| `get()` | ✓ | Get value |
| `set(value)` | ✓ | Set value |
| `initialize(value)` | ✓ | Initialize value |
| `trace_add(mode, callback)` | ✓ | Add trace |
| `trace_remove(mode, cbname)` | ✓ | Remove trace |
| `trace_info()` | ✓ | List traces |
| `trace_variable(mode, callback)` | ✓ | Legacy trace |
| `trace(mode, callback)` | ✓ | Alias of `trace_variable`, as in tkinter |
| `trace_vdelete(mode, cbname)` | ✓ | Legacy delete |
| `trace_vinfo()` | ✓ | Legacy info |
| `__eq__(other)` | ✓ | Compare variables |

### StringVar, IntVar, DoubleVar, BooleanVar

All inherit from Variable with type-specific `get()` methods.

---

## Image Classes

**An image is a plane of pixels, and it is the same pixel as everywhere else:
one cell wide, half a cell tall.** Colour arithmetic on those pixels happens
in linear light, and colour *matching* in DIN99d — see **Hex Color
Conversion**; neither is optional, and getting either wrong is visible.

See **The pixel** above. `width()` and
`height()` answer in pixels, as Tk's do, so an image 8 by 4 occupies 8 cells
across and 2 down. It is drawn by the same `compose()` that draws a canvas,
so `▀`, `▄` and `█` are what reaches the screen.

This is worth stating because the first attempt got it wrong. An image was
built as a grid of *characters*, one per cell — a second, incompatible
meaning of "pixel" in a library that already had one. It was internally
consistent and it was wrong: `get()` returned a glyph where Tk returns a
colour, an image could not be placed on a canvas without a conversion nobody
had specified, and `create_image` was therefore impossible by construction
rather than by choice. The two planes are one plane now.

What that buys, beyond tidiness: `put("red", to=...)` takes a colour as Tk's
does, `get(x, y)` answers with one, `zoom()` and `subsample()` are real pixel
operations, and an image can be handed to a canvas.

Three behaviours are reproduced rather than improved on, because tkinter code
is written around them. All three were measured on Tk 9.0.2:

- **An image is referred to by name.** `str(photo)` is `pyimage1`, and
  `cget("image")` gives that name back, not the object — so a widget holds a
  name and never owns its image.
- **An image nothing references is gone**, and a widget showing it keeps its
  size and draws nothing. Deleting an image under a live Label left the label
  at its old 22x12 with the dead name still in its option. This is the trap
  every tkinter tutorial warns about; the registry is weak so that it holds.
  Collection is silent, so a finalizer — not the change notification, which
  dies with the image — is what repaints the widget empty.
- **A widget follows its image.** Resizing an image from 4x2 to 20x10 moved a
  Label's request from 6x4 to 22x12 with nothing asked of the label, so an
  image tells its users when it changes.

### Image files

**tkinter 8.6 and later give PhotoImage PNG, GIF, PGM and PPM, and
BitmapImage XBM. All five are read, with nothing but the standard library.**
`dependencies = []` is a property of this library rather than an oversight:
PNG needs `zlib`, which is stdlib, and GIF's LZW and the netpbm headers are
short enough to write. Pillow appears only in the test extra, as an
independent decoder to check the answers against.

**The format is sniffed from the content, never from the name.** Measured on
Tk 9.0.2: opening a PNG while passing `format="gif"` still fails with
`couldn't recognize data in image file`, so Tk is plainly reading the bytes.

**An image loads at its native size.** An 800x600 PNG becomes an 800x600
pixel image — 800 cells across and 300 rows — most of it off the screen, and
that is correct. Fitting is the *caller's* job, through `subsample()`, as it
is in Tk. Auto-fitting inside PhotoImage would surprise anyone porting
tkinter code.

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| PNG | ○ | ○ | Read: 8-bit, interlaced or not: grey, RGB, palette, either with alpha. Written 8-bit RGB, RGBA when there is a hole |
| GIF | ○ | ○ | Read: 87a and 89a, first frame, interlacing undone. Written GIF89a, at most 255 colours |
| PGM / PPM | ○ | ○ | Read: P1-P6, any maxval, comments anywhere in the header. Written P6, holes black |
| XBM | ○ | | Via BitmapImage, as in tkinter |

**An image file is not trusted to say how big it is** (`TkCurses-tcbj`,
the security review of 2026-11-16). Before it, measured: a 66-byte
interlaced PNG declaring 16384x16384 made the decoder allocate 1 GB
before it found the data short; a 2 MB PNG declaring one pixel inflated
to 2 GB; a 50 KB GIF decoded for 38 s into 2 GB. Now `MAX_PIXELS` (4096 x
4096, far past anything a terminal shows) is checked from the header
before anything is allocated, PNG data is inflated with
`decompressobj().decompress(data, expected)` - no further than the header
declares, for interlaced images the sum of the seven passes - and the GIF
decoder stops at the declared size. Tk has no such limit; this is a
deliberate divergence, stated on `PhotoImage`. A file broken in a way no
check foresaw becomes `TclError` in `decode()`, because that is what a
program reading images catches. `tests/test_image_hostile.py` holds each
of these, every test checked to fail without its fix.

**Adam7 interlacing is read.** The image is stored as seven passes over a
lattice, and each pass is its own little image — its own width, its own
filter bytes, its own row above for the predictors — so the row filters are
undone per pass. Unfiltering the lot against the full width is the obvious
mistake and gives seven bands of noise. A pass can also be *empty* on an
image narrower or shorter than eight pixels, and a decoder that does not
skip those reads the next pass's bytes as this one's.

Still refused **by name**, not as "unrecognised data": PNG bit depths other
than 8, and frames after a GIF's first. Naming them matters because these
are this library's limits rather than the formats' — blaming the file would
send someone looking for a corrupt download.

Alpha becomes presence or absence, not a blend. A half-cell paints or it does
not, and by draw time the pixel has been folded into a glyph with a single
colour, so there is nothing left to blend with; below half alpha the pixel is
a hole. GIF's transparent index and PNG's `tRNS` are honoured the same way.

**Writing follows Tk 9.0.2, measured through tkinter** (`TkCurses-c5sj`;
`tests/test_photo_formats.py` holds each measurement, and checks against
the real toolkit, when there is a display, that Tk reads what is written
here and the other way round):

- `write(filename)` with no format writes a **PPM**, as Tk does; `data()`
  with none gives a tuple of rows, each a string of `#rrggbb`. A named
  colour is written as the colour it names (`red` is `#ff0000`), not as
  what the terminal shows for it, which is what `get` answers.
- A format's name is matched without case, and anything after it (`gif
  -index 1`) is the format's own options, ignored. `default` is Tk's list of
  rows: `data("default")` gives it as bytes, and it cannot be written to or
  read from a file. `svg` reads in Tk and does not write.
- **A GIF holds at most 255 colours**, and 256 are `too many colors`, with a
  hole in the picture or without: Tk keeps the last slot for transparency
  either way. Tk refuses rather than reducing the colours, so this does too.
- `-grayscale` is tkImgPhoto.c's `(11r + 16g + 5b + 16) >> 5`, and
  `-background` fills the holes before it. PPM has no holes: they are black.
- `read` is `copy_replace` from a file, sharing its code: the region
  `from_coords` goes to `to`, holes and all; an image with no size of its own
  grows to take it and with `shrink` fits it exactly, and one given a size
  keeps it and clips. Measured, not read: `photo(n)` says none of it.
- `put` and `data=` take Tk's rows - `"red"` is one pixel, `"red blue"` two
  rows of one, `"{red blue}"` one row of two - and image data as bytes or
  base64; rows of different lengths, and a colour Tk does not know, are
  refused in Tk's words. `put` grows an image with no size of its own to its
  far corner, as Tk's does.

**One difference stays.** Tk keeps a transparent pixel's colour - made
transparent with `transparency_set`, it still reports its red - where a
pixel here is a colour or a hole, so `data()` reports a hole as `#000000`,
which is what Tk reports for a pixel never painted.

Character art, which is this library's own, moved to a keyword-only
`palette=` on `data` and `write` when they became Tk's: positionally, the
second argument is Tk's `format`, and `write("x.png", "png")` had passed
`"png"` as the palette.

A file in none of these formats is read as **rows of characters** only when a
`palette` has been declared — that being how a caller says "this is character
art". Without one it is refused, as Tk refuses it. The rule keeps art
loadable without making every text file on the disk a valid image.

### PhotoImage Class

A plane of coloured pixels. A pixel holds a colour, or nothing at all —
transparency is a pixel that declines to paint, so what is behind it shows
through.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(name, cnf, master, **kw)` | ○ | PNG, GIF, PGM, PPM, or rows |
| `blank()` | ○ | Every pixel becomes transparent |
| `cget(option)` | ○ | Get option |
| `copy(...)` | ○ | Independent copy; `from_coords`, `zoom`, `subsample` |
| `copy_replace(sourceImage, ...)` | ○ | In place: `from_coords`, `to` (tiles), `shrink`, `zoom`, `subsample`, `compositingrule` |
| `zoom(...)` | ○ | Repeats each pixel |
| `subsample(...)` | ○ | Keeps every n-th pixel, as Tk does |
| `reduce(...)` | ○ | Averages each block; what fitting wants |
| `dither(...)` | ○ | Error diffusion. A tool, not a default — see below |
| `get(x, y)` | ○ | The pixel's colour |
| `put(data, to)` | ○ | A colour, Tk's rows of them, or image data; `to` places or tiles |
| `data(format, ...)` | ○ | Tk's rows, or PNG, GIF or PPM bytes; `from_coords`, `background`, `grayscale` |
| `read(filename, format, ...)` | ○ | `from_coords`, `to`, `shrink`, as Tk's |
| `write(filename, format, from_coords, ...)` | ○ | PPM unless told; PNG, GIF; `background`, `grayscale` |
| `transparency_get(x, y)` | ○ | Whether the pixel paints |
| `transparency_set(x, y, bool)` | ○ | Make it transparent, or opaque |

`zoom` and `subsample` were once marked N/A here. They are the two operations
that survive the move most cleanly: repeating a pixel is exactly what
enlarging means when the plane is this coarse.

`reduce` is an addition rather than one of Tk's. Both it and `subsample`
are wanted and they answer different questions. `subsample` keeps every
n-th pixel — exact, Tk's, and what a caller porting tkinter code reaches
for. `reduce` averages the block it covers, which is what *fitting a
photograph to a window* means. Measured on the perl-Tk demo images at 320x200
reduced by six, scored against a Lanczos reference after quantising to the
terminal palette:

| | 8 colours | 256 | truecolor |
|---|---|---|---|
| earth.gif, subsample → reduce | 25085 → 25363 | 2293 → **494** | 2106 → **260** |
| mickey.gif, subsample → reduce | 10969 → **9569** | 7405 → **1299** | 7073 → **680** |

**`resize(width, height)` is what a caller fitting a picture to a space
should use, not `reduce`.** A whole-number factor lands the picture on
whatever size that factor happens to give: mickey.gif at 320 wide, offered a
100-cell panel, comes out 80 cells — a fifth of the width discarded. It also
drifts, because an integer factor covers exactly 3 input pixels where the
true ratio may be 3.019, dropping the remainder. Measured against a correct
box filter at 106x66, `reduce` differed by 16.16 and `resize` by 5.12; against
Lanczos, 17.23 and **6.88**.

Averaging wins decisively from 256 colours up — including the flat cartoon,
which is the case where dropping pixels should have preserved the palette
and won, and still loses by 90%.

**At eight colours it is a wash**, and on earth.gif fractionally worse. With
only eight colours to land on, a careful average and a dropped pixel usually
quantise to the same entry, and where they differ it is a coin toss.

These numbers replace an earlier set that claimed a win at every depth by 38%
to 93%. That set was measured before `_average` worked in linear light, and
against a reference built the same way it was — so it was partly scoring the
method against itself. The reference here is Lanczos computed in linear
light, which shares no arithmetic with `reduce`.

`dither()` is a different matter, and the honest answer is narrower than it
first looked. Error diffusion trades colour accuracy for spatial noise, and
that pays **only when the eye merges neighbouring pixels back together**. It
does on a monitor, where a pixel is a quarter of a millimetre. It does not
here: a pixel is half a character cell, so the dither pattern is seen as
itself. Measured on mickey.gif at 256 colours against an ideal reduction:

| picture | depth | flat | dithered |
|---|---|---|---|
| mickey.gif | 8 | **71.58** | 90.87 |
| mickey.gif | 256 | **29.15** | 30.05 |
| earth.gif | 8 | 126.70 | **120.65** |
| earth.gif | 256 | **18.95** | 24.67 |
| gradient.png | 8 | **149.57** | 151.47 |
| gradient.png | 256 | **29.29** | 34.60 |

Flat wins five of six per-pixel and every time at 256 colours. After a 3x3
blur the order reverses everywhere and by a wide margin — 26.71 dithered
against 140.29 flat, on the gradient at 8 colours. So `dither()` is
available for the case where the cells really are small — a large image at a
small font — and is not what a widget or a viewer should do by default.

The blurred figure was the only one taken when it was written, and it
assumed a viewer nobody had checked for. A person comparing the four side by
side picked averaged-and-flat, which is what prompted the second
measurement.

### Image colour and the pair ceiling

**An image is the only thing in this library that can exhaust the terminal's
supply of colour pairs, and it is the reason a richer terminal currently
produces a worse picture.** The mechanism is under **Why more colour can mean
a worse picture**; this is what follows from it for images.

A widget uses a handful of colours. A photograph reduced to fit a panel uses
hundreds, and what it costs is counted in *pairs* — `(foreground,
background)` combinations — of which there are at most 255 on any screen.
Quantising every pixel to the 256-colour cube is what keeps a picture under
that ceiling today, and it does so by accident rather than by design: nobody
chose the cube for this image, it just happens to collapse things.

The decision, taken 2026-09-21, is to keep a collapse step and make it a
chosen one. **An image brings its own palette, sized to fit a pair budget,
and the entries of that palette are reproduced exactly.** Measured on both
demo images reduced to 53x33 — mean per-pixel error against the unquantised
fitted image, and the distinct pairs `compose()` asks for:

| How the colours are chosen | mickey | earth |
|---|---|---|
| 256-cube, shared — today | 231 pairs, 18.35 | 230 pairs, 14.34 |
| 16-entry image palette, entries snapped to the cube | 97 pairs, 23.89 | 102 pairs, 16.32 |
| 16-entry image palette, entries exact | **149 pairs, 14.45** | **143 pairs, 7.50** |
| 32-entry image palette, entries exact | 275 pairs, 8.98 | 304 pairs, 5.23 |

Three things follow, and the middle one is the one that is easy to get wrong.

**A small exact palette beats a large shared one.** Sixteen entries chosen
from the picture and reproduced exactly are better than 256 the picture did
not choose — on accuracy *and* on pairs, on both images. `earth` halves its
error while using 87 fewer pairs.

**The palette and the exact reproduction cannot ship separately.** A
per-image palette whose entries are then snapped to the cube is *worse than
no palette at all* — 23.89 against 18.35, 16.32 against 14.34 — because the
quantisation error and the cube error stack. This was very nearly sequenced
as two cycles, palette first; that would have shipped a regression and then
undone it. The palette is only worth having if its entries land exactly.

**The palette size is not a constant.** Thirty-two entries goes over the
ceiling on both images (275, 304) where sixteen sits comfortably under (149,
143), but which size fits depends on the picture, on how large it is drawn,
and on what else is on screen. It has to be chosen by quantising, counting
the pairs, and backing off — never assumed, because pairs do not scale with
colours: `earth.gif` at full size is 253 colours and 8583 pairs.

`TkCurses-bvu` is the work. Median cut produced the numbers above and is a
floor to beat rather than a design. Note also that the palette pass belongs
*after* the fit, not before: `reduce()` averages, and averaging creates
colours — mickey goes from 15 to 616 on the way down to 53x33.

### BitmapImage Class

XBM is the one image format that survives intact: one bit per pixel is
exactly what this plane holds. Set bits are drawn in `foreground`, clear bits
are transparent.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(name, cnf, master, **kw)` | ○ | XBM, or rows of text |
| `file=` | ○ | Real `.xbm` files, sniffed by content |
| `configure(**kw)` | ○ | `foreground`, `background` |
| `image["option"]` | ○ | BitmapImage has no `cget`, as in tkinter |

XBM packs each row into whole bytes, least significant bit leftmost, so a
12-wide bitmap spends two bytes a row and four bits of every second byte are
padding. Dropping them is not optional: keep them and every row after the
first is shifted.

### compound

`compound` says how an image and a text share a widget. The default is the
part that surprises people — measured with `text='hello'` and an 8x4 image:

| compound | Tk requests | Arrangement |
|----------|-------------|-------------|
| `none` (default) | 10x6 | **The image only. The text is not drawn.** |
| `left` / `right` | 45x23 | Side by side |
| `top` / `bottom` | 36x28 | Stacked |
| `center` | 36x23 | Text over the image |

Setting an image on a labelled widget therefore hides its text unless
`compound` says otherwise. Tk leaves one pixel between the two, which is a
fraction of a cell; here a whole cell is left horizontally, because art and
the first letter otherwise run together, and none vertically, because rows
are already distinct.

Text and pixels meeting in one widget has the same consequence it has on a
canvas: a glyph occupies a whole cell, so the text half of a compound layout
is placed on cell boundaries while the image half is placed on pixel ones.

---

## TTK Widget Classes

### ttk.Widget Base

All TTK widgets inherit from this base with additional styling.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `identify(x, y)` | ○ | The style element at a cell, as drawn |

**`identify(x, y)` answers a style ELEMENT name** (`TkCurses-d5u`). This is
not the domain answer the classic Scale, Scrollbar, Spinbox and PanedWindow
give. The manual says only "returns the name of the element at position x, y";
everything below was measured on Tk 9.0.2 by scanning every widget, and read
against its default-theme `style.layout()`:

- **Elements are nested rectangles.** Button is border ⊃ focus ⊃ padding ⊃
  label. Entry is field ⊃ padding ⊃ textarea. Checkbutton is padding ⊃ an
  indicator on the left and the label. Combobox's field holds a downarrow on
  the right. A Frame is one `border`, Separator one `separator`, Sizegrip one
  `sizegrip`. A Labelframe answers `border`, except `""` over its caption.
- **What comes back is the registered element, not the layout path.** So it is
  `label` for `Button.label`, but `Checkbutton.indicator`,
  `Combobox.downarrow` and `Spinbox.uparrow` keep their prefixes. That is
  also where the built-in themes disagree: `default` and `alt` give
  identical sets, and `clam` answers `Combobox.field` and a bare
  `downarrow`. The names here are the **default** theme's, transcribed rather
  than derived.
- **The themed Scale, Scrollbar, Spinbox and Panedwindow answer differently
  from the classic ones.** ttk.Scale gives `slider` and `trough` (classic
  `trough1`/`trough2`). ttk.Scrollbar gives `leftarrow`/`rightarrow` or
  `uparrow`/`downarrow`, `thumb` and `trough` (classic `arrow1`,
  `slider`). ttk.Spinbox gives `Spinbox.uparrow` and `Spinbox.downarrow`
  (classic `buttonup`). ttk.Panedwindow gives the sash's **index**, `0`
  (classic `(0, "sash")`). Ours answered the classic forms until this, and
  the method-surface check could not see it, because a method that exists
  passes it.
- **A pane added twice: the classic widget updates it, ttk refuses it.**
  Measured on Tk 9.0.2, a second classic `add` is a `paneconfigure`: it changes
  the options given and keeps the rest, as `paneconfigure` itself does (ours
  reset every option left out until `TkCurses-z6pp`). ttk's `add` raises
  `<path> already added`, while its `insert` of a pane already there moves it
  and keeps its weight unless one is given.
- **Notebook answers element names too, not a tab index:** `tab`, `padding`
  or `label` over a tab, and `""` past the tabs and over the page. The tab
  index is `index("@x,y")`.

**Answered from the geometry as drawn**, so a part drawn no cells wide is never
answered. There is no separate focus ring here, so `focus` never comes back.
A flat border takes no cells, so a flat widget's edge is `padding` or its
content. Every answer is one Tk gives for that widget, never one it does not.
`tests/test_ttk_widgets.py` carries Tk's measured set for each.

The bindings that hit-test (spinbox arrows, scrollbar clicks, sash drags) call
the **classic** method by name, because they act on the domain answer.

`ttk.Treeview` keeps its own `identify(component, x, y)`, as tkinter's does.
Its `identify_element` names an item's elements, below.

### ttk.Style Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `configure(style, query_opt, **kw)` | ○ | Configure theme |
| `map(style, query_opt, **kw)` | ○ | State mapping |
| `lookup(style, option, state, default)` | ○ | Lookup value |
| `layout(style, layoutspec)` | ✗ | N/A |
| `element_create(name, type, *args)` | ✗ | N/A |
| `element_names()` | ◐ | List elements |
| `element_options(elementname)` | ◐ | Element options |
| `theme_create(name, parent, settings)` | ○ | Create theme |
| `theme_settings(name, settings)` | ○ | Theme settings |
| `theme_names()` | ○ | List themes |
| `theme_use(name)` | ○ | Use theme |

**Built-in Text Themes:**

| Theme | Description |
|-------|-------------|
| `default` | Standard Unicode box drawing |
| `ascii` | Pure ASCII (`+`, `-`, `\|`) |
| `dos` | DOS/CP437 mixed boxes: double across, single down (`╒═╕`) |
| `rounded` | Rounded corners (`╭╮╰╯`) |
| `double` | Double-line boxes (`╔═╗`) |
| `minimal` | No borders, spaces only |

### ttk.Entry

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `validate()` | ✓ | Revalidate now, under every mode; sets or clears `invalid` |
| `bbox(index)` | ✓ | The cell box of one character |

Inherits from Entry; `ttk.Combobox` and `ttk.Spinbox` inherit both methods, as
in tkinter. **`validate()` follows ttk, which is not the classic Entry**
(`TkCurses-52q`). The manual gives it one sentence; this is what it does,
measured on Tk 9.0.2:

- **It runs under every mode, `none` included,** once, with the current text,
  and returns the verdict. Without a `validatecommand` it is True.
- **`invalid` follows the answer:** set on a refusal, cleared on an approval,
  even when it was set by hand. Ordinary key validation never touches it.
- **A refusal runs the `invalidcommand`.** A refused `textvariable` write does
  not.
- **A validator that raises** makes `validate()` raise `TclError` and turns
  validation off. **One that edits the entry** keeps its edit, and
  `validate()` answers False with no `invalidcommand` and sets `invalid`.
  Validation **stays on**, where the classic Entry would turn it off.

**The ttk entries validate by ttk's rules**, as of `TkCurses-4ag`; they had
inherited the classic Entry's. Every condition was measured against a validator
that approves, refuses, raises and edits the entry, on `tk.Entry` and
`ttk.Entry` side by side. `tests/test_validation_matrix.py` carries the whole
table for both. Where ttk differs:

| | classic `tk.Entry` | ttk entries |
|---|---|---|
| a `textvariable` write | validated, condition `forced` | **not validated at all** |
| a key edit's validator raises | refused, validation off | **`TclError` from `insert`/`delete`**, validation off |
| a validator edits the entry | validation off (key modes) | **validation stays on** |
| a focus check approves | — | **clears `invalid`**, even set by hand |
| a focus check refuses, or its validator edits | — | **sets `invalid`** |

Key validation never touches `invalid`, on either. A focus check whose validator
raises stays silent on both, with validation turned off. An edit made inside any
validator, under any mode, makes that validation fail. That is why a focus
validator that edits sets `invalid`, though no key validation ran.

`bbox(index)` answers `(x, y, 1, 1)` for the character at `index`, relative to
the widget and to the **view**: a character scrolled off to the left has a
negative x. An index past the last character answers the last character's box
(`end`, `len` and `99` all match `len − 1`), and an empty entry answers width 0.
The classic `tk.Spinbox` has the same method. The classic `tk.Entry` does not:
in tkinter its `bbox` is `Misc.bbox`, the **grid** alias (`TkCurses-zmf`).

### ttk.Combobox

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Dropdown entry |
| `current(newindex=None)` | ✓ | Get/set index |
| `set(value)` | ✓ | Set value, unvalidated and regardless of state — see ttk.Spinbox |

Inherits from Entry.

**Rendering:**
```
Closed: [Option 1       ▼]
Open:   [Option 1       ▼]
        ├─────────────────┤
        │ Option 1        │
        │ Option 2        │
        │ Option 3        │
        └─────────────────┘
```

### ttk.Spinbox

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Entry with step arrows |
| `set(value)` | ✓ | Set value, unvalidated and regardless of state |

Inherits from Entry.

**It starts empty and keeps its text when `-values`, `-from` or `-to`
change**, unlike the classic Spinbox above. Measured on Tk 9.0.2:
`ttk.Spinbox(values=("a", "b"))` reads `""`, and so does
`ttk.Spinbox(from_=3, to=10)`. The first step from empty goes to `-from` or
the first value (`TkCurses-fdl9`).

**`set` is not `delete` then `insert`, and the difference is all of it.**
`ttk::spinbox set` and `ttk::combobox set` are one routine in Tk,
`EntrySetValue`, and measured against Tk 9.0.2 it:

- **validates nothing.** A validatecommand that refuses everything is not
  called, under `validate="all"` or `"key"`, and the value lands anyway.
- **ignores `state`.** `readonly` and `disabled` both take the value.
- **ignores the range.** `set(99)` on a `from_=0, to=10` spinbox reads `"99"`.
- **keeps the cursor and selection**, clamped to the new text: a selection of
  1–4 over `"hello"` reads 1–2 after `set("ab")`, and one starting at or past
  the new end is dropped. A textvariable write does the same, on `tk.Entry`
  and `ttk.Entry` alike.

`Combobox.set` was `delete` then `insert` until `TkCurses-elb`, so it validated
twice, kept the old text when refused, and dropped the selection. The
dropdown's pick now does what Tk's `ttk::combobox::SelectEntry` does — `current`,
select all, cursor to the end — explicitly rather than as a side effect.

### ttk.Notebook

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Tabbed container |
| `add(child, **kw)` | ✓ | Add tab |
| `forget(tab_id)` | ✓ | Remove tab |
| `hide(tab_id)` | ✓ | Hide tab |
| `identify(x, y)` | ○ | Element at a cell: `tab`, `padding`, `label` or `""` — see ttk.Widget |
| `index(tab_id)` | ✓ | Tab index |
| `insert(pos, child, **kw)` | ✓ | Insert tab |
| `select(tab_id=None)` | ✓ | Select/get tab |
| `tab(tab_id, option, **kw)` | ✓ | Tab options |
| `tabs()` | ✓ | List tabs |
| `enable_traversal()` | ✓ | Keyboard nav |

**Rendering:**
```
┌─────┬─────┬─────┐
│ Tab1│▶Tab2│ Tab3│
├─────┴─────┴─────┤
│                 │
│   Tab Content   │
│                 │
└─────────────────┘
```

### ttk.Progressbar

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Progress display |
| `start(interval=None)` | ✓ | Auto-increment |
| `step(amount=None)` | ✓ | Step value |
| `stop()` | ✓ | Stop auto-increment |

**Rendering:**
```
Determinate:    [████████████░░░░░░░░] 60%
Indeterminate:  [░░░░███░░░░░░░░░░░░░] (animated)
```

**`phase` counts only where a style asks it to** (`TkCurses-xe9.2`). It
follows `AnimationEnabled`, `AnimateProgressProc` and `CheckAnimation` in Tk
9.0.2's ttkProgress.c, and the manual says only that it is "read-only" for
a theme's use, which it is not: a program may set it. Measured through
tkinter, where the manual is silent:

| What | Tk 9.0.2 | Here |
|------|----------|------|
| when it counts | while the bar is indeterminate and its style's `-period` is above 0, `start()` or not. No X11 theme sets `-period` (only aqua's does), so a plain bar's phase stays 0 | the same |
| how | +1 every `-period` ms; past the style's `-maxphase` (0 when unset) it goes to 0. `phase=99` under `maxphase` 3 goes 99, 0, 1, 2 | the same |
| which style | the oriented one, `Horizontal.TProgressbar` or `Vertical.TProgressbar`, inheriting `TProgressbar` | the same, for these two options |
| a style changed under a showing bar | nothing until the bar is configured or stepped; a period of 0 stops it at the next tick | the same |
| values | Tcl integers, -2³¹ to 2³² - 1, read back as written; `1.5` is `expected integer but got "1.5"`, 2³² is `integer value too large to represent` | the same |

### ttk.Treeview

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Tree/table view |
| `bbox(item, column)` | ○ | Cell bounding box, in cells. **Not** `Misc.bbox`, which is `grid_bbox` |
| `get_children(item=None)` | ✓ | Get children |
| `set_children(item, *children)` | ✓ | Replace children, in order; what it omits is **detached**, not deleted |
| `column(column, option, **kw)` | ○ | Column config |
| `delete(*items)` | ✓ | Delete items |
| `detach(*items)` | ✓ | Detach items |
| `exists(item)` | ✓ | Item exists |
| `focus(item=None)` | ✓ | Focus item |
| `heading(column, option, **kw)` | ○ | Heading config |
| `identify(component, x, y)` | ○ | Dispatcher; also takes `cell`, which tkinter lacks |
| `identify_row(y)` | ○ | Item at a row; `""` over the heading |
| `identify_column(x)` | ○ | `#0`, `#1`… at a column |
| `identify_region(x, y)` | ◐ | `heading`/`tree`/`cell`/`nothing`; never `separator` |
| `identify_element(x, y)` | ○ | Tk's item elements in Tk's order; never `image`, which is not drawn |
| `index(item)` | ✓ | Item index |
| `insert(parent, index, iid, **kw)` | ✓ | Insert item |
| `item(item, option, **kw)` | ✓ | Item options |
| `move(item, parent, index)` | ✓ | Move item |
| `next(item)` | ✓ | Next sibling |
| `prev(item)` | ✓ | Previous sibling |
| `parent(item)` | ✓ | Parent item |
| `see(item)` | ○ | Scroll to item |
| `selection()` | ✓ | Get selection |
| `selection_set(*items)` | ✓ | Set selection |
| `selection_add(*items)` | ✓ | Add to selection |
| `selection_remove(*items)` | ✓ | Remove from sel |
| `selection_toggle(*items)` | ✓ | Toggle selection |
| `set(item, column, value)` | ✓ | Set cell value |
| `tag_bind(tagname, sequence, callback)` | ✓ | Bind an event for tagged rows; returns None in all three forms |
| `tag_configure(tagname, option, **kw)` | ◐ | All seven tag options are stored; `background`, `foreground` and `stripedbackground` are drawn |
| `tag_has(tagname, item)` | ✓ | The rows carrying a tag, or a bool for one row |

**Four of the seven tag options are stored and never drawn.** `tag_configure`
answers for `background`, `foreground`, `font`, `image`, `imageanchor`,
`padding` and `stripedbackground` — seven, measured against Tcl/Tk 9.0.2,
where `tag_configure('x')` with no option lists them all. Three of those mean
something on a character grid and four describe pixels; all seven are accepted
and read back, so a program that sets `font` keeps working and simply looks the
same. One cell is one cell.

`stripedbackground` is the one that matters, and it is where this and
`-striped` (`TkCurses-xe9.4`) turn out to be one feature. The manual calls it
*"the cell or item background color for alternate lines, if `-striped` is
true"* — so **striping is a tag option in Tk, not a widget colour**. `-striped`
was built first, before any tag machinery existed, and could only read
`style.lookup("Treeview", "stripedbackground")`. A striped row now takes the
winning tag's `stripedbackground`, then the style's, then falls back to `A_DIM`
(see `_stripe_attribute` for why dim rather than a colour).

**Tk 9.0 has `tag delete` and tkinter does not wrap it**, which is why no row
above mentions it: `hasattr(tkinter.ttk.Treeview, "tag_delete")` is False, so
it is outside the method-surface comparison and nothing here is missing. Tk's
own command removes a tag from every item and cell and drops its bindings. A
program that wants the effect here can `item(iid, tags=...)` the tag off each
row.

**Hit-testing rests on one column model.** `_column_spans()` answers where every column sits, in cells, and
both the row painter and the heading painter compose from it — they each
recomputed the same arithmetic before, so a click and a repaint could disagree
about where a column was. `identify_column`, `identify_region` and `bbox` all
read it, which is why they followed with no change of their own when
`-stretch` was honoured (`TkCurses-a01`).

**Columns stretch to fill the tree**, as of `TkCurses-a01`. `-stretch` was
stored and never read before, so the space past the last column was blank. The
manual says only that `-stretch` "specifies whether the column's width should
be adjusted when the widget is resized". These measurements, on Tk 9.0.2, are
what it does:

- A column's `-width` is a **starting** size. The space left over is shared
  **evenly** among the shown columns whose `-stretch` is true, not in
  proportion to their widths. 80/60/60 in 598 pixels draws 213/193/192, and
  100/50/50 gets the same +133/+133/+132. The odd units go to the leftmost.
- A `stretch=0` column keeps its width and the others split its share. With
  none stretchable, nothing grows. A hidden `#0` (`show="headings"`) takes no
  share.
- `column(c, "width")` answers the **drawn** width: the 80-wide column reads
  back 213.
- Setting a width makes every column's drawn width its new starting size
  first, since that is what Tk's `-width` already is. From 213/193/192, setting
  the middle column to 60 reads 257/104/237: the other two start from where
  they were drawn, and the 133 freed is shared by all three.

**Where this differs from Tk.** Tk keeps a running slack total between layouts,
and here a resize keeps none:

- **A tree narrower than its columns:** a column here never draws narrower than
  its `-width`, and what does not fit is clipped. Tk does the same for a tree
  *created* too narrow (400/300/300 at 600 pixels stays 400/300/300, and only
  grows past 1002). But a tree that has been wider shrinks below its widths in
  Tk, down to `-minwidth`, and here it does not.
- **History:** after shrinking to `-minwidth`, Tk does not return to the same
  widths. 213/193/192, then 50/50/50 at 150 pixels, comes back as
  199/199/200. Here every layout is a function of the widths and the size.
- **Odd units:** they always go to the leftmost columns here. In Tk, which
  column gets them depends on the path its slack took. Once it was the last:
  257/104/237, where this gives 258/104/236.

A grow-and-shrink-back that stays at or above the configured total comes out
identical: 600 → 900 → 600 → 300 → 600 pixels, every step.

The spans carry no scroll offset: they are positions along the whole row of
columns. **The tree scrolls sideways as of `TkCurses-xe9.6`**, and every
painter and every identify answer reads the spans through the view —
`_in_view` for what is drawn, `_content_x` for a click, `_view_x` for `bbox` —
so they cannot disagree about the offset any more than about the spans. Until
then a tree never scrolled sideways, and columns wider than it were clipped
where nothing could reach them.

Measured on Tk 9.0.2, in pixels, and kept here in cells:

- One unit moves one; one page moves the width the scrolling columns are seen
  through; a bare `xview(50)` puts offset 50 at the left edge. `moveto`
  rounds, halves up, as `yview` does.
- The fractions are of the **scrolling** columns only, so frozen columns
  change them (see `-titlecolumns` below).
- A tree that has never been laid out answers `(0.0, 1.0)` and ignores
  `moveto` and `scroll`.
- `bbox` of a column scrolled off the left is answered unclipped: Tk gave
  `-101` for one scrolled a column's width past the edge.

The open/closed marker is in the tree column and scrolls with it. A click where
it would be with the view at the left opens nothing once it has scrolled away.

There is no sideways scrolling by keyboard: Tk binds none either, and Left and
Right open and close branches. Tk scrolls sideways on `<Shift-MouseWheel>`;
this tree takes no wheel at all yet, either way — `TkCurses-94fn`.

**`-titleitems` freezes the first rows** (`TkCurses-xe9.6`). Tk 9.0 added it
and `ttk_treeview(n)` gives it one sentence; measured on Tk 9.0.2:

- It counts **displayed** rows in display order, not top-level items: two
  frozen under an open first branch are the branch and its first child; with
  the branch closed, the branch and the next top-level row.
- The default is 0. A negative count is refused as `"-1" is out of range`
  and a non-integer as `expected integer but got "x"`, at construction and at
  `configure` alike. A count past the end is kept as given and freezes every
  row.
- `yview` reports fractions of the rows that **scroll**: twenty rows, three
  frozen and five more in view, is `(0.0, 5/17)`. A page is the rows under the
  titles.
- `see` of a title row moves nothing. `bbox` of a row scrolled up under the
  titles answers `""`, since it is not drawn.

Titles that do not all fit take the whole tree and nothing scrolls; the ones
past the bottom are not drawn. Tk then reports a negative end for `yview` —
`(0.0, -0.4)` with ten titles in six rows — which is not copied: this answers
one row's worth, as it does for any tree with no room. `identify_row` keeps
counting below the bottom of the tree, as Tk's does (`i18` at y=400 in a
150-pixel tree), and so it names title rows that are not drawn. Whether Tk
draws anything between the titles and the rest, a rule or a shade, could not
be read through the API and is for UAT 47 to look at.

**`-titlecolumns` freezes the first columns**, built on the sideways
scrolling above. Measured on Tk 9.0.2:

- The count includes `#0` **even when the tree column is hidden**: with
  `show="headings"`, 1 freezes nothing and 2 freezes the first data column.
- They are the first columns in display order: `displaycolumns=("c", "a",
  "b")` with 2 frozen freezes `#0` and `c`.
- Columns that scroll pass **under** the frozen ones: Tk's `bbox` put a
  scrolled column at x=51, inside a frozen one 100 wide, and `identify_column`
  there answers the frozen column.
- `xview` reports fractions of the scrolling columns only, and a page is the
  width beside the frozen ones. A count past the last column freezes them all;
  `xview` is then `(0.0, 1.0)` and nothing moves.
- A negative count is refused as `"#-1" is out of range` (a column name, where
  `-titleitems` says `"-1"`) and a non-integer as `expected integer but got
  "x"`. A large count is kept as given.

The cell joining the last frozen column to the next is frozen with it, as it
belongs to that column for a click.

**`-displaycolumns` chooses which data columns are drawn, and in what
order** (`TkCurses-aq04`; it was stored and ignored before). The manual says
only that it is a list of column identifiers or `#all`. Measured on Tk 9.0.2
with `columns=("a", "b", "c")`:

- An entry is a column's name or its **index in `-columns`**: `(2, 0)` draws
  c then a. A string is split as a list, `"b a"`. `"01"` is index 1.
- **The same column may be listed twice, and is drawn twice.** `()` draws no
  data columns.
- `#n` counts **displayed** columns everywhere it is accepted — `column`,
  `heading`, `set`, `bbox`, `identify_column` — so under `("c", "a")` `#1` is
  c. Past the end is `Column #3 out of range`; `set(item, "#0")` is `Display
  column #0 cannot be set`.
- A hidden column keeps its value (`set(item)` answers every data column) and
  has no `bbox`.
- Refused: `Invalid column index "zz"` for a name that is not a column and
  for `#0`, `#1`, `1.0`, and `#all` other than alone; `Column index "5" out of
  bounds` for an index past the columns or below zero.
- Changing `-columns` keeps the list. **Dropping a displayed column from
  `-columns` is refused** with `Invalid column index "c"` — but Tk applies
  half of it first: `cget("columns")` still answers the old three while
  `set(item)` already answers only the new two. Here the refusal changes
  nothing. Changing both options in one call is accepted.

Not reproduced: Tk answered `bbox(item, "a")` under `("a", "a")` with a width
covering both copies (200 for two 100-wide columns). Here it is the first
copy's rectangle.

**The mouse wheel scrolls it** (`TkCurses-94fn`). Tk 9.0.2's Treeview class
binds `<MouseWheel>`, `<Alt-MouseWheel>`, `<Shift-MouseWheel>` and
`<Shift-Alt-MouseWheel>` to `tk::MouseWheel` with factors -40 and -12.
Measured with `event_generate("<MouseWheel>", delta=-120)`, one notch: 3 rows
down, 10 with Alt; with Shift, 3 and 10 units sideways. Tk's sideways unit is
a pixel and ours is a cell, so the same notch moves much further here — the
same trade as `xview scroll` itself. Here they are bindings on buttons 4 and 5
with each modifier, since curses reports the wheel as buttons. Whether
Shift-wheel arrives at all is up to the terminal: many keep it for their own
scrollback.

The issue asked whether a frozen column can be dragged to resize. There is no
drag to resize any column here, frozen or not (`identify_region` never says
`separator`), so the question does not arise yet.

Three answers differ from Tk deliberately:

- **`identify_region` never returns `separator`.** Tk's separator is the
  draggable gap between column headings; this widget draws none and offers no
  such drag, so returning it would name something that is not there.
- **`identify_element` names an item's elements as Tk 9.0.2 does**
  (`TkCurses-at9`), measured by scanning the default theme's tree pixel by
  pixel. Over an item: `""` across its indent, `Treeitem.indicator` over the
  open/closed marker - every row has one, leaves included - then `text` over
  the text itself and `padding` over the rest of the column, Tk naming the
  indicator in full and the other two bare. A data cell is `""` for its first
  few pixels, then `text` and `padding`; here that gap is the one cell
  joining it to the column before. A heading answers `""` throughout, as does
  the space below the items. `tests/test_treeview_elements.py` compares the
  run of names across each row with Tk's for both `show` modes and an
  `anchor="e"` column. Tk's `image` element has no counterpart: an item's
  image is not drawn here, and an empty value, which Tk gives a sliver of
  `text`, is all `padding`.
- **`identify("cell", x, y)` is offered although tkinter has no wrapper for
  it.** Tk documents it and it answers the `(item, column)` pair that cell work
  wants; a tkinter program has to compose `identify_row` with
  `identify_column` by hand. A compatibility layer may as well spare its
  callers that.

The single cell that joins one column to the next belongs to the column on its
left. Tk's columns abut and have no such cell; the gap is an artefact of
drawing on a character grid, and leaving it unassigned would make one cell in
every gap unclickable.

**Rendering:**
```
┌──────────────────────────────────────┐
│ Name           │ Size   │ Modified   │
├──────────────────────────────────────┤
│▼ Documents     │        │            │
│  ├─ report.pdf │ 1.2 MB │ 2024-01-15 │
│  └─ notes.txt  │ 4 KB   │ 2024-01-14 │
│▶ Images        │        │            │
│  Music         │        │            │
└──────────────────────────────────────┘
```

#### Where a cell's text sits: `-anchor`

The manual says a column's `-anchor` places "the text and/or image" in each
cell, and a heading's the heading's. It does not say what the tree column
does with its indent, nor what happens to text too wide for its cell. Seen
on Tk 9.0.2 in a screenshot of a real tree (the measurement needed eyes:
`bbox` answers the cell, not where its text lands):

- The indent and the disclosure marker stay at the left of `#0`; the text is
  placed in what is left. Under `anchor e` a parent and its child therefore
  end at the same edge, whatever their depth.
- Text wider than its cell starts at the left and is cut at the right,
  whatever the anchor - a long value under `e` shows its beginning, and so
  does a long heading.
- Only the horizontal part of an anchor counts in a one-line cell: `ne` and
  `se` are `e`.

Before this, both anchors were stored and ignored, so every heading sat at
the left where Tk centres it. TkCurses-m3ii.

#### The arrows on rows, and opening and closing

`ttk_treeview(n)` documents no bindings at all. What a program sees, measured
on Tk 9.0.2 and read against `Keynav`, `OpenItem`, `CloseItem` and `Press` in
treeview.tcl:

| Gesture | Tk 9.0.2 |
|---------|----------|
| Right | Opens the focus row and selects it, **whatever the row is**: a leaf is marked `-open true` and a branch already open is opened again, and both send `<<TreeviewOpen>>` |
| Left on an open branch | Closes it and selects it |
| Left anywhere else | Goes to the parent and selects it; at the top level nothing happens, the focus staying put. An open leaf counts as "anywhere else" - Keynav closes only a row that is open *and* has children |
| Any arrow with no focus row | Nothing |
| `selectmode none` | The arrows open, close and move, and select nothing |
| `<<TreeviewOpen>>` | Sent **before** the row is opened: a handler reads `-open` false |
| `<<TreeviewClose>>` | Sent after the row is closed |
| A click on a branch's marker | Selects the branch, then opens or closes it |

One difference: Down or Up with no focus row selects the first row here,
where Tk does nothing. A terminal reaches a tree by Tab more often than by a
click, and a tree the arrows cannot enter until something is clicked would
look broken.

#### The cell selection: `-selecttype` and `cellselection`

Tk 9.0 added both (TIP 552), and the manual gives `cellselection` a
paragraph. It leaves out most of what a program can see. Measured on Tk
9.0.2 through `tree.tk.call(tree, "cellselection", ...)` and clicks sent
by `event_generate`, and read against ttkTreeview.c (`CellSelectionRange`,
`TreeviewCellSelectionCommand`, `SelObjChangeElement`) and treeview.tcl:

| Question | Tk 9.0.2 |
|----------|----------|
| What a cell reports as its column | The column's name, or `#0`, however it was given: `#1`, `0` and `a` all read back `a` |
| Order of the answer | Rows in tree order, closed branches included; a row's cells in the order they were selected |
| `<<TreeviewSelect>>` | Only on a change, unlike `selection set`. But `set` clears first, so setting the same cell again is a change |
| A row whose last cell was removed | Keeps an empty list, so the next `set` of anything counts as a change |
| One two-element argument | Tried as one cell first, then as a list of two: `("I9", "a")` fails as *Cell id must be a list of two elements*, not *Item I9 not found* |
| A rectangle | Every row from one corner to the other in tree order, closed branches included, across display order; its corners must be showing, *Cell id must be in a visible column*. A list may name a hidden column |
| `detach` | Hides the row's cells from the answer and keeps them; `move` brings them back |
| `delete` | Sends `<<TreeviewSelect>>` when a row named was selected, or had a cell selected - for rows as much as cells |
| `-columns` changed | The cell selection is cleared, with no event. `-displaycolumns` leaves it |
| `-selecttype` changed | Clears neither selection; the two are separate throughout |
| `-selecttype` values | `item` or `cell`, or a prefix; `""` is *ambiguous* |

The bindings, under `selecttype cell`: a click selects one cell and leaves
the row selection alone; Control-click toggles a cell; Shift-click adds the
rectangle from the last cell chosen when that was a Control-click, and sets
it when it was a plain click. `browse` takes one cell whatever the
modifier, and `none` only moves the focus row.

The arrows follow `ttk::treeview::Keynav` but for one limit, which TkCurses
does not copy. **Tk's Right stops one column short of the last**: Keynav
compares the column number with the count of columns less one, so with
columns `a b c` Right reaches `#2` and never `#3`. Measured on Tk 9.0.2 with
four and with five columns, each tree wide enough for every column, so it is
not a matter of the view: it is always one short. The manual says nothing of
the arrows, and Keynav itself is marked `@@@ TODO: verify/rewrite`, so this
reads as Tk's bug rather than its design. Here Right goes on to the last
column; a program that arrows there breaks nothing that worked under Tk.
Left stops at `#0`, or at `#1` without the tree column. Up and Down keep the
column of the anchor, `#1` when there is none.

**`tk.call` reaches it as in tkinter.** tkinter has no methods for the cell
selection, so a tkinter program must write
`tree.tk.call(tree, "cellselection", ...)`. That works here, answering as
tkinter does (`""` for nothing, tuples for cells), and `tk.splitlist` reads
the answer. There is no Tcl interpreter behind it: `Application.call` hands
a widget's own subcommand to the widget (see "`tk.call`" under the
implementation notes for what else it serves). TkCurses's `cellselection`
methods remain, as extensions.

**Two differences, recorded in the docstring:** the Right arrow, above, and the anchor. Tk keeps the anchor in one
namespace variable for every treeview in the interpreter; TkCurses keeps one
per tree, so a Shift-click in one tree never extends from a cell of another.

### ttk.Separator

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Line separator |

**Rendering:**
```
Horizontal: ─────────────────────────
Vertical:   │
            │
            │
```

### ttk.Sizegrip

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Resize grip |

**Rendering:**
```
◢  (bottom-right corner)
```

### ttk.LabeledScale

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Scale with label |
| `value` (property) | ✓ | Get/set value |
| `destroy()` | ✓ | Destroy widget |

### ttk.OptionMenu

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master, variable, default, *values)` | ○ | Option menu |
| `set_menu(default, *values)` | ✓ | Set options |
| `destroy()` | ✓ | Destroy widget |

---

## Dialog Modules

### commondialog.Dialog

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master, **options)` | ○ | Create dialog |
| `show(**options)` | ○ | Display dialog |
| `_fixoptions()` | ✓ | Preprocess options |
| `_fixresult(widget, result)` | ✓ | Postprocess result |

### filedialog Module

| tkinter Class/Function | TkCurses | Notes |
|------------------------|----------|-------|
| `FileDialog(master, title)` | ○ | Text file browser |
| `FileDialog.go(dir, pattern, default, key)` | ○ | Show and return |
| `FileDialog.ok_command()` | ✓ | OK handler |
| `FileDialog.cancel_command()` | ✓ | Cancel handler |
| `FileDialog.filter_command()` | ✓ | Filter handler |
| `FileDialog.get_filter()` | ✓ | Get filter |
| `FileDialog.get_selection()` | ✓ | Get selection |
| `FileDialog.set_filter(dir, pat)` | ✓ | Set filter |
| `FileDialog.set_selection(file)` | ✓ | Set selection |
| `LoadFileDialog(master, title)` | ○ | Open file dialog |
| `SaveFileDialog(master, title)` | ○ | Save file dialog |
| `Open(**options)` | ○ | Native-style open |
| `SaveAs(**options)` | ○ | Native-style save |
| `Directory(**options)` | ○ | Directory picker |
| `askopenfilename(**options)` | ○ | Convenience function |
| `asksaveasfilename(**options)` | ○ | Convenience function |
| `askopenfilenames(**options)` | ○ | Multiple files |
| `askopenfile(mode, **options)` | ○ | Open and return file |
| `askopenfiles(mode, **options)` | ○ | Multiple files |
| `asksaveasfile(mode, **options)` | ○ | Save and return file |
| `askdirectory(**options)` | ○ | Directory selection |

### simpledialog Module

| tkinter Class/Function | TkCurses | Notes |
|------------------------|----------|-------|
| `SimpleDialog(master, text, buttons, ...)` | ○ | Simple dialog |
| `SimpleDialog.go()` | ○ | Show and wait |
| `Dialog(parent, title)` | ○ | Custom dialog base |
| `Dialog.body(master)` | ✓ | Override for content |
| `Dialog.buttonbox()` | ○ | Create buttons |
| `Dialog.ok(event)` | ✓ | OK handler |
| `Dialog.cancel(event)` | ✓ | Cancel handler |
| `Dialog.validate()` | ✓ | Validate input |
| `Dialog.apply()` | ✓ | Apply result |
| `_QueryDialog(title, prompt, ...)` | ○ | Input dialog |
| `_QueryInteger(title, prompt, ...)` | ○ | Integer input |
| `_QueryFloat(title, prompt, ...)` | ○ | Float input |
| `_QueryString(title, prompt, ...)` | ○ | String input |
| `askinteger(title, prompt, **kw)` | ○ | Convenience function |
| `askfloat(title, prompt, **kw)` | ○ | Convenience function |
| `askstring(title, prompt, **kw)` | ○ | Convenience function |

### messagebox Module

| tkinter Function | TkCurses | Notes |
|------------------|----------|-------|
| `showinfo(title, message, **options)` | ○ | Info dialog |
| `showwarning(title, message, **options)` | ○ | Warning dialog |
| `showerror(title, message, **options)` | ○ | Error dialog |
| `askquestion(title, message, **options)` | ○ | Yes/No question |
| `askokcancel(title, message, **options)` | ○ | OK/Cancel |
| `askyesno(title, message, **options)` | ○ | Yes/No |
| `askyesnocancel(title, message, **options)` | ○ | Yes/No/Cancel |
| `askretrycancel(title, message, **options)` | ○ | Retry/Cancel |

**Constants:**
- Icons: `ERROR`, `INFO`, `QUESTION`, `WARNING`
- Types: `ABORTRETRYIGNORE`, `OK`, `OKCANCEL`, `RETRYCANCEL`, `YESNO`, `YESNOCANCEL`
- Replies: `ABORT`, `RETRY`, `IGNORE`, `OK`, `CANCEL`, `YES`, `NO`

### colorchooser Module

| tkinter Class/Function | TkCurses | Notes |
|------------------------|----------|-------|
| `Chooser(master, **options)` | ○ | Color picker |
| `Chooser.show(**options)` | ○ | Display chooser |
| `askcolor(color, **options)` | ○ | Convenience function |

Shaped like Tk's, read out of `clrpick.tcl`: three colour bars, one per
channel, each showing what the colour becomes as that channel varies and the
other two stay put; three numeric entries taking 0-255, applied on Return; a
`Selection:` entry holding the `#rrggbb`; a swatch of the result; OK and
Cancel. There is no colour-name lookup, because Tk has none - though the
`Selection:` entry takes a name just as Tk's does, since both hand the text
to `winfo_rgb`.

The bars are **fixed scales**, and that is a deliberate departure from Tk.
Tk draws each strip with the *other* two channels at their current values, so
moving green repaints the red and blue strips — measured against Tk 9.0.2,
where raising green from 0 to 255 turns the red strip from a black-to-red
ramp into a green-to-yellow one. On an X display that is a live preview of
millions of colours; here a bar has two to six steps, and with the other
channels at mid intensity the whole red bar resolves to **one** colour at 8
and at 16, so the scale stops being a scale. Each bar is therefore its own
channel alone, painted once. The panel under `Selection:` does what the
cross-coupling was for — showing the colour actually being built.

**What adapts is how many steps a bar has**, and it comes from
`winfo_colordepth()`. Tk draws sixteen; on an eight-colour terminal those
sixteen resolve to three results, two of which differ only by `A_BOLD` and so
look identical as a background - sixteen steps, two appearances. So the bar
is drawn with as many steps as the terminal has intensities: two at eight
colours, three at sixteen, six at 256 (the cube's own levels), sixteen in
direct colour. The entries are unaffected and reach every value at any depth.

### font Module

| tkinter Class/Function | TkCurses | Notes |
|------------------------|----------|-------|
| `Font(root, font, name, exists, **kw)` | ○ | Font wrapper |
| `Font.actual(option, displayof)` | ○ | Actual attributes |
| `Font.cget(option)` | ○ | Get attribute |
| `Font.configure(**kw)` | ○ | Configure font |
| `Font.copy()` | ○ | Copy font |
| `Font.measure(text, displayof)` | ○ | Text width (cells) |
| `Font.metrics(*options, displayof)` | ○ | Font metrics |
| `nametofont(name, root)` | ○ | Name to font |
| `families(root, displayof)` | ◐ | Font families |
| `names(root)` | ◐ | Named fonts |

**Note:** In TkCurses, all fonts are monospace. The Font class maps font attributes to text attributes (bold → A_BOLD, italic → A_ITALIC, underline → A_UNDERLINE).

### scrolledtext Module

| tkinter Class | TkCurses | Notes |
|---------------|----------|-------|
| `ScrolledText(master, **kw)` | ○ | Text + scrollbar |

Inherits from Text with integrated Scrollbar.

### dnd Module

| tkinter Function | TkCurses | Notes |
|------------------|----------|-------|
| `dnd_start(source, event)` | ○ | Start drag |

**Note:** Drag and drop operates on cell coordinates in TkCurses.

---

## Curses Compatibility Module

`tkcurses.curses` provides a curses-compatible API — a facade over
`CursesScreen` and `ScreenBuffer`, not a reimplementation, so a curses
program gets this layer's double-buffered painting, resize handling and
colour depth detection without being written any differently.

**Anything not defined there is forwarded to the standard library's curses**,
which is where every constant comes from and how the list stays current.

**`has_colors()` and `can_change_color()` tell the truth.** They were
specified as "always True" and that was wrong: a terminal has one of five
colour depths and a vt100 has none. A curses program asks those questions
precisely so it can draw differently, and a compatibility layer that lies is
worse than one that is missing.

**Importing it is safe for the rest of the package**, and that took
arranging. `tkcurses.curses` is a submodule, so importing it binds it as the
attribute `curses` on the package — which is `tkcurses/__init__.py`'s own
global namespace. Measured: a plain `import curses` there was silently
replaced by the facade, and all fifty-one references in that file would have
resolved against it. That module imports the standard library as `_curses`.

#### The refresh rule

A window has cells of its own; writing changes nothing on the terminal until
`noutrefresh()` copies them and `doupdate()` paints. **A refresh copies the
touched *part of each touched line* in that window and nothing else.**

Both halves of that are rules on their own. Lines: refreshing stdscr erases
an overlapping window in one program and leaves it standing in another, the
difference being only whether stdscr had been refreshed before. Ranges: a
program that writes five characters onto a line and refreshes leaves the rest
of that line alone, so a panel's border further along it survives — copying
whole lines wiped it. A new window starts wholly touched, so its first
refresh paints its blank background over whatever was underneath.

None of that was guessed. The tty tests run the same source twice — once
importing `curses`, once importing `tkcurses.curses` — and compare the two
screens; each rule above is a difference that comparison turned up.

A subwindow shares its parent's cells at an offset, so writing into the child
shows through the parent, as in curses.

### Module Functions

| curses Function | TkCurses | Notes |
|-----------------|----------|-------|
| `initscr()` | ✓ | Initialize, return stdscr |
| `endwin()` | ✓ | End curses mode |
| `isendwin()` | ✓ | Check if ended |
| `wrapper(func, *args, **kwargs)` | ✓ | Safe wrapper |
| `newwin(nlines, ncols, begin_y, begin_x)` | ✓ | Create window |
| `newpad(nlines, ncols)` | ✓ | A pad; `refresh` and `noutrefresh` take its six arguments, clipped as ncurses' `pnoutrefresh` clips them, and `subpad` makes its subwindows |
| `getwin(file)` | ✓ | Reads ncurses' own saved-window format, the standard library's included |
| `start_color()` | ✓ | Initialize colors |
| `init_pair(pair, fg, bg)` | ✓ | Define color pair |
| `init_color(color, r, g, b)` | ✓ | Define color |
| `color_pair(n)` | ✓ | Get pair attribute |
| `pair_number(attr)` | ✓ | Get pair number |
| `pair_content(pair)` | ✓ | Get pair colors |
| `color_content(color)` | ✓ | Get color RGB |
| `has_colors()` | ✓ | What the terminal really has — **not** always True |
| `can_change_color()` | ✓ | Likewise; both delegate to curses |
| `cbreak()` | ✓ | Cbreak mode |
| `nocbreak()` | ✓ | Exit cbreak |
| `echo()` | ✓ | Echo mode |
| `noecho()` | ✓ | No echo |
| `raw()` | ✓ | Raw mode |
| `noraw()` | ✓ | Exit raw |
| `nl()` | ✓ | Newline mode |
| `nonl()` | ✓ | No newline |
| `curs_set(visibility)` | ○ | Cursor visibility |
| `flash()` | ○ | Flash screen |
| `beep()` | ○ | Bell |
| `doupdate()` | ✓ | Update screen |
| `napms(ms)` | ✓ | Sleep |
| `flushinp()` | ✓ | Flush input |
| `ungetch(ch)` | ✓ | Push character |
| `getmouse()` | ✓ | Get mouse event |
| `mousemask(mask)` | ✓ | Set mouse events |
| `mouseinterval(interval)` | ✓ | Click interval |
| `keyname(k)` | ✓ | Key name |
| `unctrl(ch)` | ✓ | Printable repr |

### Window Methods

| curses Method | TkCurses | Notes |
|---------------|----------|-------|
| `addch(ch, attr)` | ✓ | Add character |
| `addch(y, x, ch, attr)` | ✓ | Add at position |
| `addstr(str, attr)` | ✓ | Add string |
| `addstr(y, x, str, attr)` | ✓ | Add at position |
| `addnstr(str, n, attr)` | ✓ | Add n chars |
| `echochar(ch, attr)` | ✓ | Add and refresh |
| `getch(y, x)` | ✓ | Get character |
| `getkey(y, x)` | ✓ | Get key string |
| `getstr(n)` | ✓ | Get string |
| `inch(y, x)` | ✓ | Get char+attr |
| `instr(n)` | ✓ | Get string |
| `insch(ch, attr)` | ✓ | Insert character |
| `insstr(str, attr)` | ✓ | Insert string |
| `delch(y, x)` | ✓ | Delete character |
| `deleteln()` | ✓ | Delete line |
| `insertln()` | ✓ | Insert line |
| `clear()` | ✓ | Clear and repaint |
| `erase()` | ✓ | Erase window |
| `clrtoeol()` | ✓ | Clear to EOL |
| `clrtobot()` | ✓ | Clear to bottom |
| `move(y, x)` | ✓ | Move cursor |
| `getyx()` | ✓ | Get cursor pos |
| `getbegyx()` | ✓ | Get origin |
| `getmaxyx()` | ✓ | Get dimensions |
| `refresh()` | ✓ | Update window |
| `noutrefresh()` | ✓ | Mark for update |
| `redrawwin()` | ✓ | Force redraw |
| `redrawln(beg, num)` | ✓ | Redraw lines |
| `scroll(lines)` | ✓ | Scroll window |
| `scrollok(flag)` | ✓ | Allow scroll |
| `setscrreg(top, bottom)` | ✓ | Scroll region |
| `border(...)` | ✓ | Draw border |
| `box(vertch, horch)` | ✓ | Draw box |
| `hline(ch, n)` | ✓ | Horizontal line |
| `vline(ch, n)` | ✓ | Vertical line |
| `bkgd(ch, attr)` | ✓ | Set background |
| `bkgdset(ch, attr)` | ✓ | Set background |
| `getbkgd()` | ✓ | Get background |
| `attron(attr)` | ✓ | Add attribute |
| `attroff(attr)` | ✓ | Remove attribute |
| `attrset(attr)` | ✓ | Set attribute |
| `chgat(num, attr)` | ✓ | Change attributes |
| `standout()` | ✓ | Standout on |
| `standend()` | ✓ | Standout off |
| `keypad(flag)` | ✓ | Enable keypad |
| `nodelay(flag)` | ✓ | Non-blocking |
| `timeout(delay)` | ✓ | Set timeout |
| `notimeout(flag)` | ✓ | Disable timeout |
| `clearok(flag)` | ✓ | Force clear |
| `idlok(flag)` | ✓ | Line insert/delete |
| `idcok(flag)` | ✓ | Char insert/delete |
| `immedok(flag)` | ✓ | Immediate refresh |
| `leaveok(flag)` | ✓ | Leave cursor |
| `touchwin()` | ✓ | Touch window |
| `touchline(start, count)` | ✓ | Touch lines |
| `untouchwin()` | ✓ | Untouch window |
| `is_wintouched()` | ✓ | Check touched |
| `is_linetouched(line)` | ✓ | Check line |
| `subwin(...)` | ✓ | Create subwindow |
| `derwin(...)` | ✓ | Create derived |
| `mvwin(y, x)` | ✓ | Move window |
| `mvderwin(y, x)` | ✓ | Move derived |
| `resize(nlines, ncols)` | ✓ | Resize window |
| `overlay(destwin, ...)` | ✓ | Where the windows overlap, or the six-argument rectangle; blanks left out |
| `overwrite(destwin, ...)` | ✓ | The same, blanks too |
| `syncup()` | ✓ | Sync to parent |
| `syncdown()` | ✓ | Sync from parent |
| `syncok(flag)` | ✓ | Auto sync |
| `cursyncup()` | ✓ | Sync cursor |
| `putwin(file)` | ✓ | ncurses' text format, byte for byte for what this layer keeps; read back by the standard library's `getwin` |
| `enclose(y, x)` | ✓ | Check enclosed |
| `encoding` | ✓ | The locale's; `subwin` passes it on and `derwin` does not, as in the standard library |

### Constants

All curses constants are available:
- Attributes: `A_NORMAL`, `A_STANDOUT`, `A_UNDERLINE`, `A_REVERSE`, `A_BLINK`, `A_DIM`, `A_BOLD`, `A_PROTECT`, `A_INVIS`, `A_ALTCHARSET`, `A_ITALIC`
- Colors: `COLOR_BLACK`, `COLOR_RED`, `COLOR_GREEN`, `COLOR_YELLOW`, `COLOR_BLUE`, `COLOR_MAGENTA`, `COLOR_CYAN`, `COLOR_WHITE`
- Keys: `KEY_UP`, `KEY_DOWN`, `KEY_LEFT`, `KEY_RIGHT`, `KEY_HOME`, `KEY_END`, `KEY_PPAGE`, `KEY_NPAGE`, `KEY_DC`, `KEY_IC`, `KEY_BACKSPACE`, `KEY_F0`-`KEY_F63`, `KEY_MOUSE`, `KEY_RESIZE`
- ACS Characters: `ACS_ULCORNER`, `ACS_URCORNER`, `ACS_LLCORNER`, `ACS_LRCORNER`, `ACS_HLINE`, `ACS_VLINE`, `ACS_PLUS`, `ACS_LTEE`, `ACS_RTEE`, `ACS_BTEE`, `ACS_TTEE`, `ACS_BLOCK`, `ACS_CKBOARD`, `ACS_DIAMOND`, `ACS_DEGREE`, `ACS_BULLET`

---

## Panel Module

`tkcurses.panel` provides curses.panel-compatible API, over the windows
`tkcurses.curses` makes. A curses window has no idea what is in front of it;
this adds the one thing that fixes that — an order, and an `update_panels()`
that copies every visible panel back to front.

It does **not** reuse `_core.panels.PanelStack`, which the widgets stack
themselves with. That one creates its own windows from a rectangle and hands
the ordering to real curses panels; this one is handed a window that is
already a cell buffer and does the ordering itself. Sharing the code would
mean one class doing both, badly.

| curses.panel Function | TkCurses | Notes |
|-----------------------|----------|-------|
| `new_panel(win)` | ✓ | Create panel |
| `bottom_panel()` | ✓ | Get bottom |
| `top_panel()` | ✓ | Get top |
| `update_panels()` | ✓ | Update stack |

### Panel Methods

| Method | TkCurses | Notes |
|--------|----------|-------|
| `above()` | ✓ | Panel above |
| `below()` | ✓ | Panel below |
| `bottom()` | ✓ | Move to bottom |
| `hidden()` | ✓ | Is hidden? |
| `hide()` | ✓ | Hide panel |
| `move(y, x)` | ✓ | Move panel |
| `replace(win)` | ✓ | Replace window |
| `set_userptr(obj)` | ✓ | Set user data |

## BarGraph

`tkcurses.bargraph.BarGraph` is a widget neither tkinter nor Tk has. It
began as a separate package, `tkcurses-bargraph`, by the same author, and
was brought in for 0.6 as a fresh copy without its history
(`TkCurses-5r79`). Like `curses` and `panel` it is an extension module:
`tests/support/docsurface.py` lists it in `EXTENSION_MODULES`, and its
docstrings carry the `TkCurses extension:` section.

### Its names, decided when it came in

The API was declared stable on arrival, so its names were settled first
(`TkCurses-5r79.1`):

- **The three millisecond options follow Tk's spelling** - one lowercase
  word, no unit suffix, as `repeatdelay` and `insertofftime`:
  `refresh_ms` became `refreshinterval`, `autoscale_ms` `autoscaledelay`
  and `peakhold_ms` `peakholdtime`. Each is still milliseconds and `0`
  keeps its meaning. The old names are refused like any unknown option.
- **Where an option does what a Tk widget's does, it has that name**:
  `orient` and `maximum` as `ttk.Progressbar`'s, `digits` as `Scale`'s,
  `labelanchor` as `LabelFrame`'s. `minimum` pairs with `maximum`.
- **`set`, `set_all` and `get` stay**, though `ttk.Progressbar` has no
  `set`: a bar graph holds a table of values, which Progressbar's
  `value`/`step` do not describe.

### Pure modules, one widget module

The private modules know nothing of curses or of the rest of TkCurses, and
raise `ValueError`; the widget turns that into `TclError`.

| Module | Does |
|--------|------|
| `_model` | segments × series values, validation; `AutoScale` |
| `_scale` | `"64"` and `"75%"` scales, `ValueRange` (linear or log, from `minimum`), value to points, round numbers |
| `_layout` | the frame's size to regions: bars, axis, readout, labels, box |
| `_render` | values to runs and cells, with colour *roles* (series *i*, zone *j*, marker, background), never colours |
| `_thresholds` | levels to colour zones along a bar |
| `_decor` | baseline, ticks, gridlines, markers, peak hold, readout, the box's text; composes the window |
| `_gradient` | each series cell's shade by position |
| `_glyphs` | the eighth-block ramps, monochrome patterns |

`__init__.py` holds only `BarGraph`. It parses options into a frozen
config, asks the pure modules for a window of cells, maps roles to curses
attributes, and writes the cells. It uses Frame's internals on purpose -
`_redraw`, `_window`, `_rect`, `_bordered`, `_write_line`,
`_request_size`, `_apply_requested_size`, `_invalidate_layout`,
`_options` - and the application's screen, colours and
`CursesDispatcher`; a change to any of those has this one module to fix.

**What it shares with Treemap is in `tkcurses/_charts/`**, a private
package. They moved there from BarGraph when the second chart came
(`TkCurses-i1rh.2`, `.4`, `.6`), so neither widget imports the other's
private modules:

| Module | Holds |
|---|---|
| `numformat` | how a value is written, on an axis, in a readout or a label |
| `color` | `DEFAULT_COLORS`; `mix`, `shade_rgb`, `hex_color`; WCAG `luminance` and `text_on` |
| `text` | characters to cells (`clusters`), and `fit`, cutting a line with `…` |
| `geometry` | `Rect`, and cutting regions off one |
| `options` | checking option values, with Tk's words |

All are pure but `options`, which checks a colour against the library's
colour names. Its `items` reads one value given where a list is wanted
as a list of one, as Tcl does: `colors=5` had raised a `TypeError` out
of `tuple(5)` in BarGraph since 0.6.

### Drawing in eighths

A bar's length is counted in *points*, eight to a cell, drawn with the
Block Elements ramps: `▁▂▃▄▅▆▇█` growing up, `▏▎▍▌▋▊▉█` growing right. A
scale is an absolute number of points (`scale=64`, eight cells, at least
8) or a percentage of the frame's length (`"100%"`, the default), worked
out again on every resize. Thickness, across the bar, has no eighths:
with an absolute scale it is `thickness` cells; with a percentage the
cross axis is shared among the bars, the spare cells going to the first
ones, and `thickness` is the least a bar gets.

**A cell shows at most two colours**, its foreground and its background.
A partial glyph is the series that ends in the cell over the one that
continues past it. Where three or more meet in one cell, the smallest run
is given to its larger neighbour until two remain; the bar's tip never
moves, so a stacked total, or the longest overlaid value, stays exact and
only that cell is approximate. A threshold zone is merged the same way,
except that the highest zone a bar reaches is never the one merged away:
a bar past 90% always shows red at its tip.

Both modes reduce to runs end to end before that rule: stacked, the
running totals; overlay, at each point the shortest value still covering
it, since the shorter are painted over the longer. A log scale refuses to
stack several series - equal lengths on it are equal ratios, not equal
amounts.

On a monochrome terminal, series and zones are told apart by `█▓▒░`.

### Colour

`colors` is one per series, cycled. Every colour an option names is
checked when it is set, with `parse_color`, and an unknown one is refused
with Tk's message (`TkCurses-5r79.9`): before, the name reached the paint,
which raised on every pass and left the screen blank.

`colormode="gradient"` shades by *position*, not value: at zero a series
is its `gradientstart` (default a quarter of its colour's brightness), at
the maximum its own colour, in at most 16 shades - each pairs with every
background it meets, and curses names only about 255 pairs. The blend is
linear in RGB. Thresholds win over it, and a held peak takes the shade at
its level. Smooth at truecolor, banded at 256, solid below.

### Repainting

`set` and `set_all` change the model and mark it dirty; they never paint.
A repaint is scheduled with `after(refreshinterval)`, and the tick calls
`source` if there is one, paints, and re-arms only while something is
pending: so a producer calling `set` a thousand times a second costs at
most one repaint each interval. Everything is on the event loop; data
from a thread comes through a queue that `source` reads.

**An autoscaled maximum grows at once and shrinks on the timer**
(`_model.AutoScale`). It grows to the round number at or above the
largest value, held peaks included, the moment a value needs it - in
`set`, `set_all` and `configure`, not at the next tick: the first frame
of a new graph had drawn every bar full against an unset maximum
(`TkCurses-5r79.11`). It shrinks only when the values have stayed under a
lower round number for `autoscaledelay`, and then only to the highest
round number they needed in that wait, so a burst's tail costs one step
and the next quiet stretch another. `examples/meters.py` is timed so both
steps land between bursts. Peak hold and autoscale read
`time.monotonic()`; only the repaint uses Tk's timer.

Round numbers are the 1-2-5 series - times powers of ten, or of 1024 for
`unitscale="binary"`, or steps a clock reads (15 s, 1 min, 1 h) for
time units - from one generator, `_scale.round_steps`, which ticks and
autoscale share.

### Text is measured in cells

Labels, the readout, tick labels and the axis title are measured and cut
with `_core.cells`, not `len()` (`TkCurses-5r79.10`): a CJK label ran
past its bar, and an accented one, `"Café"` written with a combining
mark, sat a cell off centre. `_decor`'s painter groups a combining mark
with its base, gives a wide character two cells - the second an empty
`CONTINUATION` cell the widget skips when writing - or a space when only
one is left.

### How its options are measured

`record_visible_options.py` names it `bargraph.BarGraph`, and
`docsurface.measured_class` resolves that name; a base of three bars of
two series with values to draw; per-widget values in `WIDGET_VALUES`;
and `WIDGET_NEEDS`, what an option needs before it can show at all - a
readout a horizontal graph, `logbase` a log scale, `units` an axis.
Measured three times alike: 40 options visible, 14 not and 3 behaviour.
`peakholdtime` is among the invisible because one screen from one set of
values has never fallen from a peak; `autoscaledelay` and
`refreshinterval` likewise act over time. Their samples are in the
docstring regardless.

A guard test fails for any public module under `tkcurses` in neither
`COUNTERPARTS` nor `EXTENSION_MODULES`: before it, the new module passed
every docstring rule by being invisible to them.

### Not yet

Negative values. The origin left room: a bar split at a zero line, the
negative side drawn with the complementary glyph in swapped colours,
since the block has no eighth steps growing down or left.

## Treemap

`tkcurses.treemap.Treemap` is the second widget neither tkinter nor Tk
has. It draws a hierarchy of values as nested rectangles, each sized by
its value, after Kibana's treemap charts. Like BarGraph it is an extension
module: listed in `EXTENSION_MODULES`, and documented with
`TkCurses extension:`.

**This section is the design, written before the code** for review. Each
heading names the decision and why. `Not yet` lists what was left out on
purpose.

### What comes from Kibana, and what does not

Kibana's treemap is the model for *behaviour*. Its options, their
defaults, and what a reader of the chart sees all follow Kibana. Kibana's
*code* is not used. Its source is licensed AGPL-3.0, SSPL or the Elastic
License 2.0, at the user's choice (the header of
`expression_partition_vis/common/expression_functions/treemap_vis_function.ts`).
None of those can be copied into a GPL-3.0-only library. Following a
product's documented behaviour is not copying its code, just as this
library follows tkinter's interface without tkinter's source.

The layout is the **squarified treemap** of Bruls, Huizing and van Wijk
("Squarified Treemaps", *Data Visualization 2000*). It is implemented from
the paper and credited beside the code, by the rule for published
algorithms.

| Kibana | Here |
|---|---|
| Up to 2 Group by levels | Up to 2 levels: a third is refused |
| Rectangles largest first | Largest first, ties in insertion order |
| Slice labels: Show / Hide; hidden when a tile is too small | `labels`; hidden by the same test |
| Slice values: Percentage / Integer / Hide; Decimal places, default 2 | `values`: `percent` / `value` / `none`; `percentdecimals`, default 2 |
| Value format | BarGraph's number options, by the same names: `units`, `digits`, `decimals` and the rest |
| Legend: Visibility Auto / Show / Hide; position; Width; Nested; Line limit | `legend`, `legendposition`, `legendsize`, `nestedlegend`, `legendlines` |
| Palette on the first level; nested levels follow their parent | `colors` on the top level; children are shades of it |
| Hide zero values, on by default | A zero value takes no space |
| Hover tooltip | The **readout** row, for the focused tile |
| Click to filter | **Zoom**: a group fills the widget, Escape comes back |
| Thin white borders between tiles | **Shades** of the group's colour; **outlines** where the terminal cannot show shades |

Not taken: split charts (small multiples), "Other" grouping, per-category
colour mapping, and empty-bucket rows.

### The data: Treeview's item API, two levels

The items are a ttk.Treeview's: `insert(parent, index, iid=None, text=,
value=)` returns an iid (generated `I001`, `I002`, as Treeview's), with
`item`, `delete`, `get_children`, `parent`, `exists`, `index`, `move`,
`focus`, `selection` and `selection_set`. Errors use Treeview's words:
`Item X not found`, `Item X already exists`. A program that knows
Treeview knows this, and each tile has a handle a program can update.

- **Two levels.** An item under the root is a *top-level item*. An item
  under one of those is a *child*. Inserting under a child is refused:
  `a treemap has two levels: I002 is already a child`. `move` refuses the
  same, and a group going under another item.
- **`delete` checks every name first**, as Tk does: one not found raises
  `Item X not found` and nothing is removed. (TkCurses' Treeview skips a
  missing name instead.)
- **A group is a top-level item with children.** Its size is the sum of
  its children. A `value` given to it is kept but not used while it has
  children, so deleting the last child brings it back.
- **A value is a finite number, not negative.** Negative, NaN and
  infinity are refused with `TclError`. Zero is kept, and takes no space.
- **Order on screen is by size, largest first**, whatever the insertion
  order; `index` and `get_children` keep the siblings' order, as
  Treeview's do. Equal sizes keep that order, so a layout is stable.
- **One item is selected at most.** Kibana's click picks one value.
  `selection()` still answers a tuple, for Treeview code.

### Modules

As BarGraph: pure modules know nothing of curses and raise `ValueError`;
`__init__.py` holds only the widget.

| Module | Does |
|---|---|
| `_model` | items, the two-level rule, sizes, order |
| `_squarify` | weights and a rectangle to rectangles: the paper's algorithm, then snapped to cells |
| `_layout` | the widget's size to regions: legend, readout, tiles; then the items to tiles, with group headers, zoom and the hidden ones |
| `_shades` | the four shades, which each child takes so no two neighbours share one, and which levels are outlined |
| `_outline` | the lines between outlined tiles, with their junctions |
| `_labels` | what text fits in a tile, and where |
| `_legend` | the entries, wrapped and truncated, flowed into the legend region |
| `_navigate` | which tile an arrow key moves to |
| `_compose` | all of that into rows of cells, with the focus reversed and the selection marked, each naming its colours as specs, `""` for the widget's own |

**Shared with BarGraph, moved, not copied.** These move into a private
package `tkcurses/_charts/`, and BarGraph imports them from there:
`_numformat` (how a value is written), the RGB blend `shade_rgb` and
`hex_color` from `_gradient`, the `Cell` and role types from `_render`,
the painter that writes text into cells by `_core.cells` widths from
`_decor`, and `_layout`'s `Rect`. A second chart widget is the reason a shared package is worth
having. BarGraph's behaviour does not change, and its tests hold it.

### Layout

**Squarified in the eye's units, not the terminal's.** A character cell is
about twice as tall as it is wide. The algorithm wants tiles near square,
so it runs on a rectangle `width × 2·height`, and the result is scaled
back. A tile square in cells would look like a tall bar.

The algorithm, from the paper:

1. Lay tiles along the shorter side of the free rectangle, adding the
   next largest to the current row while that does not make the row's
   worst aspect ratio worse.
2. When it would, fix the row and continue in what is left.

A tie keeps adding: the paper's test is "worse". The tests hold its own
worked example, 6, 6, 4, 3, 2, 2, 1 in a 6 × 4 rectangle.

**Snapped to whole cells by rounding edges, not sizes.** Each tile's
edges are cumulative positions: a row's offset from the rectangle's
start, and a tile's offset along its row. Each position is rounded once, half up. The last tile of a row ends,
and the last row ends, exactly at the free rectangle's edge, not at a sum
that may differ from it in the last bit.
Two tiles that share an edge share the rounded position too, so the tiles
cover the area exactly, with no gap and no overlap. Each edge is within
half a cell of its exact place, so a tile's area is within one row and
one column of its share. A tile whose edges round together has no cells
and is **too small to show**. It is counted in the readout, and stays
reachable through the API.

**A group has a header** when its rectangle is at least 3 rows high and
6 columns wide: one row with its name and value, in its colour, made
bold. Its children are laid out in the rest. A group too small for a
header gives its whole rectangle to its children, and its name is in the
legend and the readout. A header row comes out of the group's area, so
its children share what is left: their areas are shares of the group's
tile less its header, while a percentage is still of the values, not the
cells.

**A zoomed group's children fill the tiles region alone**, without the
group's header: the readout names the group.

**Too small to show** is an item with a size whose tile has no cells. A
hidden group hides its children with it, and each is counted. An item
whose size is zero is not counted: it was never meant to take room.

**Regions, outside in:**

1. The readout takes the bottom row, if `readout` is on.
2. The legend takes a side.
3. The tiles take the rest.

When the tiles would be left with fewer than 10 columns or 3 rows, the
legend goes first, then the readout.

```text
web 64.71%                                       │██ web
nginx                │apache        │php         │██ db
38.82%               │20.00%        │5.88%       │██ cache
                     │              │            │
db 23.53%                        │cache          │
postgres             │mysql      │11.76%         │
16.47%               │7.06%      │               │
web › nginx   330   38.82% of all   60.00% of web
```

That is 60 × 8, with the legend on the right, for `web` (nginx 330,
apache 170, php 50), `db` (postgres 140, mysql 60) and `cache` 100: 850
in all, with `nginx` focused. In the widget there are no
`│` lines between tiles: they mark where one shade or colour meets
another. The `│` before the legend is the legend's own edge.

### Colour, shades and outlines

**Each top-level item takes a colour** from `colors`, in order of size,
cycled: BarGraph's six by default. A group's children are **shades** of
its colour, as Kibana's nested slices are, so a group reads as one
region. The header is the colour itself; children take shades blended
in RGB:

| Shade | Blend |
|---|---|
| 0 | the colour's own |
| 1 | a quarter of the way to black |
| 2 | 30% of the way to white |
| 3 | half way to black |

**Neighbours never share a shade.** Shades are not dealt out in order,
since two children next to each other could then match. `_shades` builds
the adjacency of the group's tiles (rectangles sharing an edge). It gives
each tile, largest first, the lowest shade no earlier neighbour has.

That alone is not enough. Hypothesis found 11 tiles in 46 × 23 where it
gave a tile shade 0 with shade 2 free, and a later tile then met all four
among its neighbours and had to share one. Tiles that only meet at edges
can always be told apart with four (the four colour theorem). So when
a tile finds none free, the search backs up and tries the earlier tiles
with their next shades, depth first. Lowest first means a layout that
never ran out keeps exactly the shades it had. After 20,000 tries
(`SEARCH_STEPS`), or with fewer than four shades, a tile left with none
takes its smallest neighbour's shade, and the label still tells the two
apart. The four are, from `#cd00cd` for example, `#cd00cd`,
`#9a009a`, `#dc4cdc` and `#660066`; each channel is rounded to the
nearest whole value, half to even, as Python's `round` does.

**Text is black or white**, whichever contrasts more with the tile, by
WCAG 2's relative luminance and contrast ratio (`_charts.color.text_on`):
black on green, yellow and cyan, white on red, blue and magenta. It is
named `black` or `white`, so a terminal of eight colours draws its own.

**Cells name colours, not roles.** BarGraph's cells carry roles, series
and zone, that the widget maps to colours. A treemap's colours come from
the items, a shade each, so `_compose` names the spec itself: a
`colors` entry for the colour, `#rrggbb` for a shade, `""` for the
widget's `foreground` or `background`. The widget only turns specs into
curses attributes.

**Outlined, where shades cannot be seen.** Outlining is decided per
*level*: the top level, or one group's children (`outlined_levels`). The
widget counts how many of a group's four shades the terminal shows apart,
after its palette has rounded them (at 256 colours two blends can land on
one cube entry), and passes that number in, so `_shades` stays pure.
With `outline="auto"`:

| Terminal | Outlined |
|---|---|
| No colour | everything, uncoloured |
| 8 or 16 colours | every group's children; the top level is told apart by `colors` |
| 256 or more | a group whose distinct shades are fewer than 3, or than its children, whichever is less |

`outline="on"` outlines everything, `off` nothing, even without colour,
where the labels are then all that tells tiles apart. An outlined
group's children all take the group's own colour: the lines separate
them, and no shade pairs are spent.

**How the lines are laid.** An outlined tile's rectangle names its box's
corners. Its line runs along its top row and left column, and along the
row and column just past its right and bottom edges, which are its
neighbours' top row and left column. So neighbours share one line, and
`_outline.lines` draws each cell from the directions that meet there:
`┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘`. An outlined level is laid out one column and one
row short (`shrunk`), to close its last boxes, and what a tile shows is
inside its lines (`inner`).

```text
┌──────────────────────────────┬────────────────┐
│web                           │db              │
├──────────────────┬───────────┼───────────┬────┤
│nginx             │apache     │postgres   │mysq│
│                  │           │           │    │
│                  │           │           │    │
│                  │           ├───────────┴────┤
│                  ├───────────┤cache           │
│                  │php        │                │
└──────────────────┴───────────┴────────────────┘
```

That is everything outlined, as without colour: 49 × 10, the services of
the first picture. A group outlined around children that are outlined
too shares its lines with theirs, and its header needs a row more, for
the line under it: 4 rows, not 3. A group too small to hold its
children's lines has them hidden, counted, and shows as itself.

**Colour pairs stay within curses' budget.** That is at most
`len(colors) × 4` tile pairs, plus headers, legend swatches and the
readout, at the default 6 colours under 40. A program with 50 top-level
items still cycles through `colors`, so the count does not grow with the
data.

**The widget counts the shades the terminal keeps apart.** For each
group it resolves the four shades with `parse_color` at the terminal's
`ColorDepth`, and counts the distinct colours that come back. It must
pass a `ColorDepth`, not its number: `parse_color` tells the tiers apart
with `is`, so a plain `256` would be taken for none of them.

### Labels

Kibana hides a label that does not fit. So does this, by these rules:

- **Inside the tile,** a label takes the top row, from the tile's first
  column (after the line, when outlined), and the tile's colour shows
  where it starts. The name is cut with `…` to fit. If it would keep fewer
  than 3 cells, it is not drawn at all.
- **The value goes on the second row** when there is one. In a one-row
  tile it follows the name if both fit whole, and is dropped otherwise:
  the name matters more.
- **`values="percent"` is a share of what is shown.** That is the whole
  treemap, or the group zoomed into. The readout gives both.
  `percentdecimals` sets its decimals. `value` writes the number with
  BarGraph's number options - `units`, `unitplacement`, `unitspace`,
  `digits`, `decimals`, `rounding`, `unitscale` - through the shared
  `NumberFormat`. One option, `valueformat`, was planned; the seven keep
  the two charts' options the same, so a program sets them alike.
- All text is measured with `_core.cells`, so a CJK name takes the cells
  it draws in.

### Size

`width` and `height` are independent, and each is cells (any Tk
distance, `2c` included) or a percentage of the terminal, `"50%"`, kept
as written so it reads back that way. A percentage is above 0 and at most
100, and asks for at least one cell.

An axis not given asks for 40 columns or 12 rows (`NATURAL_SIZE`). A
Frame instead leaves such an axis to its children, which is what makes a
fixed-width sidebar of any height. A treemap has no children, so it
asked for 0 on that axis: `width=30` alone asked for 30 × 0 and vanished
unless packed with `fill`. Measured before the fix: `Treemap(root,
width=30)._requested` was `Size(30, 0)`.

**Following the terminal.** While either axis is a percentage, the
treemap binds the root's `<Configure>`, which `_handle_resize` sends
after every resize, and asks again. The root's tag is on every widget's
bindtags, so a child's `<Configure>` reaches it too; only the root's
own counts. Setting both axes back to cells, or destroying the treemap,
removes the binding. The layout pass that the resize runs comes first
and uses the old request, so a resize lays out twice: once at once, and
again when the new request is idle.

This is not BarGraph's percentage. BarGraph's `scale="75%"` is a share
of the space the graph is *given*, after `fill` and `expand`; a
treemap's `width="50%"` is a share of the *terminal*, asked for before
any of that.

### Legend

- **Entries** are the top-level items, largest first: a two-cell swatch
  `██` in the item's colour, a space, and the name. With `nestedlegend`,
  each group's children follow it, indented two cells, each with its own
  shade.
- **Wrapping.** An entry wraps at word boundaries onto at most
  `legendlines` lines, from 1 to 5, Kibana's default and limit. The last
  line is cut with `…`.
- **`legendposition`** is `right` (Kibana's default), `left`, `top` or
  `bottom`.
- **`legendsize`** is the width on the left or right: `small` 12,
  `medium` 20, `large` 28, `xlarge` 36 cells. `auto` is the widest entry,
  at most a third of the widget. At the top or bottom the entries flow
  across in columns of the widest entry, and the region takes the rows
  they need, at most a third of the height.
- **Overflow.** Entries that do not fit end with a `+N more` line.
- **`legend="auto"`** (Kibana's default) shows it when there are two or
  more top-level items and the tiles keep room (above).
- **The focused item's entry is drawn in reverse,** its name and not its
  swatch: a reversed `██` is a block of the background, so the colour
  would vanish from the very entry being pointed at.
- **Clicking an entry focuses that item, and does not select it.** The
  legend points; selecting is what a tile does. It is also the one way to
  reach an item too small to have a tile: focused from the legend, the
  readout names it, with its value and shares. `identify(x, y)` answers
  an entry's item, so a pointer `tag_bind` sees legend clicks too.
- **What it lists follows what is shown.** Zoomed into a group, the
  legend names the group's children. An item of zero is left out, as it
  has no tile; an item too small for a tile is listed, which is the
  point of the previous paragraph.
- **A swatch is its tile's colour,** the shade a child was given, or the
  group's colour for a child with no tile.
- **The edge.** The column (or row) on the tiles' side is the legend's
  `│` (or `─`), in the widget's foreground. Where the tiles beside it are
  boxed in lines themselves, it is left blank instead: the box's own
  line is already there, and two side by side read as one thick line.
- **Sizes include the edge.** `small` is 12 cells in all, 11 for the
  entries. A legend that cannot hold its edge, a swatch, a space and one
  character (5 columns), or at the top or bottom its edge and one row,
  is not drawn.

### Interaction

The widget takes the focus. `takefocus` is on, as an Entry's is. Focus and
selection are separate, as in Treeview:

| Input | Does |
|---|---|
| Arrow keys | Move the focus to the nearest item in that direction, at the focused item's level |
| Return | On a group: **zoom** into it, focusing its largest child. On anything else: select it |
| Space | Select the focused item, group or not |
| Escape | Zoomed: zoom out, focusing the group. On a child: focus its group. At the top: nothing, so the key reaches the program's bindings |
| Button-1 | Focus and select the tile under the pointer: a group's header selects the group |
| Double-1 | Zoom into the group under the pointer |

**Levels.** The focus is either on top-level items (groups, and items
without children) or on children, crossing from one group's children to
the next. Escape goes up a level and Return goes down. That matches how
the chart reads: first the regions, then what is in them.

**The arrow keys move by geometry** (`_navigate`). The candidates for
Right are the items whose left edge is at or beyond the focused tile's
right edge. Those that overlap it vertically come first; then the
smallest gap; then the nearest centre across the move. The same holds,
turned, for the other three keys. With no candidate the focus stays, and
the key is not consumed. With nothing focused, the first arrow focuses
the largest item shown.

**The opposite key goes back**, whatever the geometry says. The rule
alone does not promise it: Right from a tall tile can land on a short
neighbour whose own Left prefers a different tall tile. So each move
remembers where it came from, and the opposite key from where it landed
returns there; another move, or a focus set by the program, forgets.

**Selecting fires `<<TreemapSelect>>`**, and zooming fires
`<<TreemapZoom>>`. `zoom(item)` zooms in from the program, `zoom("")`
zooms out, and `zoom()` answers the current one, as `xview()` answers
the view. `identify(x, y)` answers the iid under a point, or `""`, for a
program's own mouse bindings.

**How focus and selection show.** The focused tile's label row is
reversed, inside its lines when it is outlined; a group's header row;
and **the whole tile when it is too small for any text**, so the focus
never goes unseen: such a tile is a few cells, and reversing it hides
nothing. The focus shows only while the treemap has the keyboard focus,
as a Treeview's does; `<FocusIn>` and `<FocusOut>` repaint it. The selected tile gets a `●` before its name. The readout shows
the focused item:

```text
web › nginx   330   38.82% of all   60.00% of web
```

With nothing focused, it shows the total, and how many tiles were too
small to show: `total 850 · 2 too small to show`; zoomed, it is the
group's total, `db › total 200`. A line wider than the widget is cut
with `…`, like any label.

**Tags, to act on one item**, as Treeview's: an item's `tags` is a list
or a string of names, `tag_has` answers who carries one, and
`tag_bind(tag, sequence, callback)` runs the callback only when the item
the event is for carries the tag. Which item that is depends on the
event: the tile under the pointer for a mouse event, the selected item
for `<<TreemapSelect>>`, the group zoomed into or out of for
`<<TreemapZoom>>`, and otherwise the focused item. That makes
`tag_bind("disk", "<<TreemapSelect>>", ...)` mean "when a disk is
chosen", by click or key alike. An item's tags run in its own order, as
a Treeview row's do. One widget binding per sequence carries every tag
binding, as `Treeview.tag_bind` does it. `tag_configure` is not there
yet: it would be the place for per-item colours.

### Repainting

Every item change marks the layout stale and asks for one repaint with
`after_idle`. A program updating a hundred values in a loop gets one
layout and one paint. The layout is cached by the model's version, the
widget's size and the zoom, so focus moves and selections repaint
without laying out again. Everything runs on the event loop, as
BarGraph's does. Data from a thread comes through a queue the program
drains with `after`.

The natural size is `width` 40 × `height` 12 cells, options as on a
Frame. A widget with no items, or with only zeros, shows `nothing to
show` in the middle.

### Options measured

`record_visible_options.py` names it `treemap.Treemap`. The base is two
groups and one plain item, 40 × 10, enough for headers, shades, labels
and the readout; `cache` is 1234 so the number format has a value to
scale. `WIDGET_NEEDS` gives the number options `values="value"`, since
a percentage ignores them, and `relief` a border. Measured: every
Treemap option visible but the Frame's own invisible ones. Each has a
`Sample output (option):`, run by the docs build once the reference
page includes the class.

**Making the module public brought the convention tests in at once**,
not at the docs story: `tkcurses.treemap` is in `EXTENSION_MODULES`, so
its docstring is held to the samples rule, and its options to the
measurement, from the first commit that has the widget.

### Not yet

- **"Other" grouping**, Kibana's default for top values: keep the top N
  per group and fold the rest into one tile. Left room: `_model`'s order
  is the place to cut.
- **Colour mapping**, a colour per named item. Left room: an item
  `color` option would take precedence over `colors`.
- **More than two levels.** `_squarify` and `_layout` recurse already;
  the limit is the model's, and the navigation's "level" would need to
  become a depth.

## Running Both Halves

`python -m tkcurses` is the demo, and it is the one place the library's own
claim is checked end to end: a curses window and a tkinter widget sharing a
terminal rather than taking turns with it.

`tkcurses.curses.initscr()` **attaches to a screen a Tk application already
has up** rather than starting a second one — there is one terminal — and
`endwin()` then leaves that screen alone, since the application owns it. So
what the curses half draws lands in the same cells the widgets drew into,
and one refresh paints both.

Two things make that work rather than merely not crash. `ColorManager`
passes a caller-chosen colour pair straight through when the attribute
already carries one: `A_COLOR` is a packed field, so OR-ing a second pair
into it would leave neither. And the widgets own the buffer and will draw
over anything in it, so the curses half is put back — `update_panels()` —
after every repaint.
| `show()` | ✓ | Show panel |
| `top()` | ✓ | Move to top |
| `userptr()` | ✓ | Get user data |
| `window()` | ✓ | Get window |
