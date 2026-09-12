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

## Data Flow

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

### X11 to Curses Color Mapping

TkCurses translates tkinter's X11 color names to curses color constants. The ColorManager handles this mapping and creates curses color pairs.

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

Common tkinter colors mapped to nearest curses equivalent:

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

#### Hex Color Conversion

Hex colors (`#RRGGBB`) are converted to nearest 8-color match:

```python
def hex_to_curses(hex_color: str) -> tuple[int, int]:
    """Convert #RRGGBB to (curses_color, attribute)."""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)

    # Determine brightness
    brightness = (r + g + b) / 3
    attr = A_BOLD if brightness > 170 else (A_DIM if brightness < 85 else A_NORMAL)

    # Find dominant channel(s)
    if r > 200 and g < 100 and b < 100: return COLOR_RED, attr
    if r < 100 and g > 200 and b < 100: return COLOR_GREEN, attr
    if r < 100 and g < 100 and b > 200: return COLOR_BLUE, attr
    if r > 200 and g > 200 and b < 100: return COLOR_YELLOW, attr
    if r > 200 and g < 100 and b > 200: return COLOR_MAGENTA, attr
    if r < 100 and g > 200 and b > 200: return COLOR_CYAN, attr
    if brightness > 200: return COLOR_WHITE, attr
    if brightness < 50: return COLOR_BLACK, attr
    return COLOR_WHITE, A_DIM  # gray fallback
```

#### Color Pair Management

Curses requires pre-initialized color pairs. ColorManager maintains a dynamic pair registry:

```python
class ColorManager:
    _pairs: dict[tuple[int, int], int]  # (fg, bg) -> pair_number
    _next_pair: int = 1                  # pair 0 is reserved

    def get_pair(self, fg: int, bg: int) -> int:
        """Get or create color pair for fg/bg combination."""
        key = (fg, bg)
        if key not in self._pairs:
            curses.init_pair(self._next_pair, fg, bg)
            self._pairs[key] = self._next_pair
            self._next_pair += 1
        return curses.color_pair(self._pairs[key])
```

#### 256-Color Support (Future)

When `curses.COLORS >= 256`, extended colors can be used:

| Range | Description |
|-------|-------------|
| 0-7 | Standard colors |
| 8-15 | Bright/bold colors |
| 16-231 | 6×6×6 RGB color cube |
| 232-255 | Grayscale (24 shades) |

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
2. **Text rendering only**: No actual graphical elements (images render as ASCII art or placeholders)
3. **Single root window**: One TkCurses app per process (curses limitation)
4. **Character cell precision**: Sub-cell positioning not supported

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

### Planned Extensions
1. **Theme system**: Multiple text-mode themes (DOS, Unicode, minimal)
2. **Mouse support**: Full mouse event handling (hover, drag, scroll)
3. **Clipboard**: Copy/paste integration
4. **Async/await**: Integration with asyncio event loop

### Potential Enhancements
1. **Unicode box drawing**: Full Unicode support for borders/lines
2. **256-color/truecolor**: Extended color palette support
3. **Image-to-ASCII**: Convert images to character art for Canvas
4. **Screen recording**: Export UI state as text files

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
| `image_names()` | ◐ | List images (ASCII only) |
| `image_types()` | ◐ | Supported types (ASCII) |
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
  one that was asked for. With eight colours to choose from, echoing the
  request back would hide the approximation.
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
| `padx` | pixels | Cells |
| `pady` | pixels | Cells |
| `ipadx` | pixels | Cells |
| `ipady` | pixels | Cells |

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
| `padx` | pixels | Cells |
| `pady` | pixels | Cells |
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
| `loadtk()` | ○ | No-op (curses already initialized) |
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
| `image` | PhotoImage | ✗ N/A |
| `bitmap` | bitmap | ✗ N/A |
| `compound` | position | ✗ N/A |
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
| `scan_mark(x)` | ○ | Scan start |
| `scan_dragto(x)` | ○ | Scan drag |
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

**Configuration Options:**

