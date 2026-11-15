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

"""Runtime configuration: built-in defaults, INI files, environment overrides.

Settings come from four sources, each overriding the last: the defaults below,
a system-wide INI file, the user's own INI file, and ``TKCURSES_*``
environment variables. That order is what ARCHITECTURE.md "Configuration
Hierarchy" specifies, and it means an administrator can set a policy, a user
can prefer otherwise, and a single run can override both without editing
anything.

A malformed value never stops the application. Configuration is read before
there is a screen to report errors on, and refusing to start because a number
is out of range would be a poor trade; out-of-range values are clamped and
unparseable ones fall back to their default, each recorded in
:attr:`TkCursesConfig.warnings` so the application can surface them once it
has somewhere to do so.

Every setting is one row of :data:`SETTINGS`, and that row is the only place
its type, range, allowed values, environment variable and description are
written. :meth:`Setting.parse` is strict - it refuses anything that is not
exactly valid - and the loader is lenient by catching what it raises, so
``tkcurses-cfg``, which refuses, and a program, which carries on, cannot
disagree about what is valid. :attr:`TkCursesConfig.origins` records, for
each setting, every source that offered a value, which is what lets the
command say where a value came from.
"""

from __future__ import annotations

import os
import re
import sys
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Literal, NamedTuple

__all__ = [
    "BY_NAME",
    "REMOVED",
    "SETTINGS",
    "ClipboardSettings",
    "DisplaySettings",
    "InputSettings",
    "InvalidValue",
    "MouseSettings",
    "Origin",
    "OutOfRange",
    "RemovedSetting",
    "Setting",
    "TkCursesConfig",
    "config_paths",
]

#: Values accepted for ``[display] color_mode``. A number is a ceiling on
#: what the terminal reports - it can take colours away, never add them,
#: because curses refuses a colour number past the one it was given - and
#: ``truecolor`` sends pictures as 24-bit escape sequences, as COLORTERM does.
COLOR_MODES = ("auto", "8", "16", "256", "truecolor")

#: Values accepted for ``[clipboard] system``.
CLIPBOARD_SYSTEMS = ("auto", "osc52", "command", "off")

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})

#: A whole number as a file or variable may write it: optional sign, ASCII
#: digits. Narrower than ``int()``, which also takes ``1_000`` and digits
#: from other scripts - neither of which anyone means in a config file, and
#: a strict checker that let them through would be checking Python's
#: grammar rather than this file's.
_INTEGER = re.compile(r"[+-]?[0-9]+")


# ------------------------------------------------------------ the settings


@dataclass
class MouseSettings:
    """Mouse behaviour. Each field is described by its row of SETTINGS."""

    click_interval: int = 200
    enabled: bool = True
    report_motion: bool = True
    report_hover: bool = False
    # report_motion is DEC mode 1002, report_hover 1003. ncurses asks the
    # terminal for neither on its own; see InputHandler._enable_motion.


@dataclass
class DisplaySettings:
    """Rendering behaviour. Each field is described by its row of SETTINGS."""

    color_mode: str = "auto"
    unicode_borders: bool = True
    direct_images: bool = True
    # Direct writing is what lets a picture use more than the 255
    # (foreground, background) pairs curses can name. Off is also how a test
    # exercises the pair table.


@dataclass
class InputSettings:
    """Input behaviour. Each field is described by its row of SETTINGS."""

    escape_delay: int = 25
    # ncurses defaults to a full second, which makes Escape - the key that
    # cancels things - feel broken. Every terminal in common use sends the
    # rest of a sequence in the same packet, so 25ms loses nothing and is
    # what most terminal applications settle on.


@dataclass
class ClipboardSettings:
    """Reaching the system clipboard - see :mod:`tkcurses._core.system_clipboard`.

    Each field is described by its row of SETTINGS.
    """

    system: str = "auto"  # TkCurses-hpr.
    primary: bool = True


#: The settings dataclass of each section, in the order sections are shown.
SECTIONS: dict[str, type] = {
    "mouse": MouseSettings,
    "display": DisplaySettings,
    "input": InputSettings,
    "clipboard": ClipboardSettings,
}


class InvalidValue(ValueError):
    """A value that is not one the setting accepts. The message says why,
    without saying where - the caller knows that."""


class OutOfRange(InvalidValue):
    """A number of the right kind outside the setting's range.

    Carries the nearest value in range, which is what a program uses
    instead.
    """

    def __init__(self, message: str, clamped: int) -> None:
        super().__init__(message)
        self.clamped = clamped


