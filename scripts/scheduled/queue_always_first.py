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

Lewis, 2026-11-03: "C01, C06 and C10 I think they should all be 24 hours.
C06 > C01 > C10." So all three are flagged, the wait is 24h, and the RANK
(``queue_priority``) decides: among quiet flagged campaigns the lowest rank
wins, not the quietest, and a prioritised campaign with a real owed reply
competes on the same rank. A quiet C06 beats an owed C01 reply; an owed C01
reply beats a quiet C10. A tie in rank goes to the owed reply.

Later on 2026-11-03 Lewis cut the wait to 18 hours for all three, and on
2026-11-14 he raised it to 30 hours.

Lewis, 2026-11-14: "the junction should only be in the priority queue if the
chronological queue is empty". A pair with ``queue_always_first_when_clear``
(C10) only qualifies while no campaign has an owed reply. Its rank still
orders it against the others (C06 > C01 > C10 > C11) when it does qualify,
read from its own ``queue_priority`` since the priority map leaves it out.
This is the lowest priority tier. Lewis, same day: C06 Kibwe joins it once
the campaign ends and goes into sandbox mode (set the flag on C06 then).
"""

from datetime import datetime

from commands.queue_format import build_priority_map

ALWAYS_FIRST_IDLE_HOURS = 30


def pick_always_first(config: dict, state: dict | None, scanned: dict,
                      now: datetime):
    """The quiet always-first campaign that should be the focus, or None.

    The lowest ``queue_priority`` rank wins among those that qualify (then the
    quietest). None when a prioritised campaign with an owed reply ranks as
    high or higher, so the usual pick names that reply instead.
    """
    if state is None:
        return None
    from scheduled.queue_silence_rows import idle_campaigns
    ranks = build_priority_map(config)
    queue_clear = not any(d.get("entries") for d in scanned.values())
    rows = [r for r in idle_campaigns(config, state, scanned, now)
            if r.pair.get("queue_always_first") and r.ever_posted
            and r.days * 24 >= ALWAYS_FIRST_IDLE_HOURS
            and (queue_clear or not r.pair.get("queue_always_first_when_clear"))]
    if not rows:
        return None

    def rank(r):
        qp = r.pair.get("queue_priority")
        own = qp if isinstance(qp, int) and not isinstance(qp, bool) else float("inf")
        return ranks.get(r.pid, own)

    best = min(rows, key=lambda r: (rank(r), -r.days))
    owed = [ranks[p] for p, d in scanned.items() if d.get("entries") and p in ranks]
    if owed and min(owed) <= rank(best):
        return None
    return best


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
