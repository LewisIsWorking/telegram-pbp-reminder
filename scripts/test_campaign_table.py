"""
Tests for campaign_table.py — per-line format (no column alignment).
"""

import sys
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from scheduled.campaign_table import build_campaign_table

NOW       = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
RECENT_TS = (NOW - timedelta(hours=2)).isoformat()
STALE_TS  = (NOW - timedelta(days=8)).isoformat()


def _make_config(pairs=None):
    topic_pairs = pairs or [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Riddleport",
         "gm_user_ids": [999]},
        {"pbp_topic_ids": [101], "code": "C01", "name": "Doomsday Funtime",
         "gm_user_ids": [999], "hybrid_live": True},
    ]
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": topic_pairs,
    }


def _make_state(topic_ts=None):
    ts = topic_ts or {
        "100": {"111": [RECENT_TS], "222": [RECENT_TS]},
        "101": {"333": [RECENT_TS]},
    }
    return {
        "topics": {
            "100": {"last_message_time": RECENT_TS},
            "101": {"last_message_time": STALE_TS},
        },
        "post_timestamps": ts,
    }


def _scan_empty(_config, _state):
    return {}


# ── HTML structure ─────────────────────────────────────────────────────────────

@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_output_contains_pre_block(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert "<pre>" in result
    assert "</pre>" in result


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_campaign_names_in_pre(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    pre_content = result.split("<pre>")[1].split("</pre>")[0]
    assert "Riddleport" in pre_content
    assert "Doomsday Funtime" in pre_content


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_campaign_codes_in_pre(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    pre_content = result.split("<pre>")[1].split("</pre>")[0]
    assert "C00" in pre_content
    assert "C01" in pre_content


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_week_number_in_title(mock_scan):
    week_num = NOW.isocalendar()[1]
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert f"W{week_num}" in result


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_totals_outside_pre(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    post_pre = result.split("</pre>")[1]
    assert "active players" in post_pre
    assert "posts this week" in post_pre


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_legend_outside_pre(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    post_pre = result.split("</pre>")[1]
    assert "&lt;1h" in post_pre  # new 22-tier scale starts with 🆕<1h


# ── Per-line format ────────────────────────────────────────────────────────────

@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_each_campaign_on_own_line(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    pre_content = result.split("<pre>")[1].split("</pre>")[0]
    lines = [l for l in pre_content.strip().split("\n") if l.strip()]
    # One line per campaign
    assert len(lines) == 2


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_line_contains_player_count_and_posts(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    pre_content = result.split("<pre>")[1].split("</pre>")[0]
    assert "p" in pre_content   # player count marker
    assert "/wk" in pre_content  # weekly posts marker


# ── Queue indicator ────────────────────────────────────────────────────────────

@patch("commands.queue_scan.scan_transcripts")
def test_queue_shown_when_entries_present(mock_scan):
    mock_scan.return_value = {"100": {"entries": ["a", "b", "c"]}}
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert "📋3" in result


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_no_queue_indicator_when_empty(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert "📋" not in result


# ── Warning banner ─────────────────────────────────────────────────────────────

@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_warning_shown_for_understaffed_non_hybrid(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert "⚠️" in result


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_no_warning_for_hybrid_only_camps(mock_scan):
    config = _make_config([
        {"pbp_topic_ids": [101], "code": "C01", "name": "Doomsday Funtime",
         "gm_user_ids": [999], "hybrid_live": True},
    ])
    state = {
        "topics": {"101": {"last_message_time": RECENT_TS}},
        "post_timestamps": {"101": {"333": [RECENT_TS]}},
    }
    result = build_campaign_table(config, state, now=NOW)
    assert "⚠️" not in result
