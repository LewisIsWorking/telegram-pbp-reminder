"""Foundry encounters from ComeOnOverUno driving the combat state. Added 2026-09-16.

⛔ Decided with Lewis: Foundry drives the bot. The server's tracker message is
edited in place and notifies nobody, so these pin down who the bot pings,
when, and where.
"""
from datetime import datetime, timedelta, timezone

import requests

from _test_telegram_mock import _sent_messages
from combat import foundry_sync
from combat.foundry_sync import fetch_encounters, reconcile, sync_foundry_encounters
from scheduled.combat_ping import check_combat_turns

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
PID = "107171"


def _config():
    return {"group_id": -100, "bot_topic_id": 300, "topic_pairs": [
        {"code": "C09", "name": "Metal City", "chat_topic_id": 104202,
         "pbp_topic_ids": [107171, 142887], "combat_topic_id": 142887},
    ]}


def _state():
    return {"combat": {}, "away": {}, "players": {
        "a": {"user_id": "111", "first_name": "Bella", "pbp_topic_id": PID},
        "b": {"user_id": "222", "first_name": "Ryo <3", "pbp_topic_id": PID},
    }}


def _encounter(round_num=1, acted=(), ended=False, encounter_id="E1", code="C09"):
    allies = [{"name": "Diabla", "acted": "111" in acted, "telegramUserId": "111"},
              {"name": "Changer", "acted": "222" in acted, "telegramUserId": "222"},
              {"name": "Drone", "acted": False, "telegramUserId": None}]
    phase = "allies" if len(acted) < 2 else "enemies"
    return {"code": code, "phase": phase, "trackerMessageId": 55, "snapshot": {
        "encounterId": encounter_id, "round": round_num, "allies": allies,
        "enemies": [{"name": "Ovvat", "acted": False}], "ended": ended}}


def _sync(state, *encounters, now=NOW):
    _sent_messages.clear()
    sync_foundry_encounters(_config(), state, now=now, fetch=lambda: list(encounters))
    return [m for m in _sent_messages if m["type"] == "message"]


def test_a_new_phase_pings_every_linked_ally_in_the_combat_topic_by_id():
    sent = _sync(state := _state(), _encounter())
    assert len(sent) == 1
    assert sent[0]["topic_id"] == 142887
    assert "Round 1: Unacted Allies" in sent[0]["text"]
    assert 'tg://user?id=111">Bella</a>' in sent[0]["text"]
    assert "Ryo &lt;3" in sent[0]["text"]
    combat = state["combat"][PID]
    assert combat["source"] == "foundry" and combat["current_phase"] == "players"
    assert combat["waiting_user_ids"] == ["111", "222"]
    assert combat["last_ping_at"] == NOW.isoformat()


def test_the_same_phase_again_pings_nobody_and_strikes_off_who_acted():
    state = _state()
    _sync(state, _encounter())
    sent = _sync(state, _encounter(acted=("111",)), now=NOW + timedelta(minutes=5))
    assert sent == []
    assert state["combat"][PID]["waiting_user_ids"] == ["222"]
    assert list(state["combat"][PID]["players_acted"]) == ["111"]


def test_the_enemies_phase_and_a_new_round_restart_the_phase():
    state = _state()
    _sync(state, _encounter())
    assert _sync(state, _encounter(acted=("111", "222"))) == []
    assert state["combat"][PID]["current_phase"] == "enemies"
    sent = _sync(state, _encounter(round_num=2))
    assert len(sent) == 1 and "Round 2" in sent[0]["text"]
    assert state["combat"][PID]["players_acted"] == {}


def test_an_away_player_is_not_pinged():
    state = _state()
    state["away"] = {f"{PID}:222": {"since": NOW.isoformat()}}
    sent = _sync(state, _encounter())
    assert "222" not in sent[0]["text"] and "111" in sent[0]["text"]


def test_an_ended_encounter_closes_only_its_own_combat():
    state = _state()
    _sync(state, _encounter())
    _sync(state, _encounter(ended=True, encounter_id="OTHER"))
    assert state["combat"][PID]["active"] is True
    _sync(state, _encounter(ended=True))
    assert state["combat"][PID]["active"] is False


def test_unknown_campaigns_and_disabled_combat_are_ignored():
    state = _state()
    assert reconcile(_config(), state, [_encounter(code="C99")], NOW) == []
    config = _config()
    config["topic_pairs"][0]["disabled_features"] = ["combat"]
    assert reconcile(config, state, [_encounter()], NOW) == []
    assert state["combat"] == {}


def test_reminders_for_a_foundry_fight_name_only_who_is_still_waiting():
    state = _state()
    _sync(state, _encounter(acted=("111",)))
    _sent_messages.clear()
    check_combat_turns(_config(), state, now=NOW + timedelta(hours=5))
    sent = [m for m in _sent_messages if m["type"] == "message"]
    assert len(sent) == 1 and sent[0]["topic_id"] == 142887
    assert "still waiting (5h)" in sent[0]["text"]
    assert "222" in sent[0]["text"] and "111" not in sent[0]["text"]


class _Response:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def test_fetch_sends_the_key_and_reads_nothing_without_one():
    seen = {}

    def get(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return _Response(200, [_encounter()])

    env = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://example.test/"}
    assert fetch_encounters(get=get, env=env)[0]["code"] == "C09"
    assert seen == {"url": "https://example.test/api/pathwars/encounters",
                    "headers": {foundry_sync.KEY_HEADER: "k"}}
    assert fetch_encounters(get=get, env={}) is None


def test_fetch_is_none_on_a_refusal_an_outage_or_a_strange_body():
    env = {"PATHWARS_BOT_READ_KEY": "k"}
    assert fetch_encounters(get=lambda *a, **k: _Response(401), env=env) is None
    assert fetch_encounters(get=lambda *a, **k: _Response(200, {"not": "a list"}), env=env) is None

    def down(*a, **k):
        raise requests.ConnectionError("down")

    assert fetch_encounters(get=down, env=env) is None
    _sent_messages.clear()
    sync_foundry_encounters(_config(), _state(), now=NOW, fetch=lambda: None)
    assert _sent_messages == []


def test_a_chat_message_is_not_a_turn_taken_in_foundry():
    from combat.tracker import handle_combat_message
    state = _state()
    _sync(state, _encounter())
    handle_combat_message("I swing!", "I swing!", "222", "Ryo", {"999"}, PID, "Metal City",
                          NOW.isoformat(), -100, 142887, state)
    assert state["combat"][PID]["players_acted"] == {}
