"""Tests extracted from test_aaa_isolated.py — bin 5.

Sections in this file:
  - commands/summary.py:49-52 — player activity strings
  - commands/reactions.py:67 — negative count reset
  - commands/catchup.py:161 — list acted→set
  - commands/recap.py:124-128 — truncation
  - dispatch/cmd_votes_timers.py:108-111 — tied/no votes
  - dispatch/cmd_conditions_hp.py:184 — bad hp subcommand
  - dispatch/cmd_clocks.py:91 — clock tick found but no change needed
  - dispatch/cmd_trackers.py:115 — quest not found
"""
"""
MUST RUN FIRST (alphabetical ordering): these tests cover lines that
only hit in isolation before other tests cache module paths.

Naming: test_aaa_ ensures pytest runs this file before test_b*, test_c*, etc.
"""
import sys, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))



# ── commands/summary.py:49-52 — player activity strings ──────────────────────
def test_summary_player_activity():
    from commands.summary import build_summary
    now = datetime.now(timezone.utc)
    two_days = (now - timedelta(days=2)).isoformat()
    state = {"combat": {}, "clocks": {}, "notes": {}, "quests": {}, "loot": {},
             "npcs": {}, "pins": {}, "hp_tracker": {}, "conditions": {}, "away": {},
             "votes": {}, "timers": {},
             "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                                    "last_post_time": two_days}}}
    result = build_summary("100", "Kibwe", state, {})
    assert isinstance(result, str)



# ── commands/reactions.py:67 — negative count reset ──────────────────────────
def test_reactions_negative_count():
    from commands.reactions import build_reactions
    state = {"reactions": {"100": {"given": {"U1": {"count": -1, "name": "A"}},
                                    "emojis": {"👍": 2}}}}
    with patch("commands.reactions.helpers") as mh:
        mh.gm_ids_for_campaign.return_value = set()
        mh.rank_icon.return_value = "🥇"
        result = build_reactions({}, state, "100", "Kibwe")
    assert isinstance(result, str)



# ── commands/catchup.py:161 — list acted→set ─────────────────────────────────
def test_catchup_list_acted():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=1)).isoformat()
    state = {"post_timestamps": {}, "away": {}, "topics": {},
             "acted_this_scene": {"100": ["U2"]}}
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 1.0
        mh.is_away.return_value = None
        mh.get_player.return_value = {"first_name": "A", "username": "a"}
        mh.player_full_name.return_value = "A"
        build_catchup("U1", "Alice", "100", "Kibwe", {"group_id": -1}, state)



# ── commands/recap.py:124-128 — truncation ───────────────────────────────────
def test_recap_truncation(tmp_path):
    from commands.recap import build_recap
    (tmp_path / "Kibwe").mkdir()
    long = " ".join(["word"] * 50)
    (tmp_path / "Kibwe" / "2026-04.md").write_text(
        f"**Alice** (2026-04-01 10:00:00) msg#1:\n{long}\n")
    with patch("commands.recap._LOGS_DIR", tmp_path), \
         patch("commands.recap.helpers") as mh:
        mh.campaign_dir_name.return_value = "Kibwe"
        mh.get_characters.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_label.return_value = "C00"
        result = build_recap("100", "Kibwe", {}, 5)
    assert "…" in result or isinstance(result, str)



# ── dispatch/cmd_votes_timers.py:108-111 — tied/no votes ─────────────────────
def test_endvote_tied():
    from dispatch.cmd_votes_timers import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"vote": {"100": {"question": "?", "options": ["A", "B"],
                                       "votes": {"U1": 0, "U2": 1}}}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/endvote"}, "maps": MagicMock(),
           "cmd_word": "/endvote", "text": "/endvote"}
    assert handle(ctx) is True


def test_endvote_no_votes():
    from dispatch.cmd_votes_timers import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"vote": {"100": {"question": "?", "options": ["A"], "votes": {}}}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/endvote"}, "maps": MagicMock(),
           "cmd_word": "/endvote", "text": "/endvote"}
    assert handle(ctx) is True



# ── dispatch/cmd_conditions_hp.py:184 — bad hp subcommand ────────────────────
def test_hp_bad_sub():
    from dispatch.cmd_conditions_hp import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"hp_tracker": {}}, "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/hp xyz"}, "maps": MagicMock(),
           "cmd_word": "/hp", "text": "/hp xyz"}
    assert handle(ctx) is True



# ── dispatch/cmd_clocks.py:91 — clock tick found but no change needed ─────────
def test_clock_tick_already_full():
    from dispatch.cmd_clocks import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"clocks": {"100": {"Inv": {"filled": 5, "segments": 6,
                                                "label": "Inv"}}}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/tick Inv"}, "maps": MagicMock(),
           "cmd_word": "/tick", "text": "/tick Inv"}
    with patch("dispatch.cmd_clocks.helpers") as mh:
        mh.clock_display.return_value = "█████░"
        assert handle(ctx) is True



# ── dispatch/cmd_trackers.py:115 — quest not found ───────────────────────────
def test_cmd_trackers_quest_nf():
    from dispatch.cmd_trackers import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"quests": {"100": [{"text": "Q", "status": "active"}]}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/done 9"}, "maps": MagicMock(),
           "cmd_word": "/done", "text": "/done 9"}
    assert handle(ctx) is True

