# Widget integration tests

A test belongs here only if it **needs more than one widget to be able to
fail**. Everything else is a unit test in the wrong folder.

That rule is not tidiness. Before this suite existed there were 103 test
files, every one of them a single widget on a bare root, and every
cross-widget fault this project has had was found by a person looking at a
screen: `TkCurses-bk8` by dragging a window, `TkCurses-2dz` by noticing a
dialog panel came out one row tall. None of them could have failed a test
that builds one widget and nothing else.

## What is here

| Module | The claim it tests |
|--------|--------------------|
| `conftest.py` | The fixtures: an application, not a bare widget |
| `test_stacking.py` | The widget that draws a cell is the widget that receives a click on it |
| `test_geometry_nesting.py` | A container asks for what its children need *plus* what it spends on itself |
| `test_event_routing.py` | An event reaches a list of tags, in order, until one says `"break"` |
| `test_shared_variables.py` | Changing a variable changes every widget bound to it, and the reverse |
| `test_scrollbar_pairs.py` | What the scrollbar was last told is what the widget reports |
| `test_focus_traversal.py` | Tab order is the tree's, and eligibility is `takefocus` then state |
| `test_dialog_over_app.py` | A dialog is in front of, and in the way of, what is underneath |
| `test_dialog_over_app_tty.py` | The same, with real dialogs on a real screen |
| `test_resize_full_screen_tty.py` | Everything above, and then the terminal changes size |
| `test_teardown.py` | Nothing can still reach a destroyed widget; nothing it reached is damaged |

## Writing one

**Mirror the implementation, do not call it.** `widget_at` and `through_grab`
in `conftest.py` re-state the rules that `Tk._widget_at` and
`Tk._through_grab` implement. When routing and the panel stack disagree,
*that* is the bug, and a test that called the implementation could not see it.

**Break it and watch it fail.** Every module in this suite was checked by
reintroducing the fault it claims to catch. That step found more problems in
the tests than in the code:

- A containment assertion in `test_geometry_nesting.py` passed against the
  `2dz` bug. Every frame collapsed to the leaf's size, too short to draw a
  border, so nothing was clipped and containment held trivially.
- The list of widget classes in `test_event_routing.py` was hand-written and
  had no Checkbutton and no Radiobutton, so `_ChoiceWidget` could be broken
  with the suite green. It is enumerated now.
- A test in `test_focus_traversal.py` was marked `xfail` and reported
  `xpassing`: while `s6g` stands, disabling never removes the widget, so
  disabling and re-enabling cannot change anything either way.

**Never wait on idle after a resize.** `wait_for_idle` returns when the
terminal goes quiet, and it is quiet in the gap between the resize arriving
and the application reacting. Wait for the application to say the new size
out loud. See the docstring in `test_resize_full_screen_tty.py`.

**A known bug gets an `xfail` naming its issue**, and a control beside it
asserting the case that does work - so a fault that breaks everything cannot
hide behind the known one.
