"""
Post-message state tracking.

Updates topic state, message counts, word counts, timestamps,
activity patterns, player roster, and transcript logging.
"""

from datetime import datetime

import helpers
import telegram as tg
from transcript.logger import append_to_transcript


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
            if msg_id:
                queue = state.setdefault("gm_queue", {}).setdefault(pid, [])
                existing_ids = {e["message_id"] for e in queue}
                if msg_id not in existing_ids:
                    queue.append({
                        "message_id": msg_id,
                        "thread_id": parsed["thread_id"],
                        "user_id": user_id,
                        "user_name": user_name,
                        "time": msg_time_iso,
                        "preview": (parsed["raw_text"] or "[media]")[:500],
                    })
                    # Cap queue size per campaign
                    if len(queue) > 50:
                        state["gm_queue"][pid] = queue[-50:]
    else:
        # GM replied to a specific message — mark it cleared
        if not text.startswith("/"):
            reply_to = parsed.get("reply_to_message_id")
            if reply_to:
                replied = state.setdefault("gm_queue_replied", {}).setdefault(pid, [])

                # Store message_id key
                mid_key = f"msg:{reply_to}"
                if mid_key not in replied:
                    replied.append(mid_key)

                # Try to get timestamp from live queue entry
                queue = state.get("gm_queue", {}).get(pid, [])
                for e in queue:
                    if e["message_id"] == reply_to:
                        ts = e.get("time", "")[:19].replace("T", " ")
                        if ts and ts not in replied:
                            replied.append(ts)
                        break
                else:
                    # Entry not in live queue — use reply_to_date from Telegram
                    reply_date = parsed.get("reply_to_date")
                    if reply_date:
                        from datetime import datetime as _dt
                        ts = _dt.fromtimestamp(reply_date, tz=timezone.utc
                                               ).strftime("%Y-%m-%d %H:%M:%S")
                        if ts not in replied:
                            replied.append(ts)

                # Cap at 200 entries
                if len(replied) > 200:
                    state["gm_queue_replied"][pid] = replied[-200:]

                # Remove from live queue
                state.setdefault("gm_queue", {})[pid] = [
                    e for e in queue if e["message_id"] != reply_to
                ]
                # Mark cleared for transcript scanner (persists)
                cleared = state.setdefault("queue_cleared", {}).setdefault(pid, [])
                cleared.append({"message_id": reply_to})
                # Cap at 200 per campaign
                if len(cleared) > 200:
                    state["queue_cleared"][pid] = cleared[-200:]

    # Log to persistent PBP transcript
    if not text.startswith("/"):
        append_to_transcript(parsed, gm_ids, config)

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
            char_name = helpers.character_name(config, pid, user_id)
            char_tag = f" ({char_name})" if char_name else ""
            uname = parsed.get("username", "") or removed_data.get("username", "")
            mention = f" @{uname}" if uname else ""
            tg.send_message(
                group_id, chat_tid,
                f"\U0001f44b{mention} {user_name}{char_tag} is back in {campaign_name}!"
            )
    elif old_warn_level >= 2:
        print(f"Warned player {user_name} returned to {campaign_name} (was week {old_warn_level})")
        chat_tid = maps.to_chat.get(pid)
        if chat_tid:
            char_name = helpers.character_name(config, pid, user_id)
            char_tag = f" as {char_name}" if char_name else ""
            uname = parsed.get("username", "") or old_player.get("username", "")
            mention = f" @{uname}" if uname else ""
            tg.send_message(
                group_id, chat_tid,
                f"\U0001f389{mention} {user_name} is back{char_tag}! Good to see you."
            )
