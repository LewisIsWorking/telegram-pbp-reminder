"""The weekly recruitment DM: which campaign, what it says, and how often.

Lewis, 2026-10-21: *"a weekly recruitment for the most in need campaign"*.

⚠️ The clock is always injected. Every timestamp below is built from
``_NOW`` and every call passes ``now=``, so nothing here compares a fixed
date against the real clock and turns red a month from now.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from scheduled import weekly_recruit as wr  # noqa: E402

_NOW = datetime(2026, 10, 21, 9, 13, tzinfo=timezone.utc)
_GM = "999"


def _pair(code, pid, **extra):
    pair = {"name": f"Camp {code}", "code": code, "chat_topic_id": pid + 1,
            "pbp_topic_ids": [pid], "discord_ad": f"{code}-Folder/{code}-ad.md"}
    pair.update(extra)
    return pair


def _cfg(*pairs, **extra):
    cfg = {"group_id": -100, "gm_user_ids": [_GM], "gm_user_id": _GM,
           "topic_pairs": list(pairs)}
    cfg.update(extra)
    return cfg


def _state(**counts):
    """``_state(C01=(100, 3))`` seats three players in topic 100."""
    players = {}
    for _code, (pid, n) in counts.items():
        for i in range(n):
            uid = f"{pid}{i}"
            players[f"{pid}:{uid}"] = {"user_id": uid,
                                       "pbp_topic_id": str(pid)}
    return {"players": players}


class _Sent:
    def __init__(self, monkeypatch, ok=True):
        self.calls = []
        monkeypatch.setattr(wr.tg, "send_message",
                            lambda c, t, text, **k: self.calls.append(
                                (c, t, text)) or ok)


# ── Who counts ───────────────────────────────────────────────────────────────

def test_active_counts_this_topic_only_and_never_the_gm():
    state = _state(a=(100, 2), b=(200, 4))
    state["players"]["100:999"] = {"user_id": _GM, "pbp_topic_id": "100"}
    assert wr.active_count(_pair("C01", 100), _cfg(), state) == 2


def test_active_tolerates_records_missing_fields():
    state = {"players": {"x": {}}}
    assert wr.active_count(_pair("C01", 100), _cfg(), state) == 0
    assert wr.active_count(_pair("C01", 100), _cfg(), {}) == 0


def test_not_recruiting_campaigns_are_skipped():
    off = _pair("C10", 300, disabled_features=["recruitment"])
    opt_out = _pair("C02", 400, weekly_recruit=False)
    no_topic = {"name": "Broken", "code": "CX", "pbp_topic_ids": []}
    cfg = _cfg(off, opt_out)
    assert not wr.is_recruiting(off, cfg)
    assert not wr.is_recruiting(opt_out, cfg)
    assert not wr.is_recruiting(no_topic, cfg)
    assert wr.is_recruiting(_pair("C01", 100), cfg)


def test_full_and_not_recruiting_campaigns_are_not_short():
    cfg = _cfg(_pair("C01", 100), _pair("C02", 200),
               _pair("C11", 300, disabled_features=["recruitment"]))
    short = wr.short_campaigns(cfg, _state(a=(100, 6), b=(200, 7),
                                           c=(300, 1)))
    assert short == []


# ── Who wins ─────────────────────────────────────────────────────────────────

def test_furthest_below_six_wins():
    cfg = _cfg(_pair("C01", 100), _pair("C09", 200), _pair("C04", 300))
    ranked = wr.rank(cfg, _state(a=(100, 4), b=(200, 2), c=(300, 5)))
    assert [p["code"] for p, _c in ranked] == ["C09", "C01", "C04"]


def test_a_tie_goes_to_the_one_picked_longest_ago():
    cfg = _cfg(_pair("C01", 100), _pair("C04", 200), _pair("C05", 300))
    state = _state(a=(100, 4), b=(200, 4), c=(300, 4))
    state[wr.PICKS_KEY] = {"100": (_NOW - timedelta(days=7)).isoformat(),
                           "200": (_NOW - timedelta(days=21)).isoformat()}
    ranked = [p["code"] for p, _c in wr.rank(cfg, state)]
    # Never picked beats both; then the older pick.
    assert ranked == ["C05", "C04", "C01"]


def test_a_full_tie_keeps_config_order_and_bad_stamps_count_as_never():
    cfg = _cfg(_pair("C07", 100), _pair("C01", 200))
    state = _state(a=(100, 3), b=(200, 3))
    state[wr.PICKS_KEY] = {"100": "not a date", "200": None}
    assert [p["code"] for p, _c in wr.rank(cfg, state)] == ["C07", "C01"]


def test_open_slots_is_shortfall_plus_one_and_never_zero():
    assert wr.open_slots(2) == 5
    assert wr.open_slots(5) == 2
    assert wr.open_slots(6) == 1
    assert wr.open_slots(9) == 1


# ── What it says ─────────────────────────────────────────────────────────────

def test_the_message_names_the_campaign_counts_slots_and_ad():
    cfg = _cfg(_pair("C09", 200, name="Metal City"), _pair("C01", 100))
    text, pair = wr.build_weekly_recruit(
        cfg, _state(a=(100, 4), b=(200, 2)), _NOW)
    assert pair["code"] == "C09"
    assert "Weekly recruitment: C09 Metal City" in text
    assert "Active players: 2/6 (4 short)" in text
    assert "Suggested Open Slots: 5" in text
    assert wr.WIKI_TOPICS_URL + "C09-Folder/C09-ad.md" in text
    assert wr.WIKI_TOPICS_URL + wr.MULTI_AD in text
    assert "make it a bit better" in text
    assert "Not picked for weekly recruitment before." in text
    assert "Also below 6: C01 4/6" in text
    assert chr(0x2014) not in text


def test_the_message_says_when_it_was_last_picked():
    cfg = _cfg(_pair("C09", 200))
    state = _state(b=(200, 2))
    state[wr.PICKS_KEY] = {"200": (_NOW - timedelta(days=14)).isoformat()}
    text, _pair_ = wr.build_weekly_recruit(cfg, state, _NOW)
    assert "(14d ago)" in text
    assert "Also below" not in text


def test_a_campaign_without_an_ad_page_says_how_to_add_one():
    pair = _pair("C02", 100)
    del pair["discord_ad"]
    assert "No Discord ad page recorded for C02" in wr.ad_line(pair, _cfg())
    nameless = {"name": "Loose", "pbp_topic_ids": [5]}
    assert "for Loose" in wr.ad_line(nameless, _cfg())


def test_the_wiki_base_can_be_overridden():
    line = wr.ad_line(_pair("C01", 100), _cfg(wiki_topics_url="https://x/"))
    assert line.endswith("https://x/C01-Folder/C01-ad.md")


def test_nothing_short_builds_nothing():
    assert wr.build_weekly_recruit(_cfg(_pair("C01", 100)),
                                   _state(a=(100, 6)), _NOW) == ("", None)
