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

"""What the interactive screen edits: both files, and the edits not yet saved.

Nothing here draws. The screen asks a :class:`Session` what to show and
tells it what the person did; every rule - what a value may be, which edits
a file with a bad value accepts, what a program would end up using - is
decided here, through the same pieces the command line uses, so the two
cannot disagree.

**What a program would use** is worked out by the loader itself. The edited
text of each file is written to a private temporary directory and
:meth:`TkCursesConfig.load` reads it there, as a program would read the
real one. Re-implementing the loader's order and its refusals here would
make a second copy of the policy to drift from the first.
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from tkcurses._cfg import store
from tkcurses._cfg.errors import CfgError, FileSyntaxError, InvalidSettingValue
from tkcurses._cfg.inifile import IniFile, describe_values, lookup
from tkcurses._core.config import (
    BY_NAME,
    InvalidValue,
    Origin,
    Setting,
    TkCursesConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tkcurses._cfg.errors import Problem

Scope = Literal["user", "system"]
SCOPES: tuple[Scope, Scope] = ("user", "system")


@dataclass
class FileState:
    """One file as it was last read."""

    path: Path
    #: The file checked, or ``None`` when it cannot be read as a
    #: configuration - then :attr:`error` says why, and it is not edited.
    ini: IniFile | None
    error: str | None
    #: Its bytes when read, ``None`` when there was no file: what a later
    #: look at the disk is compared with.
    stamp: bytes | None


@dataclass(frozen=True)
class Change:
    """One edit not yet saved, for the confirmation before saving."""

    scope: Scope
    name: str
    #: The file's value before and after, as written in it; ``None`` for
    #: not set.
    before: str | None
    after: str | None


@dataclass
class Session:
    """Both files, the edits made to them, and what a program would use."""

    system: Path
    user: Path
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    #: The file being edited.
    scope: Scope = "user"
    #: Per file: ``name`` -> the value to write, or ``None`` to take the
    #: line out.
    pending: dict[Scope, dict[str, str | None]] = field(
        default_factory=lambda: {"user": {}, "system": {}}
    )

    def __post_init__(self) -> None:
        self.files: dict[Scope, FileState] = {}
        #: Each file with the pending edits made, or as read where it
        #: cannot be.
        self.edited: dict[Scope, IniFile | None] = {}
        #: Per file, edits the file refuses as it stands, and why.
        self.refused: dict[Scope, dict[str, str]] = {"user": {}, "system": {}}
        self.config = TkCursesConfig()
        self.reload()

    # ------------------------------------------------------------- files

    def path(self, scope: Scope | None = None) -> Path:
        return self.user if (scope or self.scope) == "user" else self.system

    def reload(self, scope: Scope | None = None) -> None:
        """Read the files again, keeping the pending edits on top of them."""
        for each in (scope,) if scope else SCOPES:
            self.files[each] = _read(self.path(each))
        self._refresh()

    def changed_on_disk(self) -> list[Scope]:
        """The files whose contents are no longer what was read."""
        changed: list[Scope] = []
        for scope in SCOPES:
            state = self.files[scope]
            try:
                now: bytes | None = state.path.read_bytes()
            except FileNotFoundError:
                now = None
            except OSError:
                continue  # unreadable now: the save will say so
            if now != state.stamp:
                changed.append(scope)
        return changed

    def why_read_only(self, scope: Scope | None = None) -> str | None:
        """Why this file cannot be changed from here, or ``None`` if it can."""
        scope = scope or self.scope
        state = self.files[scope]
        if state.ini is None:
            return f"{state.error}. Fix it by hand, or replace it with init --force."
        path = store.target_of(state.path)
        directory = path.parent
        while not directory.exists() and directory != directory.parent:
            directory = directory.parent
        if (path.exists() and not os.access(path, os.W_OK)) or not os.access(
            directory, os.W_OK | os.X_OK
        ):
            if scope == "system":
                return "It needs root: sudo tkcurses-cfg."
            return f"You cannot write to {directory}."
        return None

    # ------------------------------------------------------------ values

    def file_value(
        self, setting: Setting | str, scope: Scope | None = None
    ) -> str | None:
        """The value this file holds with the pending edits made - an edit
        the file refuses for now included, so the person sees what they
        asked for."""
        scope = scope or self.scope
        name = setting if isinstance(setting, str) else setting.name
        if name in self.pending[scope]:
            return self.pending[scope][name]
        ini = self.edited[scope]
        entry = None if ini is None else ini.get(name)
        return None if entry is None else entry.value

    def saved_value(self, name: str, scope: Scope | None = None) -> str | None:
        """The value the file holds on disk, without the pending edits."""
        ini = self.files[scope or self.scope].ini
        entry = None if ini is None else ini.get(name)
        return None if entry is None else entry.value

    def winner(self, setting: Setting) -> Origin:
        return self.config.source(setting.name)

    def inherited(self, setting: Setting, scope: Scope | None = None) -> Origin:
        """Where the value would come from if this file did not set it -
        ignoring the environment and any file that outranks this one."""
        below = (
            {"default"}
            if (scope or self.scope) == "system"
            else {"default", str(self.system)}
        )
        applied = [
            o
            for o in self.config.origins[setting.name]
            if o.applied and (o.kind if o.kind == "default" else o.location) in below
        ]
        return applied[-1]

    def starting_value(self, setting: Setting) -> object:
        """What an edit of ``setting`` starts from: this file's value if it
        has a valid one, else what it inherits."""
        raw = self.file_value(setting)
        if raw is not None:
            try:
                return setting.parse(raw)
            except InvalidValue:
                pass
        return self.inherited(setting).value

    # ----------------------------------------------------------- editing

    def set(self, name: str, raw: str) -> None:
        """Set ``name`` to ``raw`` in the file being edited.

        Raises:
            UnknownSetting, InvalidSettingValue: as ``tkcurses-cfg set``.
        """
        setting = lookup(name)
        try:
            value = setting.parse(raw)
        except InvalidValue as exc:
            raise InvalidSettingValue(
                f"{setting.name}: {exc}; it takes {describe_values(setting)}"
            ) from None
        pending = self.pending[self.scope]
        saved = self.saved_value(setting.name)
        if saved is not None and _parses_to(setting, saved, value):
            pending.pop(setting.name, None)  # back to what the file holds
        else:
            pending[setting.name] = setting.format(value)
        self._refresh()

    def toggle(self, name: str) -> None:
        """Switch a true/false setting. Switching back to where it started
        is no change at all - not an explicit line holding the inherited
        value, which would stop it following the files below."""
        setting = BY_NAME[name]
        assert setting.kind == "bool"
        new = not self.starting_value(setting)
        pending = self.pending[self.scope]
        if (
            self.saved_value(name) is None
            and name in pending
            and new == self.inherited(setting).value
        ):
            self.revert(name)
            return
        self.set(name, setting.format(new))

    def unset(self, name: str) -> None:
        """Take ``name`` out of the file being edited."""
        pending = self.pending[self.scope]
        if self.saved_value(name) is None:
            pending.pop(name, None)
        else:
            pending[name] = None
        self._refresh()

    def revert(self, name: str) -> None:
        self.pending[self.scope].pop(name, None)
        self._refresh()

    def changes(self) -> list[Change]:
        return [
            Change(scope, name, self.saved_value(name, scope), after)
            for scope in SCOPES
            for name, after in self.pending[scope].items()
        ]

    def problems(self, scope: Scope | None = None) -> list[Problem]:
        """What is wrong with the file, with the pending edits made - so
        a problem goes from the list as soon as an edit fixes it."""
        ini = self.edited[scope or self.scope]
        return [] if ini is None else ini.problems()

    # ------------------------------------------------------------ saving

    def save(self, scope: Scope, timeout: float = 5.0) -> store.Saved:
        """Write this file's pending edits, to the file as it is now.

        The pending edits stay if anything goes wrong.

        Raises:
            CfgError: as ``tkcurses-cfg set`` would, with nothing written.
        """
        edits = dict(self.pending[scope])
        hint = (
            "The system-wide file needs root: run sudo tkcurses-cfg"
            if scope == "system"
            else None
        )
        saved = store.edit(
            self.path(scope),
            lambda ini: _apply(ini, edits, strict=True)[0],
            timeout=timeout,
            admin_hint=hint,
        )
        self.pending[scope] = {}
        self.reload(scope)
        return saved

    # ---------------------------------------------------------- internal

    def _refresh(self) -> None:
        for scope in SCOPES:
            ini = self.files[scope].ini
            if ini is None:
                self.edited[scope], self.refused[scope] = None, {}
            else:
                self.edited[scope], self.refused[scope] = _apply(
                    ini, self.pending[scope], strict=False
                )
        self.config = self._preview()

    def _preview(self) -> TkCursesConfig:
        """What a program would use, were the pending edits saved."""
        with tempfile.TemporaryDirectory(prefix="tkcurses-cfg-") as directory:
            paths: list[Path] = []
            real: dict[str, str] = {}
            for scope in ("system", "user"):
                state, edited = self.files[scope], self.edited[scope]
                if edited is None or not self.pending[scope]:
                    paths.append(state.path)  # as a program would meet it
                    continue
                copy = Path(directory) / f"{scope}.ini"
                copy.write_text(edited.text, encoding="utf-8", newline="")
                paths.append(copy)
                real[str(copy)] = str(state.path)
            config = TkCursesConfig.load(paths=tuple(paths), env=dict(self.env))
        for name, origins in config.origins.items():
            config.origins[name] = [
                dataclasses.replace(o, location=real[o.location])
                if o.location in real
                else o
                for o in origins
            ]
        for copied, original in real.items():
            config.warnings = [w.replace(copied, original) for w in config.warnings]
        return config


def _read(path: Path) -> FileState:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return FileState(path, IniFile(str(path), [], [], []), None, None)
    except OSError as exc:
        return FileState(path, None, f"{path} cannot be read: {exc.strerror}", None)
    try:
        return FileState(path, IniFile.from_bytes(data, path), None, data)
    except FileSyntaxError as exc:
        return FileState(path, None, str(exc), data)


def _parses_to(setting: Setting, raw: str, value: object) -> bool:
    try:
        return bool(setting.parse(raw) == value)
    except InvalidValue:
        return False


def _apply(
    ini: IniFile, edits: Mapping[str, str | None], *, strict: bool
) -> tuple[IniFile, dict[str, str]]:
    """``ini`` with ``edits`` made, those that fix a bad value first, so
    that a batch which repairs the file is accepted as a whole.

    With ``strict``, the first refusal is raised; without, each refused
    edit is left out and returned with its reason.
    """
    fixes = {p.name for p in ini.problems() if p.blocking}
    order = sorted(edits, key=lambda name: name not in fixes)
    refused: dict[str, str] = {}
    for name in order:
        value = edits[name]
        try:
            ini = ini.unset(name) if value is None else ini.set(name, value)
        except CfgError as exc:
            if strict:
                raise
            refused[name] = str(exc)
    return ini, refused
