"""Coverage tests extracted from test_push_to_100.py — bin 1.

Sections in this file:
  - cmd_clocks.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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


