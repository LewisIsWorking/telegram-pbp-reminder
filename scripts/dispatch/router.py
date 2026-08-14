"""
Main update processing router.

Parses Telegram updates from all groups, dispatches commands, and
triggers post-message tracking. Poll vote/close handling is in poll_router.py.
"""

import helpers
from helpers import build_topic_maps
from parsing.message import parse_message
from combat.tracker import handle_combat_message
# process_boon_callback removed 2026-05-11 — boon selection moved to the
# website. Inline buttons on old POTW messages now go unhandled.
from dispatch import cmd_info, cmd_info_ext, cmd_gm, cmd_trackers, cmd_trackers_items
from commands.markdone import handle_markdone as _handle_markdone
from dispatch import cmd_conditions_hp, cmd_clocks, cmd_votes_timers
from dispatch import cmd_player
from dispatch import cmd_heropoint
from dispatch.tracking import track_message
from dispatch.bot_topic import handle_bot_topic_cmd
from dispatch.help_text import _HELP_TEXT
from dispatch.poll_router import handle_poll_answer, handle_poll_closed

cmd_info.init(_HELP_TEXT)

_HANDLERS = [
    cmd_info.handle, cmd_info_ext.handle, cmd_gm.handle,
    cmd_trackers.handle, cmd_trackers_items.handle,
    cmd_conditions_hp.handle, cmd_clocks.handle,
    cmd_votes_timers.handle, cmd_player.handle,
    cmd_heropoint.handle,
    _handle_markdone,
]

_READ_CMDS = frozenset({
    "/help", "/pbphelp", "/status", "/overview", "/campaign",
    "/mystats", "/me", "/myhistory", "/whosturn", "/combatlog",
    "/catchup", "/party", "/notes", "/quests", "/pins", "/lootlist",
    "/npcs", "/conditions", "/clocks", "/showvote", "/showtimer",
    "/summary", "/activity", "/profile", "/recap", "/gm",
    "/boons", "/boonsall", "/search", "/queue", "/reactions", "/timeline",
    "/waiting", "/session", "/health", "/queuestats", "/registry", "/markdone", "/roster",
    # Added 2026-08-14. The three other roster shapes were registered with
    # BotFather and handled in cmd_info, but were in neither this set nor
    # bot_topic's no_campaign set. Two consequences, both silent:
    # from the bot topic they fell through to "non-read commands not
    # allowed" and did nothing at all, and from a campaign topic they
    # replied into the in-character pbp thread instead of the chat topic.
    "/rostercampaigns", "/rosterplayers", "/rosterall",
})


def process_updates(updates: list, config: dict, state: dict) -> int:
    """Process Telegram updates. Returns new offset for next poll."""
    group_id = config["group_id"]
    maps = build_topic_maps(config)
    new_offset = state.get("offset", 0)

    for update in updates:
        update_id = update["update_id"]
        new_offset = max(new_offset, update_id + 1)
        msg = update.get("message")
        cb = update.get("callback_query")

        try:
            poll_answer = update.get("poll_answer")
            if poll_answer:
                handle_poll_answer(poll_answer, config, state)
                continue

            # poll update: sent when a poll closes (is_closed=True)
            poll_update = update.get("poll")
            if poll_update and poll_update.get("is_closed"):
                handle_poll_closed(poll_update, config, state)  # pragma: no cover
                continue  # pragma: no cover

            if cb:
                from boons.hero_point import process_hero_campaign_callback
                # Boon-selection callbacks were removed 2026-05-11; selection
                # moved to the website (see scripts/scheduled/potw.py). Old
                # POTW messages still in chat history have inline buttons
                # that, when tapped, produce callbacks the bot now ignores
                # silently. Hero-point callbacks are still handled.
                process_hero_campaign_callback(cb, config, state)
                continue

            if update.get("message_reaction"):
                from commands.reactions import process_reaction
                process_reaction(update, config, state, maps)
                continue

            if not msg:
                continue

            # Bot topic (main group only)
            bot_topic = config.get("bot_topic_id")
            msg_thread = msg.get("message_thread_id")
            msg_chat = msg.get("chat", {}).get("id")
            if (bot_topic and msg_thread == bot_topic and msg_chat == group_id):
                raw = msg.get("text", "")
                who = msg.get("from", {}).get("first_name", "?")
                print(f"Bot topic msg from {who}: {raw[:50]}")
                handle_bot_topic_cmd(msg, config, state, maps, group_id, bot_topic,
                                     _READ_CMDS, _HANDLERS)
                continue

            parsed = parse_message(msg, maps)
            if not parsed:
                continue

            pid = parsed["pid"]
            text = parsed["text"]
            user_id = parsed["user_id"]
            gm_ids = helpers.gm_ids_for_campaign(config, pid)
            cmd_word = text.split()[0] if text.startswith("/") else ""
            is_read = cmd_word in _READ_CMDS or (cmd_word == "/hp" and text.strip() == "/hp")
            msg_gid = maps.to_group.get(pid, group_id)

            ctx = {
                "pid": pid, "thread_id": parsed["thread_id"],
                "reply_topic": parsed["chat_topic_id"] if is_read else parsed["thread_id"],
                "user_id": user_id, "user_name": parsed["user_name"],
                "campaign_name": parsed["campaign_name"],
                "now_iso": parsed["now_iso"], "msg_time_iso": parsed["msg_time_iso"],
                "text": text, "cmd_word": cmd_word, "gm_ids": gm_ids,
                "group_id": msg_gid, "config": config, "state": state,
                "maps": maps, "parsed": parsed,
            }

            if cmd_word == "/chooseboon":
                # /chooseboon REMOVED 2026-05-11. Boon selection moved to
                # the website. See scripts/scheduled/potw.py for the new
                # flow. The branch is kept as a continue-no-op so the
                # router doesn't fall through to command dispatch for a
                # command we explicitly no longer support.
                continue

            if cmd_word:
                for handler in _HANDLERS:
                    if handler(ctx):
                        break

            handle_combat_message(
                text, parsed["raw_text"], user_id, parsed["user_name"],
                gm_ids, pid, parsed["campaign_name"],
                parsed["now_iso"], msg_gid, parsed["thread_id"], state,
            )
            track_message(parsed, state, config, gm_ids, maps)

        except Exception as e:  # pragma: no cover
            print(f"Error processing update {update_id}: {e}")  # pragma: no cover

    return new_offset
