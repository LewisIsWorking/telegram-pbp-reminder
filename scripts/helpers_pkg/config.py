"""
Helpers: config loading and validation.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from helpers_pkg.constants import *
from helpers_pkg.time_utils import timestamps_in_window


def load_config() -> dict:
    """Load and return the config.json file."""
    with open(CONFIG_PATH, encoding="utf-8") as f:  # pragma: no cover
        return json.load(f)  # pragma: no cover



_SETTINGS_MAP = {
    "player_warn_weeks": "PLAYER_WARN_WEEKS",
    "player_remove_weeks": "PLAYER_REMOVE_WEEKS",
    "roster_interval_days": "ROSTER_INTERVAL_DAYS",
    "potw_interval_days": "POTW_INTERVAL_DAYS",
    "potw_min_posts": "POTW_MIN_POSTS",
    "pace_interval_days": "PACE_INTERVAL_DAYS",
    "leaderboard_interval_days": "LEADERBOARD_INTERVAL_DAYS",
    "combat_ping_hours": "COMBAT_PING_HOURS",
    "recruitment_interval_days": "RECRUITMENT_INTERVAL_DAYS",
    "required_players": "REQUIRED_PLAYERS",
    "post_session_minutes": "POST_SESSION_MINUTES",
}



def load_settings(config: dict) -> None:
    """Load tunable settings from config, applying defaults for any missing keys."""
    g = globals()
    s = config.get("settings", {})
    for config_key, global_name in _SETTINGS_MAP.items():
        if config_key in s:
            g[global_name] = s[config_key]  # pragma: no cover



def pace_split(topic_ts: dict[str, list[str]], gm_ids: set[str],
               now: datetime) -> dict:
    """Compute GM/player post splits for this week vs last week.

    Counts posting sessions (posts within POST_SESSION_MINUTES collapsed),
    not raw messages.

    Returns dict with: gm_this, gm_last, player_this, player_last.
    """
    from helpers_pkg.formatting import deduplicate_posts

    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    gm_this = gm_last = player_this = player_last = 0
    for uid, timestamps in topic_ts.items():
        this_count = len(deduplicate_posts(timestamps_in_window(timestamps, week_ago)))
        last_count = len(deduplicate_posts(timestamps_in_window(timestamps, two_weeks_ago, week_ago)))
        if uid in gm_ids:
            gm_this += this_count
            gm_last += last_count
        else:
            player_this += this_count
            player_last += last_count
    return {
        "gm_this": gm_this, "gm_last": gm_last,
        "player_this": player_this, "player_last": player_last,
    }



def validate_config(config: dict) -> list[str]:
    """Validate config structure and return a list of error/warning strings.

    Fatal errors are prefixed with 'ERROR:'. Warnings with 'WARNING:'.
    Caller should abort if any ERROR lines are returned.
    """
    issues = []

    # Required top-level keys
    gid = config.get("group_id")
    if not isinstance(gid, int) or gid >= 0:
        issues.append("ERROR: group_id must be a negative integer")

    if not config.get("gm_user_ids"):
        issues.append("WARNING: gm_user_ids is empty; GM posts will count as player posts")

    pairs = config.get("topic_pairs")
    if not pairs or not isinstance(pairs, list):
        issues.append("ERROR: topic_pairs must be a non-empty list")
        return issues

    # Per-campaign validation
    all_pbp_ids = set()
    all_chat_ids = set()
    all_names = set()

    for i, pair in enumerate(pairs):
        label = pair.get("name", f"topic_pairs[{i}]")

        if not pair.get("name"):
            issues.append(f"ERROR: {label} missing 'name'")  # pragma: no cover

        if "chat_topic_id" not in pair:
            issues.append(f"ERROR: {label} missing 'chat_topic_id'")

        pbp_ids = pair.get("pbp_topic_ids")
        if not pbp_ids or not isinstance(pbp_ids, list):
            issues.append(f"ERROR: {label} 'pbp_topic_ids' must be a non-empty list")
            continue

        # Check for duplicates
        if pair.get("name") in all_names:
            issues.append(f"WARNING: duplicate campaign name '{pair['name']}'")  # pragma: no cover
        all_names.add(pair.get("name"))

        chat_id = pair.get("chat_topic_id")
        if chat_id in all_chat_ids:
            issues.append(f"WARNING: {label} chat_topic_id {chat_id} used by another campaign")
        all_chat_ids.add(chat_id)

        for tid in pbp_ids:
            tid_str = str(tid)
            if tid_str in all_pbp_ids:
                issues.append(f"ERROR: {label} pbp_topic_id {tid} used by another campaign")
            all_pbp_ids.add(tid_str)

        # Validate disabled_features if present
        valid_features = {"roster", "potw", "pace", "recruitment", "combat", "anniversary", "alerts", "warnings"}
        disabled = pair.get("disabled_features", [])
        for feat in disabled:
            if feat not in valid_features:
                issues.append(f"WARNING: {label} unknown feature '{feat}' in disabled_features "
                              f"(valid: {', '.join(sorted(valid_features))})")

        # Validate created date format if present
        created = pair.get("created")
        if created:
            try:
                datetime.strptime(created, "%Y-%m-%d")
            except (ValueError, TypeError):
                issues.append(f"ERROR: {label} 'created' must be YYYY-MM-DD format, got '{created}'")

    # Leaderboard topic collision
    lb = config.get("leaderboard_topic_id")
    if lb and str(lb) in all_pbp_ids:
        issues.append("WARNING: leaderboard_topic_id collides with a PBP topic ID")

    return issues



def gm_id_set(config: dict) -> set:
    """Return global GM user IDs as a set of strings."""
    return set(str(uid) for uid in config.get("gm_user_ids", []))



def gm_ids_for_campaign(config: dict, pid: str) -> set:
    """Return GM IDs for a specific campaign.

    If the campaign's topic_pair has its own ``gm_user_ids``, use that
    (replacing the global list). Otherwise fall back to the global list.
    """
    for pair in config.get("topic_pairs", []):
        all_ids = [str(pair.get("chat_topic_id", ""))] + [str(x) for x in pair.get("pbp_topic_ids", [])]
        if pid in all_ids:
            if "gm_user_ids" in pair:
                return set(str(uid) for uid in pair["gm_user_ids"])
            break
    return gm_id_set(config)



def feature_enabled(config: dict, pid: str, feature: str) -> bool:
    """Return True unless the campaign has this feature in its disabled_features list."""
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return feature not in pair.get("disabled_features", [])
    return True

