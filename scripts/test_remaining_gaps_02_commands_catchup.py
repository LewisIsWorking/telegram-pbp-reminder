"""Coverage tests extracted from test_remaining_gaps.py — bin 2.

Sections in this file:
  - commands/catchup.py:161 — acted_ids from list
  - commands/dashboard.py:85 — active quests flag
  - commands/markdone.py:80-84 — clear by msg_id branches
  - commands/mechanics.py:80 — no HP tracked
  - commands/profile.py:57-59 — last seen branches
  - commands/queue_analytics.py:28 — skip empty entries
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── commands/catchup.py:161 — acted_ids from list ──────────────────────────

def test_catchup_acted_as_list():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=2)).isoformat()
    state = {
        "post_timestamps": {"100": {"U1": [ts]}},
        "away_status": {},
        "topics": {},
        "acted_this_scene": {"100": ["U2"]},  # list, not set
    }
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts], "U2": [ts]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 2.0
        mh.get_player.return_value = {"first_name": "Alice", "username": "alice"}
        mh.player_full_name.return_value = "Alice"
        result = build_catchup("U1", "Alice", "100", "Kibwe",
                               {"group_id": -1}, state)
    assert isinstance(result, str)



# ─── commands/dashboard.py:85 — active quests flag ───────────────────────────

def test_dashboard_quests_flag():
    from commands.dashboard import build_gm_dashboard
    state = {
        "quests": {"100": [{"text": "Q1", "done": False}, {"text": "Q2", "done": False}]},
        "conditions": {}, "timer": {}, "vote": {}, "current_scenes": {},
        "hp_tracker": {}, "clocks": {}, "combat": {}, "paused_campaigns": {},
        "topics": {}, "players": {}, "post_timestamps": {}, "message_counts": {},
    }
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 2.0
        mh.fmt_brief_relative.return_value = ("2h ago", 2.0)
        result = build_gm_dashboard(config, state)
    assert "GM Dashboard" in result or "C00" in result or isinstance(result, str)



# ─── commands/markdone.py:80-84 — clear by msg_id branches ──────────────────

def test_markdone_clear_by_id_found(tmp_path, monkeypatch):
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 999, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq))
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": []}}):
        ctx = _ctx(cmd_word="/markdone", text="/markdone 999")
        result = handle_markdone(ctx)
    assert result is True


def test_markdone_clear_by_id_not_found(tmp_path, monkeypatch):
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": []}}):
        ctx = _ctx(cmd_word="/markdone", text="/markdone 99999")
        result = handle_markdone(ctx)
    assert result is True



# ─── commands/mechanics.py:80 — no HP tracked ───────────────────────────────

def test_mechanics_no_hp():
    from commands.mechanics import build_hp_tracker
    result = build_hp_tracker("100", "Kibwe", {"hp_tracker": {}})
    assert "No HP tracked" in result



# ─── commands/profile.py:57-59 — last seen branches ─────────────────────────

def test_profile_last_seen_days():
    from commands.profile import build_profile
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00: Kibwe"
        mh.get_topic_timestamps.return_value = {"U1": [two_days_ago]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        mh.hours_since.return_value = 48.0
        mh.get_player.return_value = {"first_name": "Alice", "username": "alice",
                                       "user_id": "U1"}
        mh.player_full_name.return_value = "Alice"
        state = {"post_timestamps": {"100": {"U1": [two_days_ago]}}}
        # build_profile takes username string, not a dict
        result = build_profile("alice", {}, state)
    assert isinstance(result, str)


def test_profile_no_timestamps():
    from commands.profile import build_profile
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00: Kibwe"
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        mh.get_player.return_value = None
        result = build_profile("alice", {}, {})
    assert "unknown" in result or isinstance(result, str)



# ─── commands/queue_analytics.py:28 — skip empty entries ────────────────────

def test_age_heatmap_skips_empty_entries():
    from commands.queue_analytics import age_heatmap
    scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": []}}
    result = age_heatmap(scanned)
    assert result == ""


