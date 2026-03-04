"""Message formatting helpers for historical transcript import."""

def extract_text(msg: dict) -> str:
    """Extract readable text from a Telegram export message.

    The 'text' field can be a plain string OR a list of mixed text/entity
    objects like [{"type": "bold", "text": "hello"}, " world"].

    Desktop exports may also use 'text_entities' as a list of
    {"type": "...", "text": "..."} objects.
    """
    raw = msg.get("text", "")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, list) and raw:
        parts = []
        for chunk in raw:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                parts.append(chunk.get("text", ""))
        result = "".join(parts).strip()
        if result:
            return result

    # Fallback: text_entities (Telegram Desktop export format)
    entities = msg.get("text_entities", [])
    if entities:
        parts = [e.get("text", "") for e in entities if isinstance(e, dict)]
        return "".join(parts).strip()

    return ""


def detect_media(msg: dict) -> str | None:
    """Detect media type from Telegram export message.

    Handles both Bot API format and Desktop export format.
    """
    # Desktop export format
    media_type = msg.get("media_type")
    if media_type == "animation":
        return "gif"
    if media_type == "video_file":
        return "video"
    if media_type == "voice_message":
        return "voice message"
    if media_type == "video_message":
        return "video note"
    if media_type == "sticker":
        emoji = msg.get("sticker_emoji", "?")
        return f"sticker:{emoji}"

    # Photo (Desktop export uses "photo" as a file path string)
    if msg.get("photo"):
        return "image"

    # Document/file
    if msg.get("file") and not media_type:
        fname = str(msg.get("file", "")).split("/")[-1] if msg.get("file") else "file"
        return f"document:{fname}"

    return None


def format_entry(msg: dict, is_gm: bool) -> str:
    """Format a message as a transcript entry."""
    # Parse timestamp
    date_str = msg.get("date", "")
    ts = date_str[:19].replace("T", " ")  # 2025-01-15 14:30:05

    # Name
    name = msg.get("from", "Unknown")
    role_tag = " [GM]" if is_gm else ""

    # Content
    text = extract_text(msg)
    media = detect_media(msg)

    parts = []
    if media:
        if media.startswith("sticker:"):
            parts.append(f"*[sticker {media[8:]}]*")
        elif media.startswith("document:"):
            parts.append(f"*[{media[9:]}]*")
        else:
            parts.append(f"*[{media}]*")

    if text:
        parts.append(text)

    content = " ".join(parts) if parts else "*[empty message]*"

    return f"**{name}**{role_tag} ({ts}):\n{content}\n"
