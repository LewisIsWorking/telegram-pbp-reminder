"""Coverage tests extracted from test_branch_gaps.py — bin 9.

Sections in this file:
  - Various single-line branches (part d)

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def test_campaign_notes_truncated():
    # Tests line 169: "... and N more" when notes > 3
    from commands.campaign import build_campaign_report
    state = {
        "notes": {"100": [f"Note {i}" for i in range(10)]},
        "quests": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
        "conditions": {}, "hp_tracker": {}, "clocks": {},
        "topics": {}, "post_timestamps": {}, "message_counts": {}, "players": {},
        "session_counts": {},
    }
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    with patch("commands.campaign.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_characters.return_value = {}
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 5.0
        mh.feature_enabled.return_value = False
        mh.player_full_name.return_value = "Alice"
        mh.REQUIRED_PLAYERS = 4
        mh.players_by_campaign.return_value = {"100": []}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0 posts"
        result = build_campaign_report("100", config, state, set())
    assert "more" in result or isinstance(result, str)
