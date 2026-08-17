"""The recruit advert goes to the campaign that needs players.

COVERS  ``recruit_focus.recruit_destination``, the routing in
        ``post_recruit_focus``, and the retirement sweep that takes a
        stale advert down while it still can be taken down.
MISSES  whether the wording suits a player audience rather than the GM.
        It was written for the GM queue and still says "Recruit for this
        next", which is an instruction to Lewis. Flagged for him.
PROVEN  by ``test_the_routing_guard_can_fail``.

────────────────────────────────────────────────────────────────────────

Lewis, 2026-08-17: the post about C09 should go to **C09's chat topic**,
not the GM queue. Telling the people already at a table that it has empty
seats is what recruits; the GM queue is read by one person who already
knows.

⭐ The destination therefore changes per post, because the neediest
campaign changes. ``build_recruit_message`` now returns the campaign
alongside the words for exactly that reason: a bare string names its
campaign only in prose, so the caller would have to run the selection a
second time and hope both runs agreed.

⚠️ Unlike the schedule post's move, the delete needs no extra bookkeeping:
message ids are unique per CHAT, not per topic, and every campaign topic
is in the same group. The old advert is found wherever it sat.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

# ⚠️ Patch where the function LIVES, not where it is re-exported.
# post_recruit_focus moved to recruit_focus_post on 2026-08-17 and is
# re-exported from recruit_focus so the scheduler's import path keeps
# resolving — but it reads its OWN module globals, so patching
# recruit_focus.build_recruit_message has no effect on it at all. The
# re-export preserves the import, never the patch target.
from scheduled import recruit_focus_post as rf
from scheduled.recruit_focus_post import recruit_destination

NOW = datetime(2026, 8, 17, 6, 34, tzinfo=timezone.utc)
GROUP = -1001661053273
GM_QUEUE = 146780
C09_CHAT = 104202


def _cfg(**over):
    cfg = {"group_id": GROUP, "gm_queue_topic_id": GM_QUEUE,
           "group_username": "Path_Wars"}
    cfg.update(over)
    return cfg


def _c09(**over):
    pair = {"code": "C09", "name": "Metal City", "chat_topic_id": C09_CHAT,
            "pbp_topic_ids": [107171], "emoji": "🤖"}
    pair.update(over)
    return pair


# ── Where it goes ────────────────────────────────────────────────────────────

def test_it_goes_to_the_campaigns_own_chat_topic():
    """The whole request: the C09 advert lands in C09's chat."""
    thread, own = recruit_destination(_c09(), _cfg())
    assert (thread, own) == (C09_CHAT, True)
    assert thread != GM_QUEUE


def test_a_campaign_without_a_chat_topic_falls_back_but_says_so():
    """A silent fallback would put the post back where it started and
    look like it worked — and the campaign nobody can see is precisely
    the one that needed the advert."""
    thread, own = recruit_destination(_c09(chat_topic_id=None), _cfg())
    assert (thread, own) == (GM_QUEUE, False)


def test_the_fallback_is_reported_out_loud(capsys):
    state = {}
    with patch.object(rf, "build_recruit_message",
                      return_value=("text", _c09(chat_topic_id=None))), \
            patch.object(rf.tg, "send_message_id", return_value=9), \
            patch.object(rf.tg, "delete_message"):
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    out = capsys.readouterr().out
    assert "no chat_topic_id" in out and "C09" in out


def test_a_string_topic_id_is_accepted():
    """Config has been hand-edited before; a quoted number must not
    become a string thread_id that Telegram rejects."""
    thread, _own = recruit_destination(_c09(chat_topic_id="104202"), _cfg())
    assert thread == C09_CHAT and isinstance(thread, int)


# ── Posting ──────────────────────────────────────────────────────────────────

def _post(state, pair=None, text="advert"):
    with patch.object(rf, "build_recruit_message",
                      return_value=(text, pair if pair is not None else _c09())), \
            patch.object(rf.tg, "send_message_id", return_value=999) as send, \
            patch.object(rf.tg, "delete_message", return_value=True) as dele:
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    return send, dele


def test_the_advert_is_sent_to_the_campaign_thread():
    send, _dele = _post({})
    send.assert_called_once_with(GROUP, C09_CHAT, "advert", silent=True)


def test_the_previous_advert_is_deleted_wherever_it_sat():
    """Message ids are unique per chat, so the old post is found even
    though it is in another campaign's topic entirely."""
    _send, dele = _post({rf._MSG_KEY: 500})
    dele.assert_called_once_with(GROUP, 500)


def test_it_records_when_it_posted():
    state = {}
    _post(state)
    assert state[rf._AT_KEY] == NOW.isoformat()
    assert state[rf._MSG_KEY] == 999


def test_a_failed_send_keeps_the_old_advert():
    state = {rf._MSG_KEY: 500}
    with patch.object(rf, "build_recruit_message",
                      return_value=("advert", _c09())), \
            patch.object(rf.tg, "send_message_id", return_value=None), \
            patch.object(rf.tg, "delete_message") as dele:
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    dele.assert_not_called()
    assert state[rf._MSG_KEY] == 500


# ── Retiring a stale advert ──────────────────────────────────────────────────

def test_a_stale_advert_comes_down_when_nothing_is_recruiting():
    """"4 seats open" in a campaign that filled up is simply false.

    ⚠️ And it has to come down inside 48h: past that Telegram refuses to
    let the bot delete its own message, and the lie becomes permanent.
    """
    state = {rf._MSG_KEY: 500,
             rf._AT_KEY: (NOW - timedelta(hours=30)).isoformat()}
    with patch.object(rf, "build_recruit_message", return_value=("", None)), \
            patch.object(rf.tg, "delete_message", return_value=True) as dele:
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    dele.assert_called_once_with(GROUP, 500)
    assert state[rf._MSG_KEY] is None


def test_a_just_posted_advert_is_left_alone():
    """The positive counterpart. Retiring unconditionally would delete an
    advert minutes after posting it, and no test above would notice."""
    state = {rf._MSG_KEY: 500, rf._AT_KEY: NOW.isoformat()}
    with patch.object(rf, "build_recruit_message", return_value=("", None)), \
            patch.object(rf.tg, "delete_message") as dele:
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    dele.assert_not_called()
    assert state[rf._MSG_KEY] == 500


def test_nothing_to_retire_is_not_an_error():
    state = {}
    with patch.object(rf, "build_recruit_message", return_value=("", None)), \
            patch.object(rf.tg, "delete_message") as dele:
        rf.post_recruit_focus(_cfg(), state, now=NOW)
    dele.assert_not_called()


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_routing_guard_can_fail():
    """Restore the old destination and confirm the routing test would go
    red. Before this change every advert went to the GM queue."""
    thread, _own = recruit_destination(_c09(chat_topic_id=None), _cfg())
    assert thread == GM_QUEUE, (
        "with no chat topic the post must fall back to the GM queue — if "
        "this fails, test_it_goes_to_the_campaigns_own_chat_topic is not "
        "distinguishing the two destinations at all")


def test_state_declares_the_new_key():
    from state_schema import DEFAULT_STATE, PARTITIONS
    assert "recruit_focus_at" in PARTITIONS["live"]
    assert "recruit_focus_at" in DEFAULT_STATE
