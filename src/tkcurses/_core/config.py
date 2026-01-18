"""Configuration management for TkCurses internals.

Handles default settings, user configuration, and runtime
options for the TkCurses framework. Manages terminal
capabilities detection and feature flags.

Configuration hierarchy (later sources override earlier):
1. Built-in defaults (hardcoded)
2. System-wide config: /etc/tkcurses/tkcurses.ini (Unix) or
   %PROGRAMDATA%\\tkcurses\\tkcurses.ini (Windows)
3. User config: ~/.config/tkcurses/tkcurses.ini (Unix) or
   %LOCALAPPDATA%\\tkcurses\\tkcurses.ini (Windows)
4. Environment variables (highest priority)
"""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tkcurses import Tk


@dataclass
class MouseConfig:
    """Mouse-related configuration.

    Attributes:
        click_interval: Time window for multi-click detection in milliseconds.
            Used by curses.mouseinterval(). Range: 1-1000, default: 200.
            Recommended ranges:
            - 100-150ms: Fast, responsive (may miss double-clicks)
            - 200-300ms: Balanced (default recommendation)
            - 300-500ms: Accessible (easier double-click, feels sluggish)
        enabled: Whether mouse support is enabled. Default: True.
        report_motion: Whether to report mouse motion events. Default: True.
    """

    click_interval: int = 200
    enabled: bool = True
    report_motion: bool = True


@dataclass
class DisplayConfig:
    """Display-related configuration.

    Attributes:
        color_mode: Color mode selection. Options: 'auto', 'mono', '16',
            '256', 'truecolor'. Default: 'auto'.
        unicode_borders: Whether to use Unicode box-drawing characters
            for borders. Default: True.
        refresh_interval: Target refresh interval in milliseconds.
            Default: 16 (~60fps).
    """

    color_mode: str = 'auto'
    unicode_borders: bool = True
    refresh_interval: int = 16


@dataclass
class InputConfig:
    """Input-related configuration.

    Attributes:
        poll_timeout: Timeout for input polling in milliseconds.
            Default: 50.
        keypad: Whether to enable keypad mode for special keys.
            Default: True.
        escape_delay: Delay for escape sequence detection in milliseconds.
            Default: 25.
    """

    poll_timeout: int = 50
    keypad: bool = True
    escape_delay: int = 25


@dataclass
class AccessibilityConfig:
    """Accessibility-related configuration.

    Attributes:
        high_contrast: Whether to use high contrast color scheme.
            Default: False.
        min_click_interval: Minimum click interval for accessibility.
            Overrides mouse click_interval if larger. Default: 0.
        screen_reader: Whether screen reader mode is enabled.
            Default: False.
    """

    high_contrast: bool = False
    min_click_interval: int = 0
    screen_reader: bool = False


@dataclass
class DebugConfig:
    """Debug-related configuration.

    Attributes:
        enabled: Whether debug mode is enabled. Default: False.
        log_file: Path to debug log file. Empty string means no file
            logging. Default: ''.
        log_level: Logging level. Options: 'DEBUG', 'INFO', 'WARNING',
            'ERROR', 'CRITICAL'. Default: 'WARNING'.
    """

    enabled: bool = False
    log_file: str = ''
    log_level: str = 'WARNING'


