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
from datetime import datetime, timezone, timedelta
from pathlib import Path

import helpers
import telegram as tg
import state as state_store

from helpers import (
    fmt_date, fmt_relative_date, html_escape,
    posts_str, deduplicate_posts, calc_avg_gap_str, build_topic_maps,
    timestamps_in_window,
)


# Extracted modules
from boons.handler import (
    _format_boon_result, process_boon_callback, expire_pending_boons,
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
    build_status as _build_status,
    build_overview as _build_overview,
)
from commands.campaign import (
    build_campaign_report as _build_campaign_report,
    roster_user_stats as _roster_user_stats,
    roster_block as _roster_block,
)
from commands.player import (
    build_mystats as _build_mystats,
    build_myhistory as _build_myhistory,
)

# Backward-compat aliases for tests (functions moved to modules)
_calc_streak = helpers.calc_streak
_health_icon = helpers.health_icon

from commands.player import _sparkline

from commands.trackers import (
    build_notes as _build_notes,
    build_quests as _build_quests,
    build_pins as _build_pins,
    build_lootlist as _build_lootlist,
    build_npcs as _build_npcs,
    build_conditions as _build_conditions,
)
from commands.mechanics import (
    build_vote as _build_vote,
    build_timer as _build_timer,
    build_hp_tracker as _build_hp_tracker,
    build_clocks as _build_clocks,
)
from commands.summary import (
    build_summary as _build_summary,
    build_party as _build_party,
)
from commands.dashboard import (
    build_gm_dashboard as _build_gm_dashboard,
    build_activity as _build_activity,
)
from commands.profile import build_profile as _build_profile
from commands.catchup import build_catchup as _build_catchup
from commands.recap import build_recap as _build_recap
from commands.trackers import (
    _MAX_NOTES_PER_CAMPAIGN, _MAX_QUESTS_PER_CAMPAIGN,
    _MAX_PINS_PER_CAMPAIGN, _MAX_LOOT_PER_CAMPAIGN, _MAX_NPCS_PER_CAMPAIGN,
)
from commands.mechanics import _MAX_HP_ENTRIES, _MAX_CLOCKS
from transcript.logger import (
    append_to_transcript as _append_to_transcript,
    write_scene_marker as _write_scene_marker,
    sanitize_dirname as _sanitize_dirname,
    _LOGS_DIR,
    _transcript_cache,
)
from transcript.finalize import (
    finalize_previous_month as _finalize_previous_month,
    update_transcript_index,
)
from transcript.formatting import (
    format_log_entry as _format_log_entry,
    format_transcript_content as _format_transcript_content,
)
from scheduled.tips import post_daily_tip
from scheduled.tips_data import _TIPS
from scheduled.alerts import check_and_alert, check_player_activity
from scheduled.reports import post_roster_summary, post_pace_report
from scheduled.potw import player_of_the_week, _gather_potw_candidates
from scheduled.milestones import (
    check_streak_milestones, check_anniversaries, _next_anniversary,
)
from scheduled.message_milestones import check_message_milestones
from scheduled.leaderboard import (
    _format_leaderboard, post_campaign_leaderboard,
)
from scheduled.leaderboard_data import _gather_leaderboard_stats
from scheduled.maintenance import (
    archive_weekly_data, cleanup_timestamps, check_recruitment_needs,
)
from scheduled.smart_alerts import check_pace_drop, check_conversation_dying
from scheduled.digest import post_weekly_digest, _build_weekly_digest
from scheduled.combat_ping import check_combat_turns, check_expired_timers


# ------------------------------------------------------------------ #
#  Process updates
# ------------------------------------------------------------------ #
_HELP_TEXT = (
    "PBP Reminder Bot\n"
    "\n"
    "I track activity across PBP campaigns and post automated summaries.\n"
    "\n"
    "What I do:\n"
    "- Alert when a campaign goes quiet (configurable hours)\n"
    "- Warn inactive players at 1, 2, 3 weeks; auto-remove at 4\n"
    "- Post party rosters every few days\n"
    "- Award Player of the Week (most consistent poster)\n"
    "- Post weekly pace reports comparing this week vs last\n"
    "- Cross-campaign leaderboard\n"
    "- Ping players who haven't acted during combat\n"
    "- Recruitment notices when a party is under capacity\n"
    "- Campaign anniversary celebrations\n"
    "- Daily tips about bot features (posted randomly across campaigns)\n"
    "\n"
    "GM commands:\n"
    "/combat [enemies] - Start combat (e.g. /combat Ogre, 2 Skeletons)\n"
    "/round <N> <players|enemies> - Set specific round and phase\n"
    "/next - Advance to next phase (players→enemies→next round)\n"
    "/endcombat - End combat (shows log summary)\n"
    "/enemies [list] - View or set enemy roster\n"
    "/clog <event> - Add combat log entry\n"
    "/pause [reason] - Pause inactivity tracking (planned breaks)\n"
    "/resume - Resume inactivity tracking\n"
    "/kick @player - Remove a player from tracking\n"
    "/addplayer @user Name - Add a player to roster before they post\n"
    "/scene <name> - Mark a scene boundary in the transcript\n"
    "/note <text> - Add a persistent GM note to this campaign\n"
    "/delnote <N> - Delete a GM note by number\n"
    "/quest <text> - Add an active quest/objective\n"
    "/done <N> - Mark quest N as completed\n"
    "/delquest <N> - Delete quest N\n"
    "/pin <text> - Bookmark a story moment or key info\n"
    "/delpin <N> - Delete a pin\n"
    "/loot <text> - Add item to party loot tracker\n"
    "/delloot <N> - Remove item from loot\n"
    "/npc <name> — <desc> - Add an NPC to the tracker\n"
    "/delnpc <N> - Remove an NPC\n"
    "/condition <target> — <effect> [| duration] - Track a condition\n"
    "/endcondition <N> - Remove a condition\n"
    "/clearconditions - Clear all conditions\n"
    "/hp set <n> <cur>/<max> - Track enemy HP\n"
    "/hp d <n> <amount> - Deal damage\n"
    "/hp h <n> <amount> - Heal\n"
    "/hp remove <n> - Remove an entry\n"
    "/hp clear - Clear all HP entries\n"
    "/clock <n> <segments> - Create a progress clock\n"
    "/tick <n> [N] - Advance a clock\n"
    "/untick <n> [N] - Reverse a clock\n"
    "/delclock <n> - Delete a clock\n"
    "/vote <q> | <opt1> | <opt2> [| ...] - Start a vote\n"
    "/endvote - Close voting and show results\n"
    "/timer <duration> [reason] - Set a response deadline\n"
    "/canceltimer - Cancel the active timer\n"
    "/gm - GM dashboard: all campaigns at a glance\n"
    "\n"
    "Everyone:\n"
    "/help - Show this message\n"
    "/status - Campaign health snapshot\n"
    "/overview - All campaigns at a glance\n"
    "/campaign - Full scoreboard with roster and stats\n"
    "/mystats - Your personal stats (also: /me)\n"
    "/myhistory - 8-week posting sparkline\n"
    "/whosturn - Who has acted in combat and who hasn't\n"
    "/combatlog - View combat log entries\n"
    "/catchup - What happened since you last posted\n"
    "/party - In-fiction party composition\n"
    "/notes - View GM notes for this campaign\n"
    "/quests - View active and completed quests\n"
    "/pins - View bookmarked story moments\n"
    "/lootlist - View party loot\n"
    "/npcs - View tracked NPCs\n"
    "/conditions - View active conditions/buffs\n"
    "/hp - View enemy HP tracker\n"
    "/clocks - View progress clocks\n"
    "/dc <level> [difficulty] - PF2e DC lookup\n"
    "/pick <N> - Vote in an active poll\n"
    "/showvote - Show current vote status\n"
    "/showtimer - Show active timer\n"
    "/summary - Full campaign state at a glance\n"
    "/activity - Posting patterns: busiest hours and days\n"
    "/profile @player - Cross-campaign stats for a player\n"
    "/away [duration] [reason] - Declare an absence (skip warnings)\n"
    "/back - Return from absence\n"
    "/recap [N] - Show last N transcript entries (default 10)\n"
    "/roll <dice> [label] - Roll dice (e.g. 1d20+5 Stealth)\n"
    "/chooseboon <N> - Pick your POTW boon (if buttons don't work)\n"
    "/boons - View your held boons in this campaign\n"
    "/boonsall - View all your boons across all campaigns"
)



















































