"""
GM-only control commands: pause, resume, kick, addplayer, scene.
"""

import telegram as tg
from dispatch.gm_args import arg as _arg
from dispatch.gm_args import campaign_name as _campaign_name
from dispatch.gm_args import canonical_pid as _canonical_pid
from players.management import handle_kick, handle_addplayer
from transcript.logger import write_scene_marker


def handle(ctx: dict) -> bool:
    """Handle GM control commands. Returns True if handled."""
    uid = ctx["user_id"]
    gm_ids = ctx["gm_ids"]

    # ⛔ The authorisation gate comes FIRST. It used to sit below twelve
    # ctx lookups, one of which crashed (see below), so a non-GM could
    # take down the handler chain on a command they were not allowed to
    # run. Nothing above this line may touch ctx beyond these two keys.
    if uid not in gm_ids:
        return False

    cmd = ctx["cmd_word"]
    text = ctx["text"]
    state = ctx["state"]
    gid = ctx["group_id"]
    tid = ctx["thread_id"]
    now_iso = ctx["now_iso"]
    config = ctx["config"]

    # ⭐ Canonicalise ONCE, here, for every branch below. Four branches
    # used to do this by hand and seven did not, which is how /setproxy
    # inherited the wrong shape by being written next to one of them.
    # Why it matters and how far it actually reached (less far than I
    # first claimed): the module docstring of dispatch/gm_args.py.
    pid = _canonical_pid(ctx["pid"], config)
    name = _campaign_name(pid, config) or ctx["campaign_name"]

    # ⛔ A plain subscript, deliberately, and matching the six sibling
    # handlers that do the same. dispatch/bot_topic.py used to pass
    # `None` here and this line crashed `/markdone`; the fix belongs
    # there (see the long note on its ctx) rather than as an `or {}`
    # here, which would be defence no test could ever kill and would
    # leave the other six broken anyway.
    raw_text = ctx["parsed"]["raw_text"]

    if text.startswith("/pause"):
        reason = _arg(raw_text, 6) or "No reason given"
        state.setdefault("paused_campaigns", {})[pid] = {
            "paused_at": now_iso,
            "reason": reason,
        }
        tg.send_message(gid, tid,
                        f"\u23f8\ufe0f {name} paused. Inactivity tracking disabled.\nReason: {reason}")
        print(f"Paused {name}: {reason}")
        return True

    if text == "/resume":
        paused = state.get("paused_campaigns", {})
        if pid in paused:
            del paused[pid]
            tg.send_message(gid, tid,
                            f"\u25b6\ufe0f {name} resumed. Inactivity tracking re-enabled.")
            print(f"Resumed {name}")
        else:
            tg.send_message(gid, tid, f"{name} is not paused.")
        return True

    if text.startswith("/kick"):
        target = _arg(raw_text, 5).lstrip("@")
        if not target:
            tg.send_message(gid, tid,
                            "Usage: /kick @username or /kick PlayerName")
        else:
            handle_kick(pid, name, target, state, gid, tid, config)  # pragma: no cover
        return True

    if text.startswith("/addplayer"):
        raw_args = _arg(raw_text, 10)  # pragma: no cover
        if not raw_args:  # pragma: no cover
            tg.send_message(gid, tid,  # pragma: no cover
                            "Usage: /addplayer @username PlayerName\n"  # pragma: no cover
                            "e.g. /addplayer @alice Alice Smith")  # pragma: no cover
        else:  # pragma: no cover
            handle_addplayer(pid, name, raw_args, now_iso, state, gid, tid, config)  # pragma: no cover
        return True  # pragma: no cover

    if text.startswith("/scene"):
        scene_name = _arg(raw_text, 6)
        if not scene_name:
            tg.send_message(gid, tid,
                            "Usage: /scene <n>\ne.g. /scene The Docks at Midnight")
        else:
            state.setdefault("current_scenes", {})[pid] = scene_name
            write_scene_marker(name, scene_name)
            tg.send_message(gid, tid,
                            f"\U0001f3ad Scene: {scene_name}\nMarked in transcript.")
            print(f"Scene marker in {name}: {scene_name}")
        return True

    if cmd == "/event":
        from commands.timeline import add_event  # pragma: no cover
        event_text = text[6:].strip() if len(text) > 6 else ""  # pragma: no cover
        tg.send_message(gid, tid, add_event(pid, name, event_text, state))  # pragma: no cover
        return True  # pragma: no cover

    if text.startswith("/session set"):
        from commands.session import set_session
        num_str = text[12:].strip()
        try:
            num = int(num_str)
            tg.send_message(gid, tid, set_session(pid, name, num, state))
        except ValueError:
            tg.send_message(gid, tid, "Usage: /session set <number>")
        return True

    if text.startswith("/setchar"):
        args = text[8:].strip()
        if not args or " " not in args:
            tg.send_message(gid, tid, "Usage: /setchar @username CharacterName")
            return True
        parts = args.split(None, 1)
        target_username = parts[0].lstrip("@")
        char_name = parts[1]
        # Find user_id from username
        target_uid = None
        for key, p in state.get("players", {}).items():
            if p.get("username", "").lower() == target_username.lower():
                if p.get("pbp_topic_id") == pid:
                    target_uid = p.get("user_id")
                    break
        if not target_uid:
            tg.send_message(gid, tid,
                            f"Player @{target_username} not found in this campaign.")
            return True
        state.setdefault("characters", {}).setdefault(pid, {})[target_uid] = char_name
        tg.send_message(gid, tid,
                        f"✅ @{target_username} → {char_name}")
        return True

    if text.startswith("/setproxy") or text.startswith("/clearproxy"):
        from dispatch.cmd_proxy import handle_proxy
        return handle_proxy(text, raw_text, pid, name, state, gid, tid)

    if text.startswith("/setpermanent") or text.startswith("/unsetpermanent"):
        is_set = text.startswith("/setpermanent")
        cmd_len = 13 if is_set else 15
        target = _arg(raw_text, cmd_len).lstrip("@")
        if not target:
            tg.send_message(gid, tid,
                            "Usage: /setpermanent @username or /unsetpermanent @username")
            return True
        # `pid` is canonical from the top of handle(). This comparison
        # is why that matters: player records carry the campaign's FIRST
        # pbp topic in `pbp_topic_id`, so matching against a raw thread
        # id finds nothing and reports "Player not found" about a player
        # who is right there.
        matched = []
        for key, p in state.get("players", {}).items():
            if (p.get("username", "").lower() == target.lower()
                    and str(p.get("pbp_topic_id")) == pid):
                if is_set:
                    p["permanent"] = True
                else:
                    p.pop("permanent", None)
                matched.append(p.get("first_name", target))
        if matched:
            verb = "permanently rostered" if is_set else "removed from permanent roster"
            tg.send_message(gid, tid,
                            f"✅ {matched[0]} (@{target}) {verb} in {name}.")
            print(f"{verb}: {target} in {name}")
        else:
            tg.send_message(gid, tid,
                            f"Player @{target} not found in {name}.")
        return True

    return False