@dataclass
class TkCursesConfig:
    """Complete TkCurses configuration.

    Aggregates all configuration sections and provides methods for
    loading configuration from INI files and environment variables.

    Configuration is loaded in order with later sources overriding:
    1. Built-in defaults (hardcoded in dataclass defaults)
    2. System-wide config file
    3. User config file
    4. Environment variables (TKCURSES_* prefix)

    Attributes:
        mouse: Mouse-related configuration.
        display: Display-related configuration.
        input: Input-related configuration.
        accessibility: Accessibility-related configuration.
        debug: Debug-related configuration.

    Example:
        >>> config = TkCursesConfig.load()
        >>> print(config.mouse.click_interval)
        200
        >>> print(config.display.color_mode)
        'auto'
    """

    mouse: MouseConfig = field(default_factory=MouseConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    input: InputConfig = field(default_factory=InputConfig)
    accessibility: AccessibilityConfig = field(default_factory=AccessibilityConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)

    @classmethod
    def get_config_paths(cls) -> list[Path]:
        """Get configuration file paths in load order.

        Returns paths for system-wide and user configuration files
        based on the current platform. On Unix systems, respects
        XDG_CONFIG_HOME for user configuration.

        Returns:
            List of Path objects in the order they should be loaded.
            Earlier paths are overridden by later paths.

        Example:
            >>> paths = TkCursesConfig.get_config_paths()
            >>> # On Linux:
            >>> # [Path('/etc/tkcurses/tkcurses.ini'),
            >>> #  Path('/home/user/.config/tkcurses/tkcurses.ini')]
        """
        paths: list[Path] = []

        if sys.platform == 'win32':
            # Windows paths
            programdata = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
            localappdata = os.environ.get('LOCALAPPDATA', '')

            paths.append(Path(programdata) / 'tkcurses' / 'tkcurses.ini')
            if localappdata:
                paths.append(Path(localappdata) / 'tkcurses' / 'tkcurses.ini')
        else:
            # Unix paths (Linux, macOS, FreeBSD, etc.)
            paths.append(Path('/etc/tkcurses/tkcurses.ini'))

            # Respect XDG_CONFIG_HOME
            config_home = os.environ.get('XDG_CONFIG_HOME')
            if not config_home:
                config_home_path = Path.home() / '.config'
            else:
                config_home_path = Path(config_home)

            paths.append(config_home_path / 'tkcurses' / 'tkcurses.ini')

        return paths

    @classmethod
    def load(cls) -> TkCursesConfig:
        """Load configuration from all sources.

        Loads configuration in order:
        1. Built-in defaults (from dataclass defaults)
        2. System-wide INI file (if exists)
        3. User INI file (if exists)
        4. Environment variables (TKCURSES_* prefix)

        Malformed INI files are silently skipped. Invalid values
        in environment variables are silently ignored.

        Returns:
            TkCursesConfig instance with all settings applied.

        Example:
            >>> config = TkCursesConfig.load()
            >>> # Configuration loaded from all available sources
        """
        config = cls()

        # Load from INI files (in order)
        parser = configparser.ConfigParser()
        config_paths = cls.get_config_paths()

        for path in config_paths:
            if path.exists():
                try:
                    parser.read(path)
                except configparser.Error as e:
                    # Log config parsing failures
                    import logging
                    logging.getLogger('tkcurses').warning(
                        f"Failed to parse config file {path}: {e}"
                    )

        # Apply INI settings
        config._apply_parser(parser)

        # Apply environment variable overrides (highest priority)
        config._apply_env_overrides()

        # Validate configuration and log any warnings
        warnings = config.validate()
        if warnings:
            import logging
            logger = logging.getLogger('tkcurses')
            for warning in warnings:
                logger.warning(f"Config validation: {warning}")

        return config

    def _apply_parser(self, parser: configparser.ConfigParser) -> None:
        """Apply settings from ConfigParser.

        Reads values from the parser and applies them to the
        configuration sections. Uses fallback values from current
        configuration if keys are missing.

        Args:
            parser: ConfigParser instance with loaded INI data.
        """
        # Mouse settings
        if parser.has_section('mouse'):
            self.mouse.click_interval = parser.getint(
                'mouse', 'click_interval', fallback=self.mouse.click_interval
            )
            self.mouse.enabled = parser.getboolean(
                'mouse', 'enabled', fallback=self.mouse.enabled
            )
            self.mouse.report_motion = parser.getboolean(
                'mouse', 'report_motion', fallback=self.mouse.report_motion
            )

        # Display settings
        if parser.has_section('display'):
            self.display.color_mode = parser.get(
                'display', 'color_mode', fallback=self.display.color_mode
            )
            self.display.unicode_borders = parser.getboolean(
                'display', 'unicode_borders', fallback=self.display.unicode_borders
            )
            self.display.refresh_interval = parser.getint(
                'display', 'refresh_interval', fallback=self.display.refresh_interval
            )

        # Input settings
        if parser.has_section('input'):
            self.input.poll_timeout = parser.getint(
                'input', 'poll_timeout', fallback=self.input.poll_timeout
            )
            self.input.keypad = parser.getboolean(
                'input', 'keypad', fallback=self.input.keypad
            )
            self.input.escape_delay = parser.getint(
                'input', 'escape_delay', fallback=self.input.escape_delay
            )

        # Accessibility settings
        if parser.has_section('accessibility'):
            self.accessibility.high_contrast = parser.getboolean(
                'accessibility', 'high_contrast',
                fallback=self.accessibility.high_contrast
            )
            self.accessibility.min_click_interval = parser.getint(
                'accessibility', 'min_click_interval',
                fallback=self.accessibility.min_click_interval
            )
            self.accessibility.screen_reader = parser.getboolean(
                'accessibility', 'screen_reader',
                fallback=self.accessibility.screen_reader
            )

        # Debug settings
        if parser.has_section('debug'):
            self.debug.enabled = parser.getboolean(
                'debug', 'enabled', fallback=self.debug.enabled
            )
            self.debug.log_file = parser.get(
                'debug', 'log_file', fallback=self.debug.log_file
            )
            self.debug.log_level = parser.get(
                'debug', 'log_level', fallback=self.debug.log_level
            )

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides.

        Environment variables with TKCURSES_* prefix override
        configuration from INI files. Invalid values are silently
        ignored.

        Environment variable mapping:
        - TKCURSES_MOUSE_CLICK_INTERVAL -> mouse.click_interval
        - TKCURSES_MOUSE_ENABLED -> mouse.enabled
        - TKCURSES_DISPLAY_COLOR_MODE -> display.color_mode
        - TKCURSES_DISPLAY_UNICODE -> display.unicode_borders
        - TKCURSES_INPUT_POLL_TIMEOUT -> input.poll_timeout
        - TKCURSES_INPUT_ESCAPE_DELAY -> input.escape_delay
        - TKCURSES_ACCESSIBILITY_HIGH_CONTRAST -> accessibility.high_contrast
        - TKCURSES_DEBUG -> debug.enabled
        - TKCURSES_DEBUG_LOG_FILE -> debug.log_file
        - TKCURSES_DEBUG_LOG_LEVEL -> debug.log_level
        """
        env_mapping: dict[str, tuple[str, str, Callable[[str], int | bool | str]]] = {
            'TKCURSES_MOUSE_CLICK_INTERVAL': ('mouse', 'click_interval', int),
            'TKCURSES_MOUSE_ENABLED': ('mouse', 'enabled', self._parse_bool),
            'TKCURSES_DISPLAY_COLOR_MODE': ('display', 'color_mode', str),
            'TKCURSES_DISPLAY_UNICODE': ('display', 'unicode_borders', self._parse_bool),
            'TKCURSES_INPUT_POLL_TIMEOUT': ('input', 'poll_timeout', int),
            'TKCURSES_INPUT_ESCAPE_DELAY': ('input', 'escape_delay', int),
            'TKCURSES_ACCESSIBILITY_HIGH_CONTRAST': ('accessibility', 'high_contrast', self._parse_bool),
            'TKCURSES_DEBUG': ('debug', 'enabled', self._parse_bool),
            'TKCURSES_DEBUG_LOG_FILE': ('debug', 'log_file', str),
            'TKCURSES_DEBUG_LOG_LEVEL': ('debug', 'log_level', str),
        }

        for env_var, (section, key, converter) in env_mapping.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    section_obj = getattr(self, section)
                    setattr(section_obj, key, converter(value))
                except (ValueError, AttributeError):
                    pass  # Skip invalid values

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse boolean from string.

        Recognizes common boolean string representations.

        Args:
            value: String to parse as boolean.

        Returns:
            True if value is 'true', '1', 'yes', or 'on' (case-insensitive).
            False otherwise.

        Example:
            >>> TkCursesConfig._parse_bool('true')
            True
            >>> TkCursesConfig._parse_bool('FALSE')
            False
            >>> TkCursesConfig._parse_bool('1')
            True
            >>> TkCursesConfig._parse_bool('no')
            False
        """
        return value.lower() in ('true', '1', 'yes', 'on')

    def apply(self, app: Tk) -> None:
        """Apply configuration to a Tk application instance.

        Configures the application based on the current configuration
        settings. This includes mouse settings, display options, and
        accessibility features.

        Args:
            app: The Tk application instance to configure.
        """
        # Apply mouse settings
        if self.mouse.enabled:
            app.configure_mouse(click_interval=max(
                self.mouse.click_interval,
                self.accessibility.min_click_interval
            ))

        # Apply other settings as needed by the application...

    # Valid values for validated settings
    VALID_COLOR_MODES = frozenset({'auto', 'mono', '16', '256', 'truecolor'})
    VALID_LOG_LEVELS = frozenset({'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'})

    def validate(self) -> list[str]:
        """Validate configuration values.

        Checks that configuration values are within expected ranges and
        sets. Invalid values are corrected to defaults and warnings are
        returned.

        Returns:
            List of warning messages for invalid values that were corrected.

        Example:
            >>> config = TkCursesConfig()
            >>> config.display.color_mode = 'invalid'
            >>> warnings = config.validate()
            >>> print(warnings)
            ["Invalid color_mode 'invalid', using 'auto'"]
        """
        warnings: list[str] = []

        # Validate color_mode
        if self.display.color_mode not in self.VALID_COLOR_MODES:
            warnings.append(
                f"Invalid color_mode '{self.display.color_mode}', "
                f"using 'auto'. Valid options: {', '.join(sorted(self.VALID_COLOR_MODES))}"
            )
            self.display.color_mode = 'auto'

        # Validate log_level
        log_level_upper = self.debug.log_level.upper()
        if log_level_upper not in self.VALID_LOG_LEVELS:
            warnings.append(
                f"Invalid log_level '{self.debug.log_level}', "
                f"using 'WARNING'. Valid options: {', '.join(sorted(self.VALID_LOG_LEVELS))}"
            )
            self.debug.log_level = 'WARNING'
        else:
            # Normalize to uppercase
            self.debug.log_level = log_level_upper

        # Validate click_interval range
        if self.mouse.click_interval < 1:
            warnings.append(
                f"click_interval {self.mouse.click_interval} too low, using 1"
            )
            self.mouse.click_interval = 1
        elif self.mouse.click_interval > 1000:
            warnings.append(
                f"click_interval {self.mouse.click_interval} too high, using 1000"
            )
            self.mouse.click_interval = 1000

        # Validate poll_timeout range
        if self.input.poll_timeout < 1:
            warnings.append(
                f"poll_timeout {self.input.poll_timeout} too low, using 1"
            )
            self.input.poll_timeout = 1
        elif self.input.poll_timeout > 1000:
            warnings.append(
                f"poll_timeout {self.input.poll_timeout} too high, using 1000"
            )
            self.input.poll_timeout = 1000

        # Validate refresh_interval
        if self.display.refresh_interval < 1:
            warnings.append(
                f"refresh_interval {self.display.refresh_interval} too low, using 1"
            )
            self.display.refresh_interval = 1

        return warnings
