"""Coverage tests extracted from test_final_coverage.py — bin 5.

Sections in this file:
  - helpers_pkg/time_utils.py — parse_away_date
  - helpers_pkg/time_utils.py — parse_away_date
  - until pattern — may parse or return None, but must not raise
  - Misc single-line gaps
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.reports import post_roster_summary


@patch("scheduled.reports.helpers")
def test_roster_posts_active_player(mock_helpers):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(hours=h)).isoformat() for h in range(5)]
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    )
    mock_helpers.players_by_campaign.return_value = {"100": [
        {"user_id": "U1", "first_name": "Alice", "username": "alice"}
    ]}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_label.return_value = "C00: Kibwe"
    mock_helpers.get_topic_timestamps.return_value = {"U1": ts}
    mock_helpers.get_characters.return_value = {"U1": "Amara"}
    mock_helpers.player_full_name.return_value = "Alice"
    mock_helpers.REQUIRED_PLAYERS = 4
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999],
                               "chat_topic_id": 21514}]}
    state = {"last_roster": {}, "message_counts": {"100": {"U1": 50}},
             "player_registry": {}}
    with patch("commands.campaign.roster_user_stats", return_value={}), \
         patch("commands.campaign.roster_block", return_value="Alice block"):
        post_roster_summary(config, state, now=now)



# ═══════════════════════════════════════════════════════════════════════════════
# helpers_pkg/time_utils.py — parse_away_date

# ═══════════════════════════════════════════════════════════════════════════════

from helpers_pkg.time_utils import parse_away_duration


def test_parse_away_duration_days():
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("3 days holiday", now)
    assert dt is not None
    assert "holiday" in reason


def test_parse_away_duration_weeks():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("2 weeks vacation", now)
    assert dt is not None


def test_parse_away_duration_until():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    # until pattern — may parse or return None, but must not raise
    result = parse_away_duration("until May 1 vacation", now)
    assert isinstance(result, tuple)


def test_parse_away_duration_reason_only():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("family stuff", now)
    assert dt is None
    assert "family" in reason



# ═══════════════════════════════════════════════════════════════════════════════
# Misc single-line gaps
