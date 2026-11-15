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

"""What can go wrong, each with the exit status the command ends with.

The statuses are part of the command's interface - a script tests them - so
each class owns its number and nothing else picks one. 2 is argparse's own,
for a command line it cannot parse.
"""

from __future__ import annotations

from dataclasses import dataclass


class CfgError(Exception):
    """Anything the command reports to its user and stops on.

    The message is the whole report: it names the file or setting and, when
    a write was refused, says that nothing was changed.
    """

    exit_code = 1


class UnknownSetting(CfgError):
    """A setting name that is not one."""

    exit_code = 3


class InvalidSettingValue(CfgError):
    """A value the setting does not accept, or a file holding one."""

    exit_code = 4


class FileSyntaxError(CfgError):
    """A configuration file that cannot be read as one, so is not edited."""

    exit_code = 5

    def __init__(self, path: str, line: int | None, problem: str) -> None:
        where = f"{path}, line {line}" if line is not None else path
        super().__init__(f"{where}: {problem}")
        self.path = path
        self.line = line
        self.problem = problem


class UnsafePath(CfgError):
    """A save refused because someone other than the person running the
    command could change the file or a directory or link on the way to it."""

    exit_code = 6

    def __init__(self, message: str, why: str | None = None) -> None:
        super().__init__(message)
        #: The reason alone, without the path and the advice.
        self.why = why or message


@dataclass(frozen=True)
class Problem:
    """Something wrong in a file that is still readable."""

    #: 1-based line number.
    line: int
    #: ``section.key``, or the section alone for an unknown section.
    name: str
    #: ``invalid``, ``unknown-section``, ``unknown-key`` or ``removed``.
    kind: str
    message: str

    @property
    def blocking(self) -> bool:
        """Whether it stops an edit of any other setting. Only a value of
        the wrong type or out of range does: a program would silently use
        something else, so the file is not left that way by an edit that
        ignores it."""
        return self.kind == "invalid"


class BlockedByProblems(InvalidSettingValue):
    """An edit refused because the file holds values that are not valid,
    and the edit does not fix them."""

    def __init__(self, path: str, problems: list[Problem]) -> None:
        lines = "\n".join(f"  line {p.line}: {p.name}: {p.message}" for p in problems)
        super().__init__(
            f"{path} has values that are not valid, so it was not changed:\n"
            f"{lines}\n"
            "Fix or unset them first."
        )
        self.problems = problems
