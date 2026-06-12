"""
Bot topic command handler.

Processes read-only commands sent from the dedicated bot topic,
resolving the campaign from a text argument instead of topic context.
"""

import re
from datetime import datetime, timezone

import helpers
import telegram as tg
from dispatch.cmd_search import handle_search
from dispatch.gm_poll_cmds import handle_sessionplayed, handle_swimmingdone, poll_week_num as _poll_week_num


def _poll_week_num(week_iso: str) -> int:
    """Extract ISO week number from a week_iso string like 'sun2026-03-29'."""
    try:  # pragma: no cover
        date_part = week_iso.lstrip("sun").lstrip("sat")  # pragma: no cover
        return datetime.strptime(date_part, "%Y-%m-%d").isocalendar()[1]  # pragma: no cover
    except (ValueError, AttributeError):  # pragma: no cover
        return 0  # pragma: no cover


def resolve_campaign(args: str, maps) -> tuple[str | None, str | None]:
    """Resolve a campaign name/keyword to (pid, campaign_name) or (None, None)."""
    key = args.strip().lower()
    if not key:
        return None, None
    pid = maps.name_to_pid.get(key)
    if pid:
        return pid, maps.to_name[pid]
    for name, p in maps.name_to_pid.items():
        if name.startswith(key):
            return p, maps.to_name[p]
    return None, None


def handle_bot_topic_cmd(msg: dict, config: dict, state: dict,
                         maps, group_id: int, bot_topic: int,
                         read_cmds: frozenset, handlers: list) -> None:
    """Handle a command sent from the bot topic. Read-only, campaign arg required."""
    from_user = msg.get("from", {})
    if from_user.get("is_bot", False):
        return

    raw_text = msg.get("text", "").strip()
    text = re.sub(r"^(/\w+)@\S+", r"\1", raw_text.lower())
    if not text.startswith("/"):
        return

    parts = text.split(None, 1)
    cmd_word = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    user_id = str(from_user.get("id", ""))
    user_name = from_user.get("first_name", "Someone")
    now_iso = datetime.now(timezone.utc).isoformat()

    # /search works without campaign context
    if cmd_word == "/search":
        print(f"Bot topic: /search from {user_name}: {args}")
        handle_search(args, group_id, bot_topic, tg)
        return

    # /heropoint — MVP claims their Hero Point by campaign name/code. Not a
    # read command (it mutates pending_hero_points), so it gets its own branch
    # here rather than falling through to the read-only dispatch below.
    if cmd_word == "/heropoint":
        from dispatch.cmd_heropoint import handle_bot_topic as _hp_bot
        print(f"Bot topic: /heropoint from {user_name}: {args}")
        _hp_bot(args, user_id, user_name, config, state, group_id, bot_topic)
        return

    # /chooseboon REMOVED 2026-05-11. Boon selection moved to
    # the website. See scripts/scheduled/potw.py for the new flow.

    # /mystats and /me: cross-campaign when no arg, per-campaign with arg
    if cmd_word in ("/mystats", "/me"):
        if not args.strip():
            from commands.player import build_mystats_all
            tg.send_message(group_id, bot_topic,
                            build_mystats_all(user_id, user_name, config, state))
            return
        # With campaign arg, fall through to normal handler below

    # /waiting: cross-campaign when no arg
    if cmd_word == "/waiting":
        if not args.strip():
            from commands.waiting import build_waiting_all
            tg.send_message(group_id, bot_topic,
                            build_waiting_all(user_id, user_name, config, state))
            return
        # With campaign arg, fall through to normal handler below

    # /roll and /dc work without campaign context
    if cmd_word in ("/roll", "/dc"):
        print(f"Bot topic: {cmd_word} from {user_name}: {args}")
        pid = next(iter(maps.to_name), None)
        if not pid:
            return  # pragma: no cover
        import re as _re
        raw_text = msg.get("text", "").strip()
        if cmd_word == "/roll":
            dice = _re.sub(r"^/roll(@\S+)?", "", raw_text).strip()
            result = helpers.roll_dice(dice) if dice else None
            if not result or not dice:
                tg.send_message(group_id, bot_topic,
                                "Usage: /roll [dice] [label]\n"
                                "e.g. /roll 1d20+5 Stealth\n"
                                "e.g. /roll 4d6kh3")
            elif result.get("error"):
                tg.send_message(group_id, bot_topic, result["error"])
            else:
                label = result["label"]
                header = f"🎲 {user_name}"
                if label:
                    header += f" — {label}"
                header += ":"
                r = result["results"][0]
                tg.send_message(group_id, bot_topic,
                                f"{header}\n  {r['detail']} = {r['total']}")
        else:
            mention = f"@{user_name}" if user_name else user_name
            tg.send_message(group_id, bot_topic,
                            f"The DC is a mystery to be revealed later in the campaign! {mention}")
        return

    # /sessionplayed <code> <week> — GM marks a live session as happened, stops poll pings
    if cmd_word == "/sessionplayed":
        return handle_sessionplayed(  # pragma: no cover
            args, user_id, user_name, config, state, group_id, bot_topic)  # pragma: no cover

    if cmd_word == "/swimmingdone":  # pragma: no cover
        return handle_swimmingdone(  # pragma: no cover
            args, user_id, user_name, config, state, group_id, bot_topic)  # pragma: no cover

    # Global commands don't need a campaign
    no_campaign = {"/gm", "/overview", "/boonsall", "/profile", "/help", "/pbphelp", "/queue", "/timeline", "/health", "/queuestats", "/roster"}
    if cmd_word in no_campaign:
        print(f"Bot topic: {cmd_word} from {user_name} (global)")
        pid = next(iter(maps.to_name), None)
        if not pid:
            return
        campaign_name = maps.to_name[pid]
    elif cmd_word in read_cmds:
        pid, campaign_name = resolve_campaign(args, maps)
        if not pid:
            names = ", ".join(sorted(maps.to_name.values()))
            tg.send_message(group_id, bot_topic,
                            f"Specify a campaign: {cmd_word} <name>\n\nCampaigns: {names}")
            return
        # Strip campaign name from args for commands that use remaining text
        for word in campaign_name.lower().split():
            args = args.replace(word, "", 1).strip()
        text = f"{cmd_word} {args}".strip() if args else cmd_word
    else:
        return  # Non-read commands not allowed from bot topic

    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    ctx = {
        "pid": pid,
        "thread_id": bot_topic,
        "reply_topic": bot_topic,
        "user_id": user_id,
        "user_name": user_name,
        "campaign_name": campaign_name,
        "now_iso": now_iso,
        "msg_time_iso": now_iso,
        "text": text,
        "cmd_word": cmd_word,
        "gm_ids": gm_ids,
        "group_id": group_id,
        "config": config,
        "state": state,
        "maps": maps,
        "parsed": None,
    }

    for handler in handlers:
        if handler(ctx):
            break
