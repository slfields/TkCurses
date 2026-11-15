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

"""The configuration file editor: checked, and leaves the rest alone."""

from __future__ import annotations

import difflib
import io
from configparser import ConfigParser
from configparser import Error as ConfigParserError

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tkcurses._cfg.errors import (
    BlockedByProblems,
    FileSyntaxError,
    InvalidSettingValue,
    UnknownSetting,
)
from tkcurses._cfg.inifile import IniFile, starter_text
from tkcurses._core.config import BY_NAME, SETTINGS, TkCursesConfig


def program_reads(text: str) -> dict[tuple[str, str], str] | None:
    """What a program's ``configparser`` makes of ``text``, or None if it
    refuses it - read the way ``TkCursesConfig`` reads a file, through a
    text stream with universal newlines."""
    parser = ConfigParser(inline_comment_prefixes=(";", "#"), interpolation=None)
    try:
        parser.read_file(io.StringIO(text, newline=None))
    except ConfigParserError:
        return None
    return {
        (section, key): parser.get(section, key)
        for section in parser.sections()
        for key in parser.options(section)
    }


def editor_reads(ini: IniFile) -> dict[tuple[str, str], str]:
    return {(e.section, e.key.lower()): e.value for e in ini.entries}


def parse_or_none(text: str) -> IniFile | None:
    try:
        return IniFile.parse(text)
    except FileSyntaxError:
        return None


# Lines a hand-written file might have, the awkward ones included.
LINES = st.sampled_from(
    [
        "",
        "   ",
        "[mouse]",
        "[display]",
        "[input]",
        "  [clipboard]",
        "[Mouse]",
        "[mouse] trailing",
        "[mouse",
        "[]",
        "[DEFAULT]",
        "[debug]",
        "enabled = true",
        "Enabled=false",
        "click_interval: 300",
        "click_interval = 300 ; double-click",
        "  escape_delay = 5",
        "\tcolor_mode = 256 # comment",
        "color_mode=truecolor;not a comment",
        "system = osc52",
        "primary =",
        "primary = ;empty",
        "escape_delay = 50%",
        "    continued",
        "key",
        "= value",
        "two words = x",
        "a:b = c",
        "# a comment",
        "  ; an indented comment",
        ";click_interval = 200",
        "x = 1 #",
    ]
)
# Lines that belong inside a section and are fine there.
BODY_LINES = st.sampled_from(
    [
        "",
        "# a comment",
        "  ; an indented comment",
        ";click_interval = 200",
        "enabled = true",
        "Enabled=false",
        "report_hover : on",
        "click_interval: 300",
        "click_interval = 300 ; double-click",
        "escape_delay = 5",
        "  escape_delay = 5",
        "\tcolor_mode = 256 # comment",
        "color_mode=truecolor;not a comment",
        "system = osc52",
        "primary =",
        "primary = ;empty",
        "escape_delay = 50%",
        "unknown_key = 1",
        "x = 1 #",
    ]
)
HEADERS = st.sampled_from(
    [
        "[mouse]",
        "[display]",
        "[input]",
        "[clipboard]",
        "  [mouse]",
        "[Mouse]",
        "[debug]",
    ]
)


def _key_of(line):
    """Lines that would set the same key twice, as one; the duplicate is
    tested on its own, and drawn by chance it hides everything else."""
    key = line.split("=")[0].split(":")[0].strip().lower()
    return key if key and key[0] not in "#;" else line


SECTIONED = st.tuples(
    st.lists(st.sampled_from(["", "# preamble", "; preamble"]), max_size=2),
    st.lists(
        st.tuples(HEADERS, st.lists(BODY_LINES, max_size=6, unique_by=_key_of)),
        max_size=4,
        unique_by=lambda section: section[0].strip(),
    ),
    st.lists(st.tuples(st.integers(0, 30), LINES), max_size=1),
).map(
    lambda t: _insert(
        list(t[0]) + [line for header, body in t[1] for line in [header, *body]],
        t[2],
    )
)


def _insert(lines, extras):
    for at, line in extras:
        lines.insert(min(at, len(lines)), line)
    return lines


FILES = st.tuples(
    st.one_of(SECTIONED, SECTIONED, st.lists(LINES, max_size=12)),
    st.sampled_from(["\n", "\r\n", "\r"]),
    st.booleans(),
).map(lambda t: t[1].join(t[0]) + (t[1] if t[2] and t[0] else ""))


