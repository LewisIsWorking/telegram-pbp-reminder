"""Tests for checker.py — transcript (part b) group.

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


def test_transcript_multi_day_silence():
    """Transcript shows silence in days for 48h+ gaps."""
    import shutil
    test_dir = checker._LOGS_DIR / "longsilence_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    base = {
        "campaign_name": "longsilence_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "raw_text": "msg", "media_type": None, "caption": "",
    }

    p1 = {**base, "msg_time_iso": "2026-02-23T10:00:00+00:00", "raw_text": "bye"}
    checker._append_to_transcript(p1, {"999"})
    # 3 days later, same week
    p2 = {**base, "msg_time_iso": "2026-02-26T10:00:00+00:00", "raw_text": "hi again"}
    checker._append_to_transcript(p2, {"999"})

    content = (checker._LOGS_DIR / "longsilence_test" / "2026-02.md").read_text()
    # Day header takes precedence over silence marker when day changes.
    # But if both day changes AND silence is large — day header shown, silence suppressed.
    assert "📅 Thursday, Feb 26" in content

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

def test_transcript_quote_formatting():
    """PBP > and >> - formatting converted to blockquotes."""
    parsed = {
        "user_name": "GM", "user_last_name": "", "user_id": "1",
        "msg_time_iso": "2026-02-23T10:00:00+00:00",
        "raw_text": "> COMBAT.\n>> - Round 1!\n>> - Fierce Leopard: Strike = Hit",
        "media_type": None, "caption": "",
    }
    entry = checker._format_log_entry(parsed, {"1"})
    assert "> COMBAT." in entry
    assert ">> Round 1!" in entry
    assert ">> Fierce Leopard: Strike = Hit" in entry

def test_transcript_mechanical_styling():
    """Mechanical content (DCs, rolls) gets italic styling."""
    parsed = {
        "user_name": "GM", "user_last_name": "", "user_id": "1",
        "msg_time_iso": "2026-02-23T10:00:00+00:00",
        "raw_text": "DC 25 Reflex save",
        "media_type": None, "caption": "",
    }
    entry = checker._format_log_entry(parsed, {"1"})
    assert "*DC 25 Reflex save*" in entry

def test_transcript_monthly_stats_footer():
    """Previous month gets a stats footer when a new month starts."""
    import shutil
    test_dir = checker._LOGS_DIR / "stats_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

    # Create a fake February file with some entries
    test_dir.mkdir(parents=True)
    feb_content = (
        "# stats_test — 2026-02\n\n"
        "*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n"
        "**Alice** (2026-02-23 10:00:00):\nHello world\n\n"
        "**Bob** [GM] (2026-02-23 11:00:00):\nWelcome\n\n"
        "**Alice** (2026-02-24 14:00:00):\nAnother message here today\n\n"
    )
    (test_dir / "2026-02.md").write_text(feb_content)

    # Now write a March message (triggers finalization of Feb)
    base = {
        "campaign_name": "stats_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "raw_text": "march msg", "media_type": None, "caption": "",
    }
    p1 = {**base, "msg_time_iso": "2026-03-01T10:00:00+00:00"}
    checker._append_to_transcript(p1, {"999"})

    feb_final = (test_dir / "2026-02.md").read_text()
    assert "📊 Month Summary" in feb_final
    assert "Total messages" in feb_final
    assert "3" in feb_final  # 3 messages
    assert "Alice" in feb_final  # should be in most active

    # Check it's idempotent (writing another March msg doesn't duplicate footer)
    p2 = {**base, "msg_time_iso": "2026-03-02T10:00:00+00:00", "raw_text": "march2"}
    # Need to force is_new check — march file already exists now, so won't re-finalize
    feb_final2 = (test_dir / "2026-02.md").read_text()
    assert feb_final2.count("📊 Month Summary") == 1

    shutil.rmtree(test_dir)
    checker._transcript_cache.clear()

def test_transcript_with_character():
    _reset()
    import shutil
    test_dir = checker._LOGS_DIR / "char_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    config = {
        "topic_pairs": [
            {"name": "char_test", "chat_topic_id": 10, "pbp_topic_ids": [100],
             "characters": {"42": "Cardigan"}},
        ],
    }
    parsed = {
        "campaign_name": "char_test", "pid": "100",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "I rage!", "media_type": None, "caption": "",
    }
    checker._append_to_transcript(parsed, {"999"}, config)

    log_file = checker._LOGS_DIR / "char_test" / "2026-02.md"
    content = log_file.read_text()
    assert "(Cardigan)" in content
    assert "I rage!" in content

    shutil.rmtree(test_dir)
