"""
GM-only control commands: pause, resume, kick, addplayer, scene.
"""

import re
import telegram as tg
from players.management import handle_kick, handle_addplayer
from transcript.logger import write_scene_marker



def _canonical_pid(pid: str, config: dict) -> str:
    """Return the primary pbp_topic_id for the campaign containing pid."""
    for pair in config.get("topic_pairs", []):
        all_pids = [str(t) for t in pair.get("pbp_topic_ids", [])]
        chat = str(pair.get("chat_topic_id", ""))
        if pid in all_pids or pid == chat:
            return str(pair["pbp_topic_ids"][0])
    return pid


def _campaign_name(pid: str, config: dict) -> str:
    """Return campaign name for a given primary pid."""
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return pair.get("name", "")
    return ""


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
    config = ctx["config"]

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
            kick_pid = _canonical_pid(pid, config)
            kick_name = _campaign_name(kick_pid, config) or name
            handle_kick(kick_pid, kick_name, target, state, gid, tid, config)  # pragma: no cover
        return True

    if text.startswith("/addplayer"):
        raw_args = _arg(raw_text, 10)  # pragma: no cover
        if not raw_args:  # pragma: no cover
            tg.send_message(gid, tid,  # pragma: no cover
                            "Usage: /addplayer @username PlayerName\n"  # pragma: no cover
                            "e.g. /addplayer @alice Alice Smith")  # pragma: no cover
        else:  # pragma: no cover
            add_pid = _canonical_pid(pid, config)  # pragma: no cover
            add_name = _campaign_name(add_pid, config) or name  # pragma: no cover
            handle_addplayer(add_pid, add_name, raw_args, now_iso, state, gid, tid, config)  # pragma: no cover
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

    if text.startswith("/setpermanent") or text.startswith("/unsetpermanent"):
        is_set = text.startswith("/setpermanent")
        cmd_len = 13 if is_set else 15
        target = _arg(raw_text, cmd_len).lstrip("@")
        if not target:
            tg.send_message(gid, tid,
                            "Usage: /setpermanent @username or /unsetpermanent @username")
            return True
        matched = []
        for key, p in state.get("players", {}).items():
            if (p.get("username", "").lower() == target.lower()
                    and p.get("pbp_topic_id") == pid):
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
