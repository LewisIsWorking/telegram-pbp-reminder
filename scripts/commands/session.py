"""
Session counter per campaign.

Auto-increments when the GM posts on a new calendar day.
/session shows current count. /session set N overrides.
"""

from datetime import datetime, timezone


def track_session(pid: str, user_id: str, gm_ids: set,
                  msg_time_iso: str, state: dict) -> None:
    """Increment session counter when GM posts on a new day."""
    if user_id not in gm_ids:
        return

    sessions = state.setdefault("session_counts", {})
    last_days = state.setdefault("session_last_day", {})

    msg_date = msg_time_iso[:10]  # YYYY-MM-DD
    last_day = last_days.get(pid, "")

    if msg_date != last_day:
        sessions[pid] = sessions.get(pid, 0) + 1
        last_days[pid] = msg_date


def build_session(pid: str, campaign_name: str, state: dict,
                  config: dict) -> str:
    """Build /session output."""
    code = ""
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            code = pair.get("code", "")
            break

    count = state.get("session_counts", {}).get(pid, 0)
    label = f"{code}: {campaign_name}" if code else campaign_name

    if count == 0:
        return f"No sessions tracked yet for {label}. Use /session set N to initialize."

    return f"📖 {label} — Session {count}"


def set_session(pid: str, campaign_name: str, number: int,
                state: dict) -> str:
    """Set session counter manually."""
    state.setdefault("session_counts", {})[pid] = number
    return f"📖 Session counter set to {number} for {campaign_name}."
