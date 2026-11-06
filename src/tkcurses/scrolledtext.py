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

"""A Text with a scrollbar beside it, as ``tkinter.scrolledtext``."""

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
    """A text widget with a vertical scrollbar beside it, already connected.

    Sample output:
        from tkcurses import scrolledtext
        text = scrolledtext.ScrolledText(root, width=30, height=6)
        text.insert("end", "\\n".join(f"Line {n}" for n in range(1, 40)))
        text.pack()

    It is a :class:`~tkcurses.Text`, with every method one has. ``pack``,
    ``grid`` and ``place`` place the frame holding the text and the bar, as
    in tkinter, so ``text.pack()`` shows both.

    Attributes:
        frame: The frame holding the text and the scrollbar.
        vbar: The scrollbar.
    """

    # tkinter does this by copying the geometry methods off the frame onto the
    # instance; it calls it a hack, and it is what every caller is written
    # against.

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
