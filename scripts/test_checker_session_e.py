"""Tests for checker.py — session (part e) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_recap_time_gap():
    """Recap shows time gaps between posts."""
    import pathlib
    campaign_dir = pathlib.Path(checker._LOGS_DIR) / "TestCampaign"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "# TestCampaign — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Alice** (2026-02-26 08:00:00):\nMorning post.\n\n"
        "**Bob** (2026-02-26 20:00:00):\nEvening post.\n\n"
    )
    (campaign_dir / "2026-02.md").write_text(content, encoding="utf-8")

    config = _make_config()
    result = checker._build_recap("100", "TestCampaign", config, 10)
    assert "later" in result  # "12h later" gap indicator

def test_catchup_shows_combat_acted():
    """Catchup tells player if they've already acted in combat."""
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=5)).isoformat()],
        "999": [(now - timedelta(hours=2)).isoformat()],
    }
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": {"42": now.isoformat()},
    }

    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "already acted" in result
