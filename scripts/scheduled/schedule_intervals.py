"""Interval jobs, as data (2026-08-13).

Companion to ``schedule_table``, which holds the fixed-clock jobs. The
split is the *gate shape*, not the subject: a job here fires relative to
its own last run, so it has no time of day to advertise and the schedule
post renders "next due" instead of a clock.

⚠️ **Every job gated on an interval belongs here.** ``checks`` names the
label the job is registered under in ``checker._run_checks``, which is
what ``test_schedule_is_complete.py`` matches against. A scheduled job
absent from both this table and ``schedule_table`` fails that guard,
rather than quietly going missing from the post — which is exactly what
happened to seven of them until 2026-08-13.

Per-campaign keys
-----------------
Several of these store ``{pid: iso}`` rather than a single timestamp, so
"next due" is the *earliest* campaign's. Only campaigns still present in
``config`` count: state accumulates ids for campaigns that have since
been removed, and a removed campaign is never iterated by its job, so
its timestamp sits in the past forever and pins the line to "due now"
permanently. Orphan ``1242`` had been doing exactly that.
"""

from datetime import datetime, timedelta
from typing import NamedTuple

import helpers
from helpers import build_topic_maps


class IntervalJob(NamedTuple):
    """One interval-gated job: where its last run is stored, and how often."""

    key: str
    days: float
    label: str
    checks: tuple[str, ...]
    # ⛔ The per-campaign feature flag the job itself checks, if any.
    # Without it a campaign with the feature OFF is never iterated, so
    # its timestamp freezes and the job reads as permanently "due now".
    # The Junction had recruitment off, and the schedule post said
    # "Recruitment check - due now (1 of 8 campaigns)" every day from
    # 2026-08-13 until this was added on 2026-09-06.
    feature: str | None = None


# Ordered by nothing in particular — the post sorts by due time.
INTERVAL_JOBS: list[IntervalJob] = [
    # scheduled/leaderboard.py:136
    IntervalJob("last_leaderboard", helpers.LEADERBOARD_INTERVAL_DAYS,
                "Leaderboard", ("Leaderboard",)),
    # scheduled/reports.py:23 — per campaign
    IntervalJob("last_roster", helpers.ROSTER_INTERVAL_DAYS,
                "Roster summary", ("Roster summary",), "roster"),
    # scheduled/reports.py:105 — per campaign
    IntervalJob("last_pace", helpers.PACE_INTERVAL_DAYS,
                "Pace report", ("Pace report",), "pace"),
    # Added 2026-08-13. The six below were all running on a real interval
    # gate and none of them appeared in the schedule post, so it listed 11
    # of the 18 scheduled jobs while claiming to be the schedule.
    # scheduled/maintenance.py:147 — per campaign
    IntervalJob("last_recruitment_check", helpers.RECRUITMENT_INTERVAL_DAYS,
                "Recruitment check", ("Recruitment",), "recruitment"),
    # scheduled/digest.py:80
    IntervalJob("last_weekly_digest", 7, "Weekly digest", ("Weekly digest",)),
    # scheduled/campaign_table.py:127
    IntervalJob("last_campaign_table", 6.5, "Campaign table",
                ("Campaign table",)),
    # scheduled/smart_alerts.py:22
    IntervalJob("last_pace_drop_check", 7, "Pace-drop alerts", ("Pace drop",)),
    # scheduled/tips.py:24 — hand-rolled as hours_since(...) < 22 rather
    # than interval_elapsed, which is why a scan for the latter missed it.
    IntervalJob("last_daily_tip", 22 / 24, "Daily tip", ("Daily tip",)),
    # scheduled/state_backup.py:16
    IntervalJob("last_state_backup", 1, "State backup", ("State backup",)),
    # scheduled/recruit_focus.py:_GATE_HOURS. Added 2026-08-15 with the
    # feature itself — the completeness guard failed the moment it was
    # registered in checker._run_checks and nowhere else, which is what
    # that guard exists to do.
    IntervalJob("last_recruit_focus", 1, "Recruit focus", ("Recruit focus",)),
    # scheduled/community_roster.py:INTERVAL_DAYS. Added 2026-08-30.
    IntervalJob("last_community_roster", 7, "Community roster",
                ("Community roster",)),
]


def live_pids(config: dict) -> set[str]:
    """Canonical campaign ids currently in config, or empty if unknowable.

    ⭐ Public since 2026-09-06: ``preflight/stale_features`` needs the
    same orphan filtering, and a second copy of it would drift.

    Empty means "do not filter". An empty result is ambiguous — it is
    equally what a config with no campaigns and an unreadable config
    produce — and dropping every timestamp on that ambiguity would turn
    every per-campaign line into a permanent "due now", which is the
    bug this filter exists to fix.
    """
    try:
        return set(build_topic_maps(config).to_chat)
    except (KeyError, TypeError):
        return set()


def job_pids(config: dict, job: "IntervalJob"):
    """Campaigns this job actually iterates.

    Returns ``None`` for "cannot tell", which callers must treat as "do
    not filter" - an unreadable config is not evidence that a campaign
    is gone. Returns an EMPTY set only when the job is genuinely
    switched off everywhere, which is different and means the job has
    nothing to be overdue for.
    """
    pids = live_pids(config)
    if not pids:
        return None
    if not job.feature:
        return pids
    try:
        return {p for p in pids
                if helpers.feature_enabled(config, p, job.feature)}
    except (KeyError, TypeError, AttributeError):
        return None


def stamps(value, known: set[str]) -> list[datetime]:
    """Parsed timestamps from a str or a ``{pid: iso}`` dict.

    ⭐ Public since 2026-09-06, shared with ``preflight/stale_features``.
    ⚠️ ``known`` is what stops a REMOVED campaign's timestamp sitting in
    the past forever and reading as permanently overdue. Orphan 1242 did
    exactly that."""
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, dict):
        raw = [v for k, v in value.items()
               if isinstance(v, str) and (not known or k in known)]
    else:
        return []
    out = []
    for s in raw:
        try:
            out.append(datetime.fromisoformat(s))
        except (ValueError, TypeError):
            continue
    return out


def _when(hours: float) -> str:
    if hours <= 0:
        return "due now"
    return f"in {int(hours)}h" if hours < 48 else f"in {int(hours // 24)}d"


def interval_lines(config: dict, state: dict, now: datetime) -> list[str]:
    """One 'next due' line per interval job, soonest first.

    Per-campaign jobs also report how many campaigns are due, because
    "due now" on its own cannot distinguish one straggler from the whole
    set — and a single permanently-stalled campaign is the common case.
    """
    rows: list[tuple[float, str]] = []
    for job in INTERVAL_JOBS:
        eligible = job_pids(config, job)
        if eligible is not None and not eligible:
            continue  # the job is switched off everywhere; nothing is due
        value = state.get(job.key)
        found = stamps(value, eligible or set())
        if not found:
            rows.append((0.0, f"  • {job.label} — due now"))
            continue
        due = [s + timedelta(days=job.days) for s in found]
        hours = (min(due) - now).total_seconds() / 3600
        text = f"  • {job.label} — {_when(hours)}"
        if isinstance(value, dict):
            # Denominator is len(found), not len(value): the orphans
            # filtered out above must not pad the total either, or the
            # line reports campaigns that no longer exist.
            overdue = sum(1 for d in due if d <= now)
            if overdue:
                text += f" ({overdue} of {len(found)} campaigns)"
        rows.append((hours, text))
    rows.sort(key=lambda r: r[0])
    return [text for _h, text in rows]
