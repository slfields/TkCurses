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

"""Tab stops that line up, and indents that change where text wraps.

What to do: press Ctrl-R for the sample. Ctrl-T cycles the tab stops.
Ctrl-B, Ctrl-G and Ctrl-E apply a block indent, a hanging indent and a right
margin to the paragraph; Ctrl-N takes them off. Type Tab in the table to add
a column.
What to look for: **the table's columns line up under the ruler**, and a
hanging indent makes the paragraph **wrap earlier**, not merely sit further
right.

The ruler along the top is the point of this scenario. Tab stops are a claim
about columns, and a claim about columns is checkable by eye only if there is
something to check it against - so the ruler is drawn in the editor's own
coordinates, and a stop at column 10 should put text under the 10.

Three things here are worth a person's attention rather than a test's.

**A first-line indent and a hanging indent are the same two options with
their values swapped**, which is why they sit next to each other here.
Ctrl-P indents the first line and leaves the rest flush - what a paragraph
in a book looks like, and what most people mean by indentation. Ctrl-G does
the opposite. An implementation that confused ``lmargin1`` with ``lmargin2``
would look plausible under either key on its own and be wrong under one of
them, so the pair is checked together rather than separately.

**An indent narrows the rows it indents.** That is the whole difference
between indenting and shifting, and it is invisible in any single row: you
have to see the paragraph break sooner than it did. Press Ctrl-G and watch
where the lines end. An implementation that moved the text without narrowing
it would look right until you compared.

**Tab stops are measured from the widget, not from the text.** Indent the
paragraph and the table keeps its columns exactly where they were. That is
what makes a tabbed table survive being indented, and it is the rule that
would have been got wrong by measuring stops from where each line starts.

**The two tab styles are not interchangeable.** Cycle to the two settings
that share a stop at 4: with ``wordprocessor`` the columns land every four,
and with ``tabular`` they do not, because the first tab is assigned to stop 4
and the text has already gone past it - so the documented fallback of a
single space applies. Tk's manual says to configure both the stop and the
style for uniform spacing, and this is why.

**Right and centre alignment put the text before the stop**, not after it.
With ``10 right`` the column ENDS at 10; with ``12 center`` it straddles 12.
Cycle to those and check the ruler, because "aligned at a stop" means four
different things and only one of them is the obvious one.
"""

from __future__ import annotations

import tkcurses
from uat import _support

TITLE = "39 - tabs and indentation"

#: Loaded by Ctrl-R. A tabbed table to check stops against the ruler, and a
#: paragraph long enough that an indent visibly changes where it wraps.
SAMPLE = (
    "Widget\tQty\tPrice\n"
    "frame\t2\t4.50\n"
    "label\t13\t0.25\n"
    "button\t7\t1.00\n"
    "\n"
    "This paragraph is here to be indented. It is long enough to wrap "
    "several times, which is the only way to see that a hanging indent "
    "makes the lines it indents shorter rather than merely moving them "
    "sideways across the screen.\n"
)

#: What Ctrl-T cycles through: the stops, the style, and what to expect.
#:
#: The second one carries ``wordprocessor`` for a reason worth knowing. With
#: the default ``tabular`` style a single stop at 4 does NOT give a column
#: every four: the first tab is assigned to stop 4, the text has already
#: passed it, and the documented fallback is one space. Tk's own manual says
#: to reach uniform spacing you configure the stop AND ``-tabstyle
#: wordprocessor``, which takes the next stop to the right instead. Driving
#: this scenario is what caught the label claiming otherwise.
TAB_SETTINGS = (
    ("", "tabular", "default - every 8 columns"),
    ("4", "wordprocessor", "every 4 columns - needs wordprocessor, see below"),
    ("4", "tabular", "the SAME stop, tabular - one space, not a column"),
    ("10 right", "tabular", "one stop at 10, right aligned - text ENDS at 10"),
    ("12 center", "tabular", "one stop at 12, centred - text straddles 12"),
    ("8 left 16 right 26 center", "tabular", "8 left, 16 right, 26 centre"),
)

#: Every margin back to nothing, merged under whichever one a key sets.
#: Merged rather than passed alongside: ``tag_configure(..., lmargin1=0,
#: **options)`` is a TypeError the moment options names lmargin1 too, which
#: is exactly what the block-indent key does.
CLEARED = {"lmargin1": 0, "lmargin2": 0, "rmargin": 0}

