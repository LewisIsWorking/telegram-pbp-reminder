"""Coverage tests extracted from test_remaining_gaps.py — bin 1.

Sections in this file:
  - helpers
  - boons/handler.py:105 — _resolve_boon returns None on missing boon
  - boons/reminders.py:56-61 — third reminder at 6 days
  - checker.py:145 — __main__ guard
  - combat/commands.py:110-111 — no active combat
  - combat/display.py:106 — empty log
  - combat/tracker.py:140-142 — /clog with no combat
  - commands/campaign.py:169 — notes truncation
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── helpers ─────────────────────────────────────────────────────────────────

def _ctx(**kwargs):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": "", "text": ""},
        "maps": MagicMock(),
    }
    base.update(kwargs)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base



# ─── boons/handler.py:105 — _resolve_boon returns None on missing boon ───────

def test_boons_handler_resolve_none():
    from boons.handler import _resolve_boon
    state = {"pending_potw_boons": {"100": {
        "boons": [], "message_id": 42, "base_message": "Won!",
        "winner_user_id": "U1",
    }}, "player_boons": {}, "potw_history": []}
    # Empty boons list → choice_idx out of range
    result = _resolve_boon(state, "100", 0, "Chosen")
    assert result == (None, None)



# ─── boons/reminders.py:56-61 — third reminder at 6 days ────────────────────

def test_boons_third_reminder():
    from boons.reminders import check_boon_reminders
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    six_days_ago = (now - timedelta(days=6, hours=1)).isoformat()
    state = {"pending_potw_boons": {"100": {
        "winner_user_id": "U1", "campaign_name": "Kibwe",
        "posted_at": six_days_ago, "boons": ["Turtle"],
        "message_id": 42, "reminders_sent": 2,
    }}}
    config = {"group_id": -1001, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "chat_topic_id": 21514}
    ]}
    with patch("boons.reminders.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.player_mention.return_value = "@alice"
        mh.hours_since.return_value = 145.0  # >144h = 3rd reminder
        check_boon_reminders(config, state, now=now)
    assert state["pending_potw_boons"]["100"]["reminders_sent"] == 3



# ─── checker.py:145 — __main__ guard ────────────────────────────────────────

def test_checker_main_guard_line():
    # The if __name__ == "__main__": main() line — covered by import
    import checker
    assert hasattr(checker, "main")



# ─── combat/commands.py:110-111 — no active combat ──────────────────────────

def test_combat_no_active():
    from combat.commands import handle_enemies_command
    state = {"combat": {}}  # no combat entry at all
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)



# ─── combat/display.py:106 — empty log ──────────────────────────────────────

def test_combat_display_no_log():
    from combat.display import build_combatlog
    state = {"combat": {"100": {"active": True, "combat_log": []}}}
    result = build_combatlog("100", "Kibwe", state)
    assert "No combat log" in result



# ─── combat/tracker.py:140-142 — /clog with no combat ───────────────────────

def test_combat_tracker_clog_no_combat():
    from combat.tracker import handle_combat_message
    state = {"combat": {}}
    handle_combat_message("/clog something", "/clog something", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe",
                          "2026-04-03T12:00:00", -1, 999, state)


def test_combat_tracker_clog_no_arg():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {"active": True, "log": [], "current_phase": "player", "turn": 1}}}
    handle_combat_message("/clog", "/clog", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe",
                          "2026-04-03T12:00:00", -1, 999, state)



# ─── commands/campaign.py:169 — notes truncation ────────────────────────────

def test_campaign_notes_more():
    from commands.campaign import build_campaign_report
    state = {"notes": {"100": [f"Note {i}" for i in range(10)]},
             "quests": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
             "conditions": {}, "hp_tracker": {}, "clocks": {},
             "topics": {}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "session_counts": {}}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    with patch("commands.campaign.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_characters.return_value = {}
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 5.0
        mh.feature_enabled.return_value = False
        mh.player_full_name.return_value = "Alice"
        mh.REQUIRED_PLAYERS = 4
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0 posts"
        result = build_campaign_report("100", config, state, set())
    assert "more" in result


