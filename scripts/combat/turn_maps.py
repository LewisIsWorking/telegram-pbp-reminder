"""🗺️ The battle map after each player's combat turn, as that player's token sees it (2026-11-18).

Lewis: post a map "as each player ends their turn in combat", showing "What the player's token can see", not the
whole party's view. Foundry says who has acted (the encounter sync, combat/foundry_sync.py), so an ally newly marked
as acted gets one map from their own token, through /map's drawing (combat/map_view.post_map, quiet: a fight with no
map posts nothing).

``state["combat_maps"][pid]`` remembers, per encounter and round, whose map was posted, so each ally gets one per
round. The first time an encounter is seen, the allies who already acted are only remembered: a bot that comes back
mid-fight must not post a burst of old turns. ⚠️ The sync runs every 30 minutes, so a map comes up to 30 minutes after
the turn.
"""


def due_maps(state: dict, pid: str, snapshot: dict) -> list[str]:
    """Names of the allies whose turn ended since the last look, recording them as mapped."""
    encounter, rnd = snapshot.get("encounterId"), int(snapshot.get("round") or 0)
    acted = [a for a in snapshot.get("allies") or [] if a.get("acted") and a.get("telegramUserId") and a.get("name")]
    record = state.setdefault("combat_maps", {}).get(pid)
    first_look = record is None or record.get("encounter") != encounter
    if first_look or record.get("round") != rnd:
        record = state["combat_maps"][pid] = {"encounter": encounter, "round": rnd, "done": []}
    due = [a for a in acted if a["telegramUserId"] not in record["done"]]
    record["done"] += [a["telegramUserId"] for a in due]
    return [] if first_look else [a["name"] for a in due]


def post_turn_maps(config: dict, state: dict, encounters: list, post=None) -> int:
    """Posts each due turn-end map to its campaign's combat topic. Returns how many were posted."""
    import helpers
    if post is None:
        from combat.map_view import post_map as post
    posted = 0
    for stored in encounters:
        snapshot = stored.get("snapshot") or {}
        code = str(stored.get("code", ""))
        pair = next((p for p in config.get("topic_pairs", []) if str(p.get("code", "")).upper() == code.upper()), None)
        if not pair or not pair.get("pbp_topic_ids") or not pair.get("combat_topic_id") or snapshot.get("ended"):
            continue
        pid = str(pair["pbp_topic_ids"][0])
        if not helpers.feature_enabled(config, pid, "combat"):
            continue
        for name in due_maps(state, pid, snapshot):
            group_id = pair.get("group_id", config["group_id"])
            posted += bool(post(config, pid, code, name, group_id, pair["combat_topic_id"], quiet=True))
    return posted
