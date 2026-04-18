"""Tests for queue_format helpers — new 22-tier age icon scale."""

import pytest
from commands.queue_format import entry_age_icon, age_str, short_preview


# ── entry_age_icon — 22-tier scale ─────────────────────────────────────────────

@pytest.mark.parametrize("hours, expected", [
    # 🆕 < 1h
    (0,      "🆕"),
    (0.5,    "🆕"),
    (0.99,   "🆕"),
    # 🌱 1–6h
    (1,      "🌱"),
    (3,      "🌱"),
    (5.9,    "🌱"),
    # 🌿 6–12h
    (6,      "🌿"),
    (9,      "🌿"),
    (11.9,   "🌿"),
    # 🌳 12–24h
    (12,     "🌳"),
    (18,     "🌳"),
    (23.9,   "🌳"),
    # Days 1–16
    (24,     "🟢"),   # day 1
    (47.9,   "🟢"),
    (48,     "🟩"),   # day 2
    (71.9,   "🟩"),
    (72,     "🟡"),   # day 3
    (95.9,   "🟡"),
    (96,     "🟨"),   # day 4
    (119.9,  "🟨"),
    (120,    "🟠"),   # day 5
    (143.9,  "🟠"),
    (144,    "🟧"),   # day 6
    (167.9,  "🟧"),
    (168,    "🔴"),   # day 7
    (191.9,  "🔴"),
    (192,    "🟥"),   # day 8
    (215.9,  "🟥"),
    (216,    "🟣"),   # day 9
    (239.9,  "🟣"),
    (240,    "🟪"),   # day 10
    (263.9,  "🟪"),
    (264,    "🔵"),   # day 11
    (287.9,  "🔵"),
    (288,    "🟦"),   # day 12
    (311.9,  "🟦"),
    (312,    "🟤"),   # day 13
    (335.9,  "🟤"),
    (336,    "🟫"),   # day 14
    (359.9,  "🟫"),
    (360,    "⚫"),   # day 15
    (383.9,  "⚫"),
    (384,    "⬛"),   # day 16
    (407.9,  "⬛"),
    # 💀 day 17–25
    (408,    "💀"),
    (480,    "💀"),
    (503.9,  "💀"),
    (503.9,  "💀"),
    (504,    "💀"),
    # ☠️  day 25+
    (600,    "☠️"),
    (1000,   "☠️"),
])
def test_entry_age_icon(hours, expected):
    assert entry_age_icon(hours) == expected


def test_twenty_two_distinct_icons():
    """All 22 icon values are reachable and distinct."""
    sample_hours = [0, 1, 6, 12, 24, 48, 72, 96, 120, 144, 168, 192,
                    216, 240, 264, 288, 312, 336, 360, 384, 408, 600]
    icons = [entry_age_icon(h) for h in sample_hours]
    assert len(set(icons)) == 22, f"Expected 22 distinct icons, got {len(set(icons))}: {icons}"


def test_icon_ordering_reflects_urgency():
    """Icons should change as time increases."""
    hours = [0, 1, 6, 12, 24, 48, 72, 96, 120, 144, 168, 192,
             216, 240, 264, 288, 312, 336, 360, 384, 408, 600]
    icons = [entry_age_icon(h) for h in hours]
    # Each consecutive pair should differ
    for i in range(len(icons) - 1):
        assert icons[i] != icons[i + 1], \
            f"Icons at {hours[i]}h and {hours[i+1]}h are both {icons[i]}"


# ── age_str ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours, expected", [
    (0,     "0h"),
    (1,     "1h"),
    (5,     "5h"),
    (23,    "23h"),
    (24,    "1d 0h"),
    (25,    "1d 1h"),
    (47,    "1d 23h"),
    (48,    "2d 0h"),
    (100,   "4d 4h"),
])
def test_age_str(hours, expected):
    assert age_str(hours) == expected


# ── short_preview ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, words, expected", [
    ("hello world", 15, "hello world"),
    ("a b c d e f g h i j k l m n o p", 15, "a b c d e f g h i j k l m n o..."),
    ("one two three", 2, "one two..."),
    ("one two", 2, "one two"),
    ("", 15, ""),
    ("single", 15, "single"),
])
def test_short_preview(text, words, expected):
    assert short_preview(text, words) == expected


def test_short_preview_default_is_15_words():
    text = " ".join(str(i) for i in range(20))
    result = short_preview(text)
    assert result.endswith("...")
    assert len(result.split()) == 15  # 15 words, last one ends with "..."

# ── format_queue_line ──────────────────────────────────────────────────────────

def test_format_queue_line_includes_message_id():
    """Entry line includes [message_id] when present."""
    from commands.queue_format import format_queue_line
    entry = {"name": "Alice", "preview": "Hello world",
             "message_id": "1970", "link": ""}
    line = format_queue_line(1, entry, 2.0)
    assert "[1970]" in line
    assert "01" in line
    assert "Alice" in line


def test_format_queue_line_no_message_id():
    """Entry line omits id bracket when message_id is absent."""
    from commands.queue_format import format_queue_line
    entry = {"name": "Bob", "preview": "Hey", "link": ""}
    line = format_queue_line(3, entry, 0.5)
    assert "[" not in line
    assert "03" in line
    assert "Bob" in line


def test_format_queue_line_includes_link():
    """Entry line appends link when present."""
    from commands.queue_format import format_queue_line
    entry = {"name": "Alice", "preview": "Hi", "message_id": "42",
             "link": "https://t.me/Path_Wars/100/42"}
    line = format_queue_line(1, entry, 1.5)
    assert "https://t.me" in line
    assert "🔗" in line

def test_format_queue_line_extracts_id_from_link():
    """When message_id is None, ID is extracted from the link URL."""
    from commands.queue_format import format_queue_line
    entry = {"name": "Alice", "preview": "Hi", "message_id": None,
             "link": "https://t.me/Path_Wars/107171/1970"}
    line = format_queue_line(1, entry, 2.0)
    assert "[1970]" in line


def test_format_queue_line_no_id_no_link():
    """When both message_id and link are absent, no brackets shown."""
    from commands.queue_format import format_queue_line
    entry = {"name": "Bob", "preview": "Hey"}
    line = format_queue_line(2, entry, 0.5)
    assert "[" not in line
    assert "02" in line