@settings(max_examples=400)
@given(FILES)
def test_a_file_the_editor_accepts_is_read_the_same_by_a_program(text):
    """The editor's grammar is a subset of configparser's: whatever it
    accepts, a program reads key for key the same - so what the command
    shows and edits is what a program will use."""
    ini = parse_or_none(text)
    if ini is None:
        return
    assert program_reads(text) == editor_reads(ini)


@given(FILES)
def test_an_unedited_file_comes_back_byte_for_byte(text):
    ini = parse_or_none(text)
    if ini is not None:
        assert ini.text == text


@settings(max_examples=300)
@given(
    FILES,
    st.sampled_from(SETTINGS),
    st.sampled_from(["true", "off", "1", "500", "256", "auto", "command"]),
)
def test_an_edit_changes_only_its_own_line(text, setting, raw):
    ini = parse_or_none(text)
    if ini is None:
        return
    try:
        edited = ini.set(setting.name, raw)
    except (InvalidSettingValue, UnknownSetting):
        return
    expected = dict(editor_reads(ini))
    expected[(setting.section, setting.key)] = setting.format(setting.parse(raw))
    # A key spelt in another case is the same key, kept as written.
    expected = {
        k: v
        for k, v in expected.items()
        if not (k[0] == setting.section and k[1] == setting.key.lower())
    } | {(setting.section, setting.key): expected[(setting.section, setting.key)]}
    assert program_reads(edited.text) == expected
    changes = [
        op
        for op in difflib.SequenceMatcher(None, ini.lines, edited.lines).get_opcodes()
        if op[0] != "equal"
    ]
    assert len(changes) <= 2, changes  # the line itself, and a missing ending


@given(FILES, st.sampled_from(SETTINGS))
def test_unset_takes_out_only_its_own_line(text, setting):
    ini = parse_or_none(text)
    if ini is None or ini.get(setting.name) is None:
        return
    try:
        edited = ini.unset(setting.name)
    except InvalidSettingValue:
        return
    expected = {
        k: v
        for k, v in editor_reads(ini).items()
        if k != (setting.section, setting.key)
    }
    assert program_reads(edited.text) == expected
    assert len(edited.lines) == len(ini.lines) - 1


# ------------------------------------------------------------- syntax errors


@pytest.mark.parametrize(
    ("text", "line", "words"),
    [
        ("enabled = true\n", 1, "before any [section]"),
        ("[mouse]\nenabled = true\n  false\n", 3, "indented further than"),
        ("[mouse]\nenabled = true\n\n    more\n", 4, "indented further than"),
        ("[mouse] x\n", 1, "not a section header"),
        ("[mouse\n", 1, "not a section header"),
        ("[DEFAULT]\nenabled = false\n", 1, "[DEFAULT]"),
        ("[mouse]\n[input]\n[mouse]\n", 3, "first on line 1"),
        ("[mouse]\nenabled = 1\nENABLED = 0\n", 3, "first on line 2"),
        ("[mouse]\nenabled\n", 2, "is not a setting"),
        ("[mouse]\nclick interval = 3\n", 2, "no spaces in the name"),
    ],
)
def test_a_file_that_cannot_be_edited_safely_names_the_line(text, line, words):
    with pytest.raises(FileSyntaxError) as caught:
        IniFile.parse(text, "my.ini")
    assert caught.value.line == line
    assert words in str(caught.value)
    assert str(caught.value).startswith(f"my.ini, line {line}: ")


def test_every_file_refused_for_duplicates_is_one_a_program_ignores():
    """The duplicates are not the editor being fussy: configparser refuses
    them too, and the loader then reads nothing from the file at all."""
    for text in ("[mouse]\n[mouse]\n", "[mouse]\na = 1\nA = 2\n"):
        assert program_reads(text) is None


def test_a_missing_file_is_an_empty_one(tmp_path):
    ini = IniFile.read(tmp_path / "absent.ini")
    assert (ini.lines, ini.entries, ini.problems()) == ([], [], [])


def test_a_byte_order_mark_is_refused(tmp_path):
    path = tmp_path / "bom.ini"
    path.write_bytes(b"\xef\xbb\xbf[mouse]\nenabled = true\n")
    with pytest.raises(FileSyntaxError, match="byte order mark"):
        IniFile.read(path)


