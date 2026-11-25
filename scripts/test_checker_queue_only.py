"""Coverage tests for checker._run_checks(only=...) - the --queue-only pass.

The half-hourly run must stay cheap: it processes Telegram updates (so GM
reply-to clears register promptly) but fires ONLY the queue checks. These
tests pin that contract so a future check added to _run_checks does not
silently start running every 30 minutes.
"""
import sys, os
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import checker


def _cfg():
    return {"group_id": -1001, "bot_topic_id": 999, "topic_pairs": []}


# The checks the assertions below name, by the function each label runs.
_LABEL_OF = {
    "post_schedule": "Schedule post",
    "post_queue_reminder": "Queue reminder",
    "check_queue_nudge": "Queue nudge",
    "post_daily_tip": "Daily tip",
    "player_of_the_week": "Player of the Week",
    "post_campaign_leaderboard": "Leaderboard",
    "backup_state": "State backup",
}

# Names _run_checks reads that are not checks.
_NOT_CHECKS = {"datetime", "now", "timezone", "utc", "build_topic_maps",
               "Exception", "print"}


def _check_names() -> list[str]:
    """Every check function _run_checks calls, read from its bytecode.

    ⛔ Added 2026-11-25. This helper used to spy on only the seven checks
    the tests name and let the other ~35 run FOR REAL against the real
    clock. From 08:00 UTC the real ``run_daily_diagnostic`` was due, and
    it listed this repo's workflow runs from api.github.com, so these
    tests made a live network call at some hours of the day and not at
    others. Every check is a spy now, so nothing real runs at any hour.
    """
    return [n for n in checker._run_checks.__code__.co_names
            if n not in _NOT_CHECKS and callable(getattr(checker, n, None))]


def _labels_run(only):
    """Return what _run_checks actually invoked: a label where the tests
    name one, the function name otherwise."""
    called = []

    def _spy(name):
        def _fn(config, bot_state, now=None, maps=None):
            called.append(_LABEL_OF.get(name, name))
        return _fn

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(checker, "build_topic_maps", return_value={}))
        for name in _check_names():
            stack.enter_context(patch.object(checker, name, _spy(name)))
        checker._run_checks(_cfg(), {}, only=only)
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
    # Each label matched exactly one check, so none of them is a typo
    # that the full pass would hide.
    assert len(_labels_run(checker.QUEUE_CHECKS)) == len(checker.QUEUE_CHECKS)


def test_every_check_is_spied():
    """The full pass ran only spies: one call per check, none real."""
    assert len(_labels_run(())) == len(_check_names()) > 30


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

    # Updates are still fetched - this is what clears GM reply-to entries.
    get_updates.assert_called_once_with(5)
    # State is still persisted, so the consumed offset is not lost.
    save.assert_called_once()
    assert seen["only"] == checker.QUEUE_CHECKS
