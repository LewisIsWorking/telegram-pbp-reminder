"""Silent/caught-up sections sort longest-idle first (2026-08-10).

Reported from queue #1327, whose Caught up section read:

    C01  21h
    C00  0h
    C04  2h
    C05  5h
    C06  4d 2h
    C07  1h

which is ``config["topic_pairs"]`` order, not age order. ``silent_campaigns``
and ``caught_up_campaigns`` both built their lists by appending in iteration
order and never sorted — while ``campaign_age_lines``, ten lines below them in
the same module, already did ``rows.sort(key=lambda r: r[0], reverse=True)``.

The data needed was always there: ``_idle_campaigns`` yields ``days`` as a
float, so sub-day ages (0h vs 21h) discriminate correctly.

Also covers ``oldest_campaign_line``, the empty-queue counterpart to the
"Reply to this next" focus message.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


def _ago(hours):
    return (_NOW - timedelta(hours=hours)).isoformat()


# Deliberately in the same "wrong" order as the reported queue, so a
# regression that drops the sort reproduces the original output.
_PAIRS = [
    {"code": "C01", "name": "Doomsday Funtime", "pbp_topic_ids": [25059]},
    {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [66154]},
    {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [76799]},
    {"code": "C05", "name": "Grand Explorers", "pbp_topic_ids": [51357]},
    {"code": "C06", "name": "Kibwe", "pbp_topic_ids": [40585]},
    {"code": "C07", "name": "Hopeful End-Times", "pbp_topic_ids": [52083]},
    {"code": "C09", "name": "Metal City", "pbp_topic_ids": [107171]},
]
_CFG = {"group_id": -100, "topic_pairs": _PAIRS}
_STATE = {"topics": {
    "25059":  {"last_message_time": _ago(21)},      # C01 21h
    "66154":  {"last_message_time": _ago(0.2)},     # C00 0h
    "76799":  {"last_message_time": _ago(2)},       # C04 2h
    "51357":  {"last_message_time": _ago(5)},       # C05 5h
    "40585":  {"last_message_time": _ago(98)},      # C06 4d 2h
    "52083":  {"last_message_time": _ago(1)},       # C07 1h
    "107171": {"last_message_time": _ago(221)},     # C09 9d 5h -> silent
}}


def _codes(lines):
    """Pull the campaign codes out of rendered lines, in order."""
    out = []
    for ln in lines:
        for pair in _PAIRS:
            if f"{pair['code']}:" in ln:
                out.append(pair["code"])
                break
    return out


class TestCaughtUpOrdering:
    def test_sorted_longest_idle_first(self):
        from scheduled.queue_silence import caught_up_campaigns
        lines = caught_up_campaigns(_CFG, _STATE, {}, _NOW)
        assert _codes(lines) == ["C06", "C01", "C05", "C04", "C07", "C00"], (
            "Caught up must read worst-first; this is the reported bug")

    def test_silent_campaigns_excluded_from_caught_up(self):
        from scheduled.queue_silence import caught_up_campaigns
        assert "C09" not in _codes(caught_up_campaigns(_CFG, _STATE, {}, _NOW))

    def test_sub_day_ages_discriminate(self):
        """0h vs 21h must order correctly — `days` is a float, not an int."""
        from scheduled.queue_silence import caught_up_campaigns
        codes = _codes(caught_up_campaigns(_CFG, _STATE, {}, _NOW))
        assert codes.index("C01") < codes.index("C00")


class TestSilentOrdering:
    def test_silent_sorted_longest_first(self):
        from scheduled.queue_silence import silent_campaigns
        state = {"topics": dict(_STATE["topics"])}
        state["topics"]["25059"] = {"last_message_time": _ago(24 * 12)}  # C01 12d
        codes = _codes(silent_campaigns(_CFG, state, {}, _NOW))
        assert codes == ["C01", "C09"], "12d must precede 9d"


class TestOldestCampaignLine:
    def test_names_the_longest_idle_campaign(self):
        from scheduled.queue_silence import oldest_campaign_line
        line = oldest_campaign_line(_CFG, _STATE, {}, _NOW)
        assert "C09" in line, "the 9d silent campaign is the oldest"
        assert "no posts for" in line

    def test_falls_through_to_caught_up_when_nothing_is_silent(self):
        """With C09 gone the oldest is C06 at 4d 2h — a caught-up campaign.

        Worth stating plainly because the original report guessed C01 (21h)
        would be next after C09. It would not: C06 at 4d 2h was sitting in
        the same Caught up list, four rows further down. That mis-read is
        the bug's actual cost — an unsorted list hides the worst entry in
        the middle of the block.
        """
        from scheduled.queue_silence import oldest_campaign_line
        state = {"topics": {k: v for k, v in _STATE["topics"].items()
                            if k != "107171"}}
        cfg = {"group_id": -100,
               "topic_pairs": [p for p in _PAIRS if p["code"] != "C09"]}
        line = oldest_campaign_line(cfg, state, {}, _NOW)
        assert "C06" in line
        assert "quiet for" in line, "caught-up wording, not silent wording"

    def test_none_when_nothing_is_tracked(self):
        from scheduled.queue_silence import oldest_campaign_line
        assert oldest_campaign_line({"group_id": -100, "topic_pairs": []},
                                    {"topics": {}}, {}, _NOW) is None

    def test_campaigns_with_unreplied_entries_are_skipped(self):
        """Those are already in the queue body pointing at themselves."""
        from scheduled.queue_silence import oldest_campaign_line
        scanned = {"107171": {"entries": [{"time": "2026-08-01 00:00:00"}]}}
        line = oldest_campaign_line(_CFG, _STATE, scanned, _NOW)
        assert "C09" not in line
        assert "C06" in line, "next-oldest takes over"


class TestCaughtUpMessageWiring:
    def test_oldest_line_is_appended(self):
        from scheduled.queue_caught_up import post_caught_up
        sent = {}

        def fake(state, gid, topic, msgs, pin=True):
            sent["text"] = msgs[0]
            return True, 1

        import scheduled.queue_caught_up as mod
        real = mod.post_and_persist
        mod.post_and_persist = fake
        try:
            post_caught_up({}, -100, 1, ["  line"], "🕰️ Oldest campaign: C09")
        finally:
            mod.post_and_persist = real
        assert "Oldest campaign" in sent["text"]

    def test_omitted_when_none(self):
        from scheduled.queue_caught_up import post_caught_up
        sent = {}

        def fake(state, gid, topic, msgs, pin=True):
            sent["text"] = msgs[0]
            return True, 1

        import scheduled.queue_caught_up as mod
        real = mod.post_and_persist
        mod.post_and_persist = fake
        try:
            post_caught_up({}, -100, 1, ["  line"], None)
        finally:
            mod.post_and_persist = real
        assert "Oldest campaign" not in sent["text"]
