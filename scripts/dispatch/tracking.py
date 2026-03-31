"""Post-message state tracking: topics, counts, timestamps, roster, transcripts."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from transcript.logger import append_to_transcript
from commands import queue_io

def track_message(parsed: dict, state: dict, config: dict,
                  gm_ids: set, maps) -> None:
    """Update all tracking state for a processed message."""
    pid = parsed["pid"]
    user_id = parsed["user_id"]
    user_name = parsed["user_name"]
    campaign_name = parsed["campaign_name"]
    msg_time_iso = parsed["msg_time_iso"]
    text = parsed["text"]
    group_id = config["group_id"]

    # Topic-level tracking (for 4-hour alerts)
    state["topics"][pid] = {
        "last_message_time": msg_time_iso,
        "last_user": user_name,
        "last_user_id": user_id,
        "campaign_name": campaign_name,
    }

    # Message count
    user_counts = state["message_counts"].setdefault(pid, {})
    user_counts[user_id] = user_counts.get(user_id, 0) + 1

    # Word count
    raw_text = parsed["raw_text"] or ""
    word_count = len(raw_text.split()) if raw_text.strip() else 0
    user_words = state.setdefault("word_counts", {}).setdefault(pid, {})
    user_words[user_id] = user_words.get(user_id, 0) + word_count

    # Post timestamps (for POTW gap calculation)
    state["post_timestamps"].setdefault(pid, {}).setdefault(user_id, []).append(msg_time_iso)

    # Activity patterns (persistent hour/day counters)
    msg_dt = datetime.fromisoformat(msg_time_iso)
    hour_key = str(msg_dt.hour)
    day_key = str(msg_dt.weekday())
    user_hours = state.setdefault("activity_hours", {}).setdefault(pid, {}).setdefault(user_id, {})
    user_hours[hour_key] = user_hours.get(hour_key, 0) + 1
    user_days = state.setdefault("activity_days", {}).setdefault(pid, {}).setdefault(user_id, {})
    user_days[day_key] = user_days.get(day_key, 0) + 1

    # Player-level tracking (skip GM)
    if user_id and user_id not in gm_ids:
        _track_player(parsed, state, config, gm_ids, maps)
        # Add to GM reply queue (non-command player posts need a GM reply)
        if not text.startswith("/"):
            msg_id = parsed.get("message_id")
            media_group_id = parsed.get("media_group_id")
            if msg_id:
                cq = queue_io.load(pid)
                existing_ids = {e["message_id"] for e in cq.get("unreplied", [])}
                # Skip if same media group already queued (multi-image message)
                existing_groups = {e.get("media_group_id") for e in cq.get("unreplied", [])
                                   if e.get("media_group_id")}
                if msg_id not in existing_ids and (
                        not media_group_id or media_group_id not in existing_groups):
                    cq.setdefault("unreplied", []).append({
                        "message_id": msg_id,
                        "thread_id": parsed["thread_id"],
                        "user_id": user_id,
                        "user_name": user_name,
                        "time": msg_time_iso,
                        "preview": (parsed["raw_text"] or "[media]")[:500],
                        "media_group_id": media_group_id,
                    })
                    queue_io.save(pid, cq)
    else:
        # GM replied to a specific message — mark it cleared
        if not text.startswith("/"):
            reply_to = parsed.get("reply_to_message_id")
            if reply_to:
                cq = queue_io.load(pid)
                replied = cq.get("replied", [])

                mid_key = f"msg:{reply_to}"
                ts_key = None

                # Try to get timestamp from campaign queue
                replied_entry = {}
                unreplied = cq.get("unreplied", [])
                for e in unreplied:
                    if e["message_id"] == reply_to:
                        replied_entry = e
                        ts = e.get("time", "")[:19].replace("T", " ")
                        ts_key = ts if ts else None
                        break
                else:
                    reply_date = parsed.get("reply_to_date")
                    if reply_date:
                        ts_key = datetime.fromtimestamp(
                            reply_date, tz=timezone.utc
                        ).strftime("%Y-%m-%d %H:%M:%S")

                log_entry = {
                    "t":       msg_time_iso,
                    "pid":     pid,
                    "msg_id":  str(reply_to),
                    "player":  replied_entry.get("user_name", "?"),
                    "preview": replied_entry.get("preview", "")[:80],
                    "via":     "reply",
                }
                queue_io.mark_replied(pid, mid_key, ts_key, log_entry)

                from commands.queue_stats import record_reply
                record_reply(pid, state,
                             replied_entry.get("preview", ""),
                             replied_entry.get("user_name", ""))

    # Log to persistent PBP transcript
    if not text.startswith("/"):
        append_to_transcript(parsed, gm_ids, config)
        # Auto-increment session counter on new GM posting day
        from commands.session import track_session
        track_session(pid, user_id, gm_ids, msg_time_iso, state)
        # Register player with permanent campaign ID
        from commands.player_registry import get_or_assign_id
        get_or_assign_id(pid, user_id, user_name, user_id in gm_ids, state)
    print(f"Tracked message in {campaign_name} from {user_name}")

def _track_player(parsed: dict, state: dict, config: dict,
                  gm_ids: set, maps) -> None:
    """Update player roster, handle away auto-clear and rejoin notifications."""
    pid = parsed["pid"]
    user_id = parsed["user_id"]
    user_name = parsed["user_name"]
    campaign_name = parsed["campaign_name"]
    msg_time_iso = parsed["msg_time_iso"]
    text = parsed["text"]
    group_id = config["group_id"]

    # Auto-clear away when player posts (non-command)
    if not text.startswith("/"):
        away_key = f"{pid}:{user_id}"
        if away_key in state.get("away", {}):
            del state["away"][away_key]
            print(f"Auto-cleared away for {user_name} in {campaign_name} (posted)")

    player_key = f"{pid}:{user_id}"
    was_removed = player_key in state["removed_players"]
    old_player = state.get("players", {}).get(player_key, {})
    old_warn_level = old_player.get("last_warned_week", 0)

    state["players"][player_key] = {
        "user_id": user_id,
        "first_name": user_name,
        "last_name": parsed["user_last_name"],
        "username": parsed["username"],
        "campaign_name": campaign_name,
        "pbp_topic_id": pid,
        "last_post_time": msg_time_iso,
        "last_warned_week": 0,
    }

    if was_removed:
        removed_data = state["removed_players"].pop(player_key)
        print(f"Player {user_name} rejoined {campaign_name}")
        chat_tid = maps.to_chat.get(pid)
        if chat_tid:
            char = helpers.character_name(config, pid, user_id)
            uname = parsed.get("username", "") or removed_data.get("username", "")
            mention = f" @{uname}" if uname else ""
            tag = f" ({char})" if char else ""
            tg.send_message(group_id, chat_tid,
                            f"\U0001f44b{mention} {user_name}{tag} is back in {campaign_name}!")
    elif old_warn_level >= 2:
        print(f"Warned player {user_name} returned to {campaign_name}")
        chat_tid = maps.to_chat.get(pid)
        if chat_tid:
            char = helpers.character_name(config, pid, user_id)
            uname = parsed.get("username", "") or old_player.get("username", "")
            mention = f" @{uname}" if uname else ""
            tag = f" as {char}" if char else ""
            tg.send_message(group_id, chat_tid,
                            f"\U0001f389{mention} {user_name} is back{tag}! Good to see you.")
    elif old_player.get("last_post_time") and not text.startswith("/"):
        from dispatch.comeback import check_comeback
        check_comeback(parsed, old_player, state, config, gm_ids)
