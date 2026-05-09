"""Coverage tests extracted from test_branch_gaps.py — bin 5.

Sections in this file:
  - scheduled/campaign_table.py: post_campaign_table

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


# ─── scheduled/campaign_table.py: post_campaign_table ────────────────────────

def test_campaign_table_skips_no_bot_topic():
    from scheduled.campaign_table import post_campaign_table
    post_campaign_table({"group_id": -1}, {})


def test_campaign_table_skips_interval():
    from scheduled.campaign_table import post_campaign_table
    config = {"group_id": -1, "bot_topic_id": 999}
    with patch("scheduled.campaign_table.helpers") as mh:
        mh.interval_elapsed.return_value = False
        post_campaign_table(config, {"last_campaign_table": "recent"})


def test_campaign_table_posts():
    from scheduled.campaign_table import post_campaign_table
    config = {"group_id": -1001, "bot_topic_id": 999}
    with patch("scheduled.campaign_table.helpers") as mh, \
         patch("scheduled.campaign_table.build_campaign_table", return_value="table"):
        mh.interval_elapsed.return_value = True
        state = {}
        post_campaign_table(config, state)
        assert "last_campaign_table" in state


