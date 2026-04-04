"""
Telegram message parser.

Validates and extracts fields from raw Telegram message dicts
into a standardized parsed dict for command processing.
"""

import re
from datetime import datetime, timezone


def _real_reply_id(msg: dict) -> int | None:
    """Return the replied-to message ID only if it's a genuine reply.

    In Telegram forum topics, every message has reply_to_message set to
    the topic header (forum_topic_created). We must ignore those — they
    are not actual replies to a player message.
    """
    r = msg.get("reply_to_message", {})
    if not r:
        return None
    # Skip forum topic header (has forum_topic_created key)
    if "forum_topic_created" in r:  # pragma: no cover
        return None  # pragma: no cover
    # Skip if message_id matches the thread_id (topic root message)  # pragma: no cover
    thread_id = msg.get("message_thread_id")  # pragma: no cover
    r_id = r.get("message_id")  # pragma: no cover
    if thread_id and r_id == thread_id:  # pragma: no cover
        return None  # pragma: no cover
    return r_id  # pragma: no cover


def parse_message(msg: dict, maps) -> dict | None:
    """Validate and extract fields from a Telegram message. Returns None if skipped."""
    chat_id = msg.get("chat", {}).get("id")
    thread_id = msg.get("message_thread_id")

    # Allow /chooseboon from the main group chat (no thread_id)
    # by using a sentinel pid — boon handler finds the right campaign by user_id
    raw_text = msg.get("text", "") or msg.get("caption", "")
    _cmd = raw_text.lower().strip().split()[0] if raw_text.strip() else ""
    _cmd = re.sub(r"@\S+", "", _cmd)  # strip @botname
    if thread_id is None:
        if _cmd == "/chooseboon":  # pragma: no cover
            thread_id = 0  # sentinel — no real topic, boon handler resolves by uid  # pragma: no cover
        else:  # pragma: no cover
            return None  # pragma: no cover

    thread_id_str = str(thread_id)
    if thread_id_str not in maps.all_pbp_ids and thread_id != 0:
        return None

    # Verify the message came from the correct group for this topic
    if thread_id == 0:
        # /chooseboon from main chat — use sentinel pid, skip group check
        pid = "__main__"  # pragma: no cover
    else:
        pid = maps.to_canonical[thread_id_str]
        if chat_id != maps.to_group.get(pid):
            return None

    from_user = msg.get("from", {})
    if from_user.get("is_bot", False):
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    msg_date = msg.get("date")
    msg_time_iso = datetime.fromtimestamp(msg_date, tz=timezone.utc).isoformat() if msg_date else now_iso

    raw_text = msg.get("text", "").strip()

    # Detect media type for logging
    media_type = _detect_media(msg)

    # Caption on media messages
    caption = msg.get("caption", "").strip()

    # Strip @botname suffix from slash commands (Telegram appends it in groups)
    _lower = raw_text.lower() if raw_text else (caption.lower() if caption else "")
    if _lower.startswith("/"):
        _lower = re.sub(r"^(/\w+)@\S+", r"\1", _lower)

    return {
        "thread_id": thread_id,
        "message_id": msg.get("message_id"),
        "reply_to_message_id": _real_reply_id(msg),
        "reply_to_date": msg.get("reply_to_message", {}).get("date"),
        "media_group_id": msg.get("media_group_id"),
        "pid": maps.to_canonical[thread_id_str],
        "campaign_name": maps.to_name[maps.to_canonical[thread_id_str]],
        "user_id": str(from_user.get("id", "")),
        "user_name": from_user.get("first_name", "Someone"),
        "user_last_name": from_user.get("last_name", ""),
        "username": from_user.get("username", ""),
        "now_iso": now_iso,
        "msg_time_iso": msg_time_iso,
        "text": _lower,
        "raw_text": raw_text,
        "media_type": media_type,
        "caption": caption,
        "chat_topic_id": maps.to_chat.get(maps.to_canonical[thread_id_str], thread_id),
    }


def _detect_media(msg: dict) -> str | None:
    """Detect the media type of a Telegram message, if any."""
    if msg.get("photo"):
        return "image"
    if msg.get("sticker"):
        return f"sticker:{msg['sticker'].get('emoji', '?')}"
    if msg.get("animation"):
        return "gif"
    if msg.get("video"):
        return "video"
    if msg.get("voice"):
        return "voice message"
    if msg.get("video_note"):
        return "video note"
    if msg.get("document"):
        return f"document:{msg['document'].get('file_name', 'file')}"
    return None
