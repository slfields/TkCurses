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

"""``tkcurses-cfg`` with no command: a screen for looking and editing.

Plain curses, deliberately: this screen must work when the configuration
it is there to repair is the reason TkCurses programs misbehave, so it
reads no TkCurses setting for its own drawing. Keyboard only. Every rule
lives in :class:`.session.Session`; this module draws it and turns keys
into calls.
"""

from __future__ import annotations

import contextlib
import curses
import os
import signal
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tkcurses._cfg.cli import show
from tkcurses._cfg.errors import CfgError
from tkcurses._cfg.inifile import describe_values
from tkcurses._cfg.session import SCOPES, Change, Scope, Session
from tkcurses._core.config import (
    BY_NAME,
    SECTIONS,
    SETTINGS,
    InvalidValue,
    OutOfRange,
    Setting,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from tkcurses._cfg.errors import Problem
    from tkcurses._core.config import Origin

MIN_COLS, MIN_ROWS = 60, 15

#: Seconds between looks at the disk for a file changed by something else.
POLL = 1.0

ENTER = (10, 13, curses.KEY_ENTER)
ESCAPE = 27
CONTROL_L = 12

SCOPE_NAMES = {"user": "your file", "system": "the system-wide file"}

HELP = """\
Each row is one setting. IN THIS FILE is what the file you are editing
says; IN EFFECT is what a program would use, and FROM is where that comes
from: default, system (the system-wide file), user (your file) or
environment (a TKCURSES_ variable in this shell, which outranks both files
and is not something this screen changes).

Nothing is written until you save. A changed row is marked *, and one the
file will not take as it stands, !.

  Up Down PgUp PgDn Home End   move (also k j)
  Enter        change the value: a list of choices, or a number
  Space        switch a true/false setting
  u            take the setting out of this file
  r            undo this row's change
  Tab          edit the other file: yours or the system-wide one
  s            save: shows every change and asks first
  p            problems in this file, and how to fix them
  i            everything about this setting
  ?            this help
  q            quit; asks first if anything is not saved

Values are typed without their unit: 50, not 50 ms. Ctrl-C quits at once,
discarding unsaved changes."""


class _Terminated(Exception):
    """SIGTERM or SIGHUP while the screen was up."""


def run(
    system: Path,
    user: Path,
    *,
    scope: Scope = "user",
    user_label: str = "user",
    timeout: float = 10.0,
) -> int:
    """Show the screen until the person quits; return the exit status.

    Args:
        scope: The file it opens on: ``user``, or ``system`` for
            ``--global``.
        user_label: ``user``, or ``file`` when ``--file`` named the file
            that stands in for the person's own, as the command shows it.
        timeout: Seconds a save waits for another ``tkcurses-cfg``.
    """
    session = Session(system, user, scope=scope)
    os.environ.setdefault("ESCDELAY", "25")  # Escape closes a dialog at once

    def terminated(signum: int, _frame: Any) -> None:
        raise _Terminated(signum)

    previous = {
        sig: signal.signal(sig, terminated) for sig in (signal.SIGTERM, signal.SIGHUP)
    }
    try:
        return int(
            curses.wrapper(
                lambda stdscr: Screen(
                    stdscr, session, user_label=user_label, timeout=timeout
                ).loop()
            )
        )
    except (KeyboardInterrupt, _Terminated):
        lost = len(session.changes())
        tail = f"; {lost} unsaved change{'s' * (lost != 1)} discarded" if lost else ""
        print(f"tkcurses-cfg: interrupted{tail}", file=sys.stderr)
        return 130
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@dataclass
class _Row:
    section: str
    setting: Setting | None  # None for the section's heading


class Screen:
    """The main list, its details, and the dialogs over it."""

    def __init__(
        self,
        stdscr: Any,
        session: Session,
        *,
        user_label: str = "user",
        timeout: float = 10.0,
    ) -> None:
        self.scr = stdscr
        self.session = session
        self.user_label = user_label
        self.timeout = timeout
        own = "your file" if user_label == "user" else "the given file"
        self.names: dict[Scope, str] = {"user": own, "system": SCOPE_NAMES["system"]}
        self.rows = [
            row
            for section in SECTIONS
            for row in (
                _Row(section, None),
                *(_Row(section, s) for s in SETTINGS if s.section == section),
            )
        ]
        self.current = 1  # the first setting, under the first heading
        self.top = 0
        self.message = ""
        self.message_bad = False
        self.attr = _Attributes()
        self.scr.keypad(True)
        self.scr.timeout(int(POLL * 1000))
        _cursor(0)

    # ------------------------------------------------------------- loop

    def loop(self) -> int:
        while True:
            self.draw()
            key = self.key()
            if key == -1:
                self._poll_disk()
                continue
            if key == curses.KEY_RESIZE:
                continue
            self.message = ""
            if self.too_small():
                if key in (ord("q"), ESCAPE) and self.quit():
                    return 0
                continue
            if key == ord("q") and self.quit():
                return 0
            self.handle(key)

    def handle(self, key: int) -> None:
        setting = self.setting
        if key in (curses.KEY_DOWN, ord("j")):
            self.move(1)
        elif key in (curses.KEY_UP, ord("k")):
            self.move(-1)
        elif key == curses.KEY_NPAGE:
            self.move(max(1, self.list_height() - 1))
        elif key == curses.KEY_PPAGE:
            self.move(-max(1, self.list_height() - 1))
        elif key in (curses.KEY_HOME, ord("g")):
            self.move(-len(self.rows))
        elif key in (curses.KEY_END, ord("G")):
            self.move(len(self.rows))
        elif key in (9, curses.KEY_BTAB):
            self.session.scope = "system" if self.session.scope == "user" else "user"
            why = self.session.why_read_only()
            if why:
                self.say(
                    f"{self._titled(self.session.scope)}: read-only. {why}", bad=True
                )
            else:
                self.say(f"Now editing {self._scope_title()}.")
        elif key in ENTER:
            self.edit(setting)
        elif key == ord(" "):
            if setting.kind == "bool":
                self.edit(setting)
            else:
                self.say("Space switches true/false settings; Enter changes this one.")
        elif key == ord("u"):
            self.unset(setting)
        elif key == ord("r"):
            if setting.name in self.session.pending[self.session.scope]:
                self.session.revert(setting.name)
                self.say(f"{setting.name}: change undone.")
            else:
                self.say(f"{setting.name} has no change to undo.")
        elif key == ord("s"):
            self.save()
        elif key == ord("p"):
            self.problems()
        elif key == ord("i"):
            self.info(setting)
        elif key == ord("?"):
            self.show_text("Help", HELP)
        elif key == CONTROL_L:
            self.scr.clear()
        else:
            self.say("That key does nothing here; ? lists the keys.", bad=True)

    def key(self) -> int:
        """The next key, or -1 after :data:`POLL` seconds of none.

        A resize is applied here, wherever the key is read: ``getmaxyx()``
        stays at the old size until ``resize_term()`` is given the size the
        terminal now reports, and a terminal that shrank has scrolled what
        it showed, so the next update must repaint every cell - the same
        two facts TkCurses' own screen works from (``Screen.handle_resize``).
        """
        key = int(self.scr.getch())
        if key == curses.KEY_RESIZE:
            size = os.get_terminal_size()
            with contextlib.suppress(curses.error):
                curses.resize_term(size.lines, size.columns)
            self.scr.clearok(True)
        return key

    # ---------------------------------------------------------- actions

    @property
    def setting(self) -> Setting:
        setting = self.rows[self.current].setting
        assert setting is not None
        return setting

    def move(self, by: int) -> None:
        step = 1 if by > 0 else -1
        index, left = self.current, abs(by)
        while left:
            candidate = index + step
            if not 0 <= candidate < len(self.rows):
                break
            index = candidate
            if self.rows[index].setting is not None:
                self.current = index
                left -= 1

    def say(self, text: str, *, bad: bool = False) -> None:
        self.message, self.message_bad = text, bad

    def read_only(self) -> bool:
        why = self.session.why_read_only()
        if why:
            self.say(
                f"{self._scope_title().capitalize()} cannot be changed. {why}", bad=True
            )
        return bool(why)

    def edit(self, setting: Setting) -> None:
        if self.read_only():
            return
        if setting.kind == "bool":
            self.session.toggle(setting.name)
            self._report_edit(setting.name)
            return
        number = setting.kind == "int"
        raw = self.number(setting) if number else self.pick(setting)
        if raw is None:
            return
        try:
            self.session.set(setting.name, raw)
        except CfgError as exc:  # the dialogs only return values that parse
            self.say(str(exc), bad=True)
            return
        self._report_edit(setting.name)

    def _report_edit(self, name: str) -> None:
        setting = BY_NAME.get(name)
        pending = self.session.pending[self.session.scope]
        if setting is None or pending.get(name, "") is None:
            shown = "taken out"
        else:
            shown = self._file_shown(setting)
        if name in self.session.refused[self.session.scope]:
            self.say(
                f"{name}: {shown} - cannot be saved while this file has a bad "
                "value; p shows it.",
                bad=True,
            )
        else:
            self.say(f"{name}: {shown} - not saved yet.")

    def unset(self, setting: Setting | str) -> None:
        name = setting if isinstance(setting, str) else setting.name
        if self.read_only():
            return
        if self.session.saved_value(name) is None:
            if name in self.session.pending[self.session.scope]:
                self.session.revert(name)
                self.say(
                    f"{name}: change undone; {self._scope_title()} does not set it."
                )
            else:
                self.say(f"{self._scope_title().capitalize()} does not set {name}.")
            return
        self.session.unset(name)
        self._report_edit(name)

    def save(self) -> bool:
        """Confirm and save every change; whether everything was saved."""
        session = self.session
        if not session.changes():
            self.say("Nothing to save.")
            return True
        note = ""
        moved = [s for s in session.changed_on_disk() if session.pending[s]]
        for scope in moved:
            session.reload(scope)
            note = (
                f"{self._titled(scope)} changed on disk since it was read. Your changes "
                "are shown against what it holds now.\n\n"
            )
        for scope in SCOPES:
            if session.pending[scope] and session.refused[scope]:
                reason = next(iter(session.refused[scope].values()))
                self.show_text(
                    "Cannot save",
                    f"{reason}\n\nYour changes are kept. p lists the problems "
                    "and fixes them.",
                )
                return False
        if not self.confirm_changes(note):
            self.say("Not saved; your changes are kept.")
            return False
        saved: list[str] = []
        for scope in SCOPES:
            if not session.pending[scope]:
                continue
            count = len(session.pending[scope])
            self.say(f"Saving {self._titled(scope).lower()}...")
            self.draw()
            self.scr.refresh()
            try:
                result = session.save(scope, self.timeout)
            except CfgError as exc:
                self.show_text(
                    "Not saved", f"{exc}\n\nYour changes are kept; save again to retry."
                )
                return False
            line = f"{count} change{'s' * (count != 1)} to {show(session.path(scope))}"
            if result.backup is not None:
                line += f" (the old one is {show(result.backup)})"
            saved.append(line)
            for warning in result.warnings:
                self.show_text("Saved, with a warning", warning)
        self.say("Saved " + "; ".join(saved) + ".")
        return True

    def quit(self) -> bool:
        changes = len(self.session.changes())
        if not changes:
            return True
        plural = "s" * (changes != 1)
        key = self.ask(
            "Unsaved changes",
            f"{changes} change{plural} not saved.",
            {"s": "save and quit", "d": "discard and quit", "Esc": "keep editing"},
        )
        if key == "s":
            return self.save()
        return key == "d"

    def problems(self) -> None:
        """List what is wrong with this file and offer the fix for each."""
        session = self.session
        state = session.files[session.scope]
        if state.ini is None:
            self.show_text(
                "Problems",
                f"{state.error}\n\nThis screen cannot change a file it cannot "
                "read. Fix it by hand, or replace it: tkcurses-cfg init --force "
                "(--global for the system-wide file) keeps the old one as .bak.",
            )
            return
        index = 0
        while True:
            found = session.problems()
            if not found:
                self.say(f"No problems in {self._scope_title()}.")
                return
            index = min(index, len(found) - 1)
            items = [f"line {p.line}: {p.name}" for p in found]

            def keys(at: int, found: list[Problem] = found) -> dict[str, str]:
                kind = found[at].kind
                if kind == "invalid":
                    return {"Enter": "change it", "u": "take it out", "Esc": "close"}
                if kind == "unknown-section":
                    return {"Enter": "how to fix", "Esc": "close"}
                return {"Enter": "take it out", "Esc": "close"}

            choice = self.choose(
                f"Problems in {self._scope_title()}",
                items,
                index,
                keys,
                detail=lambda at: found[at].message,  # noqa: B023 - used at once
            )
            if choice is None:
                return
            index, key = choice
            problem = found[index]
            if problem.kind == "unknown-section":
                self.show_text(
                    "Fix by hand",
                    f"{problem.message}. This screen changes settings, not "
                    f"sections: remove line {problem.line} of "
                    f"{show(state.path)} and the lines under it by hand.",
                )
            elif problem.kind == "invalid" and key != "u":
                self.edit(BY_NAME[problem.name])
            else:
                self.unset(problem.name)

    # ---------------------------------------------------------- dialogs

    def pick(self, setting: Setting) -> str | None:
        assert setting.choices is not None
        start = self.session.starting_value(setting)
        choices = list(setting.choices)
        index = choices.index(str(start)) if str(start) in choices else 0
        items = [
            choice + ("   (now)" if choice == str(start) else "") for choice in choices
        ]
        picked = self.choose(
            setting.name, items, index, {"Enter": "choose", "Esc": "cancel"}
        )
        return None if picked is None else choices[picked[0]]

    def number(self, setting: Setting) -> str | None:
        """A field that takes a whole number in range, or ``None`` if cancelled."""
        assert setting.limits is not None
        low, high = setting.limits
        text = str(self.session.starting_value(setting))
        cursor = len(text)
        while True:
            problem = ""
            try:
                setting.parse(text)
            except InvalidValue as exc:
                problem = str(exc) if text else "type a number"
            lines = textwrap.wrap(f"Takes {describe_values(setting)}.", 40)
            box = self._dialog(
                setting.name,
                [*lines, "", "", problem or " "],
                {"Enter": "set", "Up Down": "+1 -1", "Esc": "cancel"},
                bad_line=len(lines) + 2 if problem else None,
            )
            if box is None:
                key = self.key()
                if key == ESCAPE:
                    return None
                continue
            top, left, _ = box
            row = top + 1 + len(lines) + 1
            field = 12
            shown = text[-field:]
            self._put(row, left + 2, "[" + shown.ljust(field) + "]", curses.A_UNDERLINE)
            if setting.unit:
                self._put(row, left + 4 + field + 1, setting.unit)
            _cursor(1)
            self.scr.move(row, left + 3 + min(cursor, field))
            key = self.key()
            _cursor(0)
            if key in (-1, curses.KEY_RESIZE):
                continue
            if key == ESCAPE:
                return None
            if key in ENTER:
                if not problem:
                    return text
                continue
            if key in (curses.KEY_UP, curses.KEY_DOWN):
                try:
                    value = setting.parse(text)
                except OutOfRange as exc:
                    value = exc.clamped  # from past the end: start at the end
                except InvalidValue:
                    value = low
                step = 1 if key == curses.KEY_UP else -1
                text = str(min(high, max(low, int(value) + step)))
                cursor = len(text)
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if cursor:
                    text, cursor = text[: cursor - 1] + text[cursor:], cursor - 1
            elif key == curses.KEY_DC:
                text = text[:cursor] + text[cursor + 1 :]
            elif key == curses.KEY_LEFT:
                cursor = max(0, cursor - 1)
            elif key == curses.KEY_RIGHT:
                cursor = min(len(text), cursor + 1)
            elif key == curses.KEY_HOME:
                cursor = 0
            elif key == curses.KEY_END:
                cursor = len(text)
            elif 32 <= key < 127 and chr(key) in "0123456789+-" and len(text) < field:
                text, cursor = text[:cursor] + chr(key) + text[cursor:], cursor + 1

    def choose(
        self,
        title: str,
        items: Sequence[str],
        index: int,
        keys: dict[str, str] | Callable[[int], dict[str, str]],
        detail: Callable[[int], str] | None = None,
    ) -> tuple[int, str] | None:
        """A list to pick from: ``(index, key)``, or ``None`` on Escape.

        ``keys`` and ``detail`` may depend on the item selected: the keys
        that act on it, and its whole text below the list.
        """
        while True:
            now = keys(index) if callable(keys) else keys
            below: list[str] = []
            if detail is not None:
                below = ["", *textwrap.wrap(detail(index), max(30, self.cols() - 10))]
            visible = max(1, min(len(items), self.rows_available() - 8 - len(below)))
            first = min(max(0, index - visible + 1), len(items) - visible)
            first = max(0, min(first, index))
            box = self._dialog(
                title,
                [" " + item for item in items[first : first + visible]] + below,
                now,
                selected=index - first,
                wide=detail is not None,
            )
            keys_now = now
            key = self.key()
            if key in (-1, curses.KEY_RESIZE) or (box is None and key != ESCAPE):
                continue
            if key == ESCAPE:
                return None
            if key in (curses.KEY_DOWN, ord("j")):
                index = min(len(items) - 1, index + 1)
            elif key in (curses.KEY_UP, ord("k")):
                index = max(0, index - 1)
            elif key in ENTER and "Enter" in keys_now:
                return index, "Enter"
            elif 32 <= key < 127 and chr(key) in keys_now:
                return index, chr(key)

    def ask(self, title: str, text: str, keys: dict[str, str]) -> str | None:
        """A question answered by one of ``keys``; ``None`` for Escape."""
        while True:
            self._dialog(title, textwrap.wrap(text, 50), keys)
            key = self.key()
            if key == ESCAPE:
                return None
            if 32 <= key < 127 and chr(key) in keys:
                return chr(key)

    def show_text(self, title: str, text: str) -> None:
        """Text to read, scrolled with the arrows; any other key closes it."""
        offset = 0
        while True:
            width = max(20, min(74, self.cols() - 6))
            lines = [
                wrapped
                for paragraph in text.split("\n")
                for wrapped in (
                    textwrap.wrap(paragraph, width, drop_whitespace=False) or [""]
                )
            ]
            visible = max(1, self.rows_available() - 6)
            offset = max(0, min(offset, len(lines) - visible))
            more = len(lines) > visible
            keys = (
                {"Up Down": "scroll", "any key": "close"}
                if more
                else {"any key": "close"}
            )
            self._dialog(title, lines[offset : offset + visible], keys, wide=True)
            key = self.key()
            if key in (-1, curses.KEY_RESIZE):
                continue
            if more and key in (curses.KEY_DOWN, ord("j"), curses.KEY_NPAGE):
                offset += 1 if key != curses.KEY_NPAGE else visible
                continue
            if more and key in (curses.KEY_UP, ord("k"), curses.KEY_PPAGE):
                offset -= 1 if key != curses.KEY_PPAGE else visible
                continue
            return

    def confirm_changes(self, note: str) -> bool:
        lines: list[str] = [*textwrap.wrap(note.strip(), 60), ""] if note else []
        by_scope: dict[Scope, list[Change]] = {}
        for change in self.session.changes():
            by_scope.setdefault(change.scope, []).append(change)
        for scope, changes in by_scope.items():
            lines.append(f"{self._titled(scope)} ({show(self.session.path(scope))}):")
            width = max(len(c.name) for c in changes)
            for change in changes:
                lines.append(
                    f"  {change.name.ljust(width)}  {_value(change.name, change.before)}"
                    f" -> {_value(change.name, change.after)}"
                )
        while True:
            self._dialog(
                "Save these changes?", lines, {"y": "save", "n": "go back"}, wide=True
            )
            key = self.key()
            if key in (ord("y"), ord("Y"), *ENTER):
                return True
            if key in (ord("n"), ord("N"), ESCAPE):
                return False

    def info(self, setting: Setting) -> None:
        origin = self.session.winner(setting)
        lines = [
            f"{setting.name} = {setting.display(self.session.config._get(setting))}, "
            f"from {self._where(origin)}.",
            "",
            setting.description.replace("``", ""),
            "",
            f"Takes {describe_values(setting)}. The default is "
            f"{setting.display(setting.default)}.",
            f"In the environment: ${setting.variable}.",
            "",
            "Where it comes from, lowest first:",
            *self._chain(setting),
        ]
        self.show_text(setting.name, "\n".join(lines))

    # ---------------------------------------------------------- drawing

    def cols(self) -> int:
        return int(self.scr.getmaxyx()[1])

    def rows_available(self) -> int:
        return int(self.scr.getmaxyx()[0])

    def too_small(self) -> bool:
        return self.cols() < MIN_COLS or self.rows_available() < MIN_ROWS

    def list_height(self) -> int:
        available = self.rows_available() - 5
        details = max(3, min(7, available - len(self.rows)))
        return available - details

    def draw(self) -> None:
        self.scr.erase()
        if self.too_small():
            rows, cols = self.scr.getmaxyx()
            text = [
                f"tkcurses-cfg needs {MIN_COLS}x{MIN_ROWS};",
                f"this terminal is {cols}x{rows}.",
                "Make it larger, or press q.",
            ]
            for offset, line in enumerate(text):
                self._put(
                    max(0, rows // 2 - 1) + offset,
                    max(0, (cols - len(line)) // 2),
                    line,
                )
            self.scr.noutrefresh()
            curses.doupdate()
            return
        self._draw_header()
        self._draw_list()
        self._draw_details()
        self._draw_footer()
        self.scr.noutrefresh()
        curses.doupdate()

    def _draw_header(self) -> None:
        cols = self.cols()
        changes = len(self.session.changes())
        right = f"{changes} unsaved " if changes else ""
        # Read-only goes before the path, which a narrow terminal cuts off.
        locked = " (read-only)" if self.session.why_read_only() else ""
        left = (
            f" tkcurses-cfg - editing {self._scope_title()}{locked}: "
            f"{show(self.session.path())}"
        )
        line = left[: cols - len(right) - 1].ljust(cols - len(right)) + right
        self._put(0, 0, line.ljust(cols), curses.A_REVERSE)

    def _columns(self) -> tuple[int, int, int]:
        key = max(len(s.key) for s in SETTINGS) + 2
        file = max(len("IN THIS FILE"), *(len(self._file_shown(s)) for s in SETTINGS))
        effect = max(len("IN EFFECT"), *(len(self._effect(s)) for s in SETTINGS))
        return key, file, effect

    def _draw_list(self) -> None:
        cols = self.cols()
        key_w, file_w, effect_w = self._columns()
        heading = (
            f" {'SETTING'.ljust(key_w)}  {'IN THIS FILE'.ljust(file_w)}   "
            f"{'IN EFFECT'.ljust(effect_w)}  FROM"
        )
        self._put(1, 0, heading[:cols], curses.A_BOLD)
        height = self.list_height()
        if self.current < self.top + 1:
            self.top = max(0, self.current - 1)  # keep its section heading in view
        if self.current >= self.top + height:
            self.top = self.current - height + 1
        for line, row in enumerate(self.rows[self.top : self.top + height]):
            y = 2 + line
            if row.setting is None:
                self._put(y, 1, row.section, curses.A_BOLD)
                continue
            setting = row.setting
            mark, mark_attr = self._mark(setting)
            origin = self.session.winner(setting)
            source = self.session_label(origin)
            text = (
                f"   {setting.key.ljust(key_w - 2)}  "
                f"{self._file_shown(setting).ljust(file_w)} {mark} "
                f"{self._effect(setting).ljust(effect_w)}  {source}"
            )
            selected = self.top + line == self.current
            attr = curses.A_REVERSE if selected else curses.A_NORMAL
            self._put(y, 0, text.ljust(cols)[:cols], attr)
            column = key_w + file_w + 4  # where the mark is, in the text above
            if mark != " " and column < cols:
                self._put(y, column, mark, attr | mark_attr)
            if origin.kind == "environment":
                at = column + 2 + effect_w + 2
                self._put(y, at, source[: max(0, cols - at)], attr | self.attr.env)

    def _draw_details(self) -> None:
        rows, cols = self.scr.getmaxyx()
        top = 2 + self.list_height()  # the rule above the details
        height = rows - top - 3  # below it: the details, the status, the keys
        self.scr.hline(top, 0, curses.ACS_HLINE, cols)
        setting = self.setting
        origin = self.session.winner(setting)
        first = (
            f"{setting.name} = {setting.display(self.session.config._get(setting))}, "
            f"from {self._where(origin)}"
        )
        takes = (
            f"Takes {describe_values(setting)}; default "
            f"{setting.display(setting.default)}."
        )
        chain = "Sources: " + "  ".join(line.strip() for line in self._chain(setting))
        tail = [takes, chain] if height >= 4 else [takes]
        room = max(0, height - 1 - len(tail))
        words = textwrap.wrap(setting.description.replace("``", ""), cols - 2)
        if len(words) > room and room:
            words = words[:room]
            words[-1] = words[-1][: cols - 16].rstrip() + "... i: more"
        else:
            words = words[:room]
        lines = [first, *words, *tail]
        for offset, line in enumerate(lines[:height]):
            attr = curses.A_BOLD if offset == 0 else curses.A_NORMAL
            self._put(top + 1 + offset, 1, line[: cols - 2], attr)

    def _draw_footer(self) -> None:
        rows, cols = self.scr.getmaxyx()
        status = self.message or self._standing_note()
        attr = self.attr.bad if self.message_bad or (not self.message and status) else 0
        self._put(rows - 2, 1, status[: cols - 2], attr)
        self._put(
            rows - 1, 0, self._keys_line(cols).ljust(cols)[:cols], curses.A_REVERSE
        )

    def _keys_line(self, cols: int) -> str:
        setting = self.setting
        session = self.session
        editable = session.why_read_only() is None
        pending = session.pending[session.scope]
        in_file = session.file_value(setting) is not None or setting.name in pending
        keys = [
            ("Space", "switch", editable and setting.kind == "bool"),
            ("Enter", "change", editable and setting.kind != "bool"),
            ("u", "take out", editable and in_file),
            ("r", "undo", setting.name in pending),
            ("s", "save", bool(session.changes())),
            ("Tab", "other file", True),
            (
                "p",
                "problems",
                bool(session.problems()) or session.files[session.scope].ini is None,
            ),
            ("i", "more", True),
        ]
        # Kept, when they do not all fit, in this order of need: what the row
        # can do, saving, the problems the status line points at, then the
        # rest. Shown in the order above.
        need = ["Space", "Enter", "s", "p", "u", "r", "Tab", "i"]
        always = " ? help  q quit "
        room = cols - len(always)
        chosen: set[str] = set()
        for name in need:
            for key, label, shown in keys:
                item = len(f" {key} {label} ")
                if key == name and shown and item <= room:
                    chosen.add(key)
                    room -= item
        line = "".join(f" {k} {label} " for k, label, _ in keys if k in chosen)
        return line + always

    def _standing_note(self) -> str:
        """What stays true about this file, when there is no news."""
        session = self.session
        state = session.files[session.scope]
        if state.ini is None:
            return f"{self._titled(session.scope)} cannot be read: p for details."
        why = session.why_read_only()
        if why:
            return f"Read-only. {why}"
        if session.refused[session.scope]:
            return "Some changes cannot be saved until this file's bad values are fixed: p."
        found = session.problems()
        if found:
            count = len(found)
            return (
                f"{count} problem{'s' * (count != 1)} in this file: p to see and fix."
            )
        return ""

    # ---------------------------------------------------------- helpers

    def session_label(self, origin: Origin) -> str:
        if origin.kind == "file":
            if origin.location == str(self.session.system):
                return "system"
            return self.user_label
        return origin.kind

    def _where(self, origin: Origin) -> str:
        if origin.kind == "environment":
            return f"{origin.location} in this shell"
        if origin.kind == "default":
            return "the default"
        return self.names[
            "system" if origin.location == str(self.session.system) else "user"
        ]

    def _scope_title(self) -> str:
        return self.names[self.session.scope]

    def _titled(self, scope: Scope) -> str:
        return self.names[scope][0].upper() + self.names[scope][1:]

    def _file_shown(self, setting: Setting) -> str:
        raw = self.session.file_value(setting)
        if raw is None:
            return "-"
        try:
            return setting.display(setting.parse(raw))
        except InvalidValue:
            return raw.strip() or "''"

    def _effect(self, setting: Setting) -> str:
        return setting.display(self.session.config._get(setting))

    def _mark(self, setting: Setting) -> tuple[str, int]:
        session = self.session
        if setting.name in session.refused[session.scope]:
            return "!", self.attr.bad
        raw = session.file_value(setting)
        if raw is not None:
            try:
                setting.parse(raw)
            except InvalidValue:
                return "!", self.attr.bad
        if setting.name in session.pending[session.scope]:
            return "*", self.attr.pending
        return " ", 0

    def _chain(self, setting: Setting) -> list[str]:
        winner = self.session.winner(setting)
        lines = []
        for origin in self.session.config.origins[setting.name]:
            mark = ">" if origin is winner else (" " if origin.applied else "x")
            if origin.value is not None:
                value = setting.display(origin.value)
            else:
                value = (origin.raw or "").strip()
            why = f" ({origin.problem})" if origin.problem else ""
            lines.append(f"  {mark} {self.session_label(origin)} {value}{why}")
        return lines

    def _put(self, y: int, x: int, text: str, attr: int = 0) -> None:
        rows, cols = self.scr.getmaxyx()
        if not (0 <= y < rows and 0 <= x < cols):
            return
        text = text[: cols - x]
        # The bottom-right cell is written, then the cursor cannot advance.
        with contextlib.suppress(curses.error):
            self.scr.addstr(y, x, text, attr)

    def _dialog(
        self,
        title: str,
        lines: Sequence[str],
        keys: dict[str, str],
        *,
        selected: int | None = None,
        bad_line: int | None = None,
        wide: bool = False,
    ) -> tuple[int, int, int] | None:
        """Draw a box over the screen; its top, left and width, or ``None``
        when the terminal is too small to show it."""
        self.draw()
        if self.too_small():
            return None
        rows, cols = self.scr.getmaxyx()
        prompt = "  ".join(f"{key} {label}" for key, label in keys.items())
        inner = max(len(title) + 4, len(prompt), *(len(line) for line in lines), 30)
        inner = min(inner if not wide else max(inner, 60), cols - 6)
        height = len(lines) + 4
        top = max(1, (rows - height) // 2)
        left = (cols - inner - 4) // 2
        for offset in range(height):
            self._put(top + offset, left, " " * (inner + 4))
        _box(self.scr, top, left, height, inner + 4)
        self._put(top, left + 2, f" {title} "[:inner], curses.A_BOLD)
        for offset, line in enumerate(lines):
            attr = curses.A_REVERSE if offset == selected else 0
            if offset == bad_line:
                attr |= self.attr.bad
            self._put(top + 1 + offset, left + 2, line[:inner].ljust(inner), attr)
        self._put(top + height - 2, left + 2, prompt[:inner], curses.A_DIM)
        self.scr.noutrefresh()
        curses.doupdate()
        return top, left, inner

    def _poll_disk(self) -> None:
        session = self.session
        for scope in session.changed_on_disk():
            session.reload(scope)
            kept = len(session.pending[scope])
            tail = (
                f"; your {kept} unsaved change{'s' * (kept != 1)} are kept on top"
                if kept
                else ""
            )
            self.say(f"{self._titled(scope)} changed on disk and was read again{tail}.")


class _Attributes:
    """What marks a changed row, a bad value and an environment override:
    colour where the terminal has it and NO_COLOR is not set, else type."""

    def __init__(self) -> None:
        self.pending = curses.A_BOLD
        self.bad = curses.A_BOLD
        self.env = curses.A_UNDERLINE
        if "NO_COLOR" in os.environ or not curses.has_colors():
            return
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_YELLOW, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_CYAN, -1)
        except curses.error:
            return
        self.pending = curses.color_pair(1) | curses.A_BOLD
        self.bad = curses.color_pair(2) | curses.A_BOLD
        self.env = curses.color_pair(3)


def _box(scr: Any, top: int, left: int, height: int, width: int) -> None:
    right, bottom = left + width - 1, top + height - 1
    with contextlib.suppress(curses.error):
        scr.hline(top, left + 1, curses.ACS_HLINE, width - 2)
        scr.hline(bottom, left + 1, curses.ACS_HLINE, width - 2)
        scr.vline(top + 1, left, curses.ACS_VLINE, height - 2)
        scr.vline(top + 1, right, curses.ACS_VLINE, height - 2)
        scr.addch(top, left, curses.ACS_ULCORNER)
        scr.addch(top, right, curses.ACS_URCORNER)
        scr.addch(bottom, left, curses.ACS_LLCORNER)
        scr.addch(bottom, right, curses.ACS_LRCORNER)


def _cursor(visibility: int) -> None:
    with contextlib.suppress(curses.error):  # one that cannot hide it
        curses.curs_set(visibility)


def _value(name: str, raw: str | None) -> str:
    if raw is None:
        return "not set"
    setting = BY_NAME.get(name)
    if setting is None:
        return raw
    try:
        return setting.display(setting.parse(raw))
    except InvalidValue:
        return raw
