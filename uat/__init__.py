"""Acceptance scenarios: what a person has to look at to judge.

The pytest suite asserts on an emulated terminal, which settles whether the
right characters reach the right cells. It cannot tell you that a window looks
wrong, that a resize leaves the display confused, or that Ctrl-C hands back a
terminal you can still type in. These scenarios are for those questions.

Run ``python -m uat`` for the list, ``python -m uat <number>`` for one, and
read docs/UAT_BASE_WIDGETS.md for what each is asking you to look at.
"""

from __future__ import annotations
