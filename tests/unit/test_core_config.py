"""Unit tests for tkcurses._core.config module."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tkcurses._core.config import (
    MouseConfig,
    DisplayConfig,
    InputConfig,
    AccessibilityConfig,
    DebugConfig,
    TkCursesConfig,
)


class TestMouseConfig:
    """Tests for MouseConfig dataclass."""

    def test_defaults(self):
        """MouseConfig should have sensible defaults."""
        config = MouseConfig()
        assert config.click_interval == 200
        assert config.enabled is True
        assert config.report_motion is True

    def test_custom_values(self):
        """MouseConfig should accept custom values."""
        config = MouseConfig(click_interval=300, enabled=False, report_motion=False)
        assert config.click_interval == 300
        assert config.enabled is False
        assert config.report_motion is False


class TestDisplayConfig:
    """Tests for DisplayConfig dataclass."""

    def test_defaults(self):
        """DisplayConfig should have sensible defaults."""
        config = DisplayConfig()
        assert config.color_mode == 'auto'
        assert config.unicode_borders is True
        assert config.refresh_interval == 16

    def test_custom_values(self):
        """DisplayConfig should accept custom values."""
        config = DisplayConfig(color_mode='256', unicode_borders=False, refresh_interval=33)
        assert config.color_mode == '256'
        assert config.unicode_borders is False
        assert config.refresh_interval == 33


class TestInputConfig:
    """Tests for InputConfig dataclass."""

    def test_defaults(self):
        """InputConfig should have sensible defaults."""
        config = InputConfig()
        assert config.poll_timeout == 50
        assert config.keypad is True
        assert config.escape_delay == 25

    def test_custom_values(self):
        """InputConfig should accept custom values."""
        config = InputConfig(poll_timeout=100, keypad=False, escape_delay=50)
        assert config.poll_timeout == 100
        assert config.keypad is False
        assert config.escape_delay == 50


class TestAccessibilityConfig:
    """Tests for AccessibilityConfig dataclass."""

    def test_defaults(self):
        """AccessibilityConfig should have sensible defaults."""
        config = AccessibilityConfig()
        assert config.high_contrast is False
        assert config.min_click_interval == 0
        assert config.screen_reader is False

    def test_custom_values(self):
        """AccessibilityConfig should accept custom values."""
        config = AccessibilityConfig(high_contrast=True, min_click_interval=300, screen_reader=True)
        assert config.high_contrast is True
        assert config.min_click_interval == 300
        assert config.screen_reader is True


class TestDebugConfig:
    """Tests for DebugConfig dataclass."""

    def test_defaults(self):
        """DebugConfig should have sensible defaults."""
        config = DebugConfig()
        assert config.enabled is False
        assert config.log_file == ''
        assert config.log_level == 'WARNING'

    def test_custom_values(self):
        """DebugConfig should accept custom values."""
        config = DebugConfig(enabled=True, log_file='/tmp/debug.log', log_level='DEBUG')
        assert config.enabled is True
        assert config.log_file == '/tmp/debug.log'
        assert config.log_level == 'DEBUG'


class TestTkCursesConfig:
    """Tests for TkCursesConfig class."""

    def test_defaults(self):
        """TkCursesConfig should have default sub-configs."""
        config = TkCursesConfig()
        assert isinstance(config.mouse, MouseConfig)
        assert isinstance(config.display, DisplayConfig)
        assert isinstance(config.input, InputConfig)
        assert isinstance(config.accessibility, AccessibilityConfig)
        assert isinstance(config.debug, DebugConfig)

    def test_default_values(self):
        """TkCursesConfig defaults should match sub-config defaults."""
        config = TkCursesConfig()
        assert config.mouse.click_interval == 200
        assert config.display.color_mode == 'auto'
        assert config.input.poll_timeout == 50

    def test_get_config_paths_unix(self):
        """get_config_paths should return Unix paths on Unix."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': ''}, clear=False):
                paths = TkCursesConfig.get_config_paths()
                assert len(paths) == 2
                assert paths[0] == Path('/etc/tkcurses/tkcurses.ini')
                assert 'tkcurses' in str(paths[1])

    def test_get_config_paths_xdg(self):
        """get_config_paths should respect XDG_CONFIG_HOME."""
        with patch.object(sys, 'platform', 'linux'):
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': '/custom/config'}, clear=False):
                paths = TkCursesConfig.get_config_paths()
                assert paths[1] == Path('/custom/config/tkcurses/tkcurses.ini')

    def test_get_config_paths_windows(self):
        """get_config_paths should return Windows paths on Windows."""
        with patch.object(sys, 'platform', 'win32'):
            with patch.dict(os.environ, {
                'PROGRAMDATA': r'C:\ProgramData',
                'LOCALAPPDATA': r'C:\Users\Test\AppData\Local'
            }, clear=False):
                paths = TkCursesConfig.get_config_paths()
                assert len(paths) == 2
                assert 'ProgramData' in str(paths[0]) or 'tkcurses' in str(paths[0])

    def test_load_defaults(self, clean_env):
        """TkCursesConfig.load() should return defaults with no config files."""
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 200
        assert config.display.color_mode == 'auto'

    def test_load_from_ini(self, sample_ini_config, clean_env, monkeypatch):
        """TkCursesConfig.load() should load from INI file."""
        # Patch get_config_paths to return our test config
        monkeypatch.setattr(
            TkCursesConfig, 'get_config_paths',
            classmethod(lambda cls: [sample_ini_config])
        )
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 250  # From sample config

    def test_load_env_override(self, clean_env, monkeypatch):
        """TkCursesConfig.load() should apply environment overrides."""
        monkeypatch.setenv('TKCURSES_MOUSE_CLICK_INTERVAL', '500')
        monkeypatch.setenv('TKCURSES_DEBUG', 'true')
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 500
        assert config.debug.enabled is True

    def test_parse_bool_true(self):
        """_parse_bool should parse true values."""
        assert TkCursesConfig._parse_bool('true') is True
        assert TkCursesConfig._parse_bool('TRUE') is True
        assert TkCursesConfig._parse_bool('True') is True
        assert TkCursesConfig._parse_bool('1') is True
        assert TkCursesConfig._parse_bool('yes') is True
        assert TkCursesConfig._parse_bool('on') is True

    def test_parse_bool_false(self):
        """_parse_bool should parse false values."""
        assert TkCursesConfig._parse_bool('false') is False
        assert TkCursesConfig._parse_bool('FALSE') is False
        assert TkCursesConfig._parse_bool('0') is False
        assert TkCursesConfig._parse_bool('no') is False
        assert TkCursesConfig._parse_bool('off') is False
        assert TkCursesConfig._parse_bool('') is False