@dataclass(frozen=True)
class Setting:
    """One configuration setting: everything there is to know about it."""

    section: str
    key: str
    kind: Literal["bool", "int", "choice"]
    #: The environment variable that overrides every file.
    variable: str
    #: For a user, in whole sentences; the configuration reference and
    #: ``tkcurses-cfg`` both show it. ````literal```` marks code.
    description: str
    #: The inclusive range of an ``int``.
    limits: tuple[int, int] | None = None
    #: The values a ``choice`` accepts, in the case they are stored in.
    choices: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        # A row that cannot be checked would be accepted by nothing or by
        # everything; catch it when the module loads, not when a user trips it.
        if self.kind == "int" and self.limits is None:
            raise TypeError(f"{self.name}: an int setting needs limits")
        if self.kind == "choice" and not self.choices:
            raise TypeError(f"{self.name}: a choice setting needs choices")

    @property
    def name(self) -> str:
        """``section.key``, as ``tkcurses-cfg`` names it."""
        return f"{self.section}.{self.key}"

    @property
    def default(self) -> Any:
        """The built-in value, from the section's dataclass."""
        return getattr(SECTIONS[self.section](), self.key)

    def parse(self, raw: str) -> Any:
        """Return ``raw`` as this setting's value, or raise.

        Leading and trailing space is ignored, and so is case for a boolean
        or a choice; a choice comes back in the case it is listed in.

        Raises:
            OutOfRange: a whole number outside :attr:`limits`.
            InvalidValue: anything else that is not a value of this setting.
        """
        text = raw.strip()
        if self.kind == "bool":
            lowered = text.lower()
            if lowered in _TRUE:
                return True
            if lowered in _FALSE:
                return False
            raise InvalidValue(f"{raw!r} is not a boolean")
        if self.kind == "int":
            if not _INTEGER.fullmatch(text):
                raise InvalidValue(f"{raw!r} is not a number")
            value = int(text)
            assert self.limits is not None
            low, high = self.limits
            if not low <= value <= high:
                raise OutOfRange(
                    f"{value} is outside {low}-{high}", min(max(value, low), high)
                )
            return value
        assert self.choices is not None
        for choice in self.choices:
            if text.lower() == choice.lower():
                return choice
        raise InvalidValue(f"{raw!r} is not one of {', '.join(self.choices)}")

    def format(self, value: Any) -> str:
        """``value`` as a file would write it; :meth:`parse` reads it back."""
        if self.kind == "bool":
            return "true" if value else "false"
        return str(value)


#: Every setting there is. A row is read, and nothing else is.
SETTINGS: tuple[Setting, ...] = (
    Setting(
        "mouse",
        "click_interval",
        "int",
        "TKCURSES_MOUSE_CLICK_INTERVAL",
        "How close together, in milliseconds, two clicks on the same cell must "
        "be to count as a double click, and three as a triple click.",
        limits=(1, 1000),
    ),
    Setting(
        "mouse",
        "enabled",
        "bool",
        "TKCURSES_MOUSE_ENABLED",
        "Whether to use the mouse at all. Off leaves it to the terminal, whose "
        "own text selection then works without holding Shift; the program is "
        "used from the keyboard.",
    ),
    Setting(
        "mouse",
        "report_motion",
        "bool",
        "TKCURSES_MOUSE_REPORT_MOTION",
        "Whether the terminal reports the pointer moving while a button is "
        "held, which is what a drag is made of.",
    ),
    Setting(
        "mouse",
        "report_hover",
        "bool",
        "TKCURSES_MOUSE_REPORT_HOVER",
        "Whether the terminal reports every movement of the pointer, button or "
        "no button, as hovering needs. Off by default: it sends a report for "
        "every cell the pointer crosses, and takes the terminal's own text "
        "selection away while it is on.",
    ),
    Setting(
        "display",
        "color_mode",
        "choice",
        "TKCURSES_DISPLAY_COLOR_MODE",
        "How many colours to use. ``auto`` uses what ``TERM`` says the "
        "terminal has. ``8``, ``16`` or ``256`` uses no more than that - never "
        "more than ``TERM`` says, so it can show how a program looks on a "
        "plainer terminal but not add colours. ``truecolor`` draws pictures in "
        "full colour, as ``COLORTERM=truecolor`` does, for a terminal that "
        "does not say so.",
        choices=COLOR_MODES,
    ),
    Setting(
        "display",
        "unicode_borders",
        "bool",
        "TKCURSES_DISPLAY_UNICODE",
        "Whether boxes, arrows and bars are drawn with Unicode's box-drawing "
        "characters. Off draws them in ASCII - ``+``, ``-``, ``|`` - for a "
        "terminal whose font has none.",
    ),
    Setting(
        "display",
        "direct_images",
        "bool",
        "TKCURSES_DISPLAY_DIRECT_IMAGES",
        "Whether pictures are written to the terminal directly, in as many "
        "colours as it has. Off draws them through curses, which can show a "
        "picture only a few hundred colour combinations at once; it is for a "
        "terminal that shows directly written pictures wrongly.",
    ),
    Setting(
        "input",
        "escape_delay",
        "int",
        "TKCURSES_INPUT_ESCAPE_DELAY",
        "How long, in milliseconds, to wait after Escape for the rest of a "
        "key such as an arrow, which arrives as Escape and more. Raise it over "
        "a slow connection where arrow keys arrive as Escape and letters.",
        limits=(0, 1000),
    ),
    Setting(
        "clipboard",
        "system",
        "choice",
        "TKCURSES_CLIPBOARD_SYSTEM",
        "How a copy reaches other programs. ``auto`` uses the terminal's own "
        "clipboard (OSC 52) when the terminal has one, which works over SSH, "
        "and otherwise the desktop's clipboard tool - ``wl-copy``, ``xclip`` "
        "or ``xsel``. ``osc52`` and ``command`` use only the one; ``off`` "
        "keeps the clipboard inside the program.",
        choices=CLIPBOARD_SYSTEMS,
    ),
    Setting(
        "clipboard",
        "primary",
        "bool",
        "TKCURSES_CLIPBOARD_PRIMARY",
        "Whether selecting text also sets the desktop's primary selection, so "
        "a middle click in another application pastes it, as it would from a "
        "Tk program on X11. Sent once the selection stops changing, by the "
        "same route as the clipboard. Turn it off if the desktop's tool shows "
        "a window of its own each time.",
    ),
)

