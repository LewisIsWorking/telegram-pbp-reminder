"""
State persistence — file-primary with gist backup.

Primary:  data/state/{live,players,queue,activity}.json (git-committed each run)
Fallback: GitHub Gist (read if files absent; always written for safety)

Public API is unchanged: init(token, gist_id) / load() / save(state).
"""

import json

from state_gist import gist_load, gist_save
from pathlib import Path

# ── Partition map ─────────────────────────────────────────────────────────────
# Keys not listed here (e.g. _config_cache) are transient and not persisted.

PARTITIONS: dict[str, list[str]] = {
    "live": [
        "offset", "topics", "last_alerts", "last_roster", "last_potw",
        "last_pace", "last_anniversary", "combat", "last_leaderboard",
        "last_roster_nudge", "last_roster_snapshot", "gm_escalation",
        "last_recruitment_check", "last_archived_week", "celebrated_streaks",
        "celebrated_milestones", "last_weekly_digest", "last_daily_tip",
        "used_tip_indices", "last_pace_drop_check", "dying_alerts_sent",
        "last_campaign_table", "session_poll", "last_state_backup",
        "last_queue_daily", "last_queue_fingerprint", "queue_nudged",
        "paused_campaigns", "current_scenes", "poll_unknown_voters",
        "last_week_welcome", "last_queue_daily_slots", "swimming_poll",
        "queue_scan_floor", "last_diagnostic", "last_queue_pin_id",
        "queue_post_count", "gm_queue_history",
    ],
    "players": [
        "players", "removed_players", "player_registry", "player_history",
        "player_boons", "mvp_wins", "characters", "away",
    ],
    "queue": [
        "queue_history", "queue_archive", "pending_potw_boons",
    ],
    "activity": [
        "post_timestamps", "message_counts", "activity_hours",
        "activity_days", "word_counts", "session_counts", "session_last_day",
        "poll_history", "poll_results", "potw_history",
        "thread_message_counts",
    ],
    "trackers": [
        "clocks", "conditions", "hp_tracker", "loot", "npcs",
        "pins", "quests", "reactions", "timers", "votes",
        "campaign_notes",
    ],
}

DEFAULT_STATE: dict = {
    "offset": 0, "topics": {}, "last_alerts": {}, "players": {},
    "removed_players": {}, "player_history": [], "message_counts": {}, "last_roster": {},
    "post_timestamps": {}, "last_potw": {}, "last_pace": {},
    "last_anniversary": {}, "combat": {}, "pending_potw_boons": {},
    "last_leaderboard": None, "last_recruitment_check": {}, "last_roster_nudge": None, "last_roster_snapshot": None, "gm_escalation": {},
    # Trackers (written by in-game commands)
    "characters": {}, "away": {}, "paused_campaigns": {},
    "clocks": {}, "conditions": {}, "hp_tracker": {}, "loot": {},
    "npcs": {}, "pins": {}, "quests": {}, "reactions": {},
    "timers": {}, "votes": {}, "campaign_notes": {}, "current_scenes": {},
    "poll_history": {}, "poll_results": {}, "poll_unknown_voters": {},
    "potw_history": [], "last_week_welcome": None,
    "thread_message_counts": {},
    "last_queue_daily_slots": [], "swimming_poll": {},
    "queue_scan_floor": None, "last_diagnostic": None,
    "last_queue_pin_id": None, "queue_post_count": 0,
    "gm_queue_history": [],
}

STATE_FILENAME = "pbp_state.json"  # kept for gist compatibility

# ── Module-level credentials ───────────────────────────────────────────────────

_GIST_TOKEN = ""
_GIST_API   = ""
_loaded_ok  = False   # guards against saving after a failed load


def init(gist_token: str, gist_id: str) -> None:
    """Set gist credentials (called by checker.py — signature unchanged)."""
    global _GIST_TOKEN, _GIST_API
    _GIST_TOKEN = gist_token
    _GIST_API   = f"https://api.github.com/gists/{gist_id}" if gist_id else ""


# ── Public API ─────────────────────────────────────────────────────────────────

def load() -> dict:
    """Load state — files first, gist fallback, then defaults."""
    global _loaded_ok
    state = _load_from_files()
    if state is None:
        print("State files absent — falling back to gist")
        state = gist_load(_GIST_API, _GIST_TOKEN, STATE_FILENAME)
    if state is None:
        print("Warning: could not load state from files or gist; using defaults")
        state = dict(DEFAULT_STATE)
    for key, default in DEFAULT_STATE.items():
        state.setdefault(key, default)
    _loaded_ok = True
    return state


def save(state: dict) -> None:
    """Persist state — writes files (primary) and gist (safety backup)."""
    if not _loaded_ok:
        print("REFUSING to save: state was not successfully loaded")
        return
    _save_to_files(state)
    gist_save(_GIST_API, _GIST_TOKEN, STATE_FILENAME, state)   # dual-write; gist becomes emergency read-only backup


# ── File I/O ───────────────────────────────────────────────────────────────────

def _state_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "state"


def _load_from_files() -> dict | None:
    """Load and merge all partition files. Returns None if core files are missing.

    The 'trackers' partition is optional — if absent (e.g. fresh checkout or
    pre-v4.18 install) the bot will still load and write the file on next save.
    """
    d = _state_dir()
    core = [p for p in PARTITIONS if p != "trackers"]
    if not all((d / f"{p}.json").exists() for p in core):
        return None
    merged: dict = {}
    try:
        for partition in PARTITIONS:
            path = d / f"{partition}.json"
            if not path.exists():
                continue   # trackers.json may not exist yet
            raw = json.loads(path.read_text(encoding="utf-8"))
            keys = PARTITIONS[partition]
            merged.update({k: raw[k] for k in keys if k in raw})
        print(f"State loaded from files (offset={merged.get('offset', 0)})")
        return merged
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"Warning: failed reading state files ({e}), falling back to gist")
        return None


def _save_to_files(state: dict) -> None:
    """Write each partition file atomically."""
    d = _state_dir()
    d.mkdir(parents=True, exist_ok=True)
    for partition, keys in PARTITIONS.items():
        data = {k: state[k] for k in keys if k in state}
        path = d / f"{partition}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print("State saved to files")
