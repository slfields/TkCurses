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

"""``tkcurses-cfg``'s command line: list, get, set, unset, check, path, init.

Everything a person can do here goes through the same pieces a program
uses or will use - :class:`TkCursesConfig` to say what a program would
see, :class:`IniFile` to check and edit, :mod:`.store` to save - so the
command describes the configuration rather than its own idea of it.

Standard output carries only what was asked for, so a script can use it;
notes, warnings and errors go to standard error. Every argument is checked
before anything is read or written, and every failure ends with its own
exit status, listed in ``--help``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tkcurses._cfg import store
from tkcurses._cfg.errors import CfgError, FileSyntaxError
from tkcurses._cfg.inifile import IniFile, describe_values, lookup, starter_text
from tkcurses._core.config import (
    REMOVED,
    SETTINGS,
    InvalidValue,
    Origin,
    Setting,
    TkCursesConfig,
    config_paths,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

PROG = "tkcurses-cfg"

EXIT_CODES = """\
exit status:
  0    done; for check, no errors (warnings allowed)
  1    an unexpected error - rerun with --debug and report it
  2    the command line could not be understood
  3    no such setting
  4    a value that the setting does not take, in the command or a file
  5    a file that cannot be read as a configuration file
  6    permission denied, or a read-only file system
  7    another tkcurses-cfg kept the file locked past --lock-timeout
  8    the disk is full, over quota, or failed
  9    init found a file already there; give --force to replace it
  130  interrupted (Ctrl-C, SIGTERM, SIGHUP); nothing was changed
"""

DESCRIPTION = """\
Inspect and change TkCurses's configuration: the settings a person at the
terminal can give without changing a program. Each setting comes from, in
rising order, its default, the system-wide file, your own file, and a
TKCURSES_* environment variable.

Run alone at a terminal, it opens a screen for looking and changing: the
same as edit, which also takes --global and --file.
"""

EXAMPLES = """\
examples:
  tkcurses-cfg list                      every setting and where it comes from
  tkcurses-cfg list --sources            ... and everything that offered a value
  tkcurses-cfg get display.color_mode    one value, for a script
  tkcurses-cfg set input.escape_delay 50 in your own file
  sudo tkcurses-cfg set --global mouse.enabled off
  tkcurses-cfg unset input.escape_delay  back to what the other files say
  tkcurses-cfg check                     find mistakes in the files
  tkcurses-cfg edit --file ./test.ini    a screen for another file
