"""
Register bot command menus with Telegram.

Run once (or after adding new commands) to update the / menu.
Uses setMyCommands with two scopes:
  - all_group_chats: player-facing read commands
  - all_chat_administrators: full command set including GM tools

Usage:
  TELEGRAM_BOT_TOKEN=xxx python set_commands.py
"""

import os
import sys
import json
import requests


EVERYONE_COMMANDS = [
    ("help", "Show all bot commands"),
    ("status", "Campaign status overview"),
    ("campaign", "Detailed campaign report"),
    ("overview", "All campaigns at a glance"),
    ("mystats", "Your personal stats"),
    ("party", "Party roster and activity"),
    ("whosturn", "Who hasn't acted in combat"),
    ("combatlog", "Combat round history"),
    ("catchup", "What happened since you left"),
    ("recap", "Recent transcript entries"),
    ("summary", "Campaign summary dashboard"),
    ("activity", "Posting patterns and peak times"),
    ("profile", "Cross-campaign player lookup"),
    ("notes", "View campaign notes"),
    ("quests", "View active quests"),
    ("pins", "View pinned moments"),
    ("lootlist", "View party loot"),
    ("npcs", "View NPC roster"),
    ("conditions", "View active conditions"),
    ("hp", "View HP tracker"),
    ("clocks", "View progress clocks"),
    ("showvote", "View current vote"),
    ("showtimer", "View active timer"),
    ("dc", "PF2e DC lookup by level"),
    ("roll", "Roll dice (e.g. /roll 2d20kh+5)"),
    ("away", "Mark yourself as away"),
    ("available", "Set your posting days (e.g. mon wed fri)"),
    ("back", "Clear your away status"),
    ("boons", "View your POTW boons"),
    ("boonsall", "View all your boons"),
    ("chooseboon", "Choose POTW boon by number"),
    ("pick", "Vote in an active poll"),
    ("search", "Search Archives of Nethys"),
    ("reactions", "Reaction stats for a campaign"),
    ("timeline", "Cross-campaign event timeline"),
    ("waiting", "See what the GM owes you"),
    ("session", "Current session number"),
    ("health", "Campaign health dashboard"),
    ("queuestats", "GM reply stats and productivity"),
    ("registry", "All players who have played in this campaign"),
    ("roster", "Campaign player counts and join/leave history"),
]

GM_COMMANDS = [
    ("gm", "GM dashboard overview"),
    ("rostercampaigns", "Per-campaign full breakdown for every campaign"),
    ("rosterplayers", "Cross-campaign player table with at-risk markers"),
    ("rosterall", "Full roster + at-risk + recent joiners/leavers"),
    ("queue", "Unreplied player messages"),
    ("pause", "Pause inactivity tracking"),
    ("resume", "Resume inactivity tracking"),
    ("scene", "Mark a scene in transcript"),
    ("event", "Log a story event to the timeline"),
    ("setchar", "Set a player's character name: /setchar @user Name"),
    ("note", "Add a campaign note"),
    ("delnote", "Delete a campaign note"),
    ("quest", "Add a quest"),
    ("done", "Mark a quest complete"),
    ("delquest", "Delete a quest"),
    ("pin", "Pin a story moment"),
    ("delpin", "Delete a pin"),
    ("loot", "Add loot item"),
    ("delloot", "Remove loot item"),
    ("npc", "Add an NPC"),
    ("delnpc", "Remove an NPC"),
    ("condition", "Add a condition/buff/debuff"),
    ("endcondition", "Remove a condition"),
    ("clearconditions", "Clear all conditions"),
    ("combat", "Start combat tracking"),
    ("next", "Advance combat phase"),
    ("endcombat", "End combat tracking"),
    ("enemies", "Set enemy roster"),
    ("clock", "Create a progress clock"),
    ("tick", "Advance a clock"),
    ("untick", "Reverse a clock tick"),
    ("delclock", "Delete a clock"),
    ("vote", "Start a vote/poll"),
    ("endvote", "End vote and show results"),
    ("timer", "Set a response timer"),
    ("canceltimer", "Cancel active timer"),
    ("markdone", "Mark queue entry as replied: /markdone [N|msg_id|all]"),
    ("kick", "Remove player from tracking"),
    ("addplayer", "Add player to tracking"),
]


def _fmt(commands: list[tuple[str, str]]) -> list[dict]:
    return [{"command": cmd, "description": desc} for cmd, desc in commands]


def set_commands(token: str) -> None:
    api = f"https://api.telegram.org/bot{token}"

    # Scope 1: all group members see player commands
    resp = requests.post(f"{api}/setMyCommands", json={
        "commands": _fmt(EVERYONE_COMMANDS),
        "scope": {"type": "all_group_chats"},
    })
    data = resp.json()
    if data.get("ok"):
        print(f"Set {len(EVERYONE_COMMANDS)} commands for all group members")
    else:
        print(f"FAILED (group): {data}")

    # Scope 2: group admins see full command set (player + GM)
    all_cmds = EVERYONE_COMMANDS + GM_COMMANDS
    resp = requests.post(f"{api}/setMyCommands", json={
        "commands": _fmt(all_cmds),
        "scope": {"type": "all_chat_administrators"},
    })
    data = resp.json()
    if data.get("ok"):
        print(f"Set {len(all_cmds)} commands for group admins")
    else:
        print(f"FAILED (admin): {data}")

    # Clear default scope (DMs etc) — bot is group-only
    resp = requests.post(f"{api}/setMyCommands", json={
        "commands": [],
        "scope": {"type": "default"},
    })
    if resp.json().get("ok"):
        print("Cleared default scope (DMs)")

    print("Done!")


if __name__ == "__main__":  # pragma: no cover
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN environment variable")
        sys.exit(1)
    set_commands(token)
