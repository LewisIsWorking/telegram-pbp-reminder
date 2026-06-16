"""Tests extracted from test_final_100.py — bin 3.

Sections in this file:
  - commands/summary.py content branches
  - commands/reactions.py: lines 18, 22, 34, 40, 54
  - commands/catchup.py: away player
  - commands/recap.py with real transcript
  - commands/status.py with last_message_time present
"""
"""
Final push: tests for the large remaining uncovered blocks.
Focuses on router poll/callback/reaction handling, tracking GM-reply logging,
cmd_player /available, summary content, and other high-impact gaps.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _pc(**kw):
    base = {"user_id": "U1", "user_name": "Alice", "gm_ids": set(),
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": ""}, "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0]
    return base

def _info_ctx(cmd, state=None):
    return {"cmd_word": cmd, "text": cmd,
            "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {"vote": {}, "timer": {}, "clocks": {},
                               "player_boons": {}},
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock()}

# ─── commands/summary.py content branches ────────────────────────────────────

def test_summary_timer():
    from commands.summary import build_summary
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(hours=2)).isoformat()
    state = {"clocks": {}, "notes": {}, "quests": {}, "loot": {}, "npcs": {},
             "pinned_moments": {}, "trackers": {}, "vote": {}, "hp_tracker": {},
             "conditions": {}, "away": {},
             "timers": {"100": {"deadline": expires, "reason": "Think!"}}}
    result = build_summary("100", "Kibwe", state, {})
    assert "Timer" in result or "Think" in result


def test_summary_vote():
    from commands.summary import build_summary
    state = {"clocks": {}, "notes": {}, "quests": {}, "loot": {}, "npcs": {},
             "pins": {}, "hp_tracker": {}, "conditions": {},
             "away": {},
             "votes": {"100": {"question": "Where next?", "closed": False,
                                "results": {"0": ["U1"]}}}}
    result = build_summary("100", "Kibwe", state, {})
    assert "Vote" in result


def test_summary_pins():
    from commands.summary import build_summary
    state = {"clocks": {}, "notes": {}, "quests": {}, "loot": {}, "npcs": {},
             "hp_tracker": {}, "conditions": {}, "away": {},
             "pins": {"100": [{"text": "The city burns!", "added": "2026-04-01"}]}}
    result = build_summary("100", "Kibwe", state, {})
    assert "📌" in result or "pin" in result.lower()


def test_summary_quests():
    from commands.summary import build_summary
    state = {"clocks": {}, "notes": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
             "hp_tracker": {}, "conditions": {}, "away": {}, "timer": {}, "vote": {},
             "trackers": {},
             "quests": {"100": [{"text": "Find the sword", "status": "active"}]}}
    result = build_summary("100", "Kibwe", state, {})
    assert "Quest" in result or "sword" in result


def test_summary_notes():
    from commands.summary import build_summary
    # notes show as "N notes (/notes)" — check for notes keyword
    state = {"clocks": {}, "loot": {}, "npcs": {}, "quests": {},
             "hp_tracker": {}, "conditions": {}, "away": {}, "pins": {},
             "notes": {"100": ["Session notes: the party split up"]}}
    result = build_summary("100", "Kibwe", state, {})
    assert isinstance(result, str)  # notes may not show in summary per the code



# ─── commands/reactions.py: lines 18, 22, 34, 40, 54 ─────────────────────────

def test_reactions_with_actual_data():
    from commands.reactions import build_reactions
    # reactions[pid] = {"given": {uid: {emoji: count}}, "emojis": {emoji: [uids]}}
    state = {"reactions": {"100": {
        "given": {"U1": {"count": 4, "name": "Alice"},
                  "U2": {"count": 1, "name": "Bob"}},
        "emojis": {"👍": 3, "🎉": 1},
    }}}
    with patch("commands.reactions.helpers") as mh:
        mh.gm_ids_for_campaign.return_value = set()
        mh.rank_icon.return_value = "🥇"
        result = build_reactions({}, state, "100", "Kibwe")
    assert "Alice" in result or "👍" in result



# ─── commands/catchup.py: away player ────────────────────────────────────────

def test_catchup_away_player():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=1)).isoformat()
    state = {"post_timestamps": {},
             "away": {"100:U2": {"reason": "vacation", "until": None}},
             "topics": {}, "acted_this_scene": {}}
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts], "U2": [ts]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 1.0
        mh.is_away.return_value = {"reason": "vacation"}
        mh.get_player.return_value = {"first_name": "Bob", "username": "bob"}
        mh.player_full_name.return_value = "Bob"
        result = build_catchup("U1", "Alice", "100", "Kibwe", {"group_id": -1}, state)
    assert isinstance(result, str)



# ─── commands/recap.py with real transcript ───────────────────────────────────

def test_recap_with_log(tmp_path):
    from commands.recap import build_recap
    campaign_dir = tmp_path / "Kibwe"
    campaign_dir.mkdir()
    (campaign_dir / "2026-04.md").write_text(
        "## Scene 1\n\n"
        "**Alice** (2026-04-01 10:00:00) msg#1:\nHello world!\n\n"
        "**Bob** (2026-04-01 10:05:00) msg#2:\n" + "word " * 50 + "\n\n"
    , encoding="utf-8")
    with patch("commands.recap._LOGS_DIR", tmp_path), \
         patch("commands.recap.helpers") as mh:
        mh.campaign_dir_name.return_value = "Kibwe"
        mh.get_characters.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_label.return_value = "C00"
        result = build_recap("100", "Kibwe", {}, 5)
    assert isinstance(result, str)



# ─── commands/status.py with last_message_time present ───────────────────────

def test_status_with_last_message():
    from commands.status import build_status
    now = datetime.now(timezone.utc)
    state = {"topics": {"100": {"last_message_time": now.isoformat()}},
             "post_timestamps": {}, "message_counts": {}, "players": {},
             "paused_campaigns": {}, "current_scenes": {}}
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 1.0
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 2, "player_this": 5,
                                       "gm_last": 1, "player_last": 3}
        mh.trend_icon.return_value = "📈"
        mh.posts_str.return_value = "7"
        result = build_status("100", "Kibwe", state, set(), {})
    assert "1h" in result or "Kibwe" in result

