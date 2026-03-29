"""
Main update processing router.

Parses Telegram updates from all groups, dispatches commands, and
triggers post-message tracking. Handles poll_answer by poll_id so
votes from any group are routed to the correct campaign.
"""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps
from helpers_pkg.campaigns import get_code
from helpers_pkg.groups import group_id_for_campaign
from parsing.message import parse_message
from combat.tracker import handle_combat_message
from boons.handler import process_boon_callback

from dispatch import cmd_info, cmd_info_ext, cmd_gm, cmd_trackers, cmd_trackers_items
from dispatch import cmd_conditions_hp, cmd_clocks, cmd_votes_timers
from dispatch import cmd_player
from dispatch.tracking import track_message
from dispatch.bot_topic import handle_bot_topic_cmd
from dispatch.help_text import _HELP_TEXT
from dispatch.poll_notify import notify_vote
from scheduled.session_poll_build import votes_to_option_label

cmd_info.init(_HELP_TEXT)

_HANDLERS = [
    cmd_info.handle, cmd_info_ext.handle, cmd_gm.handle,
    cmd_trackers.handle, cmd_trackers_items.handle,
    cmd_conditions_hp.handle, cmd_clocks.handle,
    cmd_votes_timers.handle, cmd_player.handle,
]

_READ_CMDS = frozenset({
    "/help", "/pbphelp", "/status", "/overview", "/campaign",
    "/mystats", "/me", "/myhistory", "/whosturn", "/combatlog",
    "/catchup", "/party", "/notes", "/quests", "/pins", "/lootlist",
    "/npcs", "/conditions", "/clocks", "/dc", "/showvote", "/showtimer",
    "/summary", "/activity", "/profile", "/recap", "/gm",
    "/boons", "/boonsall", "/search", "/queue", "/reactions", "/timeline",
    "/waiting", "/session", "/health", "/queuestats", "/registry",
})


def _build_poll_id_map(state: dict) -> dict[str, str]:
    """Return {poll_id: campaign_code} from current session_poll state."""
    result = {}
    polls = state.get("session_poll", {})
    for code, slot in polls.items():
        pid = slot.get("poll_id", "")
        if pid:
            result[pid] = code
    return result


def _find_pair(config: dict, code: str) -> dict | None:
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return pair
    return None


def _handle_poll_answer(poll_answer: dict, config: dict, state: dict) -> None:
    """Record a poll vote and fire cross-campaign notifications."""
    uid = str(poll_answer.get("user", {}).get("id", ""))
    name = poll_answer.get("user", {}).get("first_name", "?")
    option_ids = poll_answer.get("option_ids", [])
    incoming_poll_id = poll_answer.get("poll_id", "")

    poll_id_map = _build_poll_id_map(state)
    code = poll_id_map.get(incoming_poll_id)
    if not code:
        return  # vote for an unrecognised poll

    polls = state.setdefault("session_poll", {})
    poll = polls.setdefault(code, {})
    voted = poll.setdefault("voted_uids", [])
    if uid and uid not in voted:
        voted.append(uid)

    votes = poll.setdefault("votes", {})
    # Remove previous votes from this user across all options
    for key in votes:
        votes[key] = [v for v in votes[key] if v != uid]
    # Record new vote(s) by option index string
    for idx in option_ids:
        votes.setdefault(str(idx), []).append(uid)

    # Cross-notification
    pair = _find_pair(config, code)
    pid = str(pair["pbp_topic_ids"][0]) if pair else None
    option_label = votes_to_option_label(option_ids, pair or {}, datetime.now(timezone.utc))
    if pid:
        notify_vote(config, state, name, option_label, pid)
    print(f"Poll vote: {name} ({code}) → option {option_ids}")


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
                _handle_poll_answer(poll_answer, config, state)
                continue

            if cb:
                process_boon_callback(cb, config, state)
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

        except Exception as e:
            print(f"Error processing update {update_id}: {e}")

    return new_offset
