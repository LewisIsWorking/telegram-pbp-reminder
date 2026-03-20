"""
Transcript-based queue scanner.

Scans PBP transcript files to find unreplied player messages,
complementing the live gm_queue. Returns entries with message_ids
and links when available (msg#12345 tags in transcripts).
"""

import re
from datetime import datetime, timezone
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
    r'(?:\s*msg#(\d+))?'                     # optional msg#id
    r':\s*$'
)


def scan_transcripts(config: dict, state: dict | None = None) -> dict:
    """Scan recent transcripts for unreplied player messages.

    Returns {pid: {campaign, code, entries}} where each entry has:
      name, time, preview, message_id (or None), link
    Filters out messages marked as cleared via reply-to tracking.
    """
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    group_user = "Path_Wars"
    result = {}

    # Load replied entries from state (timestamps + msg:id keys)
    replied = {}
    if state:
        for pid, entries in state.get("gm_queue_replied", {}).items():
            replied[pid] = set(entries)

    # Load message_id lookup for backfilled links
    import json
    id_lookup = {}
    if _IDS_FILE.exists():
        try:
            id_lookup = json.loads(_IDS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        code = pair.get("code", "")
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        dirname = name.replace(" ", "_").replace("'", "")
        path = _LOGS_DIR / dirname / f"{month}.md"
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        pending = []
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
                pending = []
            else:
                # Check inline msg# tag first, then lookup file
                mid = msg_id
                if not mid:
                    lookup_key = f"{pid}:{timestamp}"
                    mid_val = id_lookup.get(lookup_key)
                    if mid_val:
                        mid = str(mid_val)
                link = ""
                if mid:
                    link = f"https://t.me/{group_user}/{pid}/{mid}"
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
