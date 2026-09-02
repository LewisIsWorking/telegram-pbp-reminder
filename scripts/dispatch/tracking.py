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

    # Message count — per canonical pid (existing) and per physical thread (new)
    user_counts = state["message_counts"].setdefault(pid, {})
    user_counts[user_id] = user_counts.get(user_id, 0) + 1
    thread_id = parsed.get("thread_id", pid)
    thread_counts = state.setdefault("thread_message_counts", {}).setdefault(thread_id, {})
    thread_counts[user_id] = thread_counts.get(user_id, 0) + 1

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
                from dispatch.gm_reply import record_gm_reply
                record_gm_reply(parsed, state, pid, reply_to)

    # Auto-identify previously unknown poll voters when they post
    unknown_polls = state.get("poll_unknown_voters", {})
    for _code, _uids in unknown_polls.items():
        if user_id in _uids:
            from dispatch.poll_notify import identify_unknown_voter
            identify_unknown_voter(user_id, user_name,
                                   parsed.get("first_name", user_name),
                                   _code, config, state)
            break

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


# The per-player record update lives in dispatch/track_player (extracted
# 2026-09-02 at 210 lines). Re-exported so this module's existing
# callers and tests keep working.
from dispatch.track_player import _track_player  # noqa: E402,F401
