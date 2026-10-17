"""Each campaign's daily Foundry inventory snapshot, saved for the wiki. Added 2026-10-17.

The wiki publishes these files, so what they hold is public: these pin down what goes in, one file per campaign
per day, and that the hourly run does not rewrite a day it already has.
"""
import json

from combat.inventory_records import fetch_inventories, save_records, sync_foundry_inventories

CONFIG = {"topic_pairs": [{"code": "C07", "name": "The Hopeful End-Times", "pbp_topic_ids": [1]},
                          {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [2]}]}


def _stored(code="C07", date="2026-10-18", credits=155):
    return {"code": code, "world": "c07", "date": date, "takenAt": f"{date}T05:05:00Z",
            "actors": [{"id": "p", "name": "The Party", "kind": "party", "owners": [], "currency": {"credits": credits},
                        "items": [{"name": "Radiation Sweeper", "type": "equipment", "quantity": 1, "img": "x"}]},
                       {"id": "lai", "name": "Lai", "kind": "character", "owners": ["Terra"], "currency": {},
                        "items": []},
                       {"id": "nameless"}]}


def test_one_file_per_campaign_per_day_with_the_campaign_name(tmp_path):
    assert save_records(CONFIG, [_stored(), _stored(code="C00")], tmp_path) == 2
    saved = json.loads((tmp_path / "C07" / "2026-10-18.json").read_text(encoding="utf-8"))
    assert saved["campaign"] == "The Hopeful End-Times" and saved["date"] == "2026-10-18"
    assert [a["name"] for a in saved["actors"]] == ["The Party", "Lai"]
    assert saved["actors"][0]["items"] == [{"name": "Radiation Sweeper", "type": "equipment", "quantity": 1}]
    assert (tmp_path / "C00" / "2026-10-18.json").exists()


def test_the_hourly_run_rewrites_nothing_it_already_has(tmp_path):
    save_records(CONFIG, [_stored()], tmp_path)
    assert save_records(CONFIG, [_stored()], tmp_path) == 0
    assert save_records(CONFIG, [_stored(credits=900)], tmp_path) == 1, "a corrected snapshot the same day replaces it"
    assert save_records(CONFIG, [_stored(date="2026-10-19")], tmp_path) == 1
    assert sorted(p.name for p in (tmp_path / "C07").iterdir()) == ["2026-10-18.json", "2026-10-19.json"]


def test_a_bad_code_or_date_cannot_escape_the_folder(tmp_path):
    assert save_records(CONFIG, [_stored(code="../C07"), _stored(date="..")], tmp_path) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["C07"]


class _Response:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_fetch_needs_the_key_and_a_200():
    calls = []
    def get(url, headers, timeout):
        calls.append((url, headers))
        return _Response(200, [_stored()])
    assert fetch_inventories(get, {}) is None and calls == []
    assert fetch_inventories(get, {"PATHWARS_BOT_READ_KEY": "k"})[0]["code"] == "C07"
    assert calls[0] == ("https://cooserver.duckdns.org/api/pathwars/inventories", {"X-PathWars-Bot-Key": "k"})
    assert fetch_inventories(lambda *a, **k: _Response(404, None), {"PATHWARS_BOT_READ_KEY": "k"}) is None


def test_the_job_takes_the_checkers_arguments(tmp_path):
    sync_foundry_inventories(CONFIG, {}, now=None, maps=None, fetch=lambda: [_stored()], root=tmp_path)
    assert (tmp_path / "C07" / "2026-10-18.json").exists()
    sync_foundry_inventories(CONFIG, {}, now=None, maps=None, fetch=lambda: None, root=tmp_path)
