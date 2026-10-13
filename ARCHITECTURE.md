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
- **Python**: 3.10+
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
6. **Write through `_Drawable._write_line`**, not `addstr` or `insstr` directly.
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

This applies to: `Toplevel`, `Frame`, `LabelFrame`, `Listbox`, `Text`, `Canvas`, dialog boxes, menus, and any widget with `borderwidth > 0` or `relief != FLAT`.

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
; tkcurses.ini - TkCurses Runtime Configuration
; Lines starting with ; or # are comments

[mouse]
; Double/triple click detection window (milliseconds)
; Range: 1-1000, Default: 200
click_interval = 200

; Enable mouse support (true/false)
enabled = true

; Report mouse motion events (true/false)
; Required for drag support, may increase CPU usage
report_motion = true

[display]
; Color mode: 8, 16, 256, or truecolor
; Use "auto" to detect terminal capability
color_mode = auto

; Enable Unicode box-drawing characters (true/false)
; Set to false for ASCII-only terminals
unicode_borders = true

; Refresh rate limit (milliseconds between refreshes)
; Lower = smoother, Higher = less CPU usage
; Range: 10-1000, Default: 16 (approximately 60 FPS)
refresh_interval = 16

[input]
; Input polling timeout (milliseconds)
; Affects responsiveness of after() callbacks
; Range: 10-500, Default: 50
poll_timeout = 50

; Enable keypad mode for special keys (true/false)
keypad = true

; Escape key delay (milliseconds)
; Time to wait for escape sequences after ESC
; Range: 0-1000, Default: 25
escape_delay = 25

[accessibility]
; High contrast mode (true/false)
high_contrast = false

; Minimum click interval for users with motor difficulties
; Overrides [mouse] click_interval if higher
min_click_interval = 0

; Screen reader compatibility mode (true/false)
screen_reader = false

[debug]
; Enable debug logging (true/false)
enabled = false

; Log file path (empty = stderr)
log_file =

; Log level: DEBUG, INFO, WARNING, ERROR
log_level = WARNING
```

### Configuration Implementation

```python
import configparser
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

@dataclass
class MouseConfig:
    """Mouse-related configuration."""
    click_interval: int = 200
    enabled: bool = True
    report_motion: bool = True

@dataclass
class DisplayConfig:
    """Display-related configuration."""
    color_mode: str = 'auto'
    unicode_borders: bool = True
    refresh_interval: int = 16

@dataclass
class InputConfig:
    """Input-related configuration."""
    poll_timeout: int = 50
    keypad: bool = True
    escape_delay: int = 25

@dataclass
class AccessibilityConfig:
    """Accessibility-related configuration."""
    high_contrast: bool = False
    min_click_interval: int = 0
    screen_reader: bool = False

@dataclass
class DebugConfig:
    """Debug-related configuration."""
    enabled: bool = False
    log_file: str = ''
    log_level: str = 'WARNING'

