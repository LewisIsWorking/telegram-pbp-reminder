"""Tests for checker.py — session (part d) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_away_shows_in_status():
    """Away players should appear in /status output."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["away"] = {
        "100:42": {"until": None, "reason": "holiday", "set_at": now.isoformat()}
    }

    result = checker._build_status("100", "TestCampaign", state, {"999"})
    assert "✈️ Away:" in result
    assert "Alice" in result

def test_away_expiry():
    """Away records with passed 'until' date should auto-expire."""
    state = {"away": {
        "100:42": {
            "until": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "reason": "short break",
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
    }}
    result = helpers.is_away(state, "100", "42", datetime.now(timezone.utc))
    assert result is None, "Expired away should return None"
    assert "100:42" not in state["away"], "Expired record should be cleaned up"

def test_away_shows_in_party():
    """Away players should be marked in /party output."""
    _reset()
    config = _make_config(pairs=[{
        "name": "TestCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100],
        "characters": {"42": "Cardigan"},
    }])
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["away"] = {
        "100:42": {"until": None, "reason": "vacation", "set_at": now.isoformat()}
    }

    result = checker._build_party("100", "TestCampaign", config, state)
    assert "✈️ away" in result
    assert "vacation" in result

def test_recap_basic():
    """_build_recap returns recent transcript entries."""
    import pathlib
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Write a test transcript file
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Alice** (2026-02-26 10:00:00):\nI search the room.\n\n"
        "**Bob** [GM] (2026-02-26 10:05:00):\nYou find a hidden door.\n\n"
        "**Alice** (2026-02-26 10:10:00):\nI open the door cautiously.\n\n"
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    result = checker._build_recap("100", "TestCampaign", config, 10)

    assert "📜 Recap" in result
    assert "Alice" in result
    assert "Bob" in result
    assert "I search the room" in result

def test_recap_no_transcript():
    """_build_recap handles missing transcripts gracefully."""
    config = _make_config()
    result = checker._build_recap("100", "NoCampaign", config, 10)
    assert "No transcript archive" in result

def test_recap_command():
    """/recap command sends transcript entries."""
    import pathlib
    _reset()
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Alice** (2026-02-26 10:00:00):\nHello world.\n\n"
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/recap", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    recap_msgs = [m for m in _sent_messages if "📜" in m["text"]]
    assert len(recap_msgs) >= 1, "Should send recap message"

def test_recap_with_count():
    """/recap 5 limits to 5 entries."""
    import pathlib
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    entries = ""
    for i in range(20):
        entries += f"**Alice** (2026-02-26 {10+i//60:02d}:{i%60:02d}:00):\nEntry {i+1}.\n\n"
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        + entries
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    result = checker._build_recap("100", "TestCampaign", config, 5)
    # Should show exactly 5 entries
    assert "last 5" in result

def test_recap_gm_tag():
    """Recap shows 🎲 for GM posts."""
    import pathlib
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Lewis** [GM] (2026-02-26 10:00:00):\nThe ogre swings at you.\n\n"
        "**Alice** (Cardigan) (2026-02-26 10:05:00):\nI dodge!\n\n"
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    result = checker._build_recap("100", "TestCampaign", config, 10)
    assert "🎲 Lewis" in result
    assert "Cardigan" in result

def test_recap_scene_boundary():
    """Recap shows scene markers."""
    import pathlib
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Alice** (2026-02-26 10:00:00):\nOld scene post.\n\n"
        "\n---\n\n### 🎭 Scene: The Dark Cave\n*(2026-02-26 10:30)*\n\n---\n\n"
        "**Alice** (2026-02-26 10:35:00):\nI enter the cave.\n\n"
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    result = checker._build_recap("100", "TestCampaign", config, 10)
    assert "The Dark Cave" in result
    assert "━━━" in result
