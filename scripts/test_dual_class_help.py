"""A player asking how to dual class gets the wiki guide, once.

Added 2026-11-26, after Greg asked "I can't figure out a way to dual class"
and Antoine was done explaining it by hand. Lewis: just link the guide.
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from players import dual_class_help as dch  # noqa: E402

CONFIG = {"group_id": -1, "gm_user_ids": [99],
          "topic_pairs": [{"name": "C06", "chat_topic_id": 50,
                           "pbp_topic_ids": [60, 61], "gm_user_ids": [98]}]}
T0 = 1_764_100_000  # a Unix time; the tests only use differences from it


def _msg(text="I can't figure out a way to dual class", user=7, thread=10,
         when=T0, chat=-1, bot=False, username="greg"):
    return {"chat": {"id": chat}, "message_thread_id": thread, "date": when,
            "text": text, "from": {"id": user, "is_bot": bot,
                                   "first_name": "Greg", "username": username}}


def _send(state, msg, config=CONFIG):
    send = MagicMock(return_value=True)
    return dch.maybe_answer(msg, config, state, send=send), send


def test_the_real_question_gets_the_guide_in_the_same_topic():
    sent, send = _send({}, _msg())
    assert sent
    chat, thread, text = send.call_args.args
    assert (chat, thread) == (-1, 10)
    assert "@greg" in text and dch.GUIDE_URL in text


def test_genuine_how_to_questions_match():
    for text in ["How to Dual class", "How do I dual class?", "how to dual-class in foundry",
                 "Where do I set up my dual class", "help with dualclass pls",
                 "No idea how dual classing works", "can someone dual class me?"]:
        assert dch.is_dual_class_question(text), text


def test_chatter_answers_and_the_sheet_check_do_not_match():
    for text in [
        "Ima stop explaining how to dual class and start telling people "
        "there's a guide on the path wars wiki",
        "Ryder: not dual class; 2 boosts unspent",
        "Dual class is great in this campaign",
        "I finally dual classed my wizard!",
        "how do I dual class? https://example.com",
        "/search dual class",
        "How do I level up?",
    ]:
        assert not dch.is_dual_class_question(text), text


def test_bots_and_other_chats_are_ignored_but_gms_are_answered():
    assert not _send({}, _msg(bot=True))[0]
    assert not _send({}, _msg(chat=-555))[0]
    # Lewis tested it as a GM with exactly this, 2026-11-27
    assert _send({}, _msg("How to Dual class", user=99))[0]


def test_one_reply_per_topic_per_six_hours_and_per_player_per_day():
    state = {}
    assert _send(state, _msg())[0]
    # someone else asks in the same topic an hour later: quiet
    assert not _send(state, _msg(user=8, when=T0 + 3600))[0]
    # same player, another topic, an hour later: quiet
    assert not _send(state, _msg(thread=11, when=T0 + 3600))[0]
    # another player, another topic: answered
    assert _send(state, _msg(user=8, thread=11, when=T0 + 3600))[0]
    # seven hours on, a new player in the first topic: answered again
    assert _send(state, _msg(user=9, when=T0 + 7 * 3600))[0]


def test_an_in_character_ask_is_answered_in_the_chat_topic():
    sent, send = _send({}, _msg(thread=61))
    assert sent and send.call_args.args[1] == 50


def test_a_failed_send_is_not_remembered_and_empty_url_turns_it_off():
    state = {}
    assert not dch.maybe_answer(_msg(), CONFIG, state,
                                send=MagicMock(return_value=False))
    assert _send(state, _msg())[0]
    assert not _send({}, _msg(), config={**CONFIG, "dual_class_guide_url": ""})[0]


def test_no_username_falls_back_to_first_name():
    sent, send = _send({}, _msg(username=""))
    assert "Greg," in send.call_args.args[2]
