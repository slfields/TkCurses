# Standard options

Many options mean the same thing on every widget that takes them: a colour,
a border, where the text sits. They are described once here, the way Tk's
own [options manual](https://www.tcl-lang.org/man/tcl9.0/TkCmd/options.html)
describes them, and each widget's page lists which of them it takes.
`width`, `height` and `state` are here too: every widget has them, and only
their units differ, which each widget's page gives.

An option is given when the widget is made, or changed later:

```python
label = tk.Label(root, text="Ready", relief="sunken")
label.configure(relief="raised")
label["relief"] = "flat"
```

Where an option has no visible effect on a particular widget, that widget's
page says so. That is measured, not assumed: each widget is drawn with and
without each option, under the state the option applies to, and the two
screens compared.

**Units.** Wherever Tk measures in pixels, TkCurses measures in character
cells: one column of one row of the terminal. A `padx` of 2 is two columns.

**Colours** are given as Tk takes them - one of Tk's names such as `"red"`,
`"SteelBlue"` or `"light goldenrod yellow"`, or `"#rrggbb"` - and drawn as
near as the terminal can show. A name Tk does not know is refused when it is
set.
`bg` and `fg` are short for `background` and `foreground`, and `bd` for
`borderwidth`.

## Colour

### background

The colour behind the widget's content.

```{tkcurses-sample}
for colour in ("red", "green", "blue", "magenta"):
    tk.Label(root, text=colour, bg=colour).pack(side="left", padx=1)
```

### foreground

The colour of the widget's text, and of a border drawn in characters.

```{tkcurses-sample}
for colour in ("red", "green", "cyan", "yellow"):
    tk.Label(root, text=colour, fg=colour).pack(side="left", padx=1)
```

### activebackground

The background while the widget is *active*: under the mouse, or given
`state="active"`. Not drawn by OptionMenu or Spinbox.

```{tkcurses-sample}
tk.Button(root, text="Normal").pack(side="left", padx=1)
tk.Button(root, text="Active", state="active", activebackground="blue").pack(
    side="left", padx=1
)
```

### activeforeground

The text colour while the widget is active. Not drawn by OptionMenu.

```{tkcurses-sample}
tk.Button(root, text="Normal").pack(side="left", padx=1)
tk.Button(root, text="Active", state="active", activeforeground="yellow").pack(
    side="left", padx=1
)
```

### disabledforeground

The text colour while the widget is disabled. Left at its default, a
disabled widget is drawn dim.

```{tkcurses-sample}
tk.Button(root, text="Disabled", state="disabled").pack(side="left", padx=1)
tk.Button(root, text="Red", state="disabled", disabledforeground="red").pack(
    side="left", padx=1
)
```

### selectbackground

The background of selected text or items.

```{tkcurses-sample}
entry = tk.Entry(root, selectbackground="green")
entry.insert(0, "Some selected text")
entry.pack()
entry.select_range(5, "end")
entry.focus_force()
```

### selectforeground

The colour of selected text or items.

```{tkcurses-sample}
items = tk.Listbox(root, height=3, selectforeground="yellow")
for name in ("Apples", "Pears", "Plums"):
    items.insert("end", name)
items.pack()
items.selection_set(1)
```

### troughcolor

The colour of the trough a Scale's slider runs along. Scrollbar does not
draw it.

```{tkcurses-sample}
tk.Scale(root, from_=0, to=10, orient="horizontal", troughcolor="blue").pack()
```

### highlightbackground, highlightcolor, highlightthickness

In Tk, a ring around the widget that shows where the keyboard focus is.
TkCurses shows the focus with markers drawn into the widget instead - `▶`
and `◀` either side of a button's text, for example - so these are accepted
and read back, and draw nothing.

### insertbackground, insertborderwidth, insertofftime, insertontime, insertwidth

The insertion cursor in an Entry, Spinbox, Text or Canvas. In a terminal
the insertion cursor *is* the terminal's own cursor, whose shape, colour
and blink belong to the terminal and its settings, so these are accepted
and draw nothing.

## Borders

### relief

The style of the widget's border: `flat`, `raised`, `sunken`, `groove`,
`ridge` or `solid`. Drawn with box-drawing characters: a raised border is
bright and a sunken one dim, and groove and ridge use doubled lines.

```{tkcurses-sample}
# size: 80x5
for relief in ("flat", "raised", "sunken", "groove", "ridge", "solid"):
    tk.Label(root, text=relief, relief=relief).pack(side="left", padx=1)
```

### borderwidth

The width of the border. As in Tk, a border 0 wide is not drawn,
whatever the relief, and the defaults are Tk's: 1 on most widgets, 2 on a
LabelFrame, 0 on a Frame and a Canvas. A border in a terminal is one cell of
box-drawing characters however wide it is asked to be, so any width from 1
up draws the same box.

**Differences from Tk:** a flat border takes no cell. Tk keeps its pixels
as blank space; here that would be a blank cell round every label. And a
Toplevel's frame stands in for the window manager's, so it is drawn at
its default of 1, flat or not, and `borderwidth=0` takes it away.

```{tkcurses-sample}
for width in (0, 1):
    tk.Label(root, text=f"bd={width}", relief="solid", bd=width).pack(
        side="left", padx=1
    )
```

### activeborderwidth

The border of a menu's active entry, in Tk. The active entry is shown by
its colours instead, so this draws nothing.

## Text

### text

The text the widget shows. A newline starts another line. OptionMenu shows
its variable's value instead.

```{tkcurses-sample}
tk.Label(root, text="One line").pack()
tk.Label(root, text="Two\nlines").pack()
```

### textvariable

A variable whose value is the widget's text, kept up to date as it
changes. See [Variables](../guide/concepts.md#variables).

### font

The font. A terminal has one font in one size, so of a font's description
TkCurses uses its style: `bold`, `italic` and `underline` each become the
terminal's own attribute, where the terminal has it. A family and a size
are accepted and make no difference.

**Differences from Tk:** `overstrike` is accepted and not drawn: curses
has no attribute for it.

```{tkcurses-sample}
for style in ("normal", "bold", "italic", "underline"):
    tk.Label(root, text=style, font=("TkDefaultFont", 10, style)).pack(
        side="left", padx=1
    )
```

### anchor

Where the content sits when the widget is bigger than it needs to be: a
compass point - `n`, `ne`, `e`, `se`, `s`, `sw`, `w`, `nw` - or `center`.

When the text is wider than the widget, the anchor also decides which part
is cut off, as in Tk: anchored `e`, the end shows and the start is cut;
centred, both ends are cut. A themed widget is the exception, and always
shows the start.

```{tkcurses-sample}
for anchor in ("nw", "center", "se"):
    tk.Label(root, text=anchor, width=10, height=3, relief="solid",
             anchor=anchor).pack(side="left", padx=1)
```

### justify

How the lines of a multi-line text line up with one another: `left`,
`center` or `right`. In an entry or a spinbox it places the one line in
the field, while all of it fits: a longer text starts at the left and
scrolls, as in Tk. While a field has the focus, one cell is kept at the
right for the insertion cursor. OptionMenu shows one line, so it has
nothing to line up.

```{tkcurses-sample}
# size: 60x6
for justify in ("left", "center", "right"):
    tk.Label(root, text="Short\nmuch longer", relief="solid",
             justify=justify).pack(side="left", padx=1)
```

### wraplength

The longest a line may be, in cells, before the text wraps onto the next.
0, the default, never wraps.

```{tkcurses-sample}
tk.Label(root, relief="solid", wraplength=14,
         text="A label whose text is longer than fits").pack()
```

### underline

The index of a character in the text to underline - the letter of a
keyboard shortcut. -1, the default, underlines none. Binding the shortcut
is the program's to do.

```{tkcurses-sample}
tk.Button(root, text="Save", underline=0).pack(side="left", padx=1)
tk.Button(root, text="Quit", underline=0).pack(side="left", padx=1)
```

### placeholder

Text an empty Entry or Spinbox shows until something is typed into it.

```{tkcurses-sample}
tk.Entry(root, placeholder="Search...").pack()
```

### placeholderforeground

The colour of the placeholder text.

```{tkcurses-sample}
tk.Entry(root, placeholder="Search...", placeholderforeground="cyan").pack()
```

## Images

### image

An image to show instead of the text. Images are drawn with half-cell
blocks, two pixels to a cell, so a picture keeps its proportions.

```{tkcurses-sample}
picture = tk.PhotoImage(width=8, height=4)
picture.put("red", to=(0, 0, 4, 4))
picture.put("blue", to=(4, 0, 8, 4))
tk.Label(root, image=picture).pack()
```

### compound

Where the image goes when a widget has both an image and text: `left`,
`right`, `top`, `bottom` or `center`, or `none` - the default - for the
image alone.

```{tkcurses-sample}
picture = tk.PhotoImage(width=4, height=4)
picture.put("green", to=(0, 0, 4, 4))
for compound in ("left", "top", "right"):
    tk.Label(root, text=compound, image=picture, compound=compound).pack(
        side="left", padx=1
    )
```

### bitmap

One of Tk's ten built-in bitmaps by name, or `@` and the path of an XBM
file, on Button, Checkbutton, Label, Menubutton, OptionMenu and Radiobutton.
As in Tk, a bitmap is drawn in place of the text unless `compound` says
otherwise, and an `image` wins over it; any other name is refused with Tk's
`bitmap "name" not defined`.

A file is drawn as a `BitmapImage` of it would be, in the widget's
foreground. A named bitmap is a 16-pixel picture with no room in a cell, so
each is one character that reads as it:

| Name | Glyph | Name | Glyph |
|------|-------|------|-------|
| `error` | ✖ | `hourglass` | ⧗ |
| `gray12` | · | `info` | ℹ |
| `gray25` | ░ | `questhead` | ⍰ |
| `gray50` | ▒ | `question` | ? |
| `gray75` | ▓ | `warning` | ⚠ |

```{tkcurses-sample}
for name in ("info", "warning", "error", "question"):
    tk.Label(root, bitmap=name, text=name, compound="left").pack(anchor="w")
```

## Size and spacing

### width

How wide the widget is. Its unit depends on the widget, as in Tk: characters
for the widgets that show text - Button, Checkbutton, Entry, Label, Listbox,
Menubutton, OptionMenu, Radiobutton, Spinbox and Text - and cells for the
rest. 0 lets the widget size itself to its content. A LabelFrame with
children sizes itself to them, as in Tk.

```{tkcurses-sample}
for width in (4, 10, 16):
    tk.Label(root, text="Hi", width=width, relief="solid").pack(pady=0)
```

### height

How tall the widget is: lines for the widgets that show text, cells for
the rest.

```{tkcurses-sample}
for height in (1, 3):
    tk.Label(root, text="Hi", height=height, relief="solid").pack(
        side="left", padx=1
    )
```

### padx, pady

Extra space between the widget's border and its content, across (`padx`)
and up and down (`pady`), in cells. Not drawn by an empty Frame, a Menu or
a Scrollbar, which have no content to space.

```{tkcurses-sample}
tk.Label(root, text="padx=0", relief="solid").pack(side="left", padx=1)
tk.Label(root, text="padx=3", relief="solid", padx=3).pack(side="left", padx=1)
tk.Label(root, text="pady=1", relief="solid", pady=1).pack(side="left", padx=1)
```

### orient

Which way a Scale, Scrollbar or PanedWindow runs: `horizontal` or
`vertical`.

```{tkcurses-sample}
tk.Scale(root, from_=0, to=10, orient="horizontal").pack(side="left")
tk.Scale(root, from_=0, to=10, orient="vertical", length=5).pack(side="left")
```

## State

### state

`normal`, `disabled`, and for some widgets `active` or `readonly`. A
disabled widget is drawn dim and ignores the keyboard and mouse; an
active one is drawn in its active colours.

```{tkcurses-sample}
for state in ("normal", "active", "disabled"):
    tk.Button(root, text=state, state=state).pack(side="left", padx=1)
```

## Themed widgets

The [themed widgets](ttk/index.md) take most of their look from a
[style](ttk/style.md) rather than from options of their own. These three
are on most of them, as Tk's
[ttk_widget manual](https://www.tcl-lang.org/man/tcl9.0/TkCmd/ttk_widget.html)
describes them.

### style

The style the widget is drawn with. Each themed widget has one by
default, named after its class - `TButton`, `TEntry` - and a style named
with a dot before that, such as `Danger.TButton`, takes from it whatever
it does not set itself.

```{tkcurses-sample}
style = ttk.Style()
style.configure("Danger.TButton", foreground="red")
ttk.Button(root, text="Keep").pack(side="left", padx=1)
ttk.Button(root, text="Delete", style="Danger.TButton").pack(side="left", padx=1)
```

### padding

Space between the widget's border and what it holds, in cells. One
number is every side; two are across and up and down; four are left,
top, right and bottom. A themed Label, Button, Checkbutton, Radiobutton
or Menubutton grows by it around its text. In Tk it replaces the padding
the theme gives the widget, which is a pixel or three and so no cell
here, so here it is simply added.

```{tkcurses-sample}
for padding in (0, 1, "3 0"):
    frame = ttk.Frame(root, relief="solid", padding=padding)
    ttk.Label(frame, text=f"{padding}").pack()
    frame.pack(side="left", padx=1)
ttk.Label(root, text="label", padding="2 1", relief="solid").pack(side="left")
```

### class

The widget's class, which its style and bindings are named after:
`TButton` for a themed button. Give it as `class_` when the widget is
made; tkinter refuses to change it afterwards.

## Behaviour

These change what a widget does rather than how it looks.

### cursor

The shape of the mouse pointer over the widget. The pointer belongs to the
terminal, which a program cannot change, so this is accepted and draws
nothing.

### takefocus

Whether Tab stops at the widget: `1`, `0`, or `""` to let the widget
decide, which for most is whether it takes keyboard input.

### exportselection

Whether selecting text in the widget also makes it the selection other
programs can paste.

### jump

Whether a Scrollbar's view follows the slider as it is dragged (0) or only
when it is let go (1).

### repeatdelay, repeatinterval

How long a held mouse button waits before repeating, and then how often it
repeats, in milliseconds.

### setgrid

In Tk, whether the window resizes in whole lines and characters. A
terminal already does, so this changes nothing.

### selectborderwidth

The border around selected items, in Tk. A selection is shown by its
colours instead, so this draws nothing.

### xscrollcommand, yscrollcommand

A function the widget calls when its view moves, with the fractions of its
content in view - which is how a Scrollbar is connected to it:
`listbox.configure(yscrollcommand=scrollbar.set)`.
