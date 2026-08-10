"""Scheduled tasks for PBP bot."""

from scheduled.tips import post_daily_tip
from scheduled.alerts import check_and_alert, check_player_activity
from scheduled.reports import post_roster_summary, post_pace_report
from scheduled.potw import player_of_the_week
from scheduled.potw_countdown import post_potw_countdown
from scheduled.potw_roundup import post_potw_roundup
from scheduled.milestones import (
    check_streak_milestones, check_anniversaries, _next_anniversary,
)
from scheduled.message_milestones import check_message_milestones
from scheduled.leaderboard import post_campaign_leaderboard
from scheduled.maintenance import (
    archive_weekly_data, cleanup_timestamps, check_recruitment_needs,
)
from scheduled.smart_alerts import check_pace_drop, check_conversation_dying
from scheduled.digest import post_weekly_digest
from scheduled.combat_ping import check_combat_turns, check_expired_timers

__all__ = [
    "post_daily_tip",
    "check_and_alert", "check_player_activity",
    "post_roster_summary", "post_pace_report",
    "player_of_the_week", "post_potw_countdown", "post_potw_roundup",
    "check_streak_milestones", "check_anniversaries", "_next_anniversary",
    "check_message_milestones",
    "post_campaign_leaderboard",
    "archive_weekly_data", "cleanup_timestamps", "check_recruitment_needs",
    "check_pace_drop", "check_conversation_dying",
    "post_weekly_digest",
    "check_combat_turns", "check_expired_timers",
]
