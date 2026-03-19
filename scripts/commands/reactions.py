"""
Reaction tracking for PBP engagement.

Tracks emoji reactions on messages to measure player engagement.
Stores: reactions given (per user), reactions received (per user),
and emoji frequency (per campaign).
"""

from datetime import datetime, timezone

import helpers


def process_reaction(update: dict, config: dict, state: dict, maps) -> None:
    """Process a message_reaction update from Telegram."""
    reaction = update.get("message_reaction", {})
    if not reaction:
        return

    chat_id = reaction.get("chat", {}).get("id")
    if chat_id != config["group_id"]:
        return

    # Find which campaign this reaction is in
    # Reactions don't have message_thread_id, but we can match via
    # the gm_queue or transcript data. For now, skip thread matching
    # and just track globally — we can't reliably determine the topic
    # from a reaction update alone.
    #
    # UPDATE: Telegram DOES include message_thread_id in reactions
    # for forum topics (added in Bot API 7.0+).
    thread_id = str(reaction.get("message_thread_id", ""))
    if not thread_id or thread_id not in maps.all_pbp_ids:
        return

    pid = maps.to_canonical[thread_id]

    user = reaction.get("user", {})
    if not user or user.get("is_bot", False):
        return

    reactor_id = str(user.get("id", ""))
    reactor_name = user.get("first_name", "Someone")

    old_emojis = {r.get("emoji", "") for r in reaction.get("old_reaction", [])
                  if r.get("type") == "emoji"}
    new_emojis = {r.get("emoji", "") for r in reaction.get("new_reaction", [])
                  if r.get("type") == "emoji"}

    added = new_emojis - old_emojis
    removed = old_emojis - new_emojis

    if not added and not removed:
        return

    reactions = state.setdefault("reactions", {}).setdefault(pid, {})
    given = reactions.setdefault("given", {})
    emojis = reactions.setdefault("emojis", {})

    # Track reactions given by this user
    user_given = given.setdefault(reactor_id, {
        "name": reactor_name, "count": 0,
    })
    user_given["name"] = reactor_name
    user_given["count"] += len(added) - len(removed)
    if user_given["count"] < 0:
        user_given["count"] = 0

    # Track emoji frequency
    for emoji in added:
        emojis[emoji] = emojis.get(emoji, 0) + 1
    for emoji in removed:
        emojis[emoji] = max(0, emojis.get(emoji, 0) - 1)


def build_reactions(config: dict, state: dict, pid: str,
                    campaign_name: str) -> str:
    """Build /reactions output for a campaign."""
    reactions = state.get("reactions", {}).get(pid, {})
    given = reactions.get("given", {})
    emojis = reactions.get("emojis", {})

    if not given and not emojis:
        return f"No reactions tracked yet in {campaign_name}."

    lines = [f"💬 Reactions in {campaign_name}:\n"]

    # Top reactors
    if given:
        sorted_givers = sorted(given.items(), key=lambda x: -x[1]["count"])[:10]
        lines.append("Top reactors:")
        for i, (uid, data) in enumerate(sorted_givers):
            icon = helpers.rank_icon(i)
            lines.append(f"{icon} {data['name']}: {data['count']} reactions")
        lines.append("")

    # Popular emojis
    if emojis:
        sorted_emojis = sorted(emojis.items(), key=lambda x: -x[1])[:10]
        emoji_str = "  ".join(f"{e} x{c}" for e, c in sorted_emojis if c > 0)
        if emoji_str:
            lines.append(f"Popular: {emoji_str}")

    return "\n".join(lines)
