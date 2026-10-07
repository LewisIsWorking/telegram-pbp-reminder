"""Campaigns the GM always works first, even when nobody is marked waiting.

Lewis, 2026-10-07: "We should ALWAYS prioritise Kibwe." The trigger was a
Kibwe combat: the GM posted "ROUND 2: ENEMY PHASE!" and the next move was
his, but the queue only counts unanswered PLAYER posts, so Kibwe was nowhere
in it for three days while the focus pointed at other campaigns.

A topic_pair with ``queue_always_first: true`` is handled in two ways:

  * With unreplied entries it wins through ``queue_priority`` (Kibwe is rank
    0, ahead of every other prioritised campaign). Nothing here is needed.
  * With none, once it has been quiet for ``ALWAYS_FIRST_IDLE_HOURS`` it is
    the focus over everything else, including owed replies elsewhere. The
    bot cannot tell whose move it is, so the message says to check.

The wait stops a turn the GM just handed to the players from jumping
straight back to the top of the queue.
"""

from datetime import datetime

ALWAYS_FIRST_IDLE_HOURS = 12


def pick_always_first(config: dict, state: dict | None, scanned: dict,
                      now: datetime):
    """The quiet always-first campaign that should be the focus, or None.

    Several qualify only if several are flagged; the quietest wins.
    """
    if state is None:
        return None
    from scheduled.queue_silence_rows import idle_campaigns
    rows = [r for r in idle_campaigns(config, state, scanned, now)
            if r.pair.get("queue_always_first") and r.ever_posted
            and r.days * 24 >= ALWAYS_FIRST_IDLE_HOURS]
    return max(rows, key=lambda r: r.days) if rows else None


def always_first_message(row) -> str:
    """The focus message for a quiet always-first campaign."""
    lines = ["━━━━━━━━━━━━━━━━",
             f"🎯 Post here next: {row.icon} {row.prefix}{row.label}",
             f"📌 Always first, and quiet for {row.age}.",
             "Nothing there is marked unreplied, so check whether the next "
             "move is yours."]
    if row.link.strip():
        lines.append(row.link.strip())
    return "\n".join(lines)
