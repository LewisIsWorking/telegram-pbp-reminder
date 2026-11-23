"""Put back seats the 4-week sweep took while the game waited on the GM.

Added 2026-11-23, with scheduled/gm_silence.py. That module stops the
sweep counting GM silences from now on, but it only knew the last 15
days of GM posts, and four C05 Grand Explorers players had already been
removed for a silence that was the GM's (2026-11-10 to 11-18).

Runs ONCE (``gm_wait_unsweep_done``) and does two things:

1. Backfills ``gm_silences`` for every campaign from the PBP transcripts
   (``**Name** [GM] (time) msg#id@thread:`` lines, UTC), so silences
   older than the ``post_timestamps`` prune count too.
2. Puts back the RESTORE seats, each only if it is still an inactivity
   removal (never a /kick) and the rebuilt clock confirms it: last post
   taken as removed_at minus 4 weeks (the sweep fires on the first hourly
   run past it), and the GM silences in that month leave under 4 weeks
   counted. One note per campaign names who is back.

⛔ WHY A LIST, NOT EVERY SEAT THE RULE WOULD CLEAR. Run over all removals
   on the live state, the rule cleared 10 seats, including C04's Volf, who
   left the game. A GM silence does not tell a player who waited from one
   who walked away, so only seats the GM confirmed are put back. Later
   removals need no list: the clock itself now leaves GM silences out.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import helpers
import telegram as tg
from helpers import build_topic_maps
from helpers_pkg.groups import group_id_for_campaign
from players.history import _log
from scheduled.gm_silence import GM_SILENCE_DAYS, KEEP_DAYS, counted_days

# C05 Grand Explorers: Ryo, Laetheron, Buffet and Anthony, swept 2026-11-10 to 11-18.
RESTORE = ("51357:138025700", "51357:8117756377", "51357:7130942567", "51357:6144366145")
DONE_KEY = "gm_wait_unsweep_done"
LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"
_GM_LINE = re.compile(r"^\*\*.+?\*\* \[GM\] \((\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\) msg#\d+@(\d+):")


def restore_gm_wait_sweeps(config: dict, state: dict, *, now: datetime | None = None,
                           maps=None, logs_dir: Path | None = None) -> list:
    """Run once; return the restored seat keys."""
    if state.get(DONE_KEY):
        return []
    now = now or datetime.now(timezone.utc)
    maps = maps or build_topic_maps(config)
    backfill_gm_silences(state, maps, logs_dir or LOGS_DIR, now)
    restored = []
    for key in RESTORE:
        entry = state.get("removed_players", {}).get(key)
        pid = key.split(":", 1)[0]
        if not entry or entry.get("kicked") or pid not in maps.to_chat or key in state["players"]:
            continue
        removed_at = datetime.fromisoformat(entry["removed_at"])
        last = removed_at - timedelta(weeks=helpers.PLAYER_REMOVE_WEEKS)
        if counted_days(config, state, pid, last, removed_at) >= 7 * helpers.PLAYER_REMOVE_WEEKS:
            continue
        uid = key.split(":", 1)[1]
        state["players"][key] = {
            "user_id": uid, "first_name": entry.get("first_name", ""), "last_name": "",
            "username": entry.get("username", ""), "campaign_name": entry.get("campaign_name", ""),
            "pbp_topic_id": pid, "last_post_time": last.isoformat(), "last_warned_week": 0}
        del state["removed_players"][key]
        _log("join", pid, uid, entry.get("first_name", ""), entry.get("username", ""), state)
        restored.append(key)
    _announce(config, state, maps, restored)
    state[DONE_KEY] = now.isoformat()
    return restored


def backfill_gm_silences(state: dict, maps, logs_dir: Path, now: datetime) -> None:
    """Add the silences between GM posts found in the transcripts."""
    times: dict[str, list[datetime]] = {}
    for path in sorted(logs_dir.glob("*/*.md")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _GM_LINE.match(line)
            pid = m and maps.to_canonical.get(m.group(2))
            if pid:
                at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if now - at <= timedelta(days=KEEP_DAYS):
                    times.setdefault(pid, []).append(at)
    for pid, posts in times.items():
        posts.sort()
        entry = state.setdefault("gm_silences", {}).setdefault(pid, {"last": None, "gaps": []})
        gaps = {tuple(g) for g in entry["gaps"]}
        for a, b in zip(posts, posts[1:]):
            if b - a >= timedelta(days=GM_SILENCE_DAYS):
                gaps.add((a.isoformat(), b.isoformat()))
        entry["gaps"] = [list(g) for g in sorted(gaps, key=lambda g: datetime.fromisoformat(g[0]))]
        stored = datetime.fromisoformat(entry["last"]) if entry.get("last") else None
        if stored is None or posts[-1] > stored:
            entry["last"] = posts[-1].isoformat()


def _announce(config: dict, state: dict, maps, restored: list) -> None:
    by_pid: dict[str, list[str]] = {}
    for key in restored:
        p = state["players"][key]
        by_pid.setdefault(p["pbp_topic_id"], []).append(
            f"@{p['username']}" if p.get("username") else p["first_name"])
    for pid, names in by_pid.items():
        tg.send_message(group_id_for_campaign(config, pid), maps.to_chat[pid],
                        f"Back on the {maps.to_name.get(pid, '')} roster: {', '.join(names)}.\n"
                        "The bot removed them for inactivity while the game was waiting on the GM. "
                        "That time no longer counts.")
