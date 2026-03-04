"""
Helpers: config.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ------------------------------------------------------------------ #
#  Paths
# ------------------------------------------------------------------ #
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

BOONS_PATH = Path(__file__).parent.parent.parent / "boons.json"

ARCHIVE_PATH = Path(__file__).parent.parent.parent / "data" / "weekly_archive.json"

# ------------------------------------------------------------------ #
#  Tunable settings (defaults, overridden by config.json settings block)
# ------------------------------------------------------------------ #
PLAYER_WARN_WEEKS = [1, 2, 3]

PLAYER_REMOVE_WEEKS = 4

ROSTER_INTERVAL_DAYS = 3

POTW_INTERVAL_DAYS = 7

POTW_MIN_POSTS = 5

PACE_INTERVAL_DAYS = 7

LEADERBOARD_INTERVAL_DAYS = 3

COMBAT_PING_HOURS = 4

RECRUITMENT_INTERVAL_DAYS = 14

REQUIRED_PLAYERS = 6

POST_SESSION_MINUTES = 10


MECHANICAL_BOONS = [
    "+1 circumstance bonus on your next skill check.",
    "Recover 1d6 extra HP during your next rest.",
    "Your next critical failure on a skill check is a regular failure instead.",
    "Gain a +1 circumstance bonus to initiative in your next combat.",
    "+1 circumstance bonus to your next saving throw.",
    "Your next successful Strike deals 1 extra damage.",
    "Gain 1 temporary HP at the start of your next combat.",
    "Your next Recall Knowledge check gains a +2 circumstance bonus.",
    "+10 feet to your Speed for your first turn of your next combat.",
    "The DC of your next skill check is reduced by 1.",
]

# ------------------------------------------------------------------ #
#  Config loading
# ------------------------------------------------------------------ #
