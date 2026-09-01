"""A character somebody else posts for. ``played_by`` on a player record.

Added 2026-09-01. Lewis, on C06 Kibwe, after Anthony said it out loud in
the group: *"somebody actually does your rolls for you and all... And
that somebody is me tragically."*

Lorn is in every scene. Horia has not typed in 29 days. The bot measures
**who posts**, not **who plays**, so the two are indistinguishable to it,
and Horia was one hourly run from being swept out of a campaign his
character is currently standing in. The same thing had already happened
to Ji Yun a week earlier: their player was removed on 2026-08-24 as
Caelum (@Thien_Ming), while Anthony still listed Ji Yun as party.

⭐⭐ **THIS IS A REDIRECTION, NOT AN EXEMPTION, AND THAT IS THE WHOLE
POINT.** ``permanent`` says *do not measure this person*. ``played_by``
says *measure them THROUGH SOMEONE ELSE*. If the proxy goes quiet, the
proxied seat goes quiet with them, on the same clock, and is swept like
anyone else. A flag that made a seat immortal would inflate the roster
exactly the way the recruit advert must not.

⛔ **A DANGLING POINTER MUST NOT GRANT IMMORTALITY.** If ``played_by``
names somebody who is not on the campaign's roster (removed, renamed,
mistyped), resolution falls back to the seat's **own** last post time.
The failure mode of a broken proxy is "measured normally", never
"exempt forever". This is the one behaviour worth breaking a test over.

⚠️ **One hop only.** A proxied-by-B seat resolves to B's *own* time even
if B is itself proxied. That caps the work at one lookup and makes a
cycle (A→B, B→A) harmless rather than infinite.
"""

from datetime import datetime, timezone


def proxy_username(player: dict) -> str:
    """The username this seat is played by, without '@'. '' if none."""
    return str(player.get("played_by") or "").strip().lstrip("@")


def is_proxied(player: dict) -> bool:
    """True if this seat declares a proxy. Says nothing about whether it resolves."""
    return bool(proxy_username(player))


def find_proxy(player: dict, pid: str, state: dict) -> dict | None:
    """The proxy's player record in the same campaign, or None.

    Same campaign is required. A proxy in a different game is not
    evidence that this character is being played in **this** one, and
    accepting one would let a seat ride on activity from elsewhere.
    """
    wanted = proxy_username(player).lower()
    if not wanted:
        return None
    for candidate in state.get("players", {}).values():
        if str(candidate.get("pbp_topic_id", "")) != str(pid):
            continue
        if str(candidate.get("username") or "").lower().lstrip("@") == wanted:
            return candidate
    return None


def _parse(stamp) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def effective_post_time(player: dict, pid: str, state: dict) -> datetime | None:
    """When this seat last counted as active, following ``played_by`` once.

    Returns the **proxy's** last post time for a resolved proxy, the
    seat's own otherwise. None when neither can be parsed, which callers
    already treat as "not active".

    ⛔ Deliberately returns the seat's own time when the proxy cannot be
    found. See the module docstring: a broken pointer must degrade to
    normal measurement, not to an exemption.
    """
    own = _parse(player.get("last_post_time"))
    proxy = find_proxy(player, pid, state)
    if proxy is None:
        return own
    # One hop: the proxy's OWN time, never the proxy's proxy.
    return _parse(proxy.get("last_post_time")) or own


def proxy_note(player: dict, pid: str, state: dict) -> str:
    """A short roster suffix naming the proxy, or ''.

    ⭐ Shown wherever a proxied seat is counted. A seat that counts for a
    reason the reader cannot see is how a roster stops being believed,
    and this whole feature exists because a count disagreed with the
    table. An unresolved proxy says so rather than staying silent.
    """
    name = proxy_username(player)
    if not name:
        return ""
    if find_proxy(player, pid, state) is None:
        return f" [played by @{name}: NOT ON THIS ROSTER, measured normally]"
    return f" [played by @{name}]"
