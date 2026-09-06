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
from datetime import datetime

# marker -> (label, how many days may pass before it is worth saying).
# ⚠️ Tolerances are one cadence plus slack for a bad delivery day, not
# tight. A nag that fires on an ordinary Tuesday gets ignored, and then
# so does the one that matters.
CADENCES = {
    "last_diagnostic":       ("daily diagnostic", 2),
    "last_pin_digest":       ("pin digest", 2),
    "last_queue_daily":      ("daily GM queue", 2),
    "last_daily_tip":        ("daily tip", 3),
    "last_community_roster": ("community roster", 3),
    "last_state_backup":     ("state backup", 3),
    "last_weekly_digest":    ("weekly digest", 10),
    "last_leaderboard":      ("leaderboard", 10),
    "last_campaign_table":   ("campaign table", 10),
    "last_recruit_focus":    ("recruit advert", 3),
}


def _days_since(marker, now: datetime):
    if not isinstance(marker, str) or len(marker) < 10:
        return None
    try:
        return (now.date() - datetime.fromisoformat(marker[:10]).date()).days
    except ValueError:
        return None


def overdue(state: dict, now: datetime) -> list:
    """``(label, days, tolerance)`` for every job past its cadence.

    A marker that is missing or unreadable is reported with ``days=None``
    rather than skipped: "this feature has no record of ever running" is
    the strongest version of the thing being looked for, and skipping it
    would hide the worst case. See
    ``a-null-measurement-is-skipped-not-ranked``.
    """
    out = []
    for key, (label, tolerance) in CADENCES.items():
        if key not in state:
            continue
        days = _days_since(state.get(key), now)
        if days is None or days > tolerance:
            out.append((label, days, tolerance))
    return sorted(out, key=lambda row: (row[1] is not None, -(row[1] or 0)))


def summarise(state: dict, now: datetime) -> str:
    """One block for the debug report. Never silent, so an empty result
    is visibly an answer rather than a section that failed to run."""
    tracked = [k for k in CADENCES if k in state]
    if not tracked:
        return ("Daily jobs: NO MARKERS FOUND (suspicious - the state shape "
                "may have changed under this check)")
    late = overdue(state, now)
    head = f"Daily jobs: {len(tracked)} tracked, {len(late)} overdue"
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
        return f"Daily jobs: cannot read state ({error})"
    return summarise(state, now)
