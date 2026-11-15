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

"""The interactive screen's model: edits, the preview, the blocking rule
and saving, without a terminal."""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tkcurses._cfg import store
from tkcurses._cfg.errors import BlockedByProblems, InvalidSettingValue, UnknownSetting
from tkcurses._cfg.session import Change, Session
from tkcurses._core.config import BY_NAME, SETTINGS, TkCursesConfig


@pytest.fixture
def paths(tmp_path):
    system = tmp_path / "etc" / "tkcurses.ini"
    user = tmp_path / "home" / "tkcurses" / "tkcurses.ini"
    system.parent.mkdir()
    return system, user


def value(s: Session, name: str) -> object:
    """What a program would use for ``name``, as the screen previews it."""
    return s.config._get(BY_NAME[name])


def session(paths, env=None, **files) -> Session:
    system, user = paths
    for name, text in files.items():
        target = system if name == "system" else user
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return Session(system, user, env=env or {})


# ------------------------------------------------------------------ edits


def test_an_edit_waits_until_saved_and_shows_what_a_program_would_use(paths):
    s = session(paths)
    s.set("input.escape_delay", "50")
    assert not paths[1].exists()
    assert s.file_value("input.escape_delay") == "50"
    assert value(s, "input.escape_delay") == 50
    assert s.winner(BY_NAME["input.escape_delay"]).location == str(paths[1])
    assert s.changes() == [Change("user", "input.escape_delay", None, "50")]


def test_a_value_is_stored_as_the_file_writes_it(paths):
    s = session(paths)
    s.set("mouse.enabled", " Off ")
    s.set("display.color_mode", "TrueColor")
    assert s.pending["user"] == {
        "mouse.enabled": "false",
        "display.color_mode": "truecolor",
    }


def test_setting_what_the_file_already_holds_is_no_change(paths):
    s = session(paths, user="[mouse]\nenabled = no\n")
    s.set("mouse.enabled", "on")
    s.set("mouse.enabled", "false")
    assert s.changes() == []


@pytest.mark.parametrize(
    ("name", "raw", "error"),
    [
        ("input.escape_delay", "soon", InvalidSettingValue),
        ("input.escape_delay", "1001", InvalidSettingValue),
        ("display.color_mode", "12", InvalidSettingValue),
        ("input.escape_dely", "5", UnknownSetting),
    ],
)
def test_a_value_the_setting_does_not_take_is_refused_at_once(paths, name, raw, error):
    s = session(paths)
    with pytest.raises(error):
        s.set(name, raw)
    assert s.changes() == []


def test_a_value_is_refused_with_what_the_setting_takes(paths):
    with pytest.raises(InvalidSettingValue, match="whole number of milliseconds"):
        session(paths).set("input.escape_delay", "-5")


def test_a_switch_starts_from_the_file_then_from_what_it_inherits(paths):
    s = session(paths, system="[mouse]\nenabled = false\n")
    s.toggle("mouse.enabled")  # the user file has none: from the system file's false
    assert s.file_value("mouse.enabled") == "true"
    s.save("user")
    s.toggle("mouse.enabled")  # now from the file's own true
    assert s.changes() == [Change("user", "mouse.enabled", "true", "false")]


def test_the_system_file_inherits_only_the_default(paths):
    s = session(
        paths, system="[mouse]\nenabled = false\n", user="[mouse]\nenabled = no\n"
    )
    s.scope = "system"
    setting = BY_NAME["mouse.enabled"]
    assert s.inherited(setting).kind == "default"
    s.scope = "user"
    assert s.inherited(setting).location == str(paths[0])


def test_taking_a_setting_out_falls_back_to_the_files_below(paths):
    s = session(
        paths,
        system="[input]\nescape_delay = 40\n",
        user="[input]\nescape_delay = 60\n",
    )
    s.unset("input.escape_delay")
    assert s.file_value("input.escape_delay") is None
    assert value(s, "input.escape_delay") == 40
    assert s.changes() == [Change("user", "input.escape_delay", "60", None)]


