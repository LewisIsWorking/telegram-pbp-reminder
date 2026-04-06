"""
Transcript-based queue scanner.

Scans PBP transcript files to find unreplied player messages,
complementing the live gm_queue. Returns entries with message_ids
and links when available (msg#12345 tags in transcripts).
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import helpers

_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"
_IDS_FILE = Path(__file__).parent.parent.parent / "data" / "message_ids.json"

# Matches: **Name** (char) [GM] (2026-03-16 18:02:46) msg#12345:
_ENTRY_RE = re.compile(
    r'\*\*(.+?)\*\*'                        # name
    r'(?:\s*\([^)]*\))?'                     # optional (char_name)
    r'(\s*\[GM\])?'                          # optional [GM]
    r'\s*\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)'  # timestamp
    r'(?:\s*msg#(\d+)(?:@(\d+))?)?'         # optional msg#id[@thread_id]
    r':\s*$'
)


def scan_transcripts(config: dict, state: dict | None = None) -> dict:
    """Scan recent transcripts for unreplied player messages.

    Returns {pid: {campaign, code, entries}} where each entry has:
      name, time, preview, message_id (or None), link
    Filters out messages marked as cleared via reply-to tracking,
    and entries older than state['queue_scan_floor'] (suppresses
    pre-fix backlog from before direct-reply tracking was introduced).
    """
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    # Also scan the previous month to catch entries posted near month boundaries
    prev_month_dt = (now.replace(day=1) - timedelta(days=1))
    prev_month = prev_month_dt.strftime("%Y-%m")
    months_to_scan = [prev_month, month] if prev_month != month else [month]
    group_user = "Path_Wars"
    result = {}

    # Floor timestamp — ignore entries older than this (ISO date string YYYY-MM-DD)
    floor_date = None
    if state:
        floor_date = state.get("queue_scan_floor")

    # Load replied entries from per-campaign queue files (authoritative source)
    # Falls back to legacy state["gm_queue_replied"] for campaigns not yet migrated
    replied: dict[str, set[str]] = {}
    from commands.queue_io import replied_set as _replied_set, all_pids as _all_pids
    for pid in _all_pids():
        replied[pid] = _replied_set(pid)
    # Legacy fallback
    if state:
        for pid, entries in state.get("gm_queue_replied", {}).items():
            if pid not in replied:
                replied[pid] = set(entries)

    # Load message_id → thread_id from persisted queue files (authoritative)
    # This handles multi-topic campaigns (C00, C05, C06) correctly
    thread_lookup: dict[str, str] = {}
    from commands.queue_io import load as _load_queue
    for pid in _all_pids():
        cq = _load_queue(pid)
        for e in cq.get("unreplied", []):
            mid = e.get("message_id")
            tid = e.get("thread_id")
            if mid and tid:
                thread_lookup[str(mid)] = str(tid)

    # Load message_id lookup for backfilled links (timestamp → message_id)
    import json
    id_lookup = {}
    if _IDS_FILE.exists():
        try:
            id_lookup = json.loads(_IDS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    for pid, code, name, pair in helpers.iter_campaigns(config):
        if helpers.is_excluded(config, pid):
            continue
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        dirname = name.replace(" ", "_").replace("'", "")
        pending = []
        for month_str in months_to_scan:
            path = _LOGS_DIR / dirname / f"{month_str}.md"
            if not path.exists():
                continue

            content = path.read_text(encoding="utf-8")
            lines = content.split("\n")

            i = 0
            while i < len(lines):
                m = _ENTRY_RE.match(lines[i])
                if not m:
                    i += 1
                    continue

                author = m.group(1)
                is_gm = bool(m.group(2))
                timestamp = m.group(3)
                msg_id = m.group(4)
                entry_thread = m.group(5)  # thread_id from msg#id@thread_id tag

                # Collect content lines
                i += 1
                content_lines = []
                while i < len(lines) and not _ENTRY_RE.match(lines[i]):
                    if lines[i].startswith("## ") or lines[i].startswith("### "):
                        break
                    if lines[i].startswith("*—") and "silence" in lines[i]:
                        break
                    content_lines.append(lines[i])
                    i += 1

                preview = "\n".join(content_lines).strip()

                if is_gm:
                    # A GM message does NOT clear pending entries — only a direct
                    # reply (tracked via gm_queue_replied in state) clears a specific
                    # player message. A GM posting generally shouldn't wipe the queue.
                    pass
                else:
                    # Skip entries before the scan floor (suppresses pre-fix backlog)
                    if floor_date and timestamp[:10] < floor_date:
                        i += 1
                        continue
                    # Check inline msg# tag first, then lookup file
                    mid = msg_id
                    if not mid:
                        lookup_key = f"{pid}:{timestamp}"
                        mid_val = id_lookup.get(lookup_key)
                        if mid_val:
                            mid = str(mid_val)
                    link = ""
                    if mid:
                        # Priority: persisted queue thread_id > transcript @tag > canonical pid
                        topic = thread_lookup.get(str(mid)) or entry_thread or pid
                        link = f"https://t.me/{group_user}/{topic}/{mid}"
                    pending.append({
                        "name": author.strip(),
                        "time": timestamp,
                        "preview": preview,
                        "message_id": mid,
                        "link": link,
                    })

        if pending:
            # Filter out messages cleared via reply-to
            pid_replied = replied.get(pid, set())
            if pid_replied:
                pending = [e for e in pending
                           if e["time"] not in pid_replied
                           and f"msg:{e.get('message_id', '')}" not in pid_replied]
            if pending:
                result[pid] = {
                    "campaign": name,
                    "code": code,
                    "entries": pending,
                }

    return result
