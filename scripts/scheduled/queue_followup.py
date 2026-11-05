"""The "go here next" follow-up appended to a GM queue post.

There are two candidates and they answer the same question from
different evidence:

``queue_focus.build_focus_message``   reads unreplied entries and names
                                     the campaign owed a reply longest.
``queue_silence.oldest_campaign_line`` reads last-post times and names
                                     the campaign quiet longest.

The first is more specific and wins whenever it has anything to say. It
only goes quiet when nothing is owed a reply at all, and that is exactly
when the second one is the useful answer.

⚠️ **Extracted 2026-08-25 because a queue post reached neither.**
``queue_reminder`` has three exits: two caught-up early returns and the
full queue post. Both early returns were guarded by
``and not silent_lines`` and were the only places the oldest-campaign
callout was reachable from. An empty queue WITH a silent campaign
satisfied neither guard, fell through to the full post, and got only the
reply focus, which returns "" when nothing is unreplied.

So queue #1452 read ``Unreplied: 0``, listed C05 Grand Explorers as
silent for 5d 19h, and pointed nowhere. Lewis reported it the same
morning.

The fix is not the fallback line, it is this module: every exit now asks
ONE function what to point at, so a fourth exit added later cannot
forget one of the two candidates. See ``a-guard-nothing-invokes`` -- the
callout was written, correct and tested, and simply not reachable.

**Split by campaign (Lewis, 2026-11-05).** "Could these messages be 2 split
messages when they are 2 different campaigns but 1 unified message when they
are the same campaign?" The reply focus carries two answers since
2026-11-03: the PRIORITY pick and the oldest post waiting anywhere. On the
queue post, ``followup_messages`` sends them as two Telegram messages when
they name different campaigns, and as one when they name the same campaign
(or the same post, which is the one ``SAME_POST_LINE``).

No new state is needed for the second message. It is one more message in
the queue's own batch (``gm_queue_history``), so it is sent, recorded in the
bot-sent registry, edited in place and evicted exactly like the queue
chunks. When the split comes or goes, the batch's message count changes,
``queue_refresh.refresh_in_place`` refuses to pair texts by index, and the
whole batch is reposted, deleting the old one with it. Nothing is orphaned.
"""

from datetime import datetime

from scheduled.queue_focus import build_focus_message, focus_parts
from scheduled.queue_oldest_waiting import pick_oldest_waiting
from scheduled.queue_silence import oldest_campaign_line


def build_followup(config: dict, state: dict, scanned: dict,
                   priority_map: dict, now: datetime) -> str:
    """Return the follow-up message for this queue post, or "".

    Exactly one, never both: two "go here next" instructions in one post
    is one too many, and when the queue is thin they can disagree.

    Returns "" only when there is genuinely nothing to point at, which
    means no unreplied entries AND no campaign with a recorded last
    post. A caller should treat "" as "append nothing", not as an error.
    """
    focus = build_focus_message(config, scanned, priority_map, now, state=state)
    if focus:
        return focus
    return oldest_campaign_line(config, state, scanned, now) or ""


def followup_messages(config: dict, state: dict, scanned: dict,
                      priority_map: dict, now: datetime) -> list:
    """The follow-up for a queue post as Telegram messages: 0, 1 or 2.

    Two only when the priority pick and the oldest post waiting are in
    different campaigns: the pick first, then the oldest-waiting lines on
    their own. Otherwise exactly what ``build_followup`` returns, as one.
    """
    pick, pick_pid, oldest = focus_parts(config, scanned, priority_map, now,
                                         state=state)
    if pick and oldest:
        waiting = pick_oldest_waiting(scanned)
        if waiting is not None and waiting[0] != pick_pid:
            return [pick, "\n".join(oldest)]
    text = build_followup(config, state, scanned, priority_map, now)
    return [text] if text else []
