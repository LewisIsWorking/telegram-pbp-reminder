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
_TIPS = [
    "💡 <b>/mystats</b> — Check your personal stats in any PBP topic. "
    "See your total posts, sessions, average gap, weekly activity, and current posting streak.",

    "💡 <b>/whosturn</b> — During combat, see who has acted and who the party is waiting on. "
    "Works for any player, not just the GM.",

    "💡 <b>/campaign</b> — Get a full scoreboard for the current campaign: "
    "party roster, weekly pace with trends, at-risk players, and combat state. All in one message.",

    "💡 <b>/status</b> — Quick health check: party size, last post time, "
    "posts this week, and any at-risk players. Faster than /campaign when you just need the headlines.",

    "💡 <b>/help</b> — Forgot a command? Type /help to see the full list of bot features and GM commands.",

    "💡 <b>Player of the Week</b> — Every week, the bot picks the most consistent poster "
    "(lowest average gap between posts, not just highest count). The winner picks a flavour boon!",

    "💡 <b>Inactivity warnings</b> — The bot notices if you go quiet. "
    "Week 1: friendly nudge. Week 2: concerned check-in. Week 3: urgent. Week 4: removed from roster. "
    "Just post to reset the timer!",

    "💡 <b>Combat tracking</b> — Type <code>/combat Ogre, 2 Skeletons</code> to start. "
    "The bot tracks who posts their actions. When everyone's done, the GM gets auto-pinged! "
    "Use /whosturn to see who's still needed.",

    "💡 <b>/next</b> — Advance combat phases: players → enemies → next round. "
    "No more typing <code>/round 2 players</code> — just /next! "
    "Use <code>/clog The ogre crits Cardigan!</code> to log key moments, "
    "and /endcombat for a summary.",

    "💡 <b>Roster reports</b> — Every few days the bot posts a roster showing everyone's "
    "post count, sessions, weekly activity, average gap, and last post time. "
    "It's the campaign's health dashboard.",

    "💡 <b>Pace reports</b> — Weekly comparison of this week vs last week: "
    "total posts, GM vs player split, posts per day, and trend arrows. "
    "See if your campaign is speeding up or slowing down.",

    "💡 <b>Posting streaks</b> — Post on consecutive days to build a streak. "
    "Check yours with /mystats. The longer the streak, the bigger the 🔥!",

    "💡 <b>/myhistory</b> — See a visual sparkline of your posting activity over the last 8 weeks. "
    "Track your peak weeks and whether you're trending up or down.",

    "💡 <b>/pause</b> and <b>/resume</b> (GM only) — Going on holiday or taking a break between arcs? "
    "Type <code>/pause on holiday</code> to stop inactivity warnings. <code>/resume</code> to restart.",

    "💡 <b>/kick</b> (GM only) — Need to remove a player from tracking? "
    "Type <code>/kick @username</code> or <code>/kick PlayerName</code>. "
    "They can rejoin by posting in PBP again.",

    "💡 <b>/addplayer</b> (GM only) — Want someone on the roster before they've posted? "
    "Type <code>/addplayer @username Player Name</code> to pre-register them.",

    "💡 <b>/catchup</b> — Been away? Type <code>/catchup</code> to see what happened "
    "since your last post — who posted, how many messages, and a preview of recent posts "
    "so you can jump back in without scrolling.",

    "💡 <b>Message milestones</b> — The bot celebrates every 500th PBP message in each campaign, "
    "and every 5,000th message across all campaigns combined. Keep posting!",

    "💡 <b>/party</b> — See the in-fiction party composition: character names, "
    "who plays them, and when they were last active. Requires character config.",

    "💡 <b>Smart alerts</b> — The bot watches for campaigns that lose momentum. "
    "If weekly posts drop by 40%+, or if everyone goes silent for 2+ days, "
    "you'll get a gentle heads-up. Use /pause to silence during planned breaks.",

    "💡 <b>/overview</b> — See a compact summary of ALL campaigns at once: "
    "health status, weekly posts, player count, and last post time. "
    "Perfect for GMs juggling multiple games.",

    "💡 <b>/scene</b> (GM only) — Mark a scene boundary in the transcript. "
    "Type <code>/scene The Docks at Midnight</code> and it'll appear as a divider "
    "in the archived logs. Keeps your campaign history organised by narrative beats.",

    "💡 <b>/note</b> (GM only) — Keep persistent notes for any campaign. "
    "Type <code>/note Party agreed to meet the informant at dawn</code>. "
    "View with /notes, delete with /delnote. Notes also appear in /campaign output.",

    "💡 <b>/activity</b> — See when your campaign is most active: busiest days, "
    "peak hours, and time blocks. Great for knowing when to expect replies "
    "and when to post for maximum engagement.",

    "💡 <b>/profile</b> — Look up any player across all campaigns. "
    "Type <code>/profile @alice</code> to see their character, post counts, "
    "streaks, and last activity in every game they're in.",

    "💡 <b>Word Count Tracking</b> — The bot now tracks total words written per player. "
    "Check /mystats to see your word count and average words per post. "
    "Quality and quantity both matter in PBP!",

    "💡 <b>/away</b> — Going on holiday? Type <code>/away 5 days vacation</code> "
    "and the bot will skip you for inactivity warnings and combat pings. "
    "Use /back when you return, or the bot clears it automatically when you post.",

    "💡 <b>/recap</b> — Read back the story! <code>/recap</code> shows the last 10 posts "
    "with character names, GM tags 🎲, scene markers, and time gaps so you can feel the "
    "rhythm of the conversation. Use <code>/recap 20</code> for more.",

    "💡 <b>/roll</b> — Roll dice right in chat! "
    "<code>/roll 1d20+5 Stealth</code> for a skill check, "
    "<code>/roll 2d6+3</code> for damage, or "
    "<code>/roll 4d6kh3</code> to keep the highest 3. "
    "Uses your character name if one is configured.",

    "💡 <b>/quests</b> — Your GM can track active quest objectives with "
    "<code>/quest Find the missing merchant</code>. View them with /quests. "
    "When you complete one, the GM uses /done to check it off. "
    "Never lose track of what you're supposed to be doing!",

    "💡 <b>/gm</b> (GM only) — A compact dashboard showing every campaign's health "
    "at a glance: weekly post count, player count, away/at-risk flags, "
    "active quests, and combat status. One command to check all your games.",

    "💡 <b>/dc</b> — Quick DC lookup for Pathfinder 2e! "
    "<code>/dc 5</code> shows all difficulty DCs for level 5. "
    "<code>/dc 5 hard</code> gives just the hard DC. "
    "<code>/dc trained</code> for proficiency DCs. Never flip through the CRB again.",

    "💡 <b>/pins</b> — The GM can bookmark key story moments with "
    "<code>/pin The party found the dragon's weakness</code>. "
    "View them with /pins. Great for tracking reveals, clues, and plot twists.",

    "💡 <b>/lootlist</b> — Track party loot with "
    "<code>/loot +1 striking longsword</code>. View everything with /lootlist. "
    "Remove claimed items with /delloot. Never forget what you picked up!",

    "💡 <b>/npcs</b> — Can't remember who that merchant was? "
    "GMs can add NPCs with <code>/npc Gorund — Dwarven blacksmith, owes party a favour</code>. "
    "View them all with /npcs. A living dramatis personae for your campaign.",

    "💡 <b>/conditions</b> — Track buffs, debuffs, and persistent effects. "
    "<code>/condition Cardigan — Frightened 2 | until end of next turn</code>. "
    "View active conditions with /conditions, end them with /endcondition, "
    "or /clearconditions to wipe the slate.",

    "💡 <b>/hp</b> — Track enemy HP in combat! "
    "<code>/hp set Ogre 45/45</code> to start, "
    "<code>/hp d Ogre 12</code> to deal damage, "
    "<code>/hp h Ogre 5</code> to heal. "
    "Visual HP bars show who's hurting. /hp clear when combat ends.",

    "💡 <b>/clocks</b> — Progress clocks for investigations, rituals, countdowns. "
    "<code>/clock Investigation 6</code> creates a 6-segment clock. "
    "<code>/tick Investigation</code> fills a segment. "
    "Great for tracking anything that builds over time. ◉◉◉○○○",

    "💡 <b>/vote</b> — Stuck on a group decision? GMs can start a vote: "
    "<code>/vote Where do we go? | North gate | Sewers | Rest first</code>. "
    "Players use /pick N to cast their vote. /endvote closes it and shows the winner.",

    "💡 <b>/timer</b> — Set a response deadline for the party. "
    "<code>/timer 24h Post your combat actions</code>. "
    "The bot will post a notification when time's up. "
    "Check with /showtimer, cancel with /canceltimer.",

    "💡 <b>/summary</b> — Everything at a glance: current scene, combat state, "
    "active quests, conditions, NPCs, loot, and pins. "
    "One command to see the full state of your campaign.",
]


