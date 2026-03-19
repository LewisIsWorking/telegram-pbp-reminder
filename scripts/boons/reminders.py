"""Boon reminder and expiry notifications."""

from datetime import datetime, timezone

import helpers
import telegram as tg


def check_boon_reminders(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Send reminders for unclaimed boons and notify on auto-expiry.

    Timeline:
      24h  — first reminder
      3d   — second reminder
      7d   — auto-pick boon #1, notify winner
    """
    from boons.handler import _resolve_boon

    now = now or datetime.now(timezone.utc)
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    pending = state.get("pending_potw_boons", {})

    for topic_id in list(pending.keys()):
        entry = pending[topic_id]
        posted_at = datetime.fromisoformat(entry["posted_at"])
        elapsed = helpers.hours_since(now, posted_at)
        campaign = entry.get("campaign_name", "Unknown")
        winner_uid = entry["winner_user_id"]

        # Find winner's mention
        winner_mention = winner_uid
        for key, p in state.get("players", {}).items():
            if p.get("user_id") == winner_uid:
                winner_mention = helpers.player_mention(p)
                break

        reply_to = bot_topic or int(topic_id)
        reminders_sent = entry.get("reminders_sent", 0)

        # 7 days — auto-pick
        if elapsed >= 168:
            new_text, _ = _resolve_boon(state, topic_id, 0, "Boon (auto-selected)", now)
            if new_text:
                tg.edit_message(group_id, entry["message_id"], new_text,
                                parse_mode="HTML", remove_keyboard=True)
            tg.send_message(group_id, reply_to,
                            f"⏰ {winner_mention}'s boon in {campaign} was auto-selected "
                            f"(boon #1) after 7 days with no response.")
            del pending[topic_id]
            print(f"POTW boon auto-expired for topic {topic_id}, picked #1")
            continue

        # 3 days — second reminder
        if elapsed >= 72 and reminders_sent < 2:
            tg.send_message(group_id, reply_to,
                            f"⚠️ {winner_mention} — pick your boon for {campaign}!\n"
                            f"Use /chooseboon [number] in the {campaign} PBP topic.")
            entry["reminders_sent"] = 2
            print(f"Boon reminder #2 (3d) for topic {topic_id}")
            continue

        # 24h — gentle reminder
        if elapsed >= 24 and reminders_sent < 1:
            tg.send_message(group_id, reply_to,
                            f"🎁 {winner_mention} — you have an unclaimed boon for {campaign}!\n"
                            f"Scroll up to pick one, or use /chooseboon [number] in the PBP topic.")
            entry["reminders_sent"] = 1
            print(f"Boon reminder #1 (24h) for topic {topic_id}")
