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

"""The configuration reference: every setting, generated from the code.

Every setting - its environment variable, range or allowed values, default
and description - comes from the table the configuration is read through
(``SETTINGS``), so a setting added, removed or changed in the code is
changed here too. The settings that were removed come from ``REMOVED``.

Written into the source tree when the build starts
(``docs/reference/_configuration_settings.md``, ignored by git) and
included by ``docs/reference/configuration.md``, which holds the prose.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tkcurses._core import config

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "docs" / "reference" / "_configuration_settings.md"

#: A reST literal, ``like this``, as Markdown writes it.
LITERAL = re.compile(r"``(.+?)``")

#: The dataclass each section's settings are fields of.
SECTIONS = config.SECTIONS


def markdown(text: str) -> str:
    return LITERAL.sub(r"`\1`", text)


def descriptions() -> dict[tuple[str, str], str]:
    """Each setting's description, by section and key."""
    return {
        (setting.section, setting.key): setting.description
        for setting in config.SETTINGS
    }


def values(setting: config.Setting) -> str:
    if setting.kind == "bool":
        return "on or off"
    if setting.kind == "int":
        assert setting.limits is not None
        low, high = setting.limits
        return f"a number, {low} to {high}"
    assert setting.choices is not None
    return ", ".join(f"`{choice}`" for choice in setting.choices)


def default(value: Any) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    return f"`{value}`"


def render() -> str:
    lines: list[str] = []
    current = None
    for setting in config.SETTINGS:
        if setting.section != current:
            current = setting.section
            lines += [f"## `[{current}]`", ""]
        lines += [
            f"### `{setting.key}`",
            "",
            f"- **Environment variable:** `{setting.variable}`",
            f"- **Values:** {values(setting)}",
            f"- **Default:** {default(setting.default)}",
            "",
            markdown(setting.description),
            "",
        ]
    lines += [
        "## Removed settings",
        "",
        "Earlier versions accepted these and did nothing with them. A program",
        "that still sets one is told, when it ends, that it no longer has any",
        "effect.",
        "",
        "| Setting | Environment variable | Why there is nothing to set |",
        "|---|---|---|",
    ]
    for section, key, variable, why in config.REMOVED:
        lines.append(f"| `[{section}] {key}` | `{variable}` | {markdown(why)} |")
    return "\n".join(lines) + "\n"


def write(_app: Any = None) -> None:
    text = render()
    if not FRAGMENT.exists() or FRAGMENT.read_text() != text:
        FRAGMENT.write_text(text)


def setup(app: Any) -> dict[str, Any]:
    app.connect("builder-inited", write)
    return {"parallel_read_safe": True, "version": "1"}