def post_daily_tip(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a random tip to a randomly chosen PBP chat topic once per day."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    # Check daily interval
    last_tip_str = state.get("last_daily_tip")
    if last_tip_str:
        last_tip = datetime.fromisoformat(last_tip_str)
        if helpers.hours_since(now, last_tip) < 22:
            return

    # Collect all chat topic IDs
    chat_topics = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        if helpers.feature_enabled(config, pid, "alerts"):
            chat_topics.append(pair["chat_topic_id"])

    if not chat_topics:
        return

    # Pick a tip we haven't used recently
    used_tips = state.get("used_tip_indices", [])
    available = [i for i in range(len(_TIPS)) if i not in used_tips]
    if not available:
        # Reset cycle
        available = list(range(len(_TIPS)))
        used_tips = []

    tip_idx = random.choice(available)
    topic_id = random.choice(chat_topics)

    print(f"Daily tip #{tip_idx} to topic {topic_id}")
    if tg.send_message(group_id, topic_id, _TIPS[tip_idx], parse_mode="HTML"):
        state["last_daily_tip"] = now.isoformat()
        used_tips.append(tip_idx)
        state["used_tip_indices"] = used_tips




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
def check_and_alert(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Send alerts to campaigns inactive beyond alert_after_hours."""
    group_id = config["group_id"]
    alert_hours = config.get("alert_after_hours", 4)
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name[pid]

        if not helpers.feature_enabled(config, pid, "alerts"):
            continue

        if pid in state.get("paused_campaigns", {}):
            continue

        if pid not in state.get("topics", {}):
            continue
            print(f"No messages tracked yet for {name}, skipping")
            continue

        topic_state = state["topics"][pid]
        last_time = datetime.fromisoformat(topic_state["last_message_time"])
        elapsed_hours = helpers.hours_since(now, last_time)

        if elapsed_hours < alert_hours:
            continue

        # Don't re-alert within alert_hours
        last_alert_str = state["last_alerts"].get(pid)
        if last_alert_str:
            since_last = helpers.hours_since(now, datetime.fromisoformat(last_alert_str))
            if since_last < alert_hours:
                print(f"{name}: Already alerted {since_last:.1f}h ago, skipping")
                continue

        hours_int = int(elapsed_hours)
        days = hours_int // 24
        remaining_hours = hours_int % 24
        last_user = topic_state.get("last_user", "someone")
        last_user_id = topic_state.get("last_user_id", "")

        time_str = f"{days}d {remaining_hours}h" if days > 0 else f"{hours_int}h"

        # Look up total message count for last poster
        count = state.get("message_counts", {}).get(pid, {}).get(last_user_id, 0)
        count_str = f" ({count} total posts)" if count > 0 else ""

        last_date = fmt_date(last_time)

        message = (
            f"No new posts in {name} PBP for {time_str}.\n"
            f"Last post was from {last_user}{count_str} on {last_date}."
        )

        print(f"Sending alert for {name}: {time_str} inactive")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_alerts"][pid] = now.isoformat()


# ------------------------------------------------------------------ #
#  Player inactivity tracking (weekly)
# ------------------------------------------------------------------ #
_INACTIVITY_TEMPLATES = {
    1: "{mention} hasn't posted in {campaign} PBP for {days} days (last: {date}). Everything okay?",
    2: "{mention} still no post in {campaign} PBP. It's been {days} days now (last: {date}).",
    3: "{mention} it's been {days} days without a post in {campaign} PBP (last: {date}). 1 week until auto-removal from the campaign.",
}


def check_player_activity(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn inactive players at 1/2/3 weeks, remove at 4 weeks."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)

    players_to_remove = []

    for player_key, player in state["players"].items():
        pbp_topic_id = player["pbp_topic_id"]
        chat_topic_id = maps.to_chat.get(pbp_topic_id)
        if not chat_topic_id:
            continue
        if not helpers.feature_enabled(config, pbp_topic_id, "warnings"):
            continue
        if pbp_topic_id in state.get("paused_campaigns", {}):
            continue
        # Skip players who are marked as away
        user_id = player.get("user_id", "")
        if helpers.is_away(state, pbp_topic_id, user_id, now):
            continue

        last_post = datetime.fromisoformat(player["last_post_time"])
        elapsed_days = helpers.days_since(now, last_post)
        current_week = int(elapsed_days / 7)
        last_warned = player.get("last_warned_week", 0)

        first_name = player["first_name"]
        campaign = player["campaign_name"]
        mention = helpers.player_mention(player)
        days_inactive = int(elapsed_days)
        last_date = fmt_date(last_post)

        # 4+ weeks: remove
        if current_week >= helpers.PLAYER_REMOVE_WEEKS:
            if last_warned < helpers.PLAYER_REMOVE_WEEKS:
                message = (
                    f"{mention} has not posted in {campaign} PBP for "
                    f"{days_inactive} days (last: {last_date}). They are no longer tracked "
                    f"as an active player in this campaign."
                )
                print(f"Removing {first_name} from {campaign} ({days_inactive}d)")
                tg.send_message(group_id, chat_topic_id, message)
                players_to_remove.append(player_key)
            continue

        # 1, 2, 3 week warnings
        for week_mark in helpers.PLAYER_WARN_WEEKS:
            if current_week >= week_mark and last_warned < week_mark:
                template = _INACTIVITY_TEMPLATES.get(week_mark, _INACTIVITY_TEMPLATES[3])
                message = template.format(
                    mention=mention, campaign=campaign,
                    days=days_inactive, date=last_date,
                )
                print(f"Warning {first_name} in {campaign}: week {week_mark}")
                if tg.send_message(group_id, chat_topic_id, message):
                    player["last_warned_week"] = week_mark
                break  # One warning per player per run

    # Move removed players out
    for key in players_to_remove:
        removed = state["players"].pop(key)
        state["removed_players"][key] = {
            "removed_at": now.isoformat(),
            "first_name": removed["first_name"],
            "username": removed.get("username", ""),
            "campaign_name": removed["campaign_name"],
        }


# ------------------------------------------------------------------ #
#  Party roster summary (every 3 days)
# ------------------------------------------------------------------ #
def post_roster_summary(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post a summary of all tracked players per campaign to CHAT topics."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    campaigns = helpers.players_by_campaign(state)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "roster"):
            continue
        if not helpers.interval_elapsed(state["last_roster"].get(pid), helpers.ROSTER_INTERVAL_DAYS, now):
            continue

        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        name = maps.to_name.get(pid, "Unknown")
        players = campaigns.get(pid, [])
        counts = state.get("message_counts", {}).get(pid, {})
        topic_timestamps = helpers.get_topic_timestamps(state, pid)

        if not players and not counts:
            continue

        lines = []
        characters = helpers.get_characters(config, pid)

        for player in sorted(players, key=lambda p: counts.get(p["user_id"], 0), reverse=True):
            uid = player["user_id"]
            raw_ts = topic_timestamps.get(uid, [])
            if not raw_ts:
                continue
            full = helpers.player_full_name(player)
            char_name = characters.get(uid)
            label = f"{full} ({char_name})" if char_name else full
            stats = _roster_user_stats(raw_ts, counts.get(uid, 0), now)
            lines.append(_roster_block(label, player.get("username", ""), stats))

        # Add GM stats if present
        for gm_id in gm_ids:
            gm_count = counts.get(gm_id, 0)
            raw_ts = topic_timestamps.get(gm_id, [])
            if gm_count > 0 and raw_ts:
                stats = _roster_user_stats(raw_ts, gm_count, now)
                lines.insert(0, _roster_block("GM", "", stats))

        if not lines:
            continue

        player_count = len([p for p in players if p.get("user_id", "") not in gm_ids])
        footer = f"\n\n———\n\n📋 {name} Party Size\n"
        footer += f"Party size: {player_count}/{helpers.REQUIRED_PLAYERS}."
        if player_count < helpers.REQUIRED_PLAYERS:
            needed = helpers.REQUIRED_PLAYERS - player_count
            s = "s" if needed != 1 else ""
            footer += f"\n{name} needs {needed} more player{s}!"

        message = f"Party roster for {name}:\n\n" + "\n\n".join(lines) + footer

        print(f"Posting roster for {name}")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_roster"][pid] = now.isoformat()


# ------------------------------------------------------------------ #
#  Player of the Week (weekly, consistency-based)
# ------------------------------------------------------------------ #
def _gather_potw_candidates(
    topic_timestamps: dict, gm_ids: set, week_ago: datetime, pid: str, state: dict,
) -> list[dict]:
    """Find POTW candidates: players with enough posts, ranked by avg gap."""
    candidates = []
    for user_id, timestamps in topic_timestamps.items():
        if user_id in gm_ids:
            continue

        sessions = deduplicate_posts(timestamps_in_window(timestamps, week_ago))
        if len(sessions) < helpers.POTW_MIN_POSTS:
            continue

        sessions.sort()
        avg_gap = helpers.avg_gap_hours(sessions) or float("inf")

        player = helpers.get_player(state, pid, user_id)
        candidates.append({
            "user_id": user_id,
            "first_name": player.get("first_name", "Unknown"),
            "last_name": player.get("last_name", ""),
            "username": player.get("username", ""),
            "avg_gap_hours": avg_gap,
            "post_count": len(sessions),
        })
    return candidates


def player_of_the_week(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Award Player of the Week based on smallest average gap between posts."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    try:
        with open(helpers.BOONS_PATH) as f:
            boons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load boons: {e}")
        boons = ["Something mildly beneficial happens to you today."]

    maps = maps or build_topic_maps(config)
    week_ago = now - timedelta(days=7)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "potw"):
            continue
        if not helpers.interval_elapsed(state["last_potw"].get(pid), helpers.POTW_INTERVAL_DAYS, now):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        candidates = _gather_potw_candidates(topic_timestamps, gm_ids, week_ago, pid, state)
        if not candidates:
            print(f"No POTW candidates for {name} (need {helpers.POTW_MIN_POSTS}+ posts)")
            continue

        winner = min(candidates, key=lambda c: c["avg_gap_hours"])
        mention = helpers.player_mention(winner)
        avg_gap_str = f"{winner['avg_gap_hours']:.1f}h"

        # Pick 3 random flavour boons + 1 mechanical boon
        chosen_boons = random.sample(boons, min(3, len(boons)))
        chosen_boons.append(random.choice(helpers.MECHANICAL_BOONS))

        base_message = (
            f"Player of the Week for {name}: {mention}!\n"
            f"({fmt_date(week_ago)} to {fmt_date(now)})\n\n"
            f"{posts_str(winner['post_count'])} this week with an average "
            f"gap of {avg_gap_str} between posts. The most consistent "
            f"driver of the story."
        )

        boon_text = "\n\nChoose your boon:\n"
        for i, b in enumerate(chosen_boons):
            boon_text += f"\n{i + 1}. {b}\n"

        buttons = [
            {"text": f"Boon #{i + 1}", "callback_data": f"boon:{pid}:{i}"}
            for i in range(len(chosen_boons))
        ]

        print(f"POTW for {name}: {winner['first_name']} (avg gap {avg_gap_str})")
        msg_id = tg.send_message_with_buttons(group_id, chat_topic_id, base_message + boon_text, buttons)
        if msg_id:
            state["last_potw"][pid] = now.isoformat()
            state["pending_potw_boons"][pid] = {
                "message_id": msg_id,
                "winner_user_id": winner["user_id"],
                "campaign_name": name,
                "boons": chosen_boons,
                "base_message": base_message,
                "posted_at": now.isoformat(),
            }


# ------------------------------------------------------------------ #
#  Combat turn pinger (side-based initiative)
# ------------------------------------------------------------------ #
def check_combat_turns(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """During players' phase, ping players who haven't acted yet."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, combat in list(state["combat"].items()):
        if not combat.get("active"):
            continue

        if not helpers.feature_enabled(config, pid, "combat"):
            continue

        if combat["current_phase"] != "players":
            continue

        # Check if enough time has passed since phase started
        phase_start = datetime.fromisoformat(combat["phase_started_at"])
        hours_elapsed = helpers.hours_since(now, phase_start)

        if hours_elapsed < helpers.COMBAT_PING_HOURS:
            continue

        # Don't re-ping within helpers.COMBAT_PING_HOURS
        last_ping_str = combat.get("last_ping_at")
        if last_ping_str:
            since_ping = helpers.hours_since(now, datetime.fromisoformat(last_ping_str))
            if since_ping < helpers.COMBAT_PING_HOURS:
                continue

        # Find all known players in this campaign who haven't acted
        acted_raw = combat.get("players_acted", {})
        acted = set(acted_raw.keys()) if isinstance(acted_raw, dict) else set(acted_raw)
        missing = [
            helpers.player_mention(p)
            for p in all_campaigns.get(pid, [])
            if p["user_id"] not in acted
            and not helpers.is_away(state, pid, p["user_id"], now)
        ]

        if not missing:
            continue

        campaign_name = combat.get("campaign_name", "Unknown")
        round_num = combat.get("round", 1)
        hours_int = int(hours_elapsed)

        chat_topic_id = maps.to_chat.get(pid)
        if not chat_topic_id:
            continue

        missing_str = ", ".join(missing)
        phase_date = fmt_date(phase_start)
        message = (
            f"Round {round_num} - waiting on: {missing_str}\n"
            f"({hours_int}h since players' phase started on {phase_date})"
        )

        print(f"Combat ping in {campaign_name}: waiting on {missing_str}")
        if tg.send_message(group_id, chat_topic_id, message):
            combat["last_ping_at"] = now.isoformat()


# ------------------------------------------------------------------ #
#  Weekly data archive (preserves long-term trends)
# ------------------------------------------------------------------ #
def archive_weekly_data(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Archive weekly summaries to a JSON file in the repo.

    Stores compact per-campaign stats keyed by ISO week (e.g. '2026-W07').
    The file is committed back to the repo by the GitHub Actions workflow,
    giving full git history and no gist size concerns.
    """
    now = now or datetime.now(timezone.utc)

    # Use last week's ISO week number (since current week is still in progress)
    last_week = now - timedelta(days=7)
    year, week_num, _ = last_week.isocalendar()
    week_key = f"{year}-W{week_num:02d}"

    # Check if we already archived this week (tracked in gist state)
    if state.get("last_archived_week") == week_key:
        return

    # Load existing archive from repo file
    helpers.ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(helpers.ARCHIVE_PATH) as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {}

    week_start = now - timedelta(days=now.weekday() + 7)  # Start of last week (Monday)
    week_end = week_start + timedelta(days=7)

    maps = build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, name in maps.to_name.items():
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        gm_posts = 0
        player_posts = 0
        player_counts = {}
        player_post_times = []
        player_details = {}  # name -> {posts, sessions (unique days), timestamps}

        for uid, timestamps in topic_timestamps.items():
            is_gm = uid in gm_ids
            player_info = helpers.get_player(state, pid, uid)

            user_sessions = deduplicate_posts(
                timestamps_in_window(timestamps, week_start, week_end)
            )
            session_count = len(user_sessions)

            if is_gm:
                gm_posts += session_count
            else:
                player_posts += session_count
                player_post_times.extend(user_sessions)
                if session_count > 0:
                    p_name = helpers.player_mention(player_info)
                    player_counts[p_name] = player_counts.get(p_name, 0) + session_count
                    # Collect per-player detail
                    unique_days = len({ts.date() for ts in user_sessions})
                    p_gap = helpers.avg_gap_hours(sorted(user_sessions))
                    player_details[p_name] = {
                        "posts": session_count,
                        "sessions": unique_days,
                        "avg_gap_h": round(p_gap, 1) if p_gap is not None else None,
                        "words": state.get("word_counts", {}).get(pid, {}).get(uid, 0),
                    }

        # Calculate player avg gap
        raw_gap = helpers.avg_gap_hours(sorted(player_post_times))
        player_avg_gap = round(raw_gap, 1) if raw_gap is not None else None

        active_players = len([p for p in all_campaigns.get(pid, []) if p.get("user_id", "") not in gm_ids])

        archive_key = f"{pid}:{week_key}"
        archive[archive_key] = {
            "campaign": name,
            "week": week_key,
            "gm_posts": gm_posts,
            "player_posts": player_posts,
            "total_posts": gm_posts + player_posts,
            "player_avg_gap_h": player_avg_gap,
            "active_players": active_players,
            "total_words": sum(state.get("word_counts", {}).get(pid, {}).values()),
            "top_players": dict(sorted(
                player_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]),
            "player_breakdown": player_details,
        }

    # Write archive to repo file
    with open(helpers.ARCHIVE_PATH, "w") as f:
        json.dump(archive, f, indent=2)

    state["last_archived_week"] = week_key
    print(f"Archived weekly data for {week_key} to {helpers.ARCHIVE_PATH}")


# ------------------------------------------------------------------ #
#  Timestamp cleanup (keep only last 15 days)
# ------------------------------------------------------------------ #
def cleanup_timestamps(state: dict) -> None:
    """Prune old timestamps to prevent gist from growing."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()

    for pid in list(state.get("post_timestamps", {}).keys()):
        for uid in list(state["post_timestamps"][pid].keys()):
            filtered = [
                ts for ts in state["post_timestamps"][pid][uid]
                if ts >= cutoff
            ]
            if filtered:
                state["post_timestamps"][pid][uid] = filtered
            else:
                del state["post_timestamps"][pid][uid]
        if not state["post_timestamps"][pid]:
            del state["post_timestamps"][pid]


# ------------------------------------------------------------------ #
#  Weekly pace report
# ------------------------------------------------------------------ #
def post_pace_report(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post weekly pace comparison: posts/day this week vs last week, split GM/players."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)

    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "pace"):
            continue
        if not helpers.interval_elapsed(state["last_pace"].get(pid), helpers.PACE_INTERVAL_DAYS, now):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if not topic_timestamps:
            continue

        pace = helpers.pace_split(topic_timestamps, gm_ids, now)
        gm_this = pace["gm_this"]
        gm_last = pace["gm_last"]
        player_this = pace["player_this"]
        player_last = pace["player_last"]

        this_week = gm_this + player_this
        last_week = gm_last + player_last
        this_avg = this_week / 7.0
        last_avg = last_week / 7.0

        # Determine trend
        if last_avg == 0 and this_avg == 0:
            continue  # No data
        icon = helpers.trend_icon(int(this_avg * 100), int(last_avg * 100))

        this_week_start = fmt_date(week_ago)
        this_week_end = fmt_date(now)
        last_week_start = fmt_date(two_weeks_ago)
        last_week_end = fmt_date(week_ago)

        this_week_num = f"W{now.isocalendar()[1]:02d}"
        last_week_num = f"W{week_ago.isocalendar()[1]:02d}"

        message = (
            f"{icon} Weekly pace for {name}:\n"
            f"\n"
            f"This week {this_week_num} ({this_week_start} to {this_week_end}):\n"
            f"  GM: {gm_this} posts ({gm_this / 7.0:.1f}/day)\n"
            f"  Players: {player_this} posts ({player_this / 7.0:.1f}/day)\n"
            f"  Total: {this_week} posts ({this_avg:.1f}/day)\n"
            f"\n"
            f"Last week {last_week_num} ({last_week_start} to {last_week_end}):\n"
            f"  GM: {gm_last} posts ({gm_last / 7.0:.1f}/day)\n"
            f"  Players: {player_last} posts ({player_last / 7.0:.1f}/day)\n"
            f"  Total: {last_week} posts ({last_avg:.1f}/day)\n"
            f"\n"
            f"Trend: {icon}"
        )

        print(f"Pace report for {name}: {this_week} vs {last_week} ({icon})")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_pace"][pid] = now.isoformat()


# ------------------------------------------------------------------ #
#  Streak milestone celebrations
# ------------------------------------------------------------------ #
_STREAK_MILESTONES = [7, 14, 30, 60, 90]

_STREAK_MESSAGES = {
    7: "🔥 {name} is on a 7-day posting streak in {campaign}! One full week of consistency.",
    14: "🔥🔥 {name} has hit a 14-day streak in {campaign}! Two solid weeks.",
    30: "🔥🔥🔥 {name} has reached a 30-day streak in {campaign}! A full month of daily posts. Legendary.",
    60: "🌟 {name} has been posting daily for 60 days straight in {campaign}. Absolute dedication.",
    90: "👑 {name} has hit 90 days in {campaign}. Three months without missing a day. Unbelievable.",
}


def check_streak_milestones(config: dict, state: dict, *, now: datetime | None = None, maps=None, **_kw) -> None:
    """Celebrate when a player crosses a streak milestone (7, 14, 30, 60, 90 days)."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    celebrated = state.setdefault("celebrated_streaks", {})

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name.get(pid, "Unknown")
        topic_ts = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        for uid, raw_ts in topic_ts.items():
            if uid in gm_ids:
                continue

            streak = helpers.calc_streak(raw_ts, now)
            if streak < _STREAK_MILESTONES[0]:
                continue

            # Find the highest milestone crossed
            milestone = 0
            for m in _STREAK_MILESTONES:
                if streak >= m:
                    milestone = m

            key = f"{pid}:{uid}"
            last_celebrated = celebrated.get(key, 0)

            if milestone <= last_celebrated:
                continue

            player = helpers.get_player(state, pid, uid)
            player_name = player.get("first_name", "Someone") if player else "Someone"

            message = _STREAK_MESSAGES.get(milestone, "🔥 {name} is on a {streak}-day streak in {campaign}!")
            message = message.format(name=player_name, campaign=name, streak=streak)

            print(f"Streak milestone: {player_name} hit {milestone}d in {name}")
            if tg.send_message(group_id, chat_topic_id, message):
                celebrated[key] = milestone


# ------------------------------------------------------------------ #
#  Campaign anniversary alerts
# ------------------------------------------------------------------ #
def _next_anniversary(config: dict, today) -> str | None:
    """Find the next upcoming campaign anniversary after today."""
    upcoming = []
    for pair in config["topic_pairs"]:
        created_str = pair.get("created")
        if not created_str:
            continue
        created = datetime.strptime(created_str, "%Y-%m-%d").date()
        name = pair["name"]

        # This year's anniversary
        try:
            ann_this_year = created.replace(year=today.year)
        except ValueError:
            continue  # Feb 29 edge case

        if ann_this_year > today:
            years = today.year - created.year
            if years >= 1:
                upcoming.append((ann_this_year, name, years))
        else:
            # Next year's anniversary
            try:
                ann_next_year = created.replace(year=today.year + 1)
            except ValueError:
                continue
            years = today.year + 1 - created.year
            if years >= 1:
                upcoming.append((ann_next_year, name, years))

    if not upcoming:
        return None
    upcoming.sort()
    date, name, years = upcoming[0]
    days_until = (date - today).days
    year_str = f"{years} year{'s' if years != 1 else ''}"
    return f"📅 Next anniversary: {name} turns {year_str} old on {date.strftime('%B %d')} ({days_until}d away)"


def check_anniversaries(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a celebration when a campaign hits a yearly anniversary."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)
    today = now.date()

    for pair in config["topic_pairs"]:
        pid = str(pair["pbp_topic_ids"][0])
        chat_topic_id = pair["chat_topic_id"]
        name = pair["name"]

        if not helpers.feature_enabled(config, pid, "anniversary"):
            continue

        created_str = pair.get("created")

        if not created_str:
            continue

        created = datetime.strptime(created_str, "%Y-%m-%d").date()

        # Check if today is the anniversary (same month and day)
        if today.month != created.month or today.day != created.day:
            continue

        # How many years?
        years = today.year - created.year
        if years < 1:
            continue

        # Don't post the same anniversary twice
        anniversary_key = f"{pid}:{years}"
        if anniversary_key in state["last_anniversary"]:
            continue

        if years == 1:
            year_str = "1 year"
        else:
            year_str = f"{years} years"

        message = (
            f"🎂 {name} is {year_str} old today!\n\n"
            f"Campaign started {created.strftime('%B %d, %Y')} (W{created.isocalendar()[1]}). "
            f"Here's to more adventures ahead."
        )

        # Append next upcoming anniversary
        next_ann = _next_anniversary(config, today)
        if next_ann:
            message += f"\n\n———\n\n{next_ann}"

        print(f"Anniversary for {name}: {year_str}")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_anniversary"][anniversary_key] = now.isoformat()


# ------------------------------------------------------------------ #
#  Message milestones (every 500 per campaign, every 5000 global)
# ------------------------------------------------------------------ #
_CAMPAIGN_MILESTONE_STEP = 500
_GLOBAL_MILESTONE_STEP = 5000

_MILESTONE_ICONS = {
    500: "🎯", 1000: "🏅", 1500: "⚡", 2000: "🔥", 2500: "⭐",
    3000: "💎", 3500: "🌟", 4000: "👑", 4500: "🏆", 5000: "🎆",
}


def check_message_milestones(config: dict, state: dict, *, now: datetime | None = None, maps=None, **_kw) -> None:
    """Celebrate when a campaign or the global total crosses a message milestone."""
    group_id = config["group_id"]
    maps = maps or build_topic_maps(config)
    celebrated = state.setdefault("celebrated_milestones", {})

    global_total = 0

    for pid, name in maps.to_name.items():
        # Count total messages for this campaign
        counts = state.get("message_counts", {}).get(pid, {})
        campaign_total = sum(counts.values())
        global_total += campaign_total

        if campaign_total < _CAMPAIGN_MILESTONE_STEP:
            continue

        # Find highest milestone crossed
        milestone = (campaign_total // _CAMPAIGN_MILESTONE_STEP) * _CAMPAIGN_MILESTONE_STEP

        campaign_key = f"campaign:{pid}"
        last_celebrated = celebrated.get(campaign_key, 0)

        if milestone > last_celebrated:
            icon = _MILESTONE_ICONS.get(milestone, "🎯")
            chat_topic_id = maps.to_chat.get(pid)
            if chat_topic_id:
                message = (
                    f"{icon} {name} has hit {milestone:,} PBP messages!\n\n"
                    f"That's {milestone:,} posts of collaborative storytelling. "
                    f"Every single one moved the story forward."
                )
                if tg.send_message(group_id, chat_topic_id, message):
                    celebrated[campaign_key] = milestone
                    print(f"Milestone: {name} hit {milestone:,} messages")

    # Global milestone
    if global_total >= _GLOBAL_MILESTONE_STEP:
        global_milestone = (global_total // _GLOBAL_MILESTONE_STEP) * _GLOBAL_MILESTONE_STEP
        last_global = celebrated.get("global", 0)

        if global_milestone > last_global:
            leaderboard_topic = config.get("leaderboard_topic_id")
            if leaderboard_topic:
                message = (
                    f"🎆 Path Wars has hit {global_milestone:,} total PBP messages "
                    f"across all campaigns!\n\n"
                    f"That's {global_milestone:,} posts of adventure, intrigue, "
                    f"and terrible puns spread across {len(maps.to_name)} campaigns."
                )
                if tg.send_message(group_id, leaderboard_topic, message):
                    celebrated["global"] = global_milestone
                    print(f"Global milestone: {global_milestone:,} total messages")


# ------------------------------------------------------------------ #
#  Campaign Leaderboard (cross-campaign dashboard)
# ------------------------------------------------------------------ #
def _gather_leaderboard_stats(config: dict, state: dict, now: datetime) -> tuple[list, dict, list]:
    """Collect per-campaign stats, global player rankings, and top streaks for the leaderboard."""
    seven_days_ago = now - timedelta(days=7)
    three_days_ago = now - timedelta(days=3)
    six_days_ago = now - timedelta(days=6)

    campaign_stats = []
    global_player_posts = {}
    all_streaks = []

    maps = build_topic_maps(config)

    for pid, name in maps.to_name.items():
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        gm_7d = 0
        player_7d = 0
        posts_recent_3d = 0
        posts_prev_3d = 0
        player_post_counts = {}
        all_post_times_7d = []
        player_post_times_7d = []

        for uid, timestamps in topic_timestamps.items():
            is_gm = uid in gm_ids
            player_info = helpers.get_player(state, pid, uid)

            user_7d_posts = timestamps_in_window(timestamps, seven_days_ago)
            posts_recent_3d += len(timestamps_in_window(timestamps, three_days_ago))
            posts_prev_3d += len(timestamps_in_window(timestamps, six_days_ago, three_days_ago))

            user_sessions = deduplicate_posts(user_7d_posts)
            session_count = len(user_sessions)

            all_post_times_7d.extend(user_sessions)
            if is_gm:
                gm_7d += session_count
            else:
                player_7d += session_count
                player_post_times_7d.extend(user_sessions)
                if session_count > 0:
                    full = helpers.player_full_name(player_info)
                    player_post_counts.setdefault(uid, {
                        "full_name": full,
                        "username": player_info.get("username", ""),
                        "count": 0,
                    })
                    player_post_counts[uid]["count"] += session_count

            # Collect streak data (players only)
            if not is_gm:
                streak = helpers.calc_streak(timestamps, now)
                if streak >= 2 and player_info:
                    all_streaks.append({
                        "name": helpers.player_full_name(player_info),
                        "streak": streak,
                        "campaign": name,
                    })

        total_7d = gm_7d + player_7d

        # Average response gap (all posts)
        all_post_times_7d.sort()
        all_avg = helpers.avg_gap_hours(all_post_times_7d)
        avg_gap_str = f"{all_avg:.1f}h" if all_avg is not None else "N/A"

        # Player-only average gap
        player_post_times_7d.sort()
        player_avg_gap = helpers.avg_gap_hours(player_post_times_7d)
        player_avg_gap_str = f"{player_avg_gap:.1f}h" if player_avg_gap is not None else "N/A"

        # Last post across all users
        all_ts = [ts for tss in topic_timestamps.values() for ts in tss]
        last_post_time = max((datetime.fromisoformat(ts) for ts in all_ts), default=None) if all_ts else None

        last_post_str, days_since_last = helpers.fmt_brief_relative(now, last_post_time)
        trend = helpers.trend_icon(posts_recent_3d, posts_prev_3d)

        top_players = sorted(
            player_post_counts.values(),
            key=lambda p: p["count"],
            reverse=True,
        )

        for uid, pdata in player_post_counts.items():
            entry = global_player_posts.setdefault(uid, {
                "full_name": pdata["full_name"],
                "username": pdata.get("username", ""),
                "count": 0,
                "campaigns": 0,
            })
            entry["count"] += pdata["count"]
            entry["campaigns"] += 1

        campaign_stats.append({
            "name": name,
            "total_7d": total_7d,
            "player_7d": player_7d,
            "gm_7d": gm_7d,
            "trend_icon": trend,
            "avg_gap_str": avg_gap_str,
            "player_avg_gap": player_avg_gap,
            "player_avg_gap_str": player_avg_gap_str,
            "last_post_str": last_post_str,
            "days_since_last": days_since_last,
            "top_players": top_players,
        })

    return campaign_stats, global_player_posts, all_streaks


def _format_leaderboard(campaign_stats: list, global_player_posts: dict,
                        now: datetime, streaks: list | None = None) -> str:
    """Format the leaderboard message from collected stats."""
    seven_days_ago = now - timedelta(days=7)

    campaign_stats.sort(key=lambda c: c["player_7d"], reverse=True)
    active = [c for c in campaign_stats if c["total_7d"] > 0]
    dead = [c for c in campaign_stats if c["total_7d"] == 0]

    date_from = fmt_date(seven_days_ago)
    date_to = fmt_date(now)

    lines = [f"📊 Weekly Campaign Leaderboard ({date_from} to {date_to})"]

    # Compute week totals across all campaigns
    week_total_player = sum(c["player_7d"] for c in campaign_stats)
    week_total_gm = sum(c["gm_7d"] for c in campaign_stats)
    week_total_all = sum(c["total_7d"] for c in campaign_stats)
    lines.append(
        f"\n📬 This week: {week_total_all} posts "
        f"({week_total_player} player, {week_total_gm} GM) "
        f"across {len(active)} active campaigns."
    )

    for i, c in enumerate(active):
        rank = helpers.rank_icon(i)
        campaign_block = (
            f"[{rank} {c['name']} {c['trend_icon']}]\n"
            f"- {c['player_7d']} player posts.\n"
            f"- {posts_str(c['total_7d'])} total.\n"
            f"- {c['gm_7d']} GM posts.\n"
            f"- Avg gap: {c['avg_gap_str']}.\n"
            f"- Last post: {c['last_post_str']}."
        )

        player_blocks = []
        for j, p in enumerate(c["top_players"]):
            medal = helpers.rank_icon(j)
            block = f"{medal} {p['full_name']}\n"
            uname = p.get("username", "")
            if uname:
                block += f"- @{uname}\n"
            block += f"- {posts_str(p['count'])}"
            player_blocks.append(block)

        lines.append("\n━━━━━━━━━━━━━━━━\n\n" + campaign_block + "\n\n" + "\n".join(player_blocks))

    if dead:
        lines.append("\n⚠️ Dead campaigns (0 posts in 7 days):")
        for c in dead:
            lines.append(f"💀 [{c['name']}] (last post: {c['last_post_str']})")

    gap_ranked = [c for c in campaign_stats if c["player_avg_gap"] is not None]
    if gap_ranked:
        gap_ranked.sort(key=lambda c: c["player_avg_gap"])
        lines.append("\n━━━━━━━━━━━━━━━━\n\n⏱ Fastest player response gaps:")
        for i, c in enumerate(gap_ranked):
            lines.append(f"{helpers.rank_icon(i)} {c['name']}: {c['player_avg_gap_str']}")

    if global_player_posts:
        lines.append("\n━━━━━━━━━━━━━━━━")
        top_global = sorted(
            global_player_posts.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )
        player_blocks = []
        for i, (uid, pdata) in enumerate(top_global):
            icon = helpers.rank_icon(i)
            campaign_word = "campaign" if pdata["campaigns"] == 1 else "campaigns"
            block = f"{icon} {pdata['full_name']}\n"
            if pdata["username"]:
                block += f"- @{pdata['username']}\n"
            block += f"- {posts_str(pdata['count'])} across {pdata['campaigns']} {campaign_word}"
            player_blocks.append(block)
        lines.append("\n⭐ Top Players of the Week:\n\n" + "\n\n".join(player_blocks))

        # MVP of the Week prize (most active by volume)
        if top_global:
            winner_uid, winner_data = top_global[0]
            winner_name = winner_data["full_name"]
            campaign_word = "campaign" if winner_data["campaigns"] == 1 else "campaigns"
            lines.append(
                f"\n━━━━━━━━━━━━━━━━\n\n"
                f"🏆 MVP of the Week: {winner_name}!\n"
                f"- {posts_str(winner_data['count'])} across "
                f"{winner_data['campaigns']} {campaign_word}.\n"
                f"- Prize: 1 Hero Point in a campaign of your choice! 🎲"
            )

    # Streak leaderboard
    if streaks:
        top_streaks = sorted(streaks, key=lambda s: s["streak"], reverse=True)[:5]
        streak_lines = []
        for i, s in enumerate(top_streaks):
            icon = helpers.rank_icon(i)
            streak_lines.append(f"{icon} {s['name']} — {s['streak']}d streak ({s['campaign']})")
        lines.append("\n━━━━━━━━━━━━━━━━\n\n🔥 Longest Active Streaks:\n\n" + "\n".join(streak_lines))

    return "\n".join(lines)


def post_campaign_leaderboard(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post a cross-campaign activity leaderboard to the ISSUES topic."""
    group_id = config["group_id"]
    leaderboard_topic = config.get("leaderboard_topic_id")
    if not leaderboard_topic:
        return

    now = now or datetime.now(timezone.utc)

    if not helpers.interval_elapsed(state.get("last_leaderboard"), helpers.LEADERBOARD_INTERVAL_DAYS, now):
        return

    campaign_stats, global_player_posts, all_streaks = _gather_leaderboard_stats(config, state, now)

    if not campaign_stats:
        print("No campaign data for leaderboard")
        return

    message = _format_leaderboard(campaign_stats, global_player_posts, now, all_streaks)

    print(f"Posting campaign leaderboard ({len(campaign_stats)} campaigns)")
    if tg.send_message(group_id, leaderboard_topic, message):
        state["last_leaderboard"] = now.isoformat()


# ------------------------------------------------------------------ #
#  Recruitment check (campaigns needing players)
# ------------------------------------------------------------------ #
def check_recruitment_needs(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """If a campaign has fewer than helpers.REQUIRED_PLAYERS, post a notice."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name[pid]

        if not helpers.feature_enabled(config, pid, "recruitment"):
            continue

        # Check interval
        if not helpers.interval_elapsed(state["last_recruitment_check"].get(pid), helpers.RECRUITMENT_INTERVAL_DAYS, now):
            continue

        # Count active players (excluding GM)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        campaign_players = all_campaigns.get(pid, [])
        active = [
            helpers.player_mention(p)
            for p in campaign_players
            if p.get("user_id", "") not in gm_ids
        ]

        player_count = len(active)
        needed = helpers.REQUIRED_PLAYERS - player_count

        if needed <= 0:
            # Full roster, reset timer
            state["last_recruitment_check"][pid] = now.isoformat()
            continue

        # Build roster display
        if active:
            roster_lines = "\n".join(f"- {p}" for p in active)
            roster_section = f"Current roster ({player_count}/{helpers.REQUIRED_PLAYERS}):\n{roster_lines}"
        else:
            roster_section = f"Current roster: 0/{helpers.REQUIRED_PLAYERS} (no active players)"

        message = (
            f"📢 {name} needs {needed} more player{'s' if needed != 1 else ''}!\n\n"
            f"{roster_section}\n\n"
            f"Know anyone who'd like to join? Send them to the recruitment topic!"
        )

        print(f"Recruitment notice for {name}: {player_count}/{helpers.REQUIRED_PLAYERS}")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_recruitment_check"][pid] = now.isoformat()


# ------------------------------------------------------------------ #
#  Weekly digest (compact cross-campaign newsletter)
# ------------------------------------------------------------------ #



def _build_weekly_digest(config: dict, state: dict, now: datetime) -> str:
    """Build a compact one-line-per-campaign weekly digest."""
    maps = build_topic_maps(config)
    week_ago = now - timedelta(days=7)

    campaign_lines = []
    all_campaigns = helpers.players_by_campaign(state)

    for pid, name in maps.to_name.items():
        topic_ts = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        pace = helpers.pace_split(topic_ts, gm_ids, now)
        total = pace["gm_this"] + pace["player_this"]
        total_last = pace["gm_last"] + pace["player_last"]
        trend = helpers.trend_icon(total, total_last)
        health = helpers.health_icon(total)

        # Top contributor this week
        player_week_counts = {}
        for uid, timestamps in topic_ts.items():
            if uid in gm_ids:
                continue
            count = len(timestamps_in_window(timestamps, week_ago))
            if count > 0:
                player = helpers.get_player(state, pid, uid)
                name_str = player.get("first_name", "?") if player else "?"
                player_week_counts[name_str] = count

        top_name = ""
        if player_week_counts:
            top_name = max(player_week_counts, key=player_week_counts.get)

        # Party size (excluding GMs)
        players = all_campaigns.get(pid, [])
        party = f"{len([p for p in players if p['user_id'] not in gm_ids])}/{helpers.REQUIRED_PLAYERS}"

        # Combat?
        combat = state.get("combat", {}).get(pid, {})
        combat_str = " ⚔️" if combat.get("active") else ""

        line = f"{health} {name}: {posts_str(total)} {trend} ({party}){combat_str}"
        if top_name:
            line += f" — MVP: {top_name}"

        campaign_lines.append((total, line))

    # Sort by post count descending
    campaign_lines.sort(key=lambda x: x[0], reverse=True)

    date_str = fmt_date(now)
    header = f"📰 Weekly Digest — {date_str}"
    body = "\n".join(line for _, line in campaign_lines)

    legend = "\n\n🟢 20+ posts | 🟡 10-19 | 🟠 5-9 | 🔴 <5"

    return f"{header}\n\n{body}{legend}"


def post_weekly_digest(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a compact weekly digest to the leaderboard topic."""
    group_id = config["group_id"]
    leaderboard_topic = config.get("leaderboard_topic_id")
    if not leaderboard_topic:
        return

    now = now or datetime.now(timezone.utc)

    # Weekly interval (separate from leaderboard)
    if not helpers.interval_elapsed(state.get("last_weekly_digest"), 7, now):
        return

    message = _build_weekly_digest(config, state, now)

    print(f"Posting weekly digest")
    if tg.send_message(group_id, leaderboard_topic, message):
        state["last_weekly_digest"] = now.isoformat()


# ------------------------------------------------------------------ #
#  Smart alerts: pace drop & conversation dying
# ------------------------------------------------------------------ #
def check_pace_drop(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Alert when a campaign's weekly posts drop >40% vs the previous week.

    Checks once per week (tied to archive cadence). Sends a gentle nudge
    to the campaign's chat topic so the GM is aware without being pushy.
    """
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)
    maps = maps or build_topic_maps(config)

    # Only run on archive day (weekly)
    if not helpers.interval_elapsed(state.get("last_pace_drop_check"), 7, now):
        return

    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    alerts_sent = False
    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "smart_alerts"):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if not topic_timestamps:
            continue

        pace = helpers.pace_split(topic_timestamps, gm_ids, now)
        this_week = pace["gm_this"] + pace["player_this"]
        last_week = pace["gm_last"] + pace["player_last"]

        # Skip if last week had very few posts (avoid noisy alerts)
        if last_week < 5:
            continue

        if this_week == 0 and last_week > 0:
            drop_pct = 100
        elif last_week > 0:
            drop_pct = ((last_week - this_week) / last_week) * 100
        else:
            continue

        if drop_pct > 40:
            message = (
                f"📉 Pace check for {name}:\n"
                f"\n"
                f"Posts dropped from {last_week} last week to {this_week} "
                f"this week ({drop_pct:.0f}% decrease).\n"
                f"\n"
                f"Just a heads-up — no action needed if the break is "
                f"intentional."
            )
            print(f"Pace drop alert for {name}: {last_week} -> {this_week} ({drop_pct:.0f}%)")
            tg.send_message(group_id, chat_topic_id, message)
            alerts_sent = True

    state["last_pace_drop_check"] = now.isoformat()
    if not alerts_sent:
        print("Pace drop check: no significant drops detected")


def check_conversation_dying(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn when ALL participants (including GM) are silent for 48h+.

    Distinct from the 4-hour nudge (which just prompts the next post) — this
    fires once when a campaign crosses the 48h threshold, suggesting the
    campaign may need attention or a deliberate pause.
    """
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)
    maps = maps or build_topic_maps(config)
    threshold = timedelta(hours=48)

    state.setdefault("dying_alerts_sent", {})

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "smart_alerts"):
            continue
        # Skip paused campaigns — they're intentionally quiet
        if state.get("paused", {}).get(pid):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)

        if not topic_timestamps:
            continue

        # Find the most recent post from ANYONE
        latest = None
        for uid, timestamps in topic_timestamps.items():
            for ts in timestamps:
                if latest is None or ts > latest:
                    latest = ts

        if latest is None:
            continue

        try:
            latest_dt = datetime.fromisoformat(latest)
        except (TypeError, ValueError):
            continue

        silence_hours = (now - latest_dt).total_seconds() / 3600.0

        if silence_hours >= threshold.total_seconds() / 3600.0:
            # Only alert once per silence period
            if state["dying_alerts_sent"].get(pid) == "active":
                continue

            days_silent = silence_hours / 24.0
            message = (
                f"💤 {name} has been completely silent for "
                f"{days_silent:.1f} days.\n"
                f"\n"
                f"No posts from anyone — GM or players — since "
                f"{fmt_date(latest_dt)}."
            )
            print(f"Conversation dying alert for {name}: {days_silent:.1f} days silent")
            if tg.send_message(group_id, chat_topic_id, message):
                state["dying_alerts_sent"][pid] = "active"
        else:
            # Reset the flag when activity resumes
            if state["dying_alerts_sent"].get(pid):
                del state["dying_alerts_sent"][pid]


def check_expired_timers(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Check for expired timers and post notifications."""
    if not maps:
        maps = build_topic_maps(config)
    if not now:
        now = datetime.now(timezone.utc)

    group_id = config.get("group_id")
    for pid, timer in list(state.get("timers", {}).items()):
        deadline = datetime.fromisoformat(timer["deadline"])
        if now >= deadline:
            # Check if we already notified
            if timer.get("notified"):
                continue

            chat_topic_id = maps.to_chat.get(pid)
            if not chat_topic_id:
                continue
            campaign_name = maps.to_name.get(pid, pid)
            reason = timer.get("reason", "")
            reason_str = f"\n📝 {reason}" if reason else ""

            tg.send_message(group_id, chat_topic_id,
                            f"⏰ Timer expired for {campaign_name}!{reason_str}\n"
                            f"GMs: /canceltimer to clear.")
            timer["notified"] = True
            print(f"Timer expired in {campaign_name}")


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
