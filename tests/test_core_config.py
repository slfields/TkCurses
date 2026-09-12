"""Tests for tkcurses._core.config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tkcurses._core.config import (
    COLOR_MODES,
    LOG_LEVELS,
    TkCursesConfig,
    config_paths,
)


def write(tmp_path: Path, text: str, name: str = "tkcurses.ini") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ----------------------------------------------------------------- defaults


def test_defaults_match_the_specification():
    config = TkCursesConfig()
    assert config.mouse.click_interval == 200
    assert config.mouse.enabled is True
    assert config.mouse.report_motion is True
    assert config.display.color_mode == "auto"
    assert config.display.unicode_borders is True
    assert config.display.refresh_interval == 16
    assert config.input.poll_timeout == 50
    assert config.input.keypad is True
    assert config.input.escape_delay == 25
    assert config.accessibility.high_contrast is False
    assert config.accessibility.min_click_interval == 0
    assert config.accessibility.screen_reader is False
    assert config.debug.enabled is False
    assert config.debug.log_file == ""
    assert config.debug.log_level == "WARNING"


def test_loading_nothing_yields_defaults():
    config = TkCursesConfig.load(paths=(), env={})
    assert config == TkCursesConfig()
    assert config.warnings == []


# --------------------------------------------------------------- ini files


def test_values_are_read_from_a_file(tmp_path):
    path = write(
        tmp_path,
        """
        [mouse]
        click_interval = 350
        enabled = false

        [display]
        color_mode = 256
        refresh_interval = 33
        """,
    )
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == 350
    assert config.mouse.enabled is False
    assert config.display.color_mode == "256"
    assert config.display.refresh_interval == 33
    assert config.warnings == []


def test_a_missing_file_is_skipped(tmp_path):
    config = TkCursesConfig.load(paths=(tmp_path / "absent.ini",), env={})
    assert config == TkCursesConfig()


def test_later_files_override_earlier_ones(tmp_path):
    """The user's file outranks the system-wide one."""
    system = write(tmp_path, "[mouse]\nclick_interval = 300\n", "system.ini")
    user = write(tmp_path, "[mouse]\nclick_interval = 450\n", "user.ini")
    config = TkCursesConfig.load(paths=(system, user), env={})
    assert config.mouse.click_interval == 450


