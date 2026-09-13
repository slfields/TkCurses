"""Acceptance scenarios: what a person has to look at to judge.

The pytest suite asserts on an emulated terminal, which settles whether the
right characters reach the right cells. It cannot tell you that a window looks
wrong, that a resize leaves the display confused, or that Ctrl-C hands back a
terminal you can still type in. These scenarios are for those questions.

From the repository root, ``python3 -m uat`` lists them and
``python3 -m uat <number>`` runs one. From anywhere else, give the path:
``python3 /path/to/TkCurses/uat``. uat/ is a development tool rather than
part of the installed package, which is why the root has to be findable.

docs/UAT_BASE_WIDGETS.md says what each scenario is asking you to look at.
"""

from __future__ import annotations
