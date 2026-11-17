"""COO's campaign list is laid over config.json's topic_pairs (2026-11-17).

Lewis decided COO is the source of truth for which Path Wars campaigns
exist and their Telegram topics. The bot keeps its own settings per
campaign in config.json, matched by code, and falls back to config.json
unchanged whenever COO cannot answer.
"""
import copy
import os
import sys
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))

from helpers_pkg import coo_campaigns  # noqa: E402
from helpers_pkg.config import validate_config  # noqa: E402

CONFIG = {
    "group_id": -1, "gm_user_ids": [1],
    "topic_pairs": [
        {"code": "C01", "name": "Old Name", "pbp_topic_ids": [25059, 22566],
         "chat_topic_id": 21514, "combat_topic_id": 22566,
         "queue_priority": 1, "queue_always_first": True, "emoji": "x"},
        {"code": "C99", "name": "Tongs Testing", "pbp_topic_ids": [75843],
         "chat_topic_id": 75843, "queue_exclude": True},
    ],
}


def _coo(code="C01", **over):
    item = {"code": code, "cooCampaignId": "guid", "name": "New Name",
            "status": "active", "pbpTopicIds": [22566, 25059, 30000],
            "chatTopicId": 21515, "combatTopicId": 30000,
            "discordRoleId": None, "foundryWorldId": None, "wikiSlug": None}
    item.update(over)
    return item


def _apply(*items):
    config = copy.deepcopy(CONFIG)
    campaigns = coo_campaigns.parse_campaigns(list(items))
    out = coo_campaigns.apply(config, validate_config, fetch=lambda: campaigns)
    assert config == CONFIG, "apply must not modify the config it was given"
    return out


def _pair(config, code):
    return next(p for p in config["topic_pairs"] if p["code"] == code)


def test_overlay_by_code_takes_name_and_topics_from_coo():
    c01 = _pair(_apply(_coo()), "C01")
    assert c01["name"] == "New Name"
    assert c01["chat_topic_id"] == 21515 and c01["combat_topic_id"] == 30000
    # The first id is the campaign's key in state, so it stays first.
    assert c01["pbp_topic_ids"] == [25059, 22566, 30000]
    assert c01["status"] == "active"


def test_bot_only_settings_are_kept():
    c01 = _pair(_apply(_coo()), "C01")
    assert c01["queue_priority"] == 1 and c01["queue_always_first"] is True
    assert c01["emoji"] == "x"


def test_null_fields_from_coo_keep_the_config_value():
    c01 = _pair(_apply(_coo(chatTopicId=None, combatTopicId=None,
                            name=None)), "C01")
    assert (c01["name"], c01["chat_topic_id"], c01["combat_topic_id"]) == \
        ("Old Name", 21514, 22566)


def test_coo_dropping_the_first_id_keeps_config_ids(capsys):
    c01 = _pair(_apply(_coo(pbpTopicIds=[22566])), "C01")
    assert c01["pbp_topic_ids"] == [25059, 22566]
    assert "C01 ids kept from config.json" in capsys.readouterr().out


def test_new_coo_campaign_gets_a_default_pair(capsys):
    out = _apply(_coo(), _coo("C12", name="Fresh", pbpTopicIds=[500],
                              chatTopicId=501, combatTopicId=None))
    assert _pair(out, "C12") == {"code": "C12", "name": "Fresh",
                                 "pbp_topic_ids": [500], "chat_topic_id": 501,
                                 "status": "active"}
    assert [p["code"] for p in out["topic_pairs"]] == ["C01", "C99", "C12"]
    printed = capsys.readouterr().out
    assert printed.count("\n") == 1 and "added C12" in printed


@pytest.mark.parametrize("over", [{"pbpTopicIds": []}, {"chatTopicId": None},
                                  {"status": "archived"}])
