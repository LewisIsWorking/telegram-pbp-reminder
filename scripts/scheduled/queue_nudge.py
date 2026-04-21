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
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
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

        nudged_players = set()  # one nudge per player per campaign
        for entry in data["entries"]:
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):
                continue
            if hours < 48:
                continue
            user = entry.get("name", "?")
            player_key = f"{pid}:{user}"
            if player_key in nudged_players or player_key in nudged:
                continue
            nudged_players.add(player_key)
            count = sum(1 for e in data["entries"]
                        if e.get("name") == user)
            count_str = f" ({count} messages)" if count > 1 else ""
            link = entry.get("link", "")
            link_str = f"\n🔗 {link}" if link else ""
            tg.send_message(
                group_id, bot_topic,
                f"━━━━━━━━━━━━━━━━\n"
                f"⚠️ {gm} — {user}'s message in {label} "
                f"is {int(hours)}h old!{count_str}{link_str}")
            nudged[player_key] = now.isoformat()
            print(f"Queue nudge: {user} in {name} ({int(hours)}h)")

    if len(nudged) > 200:
        for k in sorted(nudged, key=lambda k: nudged[k])[:-200]:
            del nudged[k]
