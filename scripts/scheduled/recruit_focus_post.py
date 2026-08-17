"""Where the recruit advert goes, and when it comes down.

Extracted from ``scheduled/recruit_focus.py`` on 2026-08-17 at 262 lines.
That module answers **which campaign needs players**; this one answers
**where to put the advert and how long it lives**. The split fell here
because moving the post into each campaign's chat topic made the second
question big enough to have its own file.

The two halves meet at ``build_recruit_message``, which returns the text
AND the campaign — one decision, one return value, so the destination can
never disagree with the words.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from scheduled.recruit_focus import (_AT_KEY, _GATE_HOURS, _LAST_KEY,
                                     _MSG_KEY, build_recruit_message)


def recruit_destination(pair: dict, config: dict) -> tuple[int | None, bool]:
    """``(thread_id, is_the_campaign_topic)`` for a recruit post.

    The post goes into **the campaign's own chat topic** (2026-08-17):
    telling the people already at that table that it has empty seats is
    what actually recruits, and the GM queue is read by one person who
    already knows.

    Falls back to the GM queue when a campaign has no ``chat_topic_id``,
    and returns False so the caller can say so out loud. A silent fallback
    would put the post back where it started and look like it worked —
    the campaign nobody can see is exactly the one that needed the advert.
    """
    topic = pair.get("chat_topic_id")
    if topic:
        return int(topic), True
    return config.get("gm_queue_topic_id") or config.get("bot_topic_id"), False


def post_recruit_focus(config: dict, state: dict, *,
                       now: datetime | None = None, **_kw) -> None:
    """Post once per 24h into the neediest campaign's chat topic.

    Send first, then delete, so a failed send never leaves the topic with
    no recruit post at all — same ordering as ``schedule_post``.

    The previous post may be in a DIFFERENT topic to the new one, because
    the neediest campaign changes. That costs nothing to handle: message
    ids are unique per chat, not per topic, and every campaign topic lives
    in the same group — so the delete finds it wherever it sat. (Contrast
    ``schedule_post``, which moved to another *chat* and therefore had to
    record which one.)
    """
    now = now or datetime.now(timezone.utc)
    if not config.get("recruit_focus_enabled", True):
        return

    last = state.get(_LAST_KEY)
    if last:
        try:
            since = helpers.hours_since(now, datetime.fromisoformat(last))
        except (ValueError, TypeError):
            since = _GATE_HOURS
        if since < _GATE_HOURS:
            return

    text, pair = build_recruit_message(config, state)
    if not text or not pair:
        # Every campaign is full. Take the stale advert down rather than
        # leaving it: it says "4 seats open" and that is no longer true.
        # ⚠️ It also has to come down BEFORE it is 48h old — past that
        # Telegram will not let the bot delete its own message at all, and
        # a permanently stranded "seats open" post in a full campaign's
        # chat is worse than one that lingers a day.
        _retire_stale_post(config, state, now)
        return

    thread_id, own_topic = recruit_destination(pair, config)
    if not thread_id:
        return
    if not own_topic:
        print(f"[recruit_focus] {pair.get('code', '?')} has no chat_topic_id; "
              f"posting to the GM queue instead. Players of that campaign "
              f"will not see it, which is the one thing this post is for.")

    msg_id = tg.send_message_id(config["group_id"], thread_id, text,
                                silent=True)
    if not msg_id:
        return
    prev = state.get(_MSG_KEY)
    if prev:
        tg.delete_message(config["group_id"], prev)
    state[_MSG_KEY] = msg_id
    state[_AT_KEY] = now.isoformat()
    state[_LAST_KEY] = now.isoformat()


def _retire_stale_post(config: dict, state: dict, now: datetime) -> None:
    """Remove the advert once nothing is recruiting, while it still can be.

    Only acts when a post exists. Deliberately does NOT clear ``_LAST_KEY``:
    the 24h gate is about how often to advertise, not about cleanup.
    """
    prev = state.get(_MSG_KEY)
    if not prev:
        return
    posted = state.get(_AT_KEY)
    if posted:
        try:
            if helpers.hours_since(now, datetime.fromisoformat(posted)) < 1:
                return  # posted moments ago; let it stand for now
        except (ValueError, TypeError):
            pass
    tg.delete_message(config["group_id"], prev)
    state[_MSG_KEY] = None
    state[_AT_KEY] = None
