"""A post outside every campaign topic is recorded and gets the link nudge.

Added 2026-10-08: KP asked for a C00 sheet in the group, not in an RP or
combat topic, and the bot dropped every post, so he was never told to link
COO and COO had no record that would let him.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from players import group_members  # noqa: E402

CONFIG = {"group_id": -100, "gm_user_ids": ["9"]}
MAPS = SimpleNamespace(to_chat={})


def _msg(sender=None, chat=-100, text="i request a character sheet", thread=77):
    return {"chat": {"id": chat}, "message_thread_id": thread, "date": 1791460800,
            "text": text,
            "from": sender if sender is not None else
            {"id": 7, "first_name": "KP", "username": "kp"}}


def _post(msg, state, linked=frozenset()):
    with patch.object(group_members.coo_link.tg, "send_message",
                      return_value=True) as send:
        sent = group_members.on_group_post(msg, CONFIG, state, MAPS,
                                           linked=lambda: set(linked))
    return sent, send


def test_a_group_post_is_recorded_and_nudged_in_its_own_topic():
    state = {}
    sent, send = _post(_msg(), state)
    assert sent
    assert send.call_args.args[:2] == (-100, 77)
    assert "@kp" in send.call_args.args[2]
    member = state["group_members"]["7"]
    assert member["name"] == "KP" and member["username"] == "kp"
    assert member["last"].startswith("2026-10-08")


def test_a_linked_member_is_recorded_but_not_nudged():
    state = {}
    assert _post(_msg(), state, linked={"7"})[0] is False
    assert "7" in state["group_members"]


def test_other_chats_bots_gms_and_anonymous_posts_are_ignored():
    for msg in (_msg(chat=-5), _msg(sender={"id": 8, "is_bot": True}),
                _msg(sender={"id": 9, "first_name": "GM"}), _msg(sender={})):
        state = {}
        sent, send = _post(msg, state)
        assert sent is False and state == {}
        send.assert_not_called()


def test_a_photo_with_no_date_and_no_name_still_counts():
    msg = _msg(sender={"id": 7}, text=None)
    msg.pop("date")
    msg["caption"] = "my sheet?"
    state = {}
    assert _post(msg, state)[0]
    assert state["group_members"]["7"]["name"] == "7"