class TestConfigEnvOverrides:
    """Tests for environment variable overrides."""

    def test_mouse_click_interval(self, clean_env, monkeypatch):
        """TKCURSES_MOUSE_CLICK_INTERVAL should override click_interval."""
        monkeypatch.setenv('TKCURSES_MOUSE_CLICK_INTERVAL', '350')
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 350

    def test_mouse_enabled(self, clean_env, monkeypatch):
        """TKCURSES_MOUSE_ENABLED should override enabled."""
        monkeypatch.setenv('TKCURSES_MOUSE_ENABLED', 'false')
        config = TkCursesConfig.load()
        assert config.mouse.enabled is False

    def test_display_color_mode(self, clean_env, monkeypatch):
        """TKCURSES_DISPLAY_COLOR_MODE should override color_mode."""
        monkeypatch.setenv('TKCURSES_DISPLAY_COLOR_MODE', '256')
        config = TkCursesConfig.load()
        assert config.display.color_mode == '256'

    def test_display_unicode(self, clean_env, monkeypatch):
        """TKCURSES_DISPLAY_UNICODE should override unicode_borders."""
        monkeypatch.setenv('TKCURSES_DISPLAY_UNICODE', 'false')
        config = TkCursesConfig.load()
        assert config.display.unicode_borders is False

    def test_input_poll_timeout(self, clean_env, monkeypatch):
        """TKCURSES_INPUT_POLL_TIMEOUT should override poll_timeout."""
        monkeypatch.setenv('TKCURSES_INPUT_POLL_TIMEOUT', '100')
        config = TkCursesConfig.load()
        assert config.input.poll_timeout == 100

    def test_accessibility_high_contrast(self, clean_env, monkeypatch):
        """TKCURSES_ACCESSIBILITY_HIGH_CONTRAST should override high_contrast."""
        monkeypatch.setenv('TKCURSES_ACCESSIBILITY_HIGH_CONTRAST', 'true')
        config = TkCursesConfig.load()
        assert config.accessibility.high_contrast is True

    def test_debug_enabled(self, clean_env, monkeypatch):
        """TKCURSES_DEBUG should override debug.enabled."""
        monkeypatch.setenv('TKCURSES_DEBUG', 'true')
        config = TkCursesConfig.load()
        assert config.debug.enabled is True

    def test_debug_log_file(self, clean_env, monkeypatch):
        """TKCURSES_DEBUG_LOG_FILE should override log_file."""
        monkeypatch.setenv('TKCURSES_DEBUG_LOG_FILE', '/var/log/tkcurses.log')
        config = TkCursesConfig.load()
        assert config.debug.log_file == '/var/log/tkcurses.log'

    def test_debug_log_level(self, clean_env, monkeypatch):
        """TKCURSES_DEBUG_LOG_LEVEL should override log_level."""
        monkeypatch.setenv('TKCURSES_DEBUG_LOG_LEVEL', 'DEBUG')
        config = TkCursesConfig.load()
        assert config.debug.log_level == 'DEBUG'

    def test_invalid_int_ignored(self, clean_env, monkeypatch):
        """Invalid integer values should be ignored."""
        monkeypatch.setenv('TKCURSES_MOUSE_CLICK_INTERVAL', 'not_a_number')
        config = TkCursesConfig.load()
        assert config.mouse.click_interval == 200  # Default
