"""/extrasheet: one more character sheet in a campaign, two at most.

Added 2026-10-12. Lewis: *"Telegram users could also do it to give
themselves 1 additional sheet (maximum 2 in total)"*, and the GM can give
one to a player. Instant, no approval: the one-grant cap is the limit.

    /extrasheet               a player, in a campaign's topic or its chat
    /extrasheet C06           the same, naming the campaign (any topic)
    /extrasheet @user C06     the GM, for that player
    /extrasheet C06 (reply)   the GM, for the author of the replied message

The grant goes to data/state/extra_sheets.json (players/extra_sheets.py),
which ComeOnOverUno reads and passes to Tongs in the Foundry world.

⚠️ Two entry points. ``handle`` serves the pbp topics through _HANDLERS.
``handle_outside`` serves everywhere else in the group (a campaign's chat
topic, the bot topic), which never reaches _HANDLERS because
parse_message drops every thread that is not a pbp topic. Without it the
chat topic, where a player would naturally ask, silently did nothing.
"""

import re
from datetime import datetime, timezone

import helpers
import telegram as tg
from dispatch.campaign_lookup import resolve_campaign
from parsing.message import reply_user
from players import extra_sheets

NOT_IN_TOPIC = ("Send /extrasheet in your campaign's topic or its chat, "
                "or name the campaign: /extrasheet C06")
NOT_GM = ("Only the GM can give someone else an extra sheet. To get your "
          "own, send /extrasheet in your campaign's topic.")
FROM_A_BOT = ("That message is from a bot. Reply to the player's own "
              "message, or use /extrasheet @username {code}")


def command_args(text: str) -> str | None:
    """The text after /extrasheet (or /extrasheet@Bot), None for any other."""
    cleaned = re.sub(r"^(/\w+)@\S+", r"\1", (text or "").strip().lower())
    parts = cleaned.split(None, 1)
    if not parts or parts[0] != "/extrasheet":
        return None
    return parts[1] if len(parts) > 1 else ""


def _pair(pid: str, config: dict) -> dict | None:
    return next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)


def _campaign(words: list, topic_pid, config: dict, maps):
    """(topic pair, error reply). The typed code or name wins over the topic."""
    if not words:
        return (_pair(topic_pid, config), None) if topic_pid else (None, NOT_IN_TOPIC)
    key = " ".join(words)
    pair = next((p for p in config.get("topic_pairs", [])
                 if str(p.get("code", "")).lower() == key), None)
    if pair is None:
        pid = resolve_campaign(key, maps)[0]
        pair = _pair(pid, config) if pid else None
    if pair is None:
        codes = ", ".join(sorted(f"{p['code']} {p['name']}" for p in
                                 config.get("topic_pairs", []) if p.get("code")))
        return None, f"I don't know a campaign called \"{key}\".\nCampaigns: {codes}"
    return pair, None


def _gm_ids(config: dict, pid: str) -> set:
    """The campaign's GMs, the global GMs, and config's single gm_user_id."""
    ids = helpers.gm_ids_for_campaign(config, pid) | helpers.gm_id_set(config)
    if config.get("gm_user_id"):
        ids.add(str(config["gm_user_id"]))
    return ids


def _by_username(username: str, pid: str, state: dict):
    """(user_id, name) for an @username, from the bot's own player records.

    Their record in this campaign first, then any campaign, then the people
    seen posting elsewhere in the group. ``pending_<name>`` placeholders from
    /addplayer are skipped: that is not a Telegram id COO could match.
    """
    key = username.lower()
    hits = sorted((p for p in state.get("players", {}).values()
                   if str(p.get("username", "")).lower() == key
                   and str(p.get("user_id", "")).isdigit()),
                  key=lambda p: str(p.get("pbp_topic_id")) != pid)
    if hits:
        return str(hits[0]["user_id"]), hits[0].get("first_name") or username
    for uid, member in state.get("group_members", {}).items():
        if str(member.get("username", "")).lower() == key:
            return str(uid), member.get("name") or username
    return None, None


def _target(names: list, replied: dict, code: str, pid: str, state: dict):
    """(user_id, name, error reply) for the player the GM means."""
    if names:
        uid, name = _by_username(names[0], pid, state)
        if not uid:
            return None, None, (f"I don't know @{names[0]}. They need to have "
                                f"posted in the group once, or reply to one "
                                f"of their messages with /extrasheet {code}")
        return uid, name, None
    if replied.get("is_bot"):
        return None, None, FROM_A_BOT.format(code=code)
    uid = str(replied.get("id", ""))
    return uid, replied.get("first_name") or replied.get("username") or uid, None


def reply_for(caller_id: str, caller_name: str, args: str, topic_pid,
              replied, config: dict, state: dict, maps,
              now: str | None = None) -> str:
    """Grant the extra sheet if allowed and return what to tell the group."""
    words = args.lower().split()
    names = [w.lstrip("@") for w in words if w.startswith("@") and len(w) > 1]
    pair, error = _campaign([w for w in words if not w.startswith("@")],
                            topic_pid, config, maps)
    if error:
        return error
    code = str(pair.get("code", "")).upper()
    if not code:
        return (f"{pair['name']} has no campaign code in config.json, so it "
                f"cannot have extra sheets yet.")
    pid = str(pair["pbp_topic_ids"][0])
    is_gm = caller_id in _gm_ids(config, pid)
    if names or (is_gm and replied):
        if not is_gm:
            return NOT_GM
        target_id, target_name, error = _target(names, replied, code, pid, state)
        if error:
            return error
    else:
        target_id, target_name = caller_id, caller_name
    at = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not extra_sheets.grant(target_id, code, caller_id, at):
        return (f"{target_name} already has their extra sheet in {code} "
                f"(2 sheets is the most).")
    print(f"Extra sheet: {target_name} ({target_id}) in {code}, by {caller_id}")
    return (f"✅ {target_name} can make a second character sheet in {code}. "
            f"Open the world and Tongs will offer it.")


def handle(ctx: dict) -> bool:
    """/extrasheet typed in a campaign's pbp topic (registered in _HANDLERS)."""
    args = command_args(ctx["text"])
    if args is None:
        return False
    text = reply_for(ctx["user_id"], ctx["user_name"], args, ctx["pid"],
                     ctx["parsed"].get("reply_to_user"), ctx["config"],
                     ctx["state"], ctx["maps"])
    tg.send_message(ctx["group_id"], ctx["reply_topic"], text)
    return True


def handle_outside(msg: dict, config: dict, state: dict, maps) -> bool:
    """/extrasheet anywhere in the group but a pbp topic. True when handled.

    A campaign's chat topic still names the campaign; the bot topic and the
    rest of the group do not, so there the campaign must be typed.
    """
    sender = msg.get("from") or {}
    args = command_args(msg.get("text"))
    if args is None or not sender.get("id") or sender.get("is_bot"):
        return False
    chat = msg.get("chat", {}).get("id")
    thread = msg.get("message_thread_id")
    if chat not in {config.get("group_id"), *maps.to_group.values()}:
        return False
    if str(thread) in maps.all_pbp_ids:
        return False  # parse_message and handle() own the pbp topics
    pid = maps.to_canonical.get(str(thread))
    if pid and maps.to_group.get(pid) != chat:
        pid = None
    text = reply_for(str(sender["id"]), sender.get("first_name") or "Someone",
                     args, pid, reply_user(msg), config, state, maps)
    tg.send_message(chat, thread, text)
    return True
