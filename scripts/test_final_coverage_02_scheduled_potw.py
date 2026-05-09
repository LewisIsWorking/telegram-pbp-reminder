"""Coverage tests extracted from test_final_coverage.py — bin 2.

Sections in this file:
  - scheduled/potw.py — winner selection and announcement (part a)
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _maps():
    m = MagicMock()
    m.name_to_pid = {"kibwe": "100", "riddleport": "200"}
    m.to_name = {"100": "Kibwe", "200": "Riddleport"}
    m.to_chat = {"100": 21514, "200": 21515}
    return m


def test_resolve_campaign_exact():
    pid, name = resolve_campaign("kibwe", _maps())
    assert pid == "100"
    assert name == "Kibwe"


def test_resolve_campaign_prefix():
    pid, name = resolve_campaign("kib", _maps())
    assert pid == "100"


def test_resolve_campaign_empty():
    assert resolve_campaign("", _maps()) == (None, None)


def test_resolve_campaign_not_found():
    assert resolve_campaign("zzzz", _maps()) == (None, None)


def _bt_msg(text, uid="U1", is_bot=False):
    return {"from": {"id": int(uid.lstrip("U") or 1),
                     "first_name": "Alice", "is_bot": is_bot},
            "text": text}


def _bt_config():
    return {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }


def test_bot_topic_ignores_bot_messages():
    handle_bot_topic_cmd(_bt_msg("/status", is_bot=True),
                         _bt_config(), {}, _maps(), -1001, 999, frozenset(), [])


def test_bot_topic_ignores_non_commands():
    handle_bot_topic_cmd(_bt_msg("just chatting"),
                         _bt_config(), {}, _maps(), -1001, 999, frozenset(), [])


def test_bot_topic_search():
    with patch("dispatch.bot_topic.handle_search") as ms:
        handle_bot_topic_cmd(_bt_msg("/search fireball"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/search"]), [])
        ms.assert_called_once()


def test_bot_topic_chooseboon_invalid():
    handle_bot_topic_cmd(_bt_msg("/chooseboon notanumber"),
                         _bt_config(), {}, _maps(), -1001, 999, frozenset(), [])


def test_bot_topic_chooseboon_no_pending():
    handle_bot_topic_cmd(_bt_msg("/chooseboon 1"),
                         _bt_config(), {"pending_potw_boons": {}},
                         _maps(), -1001, 999, frozenset(), [])


def test_bot_topic_mystats_no_arg():
    with patch("commands.player.build_mystats_all", return_value="stats"):
        handle_bot_topic_cmd(_bt_msg("/mystats"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/mystats"]), [])


def test_bot_topic_waiting_no_arg():
    with patch("commands.waiting.build_waiting_all", return_value="waiting"):
        handle_bot_topic_cmd(_bt_msg("/waiting"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/waiting"]), [])


def test_bot_topic_roll_no_dice():
    handle_bot_topic_cmd(_bt_msg("/roll"),
                         _bt_config(), {}, _maps(), -1001, 999,
                         frozenset(["/roll"]), [])


def test_bot_topic_roll_with_dice():
    with patch("dispatch.bot_topic.helpers.roll_dice",
               return_value={"results": [{"detail": "1d20", "total": 15}],
                             "label": "Stealth", "error": None}):
        handle_bot_topic_cmd(_bt_msg("/roll 1d20 Stealth"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/roll"]), [])


def test_bot_topic_roll_error():
    with patch("dispatch.bot_topic.helpers.roll_dice",
               return_value={"error": "bad dice", "results": [], "label": ""}):
        handle_bot_topic_cmd(_bt_msg("/roll XYZZY"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/roll"]), [])


def test_bot_topic_dc():
    sent = []
    with patch("dispatch.bot_topic.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        handle_bot_topic_cmd(_bt_msg("/dc 10"),
                             _bt_config(), {}, _maps(), -1001, 999,
                             frozenset(["/dc"]), [])
    assert any("mystery" in m.lower() for m in sent)


def test_bot_topic_global_cmd_no_campaigns():
    maps = MagicMock()
    maps.to_name = {}
    handle_bot_topic_cmd(_bt_msg("/gm"),
                         _bt_config(), {}, maps, -1001, 999,
                         frozenset(["/gm"]), [])


def test_bot_topic_campaign_cmd_no_arg():
    handle_bot_topic_cmd(_bt_msg("/status"),
                         _bt_config(), {}, _maps(), -1001, 999,
                         frozenset(["/status"]), [])


def test_bot_topic_campaign_cmd_dispatches():
    handled = []
    def fake_handler(ctx):
        handled.append(ctx["cmd_word"])
        return True
    handle_bot_topic_cmd(_bt_msg("/status kibwe"),
                         _bt_config(), {}, _maps(), -1001, 999,
                         frozenset(["/status"]), [fake_handler])
    assert "/status" in handled


def test_bot_topic_non_read_cmd_ignored():
    handle_bot_topic_cmd(_bt_msg("/pause kibwe"),
                         _bt_config(), {}, _maps(), -1001, 999,
                         frozenset(["/status"]), [])
