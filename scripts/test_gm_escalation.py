"""Tests for scheduled/gm_escalation.py."""

import sys, os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))


def _config():
    return {
        "group_id": -1001, "bot_topic_id": 999, "gm_queue_topic_id": 888,
        "gm_user_id": 1698524397,
        "topic_pairs": [
            {"pbp_topic_ids": ["100"], "code": "C07", "name": "Hopeful End-Times",
             "chat_topic_id": 500},
        ],
    }


def _entry(hours_old: float, now: datetime) -> dict:
    posted = now - timedelta(hours=hours_old)
    return {"time": posted.strftime("%Y-%m-%d %H:%M:%S"), "name": "Alice",
            "preview": "Hi", "link": ""}


def _scanned(hours_old: float, now: datetime, pid="100") -> dict:
    return {pid: {
        "campaign": "Hopeful End-Times", "code": "C07",
        "entries": [_entry(hours_old, now)],
    }}


def test_no_escalation_before_12h():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    state = {"gm_escalation": {}}
    sent = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(6, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t))):
        check_gm_escalation(_config(), state, now=now)
    assert not sent


def test_level1_single_message_bot_topic_only():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    state = {"gm_escalation": {}}
    sent = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(13, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        check_gm_escalation(_config(), state, now=now)
    assert len(sent) == 1  # single message, no DM
    assert sent[0][1] == 888  # gm_queue topic
    assert "Hopeful End-Times" in sent[0][2]
    assert "13h" in sent[0][2]
    assert state["gm_escalation"]["100"]["level"] == 1


def test_level2_sends_dm():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=13)).isoformat()
    state = {"gm_escalation": {"100": {"level": 1, "last_at": last}}}
    sent = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(25, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t))):
        check_gm_escalation(_config(), state, now=now)
    assert len(sent) == 2  # bot topic + DM
    assert 1698524397 in {s[0] for s in sent}
    assert state["gm_escalation"]["100"]["level"] == 2


def test_multiple_campaigns_batched_into_one_message():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    config = dict(_config())
    config["topic_pairs"] = [
        {"pbp_topic_ids": ["100"], "code": "C07", "name": "Hopeful End-Times", "chat_topic_id": 500},
        {"pbp_topic_ids": ["200"], "code": "C04", "name": "Magni Watch", "chat_topic_id": 501},
    ]
    state = {"gm_escalation": {}}
    scanned = {
        "100": {"campaign": "Hopeful End-Times", "code": "C07",
                "entries": [_entry(20, now)]},
        "200": {"campaign": "Magni Watch", "code": "C04",
                "entries": [_entry(15, now)]},
    }
    sent_msgs = []
    with patch("scheduled.gm_escalation.scan_transcripts", return_value=scanned), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent_msgs.append(m)):
        check_gm_escalation(config, state, now=now)
    assert len(sent_msgs) == 1  # ONE combined message
    assert "Hopeful End-Times" in sent_msgs[0]
    assert "Magni Watch" in sent_msgs[0]


def test_skips_within_12h_interval():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).isoformat()
    state = {"gm_escalation": {"100": {"level": 1, "last_at": last}}}
    sent = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(20, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t))):
        check_gm_escalation(_config(), state, now=now)
    assert not sent


def test_clears_state_when_queue_empty():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    state = {"gm_escalation": {"100": {"level": 3, "last_at": now.isoformat()}}}
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value={"100": {"campaign": "HET", "code": "C07", "entries": []}}):
        check_gm_escalation(_config(), state, now=now)
    assert "100" not in state["gm_escalation"]


def test_level_caps_at_max_message():
    from scheduled.gm_escalation import check_gm_escalation, _HEADERS
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=13)).isoformat()
    state = {"gm_escalation": {"100": {"level": len(_HEADERS), "last_at": last}}}
    sent_msgs = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(100, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent_msgs.append(m)):
        check_gm_escalation(_config(), state, now=now)
    assert sent_msgs
    assert state["gm_escalation"]["100"]["level"] == len(_HEADERS)


def test_no_gm_user_id_skips():
    from scheduled.gm_escalation import check_gm_escalation
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    config = dict(_config())
    del config["gm_user_id"]
    state = {"gm_escalation": {}}
    sent = []
    with patch("scheduled.gm_escalation.scan_transcripts",
               return_value=_scanned(20, now)), \
         patch("scheduled.gm_escalation.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        check_gm_escalation(config, state, now=now)
    assert not sent
