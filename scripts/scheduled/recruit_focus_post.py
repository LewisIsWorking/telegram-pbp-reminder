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
                                     _MSG_KEY, _POSTS_KEY,
                                     build_recruit_message)


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

    # ⭐ TWO destinations (Lewis, 2026-08-18): the campaign's own chat
    # topic, and the standing "What campaign needs people most?" topic in
    # Nudge Bot Notifications — the same advert, somewhere it reads as a
    # running list rather than a surprise in a game thread.
    main = tg.send_message_id(config["group_id"], thread_id, text, silent=True)
    if not main:
        return  # primary failed; keep the old copies rather than half-replace
    posted = [{"chat_id": config["group_id"], "message_id": main}]

    mirror_chat, mirror_thread = mirror_destination(config)
    if mirror_chat:
        mid = tg.send_message_id(mirror_chat, mirror_thread, text, silent=True)
        if mid:
            posted.append({"chat_id": mirror_chat, "message_id": mid})
        else:
            # The mirror is a convenience and the advert is already up
            # where it matters. Say so rather than failing the job.
            print(f"[recruit_focus] mirror post to chat {mirror_chat} failed; "
                  f"the campaign-topic advert is up.")

    _delete_previous(config, state)
    state[_POSTS_KEY] = posted
    # Legacy single id kept in step for readers that still expect it,
    # notably posting/bot_sent_state_scan.
    state[_MSG_KEY] = main
    state[_AT_KEY] = now.isoformat()
    state[_LAST_KEY] = now.isoformat()


def mirror_destination(config: dict) -> tuple[int | None, int | None]:
    """``(chat_id, thread_id)`` of the standing recruit topic, or (None, None)."""
    chat = config.get("recruit_mirror_chat_id")
    if not chat:
        return None, None
    return int(chat), config.get("recruit_mirror_thread_id")


def _delete_previous(config: dict, state: dict) -> None:
    """Remove every copy of the last advert, each from its own chat.

    ⚠️ Each entry carries its OWN chat_id, and that is load-bearing.
    Message ids are unique per CHAT, so the two copies have unrelated
    numbers — deleting the mirror's id against the main group would
    either miss entirely or hit a stranger's message that happens to
    share the number. Exactly the trap the schedule post hit on
    2026-08-17, and the reason a bare id was not enough there either.

    Falls back to the single legacy id for state written before this
    change, which was always in the main group.
    """
    entries = state.get(_POSTS_KEY)
    if entries:
        for entry in entries:
            if entry.get("message_id"):
                tg.delete_message(entry.get("chat_id") or config["group_id"],
                                  entry["message_id"])
        return
    if state.get(_MSG_KEY):
        tg.delete_message(config["group_id"], state[_MSG_KEY])


def _retire_stale_post(config: dict, state: dict, now: datetime) -> None:
    """Remove the advert once nothing is recruiting, while it still can be.

    Only acts when a post exists. Deliberately does NOT clear ``_LAST_KEY``:
    the 24h gate is about how often to advertise, not about cleanup.
    """
    if not (state.get(_POSTS_KEY) or state.get(_MSG_KEY)):
        return
    posted = state.get(_AT_KEY)
    if posted:
        try:
            if helpers.hours_since(now, datetime.fromisoformat(posted)) < 1:
                return  # posted moments ago; let it stand for now
        except (ValueError, TypeError):
            pass
    _delete_previous(config, state)
    state[_POSTS_KEY] = []
    state[_MSG_KEY] = None
    state[_AT_KEY] = None
