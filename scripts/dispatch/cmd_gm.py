"""
GM-only control commands: pause, resume, kick, addplayer, scene.
"""

import re
import telegram as tg
from players.management import handle_kick, handle_addplayer
from transcript.logger import write_scene_marker


def _arg(raw_text: str, cmd_len: int) -> str:
    """Extract argument from raw_text, stripping any @BotName suffix.

    e.g. '/scene@PathWarsNudgeBot The Docks' → 'The Docks'
    """
    # Strip @BotName appended by Telegram in group commands
    cleaned = re.sub(r"^(/\w+)@\S+", r"\1", raw_text)
    return cleaned[cmd_len:].strip()


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
            handle_kick(pid, name, target, state, gid, tid)
        return True

    if text.startswith("/addplayer"):
        raw_args = _arg(raw_text, 10)
        if not raw_args:
            tg.send_message(gid, tid,
                            "Usage: /addplayer @username PlayerName\n"
                            "e.g. /addplayer @alice Alice Smith")
        else:
            handle_addplayer(pid, name, raw_args, now_iso, state, gid, tid)
        return True

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
        from commands.timeline import add_event
        event_text = text[6:].strip() if len(text) > 6 else ""
        tg.send_message(gid, tid, add_event(pid, name, event_text, state))
        return True

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

    return False
