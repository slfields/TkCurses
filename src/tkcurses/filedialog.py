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

"""Choosing a file: a browser, and the seven ways tkinter asks for one.

tkinter has two kinds of file dialog and this module has to be both.
:class:`FileDialog` and its two subclasses are written in Python and drawn
from ordinary widgets, so they come across almost unchanged. ``Open``,
``SaveAs`` and ``Directory`` are wrappers round the *platform's* file chooser
- ``tk_getOpenFile`` and friends - and a terminal has no platform chooser to
wrap, so here they are built on the same browser as the others. The seven
``ask*`` functions sit on top and are what almost everybody calls.

The browser is a directory on the left, the files in it on the right, the
pattern above and the chosen path below. It behaves the way tkinter's does,
including the parts that are easy to get wrong:

- The directory list always begins with ``..``, so there is a way up even
  from a directory whose name cannot be typed.
- The pattern is applied with ``fnmatch`` to the *names*, not the paths.
- Filtering a directory that cannot be read rings the bell and changes
  nothing, rather than emptying the lists and leaving somebody stranded.
- ``Open`` and ``SaveAs`` remember the directory and the file between calls,
  in the options, which is what makes a second save start where the first
  one did.

The checks that separate the three are all in ``ok``: loading insists the
file exists, saving insists its directory does and asks before overwriting,
and the plain dialog checks nothing at all.
"""

from __future__ import annotations

import contextlib
import fnmatch
import os
from typing import IO, TYPE_CHECKING, Any, ClassVar

import tkcurses
from tkcurses.commondialog import Dialog as _CommonDialog
from tkcurses.commondialog import fit, restore_focus_grab, take_focus_grab
from tkcurses.dialog import Dialog as _ButtonDialog

if TYPE_CHECKING:
    from tkcurses import Event, Misc, Toplevel

__all__ = [
    "Directory",
    "FileDialog",
    "LoadFileDialog",
    "Open",
    "SaveAs",
    "SaveFileDialog",
    "askdirectory",
    "askopenfile",
    "askopenfilename",
    "askopenfilenames",
    "askopenfiles",
    "asksaveasfile",
    "asksaveasfilename",
]

#: Directory and pattern remembered per ``key``, as tkinter's module-level
#: dictionary of the same name does. Memory is kept even when the dialog was
#: cancelled, which is deliberate: somebody who looked in the right place and
#: changed their mind should not have to find it again.
dialogstates: dict[str, tuple[str, str]] = {}

#: Rows the two lists get. A terminal dialog cannot be resized by dragging,
#: so the browser asks for a size that leaves room for a useful listing on
#: any terminal big enough to run the application at all.
LIST_HEIGHT = 8
LIST_WIDTH = 18