def test_taking_out_what_the_file_does_not_have_is_no_change(paths):
    s = session(paths)
    s.set("input.escape_delay", "50")
    s.unset("input.escape_delay")  # only undoes the pending set
    assert s.changes() == []


def test_the_environment_still_wins_and_the_edit_is_still_made(paths):
    s = session(paths, env={"TKCURSES_INPUT_ESCAPE_DELAY": "7"})
    s.set("input.escape_delay", "50")
    assert value(s, "input.escape_delay") == 7
    assert s.winner(BY_NAME["input.escape_delay"]).kind == "environment"
    assert s.file_value("input.escape_delay") == "50"


def test_each_file_keeps_its_own_edits(paths):
    s = session(paths)
    s.set("mouse.enabled", "off")
    s.scope = "system"
    s.set("input.escape_delay", "70")
    assert {c.scope for c in s.changes()} == {"user", "system"}
    assert s.file_value("mouse.enabled") is None  # not in the system file
    assert s.file_value("mouse.enabled", "user") == "false"


# --------------------------------------------------------- the blocking rule


BAD = "[input]\nescape_delay = 5000\n"


def test_a_file_with_a_bad_value_refuses_other_edits_but_shows_them(paths):
    s = session(paths, user=BAD)
    s.set("mouse.enabled", "off")
    assert "mouse.enabled" in s.refused["user"]
    assert s.file_value("mouse.enabled") == "false"  # what was asked for
    assert value(s, "mouse.enabled") is True  # not what a program would get
    before = paths[1].read_bytes()
    with pytest.raises(BlockedByProblems):
        s.save("user")
    assert paths[1].read_bytes() == before
    assert s.pending["user"] == {"mouse.enabled": "false"}


def test_edits_that_fix_the_file_are_saved_with_the_rest(paths):
    s = session(paths, user=BAD)
    s.set("mouse.enabled", "off")  # refused, for now
    s.set("input.escape_delay", "50")  # the fix, made after it
    assert s.refused["user"] == {}
    s.save("user")
    assert (
        paths[1].read_text()
        == "[input]\nescape_delay = 50\n\n[mouse]\nenabled = false\n"
    )
    assert s.changes() == []


def test_a_problem_leaves_the_list_as_soon_as_an_edit_fixes_it(paths):
    s = session(paths, user=BAD + "[debug]\nlog_level = x\n")
    assert [p.kind for p in s.problems()] == ["invalid", "removed"]
    s.unset("debug.log_level")  # refused while the bad value is there
    assert [p.kind for p in s.problems()] == ["invalid", "removed"]
    s.set("input.escape_delay", "40")
    assert [p.kind for p in s.problems()] == []  # the fix, then the other


# ------------------------------------------------------------- the preview


VALUES = {
    "bool": st.sampled_from(["true", "false", "on", "0"]),
    "choice": None,
    "int": None,
}


def _value(setting):
    if setting.kind == "bool":
        return VALUES["bool"]
    if setting.kind == "choice":
        return st.sampled_from(setting.choices)
    low, high = setting.limits
    return st.integers(low, high).map(str)


EDITS = st.lists(
    st.tuples(
        st.sampled_from(["user", "system"]),
        st.sampled_from(SETTINGS).flatmap(
            lambda s: st.one_of(st.just(None), _value(s)).map(lambda v: (s.name, v))
        ),
    ),
    max_size=8,
)
START = st.sampled_from(
    ["", "[mouse]\nenabled = no\n", "; kept\n[input]\nescape_delay = 30 ; ssh\n"]
)
ENV = st.dictionaries(
    st.sampled_from([s.variable for s in SETTINGS[:3]]),
    st.sampled_from(["1", "off", "fast", "400"]),
    max_size=2,
)


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(system_text=START, user_text=START, edits=EDITS, env=ENV)
def test_the_preview_is_what_a_program_reads_once_saved(
    tmp_path_factory, system_text, user_text, edits, env
):
    """The screen's IN EFFECT column, before saving, against the loader
    reading the saved files: the same value from the same place, always."""
    root = tmp_path_factory.mktemp("preview")
    s = session(
        (root / "etc.ini", root / "user.ini"), env, system=system_text, user=user_text
    )
    for scope, (name, raw) in edits:
        s.scope = scope
        if raw is None:
            s.unset(name)
        else:
            s.set(name, raw)
    preview = s.config
    for scope in ("system", "user"):
        if s.pending[scope]:
            s.save(scope)
    after = TkCursesConfig.load(paths=(root / "etc.ini", root / "user.ini"), env=env)
    assert preview == after
    for setting in SETTINGS:
        assert preview.source(setting.name) == after.source(setting.name)
    assert preview.warnings == after.warnings


