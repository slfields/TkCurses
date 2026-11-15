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

"""A sandbox for accepting ``tkcurses-cfg``: see docs/UAT_CFG.md.

``python3 -m uat.cfg_sandbox [DIR]`` makes DIR (default: a new temporary
directory) with:

- ``cfg``, which runs this checkout's ``tkcurses-cfg`` with your own
  configuration file moved to ``DIR/home/tkcurses/tkcurses.ini``, so nothing
  you do touches your real one;
- ``hold-lock FILE SECONDS``, which holds a file's save lock as another
  ``tkcurses-cfg`` would;
- ``fixtures/``, one file for each kind of file the checklist needs.

Not a numbered scenario: those are TkCurses programs, and this is a command
line. It is not run by ``python3 -m uat N``.
"""

from __future__ import annotations

import shlex
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FIXTURES = {
    "hand-written.ini": (
        "; My TkCurses settings - kept by hand.\n"
        "\n"
        "[input]\n"
        "escape_delay   =   40   ; over ssh to the build box\n"
        "\n"
        "# Slower double clicks; the trackpad is twitchy.\n"
        "[mouse]\n"
        "Click_Interval: 350\n"
    ),
    "bad-value.ini": ("[input]\nescape_delay = 5000\n\n[mouse]\nenabled = true\n"),
    "duplicate-key.ini": (
        "[display]\ncolor_mode = 256\nunicode_borders = off\ncolor_mode = 16\n"
    ),
    "continued.ini": ("[mouse]\nenabled = true\n    [display]\ncolor_mode = 8\n"),
    "leftovers.ini": (
        "[debug]\n"
        "log_level = verbose\n"
        "\n"
        "[mouse]\n"
        "click_intervl = 300\n"
        "\n"
        "[colours]\n"
        "scheme = dark\n"
    ),
}

CFG = """\
#!/bin/sh
# tkcurses-cfg from {repo}, with your own file in this sandbox. PYTHONPATH
# puts this checkout ahead of any installed TkCurses.
XDG_CONFIG_HOME={home} PYTHONPATH={src} exec {python} -c \
    'import sys; from tkcurses._cfg.cli import main; sys.exit(main())' "$@"
"""

HOLD_LOCK = """\
#!{python}
# hold-lock FILE SECONDS: take FILE's save lock, as a tkcurses-cfg mid-save
# would, and keep it.
import fcntl, os, sys, time
path = sys.argv[1] + ".lock"
os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
fcntl.flock(fd, fcntl.LOCK_EX)
print(f"holding {{path}} for {{sys.argv[2]}}s", flush=True)
time.sleep(float(sys.argv[2]))
"""


def make(directory: Path) -> Path:
    """Build the sandbox in ``directory``; return it."""
    directory.mkdir(parents=True, exist_ok=True)
    home = directory / "home"
    home.mkdir(exist_ok=True)
    fixtures = directory / "fixtures"
    fixtures.mkdir(exist_ok=True)
    for name, text in FIXTURES.items():
        (fixtures / name).write_text(text)
    cfg = directory / "cfg"
    cfg.write_text(
        CFG.format(
            repo=REPO,
            home=shlex.quote(str(home)),
            python=shlex.quote(sys.executable),
            src=shlex.quote(str(REPO / "src")),
        )
    )
    cfg.chmod(0o755)
    hold = directory / "hold-lock"
    hold.write_text(HOLD_LOCK.format(python=sys.executable))
    hold.chmod(0o755)
    return directory


def main(argv: list[str]) -> int:
    if argv:
        directory = Path(argv[0]).expanduser().resolve()
        if directory.exists() and any(directory.iterdir()):
            print(f"{directory} is not empty; give a new or empty directory")
            return 2
    else:
        directory = Path(tempfile.mkdtemp(prefix="tkcurses-cfg-uat-"))
    make(directory)
    print(f"Sandbox ready in {directory}\n")
    print(f"    cd {shlex.quote(str(directory))}")
    print("    ./cfg list\n")
    print("Then follow docs/UAT_CFG.md. Run it as yourself, not as root.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