class _Browser:
    """The file browser, without any opinion about how it is answered.

    Held apart from the dialogs so that all five - the three Python ones and
    the two that stand in for the platform's - show the same thing, and so
    that the filesystem arithmetic can be exercised without a terminal.
    """

    def __init__(self, master: Misc, filetypes: Any = ()) -> None:
        self.directory: str = os.curdir
        self.filetypes = tuple(filetypes or ())

        # A chooser, but only when there is a choice. Declaring filetypes and
        # then being unable to reach any but the first is the gap this fills:
        # the patterns were read from filetypes[0] and nothing else ever
        # looked at the rest.
        self.kinds: tkcurses.OptionMenu | None = None
        self.kind: tkcurses.StringVar | None = None
        if len(self.filetypes) > 1:
            labels = [str(entry[0]) for entry in self.filetypes]
            self.kind = tkcurses.StringVar(master=master, value=labels[0])
            self.kinds = tkcurses.OptionMenu(
                master, self.kind, *labels, command=self._kind_chosen
            )
            self.kinds.pack(side="top", fill="x")

        self.filter = tkcurses.Entry(master, name="filter")
        self.filter.pack(side="top", fill="x")

        middle = tkcurses.Frame(master)
        middle.pack(expand=True, fill="both")

        self.dirs = tkcurses.Listbox(
            middle,
            name="dirs",
            height=LIST_HEIGHT,
            width=LIST_WIDTH,
            exportselection=False,  # as tkinter's FileDialog makes them
        )
        self.dirs.pack(side="left", expand=True, fill="both")
        self.dirsbar = tkcurses.Scrollbar(middle, command=self.dirs.yview)
        self.dirsbar.pack(side="left", fill="y")
        self.dirs.configure(yscrollcommand=self.dirsbar.set)

        self.files = tkcurses.Listbox(
            middle,
            name="files",
            height=LIST_HEIGHT,
            width=LIST_WIDTH,
            exportselection=False,  # as tkinter's FileDialog makes them
        )
        self.files.pack(side="left", expand=True, fill="both")
        self.filesbar = tkcurses.Scrollbar(middle, command=self.files.yview)
        self.filesbar.pack(side="left", fill="y")
        self.files.configure(yscrollcommand=self.filesbar.set)
        # The class bindings first, as tkinter's FileDialog puts them: a
        # click's release activates the item there, and the dialogs' own
        # release bindings read the active item. In the default order they
        # would read the one clicked before.
        for listbox in (self.dirs, self.files):
            tags = listbox.bindtags()
            listbox.bindtags(tags[1:] + tags[:1])

        self.selection = tkcurses.Entry(master, name="selection")
        self.selection.pack(side="bottom", fill="x")

    def _kind_chosen(self, label: Any = None) -> None:
        """Put the chosen filetype's patterns in the filter box and relist."""
        wanted = str(
            label if label is not None else (self.kind.get() if self.kind else "")
        )
        for entry in self.filetypes:
            if str(entry[0]) == wanted:
                spec = entry[1] if len(entry) > 1 else "*"
                self.set_filter(self.directory, pattern_text(spec))
                self.refresh()
                return

    # ------------------------------------------------------------- reading

    def get_filter(self) -> tuple[str, str]:
        """The directory and pattern the filter box is asking for."""
        text = os.path.expanduser(self.filter.get())
        if text[-1:] == os.sep or os.path.isdir(text):
            text = os.path.join(text, "*")
        return os.path.split(text)

    def get_selection(self) -> str:
        """The path in the selection box, with ``~`` expanded."""
        return os.path.expanduser(self.selection.get())

    # ------------------------------------------------------------- writing

    def set_filter(self, directory: str, pattern: str) -> None:
        """Put a directory and pattern in the filter box, made absolute."""
        if not os.path.isabs(directory):
            try:
                working = os.getcwd()
            except OSError:
                working = ""
            if working:
                directory = os.path.normpath(os.path.join(working, directory))
        self.filter.delete(0, "end")
        self.filter.insert("end", os.path.join(directory or os.curdir, pattern or "*"))

    def set_selection(self, name: str) -> None:
        """Put one name in the selection box, under the current directory."""
        self.selection.delete(0, "end")
        self.selection.insert("end", os.path.join(self.directory, name))

    # ------------------------------------------------------------ browsing

    def refresh(self) -> bool:
        """List the filtered directory. False if it could not be read.

        A directory that cannot be read leaves everything as it was. Emptying
        the lists would lose the place somebody had got to, for a mistake
        that is usually one keystroke.
        """
        directory, pattern = self.get_filter()
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return False
        self.directory = directory
        self.set_filter(directory, pattern)

        # `..` always first, so there is a way up even out of a directory
        # whose name nobody can spell.
        subdirs = [os.pardir]
        files = []
        for name in names:
            if os.path.isdir(os.path.join(directory, name)):
                subdirs.append(name)
            elif matches(name, pattern):
                files.append(name)

        self.dirs.delete(0, "end")
        self.dirs.insert("end", *subdirs)
        self.files.delete(0, "end")
        self.files.insert("end", *files)

        _, tail = os.path.split(self.get_selection())
        self.set_selection("" if tail == os.curdir else tail)
        return True

    def enter_directory(self, name: str) -> None:
        """Move the filter into one of the listed subdirectories."""
        _, pattern = self.get_filter()
        self.set_filter(os.path.normpath(os.path.join(self.directory, name)), pattern)


