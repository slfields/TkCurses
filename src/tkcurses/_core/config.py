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
"""

from __future__ import annotations

import os
import sys
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

__all__ = [
    "AccessibilitySettings",
    "DebugSettings",
    "DisplaySettings",
    "InputSettings",
    "MouseSettings",
    "TkCursesConfig",
    "config_paths",
]

#: Values accepted for ``[display] color_mode``.
COLOR_MODES = ("auto", "8", "16", "256", "truecolor")

#: Values accepted for ``[debug] log_level``.
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


@dataclass
class MouseSettings:
    """Mouse behaviour."""

    #: Window within which clicks count as a double or triple click.
    click_interval: int = 200
    enabled: bool = True
    #: Motion while a button is held - DEC mode 1002 - which is what a drag
    #: is made of. ncurses does not ask the terminal for this on its own.
    report_motion: bool = True
    #: Every movement, button or no button - DEC mode 1003. Needed for a
    #: widget that highlights what the pointer is over, and off by default
    #: because it sends an event for every cell the pointer crosses and takes
    #: the terminal's own text selection away while it is on.
    report_hover: bool = False


@dataclass
class DisplaySettings:
    """Rendering behaviour."""

    color_mode: str = "auto"
    #: False restricts borders to ASCII, for terminals without box drawing.
    unicode_borders: bool = True
    #: Minimum gap between refreshes; 16ms is roughly 60 per second.
    refresh_interval: int = 16


@dataclass
class InputSettings:
    """Input polling behaviour."""

    #: How long the loop waits for input, which bounds timer latency.
    poll_timeout: int = 50
    keypad: bool = True
    #: How long to wait for the rest of an escape sequence after ESC.
    escape_delay: int = 25


@dataclass
class AccessibilitySettings:
    """Settings that trade speed for reach."""

    high_contrast: bool = False
    #: Raises the click interval for users who need longer between clicks.
    min_click_interval: int = 0
    screen_reader: bool = False


@dataclass
class DebugSettings:
    """Diagnostics."""

    enabled: bool = False
    #: Empty means stderr.
    log_file: str = ""
    log_level: str = "WARNING"


#: One row per setting: section, key, the environment variable that overrides
#: it, and the valid range for numbers. Keeping this in one table means INI
#: parsing, environment parsing and validation cannot drift apart.
_FIELDS: tuple[tuple[str, str, str, str | None, tuple[int, int] | None], ...] = (
    ("mouse", "click_interval", "int", "TKCURSES_MOUSE_CLICK_INTERVAL", (1, 1000)),
    ("mouse", "enabled", "bool", "TKCURSES_MOUSE_ENABLED", None),
    ("mouse", "report_motion", "bool", "TKCURSES_MOUSE_REPORT_MOTION", None),
    ("mouse", "report_hover", "bool", "TKCURSES_MOUSE_REPORT_HOVER", None),
    ("display", "color_mode", "choice", "TKCURSES_DISPLAY_COLOR_MODE", None),
    ("display", "unicode_borders", "bool", "TKCURSES_DISPLAY_UNICODE", None),
    (
        "display",
        "refresh_interval",
        "int",
        "TKCURSES_DISPLAY_REFRESH_INTERVAL",
        (10, 1000),
    ),
    ("input", "poll_timeout", "int", "TKCURSES_INPUT_POLL_TIMEOUT", (10, 500)),
    ("input", "keypad", "bool", "TKCURSES_INPUT_KEYPAD", None),
    ("input", "escape_delay", "int", "TKCURSES_INPUT_ESCAPE_DELAY", (0, 1000)),
    (
        "accessibility",
        "high_contrast",
        "bool",
        "TKCURSES_ACCESSIBILITY_HIGH_CONTRAST",
        None,
    ),
    (
        "accessibility",
        "min_click_interval",
        "int",
        "TKCURSES_ACCESSIBILITY_MIN_CLICK_INTERVAL",
        (0, 1000),
    ),
    (
        "accessibility",
        "screen_reader",
        "bool",
        "TKCURSES_ACCESSIBILITY_SCREEN_READER",
        None,
    ),
    ("debug", "enabled", "bool", "TKCURSES_DEBUG", None),
    ("debug", "log_file", "str", "TKCURSES_DEBUG_LOG_FILE", None),
    ("debug", "log_level", "choice", "TKCURSES_DEBUG_LOG_LEVEL", None),
)

#: Allowed values for the settings validated against a fixed list.
_CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("display", "color_mode"): COLOR_MODES,
    ("debug", "log_level"): LOG_LEVELS,
}


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


@dataclass
class TkCursesConfig:
    """Every runtime setting, assembled from the configuration hierarchy."""

    mouse: MouseSettings = field(default_factory=MouseSettings)
    display: DisplaySettings = field(default_factory=DisplaySettings)
    input: InputSettings = field(default_factory=InputSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    debug: DebugSettings = field(default_factory=DebugSettings)
    #: Problems found while loading, for the application to surface later.
    warnings: list[str] = field(default_factory=list)

    # ---------------------------------------------------------- derived

    @property
    def effective_click_interval(self) -> int:
        """The click interval actually used.

        The accessibility minimum wins when it is higher, so a user who needs
        longer between clicks is not overridden by an application's own
        preference.
        """
        return max(self.mouse.click_interval, self.accessibility.min_click_interval)

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
        for section, key, kind, _, limits in _FIELDS:
            if not parser.has_section(section) or not parser.has_option(section, key):
                continue
            raw = parser.get(section, key)
            self._apply(section, key, kind, limits, raw, source=str(path))

    def _read_env(self, env: dict[str, str] | os._Environ[str]) -> None:
        """Apply environment overrides, which outrank every file."""
        for section, key, kind, variable, limits in _FIELDS:
            if variable is None or variable not in env:
                continue
            self._apply(
                section, key, kind, limits, env[variable], source=f"${variable}"
            )

    def _apply(
        self,
        section: str,
        key: str,
        kind: str,
        limits: tuple[int, int] | None,
        raw: str,
        *,
        source: str,
    ) -> None:
        """Parse one value and store it, recording anything wrong with it."""
        target = getattr(self, section)
        where = f"[{section}] {key} in {source}"
        if kind == "bool":
            value: Any = self._as_bool(raw, where, getattr(target, key))
        elif kind == "int":
            value = self._as_int(raw, where, getattr(target, key), limits)
        elif kind == "choice":
            value = self._as_choice(raw, where, getattr(target, key), section, key)
        else:
            value = raw.strip()
        setattr(target, key, value)

    def _as_bool(self, raw: str, where: str, fallback: bool) -> bool:
        text = raw.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        self.warnings.append(f"{where}: {raw!r} is not a boolean, using {fallback}")
        return fallback

    def _as_int(
        self, raw: str, where: str, fallback: int, limits: tuple[int, int] | None
    ) -> int:
        try:
            value = int(raw.strip())
        except ValueError:
            self.warnings.append(f"{where}: {raw!r} is not a number, using {fallback}")
            return fallback
        if limits is None:
            return value
        low, high = limits
        if value < low or value > high:
            clamped = min(max(value, low), high)
            self.warnings.append(
                f"{where}: {value} is outside {low}-{high}, using {clamped}"
            )
            return clamped
        return value

    def _as_choice(
        self, raw: str, where: str, fallback: str, section: str, key: str
    ) -> str:
        choices = _CHOICES[(section, key)]
        text = raw.strip()
        for choice in choices:
            if text.lower() == choice.lower():
                return choice
        self.warnings.append(
            f"{where}: {raw!r} is not one of {', '.join(choices)}, using {fallback}"
        )
        return fallback

    # ------------------------------------------------------- inspection

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """The settings as nested plain data, for logging and debugging."""
        return {
            section: {
                item.name: getattr(getattr(self, section), item.name)
                for item in fields(getattr(self, section))
            }
            for section in ("mouse", "display", "input", "accessibility", "debug")
        }
