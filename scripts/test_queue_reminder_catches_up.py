"""The daily GM queue reminder: when it posts, and when it stays quiet.

Split from ``test_core_scheduled.py`` on 2026-09-06, which reached 224
lines when the catch-up tests landed.

⛔ The behaviour these pin was silently broken for a fortnight. The
reminder fired only when a run landed in one of ``queue_daily_hours``
exactly; GitHub delivers about 27% of the cron, so **10 of 28 daily
slots went unposted** in the two weeks to 2026-09-04, both slots on
three separate days. Nothing reported it, because two configured hours
instead of one meant it half-worked.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from scheduled.queue_reminder import post_queue_reminder
from test_core_scheduled import _qr_config


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts", return_value={})
def test_queue_reminder_no_entries_no_post(mock_scan, mock_ptq):
    state = {"last_queue_fingerprint": None, "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    post_queue_reminder(_qr_config(), state, now=now)


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts")
def test_queue_reminder_same_fingerprint_skips(mock_scan, mock_ptq):
    # ⚠️ The 09 slot is marked ALREADY POSTED. Before 2026-09-06 this
    # test used hour 10 with no slots posted and relied on 10 not being
    # in [9, 21]; catch-up made that a due slot, correctly. What the
    # test is actually for is the FINGERPRINT gate, so the daily slot
    # has to be satisfied rather than merely mistimed.
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi", "link": "", "message_id": "1"}]
    mock_scan.return_value = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    # Fingerprint format: "{pid}:{time}" joined by "|"
    fp = f"100:{t}"
    state = {"last_queue_fingerprint": fp, "queue_post_count": 0,
             "last_queue_pin_id": None,
             "last_queue_daily_slots": ["2026-04-03:09"]}
    post_queue_reminder(_qr_config(), state, now=now)
    # Fingerprint matched and the daily slot is done → skipped
    assert state["queue_post_count"] == 0


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts")
def test_queue_reminder_catches_up_a_missed_daily_slot(mock_scan, mock_ptq):
    """⭐⭐ Can-fail counterpart, and the 2026-09-06 fix itself.

    Same hour, same unchanged fingerprint as the test above; the only
    difference is that the 09:00 slot was never posted. GitHub delivers
    ~27% of the cron, so a run landing exactly in hour 09 is a coin
    toss - 10 of 28 slots were missed in the fortnight to 2026-09-04.
    The first run at or after the hour must fill it.
    """
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi", "link": "", "message_id": "1"}]
    mock_scan.return_value = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": f"100:{t}", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    post_queue_reminder(_qr_config(), state, now=now)
    assert state["queue_post_count"] == 1, "the missed 09:00 slot was not caught up"
    # ⚠️ Filed under the SLOT it fills, not the wall clock. Keyed on
    # now.hour it would record a 10:00 slot nobody asked for and leave
    # 09:00 due for ever.
    assert state["last_queue_daily_slots"] == ["2026-04-03:09"]


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts")
def test_queue_reminder_posts_on_change(mock_scan, mock_ptq):
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi", "link": "", "message_id": "1"}]
    mock_scan.return_value = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    post_queue_reminder(_qr_config(), state, now=now)
    assert state["queue_post_count"] == 1

# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/potw.py — guard conditions
# ═══════════════════════════════════════════════════════════════════════════════
