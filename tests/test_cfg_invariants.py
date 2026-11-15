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

"""Acceptance for the configuration library under ``tkcurses-cfg``.

The library has no screen, so it is accepted by invariants rather than by a
person. Five, and where each is held:

1. The strict check and a program agree about every value -
   ``test_core_config.py::test_the_loader_and_the_parser_agree_about_every_value``.
2. Where a value came from is where it did come from - here.
3. An unedited file comes back byte for byte, and an edit touches only its
   own line, read the same by a program as by the editor -
   ``test_cfg_inifile.py``, the three property tests at the top.
4. A save that fails before the swap leaves the directory byte-identical -
   ``test_cfg_store.py::test_a_failure_before_the_swap_changes_nothing`` and
   ``test_a_signal_mid_save_backs_out``.
5. Saves from several processes at once all land, and a reader never sees
   a part-written file - ``test_cfg_store.py``, by those names.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tkcurses._core.config import (
    SETTINGS,
    InvalidValue,
    OutOfRange,
    TkCursesConfig,
)

#: Text for one source: valid values, out-of-range ones, rubbish.
RAW = st.one_of(
    st.sampled_from(["true", "off", "auto", "256", "osc52", "maybe", "", "50%"]),
    st.integers(-50, 1500).map(str),
)


def expected(setting, offers):
    """The value and winning location by the rules, worked out from
    ``parse`` alone: the last source whose text parses wins - clamped if
    out of range - and the default if none does."""
    value, where = setting.default, "built-in"
    for location, raw in offers:
        try:
            value, where = setting.parse(raw), location
        except OutOfRange as exc:
            value, where = exc.clamped, location
        except InvalidValue:
            pass
    return value, where


@settings(max_examples=300)
@given(
    setting=st.sampled_from(SETTINGS),
    system=st.none() | RAW,
    user=st.none() | RAW,
    env=st.none() | RAW,
)
def test_the_source_shown_is_the_source_used(setting, system, user, env):
    with tempfile.TemporaryDirectory() as directory:
        paths = (Path(directory) / "system.ini", Path(directory) / "user.ini")
        offers = []
        for path, raw in zip(paths, (system, user), strict=True):
            if raw is not None:
                path.write_text(f"[{setting.section}]\n{setting.key} = {raw}\n")
                offers.append((str(path), raw))
        environment = {}
        if env is not None:
            environment[setting.variable] = env
            offers.append((f"${setting.variable}", env))
        config = TkCursesConfig.load(paths=paths, env=environment)

    value, where = expected(setting, [(loc, raw.strip()) for loc, raw in offers])
    source = config.source(setting.name)
    assert config._get(setting) == value
    assert (source.value, source.location) == (value, where)
    # Every source that offered anything is in the chain, in order.
    chain = config.origins[setting.name]
    assert [o.location for o in chain] == ["built-in"] + [loc for loc, _ in offers]