#: Each setting by its ``section.key`` name.
BY_NAME: dict[str, Setting] = {setting.name: setting for setting in SETTINGS}


class RemovedSetting(NamedTuple):
    """A setting that was accepted once and never did anything."""

    section: str
    key: str
    variable: str
    #: Why there is nothing for it to do, for whoever still sets it.
    why: str


#: Each was read, validated and tested while nothing used it, so a file or
#: an environment setting one is told so rather than left believing it took
#: effect.
REMOVED: tuple[RemovedSetting, ...] = (
    RemovedSetting(
        "display",
        "refresh_interval",
        "TKCURSES_DISPLAY_REFRESH_INTERVAL",
        "the screen is redrawn when the program is idle, not on a timer",
    ),
    RemovedSetting(
        "input",
        "poll_timeout",
        "TKCURSES_INPUT_POLL_TIMEOUT",
        "the program waits for input and timers together, not by polling",
    ),
    RemovedSetting(
        "input",
        "keypad",
        "TKCURSES_INPUT_KEYPAD",
        "without it no arrow or function key would work",
    ),
    RemovedSetting(
        "accessibility",
        "high_contrast",
        "TKCURSES_ACCESSIBILITY_HIGH_CONTRAST",
        "a theme and the colour options do this",
    ),
    RemovedSetting(
        "accessibility",
        "min_click_interval",
        "TKCURSES_ACCESSIBILITY_MIN_CLICK_INTERVAL",
        "``[mouse] click_interval`` does this",
    ),
    RemovedSetting(
        "accessibility",
        "screen_reader",
        "TKCURSES_ACCESSIBILITY_SCREEN_READER",
        "there was nothing behind it",
    ),
    RemovedSetting("debug", "enabled", "TKCURSES_DEBUG", "TkCurses keeps no log"),
    RemovedSetting(
        "debug", "log_file", "TKCURSES_DEBUG_LOG_FILE", "TkCurses keeps no log"
    ),
    RemovedSetting(
        "debug", "log_level", "TKCURSES_DEBUG_LOG_LEVEL", "TkCurses keeps no log"
    ),
)


def config_paths() -> tuple[Path, Path]:
    """Return the system-wide and user configuration paths for this platform."""
    if sys.platform == "win32":
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        system = Path(program_data) / "tkcurses" / "tkcurses.ini"
        user = Path(local_app_data) / "tkcurses" / "tkcurses.ini"
        return system, user
    system = Path("/etc/tkcurses/tkcurses.ini")
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return system, base / "tkcurses" / "tkcurses.ini"


@dataclass(frozen=True)
class Origin:
    """One source's say about one setting, as :meth:`TkCursesConfig.load` met it."""

    #: What kind of source: the built-in default, an INI file, or the
    #: environment.
    kind: Literal["default", "file", "environment"]
    #: Where: ``built-in``, the file's path, or ``$VARIABLE``.
    location: str
    #: The text as written there; ``None`` for the default.
    raw: str | None
    #: The value this source gave the setting - clamped if it was out of
    #: range - or ``None`` if it gave none, because the text was not a
    #: value of the setting at all.
    value: Any
    #: What was wrong with the text, if anything.
    problem: str | None = None

    @property
    def applied(self) -> bool:
        """Whether this source set the value, rather than being refused."""
        return self.value is not None


