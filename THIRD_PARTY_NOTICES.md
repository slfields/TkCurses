# Third-party notices

TkCurses is free software under the **GNU General Public License, version 3
only** — see [`LICENSE`](https://github.com/slfields/TkCurses/blob/master/LICENSE). This file records the work of others that
TkCurses builds on, what was taken from each and how, and the licence each is
under. Both licences below are permissive and compatible with the GPL.

TkCurses depends on neither at run time. It does not import tkinter and needs
no Tcl or Tk installed: it is a separate implementation of tkinter's interface
that draws with curses.

## Tcl and Tk

**How TkCurses uses them.** Tk is the specification TkCurses is measured
against. Its behaviour was measured in Tk 9.0.2, and where Tk's own
documentation is silent or imprecise the rules were **read from the Tcl and Tk
library scripts**, and for binding sequences from Tk's C source, and their
logic followed, in places ported procedure by procedure. The procedure is named in the source next to the code that follows
it. The scripts, as installed with Tcl 9.0.2 and Tk 9.0.2:

| Script | Procedures followed | In TkCurses |
|---|---|---|
| Tk `entry.tcl` | `tk::EntryButton1`, `tk::EntryMouseSelect`, `tk::EntryAutoScan`, `tk::EntryKeySelect`, `tk::EntrySetCursor`, `tk::EntryPreviousWord`, `tk::EntryNextWord`, `tk::EntrySelectNextWord`; the navigation virtual-event bindings | Entry's mouse and keyboard selection, and its keyboard motion (`__init__.py`, `_core/editing.py`) |
| Tk `text.tcl` | `tk::TextButton1`, `tk::TextSelectTo`, `tk::TextResetAnchor`, `tk::TextAutoScan`, `tk::TextPrevPos`, `tk::TextNextPos`, `tk::TextSetCursor`, `tk::TextKeySelect`, `tk::TextUpDownLine`, `tk::TextNextWord`, `tk::TextSelectNextWord`, `tk::TextPrevPara`, `tk::TextNextPara`, `tk::TextScrollPages`, `tk::TextInsert`, `tk::TextUndoRedoProcessMarks`, `tk_textPaste`; the navigation virtual-event bindings, Prior, Next and their Shift and Control forms; the Return binding's separator; the `<<Undo>>` and `<<Redo>>` bindings | Text's mouse selection, autoscroll, keyboard motion, paging and clipboard, how typing groups for undo, and the ranges undo and redo answer (`__init__.py`, `_core/textbuffer.py`) |
| Tk `tkEntry.c` | `ComputeFormat`, `SpinboxInvoke` | the classic Spinbox's number format and its step (`__init__.py`) |
| Tk `spinbox.tcl` | `tk::spinbox::MouseSelect`, `tk::spinbox::ArrowPress`, `tk::spinbox::Invoke`, `tk::spinbox::ButtonUp`; the navigation virtual-event bindings | Spinbox's selection, keyboard motion, and its arrows' step and auto-repeat (`__init__.py`) |
| Tk `ttk/entry.tcl`, `ttk/spinbox.tcl`, `ttk/combobox.tcl` | `ttk::entry::Select`, `DragTo`, `ExtendTo`, `Move`, `Extend`, `PrevWord`, `NextWord`, `SelectNextWord`, `CharSelect`, `WordSelect`, `AutoScroll`, `PendingDelete`; `ttk::spinbox::DoubleClick`, `ttk::spinbox::Spin`, `ttk::spinbox::Adjust`, `ttk::spinbox::FormatValue`; `ttk::combobox::Press`, `ttk::combobox::TraverseIn` | the ttk entries' selection, keyboard motion and paste (`__init__.py`); the combobox's clicks, and the spinbox's step and number format (`ttk.py`) |
| Tk `tk.tcl` | `tk::wordBreakBefore`, `tk::wordBreakAfter`, `tk::endOfWord`, `tk::startOfNextWord`, `tk::startOfPreviousWord`, `tk::EventMotifBindings`, `tk::SetFocusGrab`, `tk::RestoreFocusGrab`, `tk::CancelRepeat`, `tk::TabToWindow`; the clipboard, navigation and undo virtual events | word boundaries (`_core/editing.py`, `_core/words.py`), dialog grabs (`commondialog.py`), `_core/application.py`, focus traversal (`__init__.py`) |
| Tk `listbox.tcl` | `tk::ListboxBeginSelect`, `tk::ListboxBeginToggle`, `tk::ListboxBeginExtend`, `tk::ListboxMotion`, `tk::ListboxUpDown`, `tk::FireListboxSelectEvent` | Listbox's selection by mouse and keyboard, per `-selectmode` (`__init__.py`) |
| Tk `ttk/treeview.tcl` | `ttk::treeview::Press`, `ttk::treeview::heading.press`, `ttk::treeview::heading.release` | a Treeview heading's `command`, run when a click on the heading is released over it (`ttk.py`) |
| Tk `focus.tcl` | `tk::FocusOK` | focus traversal (`__init__.py`) |
| Tk `menu.tcl` | `tk::FirstMenu`, `tk::TraverseToMenu`, `tk::MenuFind`, `tk::TraverseWithinMenu`, `tk::MenuFirstEntry`, `tk::MenuUnpost`, `tk::MenuNextMenu`; the Menu class's `<KeyPress>` binding | reaching the menu bar and Menubuttons from the keyboard, and moving through an open menu (`__init__.py`) |
| Tk `scrlbar.tcl` | the Scrollbar bindings | Scrollbar's mouse behaviour (`__init__.py`) |
| Tk `panedwindow.tcl` | `tk::panedwindow::DragSash`, `tk::panedwindow::ReleaseSash` | the PanedWindow's proxy while a sash is dragged with `-opaqueresize` off (`__init__.py`) |
| Tk `button.tcl`, `scale.tcl` | `tk::ButtonInvoke`, `tk::ButtonEnter`, `tk::ButtonLeave`, `tk::CheckEnter`, `tk::ButtonDown`, `tk::ButtonUp`, `tk::ButtonAutoInvoke`; `tk::ScaleActivate`, `tk::ScaleButtonDown`, `tk::ScaleButton2Down`, `tk::ScaleDrag`, `tk::ScaleEndDrag`, `tk::ScaleIncrement` | when a button or a scale is drawn active, the reliefs they take under the pointer and while held, and auto-repeat (`__init__.py`) |
| Tk `msgbox.tcl`, `dialog.tcl`, `clrpick.tcl` | the message box's button sets, `tk_dialog`, the colour chooser's layout | `messagebox.py` (its button table is taken from `msgbox.tcl`), `dialog.py`, `colorchooser.py` |
| Tcl `word.tcl` | `tcl_wordBreakBefore`, `tcl_wordBreakAfter` | word boundaries (`_core/editing.py`) |
| Tk `unix/tkUnixButton.c` (C) | `TkpDisplayButton` | the relief an indicatorless checkbutton or radiobutton is drawn in (`__init__.py`) |
| Tk `generic/tkBind.c` (C) | `Tk_BindEvent`, `MatchPatterns`, the promotion lists, `IsBetterMatch`, `CountSpecialized` | multi-event binding sequences and how matches are ranked (`_core/bindings.py`) |
| Tk `generic/tkText.c` (C) | `DeleteIndexRange`, `TextPushUndoAction`, the autoseparator test in `TextInsertCmd` and `TextDeleteCmd`; `TextReplaceCmd` and the `replace` subcommand's insertion-cursor rule | where a Text's view goes when text is deleted, a deletion to the end taking whole lines, where undo and redo put the cursor, when an edit starts a new undo group, and how `replace` groups its edits and keeps the cursor (`_core/textbuffer.py`, `__init__.py`) |
| Tk `generic/tkTextTag.c` (C) | `TkTextBindProc`, `TkTextPickCurrent`, `TagBindEvent` | which tags a Text's tag bindings reach, when the character under the pointer is picked, and the `<Enter>` and `<Leave>` a tag hears (`__init__.py`) |
| Tk `generic/tkTextDisp.c` (C) | `TkTextScanCmd` | a Text's `scan_dragto` (`__init__.py`) |
| Tk `generic/tkCanvas.c` (C) | the `find closest` search; the `scan` subcommand | a Canvas's `find_closest` with `halo` and `start`, and its `scan_dragto` (`__init__.py`) |
| Tk `generic/tkCanvWind.c` (C) | `DisplayWinItem` | when a Canvas's embedded window is unmapped (`__init__.py`) |
| Tk `generic/tkCmds.c` (C) | `ScalingCmd` | what `tk scaling` reads back once it has been set (`_core/application.py`) |
| Tk `generic/tkImgPhoto.c` (C) | the `-grayscale` and `-background` conversion in `ImgGetPhoto` | a PhotoImage's `data` and `write` in grey or over a background (`_core/images.py`) |
| Tk `generic/tkGrid.c` (C) | `ResolveConstraints`, `AdjustOffsets`, and `ArrangeGrid`'s use of them with `TkComputeAnchor` | how big each grid row and column is, and where the grid sits (`_core/grid.py`) |
| Tk `generic/tkPanedWindow.c` (C) | `ArrangePanes`, `MoveSash`, `ComputeGeometry` and `IsStretchable` | a classic PanedWindow's pane sizes, `stretch`, and how a sash moves (`_core/paned.py`) |
| Tk `generic/tkUndo.c` (C) | `TkUndoRevert`, `TkUndoApply` | the separators an undo or a redo leaves behind (`_core/textbuffer.py`) |
| Tk `xlib/rgb.txt`, `xlib/xcolors.c` (C) | the colour name table; `colorcmp` | the colour names Tk knows, and where a space may go in one (`_core/x11colors.py`) |

The project documentation (`ARCHITECTURE.md`, `docs/`) also quotes Tk's
manual pages and these scripts where it records a measurement. Tk's licence
covers its documentation as well as its software.

Where TkCurses **deliberately differs** from Tk, that is recorded in
`ARCHITECTURE.md` beside the widget concerned.

### Tk licence

As distributed with Tk 9.0.2 (`license.terms`):

```text
This software is copyrighted by the Regents of the University of
California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
Corporation, Apple Inc. and other parties.  The following terms apply to
all files associated with the software unless explicitly disclaimed in
individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7013 (b) (3) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

### Tcl licence

As distributed with Tcl 9.0.2 (`license.terms`):

```text
This software is copyrighted by the Regents of the University of
California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
Corporation and other parties.  The following terms apply to all files
associated with the software unless explicitly disclaimed in
individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7014 (b) (3) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

## Python and tkinter

**How TkCurses uses them.** TkCurses reimplements the public interface of
CPython's `tkinter` package — its module layout, class, function, method,
option and constant names, and the values of those constants — so that
programs written for tkinter run against it. That interface is reimplemented,
not copied: none of tkinter's documentation strings are reproduced (checked
mechanically against CPython 3.14's `Lib/tkinter`).

**Two modules contain code adapted from tkinter**, found by comparing every
module with its tkinter counterpart:

- `src/tkcurses/dnd.py`, from `Lib/tkinter/dnd.py` — the drag handler's
  target switching (`on_motion`) and teardown (`finish`).
- `src/tkcurses/simpledialog.py`, from `Lib/tkinter/simpledialog.py` —
  `Dialog.ok`, and `_QueryDialog`'s constructor and `validate`, including its
  warning messages, which programs may depend on.

Both carry a notice in their header. As the PSF licence asks, **a brief
summary of the changes**: both were given type annotations and new
documentation strings. In `dnd.py` the drag in progress is kept on the
application rather than on a private attribute of the root window, a
widget's `dnd_accept` is looked up with `getattr` rather than by catching
`AttributeError`, and there is no mouse cursor to save and restore. In
`simpledialog.py` `validate` answers `True` and `False` rather than `1` and
`0` and builds its messages with f-strings, keeping their wording. The
widgets both modules work with are TkCurses's own, drawn with curses.

### Python Software Foundation Licence

As distributed with CPython 3.14 (`LICENSE.txt`):

```text
PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001 Python Software Foundation; All Rights Reserved"
are retained in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.
```

## chafa

[chafa](https://hpjansson.org/chafa/) (LGPL-3.0-or-later, © Hans Petter
Jansson) was **read as a reference** for the image and colour path. No code
was taken from it. The published algorithms TkCurses uses — the sRGB transfer
function (IEC 61966-2-1), DIN99d, median cut, Floyd–Steinberg — were
implemented from their own published descriptions and are credited in the
source next to the code. See "Attribution for borrowed algorithms" in
`CLAUDE.md`.
