"""Hero Point campaign picker — MVP of the Week award handler."""

import telegram as tg


def post_hero_point_picker(winner_uid: str, winner_name: str,
                            config: dict, state: dict) -> None:
    """Post campaign picker buttons for the MVP Hero Point award.

    Stores a pending entry in state['pending_hero_points'] keyed by uid.
    """
    group_id = config.get("group_id")
    leaderboard_topic = config.get("leaderboard_topic_id")
    if not group_id or not leaderboard_topic:
        return  # pragma: no cover

    # Find all campaigns the winner is currently active in
    campaigns = []
    seen_pids = set()
    for key, p in state.get("players", {}).items():
        if p.get("user_id") == winner_uid and not p.get("removed"):
            pid = str(p.get("pbp_topic_id", ""))
            if pid and pid not in seen_pids:
                seen_pids.add(pid)
                pair = next((pr for pr in config.get("topic_pairs", [])
                             if str(pr["pbp_topic_ids"][0]) == pid), None)
                if pair:
                    campaigns.append((pid, pair.get("name", pid)))

    if not campaigns:
        return  # pragma: no cover

    buttons = [
        {"text": name, "callback_data": f"herocampaign:{winner_uid}:{pid}"}
        for pid, name in sorted(campaigns, key=lambda x: x[1])
    ]

    state.setdefault("pending_hero_points", {})[winner_uid] = {
        "name": winner_name,
    }

    tg.send_message_with_buttons(
        group_id, leaderboard_topic,
        f"🎲 {winner_name} — which campaign gets the Hero Point?",
        buttons,
    )


def process_hero_campaign_callback(cb: dict, config: dict, state: dict) -> bool:
    """Handle herocampaign:uid:pid button tap. Returns True if handled."""
    parts = cb.get("data", "").split(":")
    if len(parts) != 3 or parts[0] != "herocampaign":
        return False
    uid, pid = parts[1], parts[2]
    if str(cb.get("from", {}).get("id", "")) != uid:
        return False
    pending = state.get("pending_hero_points", {}).get(uid)
    if not pending:
        return False
    name = pending.get("name", "Winner")
    pair = next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)
    campaign = pair.get("name", pid) if pair else pid
    msg = cb.get("message", {})
    tg.edit_message(msg.get("chat", {}).get("id"),
                    msg.get("message_id"),
                    f"🎲 {name} claimed their Hero Point for {campaign}!",
                    remove_keyboard=True)
    bot_topic = config.get("bot_topic_id")
    if bot_topic:
        tg.send_message(config["group_id"], bot_topic,
                        f"✅ +1 Hero Point for {campaign} — {name}")
    del state["pending_hero_points"][uid]
    print(f"Hero Point claimed by {name} for {campaign}")
    return True
