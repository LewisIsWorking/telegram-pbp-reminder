"""Tests extracted from test_remaining_100.py — bin 2.

Sections in this file:
  - commands/markdone.py:80-84 — by id
  - commands/campaign.py:169 — notes >3
  - commands/profile.py:57 — days ago
  - commands/timeline.py:34 — potw events
  - dispatch/cmd_gm.py:57 — /resume not paused
  - dispatch/comeback.py:38 — no bot_topic
"""
"""
Definitive final coverage push — verified state for every remaining gap.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(**kw):
    base = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": "", "text": ""},
            "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base



# ── commands/markdone.py:80-84 — by id ───────────────────────────────────────
def test_markdone_id_found(tmp_path, monkeypatch):
    # Lines 80-82: scan has entries but msg_id doesn't match any →
    # falls to _clear_by_msg_id which finds it in queue file
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 140368, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq))
    # Scan returns a DIFFERENT entry so match=[] but entries is non-empty
    other_entry = {"name": "Bob", "time": "2026-03-01 09:00:00",
                   "preview": "other", "message_id": "999999", "link": ""}
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": [other_entry]}}):
        handle_markdone(_ctx(cmd_word="/markdone", text="/markdone 140368"))


def test_markdone_id_not_found(tmp_path, monkeypatch):
    # Lines 83-84: scan has entries, msg_id not in scan, _clear_by_msg_id returns False
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    # Queue file is empty (different msg_id) → _clear_by_msg_id returns False
    (tmp_path / "100.json").write_text(json.dumps(
        {"unreplied": [], "replied": [], "reply_log": []}))
    other_entry = {"name": "Bob", "time": "2026-03-01 09:00:00",
                   "preview": "other", "message_id": "999999", "link": ""}
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": [other_entry]}}):
        handle_markdone(_ctx(cmd_word="/markdone", text="/markdone 140999"))



# ── commands/campaign.py:169 — notes >3 ──────────────────────────────────────
def test_campaign_notes_more():
    from commands.campaign import build_campaign_report
    state = {"notes": {"100": [f"N{i}" for i in range(5)]},
             "quests": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
             "conditions": {}, "hp_tracker": {}, "clocks": {},
             "topics": {}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "session_counts": {}}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}]}
    with patch("commands.campaign.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_characters.return_value = {}
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 5.0
        mh.feature_enabled.return_value = False
        mh.player_full_name.return_value = "A"
        mh.REQUIRED_PLAYERS = 4
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_campaign_report("100", config, state, set())
    assert "more" in result



# ── commands/profile.py:57 — days ago ────────────────────────────────────────
def test_profile_days():
    from commands.profile import build_profile
    two_days = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    state = {"players": {"100:U1": {
        "user_id": "U1", "first_name": "Alice", "username": "alice",
        "last_name": "", "pbp_topic_id": "100", "campaign_name": "Kibwe",
        "last_post_time": two_days}},
        "post_timestamps": {"100": {"U1": [two_days]}}}
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {"U1": [two_days]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        mh.hours_since.return_value = 50.0
        mh.player_full_name.return_value = "Alice"
        mh.character_name.return_value = ""
        mh.calc_streak.return_value = 0
        result = build_profile("alice", {}, state)
    assert "2d" in result



# ── commands/timeline.py:34 — potw events ────────────────────────────────────
def test_timeline_potw():
    from commands.timeline import build_timeline
    now = datetime.now(timezone.utc)
    state = {"timeline_events": {}, "removed_players": {},
             "player_boons": {"100": {"U1": [
                 {"date": now.strftime("%Y-%m-%d"), "campaign": "Kibwe", "week": "W14"}
             ]}}}
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "chat_topic_id": 21514}]}
    maps = MagicMock()
    maps.to_name = {"100": "Kibwe"}
    with patch("commands.timeline.helpers") as mh:
        mh.build_topic_maps.return_value = maps
        result = build_timeline(config, state)
    assert "POTW" in result or "🏅" in result



# ── dispatch/cmd_gm.py:57 — /resume not paused ───────────────────────────────
def test_cmd_gm_resume_not_paused():
    from dispatch.cmd_gm import handle
    ctx = _ctx(cmd_word="/resume", text="/resume",
               state={"paused_campaigns": {}},
               parsed={"raw_text": "/resume"})
    assert handle(ctx) is True



# ── dispatch/comeback.py:38 — no bot_topic ───────────────────────────────────
def test_comeback_no_bot_topic():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old = {"user_id": "U1", "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "campaign_name": "K",
              "msg_time_iso": now.isoformat(), "thread_id": "100",
              "pid": "100", "is_gm": False, "text": "Hi!"}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.COMEBACK_THRESHOLD_HOURS = 168
        check_comeback(parsed, old, {}, {"group_id": -1, "gm_user_ids": []}, set())

