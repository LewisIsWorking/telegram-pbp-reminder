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

# Matches: **Name** (char) [GM] (2026-03-16 18:02:46) msg#12345:
_ENTRY_RE = re.compile(
    r'\*\*(.+?)\*\*'                        # name
    r'(?:\s*\([^)]*\))?'                     # optional (char_name)
    r'(\s*\[GM\])?'                          # optional [GM]
    r'\s*\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)'  # timestamp
    r'(?:\s*msg#(\d+))?'                     # optional msg#id
    r':\s*$'
)


def scan_transcripts(config: dict) -> dict:
    """Scan recent transcripts for unreplied player messages.

    Returns {pid: [entries]} where each entry has:
      name, time, preview, message_id (or None), pid
    """
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    group_user = "Path_Wars"
    result = {}

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
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
                link = ""
                if msg_id:
                    link = f"https://t.me/{group_user}/{pid}/{msg_id}"
                pending.append({
                    "name": author.strip(),
                    "time": timestamp,
                    "preview": preview,
                    "message_id": msg_id,
                    "link": link,
                })

        if pending:
            result[pid] = {
                "campaign": name,
                "entries": pending,
            }

    return result
