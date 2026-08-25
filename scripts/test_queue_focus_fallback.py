"""A cleared queue must still point somewhere.

Lewis, 2026-08-25, on GM queue #1452: *"I got the GM queue cleared BUT
the bot only posted this... And did not post the separate 'the campaign
most in need of activity' message, which in this case would be C05."*

The queue read ``Unreplied: 0`` and listed C05 Grand Explorers as silent
for 5d 19h, and then stopped. No follow-up at all.

## Why

``queue_reminder`` has three exits:

1. ``not scanned and not silent_lines``  -> caught-up post, WITH the
   oldest-campaign callout
2. ``total == 0 and not silent_lines``   -> same
3. everything else                       -> the full queue post

Both callouts live on paths guarded by ``and not silent_lines``. An
empty queue **with** a silent campaign satisfies neither, so it fell
through to (3), where the only follow-up appended was
``build_focus_message`` -- which reads unreplied entries and returns ""
when there are none.

So the pointer vanished exactly when it was most useful: nothing owed a
reply, one campaign had been dead for six days, and the post said
nothing about where to go.

## ⭐ Why the existing tests did not catch it

``test_queue_reminder_posts_when_only_silent`` covers this exact branch.
It asserts the silent SECTION renders. Nobody ever asserted what the
post ends with, so the branch was covered and the behaviour was not.
Coverage answers "did this line run", never "is the output right".

⚠️ The fallback function was not missing. ``oldest_campaign_line`` was
written for this case and says so in its own docstring. It was simply
never called from this path. See ``a-guard-nothing-invokes``: written,
correct, tested, and unreachable are four different things.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime(2026, 8, 25, 10, 42, tzinfo=timezone.utc)

CONFIG = {
    "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
    "queue_daily_hours": [NOW.hour],
    "topic_pairs": [
        {"pbp_topic_ids": [51357], "code": "C05", "name": "Grand Explorers",
         "emoji": "\U0001f52d"},
        {"pbp_topic_ids": [107171], "code": "C09", "name": "Metal City",
         "emoji": "\U0001f916"},
    ],
}


def _state(silent_days=5.8, busy_hours=0):
    return {
        "last_queue_fingerprint": "OLD", "queue_post_count": 0,
        "last_queue_pin_id": None, "last_queue_daily_slots": [],
        "topics": {
            "51357": {"last_message_time":
                      (NOW - timedelta(days=silent_days)).isoformat()},
            "107171": {"last_message_time":
                       (NOW - timedelta(hours=busy_hours)).isoformat()},
        },
    }


def _post(scanned, state):
    from scheduled.queue_reminder import post_queue_reminder
    sent = []
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id",
               side_effect=lambda gid, tid, text: sent.append(text) or 42), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(CONFIG, state, now=NOW)
    return sent


def _entry(hours_ago):
    return {"name": "Player", "preview": "are we doing this",
            "link": "", "message_id": "1",
            "time": (NOW - timedelta(hours=hours_ago)).strftime(
                "%Y-%m-%d %H:%M:%S")}


class TestTheClearedQueueStillPoints:
    def test_an_empty_queue_with_a_silent_campaign_names_it(self):
        # ⭐⭐ The reported bug, reproduced. Before the fix the post ended
        # at the caught-up section.
        combined = "\n".join(_post({}, _state()))
        assert "Oldest campaign" in combined
        assert "C05: Grand Explorers" in combined

    def test_it_says_why_it_is_pointing_there(self):
        # The wording carries the reasoning. "Nothing is waiting on a
        # reply" is what distinguishes this from the reply focus, and
        # without it the two callouts are indistinguishable in the log.
        combined = "\n".join(_post({}, _state()))
        assert "Nothing is waiting on a reply" in combined

    def test_the_callout_comes_last(self):
        # It is a "go here next" instruction, so it belongs after the
        # listing it draws its conclusion from.
        combined = "\n".join(_post({}, _state()))
        assert combined.index("Oldest campaign") > combined.index("Silent campaigns")

    def test_the_longest_idle_campaign_wins_not_the_first_listed(self):
        # ⚠️ C09 is listed first in config. Ranking must be by idle time.
        state = _state(silent_days=1, busy_hours=200)
        combined = "\n".join(_post({}, state))
        assert "C09: Metal City" in combined.split("Oldest campaign")[1]


class TestItDoesNotDisplaceTheReplyFocus:
    def test_a_waiting_reply_still_gets_the_reply_focus(self):
        # ⭐ can-fail counterpart. A fallback that fired unconditionally
        # would replace the more specific message with a vaguer one.
        scanned = {"51357": {"campaign": "Grand Explorers", "code": "C05",
                             "entries": [_entry(30)]}}
        combined = "\n".join(_post(scanned, _state()))
        assert "Reply to this next" in combined

    def test_and_does_not_also_get_the_oldest_callout(self):
        # Two "go here next" instructions in one post is one too many,
        # and they can disagree.
        scanned = {"51357": {"campaign": "Grand Explorers", "code": "C05",
                             "entries": [_entry(30)]}}
        combined = "\n".join(_post(scanned, _state()))
        assert "Oldest campaign" not in combined


class TestTheCaughtUpPathIsUnchanged:
    def test_no_queue_and_no_silence_still_posts_the_callout(self):
        # The path that already worked. Included so a future refactor
        # that unifies these branches cannot quietly drop it: this was
        # the ONLY place the callout was reachable from before today.
        sent = _post({}, _state(silent_days=1, busy_hours=2))
        combined = "\n".join(sent)
        assert "Oldest campaign" in combined
