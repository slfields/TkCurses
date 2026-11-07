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

The settings, their environment variables and ranges come from the table
the configuration is read through (``_FIELDS``), the allowed values from
``_CHOICES``, the defaults from the settings dataclasses and each
description from the ``#:`` comment on its field, so a setting added,
removed or changed in the code is changed here too. The settings that were
removed come from ``_REMOVED``.

Written into the source tree when the build starts
(``docs/reference/_configuration_settings.md``, ignored by git) and
included by ``docs/reference/configuration.md``, which holds the prose.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sphinx.pycode import ModuleAnalyzer

from tkcurses._core import config

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "docs" / "reference" / "_configuration_settings.md"

#: A reST literal, ``like this``, as Markdown writes it.
LITERAL = re.compile(r"``(.+?)``")

#: The dataclass each section's settings are fields of.
SECTIONS = {
    "mouse": config.MouseSettings,
    "display": config.DisplaySettings,
    "input": config.InputSettings,
    "clipboard": config.ClipboardSettings,
}


def markdown(text: str) -> str:
    return LITERAL.sub(r"`\1`", text)


def descriptions() -> dict[tuple[str, str], str]:
    """Each field's ``#:`` comment, by section and key."""
    found = ModuleAnalyzer.for_module(config.__name__).find_attr_docs()
    names = {cls.__name__: section for section, cls in SECTIONS.items()}
    return {
        (names[owner], key): " ".join(line.strip() for line in lines).strip()
        for (owner, key), lines in found.items()
        if owner in names
    }


def values(section: str, key: str, kind: str, limits: Any) -> str:
    if kind == "bool":
        return "on or off"
    if kind == "int":
        low, high = limits
        return f"a number, {low} to {high}"
    return ", ".join(f"`{choice}`" for choice in config._CHOICES[(section, key)])


def default(value: Any) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    return f"`{value}`"


def render() -> str:
    described = descriptions()
    defaults = config.TkCursesConfig()
    lines: list[str] = []
    current = None
    for section, key, kind, variable, limits in config._FIELDS:
        if section != current:
            current = section
            lines += [f"## `[{section}]`", ""]
        lines += [
            f"### `{key}`",
            "",
            f"- **Environment variable:** `{variable}`",
            f"- **Values:** {values(section, key, kind, limits)}",
            f"- **Default:** {default(getattr(getattr(defaults, section), key))}",
            "",
            markdown(described[(section, key)]),
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
    for section, key, variable, why in config._REMOVED:
        lines.append(f"| `[{section}] {key}` | `{variable}` | {markdown(why)} |")
    return "\n".join(lines) + "\n"


def write(_app: Any = None) -> None:
    text = render()
    if not FRAGMENT.exists() or FRAGMENT.read_text() != text:
        FRAGMENT.write_text(text)


def setup(app: Any) -> dict[str, Any]:
    app.connect("builder-inited", write)
    return {"parallel_read_safe": True, "version": "1"}
