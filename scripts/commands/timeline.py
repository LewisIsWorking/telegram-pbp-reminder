"""
Cross-campaign timeline.

/timeline shows recent events across all campaigns.
/event <text> logs a GM story beat for the current campaign.
"""

from datetime import datetime, timezone

import helpers


def build_timeline(config: dict, state: dict, count: int = 20) -> str:
    """Build /timeline output: recent events across all campaigns."""
    now = datetime.now(timezone.utc)
    maps = helpers.build_topic_maps(config)
    events = []

    # Manual events
    for pid, entries in state.get("timeline_events", {}).items():
        name = maps.to_name.get(pid, pid)
        for e in entries:
            events.append({
                "time": e["time"],
                "icon": "📜",
                "text": f"[{name}] {e['text']}",
            })

    # POTW winners from boon data
    for pid, users in state.get("player_boons", {}).items():
        name = maps.to_name.get(pid, pid)
        for uid, boons in users.items():
            for b in boons:
                events.append({
                    "time": b["date"] + "T00:00:00+00:00",
                    "icon": "🏅",
                    "text": f"[{name}] POTW: {b.get('campaign', name)} ({b.get('week', '?')})",
                })

    # Player removals
    for key, data in state.get("removed_players", {}).items():
        ts = data.get("removed_at", "")
        if ts:
            events.append({
                "time": ts,
                "icon": "👋",
                "text": f"[{data.get('campaign_name', '?')}] {data['first_name']} removed",
            })

    # Campaign creation dates
    for pair in config.get("topic_pairs", []):
        created = pair.get("created", "")
        if created:
            events.append({
                "time": created + "T00:00:00+00:00",
                "icon": "🎬",
                "text": f"[{pair['name']}] Campaign started",
            })

    if not events:
        return "No timeline events yet. GMs can add events with /event <text>"

    # Sort newest first, limit
    events.sort(key=lambda e: e["time"], reverse=True)
    events = events[:count]

    lines = ["📅 Cross-Campaign Timeline:\n"]
    for e in events:
        try:
            dt = datetime.fromisoformat(e["time"])
            date_str = dt.strftime("%b %d")
        except (ValueError, TypeError):
            date_str = "?"
        lines.append(f"{e['icon']} {date_str} — {e['text']}")

    return "\n".join(lines)


def add_event(pid: str, campaign_name: str, text: str,
              state: dict, now: datetime | None = None) -> str:
    """Add a manual timeline event. Returns confirmation message."""
    now = now or datetime.now(timezone.utc)
    if not text.strip():
        return "Usage: /event <description>"

    events = state.setdefault("timeline_events", {}).setdefault(pid, [])
    events.append({
        "time": now.isoformat(),
        "text": text.strip(),
        "author": campaign_name,
    })

    # Cap at 50 events per campaign
    if len(events) > 50:
        state["timeline_events"][pid] = events[-50:]

    return f"📜 Event logged for {campaign_name}: {text.strip()}"
