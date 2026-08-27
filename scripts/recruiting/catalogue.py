"""The venue catalogue: where a campaign advert is allowed to go.

Added 2026-08-20. Lewis: *"instead of just repeating the same thing of
always posting on the Pathfinder 2e discord... we could start a
recruitment workflow of various places to put the ad."*

Read-only here. The mutable half (when we last posted where, and who
joined from where) lives in ``recruiting.log``, deliberately separate so
the catalogue can be hand-edited at any moment without racing the bot's
state writes.

⚠️ **An assumed cooldown is not a rule, and the difference is the whole
point of the field.** Getting muted in the one venue that actually works
costs more than every missed week combined, so anything not read off the
venue's own rules is marked ``assumed`` and must be conservative. The
validator below refuses to load a catalogue that claims a short cooldown
without a stated rule behind it.
"""

import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CATALOGUE_PATH = os.path.join(_REPO_ROOT, "data", "recruitment_venues.json")

# A guess may never be more aggressive than this. Chosen so that an
# unverified venue is posted to at most fortnightly, which no venue in the
# wild objects to.
MIN_ASSUMED_COOLDOWN_DAYS = 7

STATUSES = ("active", "candidate", "rejected")
COOLDOWN_SOURCES = ("rule", "assumed")


def rotates(venue: dict) -> bool:
    """Can an advert be POSTED here, as opposed to merely credited?

    ⚠️ These are two different questions and one field cannot answer
    both. Added 2026-08-27, when Paul joined C07 and Lewis said he is an
    IRL friend. That is a real, known source: crediting him to
    ``UNKNOWN_VENUE`` would be a lie, because unknown means "we asked and
    did not find out". But a friend is not somewhere you post an advert,
    so it must never appear in the rotation.

    Absent means True, so every existing venue keeps its behaviour.
    """
    return bool(venue.get("rotates", True))


class CatalogueError(ValueError):
    """The catalogue is malformed. Raised rather than silently skipping.

    A venue dropped for being malformed would simply never be posted to,
    and the operator would have no way to notice: the rotation would look
    healthy and just be quietly smaller.
    """


def _check(venue: dict, index: int) -> None:
    where = venue.get("id") or f"venue #{index}"
    required = ["id", "name", "kind", "status"]
    if "rotates" in venue and not isinstance(venue["rotates"], bool):
        raise CatalogueError(f"{where}: rotates must be true or false")
    # A source you cannot post to has no cooldown, and demanding a
    # meaningless number would only invite a made-up one.
    if rotates(venue):
        required += ["cooldown_days", "cooldown_source"]
    for field in required:
        if field not in venue:
            raise CatalogueError(f"{where}: missing required field {field!r}")
    if venue["status"] not in STATUSES:
        raise CatalogueError(
            f"{where}: status {venue['status']!r} not one of {STATUSES}")
    if not rotates(venue):
        return
    if venue["cooldown_source"] not in COOLDOWN_SOURCES:
        raise CatalogueError(
            f"{where}: cooldown_source {venue['cooldown_source']!r} "
            f"not one of {COOLDOWN_SOURCES}")
    if not isinstance(venue["cooldown_days"], (int, float)) or venue["cooldown_days"] <= 0:
        raise CatalogueError(f"{where}: cooldown_days must be a positive number")
    if (venue["cooldown_source"] == "assumed"
            and venue["cooldown_days"] < MIN_ASSUMED_COOLDOWN_DAYS):
        raise CatalogueError(
            f"{where}: cooldown_days={venue['cooldown_days']} is below the "
            f"{MIN_ASSUMED_COOLDOWN_DAYS} day floor for an assumed cooldown. "
            f"Read the venue's rules and set cooldown_source='rule', or "
            f"leave the number conservative.")


def load(path: str = CATALOGUE_PATH) -> list:
    """Every venue in the catalogue, validated.

    Raises rather than returning a partial list. See ``CatalogueError``.
    """
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    venues = raw.get("venues", [])
    seen = set()
    for index, venue in enumerate(venues):
        _check(venue, index)
        if venue["id"] in seen:
            raise CatalogueError(f"duplicate venue id {venue['id']!r}")
        seen.add(venue["id"])
    return venues


def creditable(venues: list) -> list:
    """Every source a player can be credited to, for the yield table.

    ``rejected`` venues stay IN the file on purpose: the reason a venue
    was ruled out is worth keeping, or it gets rediscovered and
    re-evaluated every few months. They are filtered out here instead.
    """
    return [v for v in venues if v["status"] in ("active", "candidate")]


def postable(venues: list) -> list:
    """The subset of those we can actually put an advert in.

    ⚠️ Deliberately narrower than ``creditable``. Before 2026-08-27 this
    answered both questions, which was fine only while every source was
    also a place you post. It stopped being true the moment a player
    arrived through somebody's personal network.
    """
    return [v for v in creditable(venues) if rotates(v)]


def by_id(venues: list, venue_id: str) -> dict | None:
    """The named venue, or None. Callers report the miss themselves."""
    return next((v for v in venues if v["id"] == venue_id), None)
