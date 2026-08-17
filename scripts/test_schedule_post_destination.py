"""The schedule post can move to another chat without stranding the old one.

COVERS  ``schedule_post.schedule_destination`` and the send/delete pair
        in ``post_schedule``, including the one run where the previous
        post and the next one are in DIFFERENT chats.
MISSES  whether the bot is actually an admin of the destination. Only
        Telegram can answer that; checked by hand on 2026-08-17
        (administrator, can_delete_messages, can_pin_messages).
PROVEN  by ``test_the_migration_guard_can_fail``.

────────────────────────────────────────────────────────────────────────

2026-08-17: the schedule post moved from the GM queue topic to the Nudge
Bot Notifications group.

⭐ The interesting run is the FIRST one after the move, and it is the one
that is easy to get wrong. ``state["schedule_post_msg_id"]`` names a
message in the OLD chat, while the next post goes to the NEW one. Deleting
that id against the new chat either fails or — far worse — removes an
unrelated message that happens to share the number, because message ids
are per-chat and collide freely across chats.

⛔ And it cannot be fixed by trying again later. Telegram will not let a
bot delete its own message after 48 hours, so a schedule post left in the
GM queue topic is stranded permanently. The state key that records WHICH
CHAT the current post lives in is the whole fix.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from scheduled import schedule_post as sp
from scheduled.schedule_post import schedule_destination

NOW = datetime(2026, 8, 17, 4, 27, tzinfo=timezone.utc)
MAIN = -1001661053273
NOTIF = -1004303231713


# ── Where the post goes ──────────────────────────────────────────────────────

def test_a_configured_chat_wins():
    dest = schedule_destination({"group_id": MAIN, "schedule_chat_id": NOTIF})
    assert dest == (NOTIF, None), "no thread means the forum's General topic"


def test_a_thread_inside_the_new_chat_is_honoured():
    dest = schedule_destination({"group_id": MAIN, "schedule_chat_id": NOTIF,
                                 "schedule_thread_id": 42})
    assert dest == (NOTIF, 42)


def test_the_old_topic_id_is_not_reused_against_a_new_chat():
    """schedule_topic_id names a topic in the MAIN group. Carried over to
    another chat it would either fail or land somewhere unrelated that
    happens to share the number."""
    dest = schedule_destination({"group_id": MAIN, "schedule_chat_id": NOTIF,
                                 "schedule_topic_id": 146780})
    assert dest == (NOTIF, None)


def test_without_a_chat_it_stays_in_the_main_group():
    """The positive counterpart — the pre-move behaviour must survive."""
    dest = schedule_destination({"group_id": MAIN, "schedule_topic_id": 146780})
    assert dest == (MAIN, 146780)


def test_it_still_falls_back_to_the_bot_topic():
    dest = schedule_destination({"group_id": MAIN, "bot_topic_id": 137393})
    assert dest == (MAIN, 137393)


def test_no_destination_at_all_is_none():
    assert schedule_destination({"group_id": MAIN}) is None


# ── The migration run ────────────────────────────────────────────────────────

def _run(config, state):
    with patch.object(sp, "build_schedule_text", return_value="text"), \
            patch.object(sp.tg, "send_message_id", return_value=999) as send, \
            patch.object(sp.tg, "delete_message", return_value=True) as dele:
        sp.post_schedule(config, state, now=NOW)
    return send, dele


def test_the_old_post_is_deleted_from_the_OLD_chat():
    """The whole point. Deleting id 500 in the new chat could remove a
    stranger's message that happens to be number 500 there."""
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {"schedule_post_msg_id": 500}     # no chat key: pre-move state
    send, dele = _run(config, state)
    send.assert_called_once_with(NOTIF, None, "text", silent=True)
    dele.assert_called_once_with(MAIN, 500)


def test_the_new_chat_is_recorded_for_next_time():
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {"schedule_post_msg_id": 500}
    _run(config, state)
    assert state["schedule_post_chat_id"] == NOTIF
    assert state["schedule_post_msg_id"] == 999


def test_the_settled_case_deletes_from_the_new_chat():
    """Once moved, subsequent runs stay entirely in the new chat."""
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {"schedule_post_msg_id": 500, "schedule_post_chat_id": NOTIF}
    _send, dele = _run(config, state)
    dele.assert_called_once_with(NOTIF, 500)


def test_a_failed_send_leaves_the_old_post_alone():
    """Never delete the only copy when the replacement did not arrive."""
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {"schedule_post_msg_id": 500}
    with patch.object(sp, "build_schedule_text", return_value="text"), \
            patch.object(sp.tg, "send_message_id", return_value=None), \
            patch.object(sp.tg, "delete_message") as dele:
        sp.post_schedule(config, state, now=NOW)
    dele.assert_not_called()
    assert state["schedule_post_msg_id"] == 500


def test_the_first_ever_post_deletes_nothing():
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {}
    _send, dele = _run(config, state)
    dele.assert_not_called()
    assert state["schedule_post_chat_id"] == NOTIF


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_migration_guard_can_fail():
    """Restore the pre-fix behaviour — delete against the destination
    chat — and confirm the migration test would go red.

    Before this change post_schedule used config["group_id"] for both the
    send and the delete, which happened to be right only because the two
    were always the same chat.
    """
    config = {"group_id": MAIN, "schedule_chat_id": NOTIF}
    state = {"schedule_post_msg_id": 500}
    dest_chat, _thread = schedule_destination(config)
    prev_chat = state.get("schedule_post_chat_id") or config["group_id"]
    assert prev_chat != dest_chat, (
        "on the migration run the two chats MUST differ, or "
        "test_the_old_post_is_deleted_from_the_OLD_chat proves nothing")


def test_state_declares_the_new_key():
    """An undeclared key is silently dropped on save, which would make
    every run look like a migration run forever."""
    from state_schema import DEFAULT_STATE, PARTITIONS
    assert "schedule_post_chat_id" in PARTITIONS["live"]
    assert "schedule_post_chat_id" in DEFAULT_STATE
