"""
Main update processing router.

Parses Telegram updates, builds command context, dispatches to
handler modules, and triggers post-message tracking.
"""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps
from parsing.message import parse_message
from combat.tracker import handle_combat_message
from boons.handler import process_boon_callback

from dispatch import cmd_info, cmd_gm, cmd_trackers, cmd_trackers_items
from dispatch import cmd_conditions_hp, cmd_clocks, cmd_votes_timers
from dispatch import cmd_player
from dispatch.tracking import track_message
from dispatch.bot_topic import handle_bot_topic_cmd
from dispatch.help_text import _HELP_TEXT

# Initialize cmd_info with help text
cmd_info.init(_HELP_TEXT)

_HANDLERS = [
    cmd_info.handle,
    cmd_gm.handle,
    cmd_trackers.handle,
    cmd_trackers_items.handle,
    cmd_conditions_hp.handle,
    cmd_clocks.handle,
    cmd_votes_timers.handle,
    cmd_player.handle,
]

_READ_CMDS = frozenset({
    "/help", "/pbphelp", "/status", "/overview", "/campaign",
    "/mystats", "/me", "/myhistory", "/whosturn", "/combatlog",
    "/catchup", "/party", "/notes", "/quests", "/pins", "/lootlist",
    "/npcs", "/conditions", "/clocks", "/dc", "/showvote", "/showtimer",
    "/summary", "/activity", "/profile", "/recap", "/gm",
    "/boons", "/boonsall", "/search", "/queue", "/reactions", "/timeline",
})


def process_updates(updates: list, config: dict, state: dict) -> int:
    """Process Telegram updates, tracking posts and handling commands.

    Returns new offset for next poll.
    """
    group_id = config["group_id"]
    maps = build_topic_maps(config)
    new_offset = state.get("offset", 0)

    for update in updates:
        update_id = update["update_id"]
        new_offset = max(new_offset, update_id + 1)

        msg = update.get("message")
        cb = update.get("callback_query")

        try:
            if cb:
                process_boon_callback(cb, config, state)
                continue

            # Handle emoji reactions
            if update.get("message_reaction"):
                from commands.reactions import process_reaction
                process_reaction(update, config, state, maps)
                continue

            if not msg:
                continue

            # Handle commands from bot topic (read-only, campaign arg required)
            bot_topic = config.get("bot_topic_id")
            msg_thread = msg.get("message_thread_id")
            if (bot_topic and msg_thread == bot_topic
                    and msg.get("chat", {}).get("id") == group_id):
                raw = msg.get("text", "")
                who = msg.get("from", {}).get("first_name", "?")
                print(f"Bot topic msg from {who}: {raw[:50]}")
                handle_bot_topic_cmd(msg, config, state, maps, group_id, bot_topic,
                                      _READ_CMDS, _HANDLERS)
                continue

            parsed = parse_message(msg, group_id, maps)
            if not parsed:
                continue

            pid = parsed["pid"]
            text = parsed["text"]
            user_id = parsed["user_id"]
            gm_ids = helpers.gm_ids_for_campaign(config, pid)

            cmd_word = text.split()[0] if text.startswith("/") else ""
            is_read = cmd_word in _READ_CMDS or (cmd_word == "/hp" and text.strip() == "/hp")

            ctx = {
                "pid": pid,
                "thread_id": parsed["thread_id"],
                "reply_topic": parsed["chat_topic_id"] if is_read else parsed["thread_id"],
                "user_id": user_id,
                "user_name": parsed["user_name"],
                "campaign_name": parsed["campaign_name"],
                "now_iso": parsed["now_iso"],
                "msg_time_iso": parsed["msg_time_iso"],
                "text": text,
                "cmd_word": cmd_word,
                "gm_ids": gm_ids,
                "group_id": group_id,
                "config": config,
                "state": state,
                "maps": maps,
                "parsed": parsed,
            }

            # Dispatch to command handlers
            if cmd_word:
                for handler in _HANDLERS:
                    if handler(ctx):
                        break

            # Combat commands and tracking (always runs)
            handle_combat_message(
                text, parsed["raw_text"], user_id, parsed["user_name"],
                gm_ids, pid, parsed["campaign_name"],
                parsed["now_iso"], group_id, parsed["thread_id"], state,
            )

            # Post-message state tracking
            track_message(parsed, state, config, gm_ids, maps)

        except Exception as e:
            print(f"Error processing update {update_id}: {e}")

    return new_offset