@dataclass
class TkCursesConfig:
    """Complete TkCurses configuration."""
    mouse: MouseConfig = field(default_factory=MouseConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    input: InputConfig = field(default_factory=InputConfig)
    accessibility: AccessibilityConfig = field(default_factory=AccessibilityConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)

    @classmethod
    def get_config_paths(cls) -> list[Path]:
        """Get configuration file paths in load order."""
        paths = []

        if sys.platform == 'win32':
            # Windows paths
            programdata = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
            localappdata = os.environ.get('LOCALAPPDATA', '')

            paths.append(Path(programdata) / 'tkcurses' / 'tkcurses.ini')
            if localappdata:
                paths.append(Path(localappdata) / 'tkcurses' / 'tkcurses.ini')
        else:
            # Unix-like paths (Linux, macOS, FreeBSD, etc.)
            paths.append(Path('/etc/tkcurses/tkcurses.ini'))

            # XDG Base Directory Specification
            config_home = os.environ.get('XDG_CONFIG_HOME', '')
            if not config_home:
                config_home = Path.home() / '.config'
            else:
                config_home = Path(config_home)

            paths.append(config_home / 'tkcurses' / 'tkcurses.ini')

        return paths

    @classmethod
    def load(cls) -> 'TkCursesConfig':
        """Load configuration from all sources."""
        config = cls()

        # Load from INI files (in order)
        parser = configparser.ConfigParser()
        config_paths = cls.get_config_paths()

        for path in config_paths:
            if path.exists():
                try:
                    parser.read(path)
                except configparser.Error:
                    pass  # Skip malformed files

        # Apply INI settings
        config._apply_parser(parser)

        # Apply environment variable overrides (highest priority)
        config._apply_env_overrides()

        return config

    def _apply_parser(self, parser: configparser.ConfigParser) -> None:
        """Apply settings from ConfigParser."""
        # Mouse settings
        if parser.has_section('mouse'):
            self.mouse.click_interval = parser.getint(
                'mouse', 'click_interval', fallback=self.mouse.click_interval
            )
            self.mouse.enabled = parser.getboolean(
                'mouse', 'enabled', fallback=self.mouse.enabled
            )
            self.mouse.report_motion = parser.getboolean(
                'mouse', 'report_motion', fallback=self.mouse.report_motion
            )

        # Display settings
        if parser.has_section('display'):
            self.display.color_mode = parser.get(
                'display', 'color_mode', fallback=self.display.color_mode
            )
            self.display.unicode_borders = parser.getboolean(
                'display', 'unicode_borders', fallback=self.display.unicode_borders
            )
            self.display.refresh_interval = parser.getint(
                'display', 'refresh_interval', fallback=self.display.refresh_interval
            )

        # Input settings
        if parser.has_section('input'):
            self.input.poll_timeout = parser.getint(
                'input', 'poll_timeout', fallback=self.input.poll_timeout
            )
            self.input.keypad = parser.getboolean(
                'input', 'keypad', fallback=self.input.keypad
            )
            self.input.escape_delay = parser.getint(
                'input', 'escape_delay', fallback=self.input.escape_delay
            )

        # Accessibility settings
        if parser.has_section('accessibility'):
            self.accessibility.high_contrast = parser.getboolean(
                'accessibility', 'high_contrast',
                fallback=self.accessibility.high_contrast
            )
            self.accessibility.min_click_interval = parser.getint(
                'accessibility', 'min_click_interval',
                fallback=self.accessibility.min_click_interval
            )
            self.accessibility.screen_reader = parser.getboolean(
                'accessibility', 'screen_reader',
                fallback=self.accessibility.screen_reader
            )

        # Debug settings
        if parser.has_section('debug'):
            self.debug.enabled = parser.getboolean(
                'debug', 'enabled', fallback=self.debug.enabled
            )
            self.debug.log_file = parser.get(
                'debug', 'log_file', fallback=self.debug.log_file
            )
            self.debug.log_level = parser.get(
                'debug', 'log_level', fallback=self.debug.log_level
            )

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_mapping = {
            'TKCURSES_MOUSE_CLICK_INTERVAL': ('mouse', 'click_interval', int),
            'TKCURSES_MOUSE_ENABLED': ('mouse', 'enabled', self._parse_bool),
            'TKCURSES_DISPLAY_COLOR_MODE': ('display', 'color_mode', str),
            'TKCURSES_DISPLAY_UNICODE': ('display', 'unicode_borders', self._parse_bool),
            'TKCURSES_INPUT_POLL_TIMEOUT': ('input', 'poll_timeout', int),
            'TKCURSES_INPUT_ESCAPE_DELAY': ('input', 'escape_delay', int),
            'TKCURSES_ACCESSIBILITY_HIGH_CONTRAST': ('accessibility', 'high_contrast', self._parse_bool),
            'TKCURSES_DEBUG': ('debug', 'enabled', self._parse_bool),
            'TKCURSES_DEBUG_LOG_FILE': ('debug', 'log_file', str),
            'TKCURSES_DEBUG_LOG_LEVEL': ('debug', 'log_level', str),
        }

        for env_var, (section, key, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    section_obj = getattr(self, section)
                    setattr(section_obj, key, converter(value))
                except (ValueError, AttributeError):
                    pass  # Skip invalid values

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean from string."""
        return value.lower() in ('true', '1', 'yes', 'on')

    def apply(self, app: 'Tk') -> None:
        """Apply configuration to a Tk application instance."""
        # Apply mouse settings
        if self.mouse.enabled:
            app.configure_mouse(click_interval=max(
                self.mouse.click_interval,
                self.accessibility.min_click_interval
            ))

        # Apply other settings as needed...
```

### Environment Variables Reference

| Variable | INI Equivalent | Type | Description |
|----------|----------------|------|-------------|
| `TKCURSES_MOUSE_CLICK_INTERVAL` | `[mouse] click_interval` | int | Double-click timing (ms) |
| `TKCURSES_MOUSE_ENABLED` | `[mouse] enabled` | bool | Enable mouse support |
| `TKCURSES_DISPLAY_COLOR_MODE` | `[display] color_mode` | str | Color mode |
| `TKCURSES_DISPLAY_UNICODE` | `[display] unicode_borders` | bool | Unicode borders |
| `TKCURSES_INPUT_POLL_TIMEOUT` | `[input] poll_timeout` | int | Input poll timeout (ms) |
| `TKCURSES_INPUT_ESCAPE_DELAY` | `[input] escape_delay` | int | ESC sequence delay (ms) |
| `TKCURSES_ACCESSIBILITY_HIGH_CONTRAST` | `[accessibility] high_contrast` | bool | High contrast mode |
| `TKCURSES_DEBUG` | `[debug] enabled` | bool | Enable debug logging |
| `TKCURSES_DEBUG_LOG_FILE` | `[debug] log_file` | str | Debug log file path |
| `TKCURSES_DEBUG_LOG_LEVEL` | `[debug] log_level` | str | Log level |

### Usage Examples

```bash
# Temporary override for testing
$ TKCURSES_MOUSE_CLICK_INTERVAL=400 python my_app.py

# Enable debug logging
$ TKCURSES_DEBUG=true TKCURSES_DEBUG_LOG_LEVEL=DEBUG python my_app.py

# Create user config for accessibility
$ mkdir -p ~/.config/tkcurses
$ cat > ~/.config/tkcurses/tkcurses.ini << 'EOF'
[mouse]
click_interval = 350

[accessibility]
high_contrast = true
min_click_interval = 300
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
a signal of it. `mainloop()` catches the `KeyboardInterrupt` around one pass
of the loop and calls `_close_requested()`, which invokes the protocol
handler if there is one and calls `destroy()` if there is not.

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
`<<PasteSelection>>` the middle button's release; `<<Clear>>` nothing.
`event_info("<<Copy>>")` therefore differs from Tk's, which also lists
Control-c, F16 and Meta-w.

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

The clipboard is still the process's own: what is copied here does not reach
other applications. That is `TkCurses-hpr`, the OSC 52 transport.

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

**Combobox is left out.** It installs its own class bindings, and every click
on it opens the list. In Tk an editable combobox's text takes these clicks as
an entry would, and only the arrow or a read-only one opens it — which would
change a click UAT 34 accepted, so it is its own issue.

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
4. **Widget methods are thread-safe** - internally dispatch to main thread

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
is how the gap survived long enough to be found by accident. The same failure
mode as the code graph that sat 165 commits stale while still being advertised
as the way to navigate the library (see CLAUDE.md).

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
| `deletecommand(name)` | ○ | Remove callback (no Tcl, internal registry) |
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
| `winfo_name()` | ✓ | Widget name |
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
| `winfo_screen()` | ✗ | N/A (no X11 screen) |
| `winfo_screencells()` | ✗ | N/A |
| `winfo_screendepth()` | ○ | Simulated depth |
| `winfo_screenmmheight()` | ✗ | N/A (no physical size) |
| `winfo_screenmmwidth()` | ✗ | N/A |
| `winfo_screenvisual()` | ✗ | N/A |
| `winfo_server()` | ✗ | N/A |
| `winfo_visual()` | ✗ | N/A |
| `winfo_visualid()` | ✗ | N/A |
| `winfo_vrootheight()` | ○ | Virtual screen cells |
| `winfo_vrootwidth()` | ○ | Virtual screen cells |
| **Event Loop** | | |
| `update()` | ✓ | Process pending events |
| `update_idletasks()` | ✓ | Process idle callbacks |
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
| `getvar(name)` | ✓ | Get Variable value (internal storage) |
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

`bgimg` is the one synonym not offered, because `-backgroundimage` does not
exist here yet (`TkCurses-yi4`); a synonym for a missing option would only
raise with a more confusing message.

So the underscore is stripped on the keyword path only, in `_keyword_option`,
and `cget` resolves synonyms alone. Widgets with a range — `Scale`, `Spinbox`,
`ttk.Scale`, `ttk.Spinbox` — store `from`. `ttk.Progressbar` and
`ttk.LabeledScale` have no such option in either library, which corrects the
issue's own list of what needed renaming.

The remaining half of this is `TkCurses-bv0`: tkinter's key set contains both
`bg` and `background`, and ours only the long one. The values are right and
`cget` takes either; it is `configure()`'s reported keys that are short.
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
| `image_types()` | ○ | `bitmap` and `photo` |
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
- **`configure()` with no arguments** returns the current option values.
  tkinter returns a five-tuple per option carrying its resource name, class and
  default; those come from Tcl's widget definitions.
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
- **Clipboard contents do not leave the process.** A terminal has no clipboard;
  `CLIPBOARD` and `PRIMARY` are strings held in the `Application`. Escape-
  sequence clipboard access (OSC 52) is not attempted, because it is
  unsupported by many terminals and fails silently on the rest.
- **Multi-event sequences** (`<Control-x><Control-s>`) are rejected by the
  sequence parser rather than silently mis-parsed.

---

### Wm Class

Window manager interface for toplevel windows.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `wm_aspect(minN, minD, maxN, maxD)` | ✗ | N/A (fixed cells) |
| `wm_attributes(*args, **kwargs)` | ◐ | Limited attributes |
| `wm_client(name=None)` | ✗ | N/A |
| `wm_colormapwindows(*wlist)` | ✗ | N/A |
| `wm_command(value=None)` | ✗ | N/A |
| `wm_deiconify()` | ○ | Show window |
| `wm_focusmodel(model=None)` | ○ | Focus behavior |
| `wm_forget(window)` | ✓ | Remove from WM |
| `wm_frame()` | ○ | Returns self |
| `wm_geometry(newGeometry=None)` | ○ | Cell geometry "WxH+X+Y" (see below) |
| `wm_grid(baseW, baseH, wInc, hInc)` | ○ | Cell grid sizing |
| `wm_group(pathName=None)` | ✗ | N/A |
| `wm_iconbitmap(bitmap, default)` | ✗ | N/A (no icons) |
| `wm_iconify()` | ○ | Hide window |
| `wm_iconmask(bitmap=None)` | ✗ | N/A |
| `wm_iconname(newName=None)` | ✗ | N/A |
| `wm_iconphoto(default, *args)` | ✗ | N/A |
| `wm_iconposition(x=None, y=None)` | ✗ | N/A |
| `wm_iconwindow(pathName=None)` | ✗ | N/A |
| `wm_manage(widget)` | ○ | Manage as toplevel |
| `wm_maxsize(width, height)` | ○ | Max cell size |
| `wm_minsize(width, height)` | ○ | Min cell size |
| `wm_overrideredirect(boolean)` | ○ | Borderless mode |
| `wm_positionfrom(who=None)` | ✗ | N/A |
| `wm_protocol(name, func)` | ✓ | Protocol handlers |
| `wm_resizable(width, height)` | ○ | Resize enable |
| `wm_sizefrom(who=None)` | ✗ | N/A |
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

> **Note:** Aliases are only provided for methods that are implemented in TkCurses. Methods marked ✗ (N/A) in the table above do not have aliases

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
| `loadtk()` | ☐ | No-op (curses already initialized) - not implemented; TkCurses-5rt |
| `readprofile(baseName, className)` | ✗ | N/A |
| `report_callback_exception(exc, val, tb)` | ✓ | Exception handler |

Inherits all methods from `Misc` and `Wm`.

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
| `bitmap` | bitmap | ✗ N/A (the built-in named bitmaps) |
| `compound` | position | none/left/right/top/bottom/center |
| `width` | chars | Cells |
| `height` | lines | Cells |
| `padx` | pixels | Cells |
| `pady` | pixels | Cells |

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
| `scan_mark(x)` | ☐ | Scan start - not implemented; TkCurses-6lh |
| `scan_dragto(x)` | ☐ | Scan drag - not implemented; TkCurses-6lh |
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
| `insertwidth` | pixels | 1 cell (cursor) |
| `exportselection` | puts the selection on PRIMARY | Same, against the in-process PRIMARY |
| `placeholder` | ghost text in an empty field | Same |
| `placeholderforeground` | its colour | Honoured; **dim** when unset (see below) |
| `highlightthickness` | focus ring, pixels | No ring; a focused entry draws its **border** bold |
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

The data still does not leave the process — that is `TkCurses-hpr`, OSC 52 — but
the per-widget option is meaningful without it, and `TkCurses-9e8` carries
`Listbox` and `Text`, whose selection models differ. `TkCurses-163`.

**A focused entry shows it in its border, in every state.** Tk signals the
focus on an entry two ways: the insertion cursor, and the
`-highlightthickness` ring. Only the first depends on the state — Tk's manual
says `readonly` draws "no insertion cursor ... even if the input focus is in the
widget" — so in Tk a locked field is still visibly focused, by its ring. This
library drops `highlightthickness` as an X11 option with no cell equivalent, and
for a while had nothing in its place: copying Tk's cursor rule faithfully left a
focused readonly entry indistinguishable from an unfocused one. `BorderStyle.attr`
carries it now, and `relief="flat"` still draws nothing, which matches a Tk ring
of zero thickness. Reported from UAT 41; the cursor half is pinned by its own
test so the two cannot be confused again.

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

---

### Text Class

Multi-line text editor.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Scrollable text area |
| `bbox(index)` | ○ | Cell bounding box |
| `compare(index1, op, index2)` | ✓ | Compare indices |
| `count(index1, index2, *options)` | ☐ | Count items - not implemented; TkCurses-mzj |
| `debug(boolean=None)` | ✗ | N/A |
| `delete(index1, index2=None)` | ✓ | Delete text |
| `dlineinfo(index)` | ○ | Display line info |
| `dump(index1, index2, command, **kw)` | ☐ | Dump contents - not implemented; TkCurses-mzj |
| `edit_modified(arg=None)` | ✓ | Modified flag |
| `edit_redo()` | ✓ | Redo edit |
| `edit_reset()` | ✓ | Clear undo stack |
| `edit_separator()` | ✓ | Undo separator |
| `edit_undo()` | ✓ | Undo edit |
| `get(index1, index2=None)` | ✓ | Get text |
| `image_cget(index, option)` | ✗ | N/A |
| `image_configure(index, **kw)` | ✗ | N/A |
| `image_create(index, **kw)` | ✗ | N/A |
| `image_names()` | ✗ | N/A |
| `index(index)` | ✓ | Parse index |
| `insert(index, chars, *args)` | ✓ | Insert text |
| `mark_gravity(markName, direction)` | ✓ | Mark gravity |
| `mark_names()` | ✓ | List marks |
| `mark_set(markName, index)` | ✓ | Set mark |
| `mark_unset(*markNames)` | ✓ | Delete marks |
| `mark_next(index)` | ✓ | Next mark |
| `mark_previous(index)` | ✓ | Previous mark |
| `peer_create(newPathName, **kw)` | ✗ | N/A |
| `peer_names()` | ✗ | N/A |
| `replace(index1, index2, chars)` | ☐ | Replace text - not implemented; TkCurses-mzj |
| `scan_mark(x, y)` | ☐ | Scan start - not implemented; TkCurses-6lh |
| `scan_dragto(x, y)` | ☐ | Scan drag - not implemented; TkCurses-6lh |
| `search(pattern, index, **kw)` | ✓ | Find text |
| `see(index)` | ○ | Scroll to index |
| `tag_add(tagName, index1, *args)` | ✓ | Add tag |
| `tag_unbind(tagName, sequence, funcid)` | ☐ | Unbind tag - not implemented; TkCurses-mzj |
| `tag_bind(tagName, sequence, func)` | ☐ | Bind tag event - not implemented; TkCurses-mzj |
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
| `window_cget(index, option)` | ☐ | Embedded widget - not implemented; TkCurses-mzj |
| `window_configure(index, **kw)` | ☐ | Configure widget - not implemented; TkCurses-mzj |
| `window_create(index, **kw)` | ☐ | Embed widget - not implemented; TkCurses-mzj |
| `window_names()` | ☐ | List widgets - not implemented; TkCurses-mzj |

**A disabled Text refuses edits from code too** (`TkCurses-aah`), as the
manual says: "no insertions or deletions are allowed". Measured on Tk 9.0.2,
`insert` and `delete` are ignored **silently**: nothing is raised and the
modified flag does not move. Tags, marks and the selection still change. (Tk's
`image_create` and `window_create` still embed while disabled; neither is
implemented here yet, `TkCurses-mzj`.) Ours used to accept both edits from
code, and a test asserted it, unmeasured. Fill a read-only display with
tkinter's idiom: `state="normal"`, insert, `state="disabled"`.

**Undo while disabled departs from Tk, deliberately.** Tk's disabled
`edit_undo` changes nothing in the text but still pops the undo group, so the
history stops describing the text: re-enable and redo, and `hello world`
became `hello world world`. Here a disabled undo or redo moves nothing, the
stack included. An empty stack still raises `nothing to undo`, as Tk's does
whatever the state.

---

### Listbox Class

Scrollable selection list.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Text list with box |
| `activate(index)` | ○ | Highlight item |
| `bbox(index)` | ○ | Cell bounding box |
| `curselection()` | ✓ | Selected indices |
| `delete(first, last=None)` | ✓ | Delete items |
| `get(first, last=None)` | ✓ | Get items |
| `index(index)` | ✓ | Parse index |
| `insert(index, *elements)` | ✓ | Insert items |
| `nearest(y)` | ○ | Nearest cell row |
| `scan_mark(x, y)` | ☐ | Scan start - not implemented; TkCurses-6lh |
| `scan_dragto(x, y)` | ☐ | Scan drag - not implemented; TkCurses-6lh |
| `see(index)` | ○ | Scroll to item |
| `selection_anchor(index)` | ✓ | Set anchor |
| `selection_clear(first, last=None)` | ✓ | Clear selection |
| `selection_includes(index)` | ✓ | Check selection |
| `selection_set(first, last=None)` | ✓ | Set selection |
| `size()` | ✓ | Item count |
| `itemcget(index, option)` | ☐ | Get item option - not implemented; TkCurses-5kg |
| `itemconfigure(index, **kw)` | ☐ | Configure item - not implemented; TkCurses-5kg |

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

---

### Scrollbar Class

Scroll control widget.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | `▲█░░▼` display |
| `activate(element=None)` | ☐ | Highlight element - not implemented; TkCurses-5rt |
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
| `xposition(index)` | ☐ | Cell X position - not implemented; TkCurses-5rt |
| `yposition(index)` | ○ | Cell Y position |

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
| `addtag(tag, method, *args)` | ☐ | Add tag - not implemented; TkCurses-7jv |
| `addtag_above(newtag, tagOrId)` | ☐ | Tag above - not implemented; TkCurses-7jv |
| `addtag_all(newtag)` | ☐ | Tag all - not implemented; TkCurses-7jv |
| `addtag_below(newtag, tagOrId)` | ☐ | Tag below - not implemented; TkCurses-7jv |
| `addtag_closest(newtag, x, y)` | ☐ | Tag closest, in pixels - not implemented; TkCurses-7jv |
| `addtag_enclosed(newtag, x1, y1, x2, y2)` | ☐ | Tag enclosed - not implemented; TkCurses-7jv |
| `addtag_overlapping(newtag, x1, y1, x2, y2)` | ☐ | Tag overlapping - not implemented; TkCurses-7jv |
| `addtag_withtag(newtag, tagOrId)` | ✓ | Tag with tag |
| `bbox(tagOrId=None)` | ○ | Bounding box, in pixels |
| `canvasx(screenx)` | ○ | Screen column to canvas pixel |
| `canvasy(screeny)` | ○ | Screen row to canvas pixel (its upper half) |
| `coords(tagOrId, *args)` | ○ | Get/set coords, in pixels |
| `create_arc(...)` | ✗ | N/A (TkCurses-aj1.16.1) |
| `create_bitmap(...)` | ✗ | Likewise (TkCurses-aj1.16.1) |
| `create_image(...)` | ✗ | Possible now the planes match (TkCurses-aj1.16.1) |
| `create_line(...)` | ○ | Rasterised to pixels |
| `create_oval(...)` | ○ | Rasterised; round, not elliptical |
| `create_polygon(...)` | ○ | Rasterised to pixels |
| `create_rectangle(...)` | ○ | Rasterised to pixels |
| `create_text(...)` | ○ | Snaps to a cell row; a glyph is a whole cell |
| `create_window(...)` | ✗ | N/A (TkCurses-aj1.16.1) |
| `dchars(tagOrId, first, last=None)` | ☐ | Delete chars - not implemented; TkCurses-7jv |
| `delete(tagOrId)` | ✓ | Delete item |
| `dtag(tagOrId, tagToDelete=None)` | ✓ | Remove tag |
| `find(method, *args)` | ☐ | Find items - not implemented; TkCurses-7jv |
| `find_above(tagOrId)` | ☐ | Find above - not implemented; TkCurses-7jv |
| `find_all()` | ✓ | Find all |
| `find_below(tagOrId)` | ☐ | Find below - not implemented; TkCurses-7jv |
| `find_closest(x, y)` | ○ | Find at cell |
| `find_enclosed(x1, y1, x2, y2)` | ☐ | Find enclosed - not implemented; TkCurses-7jv |
| `find_overlapping(x1, y1, x2, y2)` | ○ | Find overlapping |
| `find_withtag(tagOrId)` | ✓ | Find with tag |
| `focus(tagOrId=None)` | ✓ | Set/get focus |
| `gettags(tagOrId)` | ✓ | Get tags |
| `icursor(tagOrId, index)` | ☐ | Cursor position - not implemented; TkCurses-7jv |
| `index(tagOrId, index)` | ☐ | Parse index - not implemented; TkCurses-7jv |
| `insert(tagOrId, index, string)` | ☐ | Insert text - not implemented; TkCurses-7jv |
| `itemcget(tagOrId, option)` | ✓ | Get option |
| `itemconfigure(tagOrId, **kw)` | ○ | Configure (limited) |
| `move(tagOrId, dx, dy)` | ○ | Move by cells |
| `moveto(tagOrId, x, y)` | ☐ | Move to cell - not implemented; TkCurses-7jv |
| `postscript(**kw)` | ✗ | N/A |
| `scale(tagOrId, xo, yo, xs, ys)` | ✗ | N/A (fixed cells) |
| `select_*()` | ✓ | Selection methods |
| `tag_bind(tagOrId, sequence, func)` | ✓ | Bind event |
| `tag_unbind(tagOrId, sequence, funcid)` | ✓ | Unbind event |
| `tag_lower(tagOrId, belowThis)` | ✓ | Lower item |
| `tag_raise(tagOrId, aboveThis)` | ✓ | Raise item |
| `type(tagOrId)` | ✓ | Get item type |

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
| `proxy_coord()` | ☐ | Proxy cell coords - not implemented; TkCurses-xy2 |
| `proxy_forget()` | ☐ | Hide proxy - not implemented; TkCurses-xy2 |
| `proxy_place(x, y)` | ☐ | Place proxy - not implemented; TkCurses-xy2 |
| `sash_coord(index)` | ○ | Sash cell coords |
| `sash_mark(index)` | ☐ | Mark sash - not implemented; TkCurses-xy2 |
| `sash_place(index, x, y)` | ○ | Place sash |
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

---

### Message Class

Multi-line text display.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Word-wrapped text |

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

| Format | Read | Notes |
|--------|------|-------|
| PNG | ○ | 8-bit, interlaced or not: grey, RGB, palette, either with alpha |
| GIF | ○ | 87a and 89a, first frame, interlacing undone |
| PGM / PPM | ○ | P1-P6, any maxval, comments anywhere in the header |
| XBM | ○ | Via BitmapImage, as in tkinter |

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
| `copy(...)` | ○ | Independent copy |
| `zoom(...)` | ○ | Repeats each pixel |
| `subsample(...)` | ○ | Keeps every n-th pixel, as Tk does |
| `reduce(...)` | ○ | Averages each block; what fitting wants |
| `dither(...)` | ○ | Error diffusion. A tool, not a default — see below |
| `get(x, y)` | ○ | The pixel's colour |
| `put(data, to)` | ○ | A colour, or rows of them; `to` places or tiles |
| `read(filename, ...)` | ○ | A text file of art |
| `write(filename, ...)` | ○ | Likewise |
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
Its `identify_element` still answers `""` (`TkCurses-at9`).

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
| `dos` | DOS/CP437 box characters |
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
| `identify_element(x, y)` | ✗ | Always `""`; the item and heading elements are not measured yet (TkCurses-at9) |
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

**Hit-testing rests on one column model, and on the tree not scrolling
sideways.** `_column_spans()` answers where every column sits, in cells, and
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

The spans carry no scroll offset **because a tree here never scrolls
sideways** — see `xview`. That is an invariant the whole family rests on:
adding horizontal scrolling means every answer needs the view subtracted from
it.

Three answers differ from Tk deliberately:

- **`identify_region` never returns `separator`.** Tk's separator is the
  draggable gap between column headings; this widget draws none and offers no
  such drag, so returning it would name something that is not there.
- **`identify_element` always returns `""`.** Tk answers a themed element name
  from the item and heading layouts, and documents no fixed set of values —
  `'padding'` on one machine's default theme. The other ttk widgets now answer
  the default theme's element names (see ttk.Widget), but a tree's item and
  heading elements have not been measured yet (`TkCurses-at9`). Present and
  empty so the dispatcher has something to call.
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
| `newpad(nlines, ncols)` | ☐ | Create pad - not implemented; TkCurses-8iv |
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
| `overlay(destwin, ...)` | ☐ | Non-destructive copy - not implemented; TkCurses-8iv |
| `overwrite(destwin, ...)` | ☐ | Destructive copy - not implemented; TkCurses-8iv |
| `syncup()` | ✓ | Sync to parent |
| `syncdown()` | ✓ | Sync from parent |
| `syncok(flag)` | ✓ | Auto sync |
| `cursyncup()` | ✓ | Sync cursor |
| `putwin(file)` | ☐ | Save window - not implemented; TkCurses-8iv |
| `enclose(y, x)` | ✓ | Check enclosed |
| `encoding` | ☐ | Character encoding - not implemented; TkCurses-8iv |

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
