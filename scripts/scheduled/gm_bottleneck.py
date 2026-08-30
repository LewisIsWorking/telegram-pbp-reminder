"""Is the GM the one holding the game up, and what do we say about it.

Extracted from ``scheduled/alerts.py`` on 2026-08-30, which had reached
201 lines splitting the inactivity warning gate from the removal gate.
Both halves of that file ask this same question, which is what makes it
a responsibility rather than a pair of helpers.

Why it exists at all
--------------------
Nagging a player for silence while the GM has not posted in a week is
worse than saying nothing: the player is waiting, correctly, and the bot
is blaming them for it. So the 1/2/3 week warnings are suppressed while
the GM is three or more days quiet, and the alert text carries a note
saying how long it has been.

⚠️ The 4-week **removal** is deliberately NOT suppressed by this. A seat
silent for a month is dead whoever is at fault, and leaving it counted
makes every roster figure wrong. Whose fault it was is a different
question from whether the seat is still occupied.

⛔ These two functions carry ten ``# pragma: no cover`` markers between
them, inherited unchanged. They are on live branches, not unreachable
ones, and they are on the list to clear rather than an exemption.
"""

from datetime import datetime

import helpers


def gm_last_post(config: dict, state: dict, pid: str) -> datetime | None:
    """Return the most recent GM post time for a campaign, or None."""
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    topic_ts = helpers.get_topic_timestamps(state, pid)
    gm_last = None
    for gm_id in gm_ids:
        gm_stamps = topic_ts.get(gm_id, [])
        if gm_stamps:
            gm_dt = datetime.fromisoformat(gm_stamps[-1])  # pragma: no cover
            if gm_last is None or gm_dt > gm_last:  # pragma: no cover
                gm_last = gm_dt  # pragma: no cover
    return gm_last


def gm_note(config: dict, state: dict, pid: str, now: datetime) -> str:
    """Return a GM inactivity note if the GM isn't the last poster, else ''."""
    topic_state = state.get("topics", {}).get(pid, {})
    last_user_id = topic_state.get("last_user_id", "")
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if last_user_id in gm_ids:
        return ""  # pragma: no cover
    gm_last = gm_last_post(config, state, pid)
    if not gm_last:
        return ""
    gm_elapsed = helpers.hours_since(now, gm_last)  # pragma: no cover
    gm_days = int(gm_elapsed) // 24  # pragma: no cover
    gm_hours = int(gm_elapsed) % 24  # pragma: no cover
    gm_time = f"{gm_days}d {gm_hours}h" if gm_days > 0 else f"{gm_hours}h"  # pragma: no cover
    return f"\n\nGM hasn't posted in {gm_time}."  # pragma: no cover
