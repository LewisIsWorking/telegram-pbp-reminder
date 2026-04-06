"""
Per-topic pinned queue post/update/delete loop.

Called once per hourly run from scheduled/queue_reminder.py.
For each PBP topic with unreplied entries, maintains a pinned queue
message scoped to only that topic's entries (no campaign header).

State is stored alongside other queue data in the per-campaign queue
files managed by commands/queue_io:
  topic_msg_id      — message_id of the current pinned queue message
  topic_fingerprint — change-detection string; post is skipped if unchanged
"""

from datetime import datetime

import telegram as tg
from commands.queue_io import load as _load, save as _save, all_pids as _all_pids
from commands.topic_queue_format import format_topic_queue, build_topic_fingerprint
from helpers_pkg.campaigns import get_pair


def _group_id_for(config: dict, pid: str) -> int:
    """Return the Telegram group_id for a campaign, falling back to the global default."""
    pair = get_pair(config, pid)
    return pair.get("group_id", config["group_id"]) if pair else config["group_id"]  # pragma: no cover


def _post_topic_queue(config: dict, pid: str,
                      entries: list, now: datetime) -> None:
    """Post or refresh the pinned queue in a PBP topic thread.

    Skips when the fingerprint is unchanged and a pinned message already
    exists. Deletes the stale pinned message before posting the new one.
    """
    cq = _load(pid)
    fingerprint = build_topic_fingerprint(entries)

    if fingerprint == cq.get("topic_fingerprint", "") and cq.get("topic_msg_id"):
        return  # No change — nothing to do

    group_id = _group_id_for(config, pid)
    topic_id = int(pid)

    old_msg_id = cq.get("topic_msg_id")
    if old_msg_id:
        tg.delete_message(group_id, old_msg_id)

    text = format_topic_queue(entries, now)
    new_msg_id = tg.send_message_id(group_id, topic_id, text)
    if new_msg_id:
        tg.pin_message(group_id, new_msg_id, disable_notification=False)
        cq["topic_msg_id"] = new_msg_id
        cq["topic_fingerprint"] = fingerprint
        _save(pid, cq)
        print(f"Topic queue posted: pid={pid} entries={len(entries)}")


def _clear_topic_queue(config: dict, pid: str) -> None:
    """Send an all-caught-up notification and remove the stale pin.

    No-op if there is no pinned message to clear.
    """
    cq = _load(pid)
    old_msg_id = cq.get("topic_msg_id")
    if not old_msg_id:
        return

    group_id = _group_id_for(config, pid)
    topic_id = int(pid)

    tg.send_message(group_id, topic_id, "━━━━━━━━━━━━━━━━\n✅ All caught up!")
    tg.unpin_message(group_id, old_msg_id)
    tg.delete_message(group_id, old_msg_id)
    cq["topic_msg_id"] = None
    cq["topic_fingerprint"] = ""
    _save(pid, cq)
    print(f"Topic queue cleared: pid={pid}")


def post_topic_queues(config: dict, scanned: dict, now: datetime) -> None:
    """Post, update, or clear per-topic pinned queues for all campaigns.

    Args:
        config:  bot configuration dict.
        scanned: {pid: {entries, campaign, code}} from scan_transcripts.
        now:     current UTC datetime.
    """
    for pid, data in scanned.items():
        _post_topic_queue(config, pid, data["entries"], now)

    for pid in _all_pids():
        if pid not in scanned:
            _clear_topic_queue(config, pid)
