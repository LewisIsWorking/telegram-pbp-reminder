"""Silent campaign detection for the GM queue.

A campaign is considered silent when:
  - It has zero unreplied entries in the GM queue, AND
  - Its RP topic has had no messages for 10 or more days.
"""

from datetime import datetime

from commands.queue_format import entry_age_icon

_SILENCE_THRESHOLD_DAYS = 10


def silent_campaigns(config: dict, state: dict,
                     scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns that are silently inactive.

    Each line is ready to append directly to the GM queue message.
    """
    lines = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        # Skip if the campaign has unreplied entries — it is not silent
        if pid in scanned and scanned[pid].get("entries"):
            continue
        last_str = (state.get("topics", {})
                        .get(pid, {})
                        .get("last_message_time"))
        if not last_str:
            continue
        try:
            last_dt = datetime.fromisoformat(last_str)
            days = (now - last_dt).total_seconds() / 86400
        except (ValueError, TypeError):
            continue
        if days < _SILENCE_THRESHOLD_DAYS:
            continue
        code = pair.get("code", "")
        name = pair.get("name", pid)
        emoji = pair.get("emoji", "")
        label = f"{code}: {name}" if code else name
        prefix = f"{emoji} " if emoji else ""
        icon = entry_age_icon(int(days) * 24)
        lines.append(f"  {icon} {prefix}{label} — no posts for {int(days)}d")
    return lines