| Option | tkinter | TkCurses |
|--------|---------|----------|
| `width` | chars | Cells |
| `textvariable` | Variable | Same |
| `show` | char | Password mask |
| `state` | NORMAL/DISABLED/READONLY | Same |
| `justify` | LEFT/CENTER/RIGHT | Text alignment |
| `insertwidth` | pixels | 1 cell (cursor) |

---

### Text Class

Multi-line text editor.

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Scrollable text area |
| `bbox(index)` | ○ | Cell bounding box |
| `compare(index1, op, index2)` | ✓ | Compare indices |
| `count(index1, index2, *options)` | ✓ | Count items |
| `debug(boolean=None)` | ✗ | N/A |
| `delete(index1, index2=None)` | ✓ | Delete text |
| `dlineinfo(index)` | ○ | Display line info |
| `dump(index1, index2, command, **kw)` | ✓ | Dump contents |
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
| `replace(index1, index2, chars)` | ✓ | Replace text |
| `scan_mark(x, y)` | ○ | Scan start |
| `scan_dragto(x, y)` | ○ | Scan drag |
| `search(pattern, index, **kw)` | ✓ | Find text |
| `search_all(pattern, index, **kw)` | ✓ | Find all |
| `see(index)` | ○ | Scroll to index |
| `tag_add(tagName, index1, *args)` | ✓ | Add tag |
| `tag_unbind(tagName, sequence, funcid)` | ✓ | Unbind tag |
| `tag_bind(tagName, sequence, func)` | ✓ | Bind tag event |
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
| `window_cget(index, option)` | ◐ | Embedded widget |
| `window_configure(index, **kw)` | ◐ | Configure widget |
| `window_create(index, **kw)` | ◐ | Embed widget |
| `window_names()` | ◐ | List widgets |

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
| `scan_mark(x, y)` | ○ | Scan start |
| `scan_dragto(x, y)` | ○ | Scan drag |
| `see(index)` | ○ | Scroll to item |
| `selection_anchor(index)` | ✓ | Set anchor |
| `selection_clear(first, last=None)` | ✓ | Clear selection |
| `selection_includes(index)` | ✓ | Check selection |
| `selection_set(first, last=None)` | ✓ | Set selection |
| `size()` | ✓ | Item count |
| `itemcget(index, option)` | ○ | Get item option |
| `itemconfigure(index, **kw)` | ○ | Configure item |

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
| `activate(element=None)` | ○ | Highlight element |
| `delta(deltax, deltay)` | ○ | Calculate delta |
| `fraction(x, y)` | ○ | Position fraction |
| `identify(x, y)` | ○ | Element at cell |
| `get()` | ✓ | Get scroll position |
| `set(first, last)` | ○ | Set scroll position |

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
| `bbox(index)` | ○ | Cell bounding box |
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
| `xposition(index)` | ○ | Cell X position |
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

### Canvas Class

