"""Coverage tests for checker._run_checks(only=...) — the --queue-only pass.

The half-hourly run must stay cheap: it processes Telegram updates (so GM
reply-to clears register promptly) but fires ONLY the queue checks. These
tests pin that contract so a future check added to _run_checks does not
silently start running every 30 minutes.
"""
import sys, os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import checker


def _cfg():
    return {"group_id": -1001, "bot_topic_id": 999, "topic_pairs": []}


def _labels_run(only):
    """Return the set of check labels _run_checks actually invoked."""
    called = []

    def _spy(label):
        def _fn(config, bot_state, now=None, maps=None):
            called.append(label)
        return _fn

    real = checker._run_checks

    # Patch build_topic_maps so no config plumbing is needed.
    with patch.object(checker, "build_topic_maps", return_value={}):
        # Rebuild the checks list with spies by patching each callable
        # referenced inside _run_checks at module level.
        import scheduled.queue_reminder as qr
        import scheduled.queue_nudge as qn
        import scheduled.tips as tips
        with patch.object(checker, "post_queue_reminder", _spy("Queue reminder")), \
             patch.object(checker, "check_queue_nudge", _spy("Queue nudge")), \
             patch.object(checker, "post_daily_tip", _spy("Daily tip")), \
             patch.object(checker, "player_of_the_week", _spy("Player of the Week")), \
             patch.object(checker, "post_campaign_leaderboard", _spy("Leaderboard")), \
             patch.object(checker, "backup_state", _spy("State backup")):
            real(_cfg(), {}, only=only)
    return called


def test_queue_only_runs_just_the_queue_checks():
    called = _labels_run(checker.QUEUE_CHECKS)
    assert "Queue reminder" in called
    assert "Queue nudge" in called
    # The expensive/noisy features must NOT fire on the half-hourly pass.
    for noisy in ("Daily tip", "Player of the Week", "Leaderboard", "State backup"):
        assert noisy not in called


def test_full_pass_still_runs_everything():
    called = _labels_run(())
    for label in ("Queue reminder", "Queue nudge", "Daily tip",
                  "Player of the Week", "Leaderboard", "State backup"):
        assert label in called


def test_queue_checks_are_real_labels():
    """QUEUE_CHECKS must name checks that exist, or the pass silently no-ops."""
    called = _labels_run(())
    for label in checker.QUEUE_CHECKS:
        assert label in called, f"{label} is not a real check label"


def test_main_passes_queue_only_through():
    """main(queue_only=True) must still process updates, then restrict checks."""
    seen = {}

    def _fake_run_checks(config, bot_state, only=()):
        seen["only"] = only

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t",
                                 "GIST_TOKEN": "g", "GIST_ID": "i"}), \
         patch.object(checker.tg, "init"), \
         patch.object(checker.state_store, "init"), \
         patch.object(checker.state_store, "load", return_value={"offset": 5}), \
         patch.object(checker.state_store, "save") as save, \
         patch.object(checker.helpers, "load_config", return_value=_cfg()), \
         patch.object(checker.helpers, "load_settings"), \
         patch.object(checker.helpers, "validate_config", return_value=[]), \
         patch.object(checker.tg, "get_updates", return_value=[]) as get_updates, \
         patch.object(checker, "_run_checks", _fake_run_checks), \
         patch.object(checker, "cleanup_timestamps"), \
         patch.object(checker, "update_transcript_index"):
        checker.main(queue_only=True)

    # Updates are still fetched — this is what clears GM reply-to entries.
    get_updates.assert_called_once_with(5)
    # State is still persisted, so the consumed offset is not lost.
    save.assert_called_once()
    assert seen["only"] == checker.QUEUE_CHECKS