# ------------------------------------------------------------------ #
#  Daily tips
# ------------------------------------------------------------------ #






# ------------------------------------------------------------------ #







# Patterns that indicate mechanical/dice content (case-insensitive)












def _handle_kick(pid: str, campaign_name: str, target: str,
                 state: dict, group_id: int, thread_id: int) -> None:
    """Remove a player from the campaign roster by username or name."""
    target_lower = target.lower()

    # Search for matching player in this campaign
    match_key = None
    match_player = None
    for key, player in state["players"].items():
        if not key.startswith(f"{pid}:"):
            continue
        username = player.get("username", "").lower()
        first = player.get("first_name", "").lower()
        full = f"{first} {player.get('last_name', '')}".strip().lower()

        if username == target_lower or first == target_lower or full == target_lower:
            match_key = key
            match_player = player
            break

    if not match_player:
        tg.send_message(group_id, thread_id,
                        f"No player matching '{target}' found in {campaign_name}.")
        return

    # Remove player
    removed = state["players"].pop(match_key)
    state["removed_players"][match_key] = {
        "removed_at": datetime.now(timezone.utc).isoformat(),
        "first_name": removed["first_name"],
        "username": removed.get("username", ""),
        "campaign_name": campaign_name,
        "kicked": True,
    }

    name = helpers.player_full_name(removed)
    tg.send_message(group_id, thread_id,
                    f"🚪 {name} has been removed from {campaign_name} tracking.\n"
                    f"They can rejoin by posting in PBP again.")
    print(f"Kicked {name} from {campaign_name}")


def _handle_addplayer(pid: str, campaign_name: str, raw_args: str,
                      now_iso: str, state: dict, group_id: int, thread_id: int) -> None:
    """Manually register a player who hasn't posted yet.

    Format: /addplayer @username FirstName [LastName]
    Creates a placeholder player entry. The username is stored as-is and
    updated with their real user_id when they first post.
    """
    parts = raw_args.split(None, 1)
    username = parts[0].lstrip("@") if parts else ""
    display_name = parts[1] if len(parts) > 1 else username

    if not username:
        tg.send_message(group_id, thread_id,
                        "Usage: /addplayer @username PlayerName")
        return

    # Check if player already exists in this campaign
    for key, player in state["players"].items():
        if not key.startswith(f"{pid}:"):
            continue
        if player.get("username", "").lower() == username.lower():
            tg.send_message(group_id, thread_id,
                            f"{display_name} (@{username}) is already tracked in {campaign_name}.")
            return

    # Use username as placeholder ID (will be replaced when they post)
    placeholder_id = f"pending_{username}"
    player_key = f"{pid}:{placeholder_id}"

    name_parts = display_name.split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    state["players"][player_key] = {
        "user_id": placeholder_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "campaign_name": campaign_name,
        "pbp_topic_id": pid,
        "last_post_time": now_iso,
        "last_warned_week": 0,
    }

    # Also clear from removed_players if they were previously removed
    for rkey in list(state["removed_players"].keys()):
        if rkey.startswith(f"{pid}:"):
            removed = state["removed_players"][rkey]
            if removed.get("username", "").lower() == username.lower():
                del state["removed_players"][rkey]
                break

    tg.send_message(group_id, thread_id,
                    f"✅ {display_name} (@{username}) added to {campaign_name} roster.\n"
                    f"Their tracking will update with full stats when they first post.")
    print(f"Added {display_name} (@{username}) to {campaign_name}")