def test_text_that_is_not_utf8_names_its_line(tmp_path):
    path = tmp_path / "latin1.ini"
    path.write_bytes(b"[mouse]\n; caf\xe9\nenabled = true\n")
    with pytest.raises(FileSyntaxError) as caught:
        IniFile.read(path)
    assert caught.value.line == 2
    assert "is not UTF-8" in str(caught.value)


# ----------------------------------------------------------------- problems


def test_each_kind_of_problem_is_found_with_its_line():
    ini = IniFile.parse(
        "[mouse]\n"
        "click_interval = 5000\n"
        "enabled = maybe\n"
        "clik_interval = 200\n"
        "[display]\n"
        "refresh_interval = 30\n"
        "click_interval = 200\n"
        "[colours]\n"
    )
    found = [(p.line, p.name, p.kind) for p in ini.problems()]
    assert found == [
        (2, "mouse.click_interval", "invalid"),
        (3, "mouse.enabled", "invalid"),
        (4, "mouse.clik_interval", "unknown-key"),
        (6, "display.refresh_interval", "removed"),
        (7, "display.click_interval", "unknown-key"),
        (8, "colours", "unknown-section"),
    ]
    messages = {p.name: p.message for p in ini.problems()}
    assert "outside 1-1000" in messages["mouse.click_interval"]
    assert "true or false" in messages["mouse.enabled"]
    assert "did you mean mouse.click_interval?" in messages["mouse.clik_interval"]
    assert "did you mean mouse.click_interval?" in messages["display.click_interval"]
    assert "did you mean [colors]" not in messages["colours"]  # no such section


def test_only_a_bad_value_blocks_an_edit():
    ini = IniFile.parse("[mouse]\nclik_interval = 1\n[debug]\nenabled = 1\n")
    assert [p.blocking for p in ini.problems()] == [False, False]
    ini.set("input.escape_delay", "50")  # does not raise


# ------------------------------------------------------------------ editing

COMMENTED = (
    "; my settings\n"
    "[input]\n"
    "escape_delay   =   40   ; slow link\n"
    "\n"
    "[mouse]\n"
    "Enabled: yes\n"
    "# the end\n"
)


def test_an_edit_keeps_the_lines_spacing_comment_and_key_spelling():
    edited = IniFile.parse(COMMENTED).set("input.escape_delay", " 60 ")
    assert edited.text == COMMENTED.replace("   40   ;", "   60   ;")
    edited = IniFile.parse(COMMENTED).set("mouse.enabled", "OFF")
    assert edited.text == COMMENTED.replace("Enabled: yes", "Enabled: false")


def test_a_value_is_written_the_way_the_file_format_spells_it():
    edited = IniFile.parse("[display]\ncolor_mode = auto\n").set(
        "display.color_mode", "TrueColor"
    )
    assert edited.get("display.color_mode").value == "truecolor"


def test_a_new_setting_goes_after_the_last_one_in_its_section():
    edited = IniFile.parse(COMMENTED).set("mouse.click_interval", "300")
    assert edited.lines[5:8] == [
        "Enabled: yes\n",
        "click_interval = 300\n",
        "# the end\n",
    ]


def test_a_new_section_goes_at_the_end_after_a_blank_line():
    edited = IniFile.parse("[mouse]\nenabled = true").set("display.color_mode", "8")
    assert edited.text == "[mouse]\nenabled = true\n\n[display]\ncolor_mode = 8\n"


def test_an_empty_file_gets_its_first_section():
    assert IniFile.parse("").set("mouse.enabled", "no").text == (
        "[mouse]\nenabled = false\n"
    )


def test_the_files_line_endings_are_kept():
    edited = IniFile.parse("[mouse]\r\nenabled = true\r\n").set(
        "mouse.click_interval", "250"
    )
    assert edited.text == "[mouse]\r\nenabled = true\r\nclick_interval = 250\r\n"


def test_an_empty_value_is_filled_in_before_its_comment():
    edited = IniFile.parse("[clipboard]\nprimary = ;why\n").set(
        "clipboard.primary", "off"
    )
    assert edited.text == "[clipboard]\nprimary = false ;why\n"


def test_a_new_line_is_indented_so_it_does_not_join_its_neighbours():
    text = "  [mouse]\n  enabled = true\n  [input]\n  escape_delay = 30\n"
    edited = IniFile.parse(text).set("mouse.report_hover", "on")
    assert edited.lines[2] == "  report_hover = true\n"
    assert program_reads(edited.text)[("input", "escape_delay")] == "30"


