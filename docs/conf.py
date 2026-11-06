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

"""Sphinx configuration for the TkCurses documentation (TkCurses-imii).

Pages are Markdown, read by MyST; the API reference comes from the
docstrings through autodoc, with napoleon reading their Google-style
``Args:`` and ``Raises:`` sections. Built by GitHub Actions with warnings as
errors (.github/workflows/docs.yml), and published from GitHub - Pages and a
zip on every release - rather than by Read the Docs, because the repository
is private and Read the Docs' free service builds only public ones. Decided
with the user, 2026-11-05.
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

# The project's own extensions: tkscreens draws each example's screen.
sys.path.insert(0, str(Path(__file__).parent / "_ext"))
# This checkout's library, ahead of any installed one: an editable install
# made in another checkout otherwise wins, and the reference would describe
# that one's docstrings - the trap CLAUDE.md records for the tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "TkCurses"
author = "Scott L. Fields"
copyright = "2026, Scott L. Fields"

# The installed version, which setuptools-scm took from git: a tag builds as
# exactly that tag, anything past it as a .devN. Never written by hand.
release = importlib.metadata.version("tkcurses")
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "tkscreens",
    # One entry per method, however many names it has.
    "aliases",
]

source_suffix = {".md": "markdown"}
root_doc = "index"

# docs/ also holds the UAT checklists, which are instructions for a person
# running the acceptance scenarios, not documentation of the library.
exclude_patterns = ["_build", "UAT_*.md"]

myst_enable_extensions = ["colon_fence", "deflist"]
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
# The reference's own sections, which tests/test_docstrings.py holds every
# docstring to (TkCurses-imii.3): how something differs from tkinter, and
# what TkCurses has that tkinter does not.
napoleon_custom_sections = [
    ("Differences from tkinter", "notes_style"),
    ("TkCurses extension", "notes_style"),
    # Each widget's own options, laid out as a function's arguments are.
    ("Options", "params_style"),
]
# "Sample output:" sections are turned into a heading and a run example by
# docs/_ext/tkscreens.py itself, before napoleon reads the docstring.

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_theme = "furo"
html_title = f"TkCurses {release}"
html_logo = "images/tkcurses-logo.svg"
# The square icon, for the browser tab; the logo is a wide banner.
html_favicon = "images/tkcurses-icon.svg"
html_static_path = ["_static"]
html_theme_options = {
    "sidebar_hide_name": True,
    "source_repository": "https://github.com/slfields/TkCurses/",
    "source_branch": "master",
    "source_directory": "docs/",
}

linkcheck_retries = 3
linkcheck_timeout = 30
# The repository is private, so its own pages answer 404 to the checker.
linkcheck_ignore = [r"https://github\.com/slfields/TkCurses(/.*)?"]
