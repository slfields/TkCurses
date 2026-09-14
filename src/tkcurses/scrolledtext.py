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

"""A Text with its scrollbar already attached.

Two widgets that nearly always appear together, packaged as one. It *is* a
Text - every method a Text has, it has - with a Frame holding it and a
Scrollbar down the right-hand side, already wired both ways: the text tells
the bar where the view is, and the bar tells the text where to move it.

The one awkward part is tkinter's, and it is kept because the alternative
breaks code. A ScrolledText is a Text, so ``pack`` on it would pack the text
*inside its own frame*, leaving the frame unmanaged and nothing on screen.
tkinter solves this by copying the geometry methods off the frame onto the
instance, so ``scrolled.pack()`` packs the frame and everything else reaches
the text. It is a hack, tkinter calls it one, and it is the behaviour every
caller is written against.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tkcurses

if TYPE_CHECKING:
    from tkcurses import Misc

__all__ = ["ScrolledText"]

#: Methods taken from the frame rather than from the text. Everything the
#: geometry managers define that a Text does not, less the two that would
#: send a caller's options to the wrong widget: ``config`` and ``configure``
#: belong to the text, since that is what the options are for.
_GEOMETRY_METHODS = frozenset(
    name
    for name in (
        set(vars(tkcurses.Pack)) | set(vars(tkcurses.Grid)) | set(vars(tkcurses.Place))
    )
    - set(vars(tkcurses.Text))
    if not name.startswith("_") and name not in ("config", "configure")
)


class ScrolledText(tkcurses.Text):
    """A text widget with a vertical scrollbar beside it.

    Attributes:
        frame: The container holding the text and the bar. This is what a
            geometry manager is given.
        vbar: The scrollbar.
    """

    def __init__(self, master: Misc | None = None, **kw: Any) -> None:
        """
        Args:
            master: Parent widget; the implicit root when omitted.
            **kw: Options for the Text. ``yscrollcommand`` is set here and
                anything given for it is replaced.
        """
        self.frame = tkcurses.Frame(master)
        self.vbar = tkcurses.Scrollbar(self.frame)
        self.vbar.pack(side="right", fill="y")

        kw["yscrollcommand"] = self.vbar.set
        super().__init__(self.frame, **kw)
        # Packed inside the frame, which is the one place the plain
        # tkcurses.Text.pack would have to be used rather than the
        # redirected one installed below.
        tkcurses.Text.pack(self, side="left", fill="both", expand=True)
        self.vbar.configure(command=self.yview)

        for name in _GEOMETRY_METHODS:
            setattr(self, name, getattr(self.frame, name))

    def winfo_class(self) -> str:
        """``Text``, because that is what it is.

        Binding tags name one class, not a chain: a widget reporting
        ``ScrolledText`` would be looked up under that tag and find none of
        the Text class bindings, so every key - typing included - would
        reach it and do nothing. tkinter has no such problem, its Tk class
        being whatever the underlying widget was created as, which for a
        Text subclass is still ``Text``.
        """
        return "Text"

    def __str__(self) -> str:
        """The frame's path, since the frame is what a caller manages."""
        return str(self.frame)
