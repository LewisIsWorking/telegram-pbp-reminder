"""
Helpers: mechanics.
"""

import re
from datetime import datetime, timezone, timedelta



def parse_timer_duration(text: str, now: datetime) -> tuple:
    """Parse a timer duration string into (deadline_datetime, reason).

    Supports: "24h", "2h", "30m", "1d", "48h post your actions"
    Returns (None, reason) if parsing fails.
    """
    if not text.strip():
        return None, ""

    parts = text.strip().split(None, 1)
    dur_str = parts[0].lower()
    reason = parts[1] if len(parts) > 1 else ""

    # Try patterns: Nh, Nm, Nd
    m = re.match(r'^(\d+)(h|m|d)$', dur_str)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit == 'h':
            delta = timedelta(hours=amount)
        elif unit == 'm':
            delta = timedelta(minutes=amount)
        elif unit == 'd':
            delta = timedelta(days=amount)
        else:
            return None, text.strip()

        if amount <= 0 or amount > 168:  # Max 1 week
            return None, text.strip()
        return now + delta, reason

    return None, text.strip()

# ------------------------------------------------------------------ #
#  HP Bar rendering
# ------------------------------------------------------------------ #
def hp_bar(current: int, maximum: int, width: int = 10) -> str:
    """Render an HP bar like [████████░░] 80/100."""
    if maximum <= 0:
        return f"[{'░' * width}] 0/0"
    current = max(0, min(current, maximum))
    filled = round(current / maximum * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{maximum}"



def hp_status_icon(current: int, maximum: int) -> str:
    """Get a status icon based on HP percentage."""
    if maximum <= 0:
        return "💀"
    pct = current / maximum
    if pct <= 0:
        return "💀"
    elif pct <= 0.25:
        return "🔴"
    elif pct <= 0.5:
        return "🟠"
    elif pct <= 0.75:
        return "🟡"
    else:
        return "🟢"

# ------------------------------------------------------------------ #
#  Progress Clock rendering
# ------------------------------------------------------------------ #
def clock_display(filled: int, segments: int) -> str:
    """Render a progress clock like ◉◉◉○○○ 3/6."""
    filled = max(0, min(filled, segments))
    display = "◉" * filled + "○" * (segments - filled)
    return f"{display} {filled}/{segments}"



def calc_streak(raw_timestamps: list[str], now: datetime) -> int:
    """Count consecutive days with at least one post, ending at today or yesterday.

    Returns 0 if no recent posts, otherwise the number of consecutive days.
    """
    if not raw_timestamps:
        return 0

    # Get unique posting dates
    post_dates = sorted({datetime.fromisoformat(ts).date() for ts in raw_timestamps})
    today = now.date()

    # Streak must include today or yesterday
    if post_dates[-1] < today - timedelta(days=1):
        return 0

    # Count backward from the most recent post date
    streak = 1
    for i in range(len(post_dates) - 1, 0, -1):
        gap = (post_dates[i] - post_dates[i - 1]).days
        if gap == 1:
            streak += 1
        elif gap == 0:
            continue  # Same day, skip
        else:
            break

    return streak



_HEALTH_THRESHOLDS = [(20, "🟢"), (10, "🟡"), (5, "🟠"), (0, "🔴")]



def health_icon(total_posts_7d: int) -> str:
    """Return a traffic-light icon based on weekly post volume."""
    for threshold, icon in _HEALTH_THRESHOLDS:
        if total_posts_7d >= threshold:
            return icon
    return "🔴"
