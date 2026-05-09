"""Coverage tests extracted from test_dispatch_coverage.py — bin 3.

Sections in this file:
  - dispatch/cmd_info_ext.py
  - dispatch/poll_notify.py
  - dispatch/poll_notify.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/cmd_info_ext.py

# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.cmd_info_ext import handle as handle_ext


def _ext_ctx(cmd):
    return {
        "cmd_word": cmd, "text": cmd, "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe", "user_id": "U1",
        "user_name": "Alice", "state": {}, "config": {}, "gm_ids": set(),
    }


def test_handle_ext_waiting():
    ctx = _ext_ctx("/waiting")
    with patch("dispatch.cmd_info_ext.tg.send_message") as ms:
        with patch("commands.waiting.scan_transcripts", return_value={}):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_session():
    ctx = _ext_ctx("/session")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.session.build_session", return_value="S5"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_health():
    ctx = _ext_ctx("/health")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.health.build_health", return_value="ok"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_queuestats():
    ctx = _ext_ctx("/queuestats")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.queue_stats.build_queue_stats", return_value="stats"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_reactions():
    ctx = _ext_ctx("/reactions")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.reactions.build_reactions", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_timeline():
    ctx = _ext_ctx("/timeline")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.timeline.build_timeline", return_value="t"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_search():
    ctx = {**_ext_ctx("/search"), "text": "/search fire giant"}
    with patch("dispatch.cmd_search.handle_search") as ms:
        result = handle_ext(ctx)
    assert result is True
    ms.assert_called_once()


def test_handle_ext_registry():
    ctx = _ext_ctx("/registry")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.player_registry.build_registry", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_unknown():
    ctx = _ext_ctx("/unknowncmd")
    result = handle_ext(ctx)
    assert result is False



# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/poll_notify.py
