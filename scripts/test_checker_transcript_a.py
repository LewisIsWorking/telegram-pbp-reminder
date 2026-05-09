"""Tests for checker.py — transcript (part a) group.

Extracted from test_checker.py during the test-split refactor. Module
imports, helper functions (_make_config, _make_state, _make_msg, _utc,
_reset, _run_all), and the _LOGS_DIR redirection setup all live in the
shared ``_test_checker_helpers`` module so this file contains test
functions only.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_transcript_week_headers():
    """Transcript inserts week headers when ISO week changes."""
    import shutil
    test_dir = checker._LOGS_DIR / "week_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    base = {
        "campaign_name": "week_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "raw_text": "msg", "media_type": None, "caption": "",
    }

    # Week 9: Mon Feb 23 2026
    parsed1 = {**base, "msg_time_iso": "2026-02-23T10:00:00+00:00", "raw_text": "week 9 msg"}
    checker._append_to_transcript(parsed1, {"999"})

    # Same week, no new header
    parsed2 = {**base, "msg_time_iso": "2026-02-25T12:00:00+00:00", "raw_text": "still week 9"}
    checker._append_to_transcript(parsed2, {"999"})

    # Week 10: Mon Mar 2 2026
    parsed3 = {**base, "msg_time_iso": "2026-03-02T08:00:00+00:00", "raw_text": "week 10 msg"}
    checker._append_to_transcript(parsed3, {"999"})

    # Check February file
    feb_file = checker._LOGS_DIR / "week_test" / "2026-02.md"
    feb_content = feb_file.read_text()
    assert "## Week 9" in feb_content
    assert feb_content.count("## Week 9") == 1  # Only one header for week 9
    assert "week 9 msg" in feb_content
    assert "still week 9" in feb_content

    # Check March file
    mar_file = checker._LOGS_DIR / "week_test" / "2026-03.md"
    mar_content = mar_file.read_text()
    assert "## Week 10" in mar_content
    assert "week 10 msg" in mar_content

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

def test_transcript_day_headers():
    """Transcript inserts day separators when the date changes within a week."""
    import shutil
    test_dir = checker._LOGS_DIR / "day_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    base = {
        "campaign_name": "day_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "raw_text": "msg", "media_type": None, "caption": "",
    }

    # Monday Feb 23
    p1 = {**base, "msg_time_iso": "2026-02-23T10:00:00+00:00", "raw_text": "monday msg"}
    checker._append_to_transcript(p1, {"999"})

    # Wednesday Feb 25 (same week, different day)
    p2 = {**base, "msg_time_iso": "2026-02-25T14:00:00+00:00", "raw_text": "wednesday msg"}
    checker._append_to_transcript(p2, {"999"})

    # Still Wednesday (same day, no new header)
    p3 = {**base, "msg_time_iso": "2026-02-25T16:00:00+00:00", "raw_text": "still wed"}
    checker._append_to_transcript(p3, {"999"})

    content = (checker._LOGS_DIR / "day_test" / "2026-02.md").read_text()

    # Should have day headers for both Monday and Wednesday
    assert "📅 Monday, Feb 23" in content
    assert "📅 Wednesday, Feb 25" in content
    # Wednesday header only once
    assert content.count("📅 Wednesday") == 1
    # Week header present
    assert "## Week 9" in content

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

def test_transcript_silence_gap():
    """Transcript inserts silence markers for 12+ hour gaps."""
    import shutil
    test_dir = checker._LOGS_DIR / "silence_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    base = {
        "campaign_name": "silence_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "raw_text": "msg", "media_type": None, "caption": "",
    }

    # First message
    p1 = {**base, "msg_time_iso": "2026-02-23T08:00:00+00:00", "raw_text": "morning"}
    checker._append_to_transcript(p1, {"999"})

    # 2 hours later — no silence marker
    p2 = {**base, "msg_time_iso": "2026-02-23T10:00:00+00:00", "raw_text": "still here"}
    checker._append_to_transcript(p2, {"999"})

    # 18 hours later (same day-ish) — should get silence marker
    p3 = {**base, "msg_time_iso": "2026-02-24T04:00:00+00:00", "raw_text": "back after silence"}
    checker._append_to_transcript(p3, {"999"})

    content = (checker._LOGS_DIR / "silence_test" / "2026-02.md").read_text()

    # Should NOT have a silence marker for the 2h gap
    assert "2h of silence" not in content

    # Should have a day header for Feb 24 (which suppresses the silence marker since day changed)
    # Actually: silence markers only show when NO day/week header is shown.
    # The 18h gap crosses a day boundary, so the day header takes precedence.
    # Let's test same-day silence instead.

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    # Test same-day 14h silence
    p4 = {**base, "msg_time_iso": "2026-02-23T02:00:00+00:00", "raw_text": "late night"}
    checker._append_to_transcript(p4, {"999"})
    p5 = {**base, "msg_time_iso": "2026-02-23T16:00:00+00:00", "raw_text": "afternoon"}
    checker._append_to_transcript(p5, {"999"})

    content2 = (checker._LOGS_DIR / "silence_test" / "2026-02.md").read_text()
    assert "14h of silence" in content2

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()