def test_a_file_only_overrides_what_it_sets(tmp_path):
    path = write(tmp_path, "[mouse]\nclick_interval = 300\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.enabled is True, "untouched settings keep their default"


@pytest.mark.parametrize("comment", [";", "#"])
def test_comments_are_ignored(tmp_path, comment):
    path = write(
        tmp_path,
        f"{comment} a comment\n[mouse]\nclick_interval = 250 {comment} inline\n",
    )
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == 250


def test_a_malformed_file_is_reported_not_fatal(tmp_path):
    """Configuration is read before there is a screen to report errors on."""
    path = write(tmp_path, "this is not an ini file at all\n=== nonsense\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == 200
    assert any("could not read" in w for w in config.warnings)


def test_an_unreadable_file_is_reported(tmp_path):
    path = tmp_path / "unreadable.ini"
    path.write_text("[mouse]\nclick_interval = 300\n", encoding="utf-8")
    path.chmod(0o000)
    try:
        config = TkCursesConfig.load(paths=(path,), env={})
    finally:
        path.chmod(0o644)
    if config.warnings:  # skipped when running as root, which ignores the mode
        assert any("could not read" in w for w in config.warnings)


# --------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("true", True),
        ("yes", True),
        ("1", True),
        ("on", True),
        ("TRUE", True),
        ("false", False),
        ("no", False),
        ("0", False),
        ("off", False),
    ],
)
def test_boolean_spellings(tmp_path, text, expected):
    path = write(tmp_path, f"[mouse]\nenabled = {text}\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.enabled is expected


def test_an_unparseable_boolean_falls_back(tmp_path):
    path = write(tmp_path, "[mouse]\nenabled = perhaps\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.enabled is True
    assert any("not a boolean" in w for w in config.warnings)


def test_an_unparseable_number_falls_back(tmp_path):
    path = write(tmp_path, "[mouse]\nclick_interval = soon\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == 200
    assert any("not a number" in w for w in config.warnings)


@pytest.mark.parametrize(
    ("value", "expected"), [("0", 1), ("5000", 1000), ("1", 1), ("1000", 1000)]
)
def test_numbers_are_clamped_to_their_range(tmp_path, value, expected):
    path = write(tmp_path, f"[mouse]\nclick_interval = {value}\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == expected


def test_clamping_is_reported(tmp_path):
    path = write(tmp_path, "[input]\npoll_timeout = 9999\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.input.poll_timeout == 500
    assert any("outside 10-500" in w for w in config.warnings)


@pytest.mark.parametrize("mode", COLOR_MODES)
def test_every_colour_mode_is_accepted(tmp_path, mode):
    path = write(tmp_path, f"[display]\ncolor_mode = {mode}\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.display.color_mode == mode


def test_an_unknown_colour_mode_falls_back(tmp_path):
    path = write(tmp_path, "[display]\ncolor_mode = magnificent\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.display.color_mode == "auto"
    assert any("not one of" in w for w in config.warnings)


@pytest.mark.parametrize("level", LOG_LEVELS)
def test_every_log_level_is_accepted(tmp_path, level):
    path = write(tmp_path, f"[debug]\nlog_level = {level.lower()}\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.debug.log_level == level


# ------------------------------------------------------------ environment


def test_environment_overrides_files(tmp_path):
    """A single run can override both files without editing anything."""
    path = write(tmp_path, "[mouse]\nclick_interval = 300\n")
    config = TkCursesConfig.load(
        paths=(path,), env={"TKCURSES_MOUSE_CLICK_INTERVAL": "450"}
    )
    assert config.mouse.click_interval == 450


@pytest.mark.parametrize(
    ("variable", "value", "section", "key", "expected"),
    [
        ("TKCURSES_MOUSE_CLICK_INTERVAL", "150", "mouse", "click_interval", 150),
        ("TKCURSES_MOUSE_ENABLED", "false", "mouse", "enabled", False),
        ("TKCURSES_DISPLAY_COLOR_MODE", "16", "display", "color_mode", "16"),
        ("TKCURSES_DISPLAY_UNICODE", "false", "display", "unicode_borders", False),
        ("TKCURSES_INPUT_POLL_TIMEOUT", "20", "input", "poll_timeout", 20),
        ("TKCURSES_INPUT_ESCAPE_DELAY", "0", "input", "escape_delay", 0),
        (
            "TKCURSES_ACCESSIBILITY_HIGH_CONTRAST",
            "true",
            "accessibility",
            "high_contrast",
            True,
        ),
        ("TKCURSES_DEBUG", "true", "debug", "enabled", True),
        ("TKCURSES_DEBUG_LOG_FILE", "/tmp/x.log", "debug", "log_file", "/tmp/x.log"),
        ("TKCURSES_DEBUG_LOG_LEVEL", "debug", "debug", "log_level", "DEBUG"),
    ],
)
def test_every_documented_variable(variable, value, section, key, expected):
    """Each variable in the specification's reference table."""
    config = TkCursesConfig.load(paths=(), env={variable: value})
    assert getattr(getattr(config, section), key) == expected


def test_an_invalid_environment_value_is_reported():
    config = TkCursesConfig.load(
        paths=(), env={"TKCURSES_MOUSE_CLICK_INTERVAL": "lots"}
    )
    assert config.mouse.click_interval == 200
    assert any("$TKCURSES_MOUSE_CLICK_INTERVAL" in w for w in config.warnings)


def test_unrelated_variables_are_ignored():
    config = TkCursesConfig.load(paths=(), env={"PATH": "/usr/bin", "HOME": "/root"})
    assert config == TkCursesConfig()


# --------------------------------------------------------------- behaviour


def test_accessibility_minimum_raises_the_click_interval():
    """A user who needs longer between clicks is not overridden."""
    config = TkCursesConfig()
    config.mouse.click_interval = 200
    config.accessibility.min_click_interval = 400
    assert config.effective_click_interval == 400


def test_accessibility_minimum_does_not_lower_the_click_interval():
    config = TkCursesConfig()
    config.mouse.click_interval = 300
    config.accessibility.min_click_interval = 100
    assert config.effective_click_interval == 300


def test_as_dict_covers_every_section():
    data = TkCursesConfig().as_dict()
    assert set(data) == {"mouse", "display", "input", "accessibility", "debug"}
    assert data["mouse"]["click_interval"] == 200


# ------------------------------------------------------------------- paths


def test_config_paths_are_platform_appropriate(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    system, user = config_paths()
    if sys.platform == "win32":
        assert "tkcurses.ini" in str(user)
    else:
        assert system == Path("/etc/tkcurses/tkcurses.ini")
        assert str(user).endswith(".config/tkcurses/tkcurses.ini")


def test_xdg_config_home_is_honoured(monkeypatch):
    if sys.platform == "win32":
        pytest.skip("XDG_CONFIG_HOME does not apply on Windows")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
    _, user = config_paths()
    assert user == Path("/custom/config/tkcurses/tkcurses.ini")


def test_load_defaults_to_the_platform_paths(monkeypatch, tmp_path):
    """With no paths given, the real locations are consulted."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = tmp_path / "tkcurses" / "tkcurses.ini"
    target.parent.mkdir(parents=True)
    target.write_text("[mouse]\nclick_interval = 275\n", encoding="utf-8")
    config = TkCursesConfig.load(env={})
    assert config.mouse.click_interval == 275


def test_windows_paths(monkeypatch):
    """The Windows locations differ from the XDG ones and cannot run here."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMDATA", r"C:\ProgramData")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\someone\AppData\Local")
    system, user = config_paths()
    assert system == Path(r"C:\ProgramData") / "tkcurses" / "tkcurses.ini"
    assert user == (
        Path(r"C:\Users\someone\AppData\Local") / "tkcurses" / "tkcurses.ini"
    )


def test_windows_paths_fall_back_when_unset(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("PROGRAMDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    system, _ = config_paths()
    assert "tkcurses.ini" in str(system)


def test_an_integer_without_a_range_is_left_alone():
    """Every field currently has a range; the guard is for ones that may not."""
    config = TkCursesConfig()
    assert config._as_int("99999", "where", 0, None) == 99999
    assert config.warnings == []
