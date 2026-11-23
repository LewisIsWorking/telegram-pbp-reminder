"""Days the GM was silent do not count against a player's 4-week clock.

Added 2026-11-23. C05 Grand Explorers: the GM's last post on 2026-10-21
left the arrival at the stump still to come, and the GM did not post
again until 2026-11-10. Every player was correctly waiting. The 4-week
sweep measured only each player's own silence, so between 2026-11-10 and
11-18 it removed all four of them, and the campaign read 0/6.

The rule: any stretch of GM_SILENCE_DAYS or more with no GM post in a
campaign is taken off every player's clock in that campaign, including a
stretch that is still running now. A player quiet for 28 days, 20 of
them waiting on a GM who was silent, has used 8.

Why a persistent record and not ``post_timestamps``: those are pruned to
15 days (scheduled/maintenance.py), so a GM silence longer than that
would leave no trace of when it began. ``gm_silences[pid]`` keeps the
GM's last post time and the silences that ended, for KEEP_DAYS.
"""

from datetime import datetime, timedelta

import helpers
from scheduled.gm_bottleneck import gm_last_post

GM_SILENCE_DAYS = 3  # the same line scheduled/alerts.py calls the GM bottleneck
KEEP_DAYS = 120


def record_gm_post(config: dict, state: dict, pid: str, msg_time_iso: str) -> None:
    """Note a GM post; close the silence it ends. Call BEFORE post_timestamps is appended."""
    entry = state.setdefault("gm_silences", {}).setdefault(pid, {"last": None, "gaps": []})
    now = datetime.fromisoformat(msg_time_iso)
    last = _latest(entry.get("last"), gm_last_post(config, state, pid))
    if last is not None and now - last >= timedelta(days=GM_SILENCE_DAYS):
        entry["gaps"].append([last.isoformat(), msg_time_iso])
    if last is None or now > last:
        entry["last"] = msg_time_iso
    cutoff = now - timedelta(days=KEEP_DAYS)
    entry["gaps"] = [g for g in entry["gaps"] if datetime.fromisoformat(g[1]) >= cutoff]


def counted_days(config: dict, state: dict, pid: str, since: datetime, now: datetime) -> float:
    """Days since ``since`` that count against a player: GM silences are left out."""
    entry = state.get("gm_silences", {}).get(pid, {})
    gaps = [(datetime.fromisoformat(s), datetime.fromisoformat(e)) for s, e in entry.get("gaps", [])]
    last = _latest(entry.get("last"), gm_last_post(config, state, pid))
    if last is not None and now - last >= timedelta(days=GM_SILENCE_DAYS):
        gaps.append((last, now))  # the GM is silent right now
    silent = sum((max(timedelta(0), min(e, now) - max(s, since)) for s, e in gaps), timedelta(0))
    return max(0.0, helpers.days_since(now, since) - silent / timedelta(days=1))


def _latest(stored: str | None, seen: datetime | None) -> datetime | None:
    found = [d for d in (datetime.fromisoformat(stored) if stored else None, seen) if d is not None]
    return max(found) if found else None
