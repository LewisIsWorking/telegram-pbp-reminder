"""Each Foundry encounter saved as a record for the wiki. Added 2026-09-17.

The wiki publishes these files as encounter pages, so what they hold is
public: these pin down what goes in, and that a fight's history survives
the server forgetting it.
"""
import json

from combat import encounter_records
from combat.encounter_records import save_records

CONFIG = {"topic_pairs": [{"code": "C09", "name": "Metal City", "pbp_topic_ids": [107171]}]}
STATE = {"players": {
    "a": {"user_id": "111", "first_name": "Ryo", "username": "RyoYamakawa", "pbp_topic_id": "107171"},
    "b": {"user_id": "222", "first_name": "Bella", "pbp_topic_id": "107171"},
    "c": {"user_id": "111", "first_name": "Elsewhere", "username": "other", "pbp_topic_id": "999"},
}}


def _stored(started="2026-09-13T19:49:00+00:00", hits=(), ended=False, round_num=1, **snapshot):
    return {"code": "C09", "phase": "allies", "trackerMessageId": 55,
            "startedAt": started, "updatedAt": "2026-09-16T21:10:00+00:00",
            "hits": [{"round": r, "text": t} for r, t in hits],
            "snapshot": {"encounterId": "AbC123", "round": round_num, "ended": ended,
                         "name": "Captain Vex Ashburn", "location": "Bridge",
                         "allies": [{"name": "Arktos", "acted": False, "telegramUserId": "111", "initiative": 24},
                                    {"name": "Diabla", "acted": True, "telegramUserId": "222", "initiative": 19},
                                    {"name": "Drone", "acted": False}],
                         "enemies": [{"name": "Captain Vex", "acted": False, "initiative": 24.5},
                                     {"name": "The creature", "acted": False}],
                         **snapshot}}


def _read(tmp_path):
    files = sorted((tmp_path / "C09").glob("*.json"))
    assert len(files) == 1
    return files[0].name, json.loads(files[0].read_text(encoding="utf-8"))


def test_a_fight_is_saved_as_a_stub_with_its_initiative_order_and_players(tmp_path):
    assert save_records(CONFIG, STATE, [_stored(hits=[(1, "Knemdom. ▱▱▱▱▱▱▱▱▱▱ Down")])], tmp_path) == 1
    name, record = _read(tmp_path)
    assert name == "2026-09-13-AbC123.json"
    assert record["name"] == "Captain Vex Ashburn" and record["campaign"] == "Metal City"
    assert record["ended"] is False and record["ended_at"] is None
    assert [c["name"] for c in record["initiative"]] == ["Captain Vex", "Arktos", "Diabla"]
    assert record["allies"] == [{"name": "Arktos", "player": "@RyoYamakawa"},
                                {"name": "Diabla", "player": "Bella"},
                                {"name": "Drone", "player": None}]
    assert record["enemies"] == ["Captain Vex", "The creature"]
    assert record["hits"] == [{"round": 1, "text": "Knemdom. ▱▱▱▱▱▱▱▱▱▱ Down"}]


def test_an_unchanged_fight_writes_nothing_and_an_ended_one_records_when(tmp_path):
    save_records(CONFIG, STATE, [_stored()], tmp_path)
    assert save_records(CONFIG, STATE, [_stored()], tmp_path) == 0
    assert save_records(CONFIG, STATE, [_stored(ended=True, round_num=3)], tmp_path) == 1
    _, record = _read(tmp_path)
    assert record["ended"] is True and record["ended_at"] == "2026-09-16T21:10:00+00:00"
    assert record["rounds"] == 3


def test_a_server_restart_keeps_every_earlier_hit_across_later_runs(tmp_path):
    save_records(CONFIG, STATE, [_stored(hits=[(1, "first")])], tmp_path)
    later = "2026-09-15T08:00:00+00:00"
    save_records(CONFIG, STATE, [_stored(started=later, hits=[(2, "second")])], tmp_path)
    save_records(CONFIG, STATE, [_stored(started=later, hits=[(2, "second"), (3, "third")])], tmp_path)
    name, record = _read(tmp_path)
    assert name == "2026-09-13-AbC123.json"
    assert record["started_at"] == "2026-09-13T19:49:00+00:00"
    assert [h["text"] for h in record["hits"]] == ["first", "second", "third"]


def test_unknown_campaigns_and_encounters_without_an_id_are_skipped(tmp_path):
    other = _stored()
    other["code"] = "C99"
    no_id = _stored(encounterId="")
    assert save_records(CONFIG, STATE, [other, no_id], tmp_path) == 0
    assert not tmp_path.joinpath("C09").exists()


def test_an_unnamed_fight_takes_its_scene_and_ids_cannot_escape_the_folder(tmp_path):
    save_records(CONFIG, STATE, [_stored(name=None, encounterId="../../x")], tmp_path)
    name, record = _read(tmp_path)
    assert name == "2026-09-13-x.json"
    assert record["name"] == "Bridge"


def test_the_job_writes_to_the_isolated_records_dir_in_tests():
    assert "pbpbot_test_state_" in str(encounter_records.RECORDS_DIR)
