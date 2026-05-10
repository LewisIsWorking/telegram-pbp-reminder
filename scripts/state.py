"""
State persistence — file-primary with gist backup.

Primary:  data/state/{live,players,queue,activity}.json (git-committed each run)
Fallback: GitHub Gist (read if files absent; always written for safety)

Public API is unchanged: init(token, gist_id) / load() / save(state).
"""

from state_gist import gist_load, gist_save
from pathlib import Path
from state_store import StateStore

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

# ── State persistence ─────────────────────────────────────────────────────────
#
# Slice 3 of P3/9 introduces StateStore for the read path. Per-call
# instantiation rather than a module-level singleton: this preserves
# the existing test contract where ``test_state_io.py`` patches
# ``state._state_dir`` to redirect file I/O to a tmp directory. The
# StateStore picks up that override on each call. Slice 4 will add
# the write path; slice 8 will add the locking primitives needed by
# P3/10.

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

    Slice 3 of P3/9: per-partition reads now go through
    ``StateStore.load_partition``. The StateStore is constructed per
    call from ``_state_dir()`` so test patches of that helper redirect
    file I/O to a tmp dir as before. The corruption-handling stays
    here at the call-site (returning None to trigger gist fallback)
    since that's a state.py policy choice, not a StateStore concern:
    a corrupt partition file means we cannot trust the on-disk state
    and should reload from gist rather than silently skipping the
    bad partition (which would merge a half-loaded state with stale
    other partitions).
    """
    store = StateStore(state_dir=_state_dir())
    core = [p for p in PARTITIONS if p != "trackers"]
    if not all(store.partition_exists(p) for p in core):
        return None
    merged: dict = {}
    try:
        for partition in PARTITIONS:
            if not store.partition_exists(partition):
                continue   # trackers.json may not exist yet (fresh checkout)
            raw = store.load_partition(partition)
            if raw is None:
                # File exists but parse failed (StateStore already
                # printed a diagnostic) — treat as corruption and
                # fall back to gist for a known-good snapshot.
                print(f"Warning: corrupt {partition}.json, "
                      f"falling back to gist")
                return None
            keys = PARTITIONS[partition]
            merged.update({k: raw[k] for k in keys if k in raw})
        print(f"State loaded from files (offset={merged.get('offset', 0)})")
        return merged
    except KeyError as e:
        print(f"Warning: missing key in state files ({e}), falling back to gist")
        return None


def _save_to_files(state: dict) -> None:
    """Write each partition file atomically.

    Slice 4 of P3/9: per-partition writes now go through
    ``StateStore.save_partition``, which uses tmp+rename so a crash
    mid-write cannot leave a half-written file. Pre-slice-4 this
    function did ``path.write_text(json.dumps(...))`` per partition,
    which the docstring claimed was atomic but actually wasn't —
    Python's ``write_text`` opens the target file directly. With the
    new path, ``StateStore.save_aux`` writes to ``{name}.json.tmp``
    first and only ``os.replace``s onto ``{name}.json`` once the
    full content is on disk. The replace is atomic on POSIX and on
    Windows (NTFS).
    """
    store = StateStore(state_dir=_state_dir())
    for partition, keys in PARTITIONS.items():
        data = {k: state[k] for k in keys if k in state}
        store.save_partition(partition, data)
    print("State saved to files")
