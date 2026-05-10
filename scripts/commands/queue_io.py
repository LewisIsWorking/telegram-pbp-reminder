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

Slice 5 of P3/9: persistence routes through ``StateStore.load_queue``
and ``StateStore.save_queue``. The previous ``path.write_text`` save
was non-atomic — a crash mid-write could leave a half-written
``queues/{pid}.json`` that the next process startup would fail to
parse. The new path uses tmp+rename so the partial write is invisible
until the bytes are durable.
"""

from pathlib import Path

from state_store import StateStore

# Per-call StateStore from the package default state_dir. queue_io's
# tests don't currently patch the location — they all run in tmp_path
# context via _test_state_isolation — so a module-level instance is
# fine. If a future test needs to redirect, monkeypatch ``_store``
# in the same shape as ``posting.bot_sent_registry``.
_store = StateStore()

# Test-compat hook: many existing test fixtures monkeypatch
# ``_QUEUES_DIR`` to redirect queue I/O to a tmp directory. When set,
# queue paths resolve directly to ``{_QUEUES_DIR}/{pid}.json`` rather
# than going through ``_store.queue_path``. Production code never
# sets this; it stays None outside of test runs. Keeping this hook
# means slice 5's StateStore migration doesn't force a touch on every
# test file that ever exercised the old layout. New tests should
# prefer ``monkeypatch.setattr(queue_io, "_store", StateStore(...))``.
_QUEUES_DIR: Path | None = None


def _queue_path(pid: str) -> Path:
    """Resolve the on-disk path for a queue file.

    Honours the ``_QUEUES_DIR`` test override if set; otherwise
    delegates to ``_store.queue_path`` (the production path under
    ``data/state/queues/``).
    """
    if _QUEUES_DIR is not None:
        return Path(_QUEUES_DIR) / f"{pid}.json"
    return _store.queue_path(pid)


def load(pid: str) -> dict:
    """Load campaign queue state. Returns empty structure if not yet created.

    Slice 5: production path goes through ``StateStore.load_queue``;
    test-override path reads directly from ``_QUEUES_DIR`` for
    backward compat with the broad existing fixture base. Both paths
    return the same empty default on missing/corrupt.
    """
    if _QUEUES_DIR is not None:
        path = _queue_path(pid)
        if path.exists():
            try:
                import json
                return json.loads(path.read_text())
            except (Exception,):
                pass
        return {"pid": pid, "unreplied": [], "replied": [], "reply_log": []}
    cq = _store.load_queue(pid)
    if cq is None:
        return {"pid": pid, "unreplied": [], "replied": [], "reply_log": []}
    return cq


def save(pid: str, cq: dict) -> bool:
    """Save campaign queue state to its own file atomically.

    Slice 5: production writes go through ``StateStore.save_queue``
    (tmp+rename atomic). Test-override path uses ``path.write_text``
    so existing fixtures that patch ``Path.write_text`` to simulate
    OSError still work. Returns False on OSError so callers can
    surface the failure; pre-slice-5 contract preserved.
    """
    if _QUEUES_DIR is not None:
        try:
            import json
            path = _queue_path(pid)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cq, indent=2))
            return True
        except OSError as e:
            print(f"queue_io: failed to save {pid}: {e}")
            return False
    try:
        _store.save_queue(pid, cq)
        return True
    except OSError as e:
        print(f"queue_io: failed to save {pid}: {e}")
        return False


def all_pids() -> list[str]:
    """Return PIDs for all campaigns with a queue file.

    Slice 5 of P3/9: delegates to ``StateStore.list_queues``
    (production path) or scans ``_QUEUES_DIR`` directly (test
    override). The file-system layout (``queues/`` subdirectory)
    lives in StateStore, not here.
    """
    if _QUEUES_DIR is not None:
        d = Path(_QUEUES_DIR)
        if not d.exists():
            return []
        return [p.stem for p in d.glob("*.json")]
    return _store.list_queues()


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