@dataclass
class TkCursesConfig:
    """Every runtime setting, assembled from the configuration hierarchy."""

    mouse: MouseSettings = field(default_factory=MouseSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    input: InputSettings = field(default_factory=InputSettings)
    clipboard: ClipboardSettings = field(default_factory=ClipboardSettings)
    #: Problems found while loading, for the application to surface later.
    warnings: list[str] = field(default_factory=list)
    #: For each setting by ``section.key``, every source that offered a
    #: value, in the order they were read: the default first, then each
    #: file, then the environment. The last one :attr:`Origin.applied` is
    #: where the value came from. Filled by :meth:`load`; empty otherwise.
    #: Not compared: two configurations with the same values are equal
    #: however they were arrived at.
    origins: dict[str, list[Origin]] = field(
        default_factory=dict, compare=False, repr=False
    )

    # ----------------------------------------------------------- loading

    @classmethod
    def load(
        cls,
        *,
        paths: tuple[Path, ...] | None = None,
        env: dict[str, str] | None = None,
    ) -> TkCursesConfig:
        """Build a configuration from files and the environment.

        Args:
            paths: Files to read, earliest first. Defaults to the system-wide
                and user paths for this platform. Missing files are skipped.
            env: Environment to read overrides from. Defaults to the process
                environment.
        """
        config = cls()
        for setting in SETTINGS:
            config.origins[setting.name] = [
                Origin("default", "built-in", None, config._get(setting))
            ]
        if paths is None:
            paths = config_paths()
        for path in paths:
            config._read_file(path)
        config._read_env(os.environ if env is None else env)
        return config

    def _read_file(self, path: Path) -> None:
        """Apply one INI file, if it exists and can be read."""
        try:
            if not path.is_file():
                return
            parser = ConfigParser(inline_comment_prefixes=(";", "#"))
            parser.read(path, encoding="utf-8")
        except (OSError, ConfigParserError, UnicodeDecodeError) as exc:
            self.warnings.append(f"could not read {path}: {exc}")
            return
        for setting in SETTINGS:
            section, key = setting.section, setting.key
            if not parser.has_section(section) or not parser.has_option(section, key):
                continue
            self._apply(setting, parser.get(section, key), "file", str(path))
        for removed in REMOVED:
            section, key = removed.section, removed.key
            if parser.has_section(section) and parser.has_option(section, key):
                self.warnings.append(
                    f"[{section}] {key} in {path} no longer has any effect"
                )

    def _read_env(self, env: dict[str, str] | os._Environ[str]) -> None:
        """Apply environment overrides, which outrank every file."""
        for setting in SETTINGS:
            if setting.variable in env:
                raw = env[setting.variable]
                self._apply(setting, raw, "environment", f"${setting.variable}")
        for removed in REMOVED:
            if removed.variable in env:
                self.warnings.append(f"${removed.variable} no longer has any effect")

    def _get(self, setting: Setting) -> Any:
        return getattr(getattr(self, setting.section), setting.key)

    def _apply(
        self,
        setting: Setting,
        raw: str,
        kind: Literal["file", "environment"],
        location: str,
    ) -> None:
        """Parse one value and store it, recording anything wrong with it.

        Out of range is clamped and anything else unreadable keeps the value
        the earlier sources gave; either way the warning says which.
        """
        where = f"[{setting.section}] {setting.key} in {location}"
        value: Any
        problem: str | None = None
        try:
            value = setting.parse(raw)
        except OutOfRange as exc:
            value = exc.clamped
            problem = str(exc)
            self.warnings.append(f"{where}: {exc}, using {value}")
        except InvalidValue as exc:
            value = None
            problem = str(exc)
            self.warnings.append(f"{where}: {exc}, using {self._get(setting)}")
        self.origins[setting.name].append(Origin(kind, location, raw, value, problem))
        if value is not None:
            setattr(getattr(self, setting.section), setting.key, value)

    # ------------------------------------------------------- inspection

    def source(self, name: str) -> Origin:
        """Where the value of setting ``name`` (``section.key``) came from.

        Raises:
            KeyError: ``name`` is not a setting, or this configuration was
                not built by :meth:`load`.
        """
        return [origin for origin in self.origins[name] if origin.applied][-1]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """The settings as nested plain data, for logging and debugging."""
        return {
            section: {
                item.name: getattr(getattr(self, section), item.name)
                for item in fields(getattr(self, section))
            }
            for section in SECTIONS
        }
