"""
Transcript recap builder.

Command: /recap [N] — show last N transcript entries with rich formatting.
"""

import re
from datetime import datetime
from pathlib import Path

import helpers
from combat.display import format_elapsed

_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"


def build_recap(pid: str, campaign_name: str, config: dict, count: int = 10) -> str:
    """Build a rich recap of the last N transcript entries.

    Shows character names, GM tags, scene boundaries, and time gaps
    between posts to give a real sense of the conversation flow.
    """
    count = max(1, min(count, 25))  # clamp 1-25

    dir_name = helpers.campaign_dir_name(campaign_name)
    campaign_dir = _LOGS_DIR / dir_name

    if not campaign_dir.exists():
        return f"No transcript archive found for {campaign_name}."

    # Get month files sorted newest first
    month_files = sorted(campaign_dir.glob("*.md"), reverse=True)
    if not month_files:
        return f"No transcript entries for {campaign_name}."  # pragma: no cover

    # Parse entries and scene markers from newest files
    entries = []
    entry_re = re.compile(
        r"^\*\*(.+?)\*\*"
        r"(?:\s*\(([^)\d][^)]*?)\))?"   # optional char name (must NOT start with digit)
        r"\s*(\[GM\])?"                   # optional GM tag
        r"\s*\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\):\n"
        r"(.*?)(?=\n\*\*|\n---|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    scene_re = re.compile(
        r"### 🎭 Scene: (.+?)\n\*\((\d{4}-\d{2}-\d{2} \d{2}:\d{2})\)\*",
    )

    for month_file in month_files:
        if len(entries) >= count + 10:
            break  # pragma: no cover
        try:
            text = month_file.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover
            continue  # pragma: no cover

        file_entries = []

        for m in scene_re.finditer(text):
            scene_name = m.group(1).strip()
            ts = m.group(2).strip() + ":00"
            file_entries.append((ts, "", "", False, scene_name, "scene"))

        for m in entry_re.finditer(text):
            name = m.group(1).strip()
            char_name = m.group(2).strip() if m.group(2) else None
            is_gm = bool(m.group(3))
            timestamp = m.group(4).strip()
            content = m.group(5).strip()
            file_entries.append((timestamp, name, char_name, is_gm, content, "msg"))

        file_entries.sort(key=lambda x: x[0])
        entries = file_entries + entries

    if not entries:
        return f"No transcript entries found for {campaign_name}."

    entries.sort(key=lambda x: x[0])
    msg_entries = [e for e in entries if e[5] == "msg"]
    if not msg_entries:
        return f"No transcript entries found for {campaign_name}."  # pragma: no cover

    window_entries = msg_entries[-count:]
    cutoff_ts = window_entries[0][0]

    display = [e for e in entries if e[0] >= cutoff_ts or (e[5] == "scene" and e[0] >= cutoff_ts[:10])]
    display.sort(key=lambda x: x[0])
    display = display[-(count + 5):]

    lines = [f"📜 Recap — {campaign_name} (last {len(window_entries)}):", ""]

    prev_ts = None
    for ts, name, char_name, is_gm, content, kind in display:
        if prev_ts and kind == "msg":
            try:
                prev_dt = datetime.fromisoformat(prev_ts.replace(" ", "T") + "+00:00")
                curr_dt = datetime.fromisoformat(ts.replace(" ", "T") + "+00:00")
                gap_hours = (curr_dt - prev_dt).total_seconds() / 3600
                if gap_hours >= 4:
                    gap_str = format_elapsed(gap_hours)
                    lines.append(f"        ⋯ {gap_str} later ⋯")
            except (ValueError, TypeError):  # pragma: no cover
                pass  # pragma: no cover

        if kind == "scene":
            lines.append(f"━━━ 🎭 {content} ━━━")
            lines.append("")
            prev_ts = ts
            continue

        time_str = ts[11:16]
        date_str = ts[5:10]

        if is_gm:
            poster = f"🎲 {name}"
        elif char_name:
            poster = f"{char_name}"
        else:
            poster = name

        content_flat = content.replace("\n", " ↩ ").strip()
        if len(content_flat) > 200:
            cut = content_flat[:197]  # pragma: no cover
            last_space = cut.rfind(" ")  # pragma: no cover
            if last_space > 150:  # pragma: no cover
                cut = cut[:last_space]  # pragma: no cover
            content_flat = cut + "…"  # pragma: no cover

        lines.append(f"<b>[{date_str} {time_str}] {poster}:</b>")
        lines.append(f"{content_flat}")
        lines.append("")

        prev_ts = ts

    return "\n".join(lines)