class FileDialog:
    """The browser as a dialog, with no opinion about what was chosen.

    Usage is tkinter's::

        chosen = FileDialog(master).go(directory, pattern, default, key)

    ``key`` names an entry in :data:`dialogstates`, which remembers the
    directory and pattern between calls - and remembers them even when the
    dialog was cancelled.
    """

    title = "File Selection Dialog"

    def __init__(self, master: Misc, title: str | None = None) -> None:
        """
        Args:
            master: The window the dialog belongs to.
            title: Shown on the dialog's top edge.
        """
        self.master = master
        self.how: str | None = None

        self.top = tkcurses.Toplevel(master)
        self.top.title(title if title is not None else self.title)

        self.browser = _Browser(self.top)
        self.browser.selection.bind("<Return>", self.ok_event)
        self.browser.filter.bind("<Return>", self.filter_command)
        self.browser.files.bind("<ButtonRelease-1>", self.files_select_event)
        self.browser.files.bind("<Double-Button-1>", self.files_double_event)
        self.browser.dirs.bind("<ButtonRelease-1>", self.dirs_select_event)
        self.browser.dirs.bind("<Double-Button-1>", self.dirs_double_event)

        buttons = tkcurses.Frame(self.top)
        buttons.pack(side="bottom", fill="x")
        tkcurses.Button(buttons, text="OK", command=self.ok_command).pack(side="left")
        tkcurses.Button(buttons, text="Filter", command=self.filter_command).pack(
            side="left", expand=True
        )
        tkcurses.Button(buttons, text="Cancel", command=self.cancel_command).pack(
            side="right"
        )

        self.top.protocol("WM_DELETE_WINDOW", self.cancel_command)
        self.top.bind("<Escape>", self.cancel_command)

    # --------------------------------------------------------------- using

    def go(
        self,
        dir_or_file: str = os.curdir,
        pattern: str = "*",
        default: str = "",
        key: str | None = None,
    ) -> str | None:
        """Show the dialog and wait. The chosen path, or None if cancelled."""
        if key and key in dialogstates:
            self.browser.directory, pattern = dialogstates[key]
        else:
            dir_or_file = os.path.expanduser(dir_or_file)
            if os.path.isdir(dir_or_file):
                self.browser.directory = dir_or_file
            else:
                self.browser.directory, default = os.path.split(dir_or_file)
        self.browser.set_filter(self.browser.directory, pattern)
        self.browser.set_selection(default)
        self.filter_command()
        fit(self.top)
        # Before the focus moves - see the note in simpledialog.Dialog.
        self._displaced = take_focus_grab(self.top)
        self.browser.selection.focus_set()
        self.how = None
        self.top.wait_window(self.top)
        # Re-widened on purpose: the answer arrives during the wait, from
        # quit(), and a checker that has just seen `self.how = None` two
        # lines up would otherwise call everything below it unreachable.
        chosen: str | None = self.how
        if key:
            directory, pattern = self.browser.get_filter()
            if chosen:
                directory = os.path.dirname(chosen)
            dialogstates[key] = directory, pattern
        return chosen

    def quit(self, how: str | None = None) -> None:
        """Answer with ``how`` and take the dialog down."""
        self.how = how
        if self.top.winfo_exists():
            restore_focus_grab(self.top, getattr(self, "_displaced", (None, None)))
            self.top.destroy()

    # ------------------------------------------------------------- events

    def dirs_double_event(self, event: Event) -> None:  # noqa: ARG002
        self.filter_command()

    def dirs_select_event(self, event: Event) -> None:  # noqa: ARG002
        self.browser.enter_directory(str(self.browser.dirs.get("active")))

    def files_double_event(self, event: Event) -> None:  # noqa: ARG002
        self.ok_command()

    def files_select_event(self, event: Event) -> None:  # noqa: ARG002
        self.browser.set_selection(str(self.browser.files.get("active")))

    def ok_event(self, event: Event) -> None:  # noqa: ARG002
        self.ok_command()

    def cancel_command(self, event: Event | None = None) -> None:  # noqa: ARG002
        self.quit()

    def filter_command(self, event: Event | None = None) -> None:  # noqa: ARG002
        """Re-list the directory the filter names, complaining if it cannot."""
        if not self.browser.refresh():
            self.master.bell()

    def ok_command(self) -> None:
        """Answer with whatever is in the selection box. Checked by subclasses."""
        self.quit(self.browser.get_selection())

    # ------------------------------ the browser's own methods, as tkinter has
    # them on the dialog rather than on anything else

    def get_filter(self) -> tuple[str, str]:
        return self.browser.get_filter()

    def get_selection(self) -> str:
        return self.browser.get_selection()

    def set_filter(self, dir: str, pat: str) -> None:
        self.browser.set_filter(dir, pat)

    def set_selection(self, file: str) -> None:
        self.browser.set_selection(file)


class LoadFileDialog(FileDialog):
    """A file dialog that insists the file is there."""

    title = "Load File Selection Dialog"

    def ok_command(self) -> None:
        chosen = self.get_selection()
        if not os.path.isfile(chosen):
            self.master.bell()
        else:
            self.quit(chosen)


