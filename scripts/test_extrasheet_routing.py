"""/extrasheet reaches its handler from every topic a player would use.

Added 2026-10-12. A campaign's chat topic never reaches _HANDLERS, since
parse_message drops every thread that is not a pbp topic, so this pins
both entry points and the router hook between them. The replies
themselves are tested in test_extrasheet.py.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from dispatch import cmd_extrasheet as xs  # noqa: E402
from dispatch.router import _HANDLERS, process_updates  # noqa: E402
from parsing.message import reply_user  # noqa: E402
from players import extra_sheets  # noqa: E402
from state_store import StateStore  # noqa: E402
from test_extrasheet import CONFIG, MAPS  # noqa: E402
from test_every_command_is_reachable import (  # noqa: E402
    _handled_commands, _menu_commands)

LAI = {"id": 7, "first_name": "Lai", "username": "lai"}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(extra_sheets, "_store", StateStore(state_dir=tmp_path))


def _msg(text="/extrasheet", thread=21528, chat=-100, sender=LAI, reply=None):
    msg = {"message_id": 50, "chat": {"id": chat}, "message_thread_id": thread,
           "date": 1791460800, "text": text, "from": sender}
    if reply:
        msg["reply_to_message"] = reply
    return msg


def _outside(msg):
    with patch.object(xs.tg, "send_message", return_value=True) as send:
        handled = xs.handle_outside(msg, CONFIG, {}, MAPS)
    return handled, send


def test_the_command_word_is_recognised_exactly():
    assert xs.command_args("/extrasheet") == ""
    assert xs.command_args("/ExtraSheet@PathWarsNudgeBot @Lai C06") == "@lai c06"
    for other in ("/extrasheets", "/away", "hello", "", None):
        assert xs.command_args(other) is None


def test_it_is_in_the_menu_and_has_a_handler():
    assert "/extrasheet" in _menu_commands()
    assert "/extrasheet" in _handled_commands()
    assert xs.handle in _HANDLERS


def test_in_a_chat_topic_the_campaign_comes_from_the_topic():
    handled, send = _outside(_msg())
    assert handled
    assert send.call_args.args[:2] == (-100, 21528)
    assert "Lai can make a second character sheet in C06" in send.call_args.args[2]


def test_in_the_bot_topic_the_campaign_must_be_named():
    assert _outside(_msg(thread=999))[1].call_args.args[2] == xs.NOT_IN_TOPIC
    assert "in C08" in _outside(_msg("/extrasheet C08", thread=999))[1].call_args.args[2]


def test_a_chat_topic_id_seen_in_the_wrong_group_names_no_campaign():
    # Elsewhere's chat topic 600 lives in group -200, not -100.
    assert _outside(_msg(thread=600))[1].call_args.args[2] == xs.NOT_IN_TOPIC


def test_the_gm_replying_in_a_chat_topic_grants_the_replied_player():
    reply = {"message_id": 49, "from": {"id": 42, "first_name": "Ana"}}
    send = _outside(_msg("/extrasheet", sender={"id": 1, "first_name": "GM"},
                         reply=reply))[1]
    assert send.call_args.args[2].startswith("✅ Ana can")


@pytest.mark.parametrize("msg", [
    _msg("/away"), _msg(sender={"id": 5, "is_bot": True}), _msg(sender={}),
    _msg(chat=-5), _msg(thread=40585), _msg(thread=137075)])
def test_everything_else_is_left_for_the_rest_of_the_router(msg):
    handled, send = _outside(msg)
    assert handled is False
    send.assert_not_called()


def test_a_forum_topic_header_is_not_a_reply_to_anyone():
    header = {"message_id": 21528, "forum_topic_created": {},
              "from": {"id": 3}}
    assert reply_user(_msg(reply=header)) is None
    assert reply_user(_msg(reply={"message_id": 21528, "from": {"id": 3}})) is None
    assert reply_user(_msg()) is None
    assert reply_user(_msg(reply={"message_id": 49, "from": {"id": 3}})) == {"id": 3}


def test_the_handler_ignores_other_commands():
    assert xs.handle({"text": "/away"}) is False


def _route(msg):
    state = {"offset": 0}
    with patch.object(xs.tg, "send_message", return_value=True) as send, \
         patch("dispatch.router.track_message"), \
         patch("dispatch.router.handle_combat_message"), \
         patch("players.group_members.on_group_post") as group_post:
        process_updates([{"update_id": 1, "message": msg}], CONFIG, state)
    return send, group_post


def test_the_router_answers_in_a_pbp_topic_through_the_handlers():
    send, _ = _route(_msg("/extrasheet", thread=137075))
    assert send.call_args.args[:2] == (-100, 137075)
    assert "Lai can make a second character sheet in C06" in send.call_args.args[2]


def test_the_router_answers_in_a_chat_topic_and_skips_the_group_post_path():
    send, group_post = _route(_msg("/extrasheet"))
    assert send.call_args.args[:2] == (-100, 21528)
    group_post.assert_not_called()
