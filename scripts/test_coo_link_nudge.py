"""A player whose Telegram is not linked to COO is told how to link it.

Added 2026-10-08, after KP asked for a C00 sheet that nothing could make:
with no linked COO account there is no Foundry login, so Tongs never saw
him. Lewis: nudge on the first post, and again whenever they ask.
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.dirname(__file__))

from players import coo_link  # noqa: E402

MAPS = SimpleNamespace(to_chat={"100": 555})
CONFIG = {"group_id": -1}


def _parsed(text="Hello all", when="2026-10-08T12:00:00+00:00", user="7"):
    return {"pid": "100", "thread_id": 100, "user_id": user, "user_name": "KP",
            "username": "kp", "text": text, "raw_text": text,
            "msg_time_iso": when}


def _nudge(state, parsed, linked=frozenset({"1"})):
    with patch.object(coo_link.tg, "send_message", return_value=True) as send:
        sent = coo_link.nudge_if_unlinked(parsed, state, CONFIG, MAPS,
                                          linked=lambda: set(linked))
    return sent, send


def test_first_post_nudges_once_in_the_chat_topic():
    state = {}
    sent, send = _nudge(state, _parsed())
    assert sent
    group, thread, text = send.call_args.args
    assert (group, thread) == (-1, 555)
    assert "@kp" in text and coo_link.LINK_URL in text
    assert state["coo_link_nudges"] == {"7": "2026-10-08T12:00:00+00:00"}
    assert _nudge(state, _parsed(when="2026-10-09T12:00:00+00:00"))[0] is False


def test_an_ask_nudges_again_but_not_twice_in_six_hours():
    state = {"coo_link_nudges": {"7": "2026-10-08T00:00:00+00:00"}}
    asks = _parsed("i request a character shith", "2026-10-08T12:00:00+00:00")
    assert _nudge(state, asks)[0]
    assert _nudge(state, _parsed("sheet", "2026-10-08T13:00:00+00:00"))[0] is False
    assert _nudge(state, _parsed("Foundry?", "2026-10-08T18:00:00+00:00"))[0]


def test_linked_players_commands_and_unknown_links_are_left_alone():
    assert _nudge({}, _parsed(user="1"))[0] is False
    assert _nudge({}, _parsed("/roll 1d20"))[0] is False
    with patch.object(coo_link.tg, "send_message") as send:
        assert coo_link.nudge_if_unlinked(_parsed(), {}, CONFIG, MAPS,
                                          linked=lambda: None) is False
    send.assert_not_called()


def test_a_failed_send_is_retried_next_post():
    state = {}
    with patch.object(coo_link.tg, "send_message", return_value=False):
        assert coo_link.nudge_if_unlinked(_parsed(), state, CONFIG, MAPS,
                                          linked=lambda: set()) is False
    assert state["coo_link_nudges"] == {}


def test_no_chat_topic_falls_back_to_the_thread_and_name():
    parsed = dict(_parsed(), pid="200", username="")
    with patch.object(coo_link.tg, "send_message", return_value=True) as send:
        coo_link.nudge_if_unlinked(parsed, {}, CONFIG, MAPS, linked=lambda: set())
    assert send.call_args.args[1] == 100
    assert "KP," in send.call_args.args[2]


def test_fetch_reads_the_server_with_the_bot_key():
    env = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://coo/"}
    get = MagicMock(return_value=SimpleNamespace(status_code=200, json=lambda: [1, "2"]))
    assert coo_link.fetch_linked(get=get, env=env) == {"1", "2"}
    assert get.call_args.args[0] == "https://coo/api/pathwars/linked"
    assert get.call_args.kwargs["headers"] == {"X-PathWars-Bot-Key": "k"}


def test_fetch_gives_none_whenever_the_answer_is_not_known():
    env = {"PATHWARS_BOT_READ_KEY": "k"}
    assert coo_link.fetch_linked(get=MagicMock(), env={}) is None
    refused = MagicMock(return_value=SimpleNamespace(status_code=401))
    assert coo_link.fetch_linked(get=refused, env=env) is None
    odd = MagicMock(return_value=SimpleNamespace(status_code=200, json=lambda: {}))
    assert coo_link.fetch_linked(get=odd, env=env) is None
    down = MagicMock(side_effect=requests.ConnectionError())
    assert coo_link.fetch_linked(get=down, env=env) is None


def test_linked_ids_are_fetched_once_per_run():
    coo_link.reset()
    fetch = MagicMock(return_value={"1"})
    try:
        assert coo_link.linked_ids(fetch) == {"1"}
        assert coo_link.linked_ids(fetch) == {"1"}
        fetch.assert_called_once()
    finally:
        coo_link.reset()


# ── @ComeOnOverBot posts it when COO can (Lewis, 2026-10-08) ──────────────

def test_comeonoverbot_posts_it_and_the_nudge_bot_stays_quiet():
    state = {}
    with patch.object(coo_link, "post_as_comeonoverbot", return_value=True) as coo, \
         patch.object(coo_link.tg, "send_message") as send:
        assert coo_link.nudge_if_unlinked(_parsed(), state, CONFIG, MAPS,
                                          linked=lambda: set())
    assert coo.call_args.args[1] == 555
    send.assert_not_called()
    assert "7" in state["coo_link_nudges"]


def test_post_as_comeonoverbot_sends_the_player_and_topic_with_the_key():
    env = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://coo/"}
    post = MagicMock(return_value=SimpleNamespace(status_code=200))
    assert coo_link.post_as_comeonoverbot(_parsed(), 555, post=post, env=env)
    assert post.call_args.args[0] == "https://coo/api/pathwars/link-nudge"
    assert post.call_args.kwargs["json"] == {"name": "KP", "username": "kp", "threadId": 555}
    assert post.call_args.kwargs["headers"] == {"X-PathWars-Bot-Key": "k"}


def test_post_as_comeonoverbot_is_false_whenever_coo_did_not_post():
    env = {"PATHWARS_BOT_READ_KEY": "k"}
    assert coo_link.post_as_comeonoverbot(_parsed(), 1, post=MagicMock(), env={}) is False
    for status in (503, 502, 401):
        answered = MagicMock(return_value=SimpleNamespace(status_code=status))
        assert coo_link.post_as_comeonoverbot(_parsed(), 1, post=answered, env=env) is False
    down = MagicMock(side_effect=requests.ConnectionError())
    assert coo_link.post_as_comeonoverbot(_parsed(), 1, post=down, env=env) is False