class SaveFileDialog(FileDialog):
    """A file dialog that insists the file could be written.

    Which means three different refusals: a directory is not a file, a file
    in a directory that does not exist cannot be created, and an existing
    file needs asking about first.
    """

    title = "Save File Selection Dialog"

    def ok_command(self) -> None:
        chosen = self.get_selection()
        if os.path.exists(chosen):
            if os.path.isdir(chosen):
                self.master.bell()
                return
            answer = _ButtonDialog(
                self.top,
                {
                    "title": "Overwrite Existing File Question",
                    "text": f"Overwrite existing file {chosen!r}?",
                    "bitmap": "questhead",
                    "default": 1,
                    "strings": ("Yes", "Cancel"),
                },
            )
            if answer.num != 0:
                return
        else:
            head, _ = os.path.split(chosen)
            if not os.path.isdir(head):
                self.master.bell()
                return
        self.quit(chosen)


# ----------------------------------------------------------------------
# The three that stand in for the platform's own choosers
# ----------------------------------------------------------------------


class _NativeDialog(_CommonDialog):
    """A chooser with the shape of tk_getOpenFile, drawn from our widgets."""

    #: Which of the three checks ``ok`` applies: "open", "save" or "directory".
    kind: ClassVar[str] = "open"

    def _fixoptions(self) -> None:
        with contextlib.suppress(KeyError):
            self.options["filetypes"] = tuple(self.options["filetypes"])

    def _fixresult(self, widget: Misc, result: Any) -> Any:  # noqa: ARG002
        if result:
            path, name = os.path.split(result)
            self.options["initialdir"] = path
            self.options["initialfile"] = name
        self.filename = result
        return result

    def body(self, window: Toplevel) -> Misc | None:
        self.browser = _Browser(window, self.options.get("filetypes") or ())
        directory = str(self.options.get("initialdir") or os.curdir)
        pattern = _first_pattern(self.options.get("filetypes"))
        self.browser.set_filter(directory, pattern)
        self.browser.set_selection(str(self.options.get("initialfile") or ""))
        self.browser.refresh()

        def on_return(event: Event) -> None:  # noqa: ARG001
            self.ok()

        def on_filter(event: Event) -> None:  # noqa: ARG001
            self.browser.refresh()

        def on_file(event: Event) -> None:  # noqa: ARG001
            self.browser.set_selection(str(self.browser.files.get("active")))

        def on_dir(event: Event) -> None:  # noqa: ARG001
            self.dir_clicked(str(self.browser.dirs.get("active")))

        self.browser.selection.bind("<Return>", on_return)
        self.browser.filter.bind("<Return>", on_filter)
        self.browser.files.bind("<ButtonRelease-1>", on_file)
        self.browser.files.bind("<Double-Button-1>", on_return)
        self.browser.dirs.bind("<ButtonRelease-1>", on_dir)
        self.browser.dirs.bind("<Double-Button-1>", on_filter)

        buttons = tkcurses.Frame(window)
        buttons.pack(side="bottom", fill="x")
        tkcurses.Button(buttons, text="OK", command=self.ok).pack(side="left")
        tkcurses.Button(buttons, text="Filter", command=self.browser.refresh).pack(
            side="left", expand=True
        )
        tkcurses.Button(buttons, text="Cancel", command=lambda: self.finish(None)).pack(
            side="right"
        )
        return self.browser.selection

    def dir_clicked(self, name: str) -> None:
        """What one click on a directory does. Moving there, for a file."""
        self.browser.enter_directory(name)

    def ok(self) -> None:
        """Answer, if what has been chosen passes this dialog's own check."""
        chosen = self.browser.get_selection()
        if self.kind == "directory":
            if self.options.get("mustexist") and not os.path.isdir(chosen):
                return
        elif self.kind == "open":
            if not os.path.isfile(chosen):
                return
        else:
            head, _ = os.path.split(chosen)
            if not os.path.isdir(head):
                return
            chosen = _with_extension(chosen, self.options.get("defaultextension"))
        self.finish(chosen)


def patterns_of(spec: Any) -> tuple[str, ...]:
    """Every glob one filetype's pattern field asks for.

    Tk writes these several ways and means the same thing by all of them:
    ``"*.png *.gif"``, ``("*.png", "*.gif")``, and the man page's own
    ``{.txt .text}`` - bare extensions, no star. All three are accepted, and
    a bare extension grows the ``*`` it needs, because a caller who wrote
    ``.png`` plainly did not mean a file called exactly ".png".
    """
    if not spec:
        return ("*",)
    items: list[str] = []
    if isinstance(spec, str):
        items = spec.split()
    else:
        for item in spec:
            items.extend(str(item).split())
    globs = []
    for item in items:
        if item.startswith("."):
            globs.append(f"*{item}")
        elif item:
            globs.append(item)
    return tuple(globs) or ("*",)


