"""Coverage tests extracted from test_remaining_gaps.py — bin 4.

Sections in this file:
  - commands/trackers.py:97 — no NPCs
  - commands/waiting.py:110-111 — invalid time in all-campaigns view
  - dispatch/bot_topic.py:138 — global cmd campaign_name
  - dispatch/cmd_clocks.py:123 — clock not found message
  - dispatch/cmd_conditions_hp.py:194 — hp bad args
  - dispatch/cmd_gm.py:99-106 — /session set
  - dispatch/cmd_info.py:130-131 — /queue for GM
  - dispatch/cmd_player.py:136 — roll error branch
  - dispatch/cmd_search.py:87 — blocked category skipped
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── commands/trackers.py:97 — no NPCs ──────────────────────────────────────

def test_trackers_no_npcs():
    from commands.trackers import build_npcs
    result = build_npcs("100", "Kibwe", {})
    assert "No NPCs" in result



# ─── commands/waiting.py:110-111 — invalid time in all-campaigns view ────────

def test_waiting_all_invalid_time():
    from commands.waiting import build_waiting_all
    with patch("commands.waiting.scan_transcripts") as ms:
        ms.return_value = {
            "100": {
                "code": "C00", "campaign": "Kibwe",
                "entries": [{"name": "Alice", "time": "INVALID", "preview": "hi"}]
            }
        }
        config = {"topic_pairs": [{"pbp_topic_ids": [100]}]}
        state = {"players": {"100:U1": {"first_name": "Alice"}}}
        result = build_waiting_all("U1", "Alice", config, state)
    assert isinstance(result, str)



# ─── dispatch/bot_topic.py:138 — global cmd campaign_name ───────────────────

def test_bot_topic_global_cmd_sets_campaign_name():
    from dispatch.bot_topic import handle_bot_topic_cmd
    handled = []
    def fake_handler(ctx):
        handled.append(ctx.get("campaign_name"))
        return True
    maps = MagicMock()
    maps.name_to_pid = {"kibwe": "100"}
    maps.to_name = {"100": "Kibwe"}
    maps.to_chat = {"100": 21514}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "Lewis", "is_bot": False},
         "text": "/gm"},
        {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999], "topic_pairs": []},
        {}, maps, -1001, 999,
        frozenset(["/gm"]),
        [fake_handler],
    )
    assert handled and handled[0] == "Kibwe"



# ─── dispatch/cmd_clocks.py:123 — clock not found message ───────────────────

def test_cmd_clocks_not_found_message():
    from dispatch.cmd_clocks import handle as clocks_handle
    ctx = _ctx(cmd_word="/tick", text="/tick GhostClock",
               state={"clocks": {"100": {}}})
    ctx["parsed"] = {"raw_text": "/tick GhostClock"}
    result = clocks_handle(ctx)
    assert result is True



# ─── dispatch/cmd_conditions_hp.py:194 — hp bad args ────────────────────────

def test_cmd_hp_bad_args():
    from dispatch.cmd_conditions_hp import handle as hp_handle
    ctx = _ctx(cmd_word="/hp", text="/hp badarg")
    ctx["parsed"] = {"raw_text": "/hp badarg"}
    ctx["reply_topic"] = 999
    result = hp_handle(ctx)
    assert result is True



# ─── dispatch/cmd_gm.py:99-106 — /session set ────────────────────────────────

def test_cmd_gm_session_set():
    from dispatch.cmd_gm import handle as gm_handle
    ctx = _ctx(cmd_word="/session", text="/session set 5",
               state={})
    result = gm_handle(ctx)
    assert result is True
    assert ctx["state"].get("session_counts", {}).get("100") == 5


def test_cmd_gm_session_set_invalid():
    from dispatch.cmd_gm import handle as gm_handle
    ctx = _ctx(cmd_word="/session", text="/session set notanumber",
               state={})
    result = gm_handle(ctx)
    assert result is True



# ─── dispatch/cmd_info.py:130-131 — /queue for GM ────────────────────────────

def test_cmd_info_queue_gm():
    from dispatch.cmd_info import handle as info_handle
    ctx = _ctx(cmd_word="/queue", text="/queue",
               state={}, config={"group_id": -1, "gm_user_ids": [], "topic_pairs": []})
    ctx["reply_topic"] = 999
    ctx["uid"] = "GM1"
    ctx["user_id"] = "GM1"
    with patch("dispatch.cmd_info.tg.send_message"), \
         patch("commands.queue.build_queue", return_value="queue"):
        result = info_handle(ctx)
    assert result is True



# ─── dispatch/cmd_player.py:136 — roll error branch ─────────────────────────

def test_cmd_player_roll_error():
    from dispatch.cmd_player import handle as player_handle
    ctx = _ctx(cmd_word="/roll", text="/roll XYZZY",
               parsed={"raw_text": "/roll XYZZY", "text": "/roll XYZZY"})
    with patch("dispatch.cmd_player.helpers.roll_dice",
               return_value={"error": "bad dice", "results": [], "label": ""}):
        result = player_handle(ctx)
    assert result is True



# ─── dispatch/cmd_search.py:87 — blocked category skipped ───────────────────

def test_search_blocked_category_skipped():
    from dispatch.cmd_search import handle_search
    tg = MagicMock()
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"hits": {"hits": [
        {"_source": {"name": "Goblin", "category": "creature",
                     "url": "/monsters/goblin", "level": 1,
                     "rarity": "common", "summary": "", "actions": ""}}
    ], "total": {"value": 1}}}
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("goblin", -1, 999, tg)
    # Creature is blocked — no results shown but no crash
    assert tg.send_message.call_count == 1


