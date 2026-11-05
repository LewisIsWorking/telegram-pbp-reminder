"""The GM queue footer splits into two messages when it names two campaigns.

Lewis, 2026-11-05: "Could these messages be 2 split messages when they are 2
different campaigns but 1 unified message when they are the same campaign?"

The priority pick ("Post here next" / "Reply to this next") and the oldest
post waiting go out as two Telegram messages when they are in different
campaigns, and as one when they are in the same one. The second message is
part of the queue's own batch, so it is edited and evicted with it.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from _test_queue_post_fakes import faithful_post_and_persist
from commands.queue_format import build_priority_map
from scheduled import queue_reminder
from scheduled.queue_focus import OLDEST_LABEL, SAME_POST_LINE, build_focus_message
from scheduled.queue_followup import followup_messages
from scheduled.queue_refresh import refresh_in_place

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
KIBWE = {"name": "Kibwe", "code": "C06", "emoji": "🦠", "pbp_topic_ids": [40585],
         "queue_priority": 0, "queue_always_first": True}
C04 = {"name": "Magni Guard", "code": "C04", "emoji": "🛡", "pbp_topic_ids": [144765]}
C07 = {"name": "Hopeful End-Times", "code": "C07", "emoji": "⭐", "pbp_topic_ids": [52083]}
CONFIG = {"group_id": -100, "bot_topic_id": 999, "gm_user_ids": [1],
          "topic_pairs": [KIBWE, C04, C07]}
C04_LINK = "https://t.me/Path_Wars/144765/190001"


def _at(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def _scanned():
    return {
        "144765": {"code": "C04", "campaign": "Magni Guard", "entries": [
            {"time": _at(20 * 24), "name": "Mira", "preview": "We hold the gate",
             "message_id": "190001", "link": C04_LINK}]},
        "52083": {"code": "C07", "campaign": "Hopeful End-Times", "entries": [
            {"time": _at(3 * 24), "name": "Terra", "preview": "I don't trust that",
             "message_id": "190500", "link": "https://t.me/Path_Wars/52083/190500"}]},
    }


def _state(kibwe_quiet_hours):
    ago = (NOW - timedelta(hours=kibwe_quiet_hours)).isoformat()
    recent = (NOW - timedelta(hours=1)).isoformat()
    return {"topics": {"40585": {"last_message_time": ago},
                       "144765": {"last_message_time": recent},
                       "52083": {"last_message_time": recent}}}


def _footer(scanned, state):
    return followup_messages(CONFIG, state, scanned, build_priority_map(CONFIG), NOW)


def test_two_campaigns_make_two_messages():
    """Kibwe quiet is the pick, C04's post is the oldest: two messages."""
    msgs = _footer(_scanned(), _state(kibwe_quiet_hours=25))
    assert len(msgs) == 2, msgs
    pick, oldest = msgs
    assert "🎯 Post here next" in pick and "C06: Kibwe" in pick
    assert OLDEST_LABEL not in pick and "C04" not in pick
    assert oldest.startswith(OLDEST_LABEL), oldest
    assert "🛡 C04: Magni Guard" in oldest and "Mira" in oldest
    assert C04_LINK in oldest


def test_the_same_campaign_stays_one_message():
    msgs = _footer(_scanned(), _state(kibwe_quiet_hours=1))
    assert len(msgs) == 1, msgs
    assert "Reply to this next" in msgs[0] and "C04: Magni Guard" in msgs[0]
    assert SAME_POST_LINE in msgs[0]


def test_split_texts_join_back_into_the_unified_focus():
    """The DM still gets one message, with the same words in it."""
    state = _state(kibwe_quiet_hours=25)
    msgs = _footer(_scanned(), state)
    assert "\n".join(msgs) == build_focus_message(
        CONFIG, _scanned(), build_priority_map(CONFIG), NOW, state=state)


def test_no_oldest_post_is_one_message():
    msgs = _footer({}, _state(kibwe_quiet_hours=30))
    assert len(msgs) == 1 and "C06: Kibwe" in msgs[0]
    assert OLDEST_LABEL not in msgs[0]


def test_nothing_to_point_at_is_no_message():
    assert followup_messages({"topic_pairs": []}, {}, {}, {}, NOW) == []


def _post(state):
    sent = []

    def fake(st, group_id, topic, msgs, **kw):
        sent.append(list(msgs))
        return faithful_post_and_persist(st, group_id, topic, msgs)

    with patch.object(queue_reminder, "scan_transcripts", return_value=_scanned()), \
         patch.object(queue_reminder, "drop_deleted", side_effect=lambda c, s, sc, n: sc), \
         patch.object(queue_reminder, "post_topic_queues"), \
         patch.object(queue_reminder, "send_focus_dm", return_value=False), \
         patch.object(queue_reminder, "post_and_persist", side_effect=fake):
        queue_reminder.post_queue_reminder(CONFIG, state, now=NOW)
    return sent


def test_the_queue_post_carries_both_messages_in_its_batch():
    state = _state(kibwe_quiet_hours=25)
    batch = _post(state)[0]
    assert "Post here next" in batch[-2] and batch[-1].startswith(OLDEST_LABEL)
    # Tracked with the queue, so it is edited and evicted with it.
    assert len(state["gm_queue_history"][-1]["msg_ids"]) == len(batch)
    assert state["gm_queue_texts"] == batch


def test_a_split_that_goes_away_reposts_rather_than_orphaning():
    """Two footer messages last time, one now: the refresh must not pair the
    texts by index (that would leave the old oldest-waiting message behind).
    It declines, and the repost evicts the whole old batch."""
    state = {"gm_queue_history": [{"msg_ids": [1, 2, 3], "pin_id": 1}],
             "gm_queue_texts": ["queue", "pick", "oldest"]}
    edits = []
    assert not refresh_in_place(state, -100, ["queue", "pick + same post"],
                                edit=lambda *a, **k: edits.append(a) or True)
    assert edits == []
