"""/extrasheet: who gets a second character sheet, and what the group is told.

Added 2026-10-12. The grant file is read by ComeOnOverUno and Tongs, so
these tests pin its exact shape as well as every reply. Entry points
(handle, handle_outside, the router) are in test_extrasheet_routing.py.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from dispatch import cmd_extrasheet as xs  # noqa: E402
from helpers import build_topic_maps  # noqa: E402
from players import extra_sheets  # noqa: E402
from state_store import StateStore  # noqa: E402

KIBWE, THERIA = "40585", "107151"
CONFIG = {
    "group_id": -100, "bot_topic_id": 999, "gm_user_ids": [1],
    "topic_pairs": [
        {"name": "Kibwe", "code": "C06", "chat_topic_id": 21528,
         "pbp_topic_ids": [40585, 137075]},
        {"name": "Theria", "code": "C08", "chat_topic_id": 107141,
         "pbp_topic_ids": [107151], "gm_user_ids": [6]},
        {"name": "No Code", "chat_topic_id": 500, "pbp_topic_ids": [501]},
        {"name": "Elsewhere", "code": "C11", "chat_topic_id": 600,
         "pbp_topic_ids": [601], "group_id": -200},
    ],
}
MAPS = build_topic_maps(CONFIG)
STATE = {
    "players": {
        "1:pending": {"user_id": "pending_lai", "username": "Lai",
                      "pbp_topic_id": KIBWE},
        "52083:7": {"user_id": "7", "first_name": "Lai (C07)",
                    "username": "Lai", "pbp_topic_id": "52083"},
        "40585:7": {"user_id": "7", "first_name": "Lai", "username": "lai",
                    "pbp_topic_id": KIBWE},
        "40585:8": {"user_id": "8", "username": "noname",
                    "pbp_topic_id": KIBWE},
    },
    "group_members": {"9": {"name": "KP", "username": "kp"},
                      "10": {"username": "quiet"}},
}
AT = "2026-10-12T03:00:00Z"


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(extra_sheets, "_store", StateStore(state_dir=tmp_path))
    return tmp_path


def run(caller="7", args="", pid=KIBWE, replied=None, config=CONFIG,
        name="Lai"):
    return xs.reply_for(caller, name, args, pid, replied, config, STATE,
                        MAPS, now=AT)


def grants(store):
    return json.loads((store / "extra_sheets.json").read_text(encoding="utf-8"))["grants"]


def test_a_player_grants_themself_in_their_topic_in_the_contract_shape(store):
    assert run() == ("✅ Lai can make a second character sheet in C06. "
                     "Open the world and Tongs will offer it.")
    assert grants(store) == [{"telegram_user_id": "7", "campaign": "C06",
                              "granted_by": "7", "at": AT}]


def test_a_second_request_is_refused_and_never_stored_twice(store):
    run()
    assert run() == "Lai already has their extra sheet in C06 (2 sheets is the most)."
    assert len(grants(store)) == 1
    # Another campaign is its own cap.
    assert run(args="c08").startswith("✅ Lai")
    assert [g["campaign"] for g in grants(store)] == ["C06", "C08"]


def test_outside_a_campaign_topic_the_campaign_must_be_named(store):
    assert run(pid=None) == xs.NOT_IN_TOPIC
    assert not (store / "extra_sheets.json").exists()
    assert "in C06" in run(pid=None, args="C06")
    assert "in C08" in run(pid=None, args="theria")  # by name, too


def test_an_unknown_campaign_lists_the_codes():
    reply = run(args="c42")
    assert reply.startswith('I don\'t know a campaign called "c42".')
    assert "C06 Kibwe" in reply and "C11 Elsewhere" in reply
    assert "No Code" not in reply


def test_a_campaign_without_a_code_cannot_be_granted(store):
    assert run(pid="501") == ("No Code has no campaign code in config.json, "
                              "so it cannot have extra sheets yet.")
    assert not (store / "extra_sheets.json").exists()


def test_a_player_cannot_name_someone_else():
    assert run(args="@kp C06") == xs.NOT_GM


def test_a_player_replying_to_someone_still_grants_only_themself(store):
    assert "Lai can" in run(replied={"id": 9, "first_name": "KP"})
    assert grants(store)[0]["telegram_user_id"] == "7"


def test_the_gm_names_a_player_by_username_from_the_players_data(store):
    reply = run(caller="1", name="GM", args="@LAI C06", pid=None)
    # Their Kibwe record beats their C07 one, and the placeholder is skipped.
    assert reply.startswith("✅ Lai can make")
    assert grants(store)[0] == {"telegram_user_id": "7", "campaign": "C06",
                                "granted_by": "1", "at": AT}


def test_the_gm_finds_group_members_and_falls_back_to_the_username(store):
    assert run(caller="1", args="@kp c06").startswith("✅ KP can")
    assert run(caller="1", args="@quiet c06").startswith("✅ quiet can")
    assert run(caller="1", args="@noname c06").startswith("✅ noname can")
    assert [g["telegram_user_id"] for g in grants(store)] == ["9", "10", "8"]


def test_the_gm_naming_an_unknown_user_is_told_how_to_fix_it(store):
    assert run(caller="1", args="@ghost C06") == (
        "I don't know @ghost. They need to have posted in the group once, "
        "or reply to one of their messages with /extrasheet C06")
    assert not (store / "extra_sheets.json").exists()


def test_the_gm_replying_to_a_player_grants_that_player(store):
    reply = run(caller="1", args="C06", pid=None,
                replied={"id": 42, "first_name": "Kibwe Fan"})
    assert reply.startswith("✅ Kibwe Fan can")
    assert grants(store)[0]["telegram_user_id"] == "42"
    assert "✅ zed can" in run(caller="1", replied={"id": 43, "username": "zed"})
    assert "✅ 44 can" in run(caller="1", replied={"id": 44})


def test_the_gm_replying_to_a_bot_is_refused(store):
    assert run(caller="1", replied={"id": 5, "is_bot": True}) == (
        "That message is from a bot. Reply to the player's own message, "
        "or use /extrasheet @username C06")
    assert not (store / "extra_sheets.json").exists()


def test_a_campaigns_own_gm_and_the_single_gm_user_id_count():
    assert run(caller="6", args="@kp", pid=THERIA).startswith("✅ KP")
    solo = {**CONFIG, "gm_user_ids": [], "gm_user_id": 1}
    assert run(caller="1", args="@kp", config=solo).startswith("✅ KP")
    assert run(caller="6", args="@kp") == xs.NOT_GM  # Theria's GM, not Kibwe's


def test_without_a_clock_the_grant_is_stamped_now_in_utc(store):
    xs.reply_for("7", "Lai", "", KIBWE, None, CONFIG, STATE, MAPS)
    assert grants(store)[0]["at"].endswith("Z")
    assert len(grants(store)[0]["at"]) == len(AT)


@pytest.mark.parametrize("data", [[], {"grants": {}}, {"grants": ["x", 3]}])
def test_a_file_of_the_wrong_shape_counts_as_no_grants(store, data):
    (store / "extra_sheets.json").write_text(json.dumps(data), encoding="utf-8")
    assert extra_sheets.has_grant("7", "C06") is False
    assert extra_sheets.grant("7", "C06", "7", AT) is True
    assert extra_sheets.has_grant("7", "C06") is True
