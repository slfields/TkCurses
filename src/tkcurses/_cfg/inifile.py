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

"""A configuration file as its lines, edited without disturbing the rest.

``configparser`` reads a file into a dictionary and writes it back as one,
which drops every comment and rewrites every line. A person's hand-written
file deserves better, so this keeps the file as its lines and changes only
the one an edit is about: comments, blank lines, order, spacing and line
endings come back byte for byte.

**The grammar is a strict subset of what programs read.** A program reads
the file with ``configparser`` (``_core/config.py``), so a file is only
edited when this module and ``configparser`` would read it identically -
``tests/test_cfg_inifile.py`` holds that over generated files, on every
Python CI runs. Where ``configparser`` is lenient in a way that could
surprise, this refuses the file instead, naming the line:

- a value that continues onto an indented line - every setting is one value;
- a ``[DEFAULT]`` section, whose keys ``configparser`` puts in every section;
- a section header with anything after its ``]``, a key with spaces in it,
  a line with no ``=`` or ``:``, a setting before any section;
- the same section twice, or the same key twice in a section, which
  ``configparser`` refuses too - and a program then ignores the whole file;
- text that is not UTF-8, or starts with a byte order mark.

What is readable but wrong is a :class:`~tkcurses._cfg.errors.Problem`
instead: a value of the wrong type or out of range, an unknown section or
key, a setting that was removed. Only the first kind stops an edit, and not
an edit that fixes it.
"""

from __future__ import annotations

import difflib
import re
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tkcurses._cfg.errors import (
    BlockedByProblems,
    FileSyntaxError,
    InvalidSettingValue,
    Problem,
    UnknownSetting,
)
from tkcurses._core.config import (
    BY_NAME,
    REMOVED,
    SECTIONS,
    SETTINGS,
    InvalidValue,
    Setting,
)

if TYPE_CHECKING:
    from pathlib import Path

#: Where a line ends, as Python's text files see it: a program's
#: ``configparser`` reads through one, so ``\r`` alone ends a line there too.
_NEWLINE = re.compile(r"\r\n|\r|\n")

#: The comment on a line, as ``configparser`` finds it with ``;`` and ``#``
#: as both whole-line and inline prefixes: one of them at the start, or
#: after whitespace, to the end of the line.
_COMMENT = re.compile(r"(^|\s)[#;].*")

_HEADER = re.compile(r"\[([^\[\]]+)\]")
_OPTION = re.compile(r"(?P<key>[A-Za-z0-9_.\-]+)\s*(?P<delim>[=:])\s*(?P<value>.*)")

_REMOVED_BY_NAME = {f"{r.section}.{r.key}": r for r in REMOVED}
_REMOVED_SECTIONS = {r.section for r in REMOVED} - set(SECTIONS)


@dataclass(frozen=True)
class Entry:
    """One ``key = value`` line."""

    #: Index into :attr:`IniFile.lines`.
    index: int
    section: str
    #: As written; matched in any case, as ``configparser`` does.
    key: str
    #: As a program reads it: no surrounding space, no comment.
    value: str
    #: Where the value is within the line, so an edit replaces only it.
    start: int
    end: int

    @property
    def name(self) -> str:
        return f"{self.section}.{self.key.lower()}"

    @property
    def line(self) -> int:
        return self.index + 1


@dataclass(frozen=True)
class _Content:
    """A line that is a header or a setting, which is what indentation is
    measured against."""

    index: int
    indent: int
    is_option: bool
    section: str


def split_name(name: str) -> tuple[str, str]:
    """``section.key`` as its section, as written, and its key, lowered."""
    section, dot, key = name.partition(".")
    if not dot or not section or not key:
        raise UnknownSetting(f"{name!r} is not a setting name: they are section.key")
    return section, key.lower()


def describe_values(setting: Setting) -> str:
    """What a setting takes, for a message."""
    if setting.kind == "bool":
        return "true or false"
    if setting.kind == "int":
        assert setting.limits is not None
        low, high = setting.limits
        of = f" of {setting.unit_name}" if setting.unit_name else ""
        return f"a whole number{of} from {low} to {high}"
    assert setting.choices is not None
    return "one of " + ", ".join(setting.choices)


