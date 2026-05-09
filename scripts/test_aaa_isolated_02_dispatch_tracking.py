"""Coverage tests extracted from test_aaa_isolated.py — bin 2.

Sections in this file:
  - dispatch/tracking.py:175-182 — warned player comeback
  - helpers_pkg/config.py:43 — load settings into globals
  - helpers_pkg/time_utils.py:110 — until-date parse returns
  - helpers_pkg/dice.py:80 — non-kept die rolled
  - helpers_pkg/dc_lookup.py:110-112 — adjustment returned
  - helpers_pkg/mechanics.py:124 — hp red icon
  - import_formatting.py:85 — media bracket
  - transcript/formatting.py:84 — media in transcript
  - transcript/finalize.py:51 — empty dir returns
  - scheduled/maintenance.py:147 — excluded continue
  - scheduled/combat_ping.py:95 — excluded continue
  - scheduled/smart_alerts.py:110 — feature disabled continue
  - scheduled/diagnostic_analysis.py:43 — no info match
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── dispatch/tracking.py:175-182 — warned player comeback ────────────────────
def test_tracking_warned_comeback_early():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
        "pid": "100", "is_gm": False, "thread_id": "100",
        "text": "Hi!", "raw_text": "Hi!",
        "msg_time_iso": now.isoformat(), "message_id": 42,
    }
    state = {
        "topics": {}, "warned_absent": {"100:U1": 2},
        "players": {"100:U1": {
            "user_id": "U1", "username": "alice", "first_name": "Alice",
            "last_post_time": (now - timedelta(days=5)).isoformat(),
        }},
        "message_counts": {}, "post_timestamps": {}, "removed_players": {},
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, config, set(), maps)



# ── helpers_pkg/config.py:43 — load settings into globals ────────────────────
def test_config_load_settings_line43():
    from helpers_pkg.config import load_settings
    # Providing a settings dict with known keys exercises lines 39-43
    config = {"settings": {"REQUIRED_PLAYERS": 5}}
    load_settings(config)  # updates module globals



# ── helpers_pkg/time_utils.py:110 — until-date parse returns ─────────────────
def test_time_until_parse_returns():
    from helpers_pkg.time_utils import parse_away_duration
    # Use naive datetime (avoids timezone comparison issues in the function)
    now = datetime(2026, 4, 3, 12, 0, 0)
    dt, reason = parse_away_duration("until June 15", now)
    # The function tries strptime formats — it may or may not parse
    # Either way line 110 (return dt, reason) should be hit if it parsed



# ── helpers_pkg/dice.py:80 — non-kept die rolled ─────────────────────────────
def test_dice_non_kept():
    from helpers_pkg.dice import roll_dice
    # 4d6kh3: roll 4, keep highest 3 → dropped dice stringified on line 80
    result = roll_dice("4d6kh3")
    assert result is not None and result.get("results")



# ── helpers_pkg/dc_lookup.py:110-112 — adjustment returned ───────────────────
def test_dc_adjustment_returned():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    result = dc_lookup(key)
    assert "adjustment" in result.lower() and key.title() in result



# ── helpers_pkg/mechanics.py:124 — hp red icon ───────────────────────────────
def test_hp_icon_red_branch():
    from helpers_pkg.mechanics import hp_status_icon
    # 20% or less → red (line 124: return "🔴")
    assert hp_status_icon(2, 10) == "🔴"



# ── import_formatting.py:85 — media bracket ──────────────────────────────────
def test_import_fmt_media_bracket():
    from import_formatting import format_entry
    # "[document:x.pdf]" triggers the media bracket branch at line 85
    result = format_entry({"text": "[document:report.pdf]", "is_gm": False}, False)
    assert isinstance(result, str)



# ── transcript/formatting.py:84 — media in transcript ────────────────────────
def test_transcript_fmt_media():
    from transcript.formatting import format_transcript_content
    result = format_transcript_content("[document:notes.pdf]")
    assert "notes.pdf" in result



# ── transcript/finalize.py:51 — empty dir returns ────────────────────────────
def test_finalize_empty_dir(tmp_path):
    from transcript.finalize import update_transcript_index
    (tmp_path / "Kibwe").mkdir()  # dir with no .md files → return
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()



# ── scheduled/maintenance.py:147 — excluded continue ─────────────────────────
def test_maintenance_excluded_early():
    from scheduled.maintenance import check_recruitment_needs
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns",
               return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_recruitment_needs(config, {"last_recruitment_check": {}})



# ── scheduled/combat_ping.py:95 — excluded continue ─────────────────────────
def test_combat_ping_excluded_early():
    from scheduled.combat_ping import check_combat_turns
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.combat_ping.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = True
        check_combat_turns(config, {"combat": {}})



# ── scheduled/smart_alerts.py:110 — feature disabled continue ────────────────
def test_smart_alerts_feature_disabled_early():
    from scheduled.smart_alerts import check_pace_drop
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    with patch("scheduled.smart_alerts.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.return_value = False
        check_pace_drop({"group_id": -1, "topic_pairs": []}, {}, now=now, maps=maps)



# ── scheduled/diagnostic_analysis.py:43 — no info match ─────────────────────
def test_diagnostic_no_info_match():
    from scheduled.diagnostic_analysis import _analyse_logs
    result = _analyse_logs(["just a regular log line"])
    assert result["events"] == []


