"""An "All caught up" notice must be removed while it still can be.

COVERS  ``scheduled.topic_queue_age.caught_up_is_stale`` and
        ``scheduled.topic_queue_write.sweep_aged_caught_up``, plus the
        branch in ``topic_queue_poster.post_topic_queues`` that reaches a
        slot holding only a notice.
MISSES  whether the notice is worth posting at all. That is a product
        question, not a lifecycle one.
PROVEN  by ``test_the_sweep_can_fail``.

────────────────────────────────────────────────────────────────────────

The gap this closes. A caught-up notice was only ever deleted when its
thread next had something to queue. In a quiet campaign that can be
weeks — and Telegram will not let a bot delete its own message after 48
hours, so by then it is permanent.

Nothing in the repo could see this. ``pin_audit`` records pin / unpin /
delete, and a caught-up notice is never pinned, so it had no recorded
birth and no age. The offline detector
(``test_no_delete_attempted_past_the_wall.py``) is structurally blind to
it. It was found by ``maintenance/audit_orphans.py`` asking Telegram
directly: **28 orphans, of which 15 were caught-up notices** — 169063,
169383, 170384 and 171632 among them.

⭐ The lesson worth keeping is not about notices. It is that **a message
ID with no recorded send time has no observable lifetime**, and anything
with no observable lifetime will eventually outlive the window in which
you could act on it.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from scheduled import topic_queue_age as tqa
from scheduled import topic_queue_write as tqw
from scheduled.topic_queue_age import caught_up_is_stale
from scheduled.topic_queue_write import sweep_aged_caught_up

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
GROUP = -1001661053273


def _slot(hours_old=None, mid=170384, stamped=True):
    slot = {"msg_ids": [], "fingerprint": "", "caught_up_msg_id": mid}
    if mid and stamped:
        slot["caught_up_at"] = (
            NOW - timedelta(hours=hours_old or 0)).isoformat()
    return slot


# ── When a notice counts as expired ──────────────────────────────────────────

@pytest.mark.parametrize("hours,expected", [
    (0, False), (12, False), (35.9, False), (36.1, True), (100, True),
])
def test_staleness_follows_the_same_clock_as_the_queue(hours, expected):
    """One rule for every tracked message, not a second bespoke one."""
    assert caught_up_is_stale(_slot(hours), NOW) is expected


def test_a_slot_with_no_notice_is_never_stale():
    assert caught_up_is_stale({"caught_up_msg_id": None}, NOW) is False
    assert caught_up_is_stale({}, NOW) is False


def test_an_untimestamped_notice_counts_as_stale():
    """Deliberately the OPPOSITE default to batch_is_stale.

    A batch with no timestamp is rewritten by the next content change
    anyway. A notice with no timestamp is only revisited when its thread
    wakes up, which may be never — so it gets its one attempt now, while
    that attempt can still succeed.
    """
    assert caught_up_is_stale(_slot(stamped=False), NOW) is True
    assert tqa.batch_is_stale({"last_posted_at": None}, NOW) is False


# ── What the sweep does ──────────────────────────────────────────────────────

def test_expired_notice_is_deleted_and_forgotten():
    slot = _slot(40)
    with patch.object(tqw.tg, "delete_message", return_value=True) as dele:
        assert sweep_aged_caught_up(GROUP, slot, NOW) is True
    dele.assert_called_once_with(GROUP, 170384)
    assert slot["caught_up_msg_id"] is None
    assert slot["caught_up_at"] is None


def test_young_notice_is_left_alone():
    """The positive counterpart. Sweeping everything would delete the
    notice moments after posting it, which no test above would catch."""
    slot = _slot(2)
    with patch.object(tqw.tg, "delete_message") as dele:
        assert sweep_aged_caught_up(GROUP, slot, NOW) is False
    dele.assert_not_called()
    assert slot["caught_up_msg_id"] == 170384


def test_failed_delete_is_parked_for_retry():
    """A notice already past the wall must not vanish silently — it is a
    real message still in the topic and someone has to know."""
    slot = _slot(40)
    with patch.object(tqw.tg, "delete_message", return_value=False):
        sweep_aged_caught_up(GROUP, slot, NOW)
    assert slot["pending_delete"] == [170384]
    assert slot["caught_up_msg_id"] is None


def test_sweep_is_idempotent():
    slot = _slot(40)
    with patch.object(tqw.tg, "delete_message", return_value=True):
        assert sweep_aged_caught_up(GROUP, slot, NOW) is True
        assert sweep_aged_caught_up(GROUP, slot, NOW) is False


# ── The notice is stamped when it is created ─────────────────────────────────

def test_clearing_a_thread_stamps_the_new_notice():
    """Without the stamp the notice has no age and the sweep is blind.

    This is the whole defect in one assertion: every orphaned notice was
    one that nothing could date.
    """
    slot = {"msg_ids": [7777], "fingerprint": "fp"}
    with patch.object(tqw, "retry_pending_deletes"), \
            patch.object(tqw, "build_caught_up_text", return_value="ok"), \
            patch.object(tqw.tg, "send_message_id", return_value=8888), \
            patch.object(tqw.tg, "unpin_message"), \
            patch.object(tqw.tg, "delete_message", return_value=True):
        tqw._clear_thread_queue(GROUP, "40585", slot, pid="40585",
                                state=None, config={}, now=NOW)
    assert slot["caught_up_msg_id"] == 8888
    assert slot["caught_up_at"] == NOW.isoformat()
    assert caught_up_is_stale(slot, NOW) is False
    assert caught_up_is_stale(slot, NOW + timedelta(hours=40)) is True


# ── The poster actually reaches a notice-only slot ───────────────────────────

def test_poster_sweeps_a_slot_holding_only_a_notice():
    """Before the fix this slot matched no branch at all, so nothing ever
    looked at it again — which is precisely how the notices aged out."""
    from scheduled import topic_queue_poster as tqp
    cq = {"topic_queues": {"40585": _slot(40)}}
    with patch.object(tqp, "_load", return_value=cq), \
            patch.object(tqp, "_save") as save, \
            patch.object(tqp, "_all_pids", return_value=["40585"]), \
            patch.object(tqp, "_migrate_legacy"), \
            patch.object(tqp, "_group_id_for", return_value=GROUP), \
            patch.object(tqp.time, "sleep"), \
            patch.object(tqw.tg, "delete_message", return_value=True) as dele:
        tqp.post_topic_queues({}, {}, NOW)
    dele.assert_called_once_with(GROUP, 170384)
    save.assert_called_once()


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_sweep_can_fail(monkeypatch):
    """Push the threshold out of reach — the old behaviour — and confirm
    the expired notice survives, which is the orphan being created."""
    monkeypatch.setattr(tqa, "MAX_TRACKED_AGE", timedelta(days=3650))
    slot = _slot(100)
    with patch.object(tqw.tg, "delete_message") as dele:
        assert sweep_aged_caught_up(GROUP, slot, NOW) is False
    dele.assert_not_called()
    assert slot["caught_up_msg_id"] == 170384, (
        "With an unreachable threshold the notice must survive. If this "
        "fails, sweep_aged_caught_up no longer consults the clock and the "
        "tests above prove nothing.")
