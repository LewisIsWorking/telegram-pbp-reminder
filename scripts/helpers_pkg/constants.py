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

# Legacy rolling-interval gate. No longer decides when POTW fires (that
# is a fixed weekday now, see POTW_WEEKDAY) but kept because the settings
# block and older state files still reference it.
POTW_INTERVAL_DAYS = 7

POTW_MIN_POSTS = 5

# POTW fires on a fixed calendar weekday rather than a rolling 7-day
# interval. The old interval anchored to "7 days since this campaign last
# posted one", which drifted later every week; and because a week with
# too few posts hit `continue` WITHOUT stamping last_potw, the gate
# stayed open and fired on the first tick after activity resumed — i.e.
# seemingly at random, whenever a player happened to post. 0 = Monday.
POTW_WEEKDAY = 0

# Midweek "who is currently winning" standings post. 3 = Thursday.
POTW_COUNTDOWN_WEEKDAY = 3

# UTC hour both posts wait for, so they land at a predictable time rather
# than whenever the cron first ticks past a threshold.
POTW_POST_HOUR = 9

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
