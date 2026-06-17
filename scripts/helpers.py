"""
Helpers: re-export facade.

All helper functions and constants are defined in helpers_pkg/ submodules.
This file re-exports them so existing `import helpers` / `helpers.xxx` code
continues to work unchanged.
"""

from helpers_pkg.constants import (
    CONFIG_PATH, BOONS_PATH, ARCHIVE_PATH, PLAYER_WARN_WEEKS,
    PLAYER_REMOVE_WEEKS, ROSTER_INTERVAL_DAYS, POTW_INTERVAL_DAYS, POTW_MIN_POSTS,
    PACE_INTERVAL_DAYS, LEADERBOARD_INTERVAL_DAYS, COMBAT_PING_HOURS, RECRUITMENT_INTERVAL_DAYS,
    REQUIRED_PLAYERS, POST_SESSION_MINUTES, MECHANICAL_BOONS,
)

from helpers_pkg.config import (
    load_config, _SETTINGS_MAP, load_settings, pace_split,
    validate_config, gm_id_set, gm_ids_for_campaign, feature_enabled,
)

from helpers_pkg.formatting import (
    RANK_ICONS, rank_icon, fmt_date, html_escape,
    display_name, player_mention, player_full_name, posts_str,
    fmt_relative_date, fmt_brief_relative, trend_icon, deduplicate_posts,
    calc_avg_gap_str,
)

from helpers_pkg.time_utils import (
    hours_since, days_since, interval_elapsed, timestamps_in_window,
    avg_gap_hours, is_away, parse_away_duration,
)

from helpers_pkg.topic_maps import (
    TopicMaps, _topic_maps_cache, build_topic_maps, get_characters,
    character_name, players_by_campaign, get_topic_timestamps, get_player,
    campaign_dir_name,
)

from helpers_pkg.dice import roll_dice

from helpers_pkg.campaigns import (
    get_pair, get_code, get_name, get_label,
    is_hybrid, is_priority, is_excluded,
    all_pids, iter_campaigns,
)

from helpers_pkg.dc_lookup import (
    _STANDARD_DC, _DC_ADJUSTMENTS, _PROF_DC, _DC_ALIASES,
    dc_lookup, _dc_help,
)

from helpers_pkg.mechanics import (
    parse_timer_duration, hp_bar, hp_status_icon, clock_display,
    calc_streak, _HEALTH_THRESHOLDS, health_icon,
)

from helpers_pkg.groups import (
    group_id_for_campaign, linked_poll_codes,
    all_group_ids, pid_for_code, campaign_link_target,
)
