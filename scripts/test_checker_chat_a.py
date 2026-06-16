"""Tests for checker.py — chat (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_post_daily_tip_sends():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    assert "💡" in _sent_messages[0].get("text", "")
    assert state.get("last_daily_tip") is not None
    assert len(state.get("used_tip_indices", [])) == 1

def test_post_daily_tip_respects_cooldown():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()
    state["last_daily_tip"] = (now - timedelta(hours=10)).isoformat()

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 0  # Too soon

def test_post_daily_tip_rotates():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # Exhaust all but one tip
    state["used_tip_indices"] = list(range(len(checker._TIPS) - 1))

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    # The only remaining index should be the one not in the used list
    last_idx = state["used_tip_indices"][-1]
    assert last_idx == len(checker._TIPS) - 1

def test_post_daily_tip_resets_cycle():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # All tips used
    state["used_tip_indices"] = list(range(len(checker._TIPS)))

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    # Cycle should have reset - used_tip_indices should have exactly 1 entry
    assert len(state["used_tip_indices"]) == 1

def test_append_to_transcript():
    import shutil
    test_dir = checker._LOGS_DIR / "transcript_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    parsed = {
        "campaign_name": "transcript_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "Hello world!", "media_type": None, "caption": "",
    }
    checker._append_to_transcript(parsed, {"999"})

    log_dir = checker._LOGS_DIR / "transcript_test"
    assert log_dir.exists()
    log_file = log_dir / "2026-02.md"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "transcript_test — 2026-02" in content
    assert "**Alice**" in content
    assert "Hello world!" in content

    # Second write appends
    parsed["raw_text"] = "Second message"
    checker._append_to_transcript(parsed, {"999"})
    content = log_file.read_text(encoding="utf-8")
    assert "Second message" in content
    assert content.count("transcript_test — 2026-02") == 1  # Header only once

    shutil.rmtree(test_dir)

def test_word_count_tracking():
    """Word counts are accumulated per-user per-campaign during message processing."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [
        {
            "update_id": 2001,
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 100,
                "from": {"id": 42, "first_name": "Alice", "last_name": "", "username": "alice"},
                "date": now_ts,
                "text": "Cardigan draws her blade and charges forward",
            },
        },
        {
            "update_id": 2002,
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 100,
                "from": {"id": 42, "first_name": "Alice", "last_name": "", "username": "alice"},
                "date": now_ts + 60,
                "text": "She strikes true",
            },
        },
    ]
    checker.process_updates(updates, config, state)
    # 7 words + 3 words = 10
    assert state["word_counts"]["100"]["42"] == 10

def test_conversation_dying_48h():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last post was 60h ago
    last_post = (now - timedelta(hours=60)).isoformat()
    state["post_timestamps"]["100"] = {
        "42": [last_post],
        "999": [(now - timedelta(hours=55)).isoformat()],
    }

    checker.check_conversation_dying(config, state, now=now)
    dying_msgs = [m for m in _sent_messages if "💤" in m.get("text", "") or "silent" in m.get("text", "")]
    assert len(dying_msgs) == 1
    assert state.get("dying_alerts_sent", {}).get("100") == "active"

def test_conversation_dying_not_repeated():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    last_post = (now - timedelta(hours=60)).isoformat()
    state["post_timestamps"]["100"] = {"42": [last_post]}
    state["dying_alerts_sent"] = {"100": "active"}

    checker.check_conversation_dying(config, state, now=now)
    # Should NOT send again — already flagged
    assert len(_sent_messages) == 0

def test_conversation_dying_resets_on_activity():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Recent post (1h ago) — should clear the flag
    recent = (now - timedelta(hours=1)).isoformat()
    state["post_timestamps"]["100"] = {"42": [recent]}
    state["dying_alerts_sent"] = {"100": "active"}

    checker.check_conversation_dying(config, state, now=now)
    assert "100" not in state.get("dying_alerts_sent", {})
    assert len(_sent_messages) == 0

def test_conversation_dying_skips_paused():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    last_post = (now - timedelta(hours=72)).isoformat()
    state["post_timestamps"]["100"] = {"42": [last_post]}
    state["paused"] = {"100": "on holiday"}

    checker.check_conversation_dying(config, state, now=now)
    assert len(_sent_messages) == 0
