"""What we posted where, and who actually turned up because of it.

⭐ **This is the half that makes the workflow converge.** A longer list of
venues, on its own, only spreads the same effort thinner. What turns it
into an answer is knowing that (say) the Paizo board yielded four players
from three posts while a big general LFG board yielded none from eight, so
the effort moves. Without attribution you can add venues forever and never
learn which ones work.

⚠️ Attribution needs one human habit: when someone joins, say where they
came from. Nothing can infer it. The bot asks for it at the moment a
player is added, because a week later nobody remembers.

Lives in ``state`` rather than in the catalogue file so that hand-editing
the catalogue can never race the bot's writes.
"""

from datetime import datetime, timezone

LOG_KEY = "recruitment_log"

# Attribution we asked for and did not get. Kept as a real value rather
# than dropped, so "we do not know" stays visible in the yield table
# instead of quietly inflating whichever venue was posted to most
# recently. A venue credited by guesswork is worse than one credited to
# nobody, because it survives review looking like evidence.
UNKNOWN_VENUE = "unknown"


def get_log(state: dict) -> dict:
    """The recruitment log, created empty if absent."""
    log = state.setdefault(LOG_KEY, {})
    log.setdefault("posts", {})
    log.setdefault("joins", [])
    return log


def record_post(state: dict, venue_id: str,
                now: datetime | None = None,
                url: str = "") -> dict:
    """Note that the advert went up at ``venue_id``. Returns the entry.

    ``url`` is where it went up, and it is worth capturing at exactly this
    moment because it is never recoverable later. Finding your own advert
    again is what lets you check for replies, bump it, or take it down when
    the campaign fills. Added 2026-08-25, the first time a real posting
    handed over a permalink that this function had nowhere to put.

    ⚠️ Entries changed from a bare ISO string to ``{"at": ..., "url": ...}``
    on the same day. That deliberately broke every reader rather than
    silently accepting two shapes: see ``_stamp``, which now has to know
    about both, and is the only place that does.
    """
    now = now or datetime.now(timezone.utc)
    entry = {"at": now.isoformat(), "url": url or ""}
    get_log(state)["posts"].setdefault(venue_id, []).append(entry)
    return entry


def _stamp(entry) -> str:
    """The timestamp of a post entry, in either shape.

    Legacy entries are a bare ISO string. Reading them has to keep working
    because state files predate the change and are not migrated on load.
    """
    if isinstance(entry, dict):
        return entry.get("at", "")
    return entry or ""


def post_url(entry) -> str:
    """Where a post went up, or "" for legacy entries that never recorded it."""
    return entry.get("url", "") if isinstance(entry, dict) else ""


def record_join(state: dict, venue_id: str, player: str,
                now: datetime | None = None) -> dict:
    """Credit a new player to a venue.

    ``venue_id`` may be ``UNKNOWN_VENUE``; see the note above on why that
    is recorded rather than guessed.
    """
    now = now or datetime.now(timezone.utc)
    entry = {"venue": venue_id or UNKNOWN_VENUE, "player": player,
             "at": now.isoformat()}
    get_log(state)["joins"].append(entry)
    return entry


def posts_for(state: dict, venue_id: str) -> list:
    """Every post entry for this venue, in the order they were recorded."""
    return list(get_log(state)["posts"].get(venue_id, []))


def stamps_for(state: dict, venue_id: str) -> list:
    """Just the timestamps, for callers that only care when."""
    return [_stamp(e) for e in posts_for(state, venue_id)]


def last_posted(state: dict, venue_id: str) -> str | None:
    """When the advert last went up here, or None if it never has."""
    stamps = [s for s in stamps_for(state, venue_id) if s]
    return max(stamps) if stamps else None


def last_post_url(state: dict, venue_id: str) -> str:
    """The link to the most recent advert here, or "" if unrecorded."""
    entries = [e for e in posts_for(state, venue_id) if _stamp(e)]
    if not entries:
        return ""
    return post_url(max(entries, key=_stamp))


def joins_for(state: dict, venue_id: str) -> list:
    """Players credited to this venue."""
    return [j for j in get_log(state)["joins"] if j.get("venue") == venue_id]


def yield_table(state: dict, venues: list) -> list:
    """Per venue: posts made, players gained, and players per post.

    Sorted by players gained, then by players per post, so the venues
    worth the next hour of effort are at the top.

    ⚠️ ``per_post`` is None, not 0.0, when nothing has been posted there.
    "Never tried" and "tried and got nobody" are opposite conclusions and
    must not render as the same number: one says post here next, the other
    says stop.
    """
    rows = []
    for venue in venues:
        posted = len(posts_for(state, venue["id"]))
        gained = len(joins_for(state, venue["id"]))
        rows.append({
            "id": venue["id"],
            "name": venue["name"],
            "status": venue["status"],
            "posts": posted,
            "joins": gained,
            "per_post": (gained / posted) if posted else None,
        })
    rows.sort(key=lambda r: (r["joins"], r["per_post"] or 0.0), reverse=True)
    return rows


def unattributed(state: dict) -> int:
    """How many joins we failed to credit. A quality signal on the data."""
    return len(joins_for(state, UNKNOWN_VENUE))
