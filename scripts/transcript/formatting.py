"""
Transcript entry formatting.

Formats PBP messages into markdown log entries with blockquotes,
mechanical content styling, and character/GM tags.
"""

import re

import helpers


# Patterns that indicate mechanical/dice content (case-insensitive)
_MECHANICAL_PATTERNS = re.compile(
    r"^("
    r"DC \d+|"                          # DC 14
    r"Rank \d+|"                         # Rank 4
    r"\d+d\d+[\+\-\d]*\s*=|"           # 2d6+4 =
    r".*(?:to hit|to strike)\s*=|"      # 22 to hit =
    r".*(?:critical (?:hit|miss|success|failure))|"  # Critical Hit
    r".*(?:(?:nat|natural) (?:1|20))|"  # nat 20
    r"Flat check|"                       # Flat check
    r"Saving throw|"                     # Saving throw
    r".*rolled? (?:a )?\d+|"            # rolled a 17
    r"@\w+\s*$"                         # Just a @mention (pinging for turn)
    r")",
    re.IGNORECASE
)


def format_transcript_content(text: str) -> str:
    """Format message content with blockquotes and mechanical styling."""
    lines = text.split("\n")
    out = []
    for line in lines:
        stripped = line.strip()

        # PBP quote formatting: >> - becomes nested blockquote
        if stripped.startswith(">> -") or stripped.startswith(">>-"):
            content = stripped.lstrip(">").lstrip(" -").strip()
            out.append(f">> {content}")
        elif stripped.startswith(">>"):
            content = stripped[2:].lstrip(" -").strip()
            out.append(f">> {content}")
        elif stripped.startswith(">"):
            content = stripped[1:].lstrip()
            out.append(f"> {content}")
        # Mechanical line — style in italics
        elif _MECHANICAL_PATTERNS.match(stripped):
            out.append(f"*{stripped}*")
        else:
            out.append(line)

    return "\n".join(out)


def format_log_entry(parsed: dict, gm_ids: set, char_name: str | None = None) -> str:
    """Format a single message as a markdown log line.

    Improvements:
    - PBP quote formatting (> and >> -) rendered as blockquotes
    - Mechanical content (rolls, DCs) styled in italics
    """
    ts = parsed["msg_time_iso"][:19].replace("T", " ")  # 2026-02-26 14:30:05
    name = parsed["user_name"]
    last = parsed.get("user_last_name", "")
    if last:
        name = f"{name} {last}"

    is_gm = parsed["user_id"] in gm_ids
    role_tag = " [GM]" if is_gm else ""
    char_tag = f" ({char_name})" if char_name and not is_gm else ""

    raw = parsed.get("raw_text", "")
    media = parsed.get("media_type")
    caption = parsed.get("caption", "")

    # Build content
    parts = []
    if media:
        if media.startswith("sticker:"):
            parts.append(f"*[sticker {media[8:]}]*")
        elif media.startswith("document:"):
            parts.append(f"*[{media[9:]}]*")
        else:
            parts.append(f"*[{media}]*")
    if raw:
        parts.append(format_transcript_content(raw))
    elif caption:
        parts.append(format_transcript_content(caption))

    content = " ".join(parts) if parts else "*[empty message]*"

    return f"**{name}**{char_tag}{role_tag} ({ts}):\n{content}\n"
