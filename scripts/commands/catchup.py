"""
Catch-up builder for returning players.

Command: /catchup — shows what happened since last post.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import helpers
from helpers import timestamps_in_window, posts_str
from combat.display import format_elapsed

_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"


def _get_recent_transcript_posts(campaign_name: str, since: datetime,
                                  max_posts: int = 8) -> list[tuple[str, str, str]]:
    """Pull recent transcript entries after a given time.

    Returns list of (timestamp, poster_display, content).
    """
    dir_name = helpers.campaign_dir_name(campaign_name)
    campaign_dir = _LOGS_DIR / dir_name

    if not campaign_dir.exists():
        return []  # pragma: no cover

    month_files = sorted(campaign_dir.glob("*.md"), reverse=True)
    if not month_files:
        return []  # pragma: no cover

    since_str = since.strftime("%Y-%m-%d %H:%M:%S")

    entry_re = re.compile(
        r"^\*\*(.+?)\*\*"
        r"(?:\s*\(([^)\d][^)]*?)\))?"   # optional char name (NOT starting with digit)
        r"\s*(\[GM\])?"                   # optional GM tag
        r"\s*\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\):\n"
        r"(.*?)(?=\n\*\*|\n---|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    entries = []
    for month_file in month_files[:3]:  # Check last 3 months max
        try:
            text = month_file.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover
            continue  # pragma: no cover

        for m in entry_re.finditer(text):
            name = m.group(1).strip()
            char_name = m.group(2).strip() if m.group(2) else None
            is_gm = bool(m.group(3))
            timestamp = m.group(4).strip()
            content = m.group(5).strip()

            if timestamp <= since_str:
                continue

            if is_gm:
                poster = f"🎲 {name}"
            elif char_name:
                poster = f"{char_name}"  # pragma: no cover
            else:
                poster = name

            entries.append((timestamp, poster, content))

    entries.sort(key=lambda x: x[0])
    return entries[-max_posts:]


def build_catchup(pid: str, user_id: str, campaign_name: str,
                  state: dict, gm_ids: set, config: dict | None = None) -> str:
    """Build a catch-up summary: what happened since the player last posted."""
    now = datetime.now(timezone.utc)
    topic_ts = helpers.get_topic_timestamps(state, pid)
    my_ts = topic_ts.get(user_id, [])

    if not my_ts:
        return f"No posting history in {campaign_name}. Post something first!"

    last_post = max(datetime.fromisoformat(ts) for ts in my_ts)
    hours_ago = (now - last_post).total_seconds() / 3600

    if hours_ago < 1:
        return f"You posted in {campaign_name} less than an hour ago. You're caught up!"

    # Count messages from others since our last post
    poster_counts = {}
    total_since = 0
    for uid, timestamps in topic_ts.items():
        if uid == user_id:
            continue
        is_gm = uid in gm_ids
        count = len(timestamps_in_window(timestamps, last_post))
        if count > 0:
            player = helpers.get_player(state, pid, uid)
            if is_gm:
                name = "GM"
            elif player:
                name = player.get("first_name", "?")
            else:
                name = "?"  # pragma: no cover
            poster_counts[name] = count
            total_since += count

    time_str = format_elapsed(hours_ago)

    if total_since == 0:
        return (f"Nobody has posted in {campaign_name} since your last message "
                f"({time_str} ago). The floor is yours!")

    # Build summary header
    lines = [
        f"📬 Catch-up for {campaign_name}:",
        f"Since your last post ({time_str} ago):",
        f"",
    ]

    # Poster breakdown
    for name, count in sorted(poster_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {name}: {posts_str(count)}")
    lines.append(f"  Total: {posts_str(total_since)}")

    # Pull actual recent posts from transcript
    recent_posts = _get_recent_transcript_posts(campaign_name, last_post, max_posts=8)
    if recent_posts:
        lines.append("")
        lines.append("Recent posts:")
        lines.append("")
        for ts, poster, content in recent_posts:
            time_part = ts[11:16]
            date_part = ts[5:10]
            content_flat = content.replace("\n", " ↩ ").strip()
            if len(content_flat) > 150:
                cut = content_flat[:147]  # pragma: no cover
                last_space = cut.rfind(" ")  # pragma: no cover
                if last_space > 100:  # pragma: no cover
                    cut = cut[:last_space]  # pragma: no cover
                content_flat = cut + "…"  # pragma: no cover
            lines.append(f"<b>[{date_part} {time_part}] {poster}:</b>")
            lines.append(f"{content_flat}")
            lines.append("")

        if total_since > len(recent_posts):
            lines.append(f"(+{total_since - len(recent_posts)} more — use /recap {min(total_since, 25)} for full history)")

    # Combat state
    combat = state.get("combat", {}).get(pid, {})
    if combat.get("active"):
        round_num = combat.get("round", "?")
        phase = combat.get("current_phase", "?")
        lines.append(f"⚔️ Combat is active (Round {round_num}, {phase})")
        acted = combat.get("players_acted", {})
        if isinstance(acted, dict):
            acted_ids = set(acted.keys())
        else:
            acted_ids = set(acted)  # pragma: no cover
        if user_id in acted_ids:
            lines.append("✅ You've already acted this round.")
        else:
            lines.append("⏳ You haven't acted yet — post your actions!")

    return "\n".join(lines)
