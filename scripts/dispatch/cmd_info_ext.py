"""Extended info commands: queue, health, session, waiting, reactions, timeline."""

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

    if cmd == "/registry":
        from commands.player_registry import build_registry
        tg.send_message(gid, reply, build_registry(pid, name, config, state))
        return True

    return False
