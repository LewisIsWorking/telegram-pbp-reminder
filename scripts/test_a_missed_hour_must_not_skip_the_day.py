"""A scheduled feature may not depend on a run landing in one exact hour.

⛔⛔ 2026-09-06. ``last_diagnostic`` and ``last_pin_digest`` both read
**2026-08-27**. Ten days. Both were gated::

    if now.hour != config.get("diagnostic_hour", 8):
        return

which is only "daily at 08:00" if a run happens during hour 08. The bot
asks GitHub for 48 scheduled runs a day and gets about 27% of them, so
its runs land in **4 to 13 distinct hours out of 24**. Measured over the
13 days to 2026-09-06: a run landed in hour 08 on **3 days**, with an
unbroken stretch of **8 days with none**.

Nothing noticed. The features were green, covered, and never happened.

``queue_reminder`` had the same bug in list form (``now.hour in
daily_hours``) and the state file counted the cost: **10 of 28 daily
slots unposted** in a fortnight, both slots gone on three separate days.
Two configured hours instead of one meant it half-worked, which is
exactly why it read as healthy.

The rest of the codebase already had this right - ``potw_schedule``,
``session_poll``, ``week_welcome``, ``swimming_poll`` and
``poll_result`` all use ``hour >= post_hour``. These tests stop the
equality form coming back.
"""

import ast
import pathlib

import pytest

from scheduled.due import is_done_today, is_due, latest_due_slot
from test_the_debug_topic_gets_the_whole_story import NOW  # noqa: F401

_SCHEDULED = pathlib.Path(__file__).resolve().parent / "scheduled"

# ⚠️ Eq/NotEq are the bug. `In` counts too: that is the same bug spread
# over a few hours, and it is how queue_reminder hid for a fortnight.
# GtE and Lt are the CORRECT forms and must not be flagged.
_BANNED_OPS = (ast.Eq, ast.NotEq, ast.In)


def _is_wall_clock_hour(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "hour"
            and isinstance(node.value, ast.Name) and node.value.id == "now")


def _offenders_in(source: str, name: str = "<src>") -> list:
    """⭐ AST, not regex. The first version matched text and flagged
    ``due.py``'s own docstring, which quotes the bad pattern as the
    example of what not to write. Exempting that file would have put a
    hole in the guard exactly where the subject matter lives; parsing
    means prose can never trigger it and code can never hide in prose."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare):
            continue
        if not _is_wall_clock_hour(node.left):
            continue
        if any(isinstance(op, _BANNED_OPS) for op in node.ops):
            out.append(f"{name}:{node.lineno}")
    return out


def _offenders():
    out = []
    for path in sorted(_SCHEDULED.rglob("*.py")):
        out += _offenders_in(path.read_text(encoding="utf-8"), path.name)
    return out


class TestNoFeatureHangsOnOneExactHour:
    def test_the_scan_actually_reads_the_modules(self):
        """⛔ A scan matching nothing passes for ever. Prove it reads."""
        files = list(_SCHEDULED.rglob("*.py"))
        assert len(files) > 20, f"only found {len(files)} modules to scan"
        assert any("now.hour" in p.read_text(encoding="utf-8")
                   for p in files), "no module mentions now.hour at all"

    def test_no_module_gates_on_an_exact_hour(self):
        assert _offenders() == [], (
            "these gate a scheduled feature on the wall clock matching one "
            "exact hour:\n  " + "\n  ".join(_offenders()) +
            "\nWith ~27% cron delivery that is a coin toss, not a schedule. "
            "Use scheduled.due.is_due (hour >=, once per day by marker).")

    def test_the_guard_would_catch_the_real_bug(self):
        """⭐ Fed the exact lines that were live for ten days."""
        assert _offenders_in("if now.hour != config.get('d', 8):\n    pass")
        assert _offenders_in("if now.hour in daily_hours:\n    pass")
        assert _offenders_in("if now.hour == 8:\n    pass")

    def test_the_guard_allows_the_correct_forms(self):
        """⭐ Can-fail counterpart: it must not ban the shape we want, or
        the fix could not be committed and the guard would be deleted."""
        assert not _offenders_in("if now.weekday() == 6 and now.hour >= h:\n    pass")
        assert not _offenders_in("if now.hour < post_hour:\n    pass")

    def test_prose_quoting_the_bug_is_not_an_offence(self):
        """⛔ due.py documents the banned pattern verbatim. A text-matching
        guard flagged its docstring, and the tempting fix - exempting that
        file - would have blinded the guard where the subject lives."""
        assert not _offenders_in('"""Bad: if now.hour != h. Also now.hour in hrs."""')


class TestIsDue:
    def test_it_fires_late_rather_than_not_at_all(self):
        """⭐⭐ THE FIX. 14:00 is not 08:00, and the job is still due."""
        assert is_due(NOW.replace(hour=14), 8, "2026-08-27") is True

    def test_it_does_not_fire_early(self):
        assert is_due(NOW.replace(hour=3), 8, "2026-08-27") is False

    def test_it_fires_once_a_day_only(self):
        """The date marker, not the hour, is what prevents repeats."""
        today = NOW.date().isoformat()
        assert is_due(NOW.replace(hour=14), 8, today) is False

    def test_it_fires_on_the_hour_itself(self):
        assert is_due(NOW.replace(hour=8), 8, "2026-08-27") is True

    @pytest.mark.parametrize("marker", [None, "", "not-a-date", 20260827])
    def test_an_unreadable_marker_reads_as_NOT_done(self, marker):
        """⚠️ Deliberate direction. A job running twice is a duplicate
        message someone notices; a job never running is a feature that
        silently does not exist, which is what took ten days to spot."""
        assert is_done_today(NOW, marker) is False
        assert is_due(NOW.replace(hour=14), 8, marker) is True


class TestLatestDueSlot:
    def test_a_missed_morning_slot_is_caught_up_later(self):
        assert latest_due_slot(NOW.replace(hour=14), [9, 21], []) == "2026-09-04:09"

    def test_a_posted_slot_is_not_repeated(self):
        assert latest_due_slot(NOW.replace(hour=14), [9, 21],
                               ["2026-09-04:09"]) is None

    def test_before_the_first_slot_nothing_is_due(self):
        assert latest_due_slot(NOW.replace(hour=3), [9, 21], []) is None

    def test_only_the_LATEST_missed_slot_is_filled(self):
        """⭐ At 22:00 with both slots missed, the 09:00 one stays missed
        on purpose: two reminders saying the same thing is noise, and the
        queue post replaces rather than appends."""
        assert latest_due_slot(NOW.replace(hour=22), [9, 21], []) == "2026-09-04:21"

    def test_a_malformed_hour_list_does_not_crash(self):
        assert latest_due_slot(NOW.replace(hour=14), ["9", None], []) is None
