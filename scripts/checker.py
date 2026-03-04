"""
PBP Inactivity Checker for GitHub Actions

Orchestrator that runs hourly via cron. Processes Telegram messages
and triggers all bot features (alerts, rosters, POTW, leaderboards, etc).

State is persisted between runs using a GitHub Gist.
Modules: telegram.py (API), state.py (persistence), helpers.py (utilities).
"""

import os
import sys
import json
import re
import random
from datetime import datetime, timezone

import helpers
import telegram as tg
import state as state_store

from helpers import build_topic_maps

# --- Dispatch ---
from dispatch.router import process_updates

# --- Scheduled tasks (used by _run_checks) ---
from scheduled.tips import post_daily_tip
from scheduled.alerts import check_and_alert, check_player_activity
from scheduled.reports import post_roster_summary, post_pace_report
from scheduled.potw import player_of_the_week
from scheduled.milestones import check_streak_milestones, check_anniversaries
from scheduled.message_milestones import check_message_milestones
from scheduled.leaderboard import post_campaign_leaderboard
from scheduled.maintenance import (
    archive_weekly_data, cleanup_timestamps, check_recruitment_needs,
)
from scheduled.smart_alerts import check_pace_drop, check_conversation_dying
from scheduled.digest import post_weekly_digest
from scheduled.combat_ping import check_combat_turns, check_expired_timers
from boons.handler import expire_pending_boons
from transcript.finalize import update_transcript_index

# --- Backward-compat aliases for test_checker.py ---
from boons.handler import (
    _format_boon_result, process_boon_callback,
    choose_boon_by_text, build_boons, build_boons_all,
)
from combat.display import (
    build_whosturn as _build_whosturn,
    format_elapsed as _format_elapsed,
    build_combatlog as _build_combatlog,
)
from combat.tracker import (
    handle_combat_message as _handle_combat_message,
    handle_round_command as _handle_round_command,
)
from combat.commands import (
    handle_combat_start as _handle_combat_start,
    handle_next_command as _handle_next_command,
    handle_endcombat as _handle_endcombat,
    handle_enemies_command as _handle_enemies_command,
)
from parsing.message import parse_message as _parse_message
from commands.status import (
    build_status as _build_status, build_overview as _build_overview,
)
from commands.campaign import (
    build_campaign_report as _build_campaign_report,
    roster_user_stats as _roster_user_stats,
    roster_block as _roster_block,
)
from commands.player import (
    build_mystats as _build_mystats,
    build_myhistory as _build_myhistory,
    _sparkline,
)
from commands.trackers import (
    build_notes as _build_notes, build_quests as _build_quests,
    build_pins as _build_pins, build_lootlist as _build_lootlist,
    build_npcs as _build_npcs, build_conditions as _build_conditions,
)
from commands.mechanics import (
    build_vote as _build_vote, build_timer as _build_timer,
    build_hp_tracker as _build_hp_tracker, build_clocks as _build_clocks,
)
from commands.summary import (
    build_summary as _build_summary, build_party as _build_party,
)
from commands.dashboard import (
    build_gm_dashboard as _build_gm_dashboard,
    build_activity as _build_activity,
)
from commands.profile import build_profile as _build_profile
from commands.catchup import build_catchup as _build_catchup
from commands.recap import build_recap as _build_recap
from transcript.logger import (
    append_to_transcript as _append_to_transcript,
    write_scene_marker as _write_scene_marker,
    sanitize_dirname as _sanitize_dirname,
    _LOGS_DIR, _transcript_cache,
)
from transcript.finalize import finalize_previous_month as _finalize_previous_month
from transcript.formatting import (
    format_log_entry as _format_log_entry,
    format_transcript_content as _format_transcript_content,
)
from scheduled.tips_data import _TIPS
from scheduled.potw import _gather_potw_candidates
from scheduled.milestones import _next_anniversary
from scheduled.leaderboard import _format_leaderboard
from scheduled.leaderboard_data import _gather_leaderboard_stats
from scheduled.digest import _build_weekly_digest
from dispatch.help_text import _HELP_TEXT
from players.management import (
    handle_kick as _handle_kick, handle_addplayer as _handle_addplayer,
)

_calc_streak = helpers.calc_streak
_health_icon = helpers.health_icon

# --- Orchestrator ---
def _run_checks(config: dict, bot_state: dict) -> None:
    """Run all scheduled checks, isolating failures."""
    now = datetime.now(timezone.utc)
    maps = build_topic_maps(config)

    checks = [
        ("Topic alerts", check_and_alert),
        ("Player activity", check_player_activity),
        ("Roster summary", post_roster_summary),
        ("Player of the Week", player_of_the_week),
        ("Boon expiry", expire_pending_boons),
        ("Pace report", post_pace_report),
        ("Streak milestones", check_streak_milestones),
        ("Anniversaries", check_anniversaries),
        ("Message milestones", check_message_milestones),
        ("Combat pings", check_combat_turns),
        ("Leaderboard", post_campaign_leaderboard),
        ("Weekly digest", post_weekly_digest),
        ("Recruitment", check_recruitment_needs),
        ("Archive", archive_weekly_data),
        ("Pace drop", check_pace_drop),
        ("Conversation dying", check_conversation_dying),
        ("Timer expiry", check_expired_timers),
        ("Daily tip", post_daily_tip),
    ]
    for label, func in checks:
        try:
            func(config, bot_state, now=now, maps=maps)
        except Exception as e:
            print(f"Error in {label}: {e}")

def main() -> None:
    """Entry point: load config/state, process updates, run checks, save."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    gist_token = os.environ.get("GIST_TOKEN", "")
    gist_id = os.environ.get("GIST_ID", "")

    if not telegram_token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    tg.init(telegram_token)
    state_store.init(gist_token, gist_id)

    config = helpers.load_config()
    helpers.load_settings(config)

    issues = helpers.validate_config(config)
    for issue in issues:
        print(issue)
    if any(i.startswith("ERROR:") for i in issues):
        print("Fatal config errors found, aborting")
        sys.exit(1)

    bot_state = state_store.load()

    print(f"Loaded state. Offset: {bot_state.get('offset', 0)}")
    print(f"Tracking {len(bot_state.get('topics', {}))} topics, "
          f"{len(bot_state.get('players', {}))} players")

    offset = bot_state.get("offset", 0)
    updates = tg.get_updates(offset)
    print(f"Received {len(updates)} new updates")

    if updates:
        bot_state["offset"] = process_updates(updates, config, bot_state)

    _run_checks(config, bot_state)
    cleanup_timestamps(bot_state)

    try:
        update_transcript_index(config)
    except Exception as e:
        print(f"Error updating transcript index: {e}")

    state_store.save(bot_state)
    print("Done")
if __name__ == "__main__":
    main()
