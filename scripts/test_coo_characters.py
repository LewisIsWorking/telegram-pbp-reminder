"""Character names come from COO when no GM has used /setchar.

Added 2026-11-23: players.json ``characters`` was empty for every campaign,
so /summary and the weekly reports named nobody's character. COO names
them from each campaign's Foundry party sheet.
"""
import os
import sys
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))

from helpers_pkg.topic_maps import character_name, get_characters  # noqa: E402
from players import coo_characters  # noqa: E402

KEY = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://coo.test/"}
CONFIG = {"topic_pairs": [{"name": "Kibwe", "chat_topic_id": 21528,
                           "pbp_topic_ids": [40585, 137075],
                           "characters": {"9": "From config", "1": "Overridden"}}]}


@pytest.fixture(autouse=True)
def _fresh():
    coo_characters.reset()
    yield
    coo_characters.reset()


def _get(status=200, body=None, error=None, calls=None):
    def get(url, headers, timeout):
        if calls is not None:
            calls.append((url, headers))
        if error:
            raise error
        def json():
            if isinstance(body, Exception):
                raise body
            return body
        return SimpleNamespace(status_code=status, json=json)
    return get


def test_fetch_reads_the_names_with_the_bots_key():
    calls = []
    got = coo_characters.fetch_characters(
        _get(body={"40585": {"1": "Steele", "2": " ", "3": 7}, "x": []}, calls=calls), KEY)
    assert got == {"40585": {"1": "Steele"}}
    assert calls == [("https://coo.test/api/pathwars/characters", {"X-PathWars-Bot-Key": "k"})]


@pytest.mark.parametrize("get", [
    _get(status=503),
    _get(error=requests.ConnectionError("down")),
    _get(body=ValueError("not json")),
    _get(body=["a list"]),
])
def test_no_answer_is_no_names(get):
    assert coo_characters.fetch_characters(get, KEY) is None


def test_no_key_never_asks():
    assert coo_characters.fetch_characters(_get(error=AssertionError("asked")), {}) is None


def test_load_reads_once_and_names_merge_under_setchar():
    fetched = []
    def fetch():
        fetched.append(1)
        return {"40585": {"1": "Steele", "2": "Changer"}}
    coo_characters.load(fetch)
    coo_characters.load(fetch)
    assert fetched == [1]
    state = {"characters": {"40585": {"2": "Set by /setchar"}}}
    assert get_characters(CONFIG, "40585", state) == {"9": "From config", "1": "Steele", "2": "Set by /setchar"}
    assert get_characters(CONFIG, "21528") == {"9": "From config", "1": "Steele", "2": "Changer"}
    assert character_name(CONFIG, "137075", "1") == "Steele"


def test_nothing_known_changes_nothing():
    coo_characters.load(lambda: None)
    assert get_characters(CONFIG, "40585") == {"9": "From config", "1": "Overridden"}
    assert coo_characters.for_campaign("40585") == {}


def test_first_use_reads_them_without_a_key_asking_nobody(monkeypatch):
    monkeypatch.delenv("PATHWARS_BOT_READ_KEY", raising=False)
    assert get_characters(CONFIG, "40585") == {"9": "From config", "1": "Overridden"}
    assert get_characters({"topic_pairs": [{"chat_topic_id": 5, "pbp_topic_ids": []}]}, "5") == {}
