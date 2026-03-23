"""48h nudge: @mention GM when a queue entry gets stale."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts


def _gm_mentions(config: dict, state: dict, pid: str) -> str:
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if not gm_ids:
        return "@PathWars"
    names = []
    for uid in gm_ids:
        match = next((p for p in state.get("players", {}).values()
                       if p.get("user_id") == str(uid)), None)
        if match:
            u = match.get("username", "")
            names.append(f"@{u}" if u else match.get("first_name", "@PathWars"))
        else:
            names.append("@PathWars")
    return ", ".join(names)


def check_queue_nudge(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Send a direct @mention when a queue entry crosses 48h."""
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    now = now or datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)
    if not scanned:
        return

    group_id = config["group_id"]
    nudged = state.setdefault("queue_nudged", {})

    for pid, data in scanned.items():
        gm = _gm_mentions(config, state, pid)
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name

        for entry in data["entries"]:
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):
                continue
            if hours < 48:
                continue
            nudge_key = f"{pid}:{entry['time']}"
            if nudge_key in nudged:
                continue
            user = entry.get("name", "?")
            tg.send_message(
                group_id, bot_topic,
                f"⚠️ {gm} — {user}'s message in {label} is {int(hours)}h old!")
            nudged[nudge_key] = now.isoformat()
            print(f"Queue nudge: {user} in {name} ({int(hours)}h)")

    if len(nudged) > 200:
        for k in sorted(nudged, key=lambda k: nudged[k])[:-200]:
            del nudged[k]