def test_a_bad_value_is_refused_saying_what_the_setting_takes():
    with pytest.raises(InvalidSettingValue, match="from 0 to 1000"):
        IniFile.parse("").set("input.escape_delay", "5000")
    with pytest.raises(InvalidSettingValue, match="one of auto, 8, 16, 256"):
        IniFile.parse("").set("display.color_mode", "24bit")


def test_an_unknown_setting_is_refused_with_a_suggestion():
    with pytest.raises(UnknownSetting, match=r"did you mean input\.escape_delay"):
        IniFile.parse("").set("input.escape_dely", "5")
    with pytest.raises(UnknownSetting, match=r"did you mean mouse\.enabled"):
        IniFile.parse("").set("display.enabled", "on")
    with pytest.raises(UnknownSetting, match="no longer exists"):
        IniFile.parse("").set("debug.enabled", "on")
    with pytest.raises(UnknownSetting, match=r"section\.key"):
        IniFile.parse("").set("escape_delay", "5")


# --------------------------------------------- the rule for a broken value

BROKEN = "[input]\nescape_delay = 5000\n[mouse]\nenabled = true\n"


def test_a_file_with_a_bad_value_refuses_other_edits_naming_the_line():
    with pytest.raises(BlockedByProblems) as caught:
        IniFile.parse(BROKEN, "my.ini").set("mouse.enabled", "false")
    assert "line 2: input.escape_delay" in str(caught.value)
    assert "was not changed" in str(caught.value)
    with pytest.raises(BlockedByProblems):
        IniFile.parse(BROKEN).unset("mouse.enabled")


def test_an_edit_that_fixes_the_bad_value_is_allowed():
    fixed = IniFile.parse(BROKEN).set("input.escape_delay", "50")
    assert fixed.problems() == []
    removed = IniFile.parse(BROKEN).unset("input.escape_delay")
    assert removed.problems() == []


# ------------------------------------------------------------------- unset


def test_unset_takes_the_line_out():
    edited = IniFile.parse(COMMENTED).unset("input.escape_delay")
    assert edited.text == COMMENTED.replace("escape_delay   =   40   ; slow link\n", "")


def test_unset_cleans_out_a_removed_or_unknown_setting():
    ini = IniFile.parse("[debug]\nenabled = 1\n[mouse]\nclik = 2\n")
    assert ini.unset("debug.enabled").unset("mouse.clik").entries == []


def test_unset_of_a_setting_the_file_does_not_have_changes_nothing():
    ini = IniFile.parse(COMMENTED)
    assert ini.unset("display.color_mode") is ini
    with pytest.raises(UnknownSetting):
        ini.unset("display.colour_mode")


# --------------------------------------------------------------------- init


def test_the_starter_file_sets_nothing_and_describes_everything():
    ini = IniFile.parse(starter_text())
    assert ini.entries == []
    assert ini.problems() == []
    for setting in SETTINGS:
        assert f";{setting.key} = {setting.format(setting.default)}\n" in ini.text
        assert setting.variable in ini.text
    assert "``" not in ini.text


def test_uncommenting_every_line_of_the_starter_file_gives_the_defaults(tmp_path):
    lines = [
        line[1:] if any(line[1:].startswith(f"{s.key} =") for s in SETTINGS) else line
        for line in starter_text().splitlines(keepends=True)
    ]
    path = tmp_path / "tkcurses.ini"
    path.write_text("".join(lines))
    assert len(IniFile.read(path).entries) == len(SETTINGS)
    loaded = TkCursesConfig.load(paths=(path,), env={})
    assert loaded == TkCursesConfig()
    assert loaded.warnings == []


@pytest.mark.parametrize("setting", SETTINGS, ids=lambda s: s.name)
def test_setting_a_value_in_the_starter_file_uncomments_its_line(setting):
    ini = IniFile.parse(starter_text())
    edited = ini.set(setting.name, setting.format(setting.default))
    assert len(edited.lines) == len(ini.lines)
    (changed,) = [a for a, b in zip(ini.lines, edited.lines, strict=True) if a != b]
    assert changed == f";{setting.key} = {setting.format(setting.default)}\n"
    assert BY_NAME[setting.name] is setting
