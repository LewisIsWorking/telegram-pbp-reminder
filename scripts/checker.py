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
from scheduled.queue_reminder import post_queue_reminder
from scheduled.queue_nudge import check_queue_nudge
from scheduled.campaign_table import post_campaign_table
from scheduled.session_poll import post_session_poll
from scheduled.poll_result import announce_poll_result
from scheduled.state_backup import backup_state
from scheduled.week_welcome import post_week_welcome
from scheduled.swimming_poll import post_swimming_poll, post_swimming_ping
from scheduled.diagnostic import run_daily_diagnostic
from scheduled.pin_report import run_daily_pin_digest, alert_non_bot_pin_actions
from boons.handler import expire_pending_boons
from scheduled.roster_nudge import post_roster_nudge
from scheduled.gm_escalation import check_gm_escalation
from transcript.finalize import update_transcript_index

# --- Backward-compat aliases for test_checker.py ---
from compat import *  # noqa: F401,F403

# --- Orchestrator ---
# Queue-only subset. The half-hourly `--queue-only` run ingests Telegram
# updates (so GM reply-to clears register promptly) and refreshes the GM
# queue, without firing the other ~28 scheduled features every 30 minutes.
QUEUE_CHECKS = ("Queue reminder", "Queue nudge")


def _run_checks(config: dict, bot_state: dict, only: tuple = ()) -> None:
    """Run all scheduled checks, isolating failures.

    ``only`` restricts execution to the named checks (see QUEUE_CHECKS).
    An empty tuple, the default, runs every check as before.
    """
    now = datetime.now(timezone.utc)
    maps = build_topic_maps(config)

    checks = [
        ("Topic alerts", check_and_alert),
        ("Player activity", check_player_activity),
        ("Roster summary", post_roster_summary),
        ("Player of the Week", player_of_the_week),
        ("Boon expiry", expire_pending_boons),
        ("Roster nudge", post_roster_nudge),
        ("GM escalation", check_gm_escalation),
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
        ("Queue reminder", post_queue_reminder),
        ("Queue nudge", check_queue_nudge),
        ("Campaign table", post_campaign_table),
        ("Session poll", post_session_poll),
        ("Poll result", announce_poll_result),
        ("Week welcome", post_week_welcome),
        ("Swimming poll", post_swimming_poll),
        ("Swimming ping", post_swimming_ping),
        ("Daily diagnostic", run_daily_diagnostic),
        ("Pin digest", run_daily_pin_digest),
        ("Non-bot pin alert", alert_non_bot_pin_actions),
        ("State backup", backup_state),
    ]
    for label, func in checks:
        if only and label not in only:
            continue
        try:
            func(config, bot_state, now=now, maps=maps)
        except Exception as e:
            print(f"Error in {label}: {e}")

def main(queue_only: bool = False) -> None:
    """Entry point: load config/state, process updates, run checks, save.

    ``queue_only`` runs the half-hourly lightweight pass: updates are still
    fetched and processed (this is what clears GM reply-to entries, so it
    cannot be skipped) and state is still saved, but only QUEUE_CHECKS run.
    """
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
        bot_state["offset"] = process_updates(updates, config, bot_state)  # pragma: no cover

    _run_checks(config, bot_state, only=QUEUE_CHECKS if queue_only else ())
    cleanup_timestamps(bot_state)

    try:
        update_transcript_index(config)
    except Exception as e:
        print(f"Error updating transcript index: {e}")

    state_store.save(bot_state)
    print("Done")
if __name__ == "__main__":  # pragma: no cover
    main(queue_only="--queue-only" in sys.argv)
