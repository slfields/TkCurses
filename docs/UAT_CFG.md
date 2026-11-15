# Acceptance: `tkcurses-cfg`

One question: **can a person see where each setting comes from, change it
without fear, and understand every refusal?**

`tkcurses-cfg` (`TkCurses-kge7`) shows and edits the configuration. Its
library was accepted by invariants - `tests/test_cfg_invariants.py` - because
that part has nothing to look at. This is the part a person uses: what it
prints, whether a message says what to do, whether a hand-kept file survives
an edit. It has two parts, accepted separately: the command line
(`TkCurses-kge7.4`) and, at the end, the interactive screen
(`TkCurses-kge7.5`).

**How to run**

```bash
cd /path/to/TkCurses
python3 -m uat.cfg_sandbox
```

It makes a scratch directory and prints its name. `cd` there: every command
below is run from it, as `./cfg`, which is this checkout's `tkcurses-cfg`
with your own configuration file moved into the sandbox. Your real file is
never read or written. **Run it as yourself, not as root**: the system-wide
file is the real `/etc/tkcurses/tkcurses.ini`, and one check relies on not
being allowed to write it.

`echo $?` after a command prints its exit status. `./cfg --help` lists them
all.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-11-15 |
| Result | **Accepted** (command line). Run by the author: "The UAT passed, record it as accepted". Terminal and size not recorded. Raised during the run and fixed before acceptance: values that count something show their unit, and an option must be spelt in full (`--def` had run as `--defaults`). |

The boxes below are left unticked deliberately: the acceptance was given as a
whole rather than item by item, and ticking them would claim a record that was
not taken. This matches `UAT_CLIPBOARD.md`. What was driven mechanically
is in `tests/test_cfg_cli.py`, `tests/test_docs_cfg.py` and
`tests/test_uat_cfg_sandbox.py`.

## Seeing the configuration

- [ ] `./cfg list` shows every setting, its value, and `default` as the
      source of each. The columns line up. Each value that counts
      something shows its unit - `200 ms`, `25 ms` - and you never have to
      guess what a number means.
- [ ] `./cfg list --defaults` adds what each setting takes and its
      environment variable, and you could pick a value from it without
      reading anything else.
- [ ] `./cfg get display.color_mode` prints `auto` and nothing else.
- [ ] `./cfg --help` and `./cfg set --help` say what to type. The exit
      statuses are listed.
- [ ] `./cfg list --def` and `./cfg list --j` are refused: an option must be
      spelt in full. The usage shown is `list`'s, and `echo $?` is 2.

## Changing a setting

- [ ] `./cfg set input.escape_delay 50` says what it set and in which file.
      `./cfg list --changed` then shows only that setting, from `user`, and
      names the file under the table.
- [ ] `./cfg set input.escape_delay soon` refuses, saying what the setting
      takes. `echo $?` is 4. `./cfg get input.escape_delay` is still 50.
- [ ] `./cfg set input.escape_dely 5` refuses and suggests
      `input.escape_delay`. `echo $?` is 3.
- [ ] `./cfg unset input.escape_delay` says it was removed and what the value
      is now, and where that comes from.
- [ ] `./cfg set --global mouse.enabled off` is refused: permission denied,
      nothing changed, and it tells you the `sudo` command to use. `echo $?`
      is 6. No `/etc/tkcurses` appeared if there was none.

## Where a value comes from

- [ ] `TKCURSES_DISPLAY_COLOR_MODE=8 ./cfg list --changed` shows
      `display.color_mode` as `8` from `environment *`, and the footnote
      names the variable and says it overrides both files.
- [ ] `./cfg set mouse.click_interval 300`, then
      `TKCURSES_MOUSE_CLICK_INTERVAL=fast ./cfg list --sources --changed`:
      the user file's 300 is marked `>`, and the variable's `fast` is marked
      `x` with the reason. It is clear which one a program would use.
- [ ] `TKCURSES_MOUSE_ENABLED=0 ./cfg set mouse.enabled on` sets it, then
      warns that the variable will win in this shell.

## A file kept by hand

- [ ] `cat fixtures/hand-written.ini`, then
      `./cfg set --file fixtures/hand-written.ini mouse.click_interval 400`,
      then `cat` it again. Only `350` became `400`: the comments, blank lines,
      spacing, `Click_Interval:` spelling and order are as they were.
      `fixtures/hand-written.ini.bak` holds the version before.
