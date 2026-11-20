"""🚪 When a player leaves, tell each campaign they actually play in, with its live player count (2026-11-20).

Lewis, 2026-11-20: "When a player leaves the server can the live player count be put into the campaigns chats that
player was a part of (not role wise, actual campaign roster wise)", then: only players who have posted in the
campaign, and leaving the Telegram group counts as well as leaving Discord.

"Plays in" is the bot's own roster: posted there in the last 30 days, or set permanent (roster_members). Somebody who
signed up and left before posting gets no notice anywhere. The count shown already leaves the leaver out.

One notice per person per 30 days, so leaving Discord and Telegram on the same day posts once.
"""
from datetime import datetime, timedelta, timezone

from commands.roster_members import _active_players, _split_active, effective_target

_QUIET_DAYS = 30


def played_in(config: dict, state: dict, uid: str, now: datetime) -> list[tuple[dict, list[dict]]]:
    """[(pair, active roster without the leaver)] for each campaign where uid is on the active roster."""
    out = []
    for pair in config.get("topic_pairs", []):
        if not pair.get("pbp_topic_ids"):
            continue
        active = _active_players(str(pair["pbp_topic_ids"][0]), state, config, now=now)
        if any(str(p.get("user_id")) == uid for p in active):
            out.append((pair, [p for p in active if str(p.get("user_id")) != uid]))
    return out


def notice(pair: dict, name: str, where: str, rest: list[dict], config: dict, state: dict) -> str:
    non_perm, perm = _split_active(rest, config)
    target = pair.get("roster_target") or effective_target(config, state)
    label = f"{pair['code']}: {pair['name']}" if pair.get("code") else pair.get("name", "")
    extra = f" +{len(perm)} perm" if perm else ""
    return f"🚪 {name} has left the Path Wars {where}.\n📋 {label} now has {len(non_perm)}/{target} players{extra}."


def announce_left(config: dict, state: dict, uid, name: str, where: str, now: datetime | None = None,
                  send=None) -> int:
    """Post the notice in each campaign's chat topic. Returns how many were posted."""
    now = now or datetime.now(timezone.utc)
    uid = str(uid)
    sent = state.setdefault("left_notices", {})
    last = sent.get(uid)
    if last and datetime.fromisoformat(last) > now - timedelta(days=_QUIET_DAYS):
        return 0
    if send is None:
        import telegram as tg
        send = tg.send_message
    posted = 0
    for pair, rest in played_in(config, state, uid, now):
        topic = pair.get("chat_topic_id")
        if not topic:
            continue
        if send(pair.get("group_id", config["group_id"]), topic, notice(pair, name, where, rest, config, state)):
            posted += 1
    if posted:
        sent[uid] = now.isoformat()
    print(f"left_notice: {name} left the {where}: {posted} campaign(s) told")
    return posted


def _display(user: dict) -> str:
    return " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or user.get("username") or "?"


def on_telegram_leave(update: dict, config: dict, state: dict, send=None) -> bool:
    """A chat_member update (bot is admin) or a left_chat_member service message. True when it was a leave."""
    groups = {config["group_id"]} | {p.get("group_id") for p in config.get("topic_pairs", []) if p.get("group_id")}
    cm = update.get("chat_member")
    if cm:
        if cm.get("chat", {}).get("id") not in groups:
            return False
        old, new = cm.get("old_chat_member", {}), cm.get("new_chat_member", {})
        if new.get("status") not in ("left", "kicked") or old.get("status") in ("left", "kicked"):
            return False
        user = new.get("user", {})
    else:
        msg = update.get("message") or {}
        user = msg.get("left_chat_member")
        if not user or msg.get("chat", {}).get("id") not in groups:
            return False
    if not user.get("is_bot"):
        announce_left(config, state, user.get("id"), _display(user), "Telegram group", send=send)
    return True
