"""
Integration tests for campaign_table.py.

Covers HTML structure, column alignment, and full build_campaign_table output.
Unit tests for helper functions live in test_campaign_table_unit.py.
"""

import sys
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from scheduled.campaign_table import (
    build_campaign_table,
    _HEADER,
    _ROW,
)

# ── Shared fixtures ────────────────────────────────────────────────────────────

NOW       = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
RECENT_TS = (NOW - timedelta(hours=2)).isoformat()
STALE_TS  = (NOW - timedelta(days=8)).isoformat()  # outside 7-day window


def _make_config(pairs: list[dict] | None = None) -> dict:
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


def _make_state(topic_ts: dict | None = None) -> dict:
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
def test_header_inside_pre(mock_scan):
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    pre_content = result.split("<pre>")[1].split("</pre>")[0]
    for col in ("Campaign", "Code", "Act", "Week", "Last"):
        assert col in pre_content


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
    assert "&lt;1d" in post_pre   # < must be HTML-escaped


# ── Column alignment ───────────────────────────────────────────────────────────

def test_header_prefix_is_three_spaces():
    """Header must start with 3 spaces to align under emoji+space data rows."""
    header = _HEADER.format("Campaign", "Code", "Act", "Week", "Last")
    assert header.startswith("   "), f"Expected 3-space prefix, got: {header!r}"


def test_row_name_padded_to_18():
    """Name field is left-aligned and padded to exactly 18 chars."""
    row = _ROW.format("🟢", "Short", "C00", 3, 42, "1d", "")
    name_field = row[2:20]   # skip emoji (1 char) + space (1 char)
    assert len(name_field) == 18
    assert name_field.startswith("Short")


def test_header_and_row_name_column_align():
    """Campaign header column aligns visually with name data column."""
    header = _HEADER.format("Campaign", "Code", "Act", "Week", "Last")
    row    = _ROW.format("🟢", "Kibwe", "C06", 7, 125, "0h", "")
    assert header[3] == "C"   # 'C' of Campaign
    assert row[2] == "K"      # 'K' of Kibwe


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
    # Only 2 active players for C00 (non-hybrid), below REQUIRED_PLAYERS=6
    result = build_campaign_table(_make_config(), _make_state(), now=NOW)
    assert "⚠️" in result


@patch("commands.queue_scan.scan_transcripts", side_effect=_scan_empty)
def test_no_warning_for_hybrid_only_camps(mock_scan):
    """If the only understaffed campaign is hybrid, no warning should appear."""
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
