"""
/markdone — GM command to manually mark queue entries as replied.

Usage (in any PBP topic or bot topic):
  /markdone                 — show usage (a message number or ID is required)
  /markdone 3               — clear entry #3 from the queue list
  /markdone 140368          — clear by Telegram message ID
  /markdone all             — clear ALL entries for this campaign

Each cleared entry is written to gm_reply_log for audit purposes.
"""

from datetime import datetime, timezone

import telegram as tg
from commands.queue_scan import scan_transcripts


def handle_markdone(ctx: dict) -> bool:
    """Handle /markdone [N|message_id|all] command."""
    cmd = ctx["cmd_word"]
    if cmd != "/markdone":
        return False

    text  = ctx["text"]
    uid   = ctx["user_id"]
    gm_ids = ctx["gm_ids"]
    if uid not in gm_ids:
        return False

    pid    = ctx["pid"]
    gid    = ctx["group_id"]
    tid    = ctx["thread_id"]
    state  = ctx["state"]
    config = ctx["config"]
    name   = ctx["campaign_name"]
    now    = datetime.now(timezone.utc)

    arg = text[len("/markdone"):].strip()

    # Accept full t.me links — extract the trailing message ID
    # e.g. https://t.me/Path_Wars/40585/139231 → "139231"
    if arg.startswith("http") and "/" in arg:
        arg = arg.rstrip("/").rsplit("/", 1)[-1]

    # Build current queue entries for this campaign
    scanned = scan_transcripts(config, state)
    entries = scanned.get(pid, {}).get("entries", []) if scanned else []

    if not entries:
        tg.send_message(gid, tid, f"✅ No unreplied entries in {name}.")
        return True

    if arg.lower() == "all":
        cleared = _clear_entries(entries, pid, state, now)
        tg.send_message(gid, tid,
                        f"✅ Cleared {cleared} entries from {name} queue.")
        return True

    # Try numeric index (1-based from queue display)
    # Supports single: /markdone 3  or multiple: /markdone 1 2 5
    nums = arg.split()
    if nums and all(n.isdigit() and len(n) <= 4 for n in nums):
        to_clear = []
        bad = []
        for n in nums:
            idx = int(n) - 1
            if 0 <= idx < len(entries):
                to_clear.append(entries[idx])
            else:
                bad.append(n)
        if bad:
            tg.send_message(gid, tid, f"No entr{'ies' if len(bad)>1 else 'y'} "
                                      f"{', '.join('#'+b for b in bad)} in {name} queue "
                                      f"({len(entries)} entries).")
        if to_clear:
            _clear_entries(to_clear, pid, state, now)
            if len(to_clear) == 1:
                tg.send_message(gid, tid,
                                f"✅ Marked done: {to_clear[0].get('name','?')} — "
                                f"{to_clear[0].get('preview','')[:60]}")
            else:
                names = ", ".join(e.get("name", "?") for e in to_clear)  # pragma: no cover
                tg.send_message(gid, tid,  # pragma: no cover
                                f"✅ Marked {len(to_clear)} entries done: {names}")
        return True

    # Try message ID (longer number)
    if arg.isdigit():
        match = [e for e in entries if str(e.get("message_id", "")) == arg]
        if match:
            _clear_entries(match, pid, state, now)
            tg.send_message(gid, tid,
                            f"✅ Cleared message {arg} from {name} queue.")
        elif _clear_by_msg_id(arg, pid, state, now):
            tg.send_message(gid, tid,
                            f"✅ Cleared message {arg} from {name} queue.")
        else:
            tg.send_message(gid, tid, f"Message ID {arg} not found in {name} queue.")
        return True

    # No arg — require explicit target, never clear silently
    if not arg:
        tg.send_message(gid, tid,
                        "Usage: /markdone 3  /markdone <msg_id>  /markdone all\n"
                        "A message number or ID is required.")
        return True

    tg.send_message(gid, tid,
                    "Usage: /markdone 3  /markdone <msg_id>  /markdone all\nA message number or ID is required.")
    return True


def _clear_entries(entries: list[dict], pid: str,
                   state: dict, now: datetime) -> int:
    """Mark entries as replied in per-campaign queue file."""
    from commands.queue_io import load as _load, save as _save
    cq = _load(pid)
    cleared = 0

    for e in entries:
        mid    = e.get("message_id")
        ts     = e.get("time", "")[:19].replace("T", " ")
        mid_str = str(mid) if mid is not None else None
        mid_key = f"msg:{mid_str}" if mid_str else None

        replied = cq.setdefault("replied", [])
        if mid_key and mid_key not in replied:
            replied.append(mid_key)
        if ts and ts not in replied:
            replied.append(ts)

        cq.setdefault("reply_log", []).append({
            "t":         now.isoformat(),
            "pid":       pid,
            "msg_id":    mid_str or "",
            "thread_id": e.get("thread_id", pid),
            "player":    e.get("name", "?"),
            "preview":   e.get("preview", "")[:80],
            "via":       "markdone",
        })

        # Remove from unreplied — compare as strings to handle int/str mismatch
        cq["unreplied"] = [
            q for q in cq.get("unreplied", [])
            if str(q.get("message_id", "")) != mid_str
        ]
        cleared += 1

    _save(pid, cq)
    return cleared


def _clear_by_msg_id(msg_id: str, pid: str, state: dict, now: datetime) -> bool:
    """Directly clear a message ID from queue_io even if not in transcript scan.

    Fallback for recent messages not yet in transcript, or scan misses.
    Returns True if found and cleared.
    """
    from commands.queue_io import load as _load, save as _save
    cq = _load(pid)
    mid_key = f"msg:{msg_id}"
    match = [e for e in cq.get("unreplied", [])
             if str(e.get("message_id", "")) == msg_id]
    if not match:
        return False
    e = match[0]
    ts = e.get("time", "")[:19].replace("T", " ")
    replied = cq.setdefault("replied", [])
    if mid_key not in replied:
        replied.append(mid_key)
    if ts and ts not in replied:
        replied.append(ts)
    cq.setdefault("reply_log", []).append({
        "t":         now.isoformat(),
        "pid":       pid,
        "msg_id":    msg_id,
        "thread_id": e.get("thread_id", pid),
        "player":    e.get("user_name", "?"),
        "preview":   e.get("preview", "")[:80],
        "via":       "markdone",
    })
    cq["unreplied"] = [q for q in cq.get("unreplied", [])
                       if str(q.get("message_id", "")) != msg_id]
    _save(pid, cq)
    return True
