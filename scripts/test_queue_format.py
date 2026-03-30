"""
Tests for commands/queue_format.py — shared queue entry formatting.

Covers the 8-tier age icon scale, age string formatting, and preview truncation.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import entry_age_icon, age_str, short_preview


# ── entry_age_icon — 8-tier scale ─────────────────────────────────────────────

@pytest.mark.parametrize("hours, expected", [
    # 🟢 just posted — < 6 h
    (0,      "🟢"),
    (3,      "🟢"),
    (5.9,    "🟢"),
    # ⚪ same day — 6–24 h
    (6,      "⚪"),
    (12,     "⚪"),
    (23.9,   "⚪"),
    # 🟡 1–2 d
    (24,     "🟡"),
    (36,     "🟡"),
    (47.9,   "🟡"),
    # 🟠 2–3 d
    (48,     "🟠"),
    (60,     "🟠"),
    (71.9,   "🟠"),
    # 🔴 3–5 d
    (72,     "🔴"),
    (96,     "🔴"),
    (119.9,  "🔴"),
    # 🟣 5–7 d
    (120,    "🟣"),
    (144,    "🟣"),
    (167.9,  "🟣"),
    # 🔵 7–14 d
    (168,    "🔵"),
    (240,    "🔵"),
    (335.9,  "🔵"),
    # 🟤 14 d+
    (336,    "🟤"),
    (719,    "🟤"),
    (720,    "⚫"),
    (1000,   "⚫"),
])
def test_entry_age_icon(hours, expected):
    assert entry_age_icon(hours) == expected


def test_icon_boundaries_are_exclusive_lower():
    """Each boundary value lands in the higher tier, not the lower."""
    assert entry_age_icon(6)   == "⚪"   # not 🟢
    assert entry_age_icon(24)  == "🟡"   # not ⚪
    assert entry_age_icon(48)  == "🟠"   # not 🟡
    assert entry_age_icon(72)  == "🔴"   # not 🟠
    assert entry_age_icon(120) == "🟣"   # not 🔴
    assert entry_age_icon(168) == "🔵"   # not 🟣
    assert entry_age_icon(336) == "🟤"   # not 🔵


def test_eight_distinct_icons():
    """All eight icon values are reachable and distinct."""
    icons = {entry_age_icon(h) for h in (0, 6, 24, 48, 72, 120, 168, 336)}
    assert len(icons) == 8


def test_icon_ordering_reflects_urgency():
    """Spot-check that urgency increases with age."""
    # Fresh should not equal abandoned
    assert entry_age_icon(0) != entry_age_icon(720)
    # Green is better than red
    assert entry_age_icon(1) == "🟢"
    assert entry_age_icon(500) == "🟤"


# ── age_str ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours, expected", [
    (0,    "0h"),
    (5,    "5h"),
    (23,   "23h"),
    (24,   "1d 0h"),
    (25,   "1d 1h"),
    (48,   "2d 0h"),
    (50,   "2d 2h"),
    (167,  "6d 23h"),
    (168,  "7d 0h"),
    (336,  "14d 0h"),
])
def test_age_str(hours, expected):
    assert age_str(hours) == expected


# ── short_preview ──────────────────────────────────────────────────────────────

def test_preview_short_text_unchanged():
    assert short_preview("hello world", words=5) == "hello world"


def test_preview_exact_word_count_unchanged():
    assert short_preview("one two three four five", words=5) == "one two three four five"


def test_preview_truncates_with_ellipsis():
    result = short_preview("one two three four five six", words=5)
    assert result == "one two three four five..."


def test_preview_newlines_treated_as_spaces():
    result = short_preview("line one\nline two\nline three", words=4)
    assert "..." in result
    assert "\n" not in result


def test_preview_empty_string():
    assert short_preview("", words=5) == ""


def test_preview_custom_word_count():
    result = short_preview("a b c d e f g", words=3)
    assert result == "a b c..."
