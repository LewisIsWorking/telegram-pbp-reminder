"""Tests for checker.py — chat (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_write_scene_marker():
    """Scene marker writes correct markdown to transcript."""
    import tempfile, pathlib
    from transcript import logger as _lmod
    original_dir = _lmod._LOGS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        _lmod._LOGS_DIR = pathlib.Path(tmp)
        checker._LOGS_DIR = _lmod._LOGS_DIR
        try:
            checker._write_scene_marker("Test Campaign", "The Final Battle")
            campaign_dir = pathlib.Path(tmp) / "Test_Campaign"
            assert campaign_dir.exists()
            md_files = list(campaign_dir.glob("*.md"))
            assert len(md_files) == 1
            content = md_files[0].read_text(encoding="utf-8")
            assert "### 🎭 Scene: The Final Battle" in content
        finally:
            _lmod._LOGS_DIR = original_dir
            checker._LOGS_DIR = original_dir

def test_gm_dashboard():
    """/gm shows all campaigns with health info."""
    _reset()
    config = _make_config(pairs=[
        {"name": "Campaign A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
        {"name": "Campaign B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
    ])
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"] = {
        "100:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "", "campaign_name": "Campaign A",
            "pbp_topic_id": "100", "last_post_time": now.isoformat(),
            "last_warned_week": 0,
        },
    }
    state["topics"]["100"] = {
        "last_message_time": now.isoformat(),
        "last_user": "Alice", "last_user_id": "42",
        "campaign_name": "Campaign A",
    }

    result = checker._build_gm_dashboard(config, state)
    assert "📊 GM Dashboard" in result
    assert "Campaign A" in result
    assert "Campaign B" in result

def test_gm_command_requires_gm():
    """/gm only works for GMs."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/gm", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    gm_msgs = [m for m in _sent_messages if "GM Dashboard" in m.get("text", "")]
    assert len(gm_msgs) == 0, "Non-GM should not see dashboard"

def test_gm_command_works_for_gm():
    """/gm works for GMs."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/gm", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    gm_msgs = [m for m in _sent_messages if "GM Dashboard" in m.get("text", "")]
    assert len(gm_msgs) >= 1
