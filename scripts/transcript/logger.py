"""
Transcript logger.

Appends PBP messages to monthly markdown transcript files with
structural markers (week headers, day headers, silence gaps).
Also handles scene boundary markers.
"""

import re
from datetime import date as _date, datetime, timezone
from pathlib import Path

import helpers
from transcript.formatting import format_log_entry
from transcript.finalize import finalize_previous_month

_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"

_SILENCE_THRESHOLD_HOURS = 12.0

# In-memory cache for transcript structural markers (week, date, timestamp)
_transcript_cache: dict[str, int | str] = {}


def sanitize_dirname(name: str) -> str:
    """Convert a campaign name to a safe directory name."""
    return "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in name).strip().replace(" ", "_")


def write_scene_marker(campaign_name: str, scene_name: str) -> None:
    """Write a scene boundary marker to the campaign's transcript file."""
    dir_name = sanitize_dirname(campaign_name)
    campaign_dir = _LOGS_DIR / dir_name
    campaign_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")
    log_file = campaign_dir / f"{month_str}.md"

    is_new = not log_file.exists()

    with open(log_file, "a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# {campaign_name} — {month_str}\n\n")
            f.write("*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n")
        ts = now.strftime("%Y-%m-%d %H:%M")
        f.write(f"\n---\n\n### 🎭 Scene: {scene_name}\n*({ts})*\n\n---\n\n")


def append_to_transcript(parsed: dict, gm_ids: set, config: dict | None = None) -> None:
    """Append a message to the campaign's monthly transcript file.

    Files: data/pbp_logs/{CampaignName}/{YYYY-MM}.md
    Structural markers inserted automatically:
    - ## Week N (Mon DD-Sun DD) -- when ISO week changes
    - ### Day, Mon DD -- when date changes within a week
    - *-- Xh of silence --* -- when 12+ hour gap between messages
    """
    campaign_name = parsed["campaign_name"]
    dir_name = sanitize_dirname(campaign_name)
    campaign_dir = _LOGS_DIR / dir_name
    campaign_dir.mkdir(parents=True, exist_ok=True)

    msg_date = parsed["msg_time_iso"][:10]
    month_str = msg_date[:7]
    log_file = campaign_dir / f"{month_str}.md"

    char_name = None
    if config:
        char_name = helpers.character_name(config, parsed["pid"], parsed["user_id"])

    msg_dt = datetime.fromisoformat(parsed["msg_time_iso"])
    msg_iso_year, msg_iso_week, _ = msg_dt.isocalendar()

    is_new = not log_file.exists()

    cache_prefix = f"transcript:{dir_name}:{month_str}"
    week_key = f"{cache_prefix}:week"
    date_key = f"{cache_prefix}:date"
    time_key = f"{cache_prefix}:time"

    needs_week_header = False
    needs_day_header = False
    silence_hours = 0.0

    if is_new:
        needs_week_header = True
        needs_day_header = True
    else:
        last_week = _transcript_cache.get(week_key)
        if last_week is None:
            try:
                content = log_file.read_text(encoding="utf-8")
                week_matches = re.findall(r"## Week (\d+)", content)
                last_week = int(week_matches[-1]) if week_matches else 0
            except Exception:
                last_week = 0
        if msg_iso_week != last_week:
            needs_week_header = True
            needs_day_header = True

        last_date = _transcript_cache.get(date_key)
        if last_date is None:
            try:
                if not is_new:
                    content = log_file.read_text(encoding="utf-8") if "content" not in dir() else content
                    date_matches = re.findall(
                        r"\((\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\):", content
                    )
                    last_date = date_matches[-1] if date_matches else ""
            except Exception:
                last_date = ""
        if msg_date != last_date:
            needs_day_header = True

        last_time_str = _transcript_cache.get(time_key)
        if last_time_str:
            try:
                last_time = datetime.fromisoformat(last_time_str)
                silence_hours = (msg_dt - last_time).total_seconds() / 3600.0
            except (TypeError, ValueError):
                pass

    with open(log_file, "a", encoding="utf-8") as f:
        if is_new:
            f.write(f"# {campaign_name} — {month_str}\n\n")
            f.write("*PBP transcript archived by PathWarsNudge bot.*\n\n---\n\n")
            finalize_previous_month(campaign_dir, month_str, campaign_name)

        if needs_week_header:
            week_monday = _date.fromisocalendar(msg_iso_year, msg_iso_week, 1)
            week_sunday = _date.fromisocalendar(msg_iso_year, msg_iso_week, 7)
            mon_str = week_monday.strftime("%b %d")
            sun_str = week_sunday.strftime("%b %d")
            f.write(f"## Week {msg_iso_week} ({mon_str}\u2013{sun_str})\n\n")

        if needs_day_header:
            day_label = msg_dt.strftime("%A, %b %d")
            f.write(f"### 📅 {day_label}\n\n")

        if (silence_hours >= _SILENCE_THRESHOLD_HOURS
                and not needs_day_header and not needs_week_header):
            if silence_hours >= 48:
                gap_str = f"{silence_hours / 24:.1f} days"
            else:
                gap_str = f"{silence_hours:.0f}h"
            f.write(f"*\u2014 {gap_str} of silence \u2014*\n\n")

        entry = format_log_entry(parsed, gm_ids, char_name)
        f.write(entry + "\n")

    _transcript_cache[week_key] = msg_iso_week
    _transcript_cache[date_key] = msg_date
    _transcript_cache[time_key] = parsed["msg_time_iso"]
