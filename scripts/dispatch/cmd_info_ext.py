"""Extended info commands: queue, health, session, waiting, reactions, timeline."""

import re

import telegram as tg


def handle(ctx: dict) -> bool:
    """Handle newer read-only commands. Returns True if handled."""
    cmd = ctx["cmd_word"]
    gid = ctx["group_id"]
    reply = ctx["reply_topic"]
    pid = ctx["pid"]
    name = ctx["campaign_name"]
    uid = ctx["user_id"]
    user_name = ctx["user_name"]
    state = ctx["state"]
    config = ctx["config"]
    gm_ids = ctx["gm_ids"]

    if cmd == "/waiting":
        from commands.waiting import build_waiting
        tg.send_message(gid, reply, build_waiting(uid, user_name, pid, name, config, state))
        return True

    if cmd == "/session":
        from commands.session import build_session
        tg.send_message(gid, reply, build_session(pid, name, state, config))
        return True

    if cmd == "/health":
        from commands.health import build_health
        tg.send_message(gid, reply, build_health(config, state))
        return True

    if cmd == "/queuestats":
        from commands.queue_stats import build_queue_stats
        state.setdefault("_config_cache", config)
        tg.send_message(gid, reply, build_queue_stats(config, state))
        return True

    # Recruitment venue rotation, added 2026-08-20.
    if cmd in ("/recruitads", "/recruityield"):
        from commands.recruit_ads import (build_recruit_ads,
                                          build_recruit_yield)
        body = (build_recruit_ads(config, state) if cmd == "/recruitads"
                else build_recruit_yield(state))
        tg.send_message(gid, reply, body)
        return True

    # The two write commands are GM-only: they move the yield figures that
    # decide where the next hour of effort goes, so a wrong credit quietly
    # steers the whole search.
    if cmd in ("/recruitposted", "/recruitjoined"):
        from dispatch.cmd_recruit import handle_recruit_write
        handle_recruit_write(cmd, ctx, gm_ids)
        return True

    if cmd == "/reactions":
        from commands.reactions import build_reactions
        tg.send_message(gid, reply, build_reactions(config, state, pid, name))
        return True

    if cmd == "/timeline":
        from commands.timeline import build_timeline
        tg.send_message(gid, reply, build_timeline(config, state))
        return True

    if cmd == "/search":
        from dispatch.cmd_search import handle_search
        text = ctx["text"]
        query = text[7:].strip() if len(text) > 7 else ""
        handle_search(query, gid, reply, tg)
        return True

    # 🗺️ The battle map from Foundry (2026-11-18), always ONE character's view (Lewis: "You should never see the
    #    party's view with these commands"). "/map Zerius" is Zerius's; a plain /map is the caller's own character.
    if cmd == "/map":
        from combat.map_view import post_map, whose_map
        pair = next((p for p in config.get("topic_pairs", []) if str(p["pbp_topic_ids"][0]) == pid), {})
        # 2026-11-25: "/map@PathWarsBot Zerius" (Telegram adds the bot's name in a group with several bots) read
        #    "@PathWarsBot Zerius" as the name; the command word is cut off whole now, as /roll does.
        args = re.sub(r"^/map(@\S+)?", "", ctx["parsed"].get("raw_text") or ctx["text"], flags=re.I)
        # 🧭 2026-11-25: a GM's "/map Zerius slide S4, Little Dread S4" previews the moves, sent to that GM only.
        from combat.map_moves import looks_like_moves, parse_moves
        is_gm = str(uid) in {str(g) for g in gm_ids or []}
        moves = parse_moves(args) if is_gm else None
        if moves:
            from combat.map_move_post import post_move_map
            post_move_map(pair.get("code", ""), moves, uid, gid, reply)
            return True
        if is_gm and looks_like_moves(args):
            # A move list the GM mistyped must not land in the group as "Zerius slide 4 S has no token" (a plan
            # the players should not see): the GM is told privately how to write it.
            from combat.map_move_post import tell_gm_privately
            tell_gm_privately(uid, gid, reply, "🗺️ I could not read that move list. Write each move as name, "
                              "direction, distance, split by commas: /map Zerius slide S4, Little Dread E 10 ft")
            return True
        wanted, refusal = whose_map(config, state, pid, uid, gm_ids, args)
        if refusal:
            tg.send_message(gid, reply, refusal)
        else:
            post_map(config, pid, pair.get("code", ""), wanted, gid, reply)
        return True

    if cmd == "/registry":
        from commands.player_registry import build_registry
        tg.send_message(gid, reply, build_registry(pid, name, config, state))
        return True

    return False
