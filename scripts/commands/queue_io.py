"""
Per-campaign queue I/O.

Each active campaign has its own JSON file at:
  data/state/queues/{pid}.json

Structure:
  {
    "pid":       "40585",
    "unreplied": [...],   # live queue entries (msg_id, time, player, preview, link)
    "replied":   [...],   # reply keys (msg:id, timestamp) — no cap
    "reply_log": [...]    # permanent audit trail — no cap
  }

This replaces the monolithic gm_queue / gm_queue_replied / gm_reply_log
keys in queue.json, giving each campaign its own bounded file with no
cross-campaign eviction.
"""

import json
from pathlib import Path

_QUEUES_DIR = Path(__file__).parent.parent.parent / "data" / "state" / "queues"


def _path(pid: str) -> Path:
    return _QUEUES_DIR / f"{pid}.json"


def load(pid: str) -> dict:
    """Load campaign queue state. Returns empty structure if not yet created."""
    p = _path(pid)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"pid": pid, "unreplied": [], "replied": [], "reply_log": []}


def save(pid: str, cq: dict) -> bool:
    """Save campaign queue state to its own file."""
    try:
        _QUEUES_DIR.mkdir(parents=True, exist_ok=True)
        _path(pid).write_text(json.dumps(cq, indent=2))
        return True
    except OSError as e:
        print(f"queue_io: failed to save {pid}: {e}")
        return False


def all_pids() -> list[str]:
    """Return PIDs for all campaigns with a queue file."""
    if not _QUEUES_DIR.exists():
        return []
    return [p.stem for p in _QUEUES_DIR.glob("*.json")]


def replied_set(pid: str) -> set[str]:
    """Return the set of replied keys for a campaign (fast lookup)."""
    return set(load(pid).get("replied", []))


def mark_replied(pid: str, mid_key: str, ts_key: str | None,
                 log_entry: dict) -> bool:
    """Add reply keys and a log entry to a campaign's queue file.

    Idempotent: if mid_key is already in replied the reply has already
    been recorded and reply_log is not appended again. Removes the
    message from unreplied either way (cheap and self-healing if a
    stale unreplied entry lingers).

    Returns True when the reply was newly recorded, False when it was
    already present. Callers (notably dispatch/tracking.py) use this
    to gate downstream side-effects such as record_reply.
    """
    cq = load(pid)
    replied = cq.setdefault("replied", [])
    is_new = bool(mid_key) and mid_key not in replied
    if is_new:
        replied.append(mid_key)
    if ts_key and ts_key not in replied:
        replied.append(ts_key)
    # Remove from unreplied unconditionally (no-op if already removed).
    msg_id = log_entry.get("msg_id", "")
    cq["unreplied"] = [e for e in cq.get("unreplied", [])
                       if str(e.get("message_id", "")) != msg_id]
    if is_new:
        cq.setdefault("reply_log", []).append(log_entry)
    save(pid, cq)
    return is_new


def migrate_from_state(state: dict) -> int:
    """One-time migration: copy gm_queue_replied from shared state to per-campaign files.

    Safe to call multiple times — skips PIDs already migrated.
    Returns number of campaigns migrated.
    """
    migrated = 0
    for pid, replied in state.get("gm_queue_replied", {}).items():
        existing = load(pid)
        if existing.get("replied"):
            continue  # already migrated
        existing["replied"] = list(replied)
        # Also migrate live queue entries
        for e in state.get("gm_queue", {}).get(pid, []):
            existing["unreplied"].append(e)
        # Migrate reply_log entries for this pid
        for entry in state.get("gm_reply_log", []):
            if entry.get("pid") == pid:
                existing["reply_log"].append(entry)
        save(pid, existing)
        migrated += 1
    return migrated
