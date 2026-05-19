"""Tests for the per-topic slim queue format + caught-up builder.

Lewis 2026-05-19: Cannon (player) flagged the per-topic pinned queue
as meta brick in the RP channels. The fix shipped a slim format
(no legend, no quote, no separator, no numbered prefix) and a
caught-up message that tags the active roster on transition. See
L27 in REFACTOR_PROGRESS.md.
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))


_NOW = datetime(2026, 5, 19, 13, 0, 0, tzinfo=timezone.utc)


# ── format_topic_queue: slim per-line format ────────────────────────────────

def _e(name="Ryo Yamakawa", t="2026-05-19 12:00:00",
       link="https://t.me/Path_Wars/51357/153422"):
    """Entry shape used by the per-topic queue."""
    return {"name": name, "time": t, "preview": "ignored in slim", "link": link}


class TestSlimLineFormat:
    def test_line_uses_first_name_only(self):
        """``↗ Ryo …`` not ``↗ Ryo Yamakawa …``. First-name only keeps
        the slim line scannable for players in their own channel."""
        from commands.topic_queue_format import format_topic_queue
        out = "\n".join(format_topic_queue([_e()], _NOW))
        assert "↗ Ryo · " in out
        assert "Yamakawa" not in out

    def test_line_has_age_icon_and_age(self):
        """Age icon (🌳, 🌱 etc) and age string kept — urgency hint
        survives the trim. Lewis specifically asked to keep the icon."""
        from commands.topic_queue_format import format_topic_queue
        # 1h ago → 🌱
        e = _e(t="2026-05-19 12:00:00")  # _NOW is 13:00:00
        out = "\n".join(format_topic_queue([e], _NOW))
        assert "🌱" in out and "1h" in out

    def test_line_has_bare_link_no_emoji(self):
        """Slim format drops the 🔗 emoji prefix. The ↗ at line start
        is the navigation hint; the bare URL renders as a clickable
        link in Telegram on its own."""
        from commands.topic_queue_format import format_topic_queue
        out = "\n".join(format_topic_queue([_e()], _NOW))
        assert "https://t.me/Path_Wars/51357/153422" in out
        assert "🔗" not in out

    def test_no_quote_preview(self):
        """The quote/preview text Lewis defended for the BOT-TOPIC
        queue is dropped here. Players are in the topic already; they
        can scroll up to read the message in context."""
        from commands.topic_queue_format import format_topic_queue
        e = _e()
        e["preview"] = "And who is this master? Some long preview text..."
        out = "\n".join(format_topic_queue([e], _NOW))
        assert "master" not in out
        assert "preview" not in out

    def test_no_numbered_prefix(self):
        """01/02/03 numbering is bot-topic territory. Per-topic the
        ↗ prefix carries the visual cue."""
        from commands.topic_queue_format import format_topic_queue
        out = "\n".join(format_topic_queue([_e("A"), _e("B")], _NOW))
        assert "01" not in out and "02" not in out

    def test_no_age_legend(self):
        """The big Age: 🆕<1h 🌱6h 🌿12h … brick is gone. Header is
        just ``📋 Unreplied: N``."""
        from commands.topic_queue_format import format_topic_queue
        out = "\n".join(format_topic_queue([_e()], _NOW))
        assert "Age:" not in out
        assert "🆕<1h" not in out

    def test_no_separator_line(self):
        """The ━━━━━━━━ separator at the top is also gone. Header sits
        flush; less visual weight in pinned pin previews."""
        from commands.topic_queue_format import format_topic_queue
        out = "\n".join(format_topic_queue([_e()], _NOW))
        assert "━━━" not in out

    def test_link_omitted_cleanly_when_missing(self):
        """No dangling ``· `` separator when an entry has no link."""
        from commands.topic_queue_format import format_topic_queue
        e = _e(link="")
        out = "\n".join(format_topic_queue([e], _NOW))
        assert "https://" not in out
        # Line ends after the age, no trailing dot-separator.
        assert "↗ Ryo · 🌱 1h" in out
        # No mid-dot followed by whitespace/EOL.
        for line in out.splitlines():
            if line.startswith("↗"):
                assert not line.rstrip().endswith("·")


# ── build_caught_up_text: roster tagging + edge cases ───────────────────────

def _player(uid, username, permanent=False, last_post=None):
    return {
        "user_id": str(uid),
        "first_name": username.capitalize(),
        "username": username,
        "pbp_topic_id": "100",
        "permanent": permanent,
        "last_post_time": last_post or "2026-05-19 12:00:00",
    }


def _config_with_perms(perm_user_ids=None):
    return {
        "permanent_user_ids": perm_user_ids or [],
    }


def _state_with(*players):
    return {
        "players": {f"100:{p['user_id']}": p for p in players},
    }


class TestCaughtUpBuilder:
    def test_no_state_falls_back_to_bare(self):
        """state=None means caller couldn't compute roster — emit
        the bare ``📋 All caught up here.`` form."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        out = build_caught_up_text("100", None, _config_with_perms())
        assert out == "📋 All caught up here."

    def test_no_active_players_falls_back_to_bare(self):
        """Empty roster → bare form, no dangling ``Time for players to
        post!`` with no players to nudge."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        state = _state_with()  # no players
        out = build_caught_up_text("100", state, _config_with_perms())
        assert out == "📋 All caught up here."

    def test_with_active_players_tags_them_with_nudge(self):
        """Non-empty roster → full nudge header + space-joined mentions."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        state = _state_with(
            _player("1", "alice"),
            _player("2", "bob"),
        )
        out = build_caught_up_text("100", state, _config_with_perms())
        assert "📋 All caught up. Time for players to post!" in out
        assert "@alice" in out and "@bob" in out

    def test_includes_perm_players_via_per_record_flag(self):
        """Perm players (per-record flag True) appear in tags too."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        state = _state_with(
            _player("1", "alice"),
            _player("99", "permabob", permanent=True),
        )
        out = build_caught_up_text("100", state, _config_with_perms())
        assert "@alice" in out and "@permabob" in out

    def test_includes_perm_players_via_config_list(self):
        """Perm players (config permanent_user_ids) appear in tags too.
        This is the Anthony/Horia/Ryo path post-4.50.0."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        # Bob is in config but not flagged per-record — should still tag.
        state = _state_with(
            _player("1", "alice"),
            _player("99", "permabob"),  # permanent=False per-record
        )
        config = _config_with_perms(perm_user_ids=["99"])
        out = build_caught_up_text("100", state, config)
        assert "@alice" in out and "@permabob" in out

    def test_excludes_players_in_other_campaigns(self):
        """Only the queried pid's roster — players in OTHER campaigns
        (different pbp_topic_id) are not tagged here."""
        from scheduled.per_topic_caught_up import build_caught_up_text
        state = _state_with(_player("1", "alice"))
        # Add a player in a different campaign
        state["players"]["999:2"] = {
            "user_id": "2", "first_name": "Bob", "username": "bob",
            "pbp_topic_id": "999", "permanent": False,
            "last_post_time": "2026-05-19 12:00:00",
        }
        out = build_caught_up_text("100", state, _config_with_perms())
        assert "@alice" in out
        assert "@bob" not in out, (
            "Bob is in pid 999, not the queried 100 — must not be tagged"
        )