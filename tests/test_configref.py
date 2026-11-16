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

"""The configuration reference: generated from the code, and true of it."""

from __future__ import annotations

import re
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from tkcurses._core import config

# The documentation's own toolchain, which the docs workflow installs and
# runs this under; the main test run has no Sphinx.
pytest.importorskip("sphinx")
sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "_ext"))

import configref

PAGE = Path(__file__).parents[1] / "docs" / "reference" / "configuration.md"
FENCE = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)


def page_block(language: str) -> str:
    (block,) = [
        body for lang, body in FENCE.findall(PAGE.read_text()) if lang == language
    ]
    return block


def test_every_setting_has_a_section():
    sections = {f.name for f in fields(config.TkCursesConfig)} - {
        "warnings",
        "origins",
    }
    assert set(configref.SECTIONS) == sections


def test_every_setting_is_on_the_page():
    text = configref.render()
    for setting in config.SETTINGS:
        assert f"### `{setting.key}`" in text
        assert f"`{setting.variable}`" in text
    assert text.count("### ") == len(config.SETTINGS)


@pytest.mark.parametrize(
    ("section", "key"), [(setting.section, setting.key) for setting in config.SETTINGS]
)
def test_every_setting_is_described_for_a_user(section, key):
    """The description is the one on the setting's row, so a setting
    added with a careless one fails here rather than reading badly."""
    text = configref.descriptions()[(section, key)]
    assert len(text) > 40
    assert text[0].isupper() and text.endswith("."), "whole sentences"
    assert not re.search(r"TkCurses-\w+|\b_\w+|\bDEC\b|ncurses", text), text


@pytest.mark.parametrize("row", config.REMOVED)
def test_every_removed_setting_is_listed(row):
    section, key, variable, _why = row
    assert f"| `[{section}] {key}` | `{variable}` |" in configref.render()


def test_the_defaults_are_the_codes():
    text = configref.render()
    assert "### `click_interval`" in text
    block = text.split("### `click_interval`")[1].split("###")[0]
    assert "**Default:** `200`" in block
    block = text.split("### `report_hover`")[1].split("###")[0]
    assert "**Default:** off" in block


def test_the_page_includes_what_the_build_writes():
    assert configref.FRAGMENT.name in PAGE.read_text()


def test_the_example_file_means_what_the_page_says(tmp_path):
    path = tmp_path / "tkcurses.ini"
    path.write_text(page_block("ini"))
    loaded = config.TkCursesConfig.load(paths=(path,), env={})
    assert loaded.warnings == []
    assert loaded.mouse.click_interval == 400
    assert loaded.display.unicode_borders is False


def test_the_example_variable_is_a_setting():
    blocks = [
        body for lang, body in FENCE.findall(PAGE.read_text()) if lang == "console"
    ]
    named = re.findall(r"TKCURSES_\w+", "".join(blocks))
    variables = {setting.variable for setting in config.SETTINGS}
    assert named and set(named) <= variables


def test_the_on_and_off_spellings_are_the_codes():
    words = PAGE.read_text().split("## Values")[1].split("\n\n")[1]
    on, off = words.split(", in any case")[0].split(" for on and ")
    assert set(re.findall(r"`(\w+)`", on)) == config._TRUE
    assert set(re.findall(r"`(\w+)`", off)) == config._FALSE
