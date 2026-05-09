"""test_helpers.py — bin 4.

  - post_changelog
"""
"""Tests for helpers.py utilities."""

import sys
from datetime import datetime, timezone, timedelta

import helpers



def _utc(*args):
    """Shorthand for timezone-aware UTC datetime."""
    return datetime(*args, tzinfo=timezone.utc)

def _run_all():
    """Find and run all test_ functions, report results."""
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, func in sorted(tests):
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed

def test_changelog_read_latest_entry():
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from post_changelog import read_latest_entry, markdown_to_telegram

    # Create a minimal test changelog
    test_path = Path("/tmp/test_changelog.md")
    test_path.write_text(
        "# Changelog\n\n"
        "## [2.0.0] - 2026-03-01\n\n"
        "### Added\n- New feature\n\n"
        "## [1.0.0] - 2026-02-26\n\n"
        "### Added\n- Old feature\n"
    )
    header, body = read_latest_entry(test_path)
    assert "2.0.0" in header
    assert "New feature" in body
    assert "Old feature" not in body
    test_path.unlink()

def test_changelog_markdown_to_telegram():
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from post_changelog import markdown_to_telegram

    msg = markdown_to_telegram("## [1.0.0] - 2026-02-26", "### Added\n- **Bold item**: description\n- `code` thing")
    assert "<b>PBP Reminder Bot v1.0.0</b>" in msg
    assert "<b>Added</b>" in msg
    assert "<b>Bold item</b>" in msg
    assert "<code>code</code>" in msg