Drawing surface (ASCII art).

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, cnf={}, **kw)` | ○ | Character canvas |
| `addtag(tag, method, *args)` | ✓ | Add tag |
| `addtag_above(newtag, tagOrId)` | ✓ | Tag above |
| `addtag_all(newtag)` | ✓ | Tag all |
| `addtag_below(newtag, tagOrId)` | ✓ | Tag below |
| `addtag_closest(newtag, x, y)` | ○ | Tag closest cell |
| `addtag_enclosed(newtag, x1, y1, x2, y2)` | ○ | Tag enclosed |
| `addtag_overlapping(newtag, x1, y1, x2, y2)` | ○ | Tag overlapping |
| `addtag_withtag(newtag, tagOrId)` | ✓ | Tag with tag |
| `bbox(tagOrId=None)` | ○ | Cell bounding box |
| `canvasx(screenx)` | ○ | Screen to canvas cell |
| `canvasy(screeny)` | ○ | Screen to canvas cell |
| `coords(tagOrId, *args)` | ○ | Get/set cell coords |
| `create_arc(...)` | ○ | ASCII arc |
| `create_bitmap(...)` | ✗ | N/A |
| `create_image(...)` | ✗ | N/A (ASCII art only) |
| `create_line(...)` | ○ | Line with `─│╱╲` |
| `create_oval(...)` | ○ | ASCII oval |
| `create_polygon(...)` | ○ | ASCII polygon |
| `create_rectangle(...)` | ○ | Box drawing chars |
| `create_text(...)` | ○ | Text at cells |
| `create_window(...)` | ○ | Embed widget |
| `dchars(tagOrId, first, last=None)` | ✓ | Delete chars |
| `delete(tagOrId)` | ✓ | Delete item |
| `dtag(tagOrId, tagToDelete=None)` | ✓ | Remove tag |
| `find(method, *args)` | ○ | Find items |
| `find_above(tagOrId)` | ✓ | Find above |
| `find_all()` | ✓ | Find all |
| `find_below(tagOrId)` | ✓ | Find below |
| `find_closest(x, y)` | ○ | Find at cell |
| `find_enclosed(x1, y1, x2, y2)` | ○ | Find enclosed |
| `find_overlapping(x1, y1, x2, y2)` | ○ | Find overlapping |
| `find_withtag(tagOrId)` | ✓ | Find with tag |
| `focus(tagOrId=None)` | ✓ | Set/get focus |
| `gettags(tagOrId)` | ✓ | Get tags |
| `icursor(tagOrId, index)` | ○ | Cursor position |
| `index(tagOrId, index)` | ✓ | Parse index |
| `insert(tagOrId, index, string)` | ✓ | Insert text |
| `itemcget(tagOrId, option)` | ✓ | Get option |
| `itemconfigure(tagOrId, **kw)` | ○ | Configure (limited) |
| `move(tagOrId, dx, dy)` | ○ | Move by cells |
| `moveto(tagOrId, x, y)` | ○ | Move to cell |
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
| `proxy_coord()` | ○ | Proxy cell coords |
| `proxy_forget()` | ✓ | Hide proxy |
| `proxy_place(x, y)` | ○ | Place proxy |
| `sash_coord(index)` | ○ | Sash cell coords |
| `sash_mark(index)` | ○ | Mark sash |
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

### PhotoImage Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(name, cnf, master, **kw)` | ◐ | ASCII art storage |
| `blank()` | ◐ | Clear image |
| `cget(option)` | ◐ | Get option |
| `copy(...)` | ✗ | N/A |
| `zoom(...)` | ✗ | N/A |
| `subsample(...)` | ✗ | N/A |
| `get(x, y)` | ✗ | N/A |
| `put(data, to)` | ◐ | Put ASCII chars |
| `read(filename, ...)` | ✗ | N/A |
| `write(filename, ...)` | ✗ | N/A |
| `transparency_get(x, y)` | ✗ | N/A |
| `transparency_set(x, y, bool)` | ✗ | N/A |