#: What the indent keys apply, and what each should do to the wrapping.
#:
#: The FIRST-LINE indent comes first because it is what "indentation" means
#: to most people: the indent at the start of a paragraph, the rest of it
#: flush left. It is lmargin1 on its own, and it is the one an implementation
#: is most likely to get wrong in the same breath as the hanging indent -
#: they are the same two options with the values swapped, so a version that
#: confused them would look plausible under both keys and be wrong under one.
INDENTS = {
    "p": ({"lmargin1": 6}, "FIRST-LINE indent - the classic paragraph indent"),
    "g": ({"lmargin2": 6}, "hanging indent - the other way round, wrapped rows only"),
    "b": ({"lmargin1": 6, "lmargin2": 6}, "block indent - every row moves in"),
    "e": ({"rmargin": 10}, "right margin - rows end sooner, none move"),
    "n": ({}, "no margins"),
}


def build(root, screen):
    screen.line(2, "Ctrl-R sample.  Ctrl-T tab stops.  Tab inserts a tab.")
    screen.line(
        3,
        "Ctrl-P first-line  Ctrl-G hanging  Ctrl-B block  Ctrl-E rmargin  Ctrl-N none",
    )

    editor = tkcurses.Text(root, name="editor", width=60, height=11, wrap="word")
    # x=3 and not x=2: the editor is placed at 2 and draws a border, so its
    # text begins one column further in. The ruler has to agree with the
    # text, not with the widget, or every reading off it is one out.
    editor.place(x=2, y=6, relwidth=1.0, width=-4, height=11)

    ruler = tkcurses.Label(root, name="ruler", anchor="w")
    ruler.place(x=3, y=5, relwidth=1.0, width=-6)

    stops = tkcurses.Label(root, name="stops", anchor="w")
    stops.place(x=2, y=18, relwidth=1.0, width=-4)
    indent = tkcurses.Label(root, name="indent", anchor="w")
    indent.place(x=2, y=19, relwidth=1.0, width=-4)
    where = tkcurses.Label(root, name="where", anchor="w")
    where.place(x=2, y=21, relwidth=1.0, width=-4)

    setting = {"tabs": 0}

    def draw_ruler(event=None):
        """A column scale in the editor's own coordinates.

        Redrawn on resize, because a ruler that is right only at the size
        the scenario started in is worse than none: it would be read as the
        truth and quietly disagree with the text under it.
        """
        width = max(0, editor.winfo_width() - 2)
        marks = []
        for column in range(width):
            if column % 10 == 0:
                marks.append(str((column // 10) % 10))
            elif column % 5 == 0:
                marks.append("+")
            else:
                marks.append("-")
        ruler.configure(text="".join(marks))

    def report():
        at = editor.index("insert")
        box = editor.bbox("insert")
        line = editor.dlineinfo("insert")
        cell = "off screen" if box is None else f"cell x={box[0]} y={box[1]}"
        row = "-" if line is None else f"x={line[0]} width={line[2]}"
        where.configure(text=f"insert {at}   {cell}   dlineinfo {row}")
        root.after(100, report)

    def show_tabs():
        spec, style, description = TAB_SETTINGS[setting["tabs"]]
        stops.configure(
            text=f"tabs={spec or '(default)'}  style={style}   {description}"
        )

    def cycle_tabs(event=None):
        setting["tabs"] = (setting["tabs"] + 1) % len(TAB_SETTINGS)
        spec, style, _ = TAB_SETTINGS[setting["tabs"]]
        editor.configure(tabs=spec, tabstyle=style)
        show_tabs()
        return "break"

    def apply_indent(key):
        def handler(event=None):
            options, description = INDENTS[key]
            # Cleared first: the options are applied to one tag, so leaving
            # a previous margin set would make two of these keys compose
            # rather than replace, and the checklist asks about one at a
            # time.
            editor.tag_configure("indent", **{**CLEARED, **options})
            editor.tag_add("indent", "6.0", "end")
            indent.configure(text=f"paragraph: {description}")
            return "break"

        return handler

    def load(event=None):
        editor.delete("1.0", "end")
        editor.insert("1.0", SAMPLE)
        editor.mark_set("insert", "1.0")
        editor.see("1.0")
        indent.configure(text="paragraph: no margins")
        return "break"

    def insert_tab(event=None):
        editor._type("\t")
        return "break"

    editor.bind("<Tab>", insert_tab)
    editor.bind("<Control-r>", load)
    editor.bind("<Control-t>", cycle_tabs)
    editor.bind("<Control-p>", apply_indent("p"))
    editor.bind("<Control-b>", apply_indent("b"))
    editor.bind("<Control-g>", apply_indent("g"))
    editor.bind("<Control-e>", apply_indent("e"))
    editor.bind("<Control-n>", apply_indent("n"))
    root.bind("<Configure>", draw_ruler)

    editor.focus_set()
    show_tabs()
    indent.configure(text="paragraph: no margins")
    root.after(50, draw_ruler)
    root.after(100, report)


if __name__ == "__main__":
    raise SystemExit(_support.run(TITLE, build))
