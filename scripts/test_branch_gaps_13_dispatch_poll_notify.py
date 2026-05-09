"""Coverage tests extracted from test_branch_gaps.py — bin 13.

Sections in this file:
  - dispatch/poll_notify.py: _voter_mention
  - scheduled/roster_nudge.py

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── dispatch/poll_notify.py: _voter_mention ─────────────────────────────────

def _mention_config():
    return {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_names": {"8787": "Sestina_The_Banner_Witch"}},
    ]}


def test_voter_mention_from_players_state():
    """Returns @username when player is in state with username set."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {"100:U1": {"user_id": "U1", "username": "alice", "first_name": "Alice"}}}
    assert _voter_mention("U1", "Alice", _mention_config(), state) == "@alice"


def test_voter_mention_from_poll_user_names():
    """Falls back to poll_user_names when not in state."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {}}
    result = _voter_mention("8787", "Chris", _mention_config(), state)
    assert result == "@Sestina_The_Banner_Witch"


def test_voter_mention_flags_missing_username_in_state():
    """Flags visibly when player is in state but has no username."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {"100:U1": {"user_id": "U1", "username": "", "first_name": "Chris"}}}
    result = _voter_mention("U1", "Chris", _mention_config(), state)
    assert "⚠️" in result
    assert "username unknown" in result
    assert "U1" in result


def test_voter_mention_flags_missing_username_not_in_state():
    """Flags visibly when uid not found in state or poll_user_names."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {}}
    result = _voter_mention("UNKNOWN", "Ghost", _mention_config(), state)
    assert "⚠️" in result
    assert "username unknown" in result


# ─── scheduled/roster_nudge.py ────────────────────────────────────────────────

def test_roster_nudge_posts_when_interval_elapsed():
    """Posts when below target and 3+ days since last nudge."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=4)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Magni Watch", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": old, "last_roster_snapshot": "C04:1/6", "players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert sent
    assert state["last_roster_nudge"] == now.isoformat()


def test_roster_nudge_posts_when_roster_changes():
    """Posts immediately when roster snapshot changes even within 3-day interval."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": recent, "last_roster_snapshot": "C04:2/6", "players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice", "pbp_topic_id": 100,
                   "permanent": True, "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert sent  # snapshot changed from 2 to 1


def test_roster_nudge_skips_when_all_satisfied():
    """Skips when all campaigns are at or above target."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 1},
    ]}
    state = {"players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice", "pbp_topic_id": 100,
                   "permanent": True, "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert not sent


def test_roster_nudge_skips_within_interval_no_change():
    """Skips if <3 days elapsed AND roster unchanged."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": recent, "last_roster_snapshot": "C04:0/6", "players": {}}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert not sent

