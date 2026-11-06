# API reference

Every class and function TkCurses provides. It is being written module by
module.

## How to read it

TkCurses follows tkinter's API, so most of what it provides is documented
the way tkinter's is: what a class or method does and what it takes. Two
headings mark where it is not the same.

**Differences from tkinter** says where TkCurses behaves differently from
tkinter and Tk. Most come from the terminal: it counts in character cells
rather than pixels, it has one screen rather than many windows, and it can
show only the colours and characters the terminal has. A themed (`ttk`)
widget that has a method only the classic widget has in tkinter lists it
here as well, so a program that relies on it knows it will not run on
tkinter.

**TkCurses extension** marks API that tkinter does not have at all - the
`tkcurses.curses` and `tkcurses.panel` modules, and a few methods such as
`winfo_colordepth`. A program that uses one runs only on TkCurses.

Anything without either heading behaves as tkinter's does, and tkinter's
own documentation also applies to it.
