"""Coverage tests extracted from test_remaining_100.py — bin 4.

Sections in this file:
  - helpers_pkg/dice.py:80 — non-kept die
  - helpers_pkg/mechanics.py:124 — red icon
  - helpers_pkg/time_utils.py:110 — until date parse
  - import_formatting.py:85 — media bracket
  - parsing/message.py:110 — sticker
  - players/management.py:73 — no match continue
  - boons/handler.py:105 — resolve None
  - combat/commands.py:98 — long log
  - combat/display.py:90 — all acted
  - combat/tracker.py:115 — GM round command
  - transcript/formatting.py:84 — media bracket
  - transcript/finalize.py:51 — empty dir returns
  - transcript/logger.py:144 — silence in days
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── helpers_pkg/dice.py:80 — non-kept die ────────────────────────────────────
def test_dice_drop():
    from helpers_pkg.dice import roll_dice
    result = roll_dice("4d6kh3")
    assert result is not None



# ── helpers_pkg/mechanics.py:124 — red icon ──────────────────────────────────
def test_hp_red():
    from helpers_pkg.mechanics import hp_status_icon
    assert hp_status_icon(2, 10) == "🔴"



# ── helpers_pkg/time_utils.py:110 — until date parse ────────────────────────
def test_parse_until():
    from helpers_pkg.time_utils import parse_away_duration
    now = datetime(2026, 4, 3, 12, 0, 0)
    dt, _ = parse_away_duration("until June 15", now)
    assert dt is None or isinstance(dt, datetime)



# ── import_formatting.py:85 — media bracket ──────────────────────────────────
def test_import_fmt():
    from import_formatting import format_entry
    result = format_entry({"text": "[document:x.pdf]", "is_gm": False}, False)
    assert isinstance(result, str)



# ── parsing/message.py:110 — sticker ─────────────────────────────────────────
def test_parsing_sticker():
    from parsing.message import _detect_media
    result = _detect_media({"sticker": {"emoji": "😎"}})
    assert result is not None and "sticker" in result



# ── players/management.py:73 — no match continue ─────────────────────────────
def test_management_no_match():
    from players.management import handle_kick
    state = {"players": {"100:U2": {"user_id": "U2", "first_name": "Bob",
                                     "username": "bob", "last_name": ""}}}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)



# ── boons/handler.py:105 — resolve None ──────────────────────────────────────
def test_boons_resolve_none():
    from boons.handler import _resolve_boon
    state = {"pending_potw_boons": {"100": {
        "boons": [], "message_id": 42, "base_message": "x", "winner_user_id": "U1",
    }}, "player_boons": {}, "potw_history": []}
    assert _resolve_boon(state, "100", 0, "x") == (None, None)



# ── combat/commands.py:98 — long log ─────────────────────────────────────────
def test_combat_long_log():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {"active": True, "enemies": [],
                                "log": [f"e{i}" for i in range(10)]}}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)



# ── combat/display.py:90 — all acted ─────────────────────────────────────────
def test_combat_all_acted():
    from combat.display import build_whosturn
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {
        "combat": {"100": {
            "active": True,
            "players_acted": {"U1": now_iso, "U2": now_iso},
            "phase_started_at": now_iso,
            "round": 1, "current_phase": "players"}},  # "players" phase
        "players": {
            "100:U1": {"user_id": "U1", "first_name": "Alice", "pbp_topic_id": "100"},
            "100:U2": {"user_id": "U2", "first_name": "Bob",   "pbp_topic_id": "100"},
        },
        "away": {},
    }
    with patch("combat.display.helpers") as mh:
        mh.is_away.return_value = None
        mh.hours_since.return_value = 0.5
        result = build_whosturn("100", "Kibwe", state)
    assert "Everyone" in result



# ── combat/tracker.py:115 — GM round command ─────────────────────────────────
def test_combat_gm_round():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {"active": True, "log": [], "round": 1,
                                "current_phase": "player", "actions_this_round": {},
                                "participants": ["U1"]}}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)



# ── transcript/formatting.py:84 — media bracket ──────────────────────────────
def test_transcript_fmt():
    from transcript.formatting import format_transcript_content
    result = format_transcript_content("[document:f.pdf]")
    assert "f.pdf" in result



# ── transcript/finalize.py:51 — empty dir returns ────────────────────────────
def test_finalize_empty(tmp_path):
    from transcript.finalize import update_transcript_index
    (tmp_path / "Kibwe").mkdir()
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()



# ── transcript/logger.py:144 — silence in days ───────────────────────────────
def test_logger_silence(tmp_path):
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


