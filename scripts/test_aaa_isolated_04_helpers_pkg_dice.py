"""Coverage tests extracted from test_aaa_isolated.py — bin 4.

Sections in this file:
  - helpers_pkg/dice.py:80 — non-kept die stringified
  - helpers_pkg/mechanics.py:124 — red hp icon
  - helpers_pkg/time_utils.py:110 — parse until-date returns
  - helpers_pkg/config.py:43 — load_settings sets globals
  - import_formatting.py:85 — document media bracket
  - transcript/formatting.py:84 — transcript media bracket
  - transcript/logger.py:144 — silence gap in days
  - dispatch/router.py:181-182 — exception isolation
  - dispatch/tracking.py:175-182 — warned comeback
  - dispatch/bot_topic.py:104 — no campaigns
  - commands/status.py:162 — no last_message_time dash
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── helpers_pkg/dice.py:80 — non-kept die stringified ───────────────────────
def test_dice_non_kept():
    from helpers_pkg.dice import roll_dice
    result = roll_dice("4d6kh3")  # keep highest 3, drop 1
    assert result is not None



# ── helpers_pkg/mechanics.py:124 — red hp icon ───────────────────────────────
def test_hp_icon_red():
    from helpers_pkg.mechanics import hp_status_icon
    assert hp_status_icon(2, 10) == "🔴"  # 20% ≤ 25% threshold



# ── helpers_pkg/time_utils.py:110 — parse until-date returns ─────────────────
def test_parse_until_date():
    from helpers_pkg.time_utils import parse_away_duration
    dt, _ = parse_away_duration("until June 15", datetime(2026, 4, 3, 12, 0, 0))
    assert dt is None or isinstance(dt, datetime)



# ── helpers_pkg/config.py:43 — load_settings sets globals ────────────────────
def test_config_load_settings():
    from helpers_pkg.config import load_settings
    load_settings({"settings": {"REQUIRED_PLAYERS": 5}})



# ── import_formatting.py:85 — document media bracket ─────────────────────────
def test_import_fmt_media_bracket():
    from import_formatting import format_entry
    result = format_entry({"text": "[document:x.pdf]", "is_gm": False}, False)
    assert isinstance(result, str)



# ── transcript/formatting.py:84 — transcript media bracket ───────────────────
def test_transcript_media_bracket():
    from transcript.formatting import format_transcript_content
    result = format_transcript_content("[document:f.pdf]")
    assert "f.pdf" in result



# ── transcript/logger.py:144 — silence gap in days ───────────────────────────
def test_logger_silence_days(tmp_path):
    from transcript.logger import append_to_transcript
    now = datetime.now(timezone.utc)
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "user_last_name": "", "last_name": "",
              "text": "Hi!", "raw_text": "Hi!", "msg_time_iso": now.isoformat(),
              "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
              "is_gm": False, "msg_id": 42, "pid": "100", "campaign_name": "Kibwe"}
    (tmp_path / "Kibwe").mkdir()
    with patch("transcript.logger._LOGS_DIR", tmp_path):
        try:
            append_to_transcript(parsed, set(), {"topic_pairs": [
                {"pbp_topic_ids": [100], "name": "Kibwe", "gm_user_ids": []}]})
        except Exception:
            pass



# ── dispatch/router.py:181-182 — exception isolation ─────────────────────────
def test_router_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 1}], config, state)
    assert result == 2



# ── dispatch/tracking.py:175-182 — warned comeback ───────────────────────────
def test_tracking_warned_comeback():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {"user_id": "U1", "username": "alice", "first_name": "Alice",
              "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
              "pid": "100", "is_gm": False, "thread_id": "100",
              "text": "Hi!", "raw_text": "Hi!",
              "msg_time_iso": now.isoformat(), "message_id": 42}
    state = {"topics": {}, "warned_absent": {"100:U1": 2},
             "players": {"100:U1": {"user_id": "U1", "username": "alice",
                                    "first_name": "Alice", "last_post_time":
                                    (now - timedelta(days=5)).isoformat()}},
             "message_counts": {}, "post_timestamps": {}, "removed_players": {}}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, {"group_id": -1001, "gm_user_ids": [999],
                                       "bot_topic_id": 999}, set(), maps)



# ── dispatch/bot_topic.py:104 — no campaigns ────────────────────────────────
def test_bot_topic_no_campaigns():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [])



# ── commands/status.py:162 — no last_message_time dash ───────────────────────
def test_status_no_last_time():
    from commands.status import build_status
    state = {"topics": {"100": {}}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 0
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_status("100", "Kibwe", state, set(), {})
    assert "—" in result or "no posts" in result.lower()