def test_new_coo_campaign_that_cannot_run_is_skipped(over, capsys):
    out = _apply(_coo(), _coo("C12", **{"pbpTopicIds": [500],
                                        "chatTopicId": 501, **over}))
    assert all(p["code"] != "C12" for p in out["topic_pairs"])
    assert "not added (inactive or no topics) C12" in capsys.readouterr().out


def test_config_only_campaign_is_kept_unchanged(capsys):
    out = _apply(_coo())
    assert _pair(out, "C99") == CONFIG["topic_pairs"][1]
    assert "config.json only, kept C99" in capsys.readouterr().out


def test_status_is_carried_through_not_deleted():
    out = _apply(_coo(status="archived"), _coo("C99", status="closed",
                                              pbpTopicIds=[75843],
                                              chatTopicId=75843))
    assert _pair(out, "C01")["status"] == "archived"
    assert _pair(out, "C99")["status"] == "closed"
    assert len(out["topic_pairs"]) == 2


def test_an_overlay_that_breaks_validation_is_refused(capsys):
    # C12 claiming C01's PbP topic would be a fatal config error.
    out = _apply(_coo(), _coo("C12", pbpTopicIds=[25059], chatTopicId=9))
    assert out == CONFIG
    assert "refused" in capsys.readouterr().out


# ── Every failure falls back to config.json unchanged ──────────────────────

ENV = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://coo.test/"}


def _response(status=200, body=None, bad_json=False):
    r = MagicMock(status_code=status)
    r.json.side_effect = ValueError("no json") if bad_json else None
    r.json.return_value = body
    return r


def _run(get, env=ENV):
    config = copy.deepcopy(CONFIG)
    fetch = lambda: coo_campaigns.fetch_campaigns(get=get, env=env)  # noqa: E731
    return coo_campaigns.apply(config, validate_config, fetch=fetch)


def _raises(*a, **k):
    raise requests.ConnectionError("down")


@pytest.mark.parametrize("get, env, said", [
    (MagicMock(), {}, "no read key"),
    (_raises, ENV, "server unreachable (ConnectionError)"),
    (lambda *a, **k: _response(500), ENV, "server answered 500"),
    (lambda *a, **k: _response(bad_json=True), ENV, "malformed"),
    (lambda *a, **k: _response(body={"code": "C01"}), ENV, "malformed"),
    (lambda *a, **k: _response(body=["C01"]), ENV, "malformed"),
    (lambda *a, **k: _response(body=[{"code": "C01"}]), ENV, "malformed"),
    (lambda *a, **k: _response(body=[_coo(chatTopicId="x")]), ENV,
     "malformed"),
])
def test_every_failure_uses_config_json_unchanged(get, env, said, capsys):
    assert _run(get, env) == CONFIG
    printed = capsys.readouterr().out
    assert printed.count("\n") == 1 and said in printed


def test_no_key_never_calls_the_server():
    get = MagicMock()
    _run(get, env={"PATHWARS_BOT_READ_KEY": "  "})
    get.assert_not_called()


def test_the_request_uses_the_read_key_header():
    get = MagicMock(return_value=_response(body=[_coo()]))
    out = _run(get)
    url = get.call_args.args[0]
    assert url == "https://coo.test/api/pathwars/campaigns"
    assert list(get.call_args.kwargs["headers"].values()) == ["k"]
    assert _pair(out, "C01")["name"] == "New Name"


def test_fetched_once_per_run():
    coo_campaigns.reset()
    fetch = MagicMock(return_value=[])
    try:
        coo_campaigns.coo_campaigns(fetch)
        coo_campaigns.coo_campaigns(fetch)
        assert fetch.call_count == 1
        coo_campaigns.reset()
        coo_campaigns.coo_campaigns(fetch)
        assert fetch.call_count == 2
    finally:
        coo_campaigns.reset()


def test_the_checker_run_goes_through_the_overlay():
    import checker
    import inspect
    assert "coo_campaigns.apply(helpers.load_config()" in \
        inspect.getsource(checker.main)
