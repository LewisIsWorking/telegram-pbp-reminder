"""Helper for posting the "All caught up!" notification.

Extracted from ``queue_reminder.py`` on 2026-05-12 to keep that
file under the 200-line cap after both empty-queue branches got
their fix for the orphan-GM-queue bug Lewis flagged at queue
#382. The helper exists only to dedupe the call from both
branches; nothing else uses it.

Why route through ``gm_queue_history.post_and_persist`` instead
of plain ``tg.send_message``: post_and_persist updates
``state["gm_queue_history"]`` and evicts the previous batch (its
chat messages get deleted). That's what makes the previous GM
queue go away when the caught-up message lands. Pre-2026-05-12
this used ``tg.send_message`` directly, so the previous GM queue
orphaned in chat \u2014 visible alongside the caught-up message and
never auto-evicted.

Pin=False on this path: the caught-up notification is
informational, not a sticky reference like the queue itself. The
``post_and_persist`` ``pin`` parameter exists specifically for
this caller. See ``scheduled/gm_queue_history.py`` for the
pin-param contract and the eviction semantics.
"""

from scheduled.gm_queue_history import post_and_persist


CAUGHT_UP_TEXT = (
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
    "\U0001f4cb All caught up! No unreplied messages."
)


def post_caught_up(state: dict, group_id: int, bot_topic: int,
                   age_lines: list[str] | None = None,
                   oldest_line: str | None = None) -> None:
    """Post the caught-up notification via the batch machinery.

    ``age_lines`` (from ``queue_silence.campaign_age_lines``) is appended so a
    cleared queue still reports how long each campaign has been quiet. Without
    it the message says only that there is nothing to reply to, which tells the
    GM nothing about which game has gone stale.

    ``oldest_line`` (from ``queue_silence.oldest_campaign_line``) names the
    single campaign that has gone longest without a post. A populated queue
    ends with the "Reply to this next" focus message, which is built from
    unreplied entries — so an empty queue has nothing pointing anywhere. This
    is the empty-queue equivalent: one clear next action instead of a list the
    GM has to scan and rank themselves.
    """
    text = CAUGHT_UP_TEXT
    if age_lines:
        text += "\n\n━━ 🕒 Time since last post ━━\n"
        text += "\n".join(age_lines)
    if oldest_line:
        text += "\n\n" + oldest_line
    post_and_persist(state, group_id, bot_topic, [text], pin=False)