def test_a_warning_names_the_real_file_not_the_preview_copy(paths):
    s = session(paths, user="[debug]\nlog_level = x\n")
    s.set("mouse.enabled", "off")
    assert any(str(paths[1]) in w for w in s.config.warnings)
    assert not any("tkcurses-cfg-" in w for w in s.config.warnings)


# --------------------------------------------------------------- the disk


def test_a_change_on_disk_is_noticed_and_the_edits_stay_on_top(paths):
    s = session(paths, user="[mouse]\nenabled = no\n")
    s.set("input.escape_delay", "50")
    assert s.changed_on_disk() == []
    paths[1].write_text("[mouse]\nenabled = yes\nclick_interval = 300\n")
    assert s.changed_on_disk() == ["user"]
    s.reload("user")
    assert s.changed_on_disk() == []
    assert value(s, "mouse.click_interval") == 300
    assert value(s, "input.escape_delay") == 50
    s.save("user")
    assert "click_interval = 300" in paths[1].read_text()


def test_a_file_appearing_or_going_counts_as_a_change(paths):
    s = session(paths)
    paths[0].write_text("[mouse]\nenabled = no\n")
    assert s.changed_on_disk() == ["system"]
    s.reload()
    paths[0].unlink()
    assert s.changed_on_disk() == ["system"]


def test_a_file_that_cannot_be_read_is_shown_and_not_edited(paths):
    s = session(paths, user="[display]\ncolor_mode = 8\ncolor_mode = 16\n")
    assert s.edited["user"] is None
    assert "color_mode is set again" in s.why_read_only()
    assert s.problems() == []
    assert s.file_value("display.color_mode") is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write anywhere")
def test_a_file_that_cannot_be_written_says_why(paths):
    s = session(paths)
    paths[0].parent.chmod(0o555)
    try:
        s.scope = "system"
        assert "needs root" in s.why_read_only()
        s.scope = "user"
        assert s.why_read_only() is None  # its directory is made on saving
    finally:
        paths[0].parent.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="root may write anywhere")
def test_a_failed_save_keeps_the_edits_and_the_file(paths):
    s = session(paths, user="[mouse]\nenabled = no\n")
    s.set("mouse.enabled", "yes")
    paths[1].parent.chmod(0o555)
    try:
        with pytest.raises(store.PermissionDenied):
            s.save("user")
    finally:
        paths[1].parent.chmod(0o755)
    assert s.pending["user"] == {"mouse.enabled": "true"}
    assert paths[1].read_text() == "[mouse]\nenabled = no\n"
    s.save("user")
    assert paths[1].read_text() == "[mouse]\nenabled = true\n"


def test_saving_keeps_the_files_own_words(paths):
    text = "; mine\n[mouse]\nClick_Interval: 350   ; trackpad\n"
    s = session(paths, user=text)
    s.set("mouse.click_interval", "400")
    saved = s.save("user")
    assert paths[1].read_text() == text.replace("350", "400")
    assert saved.backup is not None


def test_switching_twice_is_no_change_not_a_line_holding_the_inherited_value(paths):
    s = session(paths, system="[mouse]\nenabled = false\n")
    s.toggle("mouse.enabled")
    s.toggle("mouse.enabled")
    assert s.changes() == []
