"""Which once-a-day jobs have stopped happening.

⛔⛔ Added 2026-09-06, because nothing was asking. ``last_diagnostic``
and ``last_pin_digest`` sat at 2026-08-27 for **ten days** while the bot
reported itself healthy every hour. The runs were green, the tests were
green, and two features simply were not happening.

That is the gap this closes. Everything else in ``preflight`` asks "can
the bot still record what it sends" - a question about the machinery.
None of it asks the simpler question a human would: **has this actually
happened lately?**

⭐ Reads the ``last_*`` date markers the features already maintain, so
there is nothing new to keep in sync and nothing that can drift out of
agreement with the feature itself. A marker IS the feature's own record
of having run.

⚠️ Cadences are declared here rather than inferred. Inferring "it looks
weekly" from the data would make a feature that stopped a fortnight ago
redefine itself as monthly and go quiet again, which is precisely the
failure being fixed.
"""

import json
import os
from datetime import datetime, timezone

from scheduled.schedule_intervals import INTERVAL_JOBS, job_pids, stamps

# ⛔⛔ DERIVED, not guessed. This block used to hardcode a tolerance per
# marker, and I invented the numbers. Four were wrong the moment they
# were written - `last_community_roster` is declared 7d and I guessed 3d,
# which would have nagged every ordinary week - and four declared jobs
# (roster, pace, recruitment, pace-drop) were not watched at all because
# I did not think of them.
#
# ``schedule_intervals.INTERVAL_JOBS`` already declares key -> days for
# every interval-gated job, and ``test_schedule_is_complete`` already
# fails when a job is missing from it. Reading it means correct
# tolerances, automatic coverage of jobs added later, and no second copy
# to drift.
SLACK_DAYS = 2

# ⚠️ The fixed-clock jobs have no declared interval to read: their table
# (``schedule_table.fixed_schedule``) is keyed by label and hour, not by
# state key, so there is nothing to derive from. All three are daily by
# construction. These are also the three that were dead for ten days.
FIXED_CLOCK = {
    "last_diagnostic": ("daily diagnostic", 1.0),
    "last_pin_digest": ("pin digest", 1.0),
    "last_queue_daily": ("daily GM queue", 1.0),
}


def cadences() -> dict:
    """marker -> (label, days that may pass before it is worth saying).

    ⚠️ Tolerance is the cadence plus slack for a bad delivery day, not
    the cadence itself. A nag that fires on an ordinary Tuesday gets
    ignored, and then so does the one that matters.
    """
    out = {key: (label, days + SLACK_DAYS)
           for key, (label, days) in FIXED_CLOCK.items()}
    for job in INTERVAL_JOBS:
        out[job.key] = (job.label, job.days + SLACK_DAYS)
    return out


def _days_since(marker, now: datetime, known=frozenset()):
    """Whole days since this job last ran, or None if it never has.

    ⚠️ A marker may be a timestamp OR a ``{pid: iso}`` map, and three of
    them are the second kind. Parsed by ``schedule_intervals.stamps``
    rather than a second copy of that logic, which also brings the
    filter for REMOVED campaigns: their timestamps sit in the past
    forever and would read as permanently overdue. Orphan 1242 did
    exactly that to the schedule post.

    ⭐ For a per-campaign marker this takes the OLDEST campaign, so one
    stalled campaign is enough to report. That matches what the schedule
    post means by "next due".
    """
    found = stamps(marker, known)
    if not found:
        return None
    oldest = min(found)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return (now.date() - oldest.date()).days


def overdue(state: dict, now: datetime, config: dict | None = None) -> list:
    """``(label, days, tolerance)`` for every job past its cadence.

    A marker that is missing or unreadable is reported with ``days=None``
    rather than skipped: "this feature has no record of ever running" is
    the strongest version of the thing being looked for, and skipping it
    would hide the worst case. See
    ``a-null-measurement-is-skipped-not-ranked``.
    """
    by_key = {job.key: job for job in INTERVAL_JOBS}
    out = []
    for key, (label, tolerance) in cadences().items():
        if key not in state:
            continue
        # ⛔ Per JOB, not one set for all of them. A campaign with the
        # job's feature switched OFF is never iterated, so its timestamp
        # freezes and the job reads as permanently overdue. The Junction
        # has recruitment off and made this check cry wolf the first
        # time it ran; the schedule post had been doing the same since
        # 2026-08-13.
        job = by_key.get(key)
        eligible = job_pids(config, job) if (config and job) else None
        if eligible is not None and not eligible:
            continue  # switched off everywhere; nothing to be overdue for
        days = _days_since(state.get(key), now, eligible or frozenset())
        if days is None or days > tolerance:
            out.append((label, days, tolerance))
    return sorted(out, key=lambda row: (row[1] is not None, -(row[1] or 0)))


def summarise(state: dict, now: datetime, config: dict | None = None) -> str:
    """One block for the debug report. Never silent, so an empty result
    is visibly an answer rather than a section that failed to run."""
    tracked = [k for k in cadences() if k in state]
    if not tracked:
        return ("Scheduled jobs: NO MARKERS FOUND (suspicious - the state "
                "shape may have changed under this check)")
    late = overdue(state, now, config)
    head = f"Scheduled jobs: {len(tracked)} tracked, {len(late)} overdue"
    if not late:
        return head
    lines = [head]
    for label, days, tolerance in late:
        seen = "NEVER RUN" if days is None else f"{days}d ago"
        lines.append(f"  {label}: last {seen} (expected within {tolerance}d)")
    return "\n".join(lines)


# ⚠️ Loads its own state, the way orphan_risk loads its own queue files.
# The gate does not read bot state and should not start: this check must
# not be able to perturb what it is inspecting.
_LIVE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "state", "live.json")


def summarise_from_disk(now: datetime, path: str = _LIVE) -> str:
    """The block for the debug report, reading state itself."""
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError) as error:
        return f"Scheduled jobs: cannot read state ({error})"
    try:
        from helpers_pkg.config import load_config
        config = load_config()
    except Exception:  # noqa: BLE001 - the filter is optional, the check is not
        config = None
    return summarise(state, now, config)
