# Acceptance: `tkcurses-cfg`

One question: **can a person see where each setting comes from, change it
without fear, and understand every refusal?**

`tkcurses-cfg` (`TkCurses-kge7`) shows and edits the configuration. Its
library was accepted by invariants - `tests/test_cfg_invariants.py` - because
that part has nothing to look at. This is the part a person uses: what it
prints, whether a message says what to do, whether a hand-kept file survives
an edit. This page covers the command line (`TkCurses-kge7.4`). The
interactive screen (`TkCurses-kge7.5`) gets its own section when it lands.

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
| Date | |
| Result | |

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
