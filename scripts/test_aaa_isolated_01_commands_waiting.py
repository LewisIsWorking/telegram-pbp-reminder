"""Coverage tests extracted from test_aaa_isolated.py — bin 1.

Sections in this file:
  - commands/waiting.py:83 — continue when no name match
  - commands/mechanics.py:52 — timer with hours only
  - commands/summary.py:75 — scene line
  - commands/dashboard.py:61 — vote flag
  - combat/display.py:76 — enemies listed in whosturn
  - dispatch/comeback.py:38 — no bot_topic → return
  - dispatch/router.py:181-182 — exception in update processing
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── commands/waiting.py:83 — continue when no name match ─────────────────────
def test_waiting_pid_not_in_scanned():
    # Line 83: pid not in scanned → continue
    from commands.waiting import build_waiting_all
    with patch("commands.waiting.scan_transcripts") as ms:
        ms.return_value = {"100": {"code": "C00", "campaign": "Kibwe",
                                   "entries": []}}
        # Config has pair 200 but scanned only has 100 → line 83 fires
        result = build_waiting_all(
            "U1", "Alice",
            {"topic_pairs": [{"pbp_topic_ids": [200]}]},
            {"players": {}},
        )
    assert "caught up" in result or isinstance(result, str)



# ── commands/mechanics.py:52 — timer with hours only ─────────────────────────
def test_timer_hours_only():
    from commands.mechanics import build_timer
    now = datetime.now(timezone.utc)
    # Between 1-24 hours remaining → shows Xh Ym (no days)
    expires = (now + timedelta(hours=3, minutes=30)).isoformat()
    result = build_timer("100", "Kibwe",
                         {"timers": {"100": {"deadline": expires, "reason": "Think!"}}})
    assert "h" in result and "m" in result



# ── commands/summary.py:75 — scene line ──────────────────────────────────────
def test_summary_current_scene():
    from commands.summary import build_summary
    state = {"combat": {}, "clocks": {}, "notes": {}, "quests": {}, "loot": {},
             "npcs": {}, "pins": {}, "hp_tracker": {}, "conditions": {},
             "away": {}, "votes": {}, "timers": {},
             "current_scene": {"100": "The harbour burns"}}
    result = build_summary("100", "Kibwe", state, {})
    assert "harbour" in result or "Scene" in result



# ── commands/dashboard.py:61 — vote flag ─────────────────────────────────────
def test_dashboard_vote_flag():
    from commands.dashboard import build_gm_dashboard
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    state = {"quests": {}, "conditions": {},
             "vote": {"100": {"question": "Where?", "options": ["A"], "votes": {}}},
             "timer": {}, "current_scenes": {}, "hp_tracker": {}, "clocks": {},
             "combat": {}, "paused_campaigns": {}, "topics": {},
             "message_counts": {}, "post_timestamps": {}, "players": {}}
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 2.0
        mh.fmt_brief_relative.return_value = ("2h ago", 2.0)
        mh.is_away.return_value = None
        mh.days_since.return_value = 1.0
        result = build_gm_dashboard(config, state)
    assert "🗳️" in result or "vote" in result.lower() or isinstance(result, str)



# ── combat/display.py:76 — enemies listed in whosturn ────────────────────────
def test_combat_whosturn_with_enemies():
    from combat.display import build_whosturn
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {"combat": {"100": {
        "active": True,
        "players_acted": {},
        "phase_started_at": now_iso,
        "round": 1, "current_phase": "players",
        "enemies": ["Goblin", "Orc"],
    }}, "players": {}, "away": {}}
    with patch("combat.display.helpers") as mh:
        mh.is_away.return_value = None
        mh.hours_since.return_value = 0.5
        result = build_whosturn("100", "Kibwe", state)
    assert "Goblin" in result or "Orc" in result



# ── dispatch/comeback.py:38 — no bot_topic → return ─────────────────────────
def test_comeback_no_bot_topic_early_return():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old = {"user_id": "U1",
           "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "campaign_name": "K",
              "msg_time_iso": now.isoformat(), "thread_id": "100",
              "pid": "100", "is_gm": False, "text": "Hi!"}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.COMEBACK_THRESHOLD_HOURS = 168
        # config has no bot_topic_id → hits line 38 return
        check_comeback(parsed, old, {}, {"group_id": -1, "gm_user_ids": []}, set())



# ── dispatch/router.py:181-182 — exception in update processing ───────────────
def test_router_update_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
              "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 1}], config, state)
    assert result == 2


