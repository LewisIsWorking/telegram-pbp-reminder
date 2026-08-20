"""The two recruitment commands that WRITE: /recruitposted, /recruitjoined.

Split from the read-only pair in ``cmd_info_ext`` because these mutate the
yield figures that decide where the next hour of effort goes. A player
crediting the wrong venue would quietly steer the whole search, so both
are GM-only.

⚠️ Both refuse an unknown venue id rather than inventing one. Accepting a
typo would create a venue that exists only in the log, is in no catalogue,
has no cooldown, and shows up in the yield table as a real result.
"""

import telegram as tg
from recruiting import catalogue, log


def _venue_ids(venues: list) -> str:
    return ", ".join(v["id"] for v in catalogue.postable(venues))


def handle_recruit_write(cmd: str, ctx: dict, gm_ids: set) -> bool:
    """Record a post or a join. Returns True when handled."""
    gid, reply, state = ctx["group_id"], ctx["reply_topic"], ctx["state"]

    if str(ctx["user_id"]) not in {str(g) for g in (gm_ids or set())}:
        tg.send_message(gid, reply, "⛔ GM only.")
        return True

    args = ctx["text"].split()[1:]
    if not args:
        tg.send_message(gid, reply, _usage(cmd))
        return True

    try:
        venues = catalogue.load()
    except (OSError, ValueError) as error:
        tg.send_message(gid, reply, f"⚠️ Could not read the catalogue: {error}")
        return True

    venue_id = args[0]
    venue = catalogue.by_id(venues, venue_id)
    if not venue:
        tg.send_message(gid, reply,
                        f"⚠️ No venue with id {venue_id!r}.\n\n"
                        f"Known: {_venue_ids(venues)}")
        return True

    if cmd == "/recruitposted":
        log.record_post(state, venue_id)
        tg.send_message(gid, reply,
                        f"✅ Recorded a post to {venue['name']}. "
                        f"Next due in {venue['cooldown_days']:g}d.")
        return True

    player = " ".join(args[1:]).strip()
    if not player:
        tg.send_message(gid, reply, _usage(cmd))
        return True
    log.record_join(state, venue_id, player)
    gained = len(log.joins_for(state, venue_id))
    tg.send_message(gid, reply,
                    f"✅ {player} credited to {venue['name']} "
                    f"({gained} from there so far).")
    return True


def _usage(cmd: str) -> str:
    if cmd == "/recruitposted":
        return "Usage: /recruitposted <venue-id>\nSee /recruitads for ids."
    return ("Usage: /recruitjoined <venue-id> <player name>\n"
            "Use 'unknown' as the venue if you genuinely cannot tell. "
            "That is recorded honestly rather than guessed at.")
