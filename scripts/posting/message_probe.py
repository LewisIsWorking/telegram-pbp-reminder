"""Ask Telegram whether a message still exists, without changing anything.

Shared by ``maintenance/audit_orphans.py`` (did a delete the bot claimed
really happen?) and ``commands/queue_prune.py`` (has a player deleted a
post the GM queue is still waiting on?). Telegram never tells a bot that
a message was deleted, so asking is the only way to find out.

The probe. ``setMessageReaction`` with an empty reaction list removes the
**bot's own** reaction to a message. This bot has never reacted to
anything, so the call is a no-op: nothing changes, nobody is notified.
The response still distinguishes the two cases, which is all we need:

    "message to react not found"  -> GONE    (False)
    network error, 429, junk body -> UNKNOWN (None)
    anything else                 -> EXISTS  (True)

Only the exact "message to react not found" answer counts as gone. A
looser "not found" match would also catch "chat not found", and a wrong
chat id would then wipe a whole campaign's queue.

⚠️ Do NOT be tempted back to ``editMessageReplyMarkup`` for this. It
reads as harmless and it is not: ``telegram.send_button_message`` sends
inline keyboards, and an empty-markup edit on one of those would strip
its buttons and break an interactive message. Verified 2026-08-16.

⚠️ Never call ``getUpdates`` from here. Doing so would consume the bot's
update offset and make the live poller miss real player messages.
"""

import requests

GONE_MARKER = "message to react not found"


def message_exists(api: str, chat_id: int, message_id: int,
                   timeout: int = 20) -> bool | None:
    """True if the message exists, False if Telegram says it is gone,
    None when the answer could not be obtained (network, rate limit)."""
    try:
        r = requests.post(f"{api}/setMessageReaction",
                          json={"chat_id": chat_id,
                                "message_id": int(message_id),
                                "reaction": []}, timeout=timeout)
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  probe {message_id}: no answer, skipped "
              f"({type(e).__name__})")
        return None
    if not isinstance(body, dict):
        return None
    if body.get("ok"):
        return True
    description = str(body.get("description", ""))
    if GONE_MARKER in description:
        return False
    if (body.get("error_code") == 429 or "FLOOD" in description.upper()
            or "Too Many" in description):
        print(f"  probe {message_id}: rate limited, skipped")
        return None
    # Any other error still proves Telegram found the message.
    return True
