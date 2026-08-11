"""
Helpers: formatting.
"""

from datetime import datetime, timezone, timedelta

from helpers_pkg.constants import POST_SESSION_MINUTES
from helpers_pkg.time_utils import avg_gap_hours, days_since



RANK_ICONS = ["🥇", "🥈", "🥉"]



def rank_icon(index: int) -> str:
    """Return medal emoji for top 3, or 'N.' for the rest."""
    return RANK_ICONS[index] if index < 3 else f"{index + 1}."

# ------------------------------------------------------------------ #
#  Formatting helpers
# ------------------------------------------------------------------ #
def fmt_date(dt: datetime) -> str:
    """Format a datetime as YYYY-MM-DD (Wn)."""
    _, week, _ = dt.isocalendar()
    return f"{dt.strftime('%Y-%m-%d')} (W{week})"



def html_escape(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )



def display_name(first_name: str, username: str = "", last_name: str = "") -> str:
    """Format a player name as 'First Last (@username)' or 'First Last' or 'First'."""
    full = f"{first_name} {last_name}".strip() if last_name else first_name
    if username:
        return f"{full} (@{username})"
    return full



def player_mention(player: dict) -> str:
    """Extract display_name from a player state dict."""
    return display_name(
        player.get("first_name", "Unknown"),
        player.get("username", ""),
        player.get("last_name", ""),
    )



def player_full_name(player: dict) -> str:
    """Extract 'First Last' from a player dict, without @username."""
    first = player.get("first_name", "Unknown")
    last = player.get("last_name", "")
    return f"{first} {last}".strip() if last else first



def posts_str(n: int) -> str:
    """Return '1 post' or 'N posts'."""
    return count_str(n, "post")


def count_str(n: int, noun: str, plural: str | None = None) -> str:
    """Return '1 <noun>' or 'N <noun>s' — a generalised ``posts_str``.

    Added 2026-08-11: the weekly leaderboard hand-rolled its counts as
    f"{n} player posts", which read "1 player posts" and "1 GM posts" for
    a quiet campaign. ``posts_str`` already existed but only covers the
    bare word "post", so anything with a qualifier bypassed it.

    ``plural`` covers irregulars; it defaults to ``noun + "s"``.
    """
    return f"{n} {noun}" if n == 1 else f"{n} {plural or noun + 's'}"



def fmt_relative_date(now: datetime, then: datetime) -> str:
    """Format as relative + absolute, e.g. '5d ago (2026-02-10)'."""
    d = int(days_since(now, then))
    date_str = fmt_date(then)
    if d == 0:
        return f"today ({date_str})"
    elif d == 1:
        return f"yesterday ({date_str})"
    else:
        return f"{d}d ago ({date_str})"



def fmt_brief_relative(now: datetime, then: datetime | None) -> tuple[str, float]:
    """Short relative time (no date). Returns (string, days_since).

    Used by leaderboard for compact display: 'today', '5h ago', 'yesterday', '3d ago', 'never'.
    """
    if not then:
        return "never", 999.0
    d = days_since(now, then)
    if d < 0.04:  # ~1 hour
        return "today", d
    elif d < 1:
        return f"{int(d * 24)}h ago", d
    elif d < 2:
        return "yesterday", d
    else:
        return f"{int(d)}d ago", d



def trend_icon(recent: int, previous: int) -> str:
    """Return trend emoji comparing recent vs previous period post counts."""
    if previous == 0 and recent == 0:
        return "💤"
    elif previous == 0:
        return "🆕"
    elif recent > previous * 1.15:
        return "📈"
    elif recent < previous * 0.85:
        return "📉"
    else:
        return "➡️"

# ------------------------------------------------------------------ #
#  Post deduplication and gap calculation
# ------------------------------------------------------------------ #
def deduplicate_posts(timestamps: list[datetime]) -> list[datetime]:
    """Collapse posts within POST_SESSION_MINUTES into single sessions.

    Returns the timestamp of the first post in each session.
    """
    if not timestamps:
        return []
    sorted_ts = sorted(timestamps)
    sessions = [sorted_ts[0]]
    for ts in sorted_ts[1:]:
        if (ts - sessions[-1]).total_seconds() > POST_SESSION_MINUTES * 60:
            sessions.append(ts)
    return sessions



def calc_avg_gap_str(timestamps_iso: list[str]) -> str:
    """Calculate deduped average gap from ISO timestamp strings. Returns formatted string."""
    all_posts = sorted(datetime.fromisoformat(ts) for ts in timestamps_iso)
    sessions = deduplicate_posts(all_posts)
    avg = avg_gap_hours(sessions)
    if avg is None:
        return "N/A"
    if avg < 1:
        return f"{avg * 60:.0f} minutes"
    return f"{avg:.1f} hours"