def pattern_text(spec: Any) -> str:
    """One filetype's globs as the single string the filter box holds."""
    return " ".join(patterns_of(spec))


def matches(name: str, pattern: str) -> bool:
    """Whether ``name`` matches any of the globs in ``pattern``.

    The filter box holds one string, and that string may name several globs
    - which is the whole point: ``filetypes=[("Images", "*.png *.gif")]``
    used to match nothing at all, because fnmatch was handed the lot as a
    single pattern and no file is called "something *.png *.gif".
    """
    return any(fnmatch.fnmatch(name, glob) for glob in pattern.split() or ["*"])


def _first_pattern(filetypes: Any) -> str:
    """The pattern to start with, from ``filetypes`` if there is one."""
    if not filetypes:
        return "*"
    first = next(iter(filetypes))
    if isinstance(first, (list, tuple)) and len(first) > 1:
        return pattern_text(first[1])
    return "*"


def _with_extension(path: str, extension: Any) -> str:
    """Add ``defaultextension`` to a name that has none, as Tk does."""
    if not extension:
        return path
    root, found = os.path.splitext(path)
    if found:
        return path
    return root + str(extension)


class Open(_NativeDialog):
    """Ask for a file to open."""

    command: ClassVar[str | None] = "tk_getOpenFile"
    kind: ClassVar[str] = "open"

    def _fixresult(self, widget: Misc, result: Any) -> Any:
        if isinstance(result, tuple):
            if result:
                path, _ = os.path.split(result[0])
                self.options["initialdir"] = path
            return result
        return super()._fixresult(widget, result)


class SaveAs(_NativeDialog):
    """Ask for a file to save as."""

    command: ClassVar[str | None] = "tk_getSaveFile"
    kind: ClassVar[str] = "save"


class Directory(_NativeDialog):
    """Ask for a directory."""

    command: ClassVar[str | None] = "tk_chooseDirectory"
    kind: ClassVar[str] = "directory"

    def dir_clicked(self, name: str) -> None:
        """Choose it, rather than move into it.

        A directory chooser is asking *which directory*, so the one clicked
        belongs in the selection box - moving there instead would answer
        with whatever was being looked at, which is not what was pointed at.
        Double-click still descends, through the Filter binding.
        """
        if name == os.pardir:
            self.browser.enter_directory(name)
            self.browser.refresh()
            return
        self.browser.set_selection(name)

    def _fixresult(self, widget: Misc, result: Any) -> Any:  # noqa: ARG002
        if result:
            self.options["initialdir"] = result
        self.directory = result
        return result


# ----------------------------------------------------------------------
# convenience
# ----------------------------------------------------------------------


def askopenfilename(**options: Any) -> str:
    """Ask for a file to open. The path, or "" if cancelled."""
    return str(Open(**options).show() or "")


def asksaveasfilename(**options: Any) -> str:
    """Ask for a file to save as. The path, or "" if cancelled."""
    return str(SaveAs(**options).show() or "")


def askopenfilenames(**options: Any) -> tuple[str, ...]:
    """Ask for several files to open. Empty if cancelled."""
    options["multiple"] = 1
    chosen = Open(**options).show()
    if not chosen:
        return ()
    if isinstance(chosen, tuple):
        return tuple(str(name) for name in chosen)
    return (str(chosen),)


def askopenfile(mode: str = "r", **options: Any) -> IO[Any] | None:
    """Ask for a file to open, and open it. None if cancelled."""
    name = askopenfilename(**options)
    return open(name, mode) if name else None


def askopenfiles(mode: str = "r", **options: Any) -> list[IO[Any]]:
    """Ask for several files to open, and open them all."""
    return [open(name, mode) for name in askopenfilenames(**options)]


def asksaveasfile(mode: str = "w", **options: Any) -> IO[Any] | None:
    """Ask for a file to save as, and open it. None if cancelled."""
    name = asksaveasfilename(**options)
    return open(name, mode) if name else None


def askdirectory(**options: Any) -> str:
    """Ask for a directory. The path, or "" if cancelled."""
    return str(Directory(**options).show() or "")
