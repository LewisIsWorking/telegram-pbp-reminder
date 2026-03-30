"""
Weekly swimming poll — posted Sunday in the Dark Pockets main chat.

Separate from the session polls; this is a social/logistics poll for
a regular swim session. Pings 7 players weekly to find the best day.
"""

from datetime import datetime, timezone

import telegram as tg
from scheduled.session_poll_build import sunday_week_key

# Dark Pockets group — main chat is thread_id 1
_GROUP_ID  = -1003496373617
_TOPIC_ID  = 1

# Known real IDs; placeholders (9000000xxx) replaced as players vote
_SWIMMERS: list[tuple[int, str]] = [
    (8018921976,   "NitNatty"),       # Natasha  ✅ real
    (6452663252,   "JackGrah"),       # Jack     ✅ real
    (9000000008,   "EliciaRoseT"),    # Elicia   ⏳ placeholder
    (9100000001,   "deft_369"),       # ⏳ placeholder
    (9100000002,   "Verminatrix"),    # ⏳ placeholder
    (9100000003,   "anweshaborah190"),# ⏳ placeholder
    (9100000004,   "TwoBad22"),       # ⏳ placeholder
]

_OPTIONS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "Can't make it",
]


def post_swimming_poll(config: dict, state: dict, *,
                       now: datetime | None = None, **_kw) -> None:
    """Post weekly swimming poll on Sunday at poll_post_hour UTC."""
    now = now or datetime.now(timezone.utc)

    if now.weekday() != 6:
        return

    post_hour = config.get("poll_post_hour", 7)
    if now.hour < post_hour:
        return

    week_key = sunday_week_key(now)
    swim_state = state.setdefault("swimming_poll", {})
    if swim_state.get("week_iso") == week_key:
        return

    week_num = now.isocalendar()[1]
    question = f"🏊 Week {week_num}/52 — Swimming this week?"

    result = tg.send_poll(
        _GROUP_ID, _TOPIC_ID, question, _OPTIONS,
        is_anonymous=False, allows_multiple_answers=True,
    )
    msg_id, poll_id = result if result else (None, None)
    if not msg_id:
        return

    tg.pin_message(_GROUP_ID, msg_id)

    swim_state.update({
        "week_iso":       week_key,
        "poll_id":        poll_id or "",
        "poll_message_id": msg_id,
        "voted_uids":     [],
        "last_ping_day":  -1,
    })
    print(f"Swimming poll posted + pinned (W{week_num})")

    # Daily ping next day onwards handled by post_swimming_ping


def post_swimming_ping(config: dict, state: dict, *,
                       now: datetime | None = None, **_kw) -> None:
    """Ping unvoted swimmers daily (Mon–Sat after Sunday poll)."""
    now = now or datetime.now(timezone.utc)

    swim_state = state.get("swimming_poll", {})
    week_key = sunday_week_key(now)
    if swim_state.get("week_iso") != week_key:
        return

    today_ord = now.toordinal()
    if today_ord <= swim_state.get("last_ping_day", -1):
        return

    voted = set(str(u) for u in swim_state.get("voted_uids", []))
    unvoted = []
    for uid, uname in _SWIMMERS:
        if str(uid) not in voted:
            unvoted.append(f"@{uname}")

    if not unvoted:
        return

    link = ""
    msg_id = swim_state.get("poll_message_id")
    if msg_id:
        link = f"\n🔗 https://t.me/c/3496373617/{msg_id}"

    week_num = now.isocalendar()[1]
    msg = (f"━━━━━━━━━━━━━━━━\n"
           f"🏊 Week {week_num}/52 — Vote in the swimming poll!{link}\n\n"
           f"Waiting on:\n" + "\n".join(unvoted))

    if tg.send_message(_GROUP_ID, _TOPIC_ID, msg):
        swim_state["last_ping_day"] = today_ord
        print(f"Swimming poll ping sent (W{week_num})")