- [ ] `./cfg set --file fixtures/bad-value.ini mouse.enabled off` is refused,
      naming line 2 and saying why. `echo $?` is 4. Then
      `./cfg set --file fixtures/bad-value.ini input.escape_delay 50` is
      allowed, because it fixes that line, and the first command now works.
- [ ] `./cfg set --file fixtures/duplicate-key.ini display.color_mode 8` is
      refused, naming line 4 and the line it repeats, and saying a program
      would ignore the whole file. `echo $?` is 5.
- [ ] `./cfg check --file fixtures/continued.ini` explains why line 3 is a
      problem in words you would act on. `echo $?` is 5.
- [ ] `./cfg check --file fixtures/leftovers.ini` gives three warnings - a
      removed setting, a misspelt one with the right spelling suggested, an
      unknown section - and `echo $?` is 0. Then
      `./cfg unset --file fixtures/leftovers.ini debug.log_level` removes the
      first of them.

A `.lock` file appears beside each file `tkcurses-cfg` has tried to change,
even when it refused. That is deliberate: deleting it would let two
`tkcurses-cfg`s both believe they held the lock.

## Starting a file

- [ ] `./cfg init` writes your file. `cat home/tkcurses/tkcurses.ini`: every
      setting is there, commented out, with what it does, and you could
      change one by hand from what it says.
- [ ] `./cfg init` again refuses because the file is there, and says to give
      `--force`. `echo $?` is 9.
- [ ] `./cfg init --force` replaces it and says where the old one was kept.

## Two at once, and interruptions

- [ ] In a second terminal in the sandbox,
      `./hold-lock home/tkcurses/tkcurses.ini 30`. While it holds,
      `./cfg set --lock-timeout 2 input.escape_delay 30` waits two seconds,
      then says another `tkcurses-cfg` holds the file and nothing was
      changed. `echo $?` is 7.
- [ ] While it still holds, `./cfg set input.escape_delay 30` and press
      Ctrl-C while it waits: it says it was interrupted and nothing was
      changed. `echo $?` is 130.
- [ ] Once `hold-lock` has finished, the same `set` goes straight through.

## Output for scripts

- [ ] `./cfg list --json | python3 -m json.tool` succeeds: the output is
      JSON and nothing else.
- [ ] `./cfg get mouse.enabled 2>/dev/null` prints only the value, even with
      `TKCURSES_MOUSE_ENABLED=1` set in front of it.

## The interactive screen

`./cfg` with no command, in the sandbox, opens the screen on the sandbox's
own file. Start each check from a fresh one -
`rm -f home/tkcurses/tkcurses.ini*` - unless it says otherwise. It wants a
terminal at least 60 columns by 15 rows.

| | |
|---|---|
| Terminal | |
| Size | |
| Date | 2026-11-15 |
| Result | **Accepted** (the screen, and paths that are not safe to write). Run by the author: "The UAT passed, record it as accepted". Terminal and size not recorded. Raised during the run and fixed before acceptance: the screen had no way to edit the system-wide file or a given one (`edit --global`, `--file`), and a security review the author asked for found six faults in how paths, the lock, reads and output were handled - see "Paths that are not safe to write". |

As above, the boxes are left unticked: the acceptance was given as a whole.
What was driven mechanically is in `tests/test_cfg_session.py`,
`tests/test_cfg_ui_tty.py` and `tests/test_cfg_safety.py`.

### Looking

- [ ] `./cfg` shows every setting under its section, with what your file
      says (`-` for nothing), what a program would use, and where that
      comes from. Numbers carry their unit.
- [ ] Moving with the arrows changes the details under the list: the
      setting's value and where it comes from, what it does, what it takes,
      and its sources. The keys at the bottom change with the row: Space on
      a true/false setting, Enter on the others.
- [ ] `i` shows the whole description and every source, lowest first.
      `?` lists every key, and both close with any key.
- [ ] `TKCURSES_MOUSE_ENABLED=0 ./cfg`: `enabled` is `false` from
      `environment`, marked out from the other rows, and the details say it
      is from the variable in this shell.

### Changing and saving

- [ ] Space on `enabled` switches it, marks the row `*`, and the top line
      counts one unsaved change. Space again undoes it: no `*`, nothing
      unsaved.
- [ ] Enter on `click_interval` opens a field that says it takes
      milliseconds from 1 to 1000. Typing `5000` says it is outside the
      range and Enter does nothing; Up brings it to 1000. Esc leaves the
      row as it was.
