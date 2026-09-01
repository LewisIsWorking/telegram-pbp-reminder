"""Utility functions split from telegram.py to stay under 200 lines."""
import json
import requests

# Telegram's own maximum for one getUpdates call. ⛔ A FULL PAGE MEANS
# THERE IS MORE WAITING, which is why dispatch/drain.py imports this
# constant instead of repeating 100: on 2026-09-01 the checker read one
# page of a several-hundred-update backlog and announced "All caught up"
# from it. A duplicated literal across a module boundary is the same
# shape that took the bot down earlier that day.
PAGE_LIMIT = 100


def fetch_updates(api_base: str, offset: int) -> list:
    """Fetch new updates from Telegram Bot API. Returns list of updates."""
    try:
        resp = requests.get(
            f"{api_base}/getUpdates",
            params={
                "offset": offset,
                "limit": PAGE_LIMIT,
                "timeout": 5,
                "allowed_updates": json.dumps(
                    ["message", "callback_query", "message_reaction",
                     "poll_answer", "poll"]
                ),
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"Error fetching updates: {e}")
        return []

    if resp.status_code != 200:
        print(f"Error fetching updates: HTTP {resp.status_code}")
        return []

    try:
        data = resp.json()
    except ValueError:
        print(f"Error parsing updates response: {resp.text[:200]}")
        return []

    if not data.get("ok"):
        print(f"Telegram API error: {data}")
        return []

    return data.get("result", [])


def message_link(group_id: int, topic_id: int, message_id: int,
                 group_username: str | None = None) -> str:
    """Build a t.me deep link to a specific message."""
    if group_username:
        return f"https://t.me/{group_username}/{topic_id}/{message_id}"
    digits = str(abs(group_id))
    if digits.startswith("100"):
        digits = digits[3:]
    return f"https://t.me/c/{digits}/{message_id}"
