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

"""A treemap's items: two levels of named values. Pure.

The items are a ttk.Treeview's - identifiers, a parent, an order among
siblings, and Treeview's error words - with a value each and a limit of
two levels, as Kibana's treemap has. An item under the root is a
*top-level item*; one under a top-level item is a *child*; a top-level
item with children is a *group*, and its size is the sum of theirs.

Errors are ``ValueError``; the widget turns them into ``TclError``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Item", "Model", "checked_tags", "checked_value"]


@dataclass(slots=True)
class Item:
    """One item: its identifier, parent, name and own value."""

    iid: str
    parent: str
    text: str = ""
    #: The item's own value. A group's size is its children's sum instead;
    #: this is kept, and counts again once the last child is deleted.
    value: float = 0.0
    children: list[str] = field(default_factory=list)
    #: Names a program groups items by, for :meth:`Model.tagged`.
    tags: tuple[str, ...] = ()


def checked_tags(tags: Any) -> tuple[str, ...]:
    """``tags`` as a tuple of names: a list, or one string of names split
    at spaces, as Tk reads a list. A tag named twice is kept once."""
    if tags is None or tags == "":
        return ()
    names = tags.split() if isinstance(tags, str) else [str(tag) for tag in tags]
    return tuple(dict.fromkeys(names))


def checked_value(value: Any) -> float:
    """``value`` as a size: a finite number, not negative.

    Raises:
        ValueError: If it is not a number, is negative, or is NaN or an
            infinity.
    """
    if isinstance(value, bool):
        raise ValueError(f'expected a number but got "{value}"')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'expected a number but got "{value}"') from None
    if not math.isfinite(number):
        raise ValueError(f'a treemap value must be finite, not "{value}"')
    if number < 0:
        raise ValueError(f'a treemap value cannot be negative: "{value}"')
    return number


class Model:
    """The items of one treemap, with its focus and its selection.

    ``version`` goes up on every change to the items, so a layout computed
    for one version can be reused until the next.
    """

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}
        self._roots: list[str] = []
        self._counter = 0
        self.version = 0
        #: The focused item, or ``""``.
        self.focus = ""
        #: The selected item, or ``""``: a treemap selects one at most.
        self.selected = ""

    # ------------------------------------------------------------ changing

    def insert(
        self,
        parent: str,
        index: Any = "end",
        iid: str | None = None,
        *,
        text: str = "",
        value: Any = 0,
        tags: Any = (),
    ) -> str:
        """Add an item under ``parent`` (``""`` for the top level) and
        return its identifier, ``I001`` and on when none is given."""
        if parent:
            self._two_levels(parent)
        size = checked_value(value)
        position = self._position(index)
        if iid is None:
            self._counter += 1
            iid = f"I{self._counter:03d}"
            while iid in self._items:
                self._counter += 1
                iid = f"I{self._counter:03d}"
        else:
            iid = str(iid)
            if iid in self._items:
                raise ValueError(f"Item {iid} already exists")
        self._items[iid] = Item(iid, parent, str(text), size, tags=checked_tags(tags))
        _place(self._siblings(parent), iid, position)
        self.version += 1
        return iid

    def configure(
        self,
        iid: str,
        *,
        text: str | None = None,
        value: Any = None,
        tags: Any = None,
    ) -> None:
        """Change an item's name, value or tags; ``None`` leaves one as it
        is."""
        item = self.item(iid)
        size = item.value if value is None else checked_value(value)
        if text is not None:
            item.text = str(text)
        if tags is not None:
            item.tags = checked_tags(tags)
        item.value = size
        self.version += 1

    def delete(self, *iids: str) -> None:
        """Remove items, a group with its children.

        Every name is checked before anything is removed, so a mistake in
        the list leaves the treemap as it was.
        """
        for iid in iids:
            self.item(iid)
        for iid in iids:
            item = self._items.get(iid)
            if item is None:  # a child named after its group
                continue
            for child in item.children:
                self._forget(child)
            self._siblings(item.parent).remove(iid)
            self._forget(iid)
        self.version += 1

    def move(self, iid: str, parent: str, index: Any) -> None:
        """Put ``iid`` under ``parent`` at ``index`` among its children."""
        item = self.item(iid)
        position = self._position(index)
        if parent:
            if parent == iid:
                raise ValueError(f"Cannot insert {iid} as descendant of {iid}")
            self._two_levels(parent)
            if item.children:
                raise ValueError(
                    f"a treemap has two levels: {iid} has children, so it "
                    "cannot go under another item"
                )
        self._siblings(item.parent).remove(iid)
        item.parent = parent
        _place(self._siblings(parent), iid, position)
        self.version += 1

    # ------------------------------------------------------------- reading

    def item(self, iid: str) -> Item:
        """The item called ``iid``."""
        found = self._items.get(iid)
        if found is None:
            raise ValueError(f"Item {iid} not found")
        return found

    def exists(self, iid: str) -> bool:
        """Whether ``iid`` names an item."""
        return iid in self._items

    def get_children(self, iid: str = "") -> tuple[str, ...]:
        """The items under ``iid`` (``""``: the top level), in their order."""
        if iid:
            return tuple(self.item(iid).children)
        return tuple(self._roots)

    def parent(self, iid: str) -> str:
        """The item above ``iid``, or ``""`` for a top-level item."""
        return self.item(iid).parent

    def index(self, iid: str) -> int:
        """Where ``iid`` is among its siblings."""
        item = self.item(iid)
        return self._siblings(item.parent).index(iid)

    def size(self, iid: str) -> float:
        """How much room ``iid`` takes: its value, or a group's children's
        sum."""
        item = self.item(iid)
        if item.children:
            return math.fsum(self._items[child].value for child in item.children)
        return item.value

    def total(self, iid: str = "") -> float:
        """The sum of everything under ``iid`` (``""``: the whole treemap)."""
        if iid:
            return self.size(iid)
        return math.fsum(self.size(root) for root in self._roots)

    def ordered(self, iid: str = "") -> list[str]:
        """The items under ``iid`` as they are laid out: largest first,
        equal sizes in their order among siblings."""
        children = self.get_children(iid)
        return sorted(children, key=lambda child: -self.size(child))

    def tagged(self, tag: str) -> tuple[str, ...]:
        """The items carrying ``tag``, in the order they were inserted."""
        return tuple(iid for iid, item in self._items.items() if tag in item.tags)

    def path(self, iid: str) -> tuple[str, ...]:
        """``(group, child)`` or ``(item,)``: the iids from the top level
        down to ``iid``."""
        parent = self.parent(iid)
        return (parent, iid) if parent else (iid,)

    # -------------------------------------------------------------- inside

    def _two_levels(self, parent: str) -> None:
        """Refuse ``parent`` unless an item may go under it."""
        above = self.item(parent).parent
        if above:
            raise ValueError(f"a treemap has two levels: {parent} is already a child")

    def _siblings(self, parent: str) -> list[str]:
        return self._items[parent].children if parent else self._roots

    def _forget(self, iid: str) -> None:
        del self._items[iid]
        if self.focus == iid:
            self.focus = ""
        if self.selected == iid:
            self.selected = ""

    @staticmethod
    def _position(index: Any) -> int | None:
        """``None`` for ``"end"``, else the index as a number."""
        if str(index) == "end":
            return None
        try:
            return int(index)
        except (TypeError, ValueError):
            raise ValueError(f'bad index "{index}"') from None


def _place(siblings: list[str], iid: str, position: int | None) -> None:
    """Put ``iid`` into ``siblings`` at ``position``, clamped; at the end for
    ``None``."""
    if position is None:
        siblings.append(iid)
    else:
        siblings.insert(max(0, min(position, len(siblings))), iid)