def lookup(name: str) -> Setting:
    """The setting called ``name``, or a message saying what was meant."""
    section, key = split_name(name)
    setting = BY_NAME.get(f"{section}.{key}")
    if setting is not None:
        return setting
    removed = _REMOVED_BY_NAME.get(f"{section}.{key}")
    if removed is not None:
        raise UnknownSetting(
            f"{name} no longer exists: {_plain(removed.why)}. "
            f"Use 'unset {name}' to take it out of a file."
        )
    raise UnknownSetting(f"there is no setting {name}{_suggest(f'{section}.{key}')}")


def _suggest(name: str) -> str:
    close = difflib.get_close_matches(name, list(BY_NAME), n=1, cutoff=0.6)
    if not close:
        section, _, key = name.partition(".")
        close = [s.name for s in SETTINGS if s.key == key and s.section != section]
    return f"; did you mean {close[0]}?" if close else ""


def _plain(text: str) -> str:
    """A description's ````literal```` marks taken out, for a terminal."""
    return text.replace("``", "")


class IniFile:
    """A configuration file, checked, as lines that can be edited in place."""

    def __init__(
        self, path: str, lines: list[str], entries: list[Entry], sections: list[str]
    ) -> None:
        self.path = path
        #: Every line with its own ending; the last may have none.
        self.lines = lines
        self.entries = entries
        #: Section names in the order they appear.
        self.sections = sections

    # ------------------------------------------------------------ reading

    @classmethod
    def read(cls, path: Path) -> IniFile:
        """The file at ``path``; empty if there is none.

        Raises:
            FileSyntaxError: the file cannot be read as a configuration.
            OSError: it cannot be read at all.
        """
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return cls(str(path), [], [], [])
        return cls.from_bytes(data, path)

    @classmethod
    def from_bytes(cls, data: bytes, path: Path) -> IniFile:
        """The file whose contents are ``data``, as :meth:`read` checks it.

        Raises:
            FileSyntaxError: ``data`` cannot be read as a configuration.
        """
        if data.startswith(b"\xef\xbb\xbf"):
            raise FileSyntaxError(
                str(path),
                1,
                "starts with a byte order mark, which a program reads as "
                "part of the first line; save it as UTF-8 without one",
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            line = data.count(b"\n", 0, exc.start) + 1
            raise FileSyntaxError(str(path), line, "is not UTF-8 text") from None
        return cls.parse(text, str(path))

    @classmethod
    def parse(cls, text: str, path: str = "<text>") -> IniFile:
        """``text`` as a configuration file.

        Raises:
            FileSyntaxError: it is not one this module will edit; the
                message names the line and why.
        """
        lines = _split(text)
        entries: list[Entry] = []
        sections: dict[str, int] = {}
        keys: dict[tuple[str, str], int] = {}
        section: str | None = None
        option: _Content | None = None
        for index, line in enumerate(lines):
            number = index + 1
            body = _body(line)
            trimmed = body.strip()
            clean = _COMMENT.sub("", trimmed, count=1).rstrip()
            if not clean:
                continue
            indent = len(body) - len(body.lstrip())
            if option is not None and indent > option.indent:
                raise FileSyntaxError(
                    path,
                    number,
                    "is indented further than the setting on line "
                    f"{option.index + 1}, so a program reads it as more of that "
                    "setting's value; each setting's value must be on its own "
                    "line",
                )
            if clean.startswith("["):
                header = _HEADER.fullmatch(clean)
                if header is None:
                    raise FileSyntaxError(
                        path,
                        number,
                        "is not a section header: write [name] alone on the line",
                    )
                section = header.group(1)
                if section == "DEFAULT":
                    raise FileSyntaxError(
                        path,
                        number,
                        "[DEFAULT] sets its keys in every section; name each "
                        "setting's own section instead",
                    )
                if section in sections:
                    raise FileSyntaxError(
                        path,
                        number,
                        f"[{section}] appears again (first on line "
                        f"{sections[section]}); a program ignores the whole file",
                    )
                sections[section] = number
                option = None
                continue
            if section is None:
                raise FileSyntaxError(path, number, "comes before any [section] header")
            match = _OPTION.fullmatch(clean)
            if match is None:
                raise FileSyntaxError(
                    path,
                    number,
                    "is not a setting: write name = value, with no spaces in the name",
                )
            key = match.group("key")
            lowered = (section, key.lower())
            if lowered in keys:
                raise FileSyntaxError(
                    path,
                    number,
                    f"{key} is set again in [{section}] (first on line "
                    f"{keys[lowered]}); a program ignores the whole file",
                )
            keys[lowered] = number
            offset = len(body) - len(body.lstrip())
            start = offset + match.start("value")
            value = match.group("value")
            entries.append(Entry(index, section, key, value, start, start + len(value)))
            option = _Content(index, indent, True, section)
        return cls(path, lines, entries, list(sections))

    @property
    def text(self) -> str:
        return "".join(self.lines)

    def get(self, name: str) -> Entry | None:
        """The line setting ``name``, if the file has one."""
        section, key = split_name(name)
        for entry in self.entries:
            if entry.section == section and entry.key.lower() == key:
                return entry
        return None

    # ----------------------------------------------------------- checking

    def problems(self) -> list[Problem]:
        """What is wrong with the file's contents, in line order."""
        found: list[Problem] = []
        for section in self.sections:
            if section in SECTIONS or section in _REMOVED_SECTIONS:
                continue
            close = difflib.get_close_matches(
                section.strip().lower(), list(SECTIONS), n=1, cutoff=0.6
            )
            hint = f"; did you mean [{close[0]}]?" if close else ""
            found.append(
                Problem(
                    self._header_line(section),
                    section,
                    "unknown-section",
                    f"[{section}] is not a section a program reads{hint}",
                )
            )
        for entry in self.entries:
            name = entry.name
            setting = BY_NAME.get(name)
            if setting is not None:
                try:
                    setting.parse(entry.value)
                except InvalidValue as exc:
                    found.append(
                        Problem(
                            entry.line,
                            name,
                            "invalid",
                            f"{exc}; it takes {describe_values(setting)}",
                        )
                    )
                continue
            removed = _REMOVED_BY_NAME.get(name)
            if removed is not None:
                found.append(
                    Problem(
                        entry.line,
                        name,
                        "removed",
                        f"no longer has any effect: {_plain(removed.why)}",
                    )
                )
                continue
            if entry.section in SECTIONS or entry.section in _REMOVED_SECTIONS:
                found.append(
                    Problem(
                        entry.line,
                        name,
                        "unknown-key",
                        f"is not a setting{_suggest(name)}",
                    )
                )
        return sorted(found, key=lambda p: p.line)

    def _header_line(self, section: str) -> int:
        for index, line in enumerate(self.lines):
            header = _HEADER.fullmatch(
                _COMMENT.sub("", _body(line).strip(), count=1).rstrip()
            )
            if header is not None and header.group(1) == section:
                return index + 1
        raise AssertionError(section)

    def _refuse_unless_fixed(self, name: str) -> None:
        blocking = [p for p in self.problems() if p.blocking and p.name != name]
        if blocking:
            raise BlockedByProblems(self.path, blocking)

    # ------------------------------------------------------------ editing

    def set(self, name: str, raw: str) -> IniFile:
        """A copy with ``name`` set to ``raw``.

        The value is written as :meth:`Setting.format` writes it, so
        `` YES `` is stored as ``true``. An existing line keeps its key's
        spelling, its spacing and its comment; a new one goes where a
        commented-out line for the setting is, if there is one, else after
        the section's last setting, else in a new section at the end.

        Raises:
            UnknownSetting: ``name`` is not a setting.
            InvalidSettingValue: ``raw`` is not one of its values, or the
                file holds another value that is not valid.
        """
        setting = lookup(name)
        try:
            value = setting.parse(raw)
        except InvalidValue as exc:
            raise InvalidSettingValue(
                f"{setting.name}: {exc}; it takes {describe_values(setting)}"
            ) from None
        self._refuse_unless_fixed(setting.name)
        text = setting.format(value)
        lines = list(self.lines)
        entry = self.get(setting.name)
        if entry is not None:
            body, ending = _body(lines[entry.index]), _ending(lines[entry.index])
            if not entry.value and body[entry.start - 1 : entry.start] in ("=", ":"):
                text = " " + text
            lines[entry.index] = body[: entry.start] + text + body[entry.end :] + ending
        elif setting.section in self.sections:
            at, replace = self._place(setting)
            indent = self._indent_at(at, replace)
            new = " " * indent + f"{setting.key} = {text}" + self._eol()
            if replace:
                lines[at] = new
            else:
                if at > 0 and not _ending(lines[at - 1]):
                    lines[at - 1] += self._eol()
                lines.insert(at, new)
        else:
            if lines and not _ending(lines[-1]):
                lines[-1] += self._eol()
            if lines and _body(lines[-1]).strip():
                lines.append(self._eol())
            lines += [f"[{setting.section}]" + self._eol()]
            lines += [f"{setting.key} = {text}" + self._eol()]
        return self._verified(lines, setting.name, text.strip())

    def unset(self, name: str) -> IniFile:
        """A copy without ``name``'s line, so the setting comes from
        elsewhere. Any name the file has can be taken out - a removed or
        unknown one too, which is how a file is cleaned up.

        Raises:
            UnknownSetting: ``name`` is neither a setting nor in the file.
            InvalidSettingValue: the file holds another value that is not
                valid.
        """
        entry = self.get(name)
        if entry is None:
            lookup(name)  # a real setting with nothing to take out is fine
            return self
        self._refuse_unless_fixed(entry.name)
        lines = list(self.lines)
        del lines[entry.index]
        return self._verified(lines, entry.name, None)

    def _place(self, setting: Setting) -> tuple[int, bool]:
        """Where a new line for ``setting`` goes, and whether it replaces
        the line there (a commented-out one) rather than going before it."""
        section: str | None = None
        last = -1
        commented = re.compile(
            rf"\s*[;#]\s*{re.escape(setting.key)}\s*[=:]", re.IGNORECASE
        )
        for index, line in enumerate(self.lines):
            clean = _COMMENT.sub("", _body(line).strip(), count=1).rstrip()
            header = _HEADER.fullmatch(clean) if clean else None
            if header is not None:
                section = header.group(1)
                if section == setting.section:
                    last = index
                continue
            if section != setting.section:
                continue
            if clean:
                last = index
            elif commented.match(_body(line)):
                return index, True
        return last + 1, False

    def _indent_at(self, at: int, replace: bool) -> int:
        """An indentation that makes a new setting line at ``at`` part of
        neither its neighbour's value nor make its next one part of its own:
        the setting before it, if that is one, else the next line's."""
        before = self._content(range(at - 1, -1, -1))
        after = self._content(range(at + 1 if replace else at, len(self.lines)))
        if before is not None and before.is_option:
            return before.indent
        return after.indent if after is not None else 0

    def _content(self, indexes: range) -> _Content | None:
        for index in indexes:
            body = _body(self.lines[index])
            clean = _COMMENT.sub("", body.strip(), count=1).rstrip()
            if clean:
                indent = len(body) - len(body.lstrip())
                return _Content(index, indent, not clean.startswith("["), "")
        return None

    def _eol(self) -> str:
        for line in self.lines:
            ending = _ending(line)
            if ending:
                return ending
        return "\n"

    def _verified(self, lines: list[str], name: str, value: str | None) -> IniFile:
        """The edited file, read back to prove the edit is the one meant."""
        edited = IniFile.parse("".join(lines), self.path)
        entry = edited.get(name)
        got = None if entry is None else entry.value
        if got != value:  # pragma: no cover - a bug here, not a user error
            raise AssertionError(f"editing {name} read back {got!r}, not {value!r}")
        return edited


def starter_text() -> str:
    """A file with every setting at its default, commented out, each with
    what it does - what ``tkcurses-cfg init`` writes."""
    out = [
        "; TkCurses configuration.",
        ";",
        "; Every setting is here at its default, commented out. To change one,",
        "; take the ; off the front of its line and edit the value, or run",
        ";     tkcurses-cfg set section.key value",
        "; A TKCURSES_* environment variable overrides what this file says.",
    ]
    current = None
    for setting in SETTINGS:
        if setting.section != current:
            current = setting.section
            out += ["", f"[{current}]"]
        out.append("")
        out += textwrap.wrap(
            _plain(setting.description),
            width=76,
            initial_indent="; ",
            subsequent_indent="; ",
        )
        out.append(
            f"; Takes {describe_values(setting)}. "
            f"Environment variable: {setting.variable}"
        )
        out.append(f";{setting.key} = {setting.format(setting.default)}")
    return "\n".join(out) + "\n"


def _split(text: str) -> list[str]:
    lines: list[str] = []
    start = 0
    for match in _NEWLINE.finditer(text):
        lines.append(text[start : match.end()])
        start = match.end()
    if start < len(text):
        lines.append(text[start:])
    return lines


def _body(line: str) -> str:
    return line.rstrip("\r\n")


def _ending(line: str) -> str:
    return line[len(_body(line)) :]
