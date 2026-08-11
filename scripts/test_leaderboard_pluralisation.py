"""Leaderboard counts pluralise (2026-08-11).

Reported from the live weekly post, which read:

    [6. C06: Kibwe]
    - 1 player posts.
    - 5 posts total.
    - 4 GM posts.

``posts_str`` already existed and handles "1 post" correctly — the *total*
line was fine. But the qualified counts were hand-rolled f-strings
(``f"{c['player_7d']} player posts"``) which bypassed it entirely, so any
campaign with exactly one player post or one GM post read wrong.

Also worth a guard because the first fix attempt **silently no-op'd**: a
scripted string replacement did not match, so the import landed and the
f-strings did not. Nothing failed — the suite stayed green and the bug
shipped in the diff. A test asserting the rendered output is the only
thing that catches a formatting change that did not happen.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


class TestCountStr:
    def test_one_is_singular(self):
        from helpers import count_str
        assert count_str(1, "player post") == "1 player post"

    def test_zero_is_plural(self):
        from helpers import count_str
        assert count_str(0, "GM post") == "0 GM posts"

    def test_many_is_plural(self):
        from helpers import count_str
        assert count_str(7, "GM post") == "7 GM posts"

    def test_irregular_plural_is_supported(self):
        from helpers import count_str
        assert count_str(2, "entry", "entries") == "2 entries"

    def test_posts_str_still_behaves(self):
        """posts_str now delegates; its contract must not have shifted."""
        from helpers import posts_str
        assert posts_str(1) == "1 post"
        assert posts_str(0) == "0 posts"
        assert posts_str(5) == "5 posts"


class TestRenderedBlock:
    """Assert the actual rendered text, not just the helper.

    The helper being correct does not prove the leaderboard uses it — that
    was exactly the failure mode when the edit silently did not apply.
    """

    def _stats(self, player, gm, total):
        return [{
            "code": "C06", "name": "Kibwe", "trend_icon": "📉",
            "player_7d": player, "gm_7d": gm, "total_7d": total,
            "avg_gap_str": "38.7h", "last_post_str": "12h ago",
            # Shape mirrors the fixture in test_checker_format.py.
            "player_avg_gap": 38.7, "player_avg_gap_str": "38.7h",
            "top_players": [],
        }]

    def _render(self, stats):
        from datetime import datetime, timezone
        from scheduled.leaderboard import _format_leaderboard
        now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
        out = _format_leaderboard(stats, {}, now)
        return out if isinstance(out, str) else "\n".join(out)

    def test_single_player_post_is_singular(self):
        text = self._render(self._stats(player=1, gm=4, total=5))
        assert "- 1 player post." in text
        assert "1 player posts" not in text, "the reported bug"

    def test_single_gm_post_is_singular(self):
        text = self._render(self._stats(player=3, gm=1, total=4))
        assert "- 1 GM post." in text
        assert "1 GM posts" not in text

    def test_plurals_still_read_correctly(self):
        text = self._render(self._stats(player=11, gm=7, total=18))
        assert "- 11 player posts." in text
        assert "- 7 GM posts." in text

    def test_zero_is_plural(self):
        """C09 Metal City had 0 player posts in the reported week."""
        text = self._render(self._stats(player=0, gm=1, total=1))
        assert "- 0 player posts." in text
        assert "- 1 GM post." in text
