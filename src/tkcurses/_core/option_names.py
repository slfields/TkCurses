# TkCurses - a tkinter-compatible API layer that renders to curses
# Copyright (C) 2026  Scott L. Fields
#
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The option database names Tk reports for each widget option.

``configure("relief")`` answers five things in Tk: the option, its database
name, its database class, its default and its value. The two database names
come from Tk's C widget definitions, which do not exist here, so they are
written down instead: captured from Tcl/Tk 9.0.2's ``configure()`` on every
widget class tkinter and tkinter.ttk offer, and stored as one shared map plus
the few widgets that disagree with it. TkCurses-kifn.

The disagreements are real, not noise: a ttk Entry's ``background`` is
``windowColor``/``WindowColor`` while a ttk Label's is ``frameColor``, and a
ttk widget's ``class`` has no database name at all where a classic Frame's is
``class``/``Class``.

Regenerate rather than edit by hand if Tk changes: dump
``{name: entry[1:3] for name, entry in w.configure().items()}`` for each class
and keep the most common pair per name as the shared one.
"""

from __future__ import annotations

__all__ = ["WIDGET_CLASSES", "database_names"]

_SHARED: dict[str, tuple[str, str]] = {
    "activebackground": ("activeBackground", "Foreground"),
    "activeborderwidth": ("activeBorderWidth", "BorderWidth"),
    "activeforeground": ("activeForeground", "Background"),
    "activerelief": ("activeRelief", "Relief"),
    "activestyle": ("activeStyle", "ActiveStyle"),
    "anchor": ("anchor", "Anchor"),
    "aspect": ("aspect", "Aspect"),
    "autoseparators": ("autoSeparators", "AutoSeparators"),
    "background": ("background", "Background"),
    "backgroundimage": ("backgroundImage", "BackgroundImage"),
    "bigincrement": ("bigIncrement", "BigIncrement"),
    "bitmap": ("bitmap", "Bitmap"),
    "blockcursor": ("blockCursor", "BlockCursor"),
    "borderwidth": ("borderWidth", "BorderWidth"),
    "buttonbackground": ("buttonBackground", "Background"),
    "buttoncursor": ("buttonCursor", "Cursor"),
    "buttondownrelief": ("buttonDownRelief", "Relief"),
    "buttonuprelief": ("buttonUpRelief", "Relief"),
    "class": ("", ""),
    "closeenough": ("closeEnough", "CloseEnough"),
    "colormap": ("colormap", "Colormap"),
    "columns": ("columns", "Columns"),
    "command": ("command", "Command"),
    "compound": ("compound", "Compound"),
    "confine": ("confine", "Confine"),
    "container": ("container", "Container"),
    "cursor": ("cursor", "Cursor"),
    "default": ("default", "Default"),
    "digits": ("digits", "Digits"),
    "direction": ("direction", "Direction"),
    "disabledbackground": ("disabledBackground", "DisabledBackground"),
    "disabledforeground": ("disabledForeground", "DisabledForeground"),
    "displaycolumns": ("displayColumns", "DisplayColumns"),
    "elementborderwidth": ("elementBorderWidth", "BorderWidth"),
    "endline": ("", ""),
    "exportselection": ("exportSelection", "ExportSelection"),
    "font": ("font", "Font"),
    "foreground": ("foreground", "Foreground"),
    "format": ("format", "Format"),
    "from": ("from", "From"),
    "handlepad": ("handlePad", "HandlePad"),
    "handlesize": ("handleSize", "HandleSize"),
    "height": ("height", "Height"),
    "highlightbackground": ("highlightBackground", "HighlightBackground"),
    "highlightcolor": ("highlightColor", "HighlightColor"),
    "highlightthickness": ("highlightThickness", "HighlightThickness"),
    "image": ("image", "Image"),
    "inactiveselectbackground": ("inactiveSelectBackground", "Foreground"),
    "increment": ("increment", "Increment"),
    "indicatoron": ("indicatorOn", "IndicatorOn"),
    "insertbackground": ("insertBackground", "Foreground"),
    "insertborderwidth": ("insertBorderWidth", "BorderWidth"),
    "insertofftime": ("insertOffTime", "OffTime"),
    "insertontime": ("insertOnTime", "OnTime"),
    "insertunfocussed": ("insertUnfocussed", "InsertUnfocussed"),
    "insertwidth": ("insertWidth", "InsertWidth"),
    "invalidcommand": ("invalidCommand", "InvalidCommand"),
    "jump": ("jump", "Jump"),
    "justify": ("justify", "Justify"),
    "label": ("label", "Label"),
    "labelanchor": ("labelAnchor", "LabelAnchor"),
    "labelwidget": ("labelWidget", "LabelWidget"),
    "length": ("length", "Length"),
    "listvariable": ("listVariable", "Variable"),
    "maximum": ("maximum", "Maximum"),
    "maxundo": ("maxUndo", "MaxUndo"),
    "menu": ("menu", "Menu"),
    "mode": ("mode", "ProgressMode"),
    "offrelief": ("offRelief", "OffRelief"),
    "offset": ("offset", "Offset"),
    "offvalue": ("offValue", "Value"),
    "onvalue": ("onValue", "Value"),
    "opaqueresize": ("opaqueResize", "OpaqueResize"),
    "orient": ("orient", "Orient"),
    "overrelief": ("overRelief", "OverRelief"),
    "padding": ("padding", "Pad"),
    "padx": ("padX", "Pad"),
    "pady": ("padY", "Pad"),
    "phase": ("phase", "Phase"),
    "placeholder": ("placeHolder", "PlaceHolder"),
    "placeholderforeground": ("placeholderForeground", "PlaceholderForeground"),
    "postcommand": ("postCommand", "Command"),
    "proxybackground": ("proxyBackground", "ProxyBackground"),
    "proxyborderwidth": ("proxyBorderWidth", "ProxyBorderWidth"),
    "proxyrelief": ("proxyRelief", "Relief"),
    "readonlybackground": ("readonlyBackground", "ReadonlyBackground"),
    "relief": ("relief", "Relief"),
    "repeatdelay": ("repeatDelay", "RepeatDelay"),
    "repeatinterval": ("repeatInterval", "RepeatInterval"),
    "resolution": ("resolution", "Resolution"),
    "sashcursor": ("sashCursor", "Cursor"),
    "sashpad": ("sashPad", "SashPad"),
    "sashrelief": ("sashRelief", "Relief"),
    "sashwidth": ("sashWidth", "Width"),
    "screen": ("screen", "Screen"),
    "scrollregion": ("scrollRegion", "ScrollRegion"),
    "selectbackground": ("selectBackground", "Foreground"),
    "selectborderwidth": ("selectBorderWidth", "BorderWidth"),
    "selectcolor": ("selectColor", "Background"),
    "selectforeground": ("selectForeground", "Background"),
    "selectimage": ("selectImage", "SelectImage"),
    "selectmode": ("selectMode", "SelectMode"),
    "selecttype": ("selectType", "SelectType"),
    "setgrid": ("setGrid", "SetGrid"),
    "show": ("show", "Show"),
    "showhandle": ("showHandle", "ShowHandle"),
    "showvalue": ("showValue", "ShowValue"),
    "sliderlength": ("sliderLength", "SliderLength"),
    "sliderrelief": ("sliderRelief", "SliderRelief"),
    "spacing1": ("spacing1", "Spacing"),
    "spacing2": ("spacing2", "Spacing"),
    "spacing3": ("spacing3", "Spacing"),
    "startline": ("", ""),
    "state": ("state", "State"),
    "striped": ("striped", "Striped"),
    "style": ("style", "Style"),
    "tabs": ("tabs", "Tabs"),
    "tabstyle": ("tabStyle", "TabStyle"),
    "takefocus": ("takeFocus", "TakeFocus"),
    "tearoff": ("tearOff", "TearOff"),
    "tearoffcommand": ("tearOffCommand", "TearOffCommand"),
    "text": ("text", "Text"),
    "textvariable": ("textVariable", "Variable"),
    "tickinterval": ("tickInterval", "TickInterval"),
    "tile": ("tile", "Tile"),
    "title": ("title", "Title"),
    "titlecolumns": ("titlecolumns", "Titlecolumns"),
    "titleitems": ("titleitems", "Titleitems"),
    "to": ("to", "To"),
    "tristateimage": ("tristateImage", "TristateImage"),
    "tristatevalue": ("tristateValue", "TristateValue"),
    "troughcolor": ("troughColor", "Background"),
    "type": ("type", "Type"),
    "underline": ("underline", "Underline"),
    "undo": ("undo", "Undo"),
    "use": ("use", "Use"),
    "validate": ("validate", "Validate"),
    "validatecommand": ("validateCommand", "ValidateCommand"),
    "value": ("value", "Value"),
    "values": ("values", "Values"),
    "variable": ("variable", "Variable"),
    "visual": ("visual", "Visual"),
    "width": ("width", "Width"),
    "wrap": ("wrap", "Wrap"),
    "wraplength": ("wrapLength", "WrapLength"),
    "xscrollcommand": ("xScrollCommand", "ScrollCommand"),
    "xscrollincrement": ("xScrollIncrement", "ScrollIncrement"),
    "yscrollcommand": ("yScrollCommand", "ScrollCommand"),
    "yscrollincrement": ("yScrollIncrement", "ScrollIncrement"),
}

_EXCEPTIONS: dict[str, dict[str, tuple[str, str]]] = {
    "tk.Frame": {
        "class": ("class", "Class"),
    },
    "tk.LabelFrame": {
        "class": ("class", "Class"),
    },
    "tk.Spinbox": {
        "activebackground": ("activeBackground", "Background"),
    },
    "tk.Tk": {
        "class": ("class", "Class"),
    },
    "tk.Toplevel": {
        "class": ("class", "Class"),
    },
    "ttk.Checkbutton": {
        "offvalue": ("offValue", "OffValue"),
        "onvalue": ("onValue", "OnValue"),
    },
    "ttk.Combobox": {
        "background": ("windowColor", "WindowColor"),
        "foreground": ("textColor", "TextColor"),
        "postcommand": ("postCommand", "PostCommand"),
    },
    "ttk.Entry": {
        "background": ("windowColor", "WindowColor"),
        "foreground": ("textColor", "TextColor"),
    },
    "ttk.Label": {
        "background": ("frameColor", "FrameColor"),
        "foreground": ("textColor", "TextColor"),
    },
    "ttk.Notebook": {
        "padding": ("padding", "Padding"),
    },
    "ttk.Progressbar": {
        "foreground": ("textColor", "TextColor"),
    },
    "ttk.Radiobutton": {
        "value": ("Value", "Value"),
    },
    "ttk.Spinbox": {
        "background": ("windowColor", "WindowColor"),
        "foreground": ("textColor", "TextColor"),
    },
}

#: The widget classes the table was captured from, as ``"tk.Button"`` or
#: ``"ttk.Button"`` - tkinter's class names, not Tk's ``winfo_class``.
WIDGET_CLASSES = frozenset(
    {
        "tk.Button",
        "tk.Canvas",
        "tk.Checkbutton",
        "tk.Entry",
        "tk.Frame",
        "tk.Label",
        "tk.LabelFrame",
        "tk.Listbox",
        "tk.Menu",
        "tk.Menubutton",
        "tk.Message",
        "tk.OptionMenu",
        "tk.PanedWindow",
        "tk.Radiobutton",
        "tk.Scale",
        "tk.Scrollbar",
        "tk.Spinbox",
        "tk.Text",
        "tk.Tk",
        "tk.Toplevel",
        "ttk.Button",
        "ttk.Checkbutton",
        "ttk.Combobox",
        "ttk.Entry",
        "ttk.Frame",
        "ttk.Label",
        "ttk.LabeledScale",
        "ttk.Labelframe",
        "ttk.Menubutton",
        "ttk.Notebook",
        "ttk.OptionMenu",
        "ttk.Panedwindow",
        "ttk.Progressbar",
        "ttk.Radiobutton",
        "ttk.Scale",
        "ttk.Scrollbar",
        "ttk.Separator",
        "ttk.Sizegrip",
        "ttk.Spinbox",
        "ttk.Treeview",
    }
)


def database_names(widget_class: str, option: str) -> tuple[str, str]:
    """The database name and class Tk reports for ``option`` on a widget.

    Args:
        widget_class: One of :data:`WIDGET_CLASSES`, or ``""`` when the widget
            is none of them.
        option: The option's full name, ``"background"`` and not ``"bg"``.

    An option Tk's table does not have answers its own name and that name
    capitalised, which is the pattern most of Tk's own entries follow.
    """
    found = _EXCEPTIONS.get(widget_class, {}).get(option) or _SHARED.get(option)
    return found if found is not None else (option, option[:1].upper() + option[1:])
