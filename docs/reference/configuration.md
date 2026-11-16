# Configuration

A few things about how TkCurses uses the terminal can be set by whoever
runs a program, without changing it: how many colours to use, whether
boxes are drawn in Unicode or ASCII, the mouse, the Escape key and the
clipboard. They are for the person at the terminal; a program decides
everything else through its own code, as with tkinter.
[Terminals](../guide/terminals.md) explains when each one helps.

## Seeing and changing settings

[`tkcurses-cfg`](tkcurses-cfg.md), installed with TkCurses, is the easiest
way to change a setting. Run alone at a terminal, it opens a screen of
every setting, with what each one does, the value a program would use and
where that value comes from: move to one, press Enter to change it, `s` to
save.

Given a command, it does that one thing. `set` writes a setting into your
own file, making the file if there is none, and refuses a value the
setting does not take; `list --changed` shows what is no longer at its
default; `check` reads every file for mistakes; `unset` takes the setting
out again:

```console
$ tkcurses-cfg set display.unicode_borders off
display.unicode_borders = false in ~/.config/tkcurses/tkcurses.ini
$ tkcurses-cfg list --changed
SETTING                  VALUE  SOURCE
display.unicode_borders  false  user

user:  ~/.config/tkcurses/tkcurses.ini
$ tkcurses-cfg check
0 errors, 0 warnings (~/.config/tkcurses/tkcurses.ini; and this shell's environment)
$ tkcurses-cfg unset display.unicode_borders
display.unicode_borders removed from ~/.config/tkcurses/tkcurses.ini
note: display.unicode_borders is now true, from default
```

A setting is named by its section and key, as below: `unicode_borders` in
`[display]` is `display.unicode_borders`. `tkcurses-cfg list` shows them
all. [Its page](tkcurses-cfg.md) describes every command, the screen, and
how it keeps a file safe while changing it.

## Where settings come from

Each setting can be given in three places. Later ones win:

1. `/etc/tkcurses/tkcurses.ini`, for everyone on the machine.
2. `~/.config/tkcurses/tkcurses.ini`, for one user - or
   `$XDG_CONFIG_HOME/tkcurses/tkcurses.ini` if `XDG_CONFIG_HOME` is set.
3. An environment variable, for one run:

   ```console
   $ TKCURSES_DISPLAY_COLOR_MODE=8 python3 app.py
   ```

A setting given nowhere has its default. The files are INI files, a
section in brackets and then `key = value` lines; `;` or `#` starts a
comment:

```ini
[mouse]
click_interval = 400   ; slower double clicks

[display]
unicode_borders = off
```

Settings are read once, when the program starts.

## Values

An on-or-off setting takes `on`, `true`, `yes` or `1` for on and `off`,
`false`, `no` or `0` for off, in any case. A setting with named values
takes them in any case too: `TrueColor` is `truecolor`.

A value that cannot be read never stops a program from starting. It is
ignored and the default used; a number out of range is brought to the
nearest end of it. Either is reported on the terminal when the program
ends, once the screen has been given back - there is nowhere to say it
while the program is running.

```{include} _configuration_settings.md
```
