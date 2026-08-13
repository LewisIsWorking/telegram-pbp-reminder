"""Every scheduled job must appear in the schedule post (2026-08-13).

The bug this prevents
---------------------
Lewis asked whether the posted schedule was correct. Everything it said
was true — every hour, weekday and interval matched its real gate,
because ``test_schedule_post.py`` already checks the rows it *has*
against the constants they quote.

It listed 11 of the 18 scheduled jobs.

Missing entirely: the daily pin digest (which fires at the same hour as
the diagnostic, so the post showed one job at 09:00 BST when two were
due), plus six interval jobs — recruitment, weekly digest, campaign
table, pace-drop alerts, daily tip and state backup.

Why nothing caught it
---------------------
Every existing guard is *per row*: given a row, does it quote the right
constant. A missing row has no constant to disagree with, so a job that
was never added is indistinguishable from a job that does not exist.
That is a gap that reads as done — the suite is green, the post renders,
and the only way to notice is to hold the schedule beside the job list
and count.

This guard closes it by anchoring to ``checker._run_checks``, which is
the one authoritative registry of what the bot runs. Every label there
must be claimed by a fixed-clock row, an interval row, or an explicit
entry below saying why it has no schedule. Adding a job to the checker
and not the schedule fails here.

It reads the registry by AST rather than importing ``checker``, which
pulls in the whole bot and its credentials.
"""

import ast
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

_CHECKER = Path(os.path.dirname(__file__)) / "checker.py"

# A config with every switchable job ON, so the guard sees rows that the
# live config currently suppresses. Swimming is off in production; that
# is a setting, not a reason for the schedule to have no row for it.
_MAX_CFG = {
    "group_id": -100, "bot_topic_id": 1, "topic_pairs": [],
    "queue_daily_hours": [9, 21], "poll_post_hour": 7,
    "diagnostic_hour": 8, "pin_digest_hour": 8,
    "swimming_poll_enabled": True,
}

# Jobs with no schedule because they have no schedule — they fire on a
# condition, not a clock or an interval. Each needs a reason; an
# unexplained entry here is how this guard would rot into a rubber stamp.
_EVENT_DRIVEN = {
    "Topic alerts": "fires when a topic passes alert_after_hours of silence",
    "Player activity": "recomputes from transcripts every run",
    "Boon expiry": "fires when a pending boon passes its expiry",
    "Roster nudge": "fires when a roster falls below its target",
    "GM escalation": "fires when a queue entry passes the escalation age",
    "Streak milestones": "fires when a player's streak crosses a threshold",
    "Anniversaries": "fires on a campaign's created-date anniversary",
    "Message milestones": "fires when a count crosses a round number",
    "Combat pings": "fires when a combat turn passes COMBAT_PING_HOURS",
    "Archive": "fires on the first tick of a new ISO week, at no set hour",
    "Conversation dying": "fires when a thread's gap crosses the threshold",
    "Timer expiry": "fires when a GM-set timer runs out",
    "Queue nudge": "fires when a queue entry crosses 48h",
    "Swimming ping": "daily only while a swimming poll is open",
    "Non-bot pin alert": "fires when a pin touches a non-bot message",
    "Schedule post": "the post itself",
}


def _registered_checks() -> list[str]:
    """The labels in ``checker._run_checks``'s ``checks`` list."""
    tree = ast.parse(_CHECKER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "_run_checks":
            continue
        for stmt in ast.walk(node):
            if not isinstance(stmt, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "checks"
                       for t in stmt.targets):
                continue
            return [e.elts[0].value for e in stmt.value.elts
                    if isinstance(e, ast.Tuple)
                    and isinstance(e.elts[0], ast.Constant)]
    return []


def _scheduled_checks() -> set[str]:
    """Every checker label claimed by a row in the schedule tables."""
    from scheduled.schedule_intervals import INTERVAL_JOBS
    from scheduled.schedule_table import fixed_schedule
    claimed: set[str] = set()
    for row in fixed_schedule(_MAX_CFG):
        claimed.update(row["checks"])
    for job in INTERVAL_JOBS:
        claimed.update(job.checks)
    return claimed


class TestDiscovery:
    """If the AST scan breaks, this guard silently passes forever."""

    def test_finds_the_whole_registry(self):
        checks = _registered_checks()
        assert len(checks) > 25, (
            f"only found {len(checks)} checks in checker._run_checks — the "
            f"AST scan has probably broken, which would make this guard "
            f"vacuous")

    def test_finds_a_known_label(self):
        assert "Daily diagnostic" in _registered_checks()

    def test_labels_are_unique(self):
        """``only=`` filters by label, so a duplicate would run twice."""
        checks = _registered_checks()
        assert len(checks) == len(set(checks))


class TestEveryJobIsAccountedFor:
    def test_no_scheduled_job_is_missing_from_the_post(self):
        accounted = _scheduled_checks() | set(_EVENT_DRIVEN)
        missing = sorted(set(_registered_checks()) - accounted)
        assert not missing, (
            f"these jobs run but appear nowhere in the schedule post: "
            f"{missing}.\nAdd a row to scheduled/schedule_table.py (fixed "
            f"clock) or scheduled/schedule_intervals.py (interval gate), "
            f"naming the check in its `checks` field — or add it to "
            f"_EVENT_DRIVEN in this file with the condition it fires on.\n"
            f"A job missing from the post is invisible to the GM, who has "
            f"no other list of what the bot does.")

    def test_no_row_names_a_job_that_no_longer_runs(self):
        """A renamed check must not leave a row advertising a dead job."""
        registered = set(_registered_checks())
        dangling = sorted((_scheduled_checks() | set(_EVENT_DRIVEN))
                          - registered)
        assert not dangling, (
            f"these are claimed by the schedule but are not registered in "
            f"checker._run_checks: {dangling}. Either the check was renamed "
            f"or removed — update the `checks` field or drop the row.")

    def test_event_driven_entries_all_give_a_reason(self):
        blank = [k for k, v in _EVENT_DRIVEN.items() if not v.strip()]
        assert not blank, f"no reason given for {blank}"


class TestTheSevenThatWereMissing:
    """Named so a refactor cannot quietly drop them again."""

    def test_pin_digest_is_on_the_fixed_clock(self):
        from scheduled.schedule_table import fixed_schedule
        rows = fixed_schedule(_MAX_CFG)
        pin = next(r for r in rows if "Pin digest" in r["label"])
        assert pin["day"] is None, "it is daily"
        assert pin["hour"] == 8, "mirrors pin_report's pin_digest_hour"

    def test_the_six_interval_jobs_are_listed(self):
        from scheduled.schedule_intervals import INTERVAL_JOBS
        keys = {j.key for j in INTERVAL_JOBS}
        for key in ("last_recruitment_check", "last_weekly_digest",
                    "last_campaign_table", "last_pace_drop_check",
                    "last_daily_tip", "last_state_backup"):
            assert key in keys, f"{key} gates a real job but is not listed"


class TestTheGuardCanFail:
    """Prove it by feeding it the bug, rather than trusting green."""

    def test_removing_an_interval_row_is_caught(self, monkeypatch):
        from scheduled import schedule_intervals as si
        kept = [j for j in si.INTERVAL_JOBS if j.label != "Leaderboard"]
        assert len(kept) == len(si.INTERVAL_JOBS) - 1, "MUTATION DID NOT APPLY"
        monkeypatch.setattr(si, "INTERVAL_JOBS", kept)
        accounted = _scheduled_checks() | set(_EVENT_DRIVEN)
        assert "Leaderboard" in set(_registered_checks()) - accounted, (
            "the completeness check did not notice a removed row")
