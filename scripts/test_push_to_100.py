"""Tests for the 4 largest remaining coverage gaps."""
import sys, os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(cmd, text, state, config=None, **kw):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": state,
        "config": config or {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
        "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": text}, "maps": MagicMock(),
        "cmd_word": cmd, "text": text,
    }
    base.update(kw)
    return base


# ── cmd_clocks.py ─────────────────────────────────────────────────────────────

def test_clock_create_no_args():
    from dispatch.cmd_clocks import handle
    assert handle(_ctx("/clock", "/clock", {"clocks": {}})) is True


def test_clock_create_bad_segments():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation 15",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation 15"})
    assert handle(ctx) is True


def test_clock_create_segments_not_int():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation bad",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation bad"})
    assert handle(ctx) is True


def test_clock_create_name_only():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation"})
    assert handle(ctx) is True


def test_clock_tick_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Ghost",
               {"clocks": {"100": {"Real": {"filled": 1, "segments": 6}}}},
               parsed={"raw_text": "/tick Ghost"})
    assert handle(ctx) is True


def test_clock_tick_with_amount():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Investigation 2",
               {"clocks": {"100": {"Investigation": {"filled": 1, "segments": 6,
                                                      "label": "Investigation"}}}},
               parsed={"raw_text": "/tick Investigation 2"})
    assert handle(ctx) is True


def test_clock_tick_amount_not_int():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Investigation lots",
               {"clocks": {"100": {"Investigation": {"filled": 1, "segments": 6,
                                                      "label": "Investigation"}}}},
               parsed={"raw_text": "/tick Investigation lots"})
    assert handle(ctx) is True


def test_clock_untick_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/untick", "/untick Ghost",
               {"clocks": {"100": {}}}, parsed={"raw_text": "/untick Ghost"})
    assert handle(ctx) is True


def test_clock_delclock_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/delclock", "/delclock Ghost",
               {"clocks": {"100": {}}}, parsed={"raw_text": "/delclock Ghost"})
    assert handle(ctx) is True


# ── cmd_conditions_hp.py ─────────────────────────────────────────────────────

def test_condition_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition", {"conditions": {}},
               parsed={"raw_text": "/condition"})
    assert handle(ctx) is True


def test_condition_double_dash():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin -- Stunned",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin -- Stunned"})
    assert handle(ctx) is True


def test_condition_single_dash():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin - Stunned",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin - Stunned"})
    assert handle(ctx) is True


def test_condition_no_separator():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin"})
    assert handle(ctx) is True


def test_endcondition_num_out_of_range():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/endcondition", "/endcondition 9",
               {"conditions": {"100": [{"target": "G", "effect": "S"}]}},
               parsed={"raw_text": "/endcondition 9"})
    assert handle(ctx) is True


def test_endcondition_not_a_number():
    from dispatch.cmd_conditions_hp import handle
    # /delcondition with non-numeric → hits ValueError branch (lines 74-75)
    ctx = _ctx("/endcondition", "/endcondition bad",
               {"conditions": {"100": [{"target": "G", "effect": "S"}]}},
               parsed={"raw_text": "/endcondition bad"})
    assert handle(ctx) is True


def test_hp_bare_shows_tracker():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp",
               {"hp_tracker": {"100": {"Goblin": {"current": 10, "max": 20}}}},
               parsed={"raw_text": "/hp"})
    assert handle(ctx) is True


def test_hp_set_max_out_of_range():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set Goblin 10/99999",
               {"hp_tracker": {}}, parsed={"raw_text": "/hp set Goblin 10/99999"})
    assert handle(ctx) is True


def test_hp_set_bad_format():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set Goblin notanumber",
               {"hp_tracker": {}}, parsed={"raw_text": "/hp set Goblin notanumber"})
    assert handle(ctx) is True


def test_hp_set_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set", {"hp_tracker": {}}, parsed={"raw_text": "/hp set"})
    assert handle(ctx) is True


def test_hp_damage_bad_amount():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp d Goblin bad",
               {"hp_tracker": {"100": {"Goblin": {"current": 20, "max": 20}}}},
               parsed={"raw_text": "/hp d Goblin bad"})
    assert handle(ctx) is True


