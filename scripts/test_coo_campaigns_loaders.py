"""Every config loader sees COO's campaign list; writers never do (2026-11-17).

The overlay lives in the shared loader, ``helpers_pkg.config.load_config``,
so checker, preflight, the alert scripts and every other caller get it.
``import_history`` and ``recruiting.roster_basis`` read a config.json at a
path of their own and go through ``with_coo_campaigns`` explicitly.
``promote_poll_voters`` writes config.json back, so it must read it raw.
"""
import inspect
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from helpers_pkg import config_load, coo_campaigns  # noqa: E402
import helpers  # noqa: E402
import helpers_pkg.config as config_mod  # noqa: E402

RAW = {"group_id": -1, "gm_user_ids": [1], "topic_pairs": [
    {"code": "C01", "name": "Old", "pbp_topic_ids": [10],
     "chat_topic_id": 11, "emoji": "x"}]}
COO = [{"code": "C01", "name": "From COO", "status": "active",
        "pbpTopicIds": [10], "chatTopicId": 12, "combatTopicId": None}]


@pytest.fixture
def coo_answered(tmp_path, monkeypatch):
    """A config.json in tmp_path, and COO's answer already fetched."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(RAW), encoding="utf-8")
    monkeypatch.setattr(config_load, "CONFIG_PATH", path)
    coo_campaigns.reset()
    coo_campaigns._fetched["campaigns"] = coo_campaigns.parse_campaigns(COO)
    yield path
    coo_campaigns.reset()


def test_the_shared_loader_overlays_coo(coo_answered):
    pair = config_mod.load_config()["topic_pairs"][0]
    assert (pair["name"], pair["chat_topic_id"], pair["emoji"]) == \
        ("From COO", 12, "x")


def test_every_import_path_is_the_same_loader():
    assert helpers.load_config is config_mod.load_config \
        is config_load.load_config


def test_the_raw_loader_never_overlays(coo_answered):
    assert config_load.load_raw_config() == RAW
    assert config_load.load_raw_config(coo_answered) == RAW


def test_the_shared_loader_falls_back_to_raw_when_coo_is_unknown(
        coo_answered):
    coo_campaigns._fetched["campaigns"] = None
    assert config_mod.load_config() == RAW


def test_import_history_overlays_its_own_config_path(coo_answered,
                                                     monkeypatch):
    import import_history
    monkeypatch.setattr(import_history, "CONFIG_PATH", coo_answered)
    assert import_history.load_config()["topic_pairs"][0]["name"] == \
        "From COO"


def test_roster_basis_overlays_the_live_campaign_list(coo_answered):
    from recruiting import roster_basis
    seen = []

    def counts(players, config, asof):
        seen.append(config)
        return {}

    players = coo_answered.parent / "players.json"
    players.write_text("{}", encoding="utf-8")
    with patch.object(roster_basis, "repo_root",
                      return_value=coo_answered.parent), \
            patch.object(roster_basis, "counts", side_effect=counts), \
            patch.object(roster_basis, "render", return_value=""):
        assert roster_basis.main(["x", str(players)], out=lambda *_: None) == 0
    assert seen[0]["topic_pairs"][0]["name"] == "From COO"


def test_the_config_writer_reads_config_json_raw():
    """promote_poll_voters writes config.json back: no COO values in it."""
    import promote_poll_voters
    source = inspect.getsource(promote_poll_voters.main)
    assert "load_raw_config(CONFIG)" in source
    assert "load_config()" not in source and "with_coo" not in source
