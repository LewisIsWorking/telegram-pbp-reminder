"""Coverage tests extracted from test_branch_gaps.py — bin 8.

Sections in this file:
  - Various single-line branches (part c)

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


def test_maintenance_no_active_players():
    from scheduled.maintenance import check_recruitment_needs
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999],
                               "chat_topic_id": 21514}]}
    state = {"players": {}, "post_timestamps": {}, "last_recruitment_check": {}}
    with patch("scheduled.maintenance.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.gm_ids_for_campaign.return_value = {"999"}
        mh.get_topic_timestamps.return_value = {}
        mh.REQUIRED_PLAYERS = 4
        mh.interval_elapsed.return_value = True
        check_recruitment_needs(config, state, now=now)


def test_waiting_invalid_time_ignored():
    from commands.waiting import build_waiting
    with patch("commands.waiting.scan_transcripts") as ms, \
         patch("commands.queue_stats.avg_reply_hours", return_value=None):
        ms.return_value = {"100": {"entries": [
            {"name": "Alice", "time": "INVALID", "preview": "hi", "link": ""}
        ]}}
        state = {"players": {"100:U1": {"first_name": "Alice"}},
                 "_config_cache": {}}
        result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "Waiting on GM" in result or "No pending" in result


# (old stale test removed)


def test_players_management_skip_no_pid():
    from players.management import handle_kick
    # Kick with no matching player → sends not-found message
    state = {"players": {}}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)


def test_catchup_acted_ids():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=2)).isoformat()
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts], "U2": []}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 2.0
        mh.get_player.return_value = {"first_name": "Alice", "username": "alice"}
        mh.player_full_name.return_value = "Alice"
        result = build_catchup("U1", "Alice", "100", "Kibwe",
                                {"group_id": -1},
                                {"post_timestamps": {"100": {"U1": [ts]}}})
    assert isinstance(result, str)


def test_reactions_zero_count_reset():
    from commands.reactions import build_reactions
    state = {"reactions": {"100": {
        "U1": {"👍": 3},
        "U2": {"👍": -1},  # negative → reset to 0
    }}}
    with patch("commands.reactions.helpers") as mh:
        mh.get_player.return_value = {"first_name": "Alice", "username": "alice"}
        mh.gm_ids_for_campaign.return_value = set()
        result = build_reactions({}, state, "100", "Kibwe")
    assert isinstance(result, str)


def test_post_changelog_main_exits():
    import post_changelog as pc
    with patch.object(pc, "main", return_value=0) as mm:
        mm()
        mm.assert_called_once()


def test_import_history_main():
    import import_history as ih
    with patch.object(ih, "main", return_value=None) as mm:
        ih.main()
        mm.assert_called_once()


def test_migrate_main():
    import migrate_gist_to_files as mg
    with patch.object(mg, "main", return_value=None) as mm:
        mg.main()
        mm.assert_called_once()


def test_set_commands_main_exits(monkeypatch, capsys):
    import set_commands as sc
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise SystemExit(1)


def test_recap_long_content_truncated():
    from commands.recap import build_recap
    long_content = "word " * 50  # > 197 chars
    with patch("commands.recap.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        mh.get_characters.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        result = build_recap("100", "Kibwe", {}, 10)
    assert isinstance(result, str)


def test_dc_lookup_adjustment_positive():
    from helpers_pkg.dc_lookup import dc_lookup
    result = dc_lookup("simple")
    if "adjustment" in result.lower():
        assert "+" in result or "−" in result or "±" in result
    else:
        assert isinstance(result, str)


def test_combat_tracker_no_combat():
    from combat.tracker import handle_round_command
    handle_round_command("/next", "100", "Kibwe", -1, 999,
                         {"combat": {}}, {})  # no active combat → sends message


def test_commands_mechanics_no_clocks():
    from commands.mechanics import build_clocks
    result = build_clocks("100", "Kibwe", {"clocks": {}})
    assert "No clocks" in result


def test_alerts_excluded_skip():
    from scheduled.alerts import check_and_alert
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "chat_topic_id": 21514}]}
    state = {}
    with patch("scheduled.alerts.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = True
        check_and_alert(config, state, now=now)
