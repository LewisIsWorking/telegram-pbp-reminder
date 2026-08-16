"""A tracked message must never be allowed to age past Telegram's 48h wall.

COVERS  ``scheduled.topic_queue_write._batch_is_stale`` and the early
        return in ``_post_thread_queue`` that it now gates.
MISSES  The 48h limit itself. That is Telegram's behaviour, not ours, and
        the only way to observe it is against the live API — measured by
        hand on 2026-08-16 and recorded below rather than asserted here.
PROVEN  by ``test_the_refresh_can_fail``.

The measurement, against the real Path Wars group. The bot is a group
administrator with ``can_delete_messages = True``, and it still cannot
delete its own messages once they are older than 48 hours:

    deleted when older than 48h -> 15 of 15 still exist
    deleted when younger        ->  0 of 12 still exist

No exceptions in either direction. So an orphan is not caused by a
delete going wrong; it is caused by the message being **allowed to grow
old while the bot was still holding its ID**. The fingerprint early
return did exactly that: a quiet campaign left its pinned queue post
untouched for days, and by the time a player posted and the fingerprint
moved, the delete was already unwinnable.

This is the fix for the cause. ``test_delete_can_actually_fail.py`` is
the fix for the reporting — both are needed, because the reporting is
what makes the next occurrence visible instead of silent.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from scheduled import topic_queue_write as tqw
from scheduled.topic_queue_write import _batch_is_stale, _post_thread_queue

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
GROUP = -1001661053273
THREAD = "40585"


def _slot(hours_old: float | None, msg_ids=(172195,), fingerprint="fp"):
    stamp = None if hours_old is None else (
        NOW - timedelta(hours=hours_old)).isoformat()
    return {"msg_ids": list(msg_ids), "fingerprint": fingerprint,
            "last_posted_at": stamp}


# ── The staleness rule ───────────────────────────────────────────────────────

@pytest.mark.parametrize("hours,expected", [
    (0, False),
    (12, False),
    (35.9, False),
    (36.1, True),
    (47, True),      # still deletable, which is the entire point of 36h
    (72, True),
])
def test_staleness_threshold(hours, expected):
    """36h leaves 12 hours of slack before Telegram's wall at 48."""
    assert _batch_is_stale(_slot(hours), NOW) is expected


def test_threshold_sits_safely_inside_the_telegram_limit():
    """The margin is the safety property — assert it, don't assume it."""
    assert tqw._MAX_TRACKED_AGE < timedelta(hours=48)
    assert timedelta(hours=48) - tqw._MAX_TRACKED_AGE >= timedelta(hours=6), (
        "too little slack: one missed run must not push a tracked message "
        "past the point where it can never be deleted")


def test_missing_timestamp_is_not_stale():
    """Legacy slots predate last_posted_at. Failing closed would
    republish every one of them at once on the first run after deploy."""
    assert _batch_is_stale(_slot(None), NOW) is False
    assert _batch_is_stale({}, NOW) is False


def test_unparseable_timestamp_is_not_stale():
    assert _batch_is_stale({"last_posted_at": "not a date"}, NOW) is False


def test_naive_timestamp_is_treated_as_utc():
    """State written before tz-awareness must not crash the poster."""
    naive = (NOW - timedelta(hours=72)).replace(tzinfo=None).isoformat()
    assert _batch_is_stale({"last_posted_at": naive}, NOW) is True


# ── What the poster does with it ─────────────────────────────────────────────

def _run(slot, entries=None):
    """Drive _post_thread_queue with all Telegram calls mocked."""
    entries = entries if entries is not None else [{"message_id": 1}]
    with patch.object(tqw, "build_topic_fingerprint", return_value="fp"), \
            patch.object(tqw, "format_topic_queue", return_value=["text"]), \
            patch.object(tqw, "retry_pending_deletes"), \
            patch.object(tqw, "post_batch") as post, \
            patch.object(tqw.tg, "unpin_message"), \
            patch.object(tqw.tg, "delete_message", return_value=True):
        post.return_value = None
        _post_thread_queue(GROUP, THREAD, slot, entries, NOW)
        return post


def test_young_unchanged_queue_is_left_alone():
    """The early return must survive — this is the common case by far."""
    assert _run(_slot(2)).call_count == 0


def test_stale_unchanged_queue_is_reposted():
    """The bug. Unchanged content used to mean 'skip forever'."""
    assert _run(_slot(40)).call_count == 1


def test_age_refresh_is_silent():
    """Players must not be pinged for a message they have already read."""
    post = _run(_slot(40))
    assert post.call_args.kwargs["disable_notification"] is True


def test_real_content_change_still_notifies():
    """The positive counterpart — silencing everything would be a
    different bug, and one nobody would notice for weeks."""
    post = _run(_slot(2, fingerprint="something-else"))
    assert post.call_count == 1
    assert post.call_args.kwargs["disable_notification"] is False


def test_stale_queue_deletes_the_old_batch_first():
    """A refresh that posts without deleting doubles the orphan problem."""
    slot = _slot(40)
    with patch.object(tqw, "build_topic_fingerprint", return_value="fp"), \
            patch.object(tqw, "format_topic_queue", return_value=["t"]), \
            patch.object(tqw, "retry_pending_deletes"), \
            patch.object(tqw, "post_batch", return_value=None), \
            patch.object(tqw.tg, "unpin_message"), \
            patch.object(tqw.tg, "delete_message", return_value=True) as dele:
        _post_thread_queue(GROUP, THREAD, slot, [{"message_id": 1}], NOW)
    assert 172195 in [c.args[1] for c in dele.call_args_list]


def test_empty_slot_still_posts():
    """Nothing tracked means nothing to age out — post as normal."""
    assert _run(_slot(2, msg_ids=())).call_count == 1


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_refresh_can_fail(monkeypatch):
    """Restore the pre-fix behaviour and confirm the guard goes red.

    Before this change the early return consulted only the fingerprint.
    Setting the threshold beyond any real age reproduces that exactly:
    the stale queue is skipped, which is the orphan being created.
    """
    monkeypatch.setattr(tqw, "_MAX_TRACKED_AGE", timedelta(days=3650))
    assert _run(_slot(40)).call_count == 0, (
        "With an unreachable threshold the stale post must be skipped. If "
        "this fails, _post_thread_queue no longer consults _batch_is_stale "
        "and test_stale_unchanged_queue_is_reposted proves nothing.")