def test_hp_damage_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp d", {"hp_tracker": {}}, parsed={"raw_text": "/hp d"})
    assert handle(ctx) is True


def test_hp_heal_no_entry():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h Ghost 10",
               {"hp_tracker": {"100": {}}}, parsed={"raw_text": "/hp h Ghost 10"})
    assert handle(ctx) is True


def test_hp_heal_bad_amount():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h Goblin bad",
               {"hp_tracker": {"100": {"Goblin": {"current": 20, "max": 20}}}},
               parsed={"raw_text": "/hp h Goblin bad"})
    assert handle(ctx) is True


def test_hp_heal_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h", {"hp_tracker": {}}, parsed={"raw_text": "/hp h"})
    assert handle(ctx) is True


def test_hp_bad_subcommand():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp unknown", {"hp_tracker": {}},
               parsed={"raw_text": "/hp unknown"})
    assert handle(ctx) is True


# ── cmd_info.py — missing commands ────────────────────────────────────────────

def _ic(cmd, state=None):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {}, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-04-03T12:00:00+00:00", "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock(), "cmd_word": cmd, "text": cmd}


def test_cmd_info_overview():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/overview", {"clocks": {}, "quests": {}, "npcs": {},
                                        "conditions": {}, "hp_tracker": {}})) is True


def test_cmd_info_combatlog():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/combatlog", {"combat": {}})) is True


def test_cmd_info_party():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/party", {"players": {}})) is True


def test_cmd_info_catchup():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"), \
         patch("dispatch.cmd_info.build_catchup", return_value="ok"):
        assert handle(_ic("/catchup", {"post_timestamps": {}, "away": {},
                                       "topics": {}, "acted_this_scene": {}})) is True


def test_cmd_info_quests():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/quests", {"quests": {}})) is True


def test_cmd_info_pins():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/pins", {"pins": {}})) is True


def test_cmd_info_loot():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/lootlist", {"loot": {}})) is True


# ── commands/status.py ────────────────────────────────────────────────────────

def _status(state_extras=None):
    s = {"topics": {}, "post_timestamps": {}, "message_counts": {},
         "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    if state_extras:
        s.update(state_extras)
    return s


def _run_status(state, gm_ids=None, hours=1.0):
    from commands.status import build_status
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = hours
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        return build_status("100", "Kibwe", state, gm_ids or set(), {})


def test_status_just_now():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    assert "just now" in _run_status(state, hours=0.3)


def test_status_days_ago():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=2, hours=3)).isoformat()
    state = _status({"topics": {"100": {"last_message_time": old}}})
    result = _run_status(state, hours=51.0)
    assert "d" in result and "h ago" in result


def test_status_1h_ago():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    assert "5h" in _run_status(state, hours=5.0)


def test_status_with_combat():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "combat": {"100": {"active": True, "round": 3,
                                        "current_phase": "players"}}})
    result = _run_status(state)
    assert "Combat" in result or "Round" in result


def test_status_with_quests():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "quests": {"100": [{"text": "Find sword", "status": "active"}]}})
    result = _run_status(state)
    assert "quest" in result.lower() or "📋" in result


def test_status_with_hp():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "hp_tracker": {"100": {"G": {"current": 5, "max": 20}}}})
    result = _run_status(state)
    assert "❤️" in result or "standing" in result


def test_status_with_conditions():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "conditions": {"100": [{"target": "G", "effect": "Stunned"}]}})
    result = _run_status(state)
    assert "⚡" in result or "condition" in result.lower()


def test_status_with_clocks():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "clocks": {"100": {"Inv": {"filled": 2, "segments": 6}}}})
    result = _run_status(state)
    assert "⏱️" in result or "clock" in result.lower()


def test_status_with_queue():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    from commands.status import build_status
    with patch("commands.status.helpers") as mh, \
         patch("commands.queue_scan.scan_transcripts",
               return_value={"100": {"entries": [
                   {"name": "A", "time": "2026-03-01 10:00:00", "preview": "hi"}]}}):
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 1.0
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_status("100", "Kibwe", state, {"GM1"}, {})
    assert isinstance(result, str)
