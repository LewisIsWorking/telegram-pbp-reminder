"""
GM-only control commands: pause, resume, kick, addplayer, scene.
"""

import telegram as tg
from players.management import handle_kick, handle_addplayer
from transcript.logger import write_scene_marker


def handle(ctx: dict) -> bool:
    """Handle GM control commands. Returns True if handled."""
    cmd = ctx["cmd_word"]
    text = ctx["text"]
    uid = ctx["user_id"]
    gm_ids = ctx["gm_ids"]
    pid = ctx["pid"]
    name = ctx["campaign_name"]
    state = ctx["state"]
    gid = ctx["group_id"]
    tid = ctx["thread_id"]
    now_iso = ctx["now_iso"]
    raw_text = ctx["parsed"]["raw_text"]

    if uid not in gm_ids:
        return False

    if text.startswith("/pause"):
        reason = raw_text[6:].strip() or "No reason given"
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
        target = raw_text[5:].strip().lstrip("@")
        if not target:
            tg.send_message(gid, tid,
                            "Usage: /kick @username or /kick PlayerName")
        else:
            handle_kick(pid, name, target, state, gid, tid)
        return True

    if text.startswith("/addplayer"):
        raw_args = raw_text[10:].strip()
        if not raw_args:
            tg.send_message(gid, tid,
                            "Usage: /addplayer @username PlayerName\n"
                            "e.g. /addplayer @alice Alice Smith")
        else:
            handle_addplayer(pid, name, raw_args, now_iso, state, gid, tid)
        return True

    if text.startswith("/scene"):
        scene_name = raw_text[6:].strip()
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
        from commands.timeline import add_event
        event_text = text[6:].strip() if len(text) > 6 else ""
        tg.send_message(gid, tid, add_event(pid, name, event_text, state))
        return True

    return False
