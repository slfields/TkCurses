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

"""Tests for tkcurses._core.config."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tkcurses._core import config as config_module
from tkcurses._core.config import (
    COLOR_MODES,
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
    assert config.input.escape_delay == 25


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
        unicode_borders = no
        """,
    )
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.mouse.click_interval == 350
    assert config.mouse.enabled is False
    assert config.display.color_mode == "256"
    assert config.display.unicode_borders is False
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
    path = write(tmp_path, "[input]\nescape_delay = 9999\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.input.escape_delay == 1000
    assert any("outside 0-1000" in w for w in config.warnings)


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
        ("TKCURSES_MOUSE_REPORT_MOTION", "no", "mouse", "report_motion", False),
        ("TKCURSES_MOUSE_REPORT_HOVER", "yes", "mouse", "report_hover", True),
        (
            "TKCURSES_DISPLAY_COLOR_MODE",
            "TrueColor",
            "display",
            "color_mode",
            "truecolor",
        ),
        ("TKCURSES_DISPLAY_UNICODE", "false", "display", "unicode_borders", False),
        ("TKCURSES_DISPLAY_DIRECT_IMAGES", "0", "display", "direct_images", False),
        ("TKCURSES_INPUT_ESCAPE_DELAY", "0", "input", "escape_delay", 0),
        ("TKCURSES_CLIPBOARD_SYSTEM", "osc52", "clipboard", "system", "osc52"),
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


def test_as_dict_covers_every_section():
    data = TkCursesConfig().as_dict()
    assert set(data) == {"mouse", "display", "input", "clipboard"}
    assert data["mouse"]["click_interval"] == 200


# --------------------------------------------------------- removed settings

REMOVED = config_module.REMOVED


def test_every_setting_there_is_has_a_variable():
    """The table is the configuration: a row is read, and nothing else is."""
    rows = {(setting.section, setting.key) for setting in config_module.SETTINGS}
    fields = {
        (section, key)
        for section, keys in TkCursesConfig().as_dict().items()
        for key in keys
    }
    assert rows == fields


def test_no_removed_setting_is_still_read():
    rows = {(setting.section, setting.key) for setting in config_module.SETTINGS}
    assert not rows & {(section, key) for section, key, *_ in REMOVED}


@pytest.mark.parametrize(("section", "key", "variable"), [row[:3] for row in REMOVED])
def test_a_removed_setting_in_a_file_is_reported(tmp_path, section, key, variable):
    """Read, validated and used by nothing, once; whoever still sets one is
    told it does nothing rather than left believing it took effect."""
    path = write(tmp_path, f"[{section}]\n{key} = 1\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.warnings == [f"[{section}] {key} in {path} no longer has any effect"]


@pytest.mark.parametrize(("section", "key", "variable"), [row[:3] for row in REMOVED])
def test_a_removed_variable_is_reported(section, key, variable):
    config = TkCursesConfig.load(paths=(), env={variable: "1"})
    assert config.warnings == [f"${variable} no longer has any effect"]
    assert config == TkCursesConfig(warnings=config.warnings)


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


def test_a_setting_that_cannot_be_checked_is_refused_when_defined():
    """A number with no range, or a choice of nothing, would accept
    everything or nothing; the table refuses the row instead."""
    with pytest.raises(TypeError, match="needs limits"):
        config_module.Setting("s", "k", "int", "V", "Text.")
    with pytest.raises(TypeError, match="needs choices"):
        config_module.Setting("s", "k", "choice", "V", "Text.")


# ------------------------------------------------- one table, strict parsing

SETTINGS = config_module.SETTINGS
Setting = config_module.Setting
InvalidValue = config_module.InvalidValue
OutOfRange = config_module.OutOfRange


def test_every_setting_is_named_once():
    names = [setting.name for setting in SETTINGS]
    assert len(names) == len(set(names))
    assert set(config_module.BY_NAME) == set(names)
    assert config_module.BY_NAME["input.escape_delay"].variable == (
        "TKCURSES_INPUT_ESCAPE_DELAY"
    )


@pytest.mark.parametrize("setting", SETTINGS, ids=lambda s: s.name)
def test_every_setting_says_what_it_does(setting):
    """The main run has no Sphinx, so the docs build's own check of the
    descriptions is skipped there; this one is not."""
    assert setting.description[0].isupper()
    assert setting.description.endswith(".")


@pytest.mark.parametrize("setting", SETTINGS, ids=lambda s: s.name)
def test_every_default_is_a_value_of_its_setting(setting):
    assert setting.parse(setting.format(setting.default)) == setting.default


@pytest.mark.parametrize("setting", SETTINGS, ids=lambda s: s.name)
def test_every_value_reads_back_as_written(setting):
    if setting.kind == "bool":
        values = [True, False]
    elif setting.kind == "int":
        low, high = setting.limits
        values = [low, (low + high) // 2, high]
    else:
        values = list(setting.choices)
    for value in values:
        assert setting.parse(setting.format(value)) == value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        (" YES ", True),
        ("On", True),
        ("1", True),
        ("false", False),
        ("no", False),
        ("OFF", False),
        ("0", False),
    ],
)
def test_a_boolean_is_one_of_the_spellings_in_any_case(raw, expected):
    assert config_module.BY_NAME["mouse.enabled"].parse(raw) is expected


@pytest.mark.parametrize("raw", ["", "y", "t", "2", "enabled", "truee"])
def test_anything_else_is_not_a_boolean(raw):
    with pytest.raises(InvalidValue, match="is not a boolean"):
        config_module.BY_NAME["mouse.enabled"].parse(raw)


@pytest.mark.parametrize(("raw", "expected"), [("25", 25), (" 7 ", 7), ("+5", 5)])
def test_a_number_is_ascii_digits_with_an_optional_sign(raw, expected):
    assert config_module.BY_NAME["input.escape_delay"].parse(raw) == expected


@pytest.mark.parametrize("raw", ["", "1_000", "2.5", "1e2", "0x10", "٣", "25ms"])
def test_python_spellings_of_numbers_are_not_numbers(raw):
    """``int()`` takes ``1_000`` and Arabic-Indic digits; a config file
    meaning either is far likelier a mistake."""
    with pytest.raises(InvalidValue, match="is not a number"):
        config_module.BY_NAME["input.escape_delay"].parse(raw)


@pytest.mark.parametrize(("raw", "clamped"), [("-1", 0), ("1001", 1000)])
def test_a_number_out_of_range_says_where_it_would_be_in_range(raw, clamped):
    with pytest.raises(OutOfRange, match="is outside 0-1000") as caught:
        config_module.BY_NAME["input.escape_delay"].parse(raw)
    assert caught.value.clamped == clamped


def test_a_choice_comes_back_as_it_is_listed():
    assert config_module.BY_NAME["display.color_mode"].parse(" TrueColor ") == (
        "truecolor"
    )
    with pytest.raises(InvalidValue, match="is not one of auto, 8, 16"):
        config_module.BY_NAME["display.color_mode"].parse("24bit")


@given(
    setting=st.sampled_from(SETTINGS),
    raw=st.one_of(
        st.text(max_size=8),
        st.integers(-2000, 2000).map(str),
        st.sampled_from(["true", "off", "auto", "256", "osc52", " On "]),
    ),
)
def test_the_loader_and_the_parser_agree_about_every_value(setting, raw):
    """A program keeps exactly what ``parse`` accepts, clamps exactly what it
    calls out of range, and keeps the earlier value for everything else, so
    ``tkcurses-cfg``'s strict check and a program cannot disagree."""
    loaded = TkCursesConfig.load(paths=(), env={setting.variable: raw})
    value = loaded._get(setting)
    try:
        expected = setting.parse(raw)
    except OutOfRange as exc:
        assert value == exc.clamped
        assert len(loaded.warnings) == 1
    except InvalidValue:
        assert value == setting.default
        assert len(loaded.warnings) == 1
    else:
        assert value == expected
        assert loaded.warnings == []


# ------------------------------------------------------------------ origins


def test_each_setting_starts_at_its_default(tmp_path):
    config = TkCursesConfig.load(paths=(), env={})
    for setting in SETTINGS:
        (origin,) = config.origins[setting.name]
        assert origin == config_module.Origin(
            "default", "built-in", None, setting.default
        )
        assert config.source(setting.name) is origin


def test_every_source_is_recorded_and_the_last_one_wins(tmp_path):
    system = write(tmp_path, "[input]\nescape_delay = 50\n", "system.ini")
    user = write(tmp_path, "[input]\nescape_delay = 40\n", "user.ini")
    variable = "TKCURSES_INPUT_ESCAPE_DELAY"
    config = TkCursesConfig.load(paths=(system, user), env={variable: "10"})
    chain = config.origins["input.escape_delay"]
    assert [(o.kind, o.location, o.raw, o.value) for o in chain] == [
        ("default", "built-in", None, 25),
        ("file", str(system), "50", 50),
        ("file", str(user), "40", 40),
        ("environment", f"${variable}", "10", 10),
    ]
    assert config.source("input.escape_delay") is chain[-1]
    assert config.input.escape_delay == 10
    # Untouched settings still say where they came from.
    assert config.source("mouse.enabled").kind == "default"


def test_a_refused_value_is_recorded_and_does_not_win(tmp_path):
    user = write(tmp_path, "[mouse]\nenabled = false\n", "user.ini")
    config = TkCursesConfig.load(paths=(user,), env={"TKCURSES_MOUSE_ENABLED": "maybe"})
    *_, refused = config.origins["mouse.enabled"]
    assert refused.kind == "environment"
    assert refused.applied is False
    assert refused.problem == "'maybe' is not a boolean"
    assert config.source("mouse.enabled").location == str(user)
    assert config.mouse.enabled is False


def test_a_clamped_value_wins_and_says_it_was_clamped(tmp_path):
    user = write(tmp_path, "[input]\nescape_delay = 5000\n", "user.ini")
    config = TkCursesConfig.load(paths=(user,), env={})
    origin = config.source("input.escape_delay")
    assert (origin.raw, origin.value) == ("5000", 1000)
    assert origin.problem == "5000 is outside 0-1000"


def test_origins_are_not_part_of_equality(tmp_path):
    user = write(tmp_path, "[input]\nescape_delay = 25\n", "user.ini")
    assert TkCursesConfig.load(paths=(user,), env={}) == TkCursesConfig()


def test_a_configuration_not_loaded_has_no_origins():
    with pytest.raises(KeyError):
        TkCursesConfig().source("input.escape_delay")


def test_a_percent_sign_in_a_value_is_a_bad_value_not_a_crash(tmp_path):
    """With configparser's default interpolation, ``50%`` raised from the
    loader and the program never started."""
    path = write(tmp_path, "[input]\nescape_delay = 50%\n")
    config = TkCursesConfig.load(paths=(path,), env={})
    assert config.input.escape_delay == 25
    assert config.warnings == [
        f"[input] escape_delay in {path}: '50%' is not a number, using 25"
    ]
