"""Daily pin-activity digest + real-time non-bot pin alert.

Two scheduled tasks (dispatched from ``checker.py``) that both read the
``posting.pin_audit`` trail. They exist because Telegram shows nothing
in the chat when a message is unpinned — so without these, all of the
bot's pin activity is invisible to a human watching the group.

* ``run_daily_pin_digest`` — once per day, posts a plain-language
  "Pin activity (24h)" summary to the bot topic: how many messages the
  bot pinned, unpinned, and deleted, and whether any touched a message
  the bot didn't make. Passive reassurance / trend visibility.

* ``alert_non_bot_pin_actions`` — every run, scans for any pin/unpin/
  delete the bot performed on a message it did NOT make (``bot_owned``
  is False) since the last check, and posts an immediate warning naming
  the message id and call site. In normal operation the bot only ever
  touches its own pins, so this should never fire — if it does, it is
  the vanishing-pin bug caught in the act.

Both are best-effort: a failure to post leaves the day/marker unmoved so
the next run retries, and both no-op cleanly when config lacks a bot
topic. State keys: ``last_pin_digest`` (date str) and
``last_pin_alert_ts`` (ISO timestamp marker).
"""

from datetime import datetime, timedelta, timezone

from scheduled.due import is_due

import telegram as tg
from posting import pin_audit


def _format_digest(window: list) -> str:
    """Build the daily digest message body from a 24h window of entries."""
    pins = sum(1 for e in window if e.get("action") == "pin")
    unpins = sum(1 for e in window if e.get("action") == "unpin")
    dels = sum(1 for e in window if e.get("action") == "delete")
    nonbot = [e for e in window if pin_audit.is_non_bot(e)]
    lines = [
        "📌 Pin activity — last 24h",
        "━━━━━━━━━━━━━━━━",
        f"📌 Pinned: {pins}",
        f"📍 Unpinned: {unpins}",
        f"🗑 Deleted: {dels}",
    ]
    if nonbot:
        lines.append(f"⚠️ {len(nonbot)} action(s) on NON-bot messages — "
                     f"see the alert(s) and pin_audit_log.json")
    else:
        lines.append(f"✅ All {len(window)} actions were on the bot's own "
                     f"messages. No non-bot pins touched.")
    return "\n".join(lines)


def run_daily_pin_digest(config: dict, state: dict, *,
                         now: datetime | None = None, **_kw) -> None:
    """Post the once-per-day pin-activity summary to the bot topic."""
    now = now or datetime.now(timezone.utc)
    hour = config.get("pin_digest_hour", config.get("diagnostic_hour", 8))
    # ⛔⛔ Same ten-day silent death as the diagnostic; same cause, same
    # hour. See scheduled/due.py.
    today = now.date().isoformat()
    if not is_due(now, hour, state.get("last_pin_digest")):
        return
    bot_topic = config.get("bot_topic_id")
    group_id = config.get("group_id")
    if not (bot_topic and group_id):
        return
    cutoff = (now - timedelta(hours=24)).isoformat()
    window = pin_audit.entries_since(cutoff)
    if tg.send_message(group_id, bot_topic, _format_digest(window)):
        state["last_pin_digest"] = today
        print(f"Pin digest posted ({len(window)} actions in 24h)")


def _format_alert(nonbot: list) -> str:
    """Build the real-time non-bot-action warning body."""
    lines = ["🚨 PIN GUARD ALERT",
             f"The bot acted on {len(nonbot)} message(s) it did NOT send:"]
    for e in nonbot[:20]:
        lines.append(f"• {e.get('action')} mid={e.get('message_id')} "
                     f"chat={e.get('chat_id')} refused={e.get('refused')} "
                     f"@ {str(e.get('timestamp', ''))[:19]} [{e.get('site')}]")
    lines.append("This is the vanishing-pin signal — check pin_audit_log.json.")
    return "\n".join(lines)


def alert_non_bot_pin_actions(config: dict, state: dict, *,
                              now: datetime | None = None, **_kw) -> None:
    """Alert immediately on any pin/unpin/delete of a non-bot message."""
    bot_topic = config.get("bot_topic_id")
    group_id = config.get("group_id")
    if not (bot_topic and group_id):
        return
    marker = state.get("last_pin_alert_ts", "")
    fresh = pin_audit.entries_since(marker)
    if not fresh:
        return
    newest = max(str(e.get("timestamp", "")) for e in fresh)
    nonbot = [e for e in fresh if pin_audit.is_non_bot(e)]
    if nonbot:
        if not tg.send_message(group_id, bot_topic, _format_alert(nonbot)):
            return  # leave marker unmoved so the alert retries next run
        print(f"Non-bot pin alert posted ({len(nonbot)} action(s))")
    state["last_pin_alert_ts"] = newest
