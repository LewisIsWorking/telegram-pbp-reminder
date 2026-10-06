"""Apply a Telegram message EDIT to the transcript entry it changes.

Added 2026-10-06. Lewis edited C10's Setting 3 lore post on 2026-10-01 to
correct its year (2,000,000 to 112,026 AF). The bot never asked Telegram for
``edited_message`` updates, so the transcript kept the original, and five
days later a Claude session read the transcript, took the wrong year as
still posted, and drafted a correction for a post that was already fixed.

An edit is not a new post. It must not count toward activity, word totals,
the reply queue, combat or commands. It only replaces the text of an entry
that is already in the transcript, found by its ``msg#<id>`` tag, and the
preview of a queued unreplied message with the same id.

⚠️ Nothing is added when the original entry is not found (an edit to a
message from before the transcript existed, or from an older month than
its date says). Inventing an entry would put a post at the wrong point in
the record.
"""

import re

import transcript.logger as _logger
from commands import queue_io
from transcript.formatting import format_log_entry
from transcript.logger import sanitize_dirname

EDITED_MARK = "*(edited)*"

# An entry header, as format_log_entry writes it.
_HEADER_RE = re.compile(r"^\*\*.+\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\)"
                        r"(?: msg#\d+(?:@\d+)?)?:\s*$")


def _is_boundary(line: str) -> bool:
    """Where one entry's body stops: the next entry or a structural marker."""
    return (bool(_HEADER_RE.match(line)) or line.startswith("## ")
            or line.startswith("### ") or line.startswith("*- ")
            or line.strip() == "---")


def replace_entry(content: str, message_id, new_entry: str) -> str | None:
    """``content`` with message ``message_id``'s entry replaced, else None."""
    lines = content.split("\n")
    tag = re.compile(rf" msg#{re.escape(str(message_id))}(?:@\d+)?:\s*$")
    start = next((i for i, line in enumerate(lines)
                  if _HEADER_RE.match(line) and tag.search(line)), None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines) and not _is_boundary(lines[end]):
        end += 1
    # Keep the blank line(s) that separate this entry from the next.
    while end > start + 1 and lines[end - 1].strip() == "":
        end -= 1
    body = new_entry.rstrip("\n").split("\n")
    return "\n".join(lines[:start] + body + lines[end:])


def apply_edit(parsed: dict, gm_ids: set, config: dict) -> bool:
    """Rewrite the edited message's transcript entry. True if it changed."""
    message_id = parsed.get("message_id")
    if not message_id or parsed.get("text", "").startswith("/"):
        return False
    _update_queue_preview(parsed)
    import helpers
    char_name = helpers.character_name(config, parsed["pid"], parsed["user_id"])
    # Read at call time: the test isolation module repoints it.
    log_file = (_logger._LOGS_DIR / sanitize_dirname(parsed["campaign_name"])
                / f"{parsed['msg_time_iso'][:7]}.md")
    if not log_file.exists():
        return False
    content = log_file.read_text(encoding="utf-8")
    entry = format_log_entry(parsed, gm_ids, char_name).rstrip("\n")
    updated = replace_entry(content, message_id, f"{entry}\n{EDITED_MARK}")
    if updated is None or updated == content:
        return False
    log_file.write_text(updated, encoding="utf-8")
    print(f"Applied edit to msg#{message_id} in {parsed['campaign_name']}")
    return True


def _update_queue_preview(parsed: dict) -> None:
    """A queued unreplied message shows its edited text, not the original."""
    cq = queue_io.load(parsed["pid"])
    for entry in cq.get("unreplied", []):
        if entry.get("message_id") == parsed["message_id"]:
            entry["preview"] = (parsed.get("raw_text") or "[media]")[:500]
            queue_io.save(parsed["pid"], cq)
            return
