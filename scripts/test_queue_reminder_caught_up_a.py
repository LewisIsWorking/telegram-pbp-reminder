"""Tests for the 'All caught up!' branch in scheduled/queue_reminder.py.

Covers the empty-queue branch at queue_reminder.py:73-77 — previously
marked ``# pragma: no cover`` because no test exercised it. The
branch fires when:

  1. ``scanned`` has at least one campaign (so we got past the
     'nothing scanned' early return), but
  2. The total number of unreplied entries across all campaigns is 0,
     and
  3. There are no silent campaigns to display.

Sub-cases covered in this file (line-73 DEFENSIVE path — scanner
returns campaigns with empty entries lists, which the production
scanner does not currently do but might in the future):

  * ``last_queue_fingerprint != "empty"`` — bot posts "All caught up!"
    once, then sets fingerprint to "empty" so subsequent runs don't
    repeat it.
  * ``last_queue_fingerprint == "empty"`` (already marked empty) —
    bot stays silent. Reaching this case requires bypassing the
    duplicate-fingerprint early return at line 65, which only
    happens on a daily-hour run with the slot not yet posted.

Slice 6 of the spam-prevention design (avoid posting the same
'All caught up!' on every cron tick after the queue empties).
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))


def _empty_scanned() -> dict:
    """Scanner result for a campaign that has no unreplied entries.

    The dict is non-empty (so we get past the
    ``not scanned and not silent_lines`` early return at line 68),
    but the ``entries`` list is empty (so ``total == 0`` at line 73).

    Note: the production scanner ``commands.queue_scan.scan_transcripts``
    does NOT actually return this shape — it omits empty campaigns
    entirely (see queue_scan.py:185-197). The ``_no_scanned()``
    helper below produces the shape the production scanner uses
    when every queue is clean. The two shapes hit different early-
    return branches; both are tested.
    """
    return {"100": {"campaign": "Active", "code": "C01", "entries": []}}


def _no_scanned() -> dict:
    """Scanner result the production scanner returns when every
    queue is clean: empty dict, no campaigns at all.

    Hits the line-68 branch (``not scanned and not silent_lines``).
    This is the branch that fires in real production runs.
    """
    return {}


def test_caught_up_message_posted_when_queue_first_empties():
    """When the queue empties (prior fingerprint was non-empty), the
    bot posts a single 'All caught up!' notification and updates the
    fingerprint to 'empty' so it doesn't repeat.

    This is the visible-state-change case: GMs see one post telling
    them they're caught up. Subsequent runs with the queue still
    empty will hit the ``last_queue_fingerprint == 'empty'`` branch
    and stay silent.
    """
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C01", "name": "Active"},
        ],
    }
    state = {
        "last_queue_fingerprint": "100:2026-05-09 12:00:00",  # prior content
        "queue_post_count": 5,
        "last_queue_pin_id": 12345,
        "last_queue_daily_slots": [],
    }

    # 2026-05-12 update: the caught-up path now routes through
    # the _post_caught_up helper (which goes through
    # gm_queue_history.post_and_persist) so the previous GM queue
    # batch gets evicted. Mock the helper directly to verify it's
    # called — testing the deeper post_and_persist chain would
    # duplicate the gm_queue_history tests' coverage.
    with patch("scheduled.queue_reminder.scan_transcripts",
               return_value=_empty_scanned()), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.silent_campaigns",
               return_value=[]), \
         patch("scheduled.queue_reminder._post_caught_up") as mock_caught:
        post_queue_reminder(config, state, now=now)

    # _post_caught_up called exactly once with the right state/group/topic.
    assert mock_caught.call_count == 1, (
        f"Expected one _post_caught_up call, got {mock_caught.call_count}"
    )
    args = mock_caught.call_args[0]
    assert args[0] is state
    assert args[1] == -1001
    assert args[2] == 999

    # Fingerprint flipped to 'empty' so the next run won't re-post.
    assert state["last_queue_fingerprint"] == "empty"


def test_caught_up_silent_when_already_marked_empty():
    """When the queue is empty AND the prior fingerprint was already
    'empty', the bot stays silent. Prevents spamming the topic with
    repeated 'All caught up!' messages on every cron tick.

    Reaching this case requires ``is_daily=True`` to bypass the
    line-65 duplicate-fingerprint early return (since the new
    fingerprint is also 'empty', and a non-daily run with both equal
    would have returned early before reaching the empty-queue branch).
    """
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        # queue_daily_hours includes now.hour AND the slot isn't in
        # last_queue_daily_slots, so is_daily=True at line 59 →
        # bypasses the line-65 fingerprint match.
        "queue_daily_hours": [now.hour],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C01", "name": "Active"},
        ],
    }
    state = {
        "last_queue_fingerprint": "empty",  # already marked empty
        "queue_post_count": 5,
        "last_queue_pin_id": None,
        "last_queue_daily_slots": [],
    }

    captured = []

    def _capture(gid, tid, text):
        captured.append(text)

    with patch("scheduled.queue_reminder.scan_transcripts",
               return_value=_empty_scanned()), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.silent_campaigns",
               return_value=[]), \
         patch("scheduled.queue_reminder.tg.send_message",
               side_effect=_capture), \
         patch("scheduled.queue_reminder.tg.send_message_id",
               return_value=42), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=now)

    # No 'All caught up!' message — we already told them.
    assert captured == [], (
        f"Expected silent re-empty (no message), but got: {captured}"
    )

    # Fingerprint stays 'empty' (overwritten with itself).
    assert state["last_queue_fingerprint"] == "empty"
