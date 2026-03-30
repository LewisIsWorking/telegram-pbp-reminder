"""
/markdone — GM command to manually mark queue entries as replied.

Usage (in any PBP topic or bot topic):
  /markdone                 — clear the oldest unreplied entry in this campaign
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
    if arg.isdigit() and len(arg) <= 4:
        idx = int(arg) - 1
        if 0 <= idx < len(entries):
            _clear_entries([entries[idx]], pid, state, now)
            tg.send_message(gid, tid,
                            f"✅ Marked done: {entries[idx].get('name','?')} — "
                            f"{entries[idx].get('preview','')[:60]}")
            return True
        tg.send_message(gid, tid, f"No entry #{arg} in {name} queue "
                                  f"({len(entries)} entries).")
        return True

    # Try message ID (longer number)
    if arg.isdigit():
        match = [e for e in entries if str(e.get("message_id", "")) == arg]
        if match:
            _clear_entries(match, pid, state, now)
            tg.send_message(gid, tid,
                            f"✅ Cleared message {arg} from {name} queue.")
        else:
            tg.send_message(gid, tid, f"Message ID {arg} not found in {name} queue.")
        return True

    # No arg — clear oldest entry
    if not arg:
        _clear_entries([entries[0]], pid, state, now)
        tg.send_message(gid, tid,
                        f"✅ Cleared oldest entry: {entries[0].get('name','?')} — "
                        f"{entries[0].get('preview','')[:60]}")
        return True

    tg.send_message(gid, tid,
                    "Usage: /markdone  /markdone 3  /markdone <msg_id>  /markdone all")
    return True


def _clear_entries(entries: list[dict], pid: str,
                   state: dict, now: datetime) -> int:
    """Mark entries as replied in gm_queue_replied and gm_reply_log."""
    replied = state.setdefault("gm_queue_replied", {}).setdefault(pid, [])
    log     = state.setdefault("gm_reply_log", [])
    cleared = 0

    for e in entries:
        mid = e.get("message_id")
        ts  = e.get("time", "")

        mid_key = f"msg:{mid}" if mid else None
        if mid_key and mid_key not in replied:
            replied.append(mid_key)
        if ts and ts not in replied:
            replied.append(ts)

        log.append({
            "t":       now.isoformat(),
            "pid":     pid,
            "msg_id":  str(mid or ""),
            "player":  e.get("name", "?"),
            "preview": e.get("preview", "")[:80],
            "via":     "markdone",
        })

        # Remove from live gm_queue
        queue = state.get("gm_queue", {}).get(pid, [])
        state["gm_queue"][pid] = [
            q for q in queue if q.get("message_id") != mid
        ]
        cleared += 1

    if len(replied) > 200:
        state["gm_queue_replied"][pid] = replied[-200:]
    if len(log) > 500:
        state["gm_reply_log"] = log[-500:]

    return cleared
