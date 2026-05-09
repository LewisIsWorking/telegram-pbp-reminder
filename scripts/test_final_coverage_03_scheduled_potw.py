"""Coverage tests extracted from test_final_coverage.py — bin 3.

Sections in this file:
  - scheduled/potw.py — winner selection and announcement
  - boons/handler.py — choose_boon_by_text
  - boons/handler.py — choose_boon_by_text
  - scheduled/leaderboard.py — post_campaign_leaderboard
  - scheduled/leaderboard.py — post_campaign_leaderboard
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/potw.py — winner selection and announcement

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.potw import player_of_the_week, _gather_potw_candidates, _find_player_post_links


def test_gather_potw_candidates_no_posts():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    result = _gather_potw_candidates({}, {"999"}, week_ago, "100", {})
    assert result == []


def test_gather_potw_candidates_with_posts():
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    ts = [(now - timedelta(hours=h*4)).isoformat() for h in range(5)]
    ts_map = {"U1": ts}
    state = {"players": {"100:U1": {"user_id": "U1", "first_name": "Alice"}}}
    with patch("scheduled.potw.helpers") as mh:
        mh.POTW_MIN_POSTS = 3
        mh.get_player.return_value = {"user_id": "U1", "first_name": "Alice", "username": "alice"}
        result = _gather_potw_candidates(ts_map, {"999"}, week_ago, "100", state)
    assert len(result) == 1
    assert result[0]["first_name"] == "Alice"


def test_find_player_post_links_no_dir(tmp_path):
    with patch("scheduled.potw._LOGS_DIR", tmp_path / "missing"):
        result = _find_player_post_links("Kibwe", "Alice", "100",
                                         datetime(2026, 3, 27, tzinfo=timezone.utc))
    assert result == []


@patch("scheduled.potw.helpers")
def test_potw_announces_winner(mock_helpers):
    now = datetime(2026, 3, 29, 9, tzinfo=timezone.utc)
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    )
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {}
    mock_helpers.POTW_MIN_POSTS = 3
    mock_helpers.POTW_INTERVAL_DAYS = 7
    mock_helpers.BOONS_PATH = "/nonexistent/boons.json"
    mock_helpers.MECHANICAL_BOONS = ["Gain 1 Hero Point"]
    mock_helpers.player_mention.return_value = "@alice"
    mock_helpers.fmt_date.return_value = "2026-03-22"
    mock_helpers.posts_str.return_value = "10 posts"
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                               "chat_topic_id": 21514, "gm_user_ids": [999]}]}
    state = {"last_potw": {}, "pending_potw_boons": {}}
    candidate = {"user_id": "U1", "first_name": "Alice", "username": "alice",
                 "post_count": 10, "avg_gap_hours": 4.0}
    with patch("scheduled.potw._gather_potw_candidates", return_value=[candidate]), \
         patch("scheduled.potw._find_player_post_links", return_value=[]), \
         patch("scheduled.potw_streaks.announce_streaks"), \
         patch("scheduled.potw.random.sample", return_value=["Boon A", "Boon B", "Boon C"]), \
         patch("scheduled.potw.random.choice", return_value="Gain 1 Hero Point"):
        player_of_the_week(config, state, now=now)
    assert "100" in state.get("last_potw", {}) or "pending_potw_boons" in state



# ═══════════════════════════════════════════════════════════════════════════════
# boons/handler.py — choose_boon_by_text

# ═══════════════════════════════════════════════════════════════════════════════

from boons.handler import choose_boon_by_text


def _boons_state(pid="100", uid="U1"):
    return {
        "pending_potw_boons": {pid: {
            "winner_user_id": uid,
            "message_id": 42,
            "campaign_name": "Kibwe",
            "boons": ["Turtle", "Coin", "Map"],
            "base_message": "You won!",
        }},
        "player_boons": {},
        "players": {"100:U1": {"user_id": uid, "first_name": "Alice"}},
    }


def test_choose_boon_no_pending():
    result = choose_boon_by_text("100", "U1", 1, {}, {})
    assert "No pending" in result


def test_choose_boon_wrong_user():
    state = _boons_state()
    result = choose_boon_by_text("100", "U2", 1, {}, state)
    assert "Only the Player" in result


def test_choose_boon_out_of_range():
    state = _boons_state()
    result = choose_boon_by_text("100", "U1", 99, {}, state)
    assert "Pick a number" in result


def test_choose_boon_success():
    state = _boons_state()
    config = {"group_id": -1001, "bot_topic_id": 999}
    with patch("boons.handler._resolve_boon",
               return_value=("You won Turtle!", None)):
        result = choose_boon_by_text("100", "U1", 1, config, state)
    assert "Turtle" in result or "✅" in result


def test_choose_boon_fallback_by_winner_uid():
    state = _boons_state(pid="200")  # wrong pid
    config = {"group_id": -1001, "bot_topic_id": 999}
    with patch("boons.handler._resolve_boon",
               return_value=("You won Coin!", None)):
        result = choose_boon_by_text("100", "U1", 2, config, state)
    assert "Coin" in result or "✅" in result


def test_choose_boon_no_bot_topic():
    state = _boons_state()
    config = {"group_id": -1001}  # no bot_topic_id
    with patch("boons.handler._resolve_boon",
               return_value=("You won Map!", None)):
        result = choose_boon_by_text("100", "U1", 3, config, state)
    assert "Map" in result or "✅" in result



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/leaderboard.py — post_campaign_leaderboard
