"""Tests for the daily GM digest of overdue combat turns (scheduled/turn_digest.py)."""
from _test_checker_helpers import (
    datetime, timezone, timedelta, _sent_messages, _reset, _make_config, _make_state,
)
from scheduled.turn_digest import post_turn_digest, overdue_turns, STATE_KEY

NOW = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)


def _config():
    config = _make_config(pairs=[{
        "name": "Kibwe", "chat_topic_id": 200, "pbp_topic_ids": [100], "combat_topic_id": 137075,
    }])
    config["group_username"] = "Path_Wars"
    config["gm_queue_topic_id"] = 146780
    return config


def _state(hours=30, source="foundry", waiting=("42",), acted=()):
    state = _make_state()
    state["combat"] = {"100": {
        "active": True, "source": source, "round": 2, "current_phase": "players",
        "phase_started_at": (NOW - timedelta(hours=hours)).isoformat(),
        "players_acted": {uid: NOW.isoformat() for uid in acted},
        "waiting_user_ids": list(waiting), "campaign_name": "Kibwe",
    }}
    for uid, name in (("42", "Thien"), ("43", "Ryo")):
        state["players"][f"100:{uid}"] = {
            "user_id": uid, "first_name": name, "username": name.lower(),
            "pbp_topic_id": "100", "campaign_name": "Kibwe",
        }
    return state


def _digests():
    return [m for m in _sent_messages if "waiting 24h+" in m.get("text", "")]


def test_lists_overdue_player_without_pinging_them():
    _reset()
    state = _state()
    post_turn_digest(_config(), state, now=NOW)
    sent = _digests()
    assert len(sent) == 1
    text = sent[0]["text"]
    assert "Thien, Kibwe, waiting 1d 6h" in text
    assert "https://t.me/Path_Wars/137075" in text
    assert "tg://user" not in text and "@thien" not in text
    assert "Ryo" not in text
    assert state[STATE_KEY] == NOW.isoformat()


def test_nothing_before_24_hours():
    _reset()
    post_turn_digest(_config(), _state(hours=23), now=NOW)
    assert _digests() == []


def test_once_a_day():
    _reset()
    state = _state()
    state[STATE_KEY] = (NOW - timedelta(hours=10)).isoformat()
    post_turn_digest(_config(), state, now=NOW)
    assert _digests() == []
    state[STATE_KEY] = (NOW - timedelta(hours=23)).isoformat()
    post_turn_digest(_config(), state, now=NOW)
    assert len(_digests()) == 1


def test_skips_away_players_and_enemy_phase():
    _reset()
    state = _state()
    state["away"] = {"100:42": {"until": (NOW + timedelta(days=2)).isoformat()}}
    assert overdue_turns(_config(), state, NOW) == []
    state2 = _state()
    state2["combat"]["100"]["current_phase"] = "enemies"
    assert overdue_turns(_config(), state2, NOW) == []


def test_slash_combat_fight_uses_players_acted():
    _reset()
    entries = overdue_turns(_config(), _state(source=None, waiting=(), acted=("42",)), NOW)
    assert [e["name"] for e in entries] == ["Ryo"]


def test_private_group_link_and_no_combat_topic():
    config = _config()
    config["topic_pairs"][0]["group_id"] = -1001234567
    entries = overdue_turns(config, _state(), NOW)
    assert entries[0]["link"] == "https://t.me/c/1234567/137075"
    config["topic_pairs"][0].pop("combat_topic_id")
    assert overdue_turns(config, _state(), NOW)[0]["link"] is None


def test_combat_feature_off_is_skipped():
    config = _config()
    config["topic_pairs"][0]["disabled_features"] = ["combat"]
    assert overdue_turns(config, _state(), NOW) == []


def test_no_topic_no_post():
    _reset()
    config = _config()
    config.pop("gm_queue_topic_id")
    config.pop("bot_topic_id")
    post_turn_digest(config, _state(), now=NOW)
    assert _digests() == []