### BitmapImage Class

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(name, cnf, master, **kw)` | ✗ | N/A |

---

## TTK Widget Classes

### ttk.Widget Base

All TTK widgets inherit from this base with additional styling.

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

### ttk.Combobox

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Dropdown entry |
| `current(newindex=None)` | ✓ | Get/set index |
| `set(value)` | ✓ | Set value |

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

### ttk.Notebook

| tkinter Method | TkCurses | Notes |
|----------------|----------|-------|
| `__init__(master=None, **kw)` | ○ | Tabbed container |
| `add(child, **kw)` | ✓ | Add tab |
| `forget(tab_id)` | ✓ | Remove tab |
| `hide(tab_id)` | ✓ | Hide tab |
| `identify(x, y)` | ○ | Identify at cell |
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
| `bbox(item, column)` | ○ | Cell bounding box |
| `get_children(item=None)` | ✓ | Get children |
| `set_children(item, *children)` | ✓ | Set children |
| `column(column, option, **kw)` | ○ | Column config |
| `delete(*items)` | ✓ | Delete items |
| `detach(*items)` | ✓ | Detach items |
| `exists(item)` | ✓ | Item exists |
| `focus(item=None)` | ✓ | Focus item |
| `heading(column, option, **kw)` | ○ | Heading config |
| `identify(component, x, y)` | ○ | Identify at cell |
| `identify_row(y)` | ○ | Row at cell |
| `identify_column(x)` | ○ | Column at cell |
| `identify_region(x, y)` | ○ | Region at cell |
| `identify_element(x, y)` | ○ | Element at cell |
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
| `tag_bind(tagname, sequence, callback)` | ✓ | Bind tag event |
| `tag_configure(tagname, option, **kw)` | ○ | Tag attributes |
| `tag_has(tagname, item)` | ✓ | Check tag |

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

`tkcurses.curses` provides a curses-compatible API.

### Module Functions

| curses Function | TkCurses | Notes |
|-----------------|----------|-------|
| `initscr()` | ✓ | Initialize, return stdscr |
| `endwin()` | ✓ | End curses mode |
| `isendwin()` | ✓ | Check if ended |
| `wrapper(func, *args, **kwargs)` | ✓ | Safe wrapper |
| `newwin(nlines, ncols, begin_y, begin_x)` | ✓ | Create window |
| `newpad(nlines, ncols)` | ✓ | Create pad |
| `start_color()` | ✓ | Initialize colors |
| `init_pair(pair, fg, bg)` | ✓ | Define color pair |
| `init_color(color, r, g, b)` | ✓ | Define color |
| `color_pair(n)` | ✓ | Get pair attribute |
| `pair_number(attr)` | ✓ | Get pair number |
| `pair_content(pair)` | ✓ | Get pair colors |
| `color_content(color)` | ✓ | Get color RGB |
| `has_colors()` | ✓ | Always True |
| `can_change_color()` | ✓ | Always True |
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
| `overlay(destwin, ...)` | ✓ | Non-destructive copy |
| `overwrite(destwin, ...)` | ✓ | Destructive copy |
| `syncup()` | ✓ | Sync to parent |
| `syncdown()` | ✓ | Sync from parent |
| `syncok(flag)` | ✓ | Auto sync |
| `cursyncup()` | ✓ | Sync cursor |
| `putwin(file)` | ✓ | Save window |
| `enclose(y, x)` | ✓ | Check enclosed |
| `encoding` | ✓ | Character encoding |

### Constants

All curses constants are available:
- Attributes: `A_NORMAL`, `A_STANDOUT`, `A_UNDERLINE`, `A_REVERSE`, `A_BLINK`, `A_DIM`, `A_BOLD`, `A_PROTECT`, `A_INVIS`, `A_ALTCHARSET`, `A_ITALIC`
- Colors: `COLOR_BLACK`, `COLOR_RED`, `COLOR_GREEN`, `COLOR_YELLOW`, `COLOR_BLUE`, `COLOR_MAGENTA`, `COLOR_CYAN`, `COLOR_WHITE`
- Keys: `KEY_UP`, `KEY_DOWN`, `KEY_LEFT`, `KEY_RIGHT`, `KEY_HOME`, `KEY_END`, `KEY_PPAGE`, `KEY_NPAGE`, `KEY_DC`, `KEY_IC`, `KEY_BACKSPACE`, `KEY_F0`-`KEY_F63`, `KEY_MOUSE`, `KEY_RESIZE`
- ACS Characters: `ACS_ULCORNER`, `ACS_URCORNER`, `ACS_LLCORNER`, `ACS_LRCORNER`, `ACS_HLINE`, `ACS_VLINE`, `ACS_PLUS`, `ACS_LTEE`, `ACS_RTEE`, `ACS_BTEE`, `ACS_TTEE`, `ACS_BLOCK`, `ACS_CKBOARD`, `ACS_DIAMOND`, `ACS_DEGREE`, `ACS_BULLET`

---

## Panel Module

`tkcurses.panel` provides curses.panel-compatible API.

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
| `show()` | ✓ | Show panel |
| `top()` | ✓ | Move to top |
| `userptr()` | ✓ | Get user data |
| `window()` | ✓ | Get window |
