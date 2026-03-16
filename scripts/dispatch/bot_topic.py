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

    # Global commands don't need a campaign
    no_campaign = {"/gm", "/overview", "/boonsall", "/profile", "/help", "/pbphelp"}
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
