# tkcurses-cfg

`tkcurses-cfg` shows and changes the [configuration](configuration.md):
what each setting is, where its value comes from, and what a program
started now would use. It edits your own configuration file or, as root,
the system-wide one, and checks both for mistakes. It is installed with
TkCurses.

Every setting has a name made of its section and key, such as
`input.escape_delay` for `escape_delay` in the `[input]` section.

Run alone at a terminal, `tkcurses-cfg` opens [a screen](#the-interactive-screen)
for looking and changing; given a command, it does that one thing and
prints the result, for a person or a script.

## Seeing the configuration

`list` shows every setting, the value a program would use, and where that
value comes from. With nothing set anywhere, everything is a default:

```console
$ tkcurses-cfg list
SETTING                  VALUE   SOURCE
mouse.click_interval     200 ms  default
mouse.enabled            true    default
mouse.report_motion      true    default
mouse.report_hover       false   default
display.color_mode       auto    default
display.unicode_borders  true    default
display.direct_images    true    default
input.escape_delay       25 ms   default
clipboard.system         auto    default
clipboard.primary        true    default
```

A value that counts something is shown with its unit: `ms` is
milliseconds.

`list --defaults` adds what each setting takes and the environment variable
that overrides it, and [the configuration reference](configuration.md)
describes each one.

`get` prints one value and nothing else - no unit either - for a script:

```console
$ tkcurses-cfg get display.color_mode
auto
```

## Changing a setting

`set` writes the value into your own file, making the file if there is
none. A value is given as a plain number, without its unit, and is checked
against what the setting takes and refused if it is not one:

```console
$ tkcurses-cfg set input.escape_delay 50
input.escape_delay = 50 ms in ~/.config/tkcurses/tkcurses.ini
$ tkcurses-cfg set input.escape_delay soon
tkcurses-cfg: input.escape_delay: 'soon' is not a number; it takes a whole number of milliseconds from 0 to 1000
$ tkcurses-cfg set display.colour_mode 256
tkcurses-cfg: there is no setting display.colour_mode; did you mean display.color_mode?
```

`list --changed` shows only what is no longer at its default, and names
the files the values came from:

```console
$ tkcurses-cfg list --changed
SETTING             VALUE  SOURCE
input.escape_delay  50 ms  user

user:  ~/.config/tkcurses/tkcurses.ini
```

`unset` takes a setting out of the file again, so it comes from wherever
else it is given, and says what that now is:

```console
$ tkcurses-cfg unset input.escape_delay
input.escape_delay removed from ~/.config/tkcurses/tkcurses.ini
note: input.escape_delay is now 25 ms, from default
```

`--global` does the same to the system-wide file, which applies to everyone
on the machine and usually needs root: `sudo tkcurses-cfg set --global
mouse.enabled off`. Your own file still overrides it for you, and
`tkcurses-cfg` says so when it does.

## Where a value comes from

A `TKCURSES_*` environment variable overrides both files. `list` marks a
setting the environment decides, because nothing in either file will change
it while the variable is set:

```console
$ TKCURSES_DISPLAY_COLOR_MODE=8 tkcurses-cfg list --changed
SETTING             VALUE  SOURCE
display.color_mode  8      environment *

* Set in this shell's environment ($TKCURSES_DISPLAY_COLOR_MODE),
  which overrides both files. Programs started from another shell
  may not have it.
```

`tkcurses-cfg` sees only its own environment. A variable set in another
terminal, or by whatever starts a program, is not visible to it.

`list --sources` shows every source that offered a value, in the order
they are read. The one a program uses is marked `>`, and one that could
not be used is marked `x`, with the reason:

```console
$ tkcurses-cfg set mouse.click_interval 300
mouse.click_interval = 300 ms in ~/.config/tkcurses/tkcurses.ini
$ TKCURSES_MOUSE_CLICK_INTERVAL=fast tkcurses-cfg list --sources --changed
mouse.click_interval = 300 ms
    default      200 ms
  > user         300 ms  ~/.config/tkcurses/tkcurses.ini
  x environment  fast    $TKCURSES_MOUSE_CLICK_INTERVAL  ('fast' is not a number)
```

Plain `list` reports a value that could not be used as a warning after the
table. `list --json` and `get --json` give everything `--sources` does,
with the values as JSON numbers and booleans and each setting's unit
alongside, for a program to read.

## Finding mistakes

`check` reads both files and the environment and reports everything wrong,
with the line it is on:

```console
$ tkcurses-cfg check
0 errors, 0 warnings (~/.config/tkcurses/tkcurses.ini; and this shell's environment)
```

An error is something a program would not use as written: a value the
setting does not take, or a file it cannot read at all. A warning is
something that does nothing: a setting that does not exist, perhaps
misspelt, or one that was removed from TkCurses. A program carries on past
either - an error is replaced by the setting's earlier value - so `check`
is how to find them before they surprise you.

A file is edited only if it is free of errors, other than the one the edit
fixes. `tkcurses-cfg` will also not edit a file that a program could read
differently from the way it reads it - a line indented under a setting,
which a program takes as more of that setting's value, or a `[DEFAULT]`
section - and names the line instead.

## Starting a file

`init` writes a file with every setting in it, commented out at its
default, each with what it does. To change one, take the `;` off its line
and edit the value; `set` does the same for you. `init` will not replace a
file that is there unless given `--force`, and then keeps the old one as
`tkcurses.ini.bak`.

## The interactive screen

`tkcurses-cfg` with no command opens a screen of every setting:

```text
 tkcurses-cfg - editing your file: ~/.config/tkcurses/tkcurses.ini  1 unsaved
 SETTING            IN THIS FILE   IN EFFECT  FROM
 mouse
   click_interval   300 ms         300 ms     user
   enabled          false        * false      user
   report_motion    -              true       default
   ...
──────────────────────────────────────────────────────────────────────────────
 mouse.enabled = false, from your file
 Whether to use the mouse at all. Off leaves it to the terminal, whose own text
 selection then works without holding Shift; the program is used from the
 keyboard.
 Takes true or false; default true.
 mouse.enabled: false - not saved yet.
 Space switch  u take out  r undo  s save  Tab other file  ? help  q quit
```

IN THIS FILE is what the file you are editing says, and `-` where it says
nothing. IN EFFECT and FROM are what a program started now would use and
where that comes from - with your unsaved changes counted, so you see the
result before you save it. Below the list is everything about the setting
under the cursor, and at the bottom the keys that do something there.

| Key | Does |
|---|---|
| Up, Down, PgUp, PgDn, Home, End | Move. `k` and `j` too. |
| Enter | Change the value: a list to pick from, or a field for a number, which shows the range and refuses anything outside it. |
| Space | Switch a true/false setting. |
| `u` | Take the setting out of this file, so it comes from the one below. |
| `r` | Undo this row's change. |
| Tab | Edit the other file: yours, or the system-wide one. |
| `s` | Save: lists every change, before and after, and asks first. |
| `p` | The problems in this file, and a fix for each. |
| `i` | The setting's whole description and where its value comes from. |
| `?` | Help. |
| `q` | Quit, asking first if anything is not saved. |

Nothing is written until you save, and a changed row is marked `*`. A file
with a value that is not valid takes no other change until that value is
fixed, as with `set`: a change it cannot take yet is marked `!`, and `p`
lists the bad value with the fix. The system-wide file is read-only unless
you run the screen as root. If something else changes a file while the
screen is open, the screen reads it again and keeps your changes on top.
If saving fails, your changes are kept.

Ctrl-C quits at once and says how many changes were discarded; the exit
status is 130. The screen needs a terminal of 60 by 15 or more, and works
without colour; it marks changes in bold, or in colour where the terminal
has it and `NO_COLOR` is not set. With no terminal - in a pipe or a
script - `tkcurses-cfg` alone prints its help and exits with status 2.

## Safety

A file is never left half-written. A change is written to a new file beside
the old one and swapped in at once, so a program starting at that moment
reads either the old file or the new one. If anything goes wrong first - a
full disk, a permission, Ctrl-C - nothing is changed, and the message says
so. The version before each change is kept as `tkcurses.ini.bak`.

Two `tkcurses-cfg`s changing the same file at once take turns: the second
waits up to `--lock-timeout` seconds, ten by default, for the first to
finish.

The edit changes only its own line. Comments, blank lines, the order of
settings and their spacing stay as they were.

## Exit status

| Status | Meaning |
|---|---|
| 0 | Done. For `check`, no errors, though there may be warnings. |
| 1 | An unexpected error. Run it again with `--debug` and report it. |
| 2 | The command line could not be understood. |
| 3 | No such setting. |
| 4 | A value the setting does not take, given on the command line or found in a file. |
| 5 | A file that cannot be read as a configuration file. |
| 6 | Permission denied, or a read-only file system. |
| 7 | Another `tkcurses-cfg` kept the file locked longer than `--lock-timeout`. |
| 8 | The disk is full, over quota, or failed. |
| 9 | `init` found a file already there. |
| 130 | Interrupted. Nothing was changed. |

## Options

`--file PATH` uses another file in place of your own, for every command.
`--global` makes `set`, `unset`, `init` and `path` work on the system-wide
file instead of yours. `--lock-timeout SECONDS` sets how long `set`,
`unset` and `init` wait for another `tkcurses-cfg`. `--debug` shows the
traceback of an unexpected error. `tkcurses-cfg COMMAND --help` describes
each command.
