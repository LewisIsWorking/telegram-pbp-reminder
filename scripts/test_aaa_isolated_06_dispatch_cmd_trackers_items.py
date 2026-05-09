"""Tests extracted from test_aaa_isolated.py — bin 6.

Sections in this file:
  - dispatch/cmd_trackers_items.py:108 — loot not found
"""
"""
MUST RUN FIRST (alphabetical ordering): these tests cover lines that
only hit in isolation before other tests cache module paths.

Naming: test_aaa_ ensures pytest runs this file before test_b*, test_c*, etc.
"""
import sys, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))



# ── dispatch/cmd_trackers_items.py:108 — loot not found ─────────────────────
def test_cmd_loot_nf():
    from dispatch.cmd_trackers_items import handle
    ctx = {"user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"loot": {"100": []}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/delloot 9"}, "maps": MagicMock(),
           "cmd_word": "/delloot", "text": "/delloot 9"}
    assert handle(ctx) is True
