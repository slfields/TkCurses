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


"""The decisions in .github/workflows/release.yml, where they can be tested.

A workflow can only be run by pushing a tag, and a pushed tag is a published
release, so what the workflow decides lives here instead and the workflow
calls it:

``check TAG DIST``
    Every distribution in DIST is exactly TAG's version - ``v0.3.0rc1``
    builds ``0.3.0rc1``, with no ``.dev`` and no ``+g<hash>``. setuptools-scm
    gives a tagged commit its tag's version; anything else means the tag is
    not on the commit that was built, and a release would carry the wrong
    code under the right name.

``prerelease TAG``
    ``true`` for an rc, alpha, beta or dev tag, which GitHub then shows as a
    pre-release and does not mark Latest.

``notes TAG CHANGELOG``
    The CHANGELOG's section for that version, for the release's text. Empty
    when there is none, and the workflow then asks GitHub to list the merged
    pull requests instead.

Releases go to GitHub only, not PyPI - decided 2026-11-05, TkCurses-2q6o.5.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from packaging.utils import parse_sdist_filename, parse_wheel_filename
from packaging.version import InvalidVersion, Version


def tag_version(tag: str) -> Version:
    """``v0.3.0rc1`` -> ``0.3.0rc1``. Refuses anything that is not ``v`` and
    a plain PEP 440 release, which is all setuptools-scm will turn back into
    the same version."""
    if not tag.startswith("v"):
        raise ValueError(f"a release tag starts with v: {tag!r}")
    try:
        version = Version(tag[1:])
    except InvalidVersion:
        raise ValueError(f"not a version: {tag!r}") from None
    if version.local is not None or version.is_devrelease:
        raise ValueError(f"a release has no .dev or local part: {tag!r}")
    return version


def built_versions(dist: Path) -> dict[str, Version]:
    """The version of every sdist and wheel in ``dist``, by file name."""
    found: dict[str, Version] = {}
    for path in sorted(dist.iterdir()):
        if path.name.endswith(".whl"):
            found[path.name] = parse_wheel_filename(path.name)[1]
        elif path.name.endswith(".tar.gz"):
            found[path.name] = parse_sdist_filename(path.name)[1]
    return found


def check(tag: str, dist: Path) -> list[str]:
    """What is wrong with releasing ``dist`` as ``tag``; empty when nothing."""
    expected = tag_version(tag)
    built = built_versions(dist)
    problems = []
    kinds = {name.endswith(".whl") for name in built}
    if kinds != {True, False}:
        problems.append(f"expected one sdist and one wheel, found {sorted(built)}")
    for name, version in built.items():
        # Compared as strings too: Version("0.3.0rc1") == Version("0.3.0rc1+g1")
        # is False already, but "0.3.0-rc1" and "0.3.0rc1" are equal Versions
        # and the file name should carry the canonical spelling.
        if version != expected or str(version) != str(expected):
            problems.append(f"{name} is {version}, the tag says {expected}")
    return problems


def is_prerelease(tag: str) -> bool:
    return tag_version(tag).is_prerelease


def notes(tag: str, changelog: Path) -> str:
    """The body of the CHANGELOG section headed with this tag's version.

    Keep a Changelog's headings: ``## [0.3.0rc1] - 2026-11-20``, or
    ``## 0.3.0rc1``. The section runs to the next ``## `` heading, and link
    references at the foot of the file are not part of it.
    """
    if not changelog.is_file():
        return ""
    version = str(tag_version(tag))
    heading = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s|$)")
    lines = changelog.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return ""
    body = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") or re.match(r"^\[[^\]]+\]:\s", line):
            break
        body.append(line)
    return "\n".join(body).strip()


def main(argv: list[str]) -> int:
    command, *args = argv
    if command == "check":
        tag, dist = args
        problems = check(tag, Path(dist))
        for problem in problems:
            print(f"::error::{problem}")
        return 1 if problems else 0
    if command == "prerelease":
        (tag,) = args
        print("true" if is_prerelease(tag) else "false")
        return 0
    if command == "notes":
        tag, changelog = args
        print(notes(tag, Path(changelog)))
        return 0
    print(f"unknown command {command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
