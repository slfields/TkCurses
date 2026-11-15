# Configuration

A few things about how TkCurses uses the terminal can be set by whoever
runs a program, without changing it: how many colours to use, whether
boxes are drawn in Unicode or ASCII, the mouse, the Escape key and the
clipboard. They are for the person at the terminal; a program decides
everything else through its own code, as with tkinter.
[Terminals](../guide/terminals.md) explains when each one helps.

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

[`tkcurses-cfg`](tkcurses-cfg.md) shows every setting and where its value
comes from, changes them in either file without disturbing the rest of it,
and checks both files for mistakes.

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
