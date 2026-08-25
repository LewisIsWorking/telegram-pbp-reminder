"""Is the table we are about to advertise actually alive?

``recruit_focus`` answers "which campaign has the biggest gap", and that
is the right question for the in-group advert, where everyone reading it
already knows the table. It is the WRONG question on its own for an
external advert, because the biggest gap and the deadest table are the
same campaign more often than not: seats empty because nobody is posting,
and nobody is posting because seats are empty.

Advertising a dormant table is worse than not advertising. The joiner
writes an introduction, gets one GM reply, waits a fortnight, and leaves,
and the recruitment log records that as **the venue failing**, which is
how a good venue gets dropped for a table problem. See
``a-measurement-that-blames-the-wrong-subject``.

⚠️ This deliberately reads ``last_post_time`` directly rather than going
through ``roster_members._active_players``. That function counts a
permanent player regardless of when they last posted, which is correct
and intentional for "who is on the roster" (see the L20 note there) and
wrong here. "Is anyone actually posting" is a different question from
"who is enrolled", and the permanent flag is an answer to the second.
Do NOT swap this for ``_active_players``.
"""

from datetime import datetime, timezone

# A table with no player post in this long is not ready for a new
# arrival. Two weeks is one full round-trip of a slow play-by-post
# exchange, so it clears an ordinary quiet week without clearing a
# stall.
QUIET_DAYS = 14


def _seat_posts(pair: dict, state: dict) -> list:
    """Every ``last_post_time`` among this campaign's seats.

    All of ``pbp_topic_ids``, not just the first: a campaign with two
    tables is alive if either one is posting, and ``_shortfall`` only
    looking at ``[0]`` is a seat-counting decision, not a liveness one.
    """
    wanted = {str(t) for t in pair.get("pbp_topic_ids") or []}
    return [seat["last_post_time"] for seat in (state.get("players") or {}).values()
            if str(seat.get("pbp_topic_id")) in wanted and seat.get("last_post_time")]


def days_since_a_player_posted(pair: dict, state: dict,
                               now: datetime | None = None) -> float | None:
    """Days since the newest PLAYER post, or None if there are none.

    None means "no seated player has ever posted", which is not zero and
    not "fine". A campaign with no seats at all lands here too, and both
    cases deserve the warning rather than a silent pass.
    """
    now = now or datetime.now(timezone.utc)
    newest = None
    for stamp in _seat_posts(pair, state):
        try:
            when = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if newest is None or when > newest:
            newest = when
    if newest is None:
        return None
    return max(0.0, (now - newest).total_seconds() / 86400.0)


def is_quiet(pair: dict, state: dict, now: datetime | None = None) -> bool:
    """True when this table should be woken before it is advertised."""
    quiet_for = days_since_a_player_posted(pair, state, now)
    return quiet_for is None or quiet_for >= QUIET_DAYS


def warning(pair: dict, state: dict, now: datetime | None = None) -> str:
    """The line to show above the venue list, or "" when the table is fine.

    Returns advice, not a refusal. The GM knows things this does not
    (a table can be quiet because everyone agreed to pause), so this
    never blocks the advert, it only makes the risk visible before the
    post goes out rather than after the joiner has left.
    """
    if not is_quiet(pair, state, now):
        return ""
    quiet_for = days_since_a_player_posted(pair, state, now)
    if quiet_for is None:
        measured = "no seated player has ever posted here"
    else:
        measured = f"no player has posted for {quiet_for:.0f} days"
    return (f"\n⚠️ This table is quiet: {measured}. A new arrival posts an "
            f"introduction, hears nothing, and leaves, and the yield log "
            f"blames the venue for it. Consider waking the seated players "
            f"first, or advertise anyway knowing the first reply has to "
            f"come fast.")