"""


# ----------------------------------------------------------- the files


@dataclass(frozen=True)
class Files:
    """The two files a program reads, as this run of the command sees them."""

    system: Path
    user: Path
    #: How ``user`` is shown: ``user``, or ``file`` when ``--file`` named it.
    user_label: str

    def label(self, origin: Origin) -> str:
        if origin.kind == "file":
            if origin.location == str(self.system):
                return "system"
            if origin.location == str(self.user):
                return self.user_label
            return "file"
        return origin.kind


def files_for(args: argparse.Namespace) -> Files:
    system, user = config_paths()
    if args.file is not None:
        return Files(system, args.file, "file")
    return Files(system, user, "user")


def target_for(args: argparse.Namespace, files: Files) -> Path:
    """The file an edit goes to."""
    if getattr(args, "global_", False):
        return files.system
    return files.user


def load(files: Files) -> TkCursesConfig:
    return TkCursesConfig.load(paths=(files.system, files.user))


# ------------------------------------------------------- the commands


def cmd_list(args: argparse.Namespace) -> int:
    files = files_for(args)
    if args.defaults:
        rows = [
            (s.name, s.display(s.default), describe_values(s), s.variable)
            for s in SETTINGS
        ]
        if args.json:
            _json(
                {
                    "settings": [
                        {
                            "name": s.name,
                            "default": s.default,
                            "unit": s.unit_name,
                            "takes": describe_values(s),
                            "variable": s.variable,
                            "description": s.description.replace("``", ""),
                        }
                        for s in SETTINGS
                    ]
                }
            )
            return 0
        _table(("SETTING", "DEFAULT", "TAKES", "VARIABLE"), rows)
        return 0

    config = load(files)
    shown = [
        s
        for s in SETTINGS
        if not args.changed or config.source(s.name).kind != "default"
    ]
    if args.json:
        _json(
            {
                "settings": [_setting_json(s, config, files) for s in shown],
                "warnings": config.warnings,
            }
        )
        return 0
    if args.sources:
        # Each refused value is on its own row there, with its reason, so
        # the loader's warnings would only say it twice.
        for index, setting in enumerate(shown):
            if index:
                print()
            _print_chain(setting, config, files)
        _footnote(config, shown)
        return 0
    if not shown:
        print("Every setting is at its default.")
        _warn_all(config.warnings)
        return 0
    values: list[tuple[str, str, str]] = []
    for setting in shown:
        origin = config.source(setting.name)
        mark = " *" if origin.kind == "environment" else ""
        values.append(
            (
                setting.name,
                setting.display(config._get(setting)),
                files.label(origin) + mark,
            )
        )
    _table(("SETTING", "VALUE", "SOURCE"), values)
    _legend(config, shown, files)
    _footnote(config, shown)
    _warn_all(config.warnings)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    setting = lookup(args.name)
    files = files_for(args)
    config = load(files)
    _warn_all(w for w in config.warnings if setting.key in w or "could not" in w)
    origin = config.source(setting.name)
    if args.json:
        _json(_setting_json(setting, config, files))
    else:
        print(setting.format(config._get(setting)))
    if origin.kind == "environment":
        _note(
            f"{origin.location} sets this in this shell's environment, which "
            "overrides both files"
        )
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    setting = lookup(args.name)
    files = files_for(args)
    target = target_for(args, files)
    saved = store.edit(
        target,
        lambda ini: ini.set(setting.name, args.value),
        timeout=args.lock_timeout,
        admin_hint=_admin_hint(args, files, target),
    )
    entry = saved.ini.get(setting.name)
    assert entry is not None
    shown = setting.display(setting.parse(entry.value))  # the file's text, parsed
    if saved.changed:
        print(f"{setting.name} = {shown} in {show(target)}")
    else:
        print(f"{setting.name} is already {shown} in {show(target)}; nothing changed")
    _warn_all(saved.warnings)
    _shadowed(setting, files, target)
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    files = files_for(args)
    target = target_for(args, files)
    name = args.name
    saved = store.edit(
        target,
        lambda ini: ini.unset(name),
        timeout=args.lock_timeout,
        admin_hint=_admin_hint(args, files, target),
    )
    _warn_all(saved.warnings)
    if not saved.changed:
        print(f"{show(target)} does not set {name}; nothing changed")
        return 0
    print(f"{name} removed from {show(target)}")
    try:
        setting = lookup(name)
    except CfgError:
        return 0  # a removed or unknown key: there is no value to report
    config = load(files)
    origin = config.source(setting.name)
    _note(
        f"{setting.name} is now {setting.display(config._get(setting))}, "
        f"from {_where(origin, files)}"
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    files = files_for(args)
    worst = 0
    errors = warnings = 0
    for path in (files.system, files.user):
        try:
            ini = IniFile.read(path)
        except FileSyntaxError as exc:
            print(f"error: {exc}")
            errors += 1
            worst = max(worst, exc.exit_code)
            continue
        except OSError as exc:
            print(f"error: {path}: cannot be read: {exc.strerror}")
            errors += 1
            worst = max(worst, store.PermissionDenied.exit_code)
            continue
        if not ini.lines and not path.exists():
            continue
        for problem in ini.problems():
            kind = "error" if problem.blocking else "warning"
            print(
                f"{kind}: {path}, line {problem.line}: {problem.name}: {problem.message}"
            )
            if problem.blocking:
                errors += 1
                worst = max(worst, 4)
            else:
                warnings += 1
    for setting in SETTINGS:
        raw = os.environ.get(setting.variable)
        if raw is None:
            continue
        try:
            setting.parse(raw)
        except InvalidValue as exc:
            print(
                f"error: ${setting.variable}: {exc}; it takes "
                f"{describe_values(setting)}"
            )
            errors += 1
            worst = max(worst, 4)
    for removed in REMOVED:
        if removed.variable in os.environ:
            print(
                f"warning: ${removed.variable} no longer has any effect: "
                f"{removed.why.replace('``', '')}"
            )
            warnings += 1
    checked = [show(p) for p in (files.system, files.user) if p.exists()]
    summary = f"{errors} error{'s' * (errors != 1)}, {warnings} warning{'s' * (warnings != 1)}"
    where = ", ".join(checked) if checked else "no configuration files exist"
    print(f"{summary} ({where}; and this shell's environment)")
    return worst


def cmd_path(args: argparse.Namespace) -> int:
    files = files_for(args)
    print(target_for(args, files))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    files = files_for(args)
    target = target_for(args, files)
    saved = store.overwrite(
        target,
        starter_text(),
        replace=args.force,
        timeout=args.lock_timeout,
        admin_hint=_admin_hint(args, files, target),
    )
    print(f"wrote {show(target)}: every setting, commented out at its default")
    if saved.backup is not None:
        _note(f"the previous file is kept as {show(saved.backup)}")
    _warn_all(saved.warnings)
    return 0


# --------------------------------------------------------------- output


def _where(origin: Origin, files: Files) -> str:
    label = files.label(origin)
    if origin.kind == "default":
        return "default"
    return f"{label} ({show(origin.location)})"


def _setting_json(
    setting: Setting, config: TkCursesConfig, files: Files
) -> dict[str, Any]:
    origin = config.source(setting.name)
    return {
        "name": setting.name,
        "value": config._get(setting),
        "default": setting.default,
        "unit": setting.unit_name,
        "source": files.label(origin),
        "location": origin.location,
        "environment_override": origin.kind == "environment",
        "chain": [
            {
                "source": files.label(o),
                "location": o.location,
                "raw": o.raw,
                "value": o.value,
                "applied": o.applied,
                "problem": o.problem,
            }
            for o in config.origins[setting.name]
        ],
    }


def _print_chain(setting: Setting, config: TkCursesConfig, files: Files) -> None:
    winner = config.source(setting.name)
    print(f"{setting.name} = {setting.display(config._get(setting))}")
    rows = []
    for origin in config.origins[setting.name]:
        if origin is winner:
            mark = ">"
        elif origin.applied:
            mark = " "
        else:
            mark = "x"
        shown = (
            setting.display(origin.value)
            if origin.value is not None
            else (origin.raw or "").strip()
        )
        note = f"  ({origin.problem})" if origin.problem else ""
        where = "" if origin.kind == "default" else show(origin.location)
        rows.append((f"  {mark} {files.label(origin)}", shown, where + note))
    _table(None, rows)


def _legend(config: TkCursesConfig, shown: Sequence[Setting], files: Files) -> None:
    """Which file each label in the SOURCE column is."""
    used = {files.label(config.source(s.name)) for s in shown}
    rows = [
        (label, show(str(path)))
        for label, path in (("system", files.system), (files.user_label, files.user))
        if label in used
    ]
    if rows:
        print()
        _table(None, [(f"{label}:", where) for label, where in rows])


def _footnote(config: TkCursesConfig, shown: Sequence[Setting]) -> None:
    variables = [
        config.source(s.name).location
        for s in shown
        if config.source(s.name).kind == "environment"
    ]
    if variables:
        print()
        print(f"* Set in this shell's environment ({', '.join(variables)}),")
        print("  which overrides both files. Programs started from another shell")
        print("  may not have it.")


def _table(header: Sequence[str] | None, rows: Sequence[Sequence[str]]) -> None:
    lines = ([list(header)] if header else []) + [list(r) for r in rows]
    if not lines:
        return
    widths = [max(len(line[i]) for line in lines) for i in range(len(lines[0]) - 1)]
    for line in lines:
        cells = [
            cell.ljust(width) for cell, width in zip(line, widths, strict=False)
        ] + [line[-1]]
        print("  ".join(cells).rstrip())


def _json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def show(path: str | Path) -> str:
    """A path for a person: the home directory as ``~``."""
    text = str(path)
    home = str(Path.home())
    if home != "/" and (text == home or text.startswith(home + os.sep)):
        return "~" + text[len(home) :]
    return text


def _note(text: str) -> None:
    sys.stdout.flush()  # after what it is a note on, even into a pipe
    print(f"note: {text}", file=sys.stderr)


def _warn_all(warnings: Any) -> None:
    sys.stdout.flush()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)


def _shadowed(setting: Setting, files: Files, target: Path) -> None:
    """Say so when what was just set is not what a program will use."""
    if target == files.system:
        try:
            entry = IniFile.read(files.user).get(setting.name)
        except (CfgError, OSError):
            entry = None
        if entry is not None:
            _note(
                f"{show(files.user)} sets {setting.name} to {entry.value}, which "
                "overrides the system-wide file for that user"
            )
    raw = os.environ.get(setting.variable)
    if raw is not None:
        _note(
            f"${setting.variable}={raw} is set in this shell's environment and "
            "overrides both files for programs started from here"
        )


def _admin_hint(args: argparse.Namespace, files: Files, target: Path) -> str | None:
    if target != files.system:
        return None
    argv = args.argv if args.argv is not None else sys.argv[1:]
    return "The system-wide file needs root: " + shlex.join(["sudo", PROG, *argv])


# --------------------------------------------------------------- parsing


def _timeout(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a number of seconds"
        ) from None
    if not math.isfinite(value) or not 0 <= value <= store.MAX_LOCK_TIMEOUT:
        raise argparse.ArgumentTypeError(
            f"{text} is not from 0 to {store.MAX_LOCK_TIMEOUT:g} seconds"
        )
    return value


def _file(text: str) -> Path:
    if not text or "\0" in text:
        raise argparse.ArgumentTypeError(f"{text!r} is not a file name")
    path = Path(text).expanduser()
    if path.is_dir():
        raise argparse.ArgumentTypeError(f"{text} is a directory, not a file")
    return path


def build_parser() -> argparse.ArgumentParser:
    # argparse accepts any unambiguous prefix of a long option by default, so
    # --def meant --defaults. Off everywhere: a script that relied on a prefix
    # would change meaning, or break, when an option sharing it was added.
    common = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    common.add_argument(
        "--file",
        type=_file,
        metavar="PATH",
        help="use PATH in place of your own configuration file",
    )
    common.add_argument(
        "--debug", action="store_true", help="show a traceback on an unexpected error"
    )
    writing = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    writing.add_argument(
        "--global",
        dest="global_",
        action="store_true",
        help="the system-wide file, for everyone, instead of your own",
    )
    writing.add_argument(
        "--lock-timeout",
        type=_timeout,
        default=10.0,
        metavar="SECONDS",
        help="how long to wait for another tkcurses-cfg to finish (default 10)",
    )

    parser = argparse.ArgumentParser(
        prog=PROG,
        description=DESCRIPTION,
        epilog=EXAMPLES + "\n" + EXIT_CODES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--version", action="version", version=_version())
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    def command(name: str, help: str, run: Any, parents: list[Any]) -> Any:
        sub = commands.add_parser(
            name,
            help=help,
            description=help[0].upper() + help[1:] + ".",
            parents=parents,
            epilog=EXIT_CODES,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            allow_abbrev=False,
        )
        sub.set_defaults(run=run)
        return sub

    listing = command(
        "list", "show every setting and where its value comes from", cmd_list, [common]
    )
    shape = listing.add_mutually_exclusive_group()
    shape.add_argument(
        "--defaults",
        action="store_true",
        help="the built-in defaults, what each takes, and its variable",
    )
    shape.add_argument(
        "--sources",
        action="store_true",
        help="every source that offered a value, the one used marked >",
    )
    listing.add_argument(
        "--changed", action="store_true", help="only settings not at their default"
    )
    listing.add_argument("--json", action="store_true", help="as JSON, for a program")

    get = command("get", "print the value a program would use", cmd_get, [common])
    get.add_argument(
        "name", metavar="NAME", help="section.key, such as input.escape_delay"
    )
    get.add_argument(
        "--json", action="store_true", help="the value with its sources, as JSON"
    )

    set_ = command(
        "set",
        "set a value in your file, or with --global the system-wide one",
        cmd_set,
        [common, writing],
    )
    set_.add_argument(
        "name", metavar="NAME", help="section.key, such as input.escape_delay"
    )
    set_.add_argument(
        "value", metavar="VALUE", help="checked against what the setting takes"
    )

    unset = command(
        "unset",
        "take a setting out of a file, so it comes from elsewhere",
        cmd_unset,
        [common, writing],
    )
    unset.add_argument(
        "name", metavar="NAME", help="section.key; a removed or unknown one is fine"
    )

    command(
        "edit",
        "look and change on a screen; what tkcurses-cfg alone does at a terminal",
        cmd_edit,
        [common, writing],
    )
    command(
        "check",
        "report every mistake in the files and the environment",
        cmd_check,
        [common],
    )
    command(
        "path",
        "print where your file, or with --global the system-wide one, is",
        cmd_path,
        [common, writing],
    )

    init = command(
        "init",
        "write a starter file with every setting commented out",
        cmd_init,
        [common, writing],
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="replace a file that is there, keeping it as .bak",
    )
    return parser


def _version() -> str:
    try:
        from tkcurses import __version__
    except ImportError:  # pragma: no cover - an uninstalled checkout
        return PROG
    return f"{PROG} {__version__}"


def _subparser(parser: argparse.ArgumentParser, command: str | None) -> Any:
    """The parser for ``command``, or ``parser`` itself for none."""
    for action in parser._actions:
        if command is not None and isinstance(action, argparse._SubParsersAction):
            return action.choices[command]
    return parser


def cmd_edit(args: argparse.Namespace) -> int:
    """The screen: ``edit``, and ``tkcurses-cfg`` alone at a terminal."""
    import curses

    from tkcurses._cfg import ui

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(
            f"{PROG} edit: needs a terminal; a script uses list, get, set and unset",
            file=sys.stderr,
        )
        return 2
    files = files_for(args)
    try:
        return ui.run(
            files.system,
            files.user,
            scope="system" if args.global_ else "user",
            user_label=files.user_label,
            timeout=args.lock_timeout,
        )
    except curses.error as exc:
        print(
            f"{PROG}: cannot show the screen in this terminal ({exc}); give a "
            f"command instead - {PROG} --help lists them",
            file=sys.stderr,
        )
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command; return its exit status."""
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    args.argv = list(argv) if argv is not None else None
    # Errors found after the subcommand is known are reported by it, so the
    # usage line shown is the one for what was typed: argparse would report
    # leftover arguments with the top-level usage.
    owner = _subparser(parser, args.command)
    if extra:
        owner.error(f"unrecognized arguments: {' '.join(extra)}")
    if args.command is None:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            parser.print_help(sys.stderr)
            return 2
        args = parser.parse_args(["edit"])  # alone at a terminal: the screen
        args.argv = []
    if getattr(args, "global_", False) and args.file is not None:
        owner.error("give --global or --file, not both")
    try:
        return int(args.run(args))
    except CfgError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print(f"{PROG}: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # The reader went away (| head): say nothing more, and do not let
        # Python complain while flushing at exit.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 1
    except Exception as exc:  # anything here is a bug
        if args.debug:
            traceback.print_exc()
        else:
            print(
                f"{PROG}: unexpected error: {exc!r}. Rerun with --debug for the "
                "details, and please report it.",
                file=sys.stderr,
            )
        return 1
