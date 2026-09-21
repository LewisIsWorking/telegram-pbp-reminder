"""Players' phones still type em dashes, so the bot must still read them.

Lewis, 2026-09-21: "There should be NO em dashes across any repo!" Every em
dash character was removed, but phones turn "--" into one, so /condition and
/npc still receive them. Those parsers match the escape, which keeps the
character out of the source while still recognising it at runtime.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

DASH = chr(0x2014)


def _ctx(text, state):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-09-21T12:00:00+00:00",
            "msg_time_iso": "2026-09-21T12:00:00+00:00",
            "parsed": {"raw_text": text}, "maps": MagicMock(),
            "cmd_word": text.split()[0], "text": text}


def test_condition_splits_on_a_phone_em_dash():
    from dispatch import cmd_conditions_hp
    state = {}
    with patch.object(cmd_conditions_hp.tg, "send_message"):
        cmd_conditions_hp.handle(_ctx(f"/condition Cardigan {DASH} Frightened 2 | 1 round", state))
    cond = state["conditions"]["100"][0]
    assert (cond["target"], cond["effect"], cond["duration"]) == ("Cardigan", "Frightened 2", "1 round")


def test_condition_still_splits_on_a_plain_hyphen():
    from dispatch import cmd_conditions_hp
    state = {}
    with patch.object(cmd_conditions_hp.tg, "send_message"):
        cmd_conditions_hp.handle(_ctx("/condition All - Inspired +1", state))
    assert state["conditions"]["100"][0]["target"] == "All"


def test_npc_splits_on_a_phone_em_dash():
    from dispatch import cmd_trackers_items
    state = {}
    with patch.object(cmd_trackers_items.tg, "send_message"):
        cmd_trackers_items.handle(_ctx(f"/npc Gorund {DASH} Dwarven blacksmith", state))
    npc = state["npcs"]["100"][0]
    assert (npc["name"], npc["desc"]) == ("Gorund", "Dwarven blacksmith")