- [ ] Enter on `color_mode` lists its choices with the one in use marked;
      choosing `256` marks the row.
- [ ] `s` lists each change with its value before and after, and asks.
      `n` goes back with nothing written; `s` then `y` saves, says where,
      and `cat home/tkcurses/tkcurses.ini` afterwards holds exactly those
      changes.
- [ ] `u` on a setting your file holds marks it for taking out; after
      saving, the line is gone and the value comes from the default.
- [ ] Make a change and press `q`: it asks. Esc keeps editing, `d` quits
      without saving, and the file is as it was.
- [ ] Make a change and press Ctrl-C: the screen closes, the terminal is
      as it was before, and it says one unsaved change was discarded.
      `echo $?` is 130.

### When things are not simple

- [ ] `cp fixtures/bad-value.ini home/tkcurses/tkcurses.ini`, then `./cfg`.
      The bottom says there is a problem. Switch `enabled`: the row is
      marked `!` and the message says why it cannot be saved. `s` says
      the same and keeps the change.
- [ ] `p` lists the bad value with the whole message. `u` takes it out;
      the problem goes, the `!` becomes `*`, and saving writes both.
- [ ] `cp fixtures/duplicate-key.ini home/tkcurses/tkcurses.ini`, then
      `./cfg`: your file is read-only, and `p` says why and how to
      replace it.
- [ ] Tab: the top line says the system-wide file, read-only, and that it
      needs root. Space does nothing to it but say so. Tab again comes
      back to your file, with any change you had made still there.
- [ ] With the screen open, in another terminal in the sandbox:
      `./cfg set mouse.click_interval 333`. Within a second the screen
      says your file changed and shows 333.
- [ ] Make a change, then in another terminal
      `chmod 555 home/tkcurses`, and save: it says permission denied and
      that your changes are kept. `chmod 755 home/tkcurses` and save
      again: it saves.
- [ ] Shrink the terminal below 60x15: the screen says how big it needs to
      be. Grow it again: everything is back where it was. At exactly 60x15
      the list, the details and the keys all fit.
- [ ] `NO_COLOR=1 ./cfg`: changed and refused rows are still told apart,
      in bold, without colour.

### Choosing the file

- [ ] `./cfg edit` is the same screen as `./cfg` alone. `./cfg edit --help`
      lists `--global`, `--file` and `--lock-timeout`.
- [ ] `./cfg edit --global` opens on the system-wide file, read-only,
      saying it needs root.
- [ ] `cp fixtures/hand-written.ini /tmp/mine.ini`, then
      `./cfg edit --file /tmp/mine.ini`: the top line says the given file
      and its path, its values show as from `file`, and saving a change
      writes `/tmp/mine.ini` with its comments kept, leaving
      `home/tkcurses/tkcurses.ini` alone.
- [ ] `./cfg edit --global --file /tmp/mine.ini` is refused: give one or the
      other. `echo $?` is 2.
- [ ] `./cfg edit < /dev/null` says it needs a terminal. `echo $?` is 2.

### Paths that are not safe to write

- [ ] `mkdir open && chmod 777 open && echo precious > victim.txt &&
      ln -s "$PWD/victim.txt" open/cfg.ini`, then
      `./cfg init --force --file open/cfg.ini`: refused, saying anyone can
      change `open` and nothing was changed. `echo $?` is 6, and
      `cat victim.txt` still says `precious`.
- [ ] `./cfg edit --file open/cfg.ini`: the screen opens read-only and its
      bottom line says why.
- [ ] `ln -s "$PWD/made-by-lock" fixtures/hand-written.ini.lock`, then
      `./cfg set --file fixtures/hand-written.ini mouse.enabled off`:
      refused, the lock is a link. `ls made-by-lock` finds nothing.
      `rm fixtures/hand-written.ini.lock` afterwards.
- [ ] `mkfifo pipe.ini && ./cfg check --file pipe.ini` answers at once:
      not a regular file, `echo $?` is 5.
- [ ] `printf '[mouse]\nenabled = \033[2Jno\n' > esc.ini`, then
      `./cfg list --sources --file esc.ini`: the value shows as
      `\x1b[2Jno` and the terminal is not cleared.
- [ ] If you have sudo: `sudo ./cfg set --file /tmp/x.ini mouse.enabled
      off` is refused - users other than root can change `/tmp` - and
      says to use `sudo -u USER`.
