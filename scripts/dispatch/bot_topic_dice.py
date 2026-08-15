"""``/roll`` and ``/dc`` from the bot topic.

Extracted from ``dispatch/bot_topic.py`` on 2026-08-15, which had reached
214 lines against the 200 limit.

This pair was chosen over the other contextless branches because it is the
only one that is **unconditionally terminal** — it always answers and always
returns. ``/mystats``, ``/me`` and ``/waiting`` deliberately *fall through*
to normal campaign handling when given an argument, so lifting them would
have meant inventing a handled/not-handled protocol and getting the
fall-through right in a mechanical edit. Not worth the risk for 15 lines.
"""

import re
from datetime import datetime, timezone  # noqa: F401  (parity with caller)

import helpers
import telegram as tg


def handle_dice(cmd_word: str, args: str, msg: dict, maps,
                group_id: int, bot_topic: int, user_name: str) -> None:
    """Answer ``/roll`` or ``/dc``. Always terminal — the caller returns."""
    print(f"Bot topic: {cmd_word} from {user_name}: {args}")
    pid = next(iter(maps.to_name), None)
    if not pid:
        return  # pragma: no cover
    raw_text = msg.get("text", "").strip()
    if cmd_word == "/dc":
        mention = f"@{user_name}" if user_name else user_name
        tg.send_message(group_id, bot_topic,
                        f"The DC is a mystery to be revealed later in the "
                        f"campaign! {mention}")
        return

    dice = re.sub(r"^/roll(@\S+)?", "", raw_text).strip()
    result = helpers.roll_dice(dice) if dice else None
    if not result or not dice:
        tg.send_message(group_id, bot_topic,
                        "Usage: /roll [dice] [label]\n"
                        "e.g. /roll 1d20+5 Stealth\n"
                        "e.g. /roll 4d6kh3")
        return
    if result.get("error"):
        tg.send_message(group_id, bot_topic, result["error"])
        return
    label = result["label"]
    header = f"🎲 {user_name}"
    if label:
        header += f" — {label}"
    header += ":"
    r = result["results"][0]
    tg.send_message(group_id, bot_topic,
                    f"{header}\n  {r['detail']} = {r['total']}")