def process_updates(updates: list, config: dict, state: dict) -> int:
    """Process new Telegram updates, tracking posts and handling commands. Returns new offset."""
    group_id = config["group_id"]

    maps = build_topic_maps(config)

    new_offset = state.get("offset", 0)

    for update in updates:
        update_id = update["update_id"]
        new_offset = max(new_offset, update_id + 1)

        msg = update.get("message")
        cb = update.get("callback_query")

        # ---- Handle boon choice callbacks ----
        if cb:
            process_boon_callback(cb, config, state)
            continue

        if not msg:
            continue

        parsed = _parse_message(msg, group_id, maps)
        if not parsed:
            continue

        pid = parsed["pid"]
        thread_id = parsed["thread_id"]
        user_id = parsed["user_id"]
        user_name = parsed["user_name"]
        campaign_name = parsed["campaign_name"]
        now_iso = parsed["now_iso"]
        msg_time_iso = parsed["msg_time_iso"]
        text = parsed["text"]

        # Per-campaign GM IDs (supports per-campaign overrides)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        # Read-only commands: redirect response from PBP topic to chat topic
        _READ_CMDS = frozenset({
            "/help", "/pbphelp", "/status", "/overview", "/campaign",
            "/mystats", "/me", "/myhistory", "/whosturn", "/combatlog",
            "/catchup", "/party", "/notes", "/quests", "/pins", "/lootlist",
            "/npcs", "/conditions", "/clocks", "/dc", "/showvote", "/showtimer",
            "/summary", "/activity", "/profile", "/recap", "/gm",
            "/boons", "/boonsall",
        })
        cmd_word = text.split()[0] if text.startswith("/") else ""
        # /hp alone = read (view tracker), /hp set|d|h|... = write
        is_read = cmd_word in _READ_CMDS or (cmd_word == "/hp" and text.strip() == "/hp")
        reply_topic = parsed["chat_topic_id"] if is_read else thread_id

        # ---- /help command ----
        if text in ("/help", "/pbphelp"):
            tg.send_message(group_id, reply_topic, _HELP_TEXT)

        # ---- /status command ----
        if text == "/status":
            status = _build_status(pid, campaign_name, state, gm_ids)
            tg.send_message(group_id, reply_topic, status)

        # ---- /overview command ----
        if text == "/overview":
            overview = _build_overview(config, state)
            tg.send_message(group_id, reply_topic, overview)

        # ---- /campaign command ----
        if text == "/campaign":
            report = _build_campaign_report(pid, config, state, gm_ids)
            tg.send_message(group_id, reply_topic, report)

        # ---- /mystats command ----
        if text in ("/mystats", "/me"):
            my_report = _build_mystats(pid, user_id, campaign_name, state, gm_ids, config)
            tg.send_message(group_id, reply_topic, my_report)

        # ---- /whosturn command ----
        if text == "/whosturn":
            turn_report = _build_whosturn(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, turn_report)

        # ---- /combatlog command (everyone) ----
        if text == "/combatlog":
            log_report = _build_combatlog(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, log_report)

        # ---- /party command ----
        if text == "/party":
            party_report = _build_party(pid, campaign_name, config, state)
            tg.send_message(group_id, reply_topic, party_report)

        # ---- /myhistory command ----
        if text == "/myhistory":
            history = _build_myhistory(pid, user_id, campaign_name, state, gm_ids)
            tg.send_message(group_id, reply_topic, history)

        # ---- /catchup command ----
        if text == "/catchup":
            catchup = _build_catchup(pid, user_id, campaign_name, state, gm_ids, config)
            tg.send_message(group_id, reply_topic, catchup)

        # ---- /pause command (GM only) ----
        if text.startswith("/pause") and user_id in gm_ids:
            reason = parsed["raw_text"][6:].strip() or "No reason given"
            state.setdefault("paused_campaigns", {})[pid] = {
                "paused_at": now_iso,
                "reason": reason,
            }
            tg.send_message(group_id, thread_id,
                            f"⏸️ {campaign_name} paused. Inactivity tracking disabled.\nReason: {reason}")
            print(f"Paused {campaign_name}: {reason}")

        # ---- /resume command (GM only) ----
        if text == "/resume" and user_id in gm_ids:
            paused = state.get("paused_campaigns", {})
            if pid in paused:
                del paused[pid]
                tg.send_message(group_id, thread_id,
                                f"▶️ {campaign_name} resumed. Inactivity tracking re-enabled.")
                print(f"Resumed {campaign_name}")
            else:
                tg.send_message(group_id, thread_id, f"{campaign_name} is not paused.")

        # ---- /kick command (GM only) ----
        if text.startswith("/kick") and user_id in gm_ids:
            target = parsed["raw_text"][5:].strip().lstrip("@")
            if not target:
                tg.send_message(group_id, thread_id,
                                "Usage: /kick @username or /kick PlayerName")
            else:
                _handle_kick(pid, campaign_name, target, state, group_id, thread_id)

        # ---- /addplayer command (GM only) ----
        if text.startswith("/addplayer") and user_id in gm_ids:
            raw_args = parsed["raw_text"][10:].strip()
            if not raw_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /addplayer @username PlayerName\n"
                                "e.g. /addplayer @alice Alice Smith")
            else:
                _handle_addplayer(pid, campaign_name, raw_args, now_iso, state, group_id, thread_id)

        # ---- /scene command (GM only) ----
        if text.startswith("/scene") and user_id in gm_ids:
            scene_name = parsed["raw_text"][6:].strip()
            if not scene_name:
                tg.send_message(group_id, thread_id,
                                "Usage: /scene <name>\ne.g. /scene The Docks at Midnight")
            else:
                state.setdefault("current_scenes", {})[pid] = scene_name
                _write_scene_marker(campaign_name, scene_name)
                tg.send_message(group_id, thread_id,
                                f"🎭 Scene: {scene_name}\nMarked in transcript.")
                print(f"Scene marker in {campaign_name}: {scene_name}")

        # ---- /note command (GM only) ----
        if text.startswith("/note") and not text.startswith("/notes") and user_id in gm_ids:
            note_text = parsed["raw_text"][5:].strip()
            if not note_text:
                tg.send_message(group_id, thread_id,
                                "Usage: /note <text>\ne.g. /note Party agreed to meet the informant at dawn")
            else:
                notes = state.setdefault("campaign_notes", {}).setdefault(pid, [])
                if len(notes) >= _MAX_NOTES_PER_CAMPAIGN:
                    tg.send_message(group_id, thread_id,
                                    f"Maximum {_MAX_NOTES_PER_CAMPAIGN} notes reached. Use /delnote <N> to remove old ones.")
                else:
                    notes.append({"text": note_text, "created_at": now_iso})
                    tg.send_message(group_id, thread_id,
                                    f"📝 Note #{len(notes)} saved.")
                    print(f"Note added to {campaign_name}: {note_text[:50]}")

        # ---- /notes command (everyone) ----
        if text == "/notes":
            notes_report = _build_notes(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, notes_report)

        # ---- /activity command (everyone) ----
        if text == "/activity":
            activity_report = _build_activity(pid, campaign_name, state, gm_ids)
            tg.send_message(group_id, reply_topic, activity_report)

        # ---- /profile command (everyone) ----
        if text.startswith("/profile"):
            target = parsed["raw_text"][8:].strip()
            if not target:
                tg.send_message(group_id, reply_topic,
                                "Usage: /profile @username or /profile PlayerName")
            else:
                profile = _build_profile(target, config, state)
                tg.send_message(group_id, reply_topic, profile)

        # ---- /delnote command (GM only) ----
        if text.startswith("/delnote") and user_id in gm_ids:
            num_str = parsed["raw_text"][8:].strip()
            notes = state.get("campaign_notes", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(notes):
                    removed = notes.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"🗑️ Deleted note #{idx + 1}: {removed['text'][:60]}")
                    print(f"Note deleted from {campaign_name}: {removed['text'][:50]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Note #{num_str} not found. Use /notes to see current notes.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /delnote <number>\ne.g. /delnote 3")

        # ---- /quest command (GM only) ----
        if text.startswith("/quest") and not text.startswith("/quests") and user_id in gm_ids:
            quest_text = parsed["raw_text"][6:].strip()
            if not quest_text:
                tg.send_message(group_id, thread_id,
                                "Usage: /quest <text>\ne.g. /quest Find the missing merchant")
            else:
                quests = state.setdefault("quests", {}).setdefault(pid, [])
                if len(quests) >= _MAX_QUESTS_PER_CAMPAIGN:
                    tg.send_message(group_id, thread_id,
                                    f"Maximum {_MAX_QUESTS_PER_CAMPAIGN} quests reached. Use /delquest <N> to remove old ones.")
                else:
                    quests.append({"text": quest_text, "status": "active", "created_at": now_iso, "completed_at": None})
                    tg.send_message(group_id, thread_id,
                                    f"📋 Quest #{len(quests)} added: {quest_text}")
                    print(f"Quest added to {campaign_name}: {quest_text[:50]}")

        # ---- /quests command (everyone) ----
        if text == "/quests":
            quests_report = _build_quests(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, quests_report)

        # ---- /done command (GM only) ----
        if text.startswith("/done") and user_id in gm_ids:
            num_str = parsed["raw_text"][5:].strip()
            quests = state.get("quests", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(quests):
                    quests[idx]["status"] = "completed"
                    quests[idx]["completed_at"] = now_iso
                    tg.send_message(group_id, thread_id,
                                    f"✅ Quest #{idx + 1} completed: {quests[idx]['text']}")
                    print(f"Quest completed in {campaign_name}: {quests[idx]['text'][:50]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Quest #{num_str} not found. Use /quests to see current quests.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /done <number>\ne.g. /done 2")

        # ---- /delquest command (GM only) ----
        if text.startswith("/delquest") and user_id in gm_ids:
            num_str = parsed["raw_text"][9:].strip()
            quests = state.get("quests", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(quests):
                    removed = quests.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"🗑️ Deleted quest #{idx + 1}: {removed['text'][:60]}")
                    print(f"Quest deleted from {campaign_name}: {removed['text'][:50]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Quest #{num_str} not found. Use /quests to see current quests.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /delquest <number>\ne.g. /delquest 3")

        # ---- /gm command (GM only) ----
        if text == "/gm" and user_id in gm_ids:
            dashboard = _build_gm_dashboard(config, state)
            tg.send_message(group_id, reply_topic, dashboard)

        # ---- /pin command (GM only) ----
        if text.startswith("/pin") and not text.startswith("/pins") and user_id in gm_ids:
            pin_text = parsed["raw_text"][4:].strip()
            if not pin_text:
                tg.send_message(group_id, thread_id,
                                "Usage: /pin <text>\ne.g. /pin The party discovered the hidden temple entrance")
            else:
                pins = state.setdefault("pins", {}).setdefault(pid, [])
                if len(pins) >= _MAX_PINS_PER_CAMPAIGN:
                    tg.send_message(group_id, thread_id,
                                    f"Maximum {_MAX_PINS_PER_CAMPAIGN} pins reached. Use /delpin <N> to remove old ones.")
                else:
                    pins.append({"text": pin_text, "created_at": now_iso, "author": user_name})
                    tg.send_message(group_id, thread_id,
                                    f"📌 Pin #{len(pins)} saved: {pin_text}")
                    print(f"Pin added to {campaign_name}: {pin_text[:50]}")

        # ---- /pins command (everyone) ----
        if text == "/pins":
            pins_report = _build_pins(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, pins_report)

        # ---- /delpin command (GM only) ----
        if text.startswith("/delpin") and user_id in gm_ids:
            num_str = parsed["raw_text"][7:].strip()
            pins = state.get("pins", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(pins):
                    removed = pins.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"🗑️ Deleted pin #{idx + 1}: {removed['text'][:60]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Pin #{num_str} not found. Use /pins to see current pins.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /delpin <number>\ne.g. /delpin 3")

        # ---- /loot command (GM only) ----
        if text.startswith("/loot") and not text.startswith("/lootlist") and user_id in gm_ids:
            loot_text = parsed["raw_text"][5:].strip()
            if not loot_text:
                tg.send_message(group_id, thread_id,
                                "Usage: /loot <item>\ne.g. /loot +1 striking longsword")
            else:
                loot = state.setdefault("loot", {}).setdefault(pid, [])
                if len(loot) >= _MAX_LOOT_PER_CAMPAIGN:
                    tg.send_message(group_id, thread_id,
                                    f"Maximum {_MAX_LOOT_PER_CAMPAIGN} items. Use /delloot <N> to remove.")
                else:
                    loot.append({"text": loot_text, "added_at": now_iso})
                    tg.send_message(group_id, thread_id,
                                    f"💰 Loot #{len(loot)}: {loot_text}")
                    print(f"Loot added to {campaign_name}: {loot_text[:50]}")

        # ---- /lootlist command (everyone) ----
        if text == "/lootlist":
            loot_report = _build_lootlist(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, loot_report)

        # ---- /delloot command (GM only) ----
        if text.startswith("/delloot") and user_id in gm_ids:
            num_str = parsed["raw_text"][8:].strip()
            loot = state.get("loot", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(loot):
                    removed = loot.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"🗑️ Removed loot #{idx + 1}: {removed['text'][:60]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Loot #{num_str} not found. Use /lootlist to see items.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /delloot <number>\ne.g. /delloot 3")

        # ---- /npc command (GM only) ----
        if text.startswith("/npc") and not text.startswith("/npcs") and user_id in gm_ids:
            raw_args = parsed["raw_text"][4:].strip()
            if not raw_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /npc <name> — <description>\n"
                                "e.g. /npc Gorund — Dwarven blacksmith, owes party a favour")
            else:
                npcs = state.setdefault("npcs", {}).setdefault(pid, [])
                if len(npcs) >= _MAX_NPCS_PER_CAMPAIGN:
                    tg.send_message(group_id, thread_id,
                                    f"Maximum {_MAX_NPCS_PER_CAMPAIGN} NPCs. Use /delnpc <N> to remove.")
                else:
                    # Split on em-dash or double-hyphen
                    if " — " in raw_args:
                        name, desc = raw_args.split(" — ", 1)
                    elif " -- " in raw_args:
                        name, desc = raw_args.split(" -- ", 1)
                    elif " - " in raw_args:
                        name, desc = raw_args.split(" - ", 1)
                    else:
                        name, desc = raw_args, ""
                    npcs.append({"name": name.strip(), "desc": desc.strip(), "added_at": now_iso})
                    tg.send_message(group_id, thread_id,
                                    f"🎭 NPC #{len(npcs)}: {name.strip()}")
                    print(f"NPC added to {campaign_name}: {name.strip()[:50]}")

        # ---- /npcs command (everyone) ----
        if text == "/npcs":
            npcs_report = _build_npcs(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, npcs_report)

        # ---- /delnpc command (GM only) ----
        if text.startswith("/delnpc") and user_id in gm_ids:
            num_str = parsed["raw_text"][7:].strip()
            npcs = state.get("npcs", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(npcs):
                    removed = npcs.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"🗑️ Removed NPC #{idx + 1}: {removed['name']}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"NPC #{num_str} not found. Use /npcs to see the list.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /delnpc <number>\ne.g. /delnpc 3")

        # ---- /condition command (GM only) ----
        if text.startswith("/condition") and not text.startswith("/conditions") and user_id in gm_ids:
            raw_args = parsed["raw_text"][10:].strip()
            if not raw_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /condition <target> — <effect> [| duration]\n"
                                "e.g. /condition Cardigan — Frightened 2 | until end of next turn\n"
                                "e.g. /condition All — Inspired +1")
            else:
                # Parse: target — effect [| duration]
                if " — " in raw_args:
                    target, rest = raw_args.split(" — ", 1)
                elif " -- " in raw_args:
                    target, rest = raw_args.split(" -- ", 1)
                elif " - " in raw_args:
                    target, rest = raw_args.split(" - ", 1)
                else:
                    target, rest = raw_args, ""

                if "|" in rest:
                    effect, duration = rest.split("|", 1)
                else:
                    effect, duration = rest, ""

                conds = state.setdefault("conditions", {}).setdefault(pid, [])
                conds.append({
                    "target": target.strip(),
                    "effect": effect.strip(),
                    "duration": duration.strip(),
                    "added_at": now_iso,
                })
                tg.send_message(group_id, thread_id,
                                f"⚡ Condition on {target.strip()}: {effect.strip()}")
                print(f"Condition in {campaign_name}: {target.strip()} — {effect.strip()[:50]}")

        # ---- /conditions command (everyone) ----
        if text == "/conditions":
            conds_report = _build_conditions(pid, campaign_name, state, config)
            tg.send_message(group_id, reply_topic, conds_report)

        # ---- /endcondition command (GM only) ----
        if text.startswith("/endcondition") and user_id in gm_ids:
            num_str = parsed["raw_text"][13:].strip()
            conds = state.get("conditions", {}).get(pid, [])
            try:
                idx = int(num_str) - 1
                if 0 <= idx < len(conds):
                    removed = conds.pop(idx)
                    tg.send_message(group_id, thread_id,
                                    f"✅ Ended: {removed['target']} — {removed['effect']}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Condition #{num_str} not found. Use /conditions to see list.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                "Usage: /endcondition <number>\ne.g. /endcondition 2")

        # ---- /clearconditions command (GM only) ----
        if text == "/clearconditions" and user_id in gm_ids:
            old = state.get("conditions", {}).get(pid, [])
            count = len(old)
            state.setdefault("conditions", {})[pid] = []
            tg.send_message(group_id, thread_id,
                            f"✅ Cleared {count} condition{'s' if count != 1 else ''} from {campaign_name}.")

        # ---- /hp command (GM set/damage/heal/remove/clear, everyone view) ----
        if text.startswith("/hp"):
            hp_args = parsed["raw_text"][3:].strip()
            hp_tracker = state.setdefault("hp_tracker", {}).setdefault(pid, {})

            if not hp_args or hp_args == "show":
                # View HP tracker
                report = _build_hp_tracker(pid, campaign_name, state)
                tg.send_message(group_id, reply_topic, report)

            elif user_id in gm_ids:
                parts = hp_args.split(None, 1)
                sub = parts[0].lower()
                rest = parts[1] if len(parts) > 1 else ""

                if sub == "set":
                    # /hp set <name> <current>/<max>
                    set_parts = rest.rsplit(None, 1)
                    if len(set_parts) == 2 and "/" in set_parts[1]:
                        name = set_parts[0].strip()
                        try:
                            cur, mx = set_parts[1].split("/", 1)
                            cur, mx = int(cur), int(mx)
                            if mx <= 0 or mx > 9999:
                                tg.send_message(group_id, thread_id, "Max HP must be 1–9999.")
                            elif len(hp_tracker) >= _MAX_HP_ENTRIES and name not in hp_tracker:
                                tg.send_message(group_id, thread_id,
                                                f"Max {_MAX_HP_ENTRIES} entries. Use /hp remove <name> first.")
                            else:
                                hp_tracker[name] = {"current": min(cur, mx), "max": mx}
                                icon = helpers.hp_status_icon(min(cur, mx), mx)
                                bar = helpers.hp_bar(min(cur, mx), mx)
                                tg.send_message(group_id, thread_id,
                                                f"{icon} {name}: {bar}")
                        except ValueError:
                            tg.send_message(group_id, thread_id,
                                            "Usage: /hp set <name> <current>/<max>\ne.g. /hp set Ogre 45/45")
                    else:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp set <name> <current>/<max>\ne.g. /hp set Ogre 45/45")

                elif sub in ("d", "damage"):
                    # /hp d <name> <amount>
                    dmg_parts = rest.rsplit(None, 1)
                    if len(dmg_parts) == 2:
                        name = dmg_parts[0].strip()
                        try:
                            amount = int(dmg_parts[1])
                            if name in hp_tracker:
                                hp = hp_tracker[name]
                                hp["current"] = max(0, hp["current"] - amount)
                                icon = helpers.hp_status_icon(hp["current"], hp["max"])
                                bar = helpers.hp_bar(hp["current"], hp["max"])
                                status = " 💀 DOWN!" if hp["current"] == 0 else ""
                                tg.send_message(group_id, thread_id,
                                                f"{icon} {name} takes {amount} damage!\n{bar}{status}")
                            else:
                                tg.send_message(group_id, thread_id,
                                                f"No HP entry for '{name}'. Use /hp set {name} <hp>/<max> first.")
                        except ValueError:
                            tg.send_message(group_id, thread_id,
                                            "Usage: /hp d <name> <amount>\ne.g. /hp d Ogre 12")
                    else:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp d <name> <amount>\ne.g. /hp d Ogre 12")

                elif sub in ("h", "heal"):
                    # /hp h <name> <amount>
                    heal_parts = rest.rsplit(None, 1)
                    if len(heal_parts) == 2:
                        name = heal_parts[0].strip()
                        try:
                            amount = int(heal_parts[1])
                            if name in hp_tracker:
                                hp = hp_tracker[name]
                                hp["current"] = min(hp["max"], hp["current"] + amount)
                                icon = helpers.hp_status_icon(hp["current"], hp["max"])
                                bar = helpers.hp_bar(hp["current"], hp["max"])
                                tg.send_message(group_id, thread_id,
                                                f"{icon} {name} healed {amount}!\n{bar}")
                            else:
                                tg.send_message(group_id, thread_id,
                                                f"No HP entry for '{name}'. Use /hp set {name} <hp>/<max> first.")
                        except ValueError:
                            tg.send_message(group_id, thread_id,
                                            "Usage: /hp h <name> <amount>\ne.g. /hp h Ogre 10")
                    else:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp h <name> <amount>\ne.g. /hp h Ogre 10")

                elif sub == "remove":
                    name = rest.strip()
                    if name in hp_tracker:
                        del hp_tracker[name]
                        tg.send_message(group_id, thread_id, f"🗑️ Removed {name} from HP tracker.")
                    else:
                        tg.send_message(group_id, thread_id,
                                        f"No HP entry for '{name}'. Use /hp to see entries.")

                elif sub == "clear":
                    count = len(hp_tracker)
                    state["hp_tracker"][pid] = {}
                    tg.send_message(group_id, thread_id,
                                    f"✅ Cleared {count} HP entr{'ies' if count != 1 else 'y'}.")

                else:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /hp set <n> <cur>/<max> | /hp d <n> <amt> | "
                                    "/hp h <n> <amt> | /hp remove <n> | /hp clear")

        # ---- /clock command (GM only) ----
        if text.startswith("/clock") and not text.startswith("/clocks") and user_id in gm_ids:
            clock_args = parsed["raw_text"][6:].strip()
            if not clock_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6\ne.g. /clock Ritual 4")
            else:
                clock_parts = clock_args.rsplit(None, 1)
                if len(clock_parts) == 2:
                    name = clock_parts[0].strip()
                    try:
                        segments = int(clock_parts[1])
                        if segments < 2 or segments > 12:
                            tg.send_message(group_id, thread_id, "Segments must be 2–12.")
                        else:
                            clocks = state.setdefault("clocks", {}).setdefault(pid, {})
                            if len(clocks) >= _MAX_CLOCKS and name not in clocks:
                                tg.send_message(group_id, thread_id,
                                                f"Max {_MAX_CLOCKS} clocks. Use /delclock <name> first.")
                            else:
                                clocks[name] = {"filled": 0, "segments": segments}
                                display = helpers.clock_display(0, segments)
                                tg.send_message(group_id, thread_id,
                                                f"⏱️ Clock: {name}\n{display}")
                    except ValueError:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6")
                else:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6")

        # ---- /clocks command (everyone) ----
        if text == "/clocks":
            clocks_report = _build_clocks(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, clocks_report)

        # ---- /tick command (GM only) ----
        if text.startswith("/tick") and not text.startswith("/ticker") and user_id in gm_ids:
            tick_args = parsed["raw_text"][5:].strip()
            clocks = state.get("clocks", {}).get(pid, {})
            if not tick_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /tick <name> [N]\ne.g. /tick Investigation 2")
            else:
                tick_parts = tick_args.rsplit(None, 1)
                amount = 1
                name = tick_args
                if len(tick_parts) == 2:
                    try:
                        amount = int(tick_parts[1])
                        name = tick_parts[0]
                    except ValueError:
                        name = tick_args
                        amount = 1
                name = name.strip()
                if name in clocks:
                    clock = clocks[name]
                    clock["filled"] = min(clock["segments"], clock["filled"] + amount)
                    display = helpers.clock_display(clock["filled"], clock["segments"])
                    complete = " ✅ COMPLETE!" if clock["filled"] >= clock["segments"] else ""
                    tg.send_message(group_id, thread_id,
                                    f"⏱️ {name}\n{display}{complete}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"No clock named '{name}'. Use /clocks to see all.")

        # ---- /untick command (GM only) ----
        if text.startswith("/untick") and user_id in gm_ids:
            tick_args = parsed["raw_text"][7:].strip()
            clocks = state.get("clocks", {}).get(pid, {})
            if not tick_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /untick <name> [N]\ne.g. /untick Investigation 1")
            else:
                tick_parts = tick_args.rsplit(None, 1)
                amount = 1
                name = tick_args
                if len(tick_parts) == 2:
                    try:
                        amount = int(tick_parts[1])
                        name = tick_parts[0]
                    except ValueError:
                        name = tick_args
                        amount = 1
                name = name.strip()
                if name in clocks:
                    clock = clocks[name]
                    clock["filled"] = max(0, clock["filled"] - amount)
                    display = helpers.clock_display(clock["filled"], clock["segments"])
                    tg.send_message(group_id, thread_id, f"⏱️ {name}\n{display}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"No clock named '{name}'. Use /clocks to see all.")

        # ---- /delclock command (GM only) ----
        if text.startswith("/delclock") and user_id in gm_ids:
            name = parsed["raw_text"][9:].strip()
            clocks = state.get("clocks", {}).get(pid, {})
            if name in clocks:
                del clocks[name]
                tg.send_message(group_id, thread_id, f"🗑️ Removed clock: {name}")
            else:
                tg.send_message(group_id, thread_id,
                                f"No clock named '{name}'. Use /clocks to see all.")

        # ---- /vote command (GM only) ----
        if text.startswith("/vote") and not text.startswith("/votes") and user_id in gm_ids:
            raw_args = parsed["raw_text"][5:].strip()
            if not raw_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /vote <question> | <option1> | <option2> [| ...]\n"
                                "e.g. /vote Where do we go? | North gate | Sewers | Stay and rest")
            else:
                parts = [p.strip() for p in raw_args.split("|")]
                if len(parts) < 3:
                    tg.send_message(group_id, thread_id,
                                    "Need a question and at least 2 options, separated by |\n"
                                    "e.g. /vote Left or right? | Left | Right")
                else:
                    question = parts[0]
                    options = parts[1:]
                    if len(options) > 6:
                        tg.send_message(group_id, thread_id, "Maximum 6 options per vote.")
                    else:
                        state.setdefault("votes", {})[pid] = {
                            "question": question,
                            "options": options,
                            "results": {str(i): [] for i in range(1, len(options) + 1)},
                            "closed": False,
                            "created_at": now_iso,
                        }
                        # Build display
                        option_lines = "\n".join(f"  {i}. {opt}" for i, opt in enumerate(options, 1))
                        tg.send_message(group_id, thread_id,
                                        f"🗳️ Vote started!\n\n❓ {question}\n\n{option_lines}\n\n"
                                        f"Use /pick <N> to cast your vote.")
                        print(f"Vote started in {campaign_name}: {question}")

        # ---- /pick command (everyone) ----
        if text.startswith("/pick"):
            pick_str = parsed["raw_text"][5:].strip()
            vote = state.get("votes", {}).get(pid)
            if not vote or vote.get("closed"):
                tg.send_message(group_id, thread_id, "No active vote. GMs can start one with /vote")
            else:
                try:
                    choice = int(pick_str)
                    if 1 <= choice <= len(vote["options"]):
                        # Remove previous vote by this user
                        for key in vote["results"]:
                            vote["results"][key] = [n for n in vote["results"][key] if n != user_name]
                        # Add new vote
                        vote["results"][str(choice)].append(user_name)
                        tg.send_message(group_id, thread_id,
                                        f"✅ {user_name} voted for: {vote['options'][choice - 1]}")
                    else:
                        tg.send_message(group_id, thread_id,
                                        f"Pick a number 1–{len(vote['options'])}.")
                except (ValueError, TypeError):
                    tg.send_message(group_id, thread_id,
                                    f"Usage: /pick <number>\ne.g. /pick 2")

        # ---- /showvote command (everyone) ----
        if text == "/showvote":
            vote_report = _build_vote(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, vote_report)

        # ---- /endvote command (GM only) ----
        if text == "/endvote" and user_id in gm_ids:
            vote = state.get("votes", {}).get(pid)
            if not vote or vote.get("closed"):
                tg.send_message(group_id, thread_id, "No active vote to close.")
            else:
                vote["closed"] = True
                # Find winner
                results = vote["results"]
                best_count = max(len(v) for v in results.values())
                total = sum(len(v) for v in results.values())
                winners = [vote["options"][int(k) - 1] for k, v in results.items() if len(v) == best_count]

                lines = [f"🗳️ Vote closed — {vote['question']}", ""]
                for i, option in enumerate(vote["options"], 1):
                    voters = results.get(str(i), [])
                    count = len(voters)
                    marker = " 👑" if count == best_count and count > 0 else ""
                    voter_names = ", ".join(voters) if voters else "—"
                    lines.append(f"  {i}. {option}: {count} ({voter_names}){marker}")
                lines.append("")
                if len(winners) == 1:
                    lines.append(f"Winner: {winners[0]} ({best_count}/{total} votes)")
                elif best_count > 0:
                    lines.append(f"Tied: {', '.join(winners)} ({best_count} each)")
                else:
                    lines.append("No votes were cast.")
                tg.send_message(group_id, thread_id, "\n".join(lines))

        # ---- /timer command (GM only) ----
        if text.startswith("/timer") and not text.startswith("/timers") and user_id in gm_ids:
            raw_args = parsed["raw_text"][6:].strip()
            if not raw_args:
                tg.send_message(group_id, thread_id,
                                "Usage: /timer <duration> [reason]\n"
                                "e.g. /timer 24h Post your combat actions\n"
                                "e.g. /timer 2d\n"
                                "Durations: Nh (hours), Nm (minutes), Nd (days)")
            else:
                now_dt = datetime.fromisoformat(now_iso)
                deadline, reason = helpers.parse_timer_duration(raw_args, now_dt)
                if deadline is None:
                    tg.send_message(group_id, thread_id,
                                    "Couldn't parse duration. Use Nh, Nm, or Nd.\n"
                                    "e.g. /timer 24h Post your actions")
                else:
                    state.setdefault("timers", {})[pid] = {
                        "deadline": deadline.isoformat(),
                        "reason": reason,
                        "set_at": now_iso,
                        "set_by": user_name,
                    }
                    time_fmt = deadline.strftime("%b %d %H:%M UTC")
                    reason_str = f"\n📝 {reason}" if reason else ""
                    tg.send_message(group_id, thread_id,
                                    f"⏳ Timer set! Deadline: {time_fmt}{reason_str}\n"
                                    f"Use /showtimer to check remaining time.")
                    print(f"Timer set in {campaign_name}: deadline {time_fmt}")

        # ---- /showtimer command (everyone) ----
        if text == "/showtimer":
            timer_report = _build_timer(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, timer_report)

        # ---- /canceltimer command (GM only) ----
        if text == "/canceltimer" and user_id in gm_ids:
            if state.get("timers", {}).get(pid):
                del state["timers"][pid]
                tg.send_message(group_id, thread_id, f"⏳ Timer cancelled for {campaign_name}.")
            else:
                tg.send_message(group_id, thread_id, "No active timer to cancel.")

        # ---- /summary command (everyone) ----
        if text == "/summary":
            summary = _build_summary(pid, campaign_name, state, config)
            tg.send_message(group_id, reply_topic, summary)

        # ---- /dc command (everyone) ----
        if text.startswith("/dc"):
            dc_query = parsed["raw_text"][3:].strip()
            result = helpers.dc_lookup(dc_query)
            tg.send_message(group_id, reply_topic, result)

        # ---- /away command (everyone) ----
        if text.startswith("/away"):
            args = parsed["raw_text"][5:].strip()
            now_dt = datetime.fromisoformat(now_iso)
            until_dt, reason = helpers.parse_away_duration(args, now_dt)
            away_key = f"{pid}:{user_id}"
            state.setdefault("away", {})[away_key] = {
                "until": until_dt.isoformat() if until_dt else None,
                "reason": reason,
                "set_at": now_iso,
            }
            if until_dt:
                until_str = f"{until_dt.strftime('%b %d')} (W{until_dt.isocalendar()[1]})"
                msg = f"✈️ {user_name} marked as away until {until_str}.\nReason: {reason}"
            else:
                msg = f"✈️ {user_name} marked as away (indefinite).\nReason: {reason}"
            msg += "\nUse /back when you return."
            print(f"Away: {user_name} in {campaign_name} — {reason}")
            tg.send_message(group_id, thread_id, msg)

        # ---- /back command (everyone) ----
        if text == "/back":
            away_key = f"{pid}:{user_id}"
            if away_key in state.get("away", {}):
                del state["away"][away_key]
                char_name = helpers.character_name(config, pid, user_id)
                char_tag = f" ({char_name})" if char_name else ""
                tg.send_message(group_id, thread_id,
                                f"👋 {user_name}{char_tag} is back!")
                print(f"Back: {user_name} in {campaign_name}")
            else:
                tg.send_message(group_id, thread_id,
                                f"You're not currently marked as away.")

        # ---- /recap command (everyone) ----
        if text.startswith("/recap"):
            args = parsed["raw_text"][6:].strip()
            try:
                count = int(args) if args else 10
            except ValueError:
                count = 10
            recap = _build_recap(pid, campaign_name, config, count)
            tg.send_message(group_id, reply_topic, recap)

        # ---- /chooseboon command (POTW winner fallback for broken buttons) ----
        if text.startswith("/chooseboon"):
            num_str = parsed["raw_text"][11:].strip()
            try:
                choice = int(num_str)
            except ValueError:
                tg.send_message(group_id, thread_id, "Usage: /chooseboon <number>")
            else:
                result = choose_boon_by_text(pid, user_id, choice, config, state)
                tg.send_message(group_id, thread_id, result)

        # ---- /boons command (everyone, read-only) ----
        if text == "/boons":
            report = build_boons(pid, user_id, campaign_name, state)
            tg.send_message(group_id, reply_topic, report)

        # ---- /boonsall command (everyone, read-only) ----
        if text == "/boonsall":
            report = build_boons_all(user_id, state)
            tg.send_message(group_id, reply_topic, report)

        # ---- /roll command (everyone) ----
        if text.startswith("/roll"):
            dice_expr = parsed["raw_text"][5:].strip()
            if not dice_expr:
                tg.send_message(group_id, thread_id,
                                "Usage: /roll <dice> [label]\n"
                                "e.g. /roll 1d20+5 Stealth\n"
                                "e.g. /roll 2d6+3\n"
                                "e.g. /roll 4d6kh3 (keep highest 3)")
            else:
                result = helpers.roll_dice(dice_expr)
                if result.get("error"):
                    tg.send_message(group_id, thread_id, result["error"])
                else:
                    char_name = helpers.character_name(config, pid, user_id)
                    roller = char_name or user_name
                    label = result["label"]

                    lines = []
                    grand_total = 0
                    for r in result["results"]:
                        grand_total += r["total"]
                        lines.append(f"  {r['expr']}: {r['detail']} = {r['total']}")

                    header = f"🎲 {roller}"
                    if label:
                        header += f" — {label}"
                    header += ":"

                    if len(result["results"]) == 1:
                        r = result["results"][0]
                        msg = f"{header}\n  {r['detail']} = {r['total']}"
                    else:
                        msg = header + "\n" + "\n".join(lines) + f"\n  Total: {grand_total}"

                    tg.send_message(group_id, thread_id, msg)

        # ---- Combat commands and tracking ----
        _handle_combat_message(
            text, parsed["raw_text"], user_id, user_name, gm_ids, pid, campaign_name,
            now_iso, group_id, thread_id, state,
        )

        # Update topic-level tracking (for 4-hour alerts)
        state["topics"][pid] = {
            "last_message_time": msg_time_iso,
            "last_user": user_name,
            "last_user_id": user_id,
            "campaign_name": campaign_name,
        }

        # Increment message count for this user in this topic
        user_counts = state["message_counts"].setdefault(pid, {})
        user_counts[user_id] = user_counts.get(user_id, 0) + 1

        # Track word count (measures RP engagement depth, not just frequency)
        raw_text = parsed["raw_text"] or ""
        word_count = len(raw_text.split()) if raw_text.strip() else 0
        user_words = state.setdefault("word_counts", {}).setdefault(pid, {})
        user_words[user_id] = user_words.get(user_id, 0) + word_count

        # Track post timestamps for Player of the Week gap calculation
        state["post_timestamps"].setdefault(pid, {}).setdefault(user_id, []).append(msg_time_iso)

        # Track activity patterns (persistent hour/day counters)
        msg_dt = datetime.fromisoformat(msg_time_iso)
        hour_key = str(msg_dt.hour)
        day_key = str(msg_dt.weekday())  # 0=Mon, 6=Sun
        user_hours = state.setdefault("activity_hours", {}).setdefault(pid, {}).setdefault(user_id, {})
        user_hours[hour_key] = user_hours.get(hour_key, 0) + 1
        user_days = state.setdefault("activity_days", {}).setdefault(pid, {}).setdefault(user_id, {})
        user_days[day_key] = user_days.get(day_key, 0) + 1

        # Update player-level tracking (skip GM)
        if user_id and user_id not in gm_ids:
            # Auto-clear away status when player posts (non-command only)
            if not text.startswith("/"):
                away_key = f"{pid}:{user_id}"
                if away_key in state.get("away", {}):
                    del state["away"][away_key]
                    print(f"Auto-cleared away for {user_name} in {campaign_name} (posted)")

            player_key = f"{pid}:{user_id}"
            was_removed = player_key in state["removed_players"]
            old_player = state.get("players", {}).get(player_key, {})
            old_warn_level = old_player.get("last_warned_week", 0)

            state["players"][player_key] = {
                "user_id": user_id,
                "first_name": user_name,
                "last_name": parsed["user_last_name"],
                "username": parsed["username"],
                "campaign_name": campaign_name,
                "pbp_topic_id": pid,
                "last_post_time": msg_time_iso,
                "last_warned_week": 0,
            }

            if was_removed:
                removed_data = state["removed_players"].pop(player_key)
                print(f"Player {user_name} rejoined {campaign_name}")
                # Welcome back notification — post to CHAT topic, not PBP
                chat_tid = maps.to_chat.get(pid)
                if chat_tid:
                    char_name = helpers.character_name(config, pid, user_id)
                    char_tag = f" ({char_name})" if char_name else ""
                    uname = parsed.get("username", "") or removed_data.get("username", "")
                    mention = f" @{uname}" if uname else ""
                    tg.send_message(
                        group_id, chat_tid,
                        f"👋{mention} {user_name}{char_tag} is back in {campaign_name}!"
                    )
            elif old_warn_level >= 2:
                # Player was warned for 2+ weeks of inactivity — acknowledge return
                print(f"Warned player {user_name} returned to {campaign_name} (was week {old_warn_level})")
                chat_tid = maps.to_chat.get(pid)
                if chat_tid:
                    char_name = helpers.character_name(config, pid, user_id)
                    char_tag = f" as {char_name}" if char_name else ""
                    uname = parsed.get("username", "") or old_player.get("username", "")
                    mention = f" @{uname}" if uname else ""
                    tg.send_message(
                        group_id, chat_tid,
                        f"🎉{mention} {user_name} is back{char_tag}! Good to see you."
                    )

        # Log to persistent PBP transcript
        if not text.startswith("/"):
            _append_to_transcript(parsed, gm_ids, config)

        print(f"Tracked message in {campaign_name} from {user_name}")

    return new_offset


# ------------------------------------------------------------------ #
#  Topic inactivity alerts (4-hour)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Player inactivity tracking (weekly)
# ------------------------------------------------------------------ #




# ------------------------------------------------------------------ #
#  Party roster summary (every 3 days)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Player of the Week (weekly, consistency-based)
# ------------------------------------------------------------------ #




# ------------------------------------------------------------------ #
#  Combat turn pinger (side-based initiative)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Weekly data archive (preserves long-term trends)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Timestamp cleanup (keep only last 15 days)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Weekly pace report
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Streak milestone celebrations
# ------------------------------------------------------------------ #





# ------------------------------------------------------------------ #
#  Campaign anniversary alerts
# ------------------------------------------------------------------ #




# ------------------------------------------------------------------ #
#  Message milestones (every 500 per campaign, every 5000 global)
# ------------------------------------------------------------------ #





# ------------------------------------------------------------------ #
#  Campaign Leaderboard (cross-campaign dashboard)
# ------------------------------------------------------------------ #






# ------------------------------------------------------------------ #
#  Recruitment check (campaigns needing players)
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  Weekly digest (compact cross-campaign newsletter)
# ------------------------------------------------------------------ #







# ------------------------------------------------------------------ #
#  Smart alerts: pace drop & conversation dying
# ------------------------------------------------------------------ #






# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #
def _run_checks(config: dict, bot_state: dict) -> None:
    """Run all scheduled checks, isolating failures so one crash doesn't block others."""
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
    """Entry point: load config/state, process updates, run all scheduled checks, save."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    gist_token = os.environ.get("GIST_TOKEN", "")
    gist_id = os.environ.get("GIST_ID", "")

    if not telegram_token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    # Initialize modules
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

    # Fetch and process new messages
    offset = bot_state.get("offset", 0)
    updates = tg.get_updates(offset)
    print(f"Received {len(updates)} new updates")

    if updates:
        bot_state["offset"] = process_updates(updates, config, bot_state)

    # Run all scheduled checks (error-isolated)
    _run_checks(config, bot_state)

    # Prune old timestamps (lightweight, unlikely to fail)
    cleanup_timestamps(bot_state)

    # Regenerate transcript index if logs exist
    try:
        update_transcript_index(config)
    except Exception as e:
        print(f"Error updating transcript index: {e}")

    # Always save state, even if checks failed
    state_store.save(bot_state)
    print("Done")


if __name__ == "__main__":
    main()
