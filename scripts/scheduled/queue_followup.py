"""The single "go here next" message appended to a GM queue post.

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
"""

from datetime import datetime

from scheduled.queue_focus import build_focus_message
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
    focus = build_focus_message(config, scanned, priority_map, now)
    if focus:
        return focus
    return oldest_campaign_line(config, state, scanned, now) or ""
