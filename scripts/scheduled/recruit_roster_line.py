"""The "Current players" line on the recruit advert (2026-08-29).

Lewis, after reading a live C00 Riddleport advert: *"These are great but
could we add a 4th line of 'Current Players:' then their telegram @s?"*

Fourth line counting the separator, so it sits directly under the seat
count it substantiates: the advert says four of six seats are taken, and
this says who is in them.

Why the players are passed IN rather than fetched here
------------------------------------------------------
The advert already states a count. If this module called
``_active_players`` for itself, the post could name five people on the
line below one that says four, and both halves would look right in
isolation. ``build_recruit_message`` resolves the roster once and hands
the same list to both.

That is a shared source, not a proof. ``test_recruit_focus_roster_line``
parses the rendered post and asserts the names and the ratio agree, so
the two cannot drift apart later without a test failing.

Why nobody is ever dropped
--------------------------
Two player records have no Telegram username (2 of 41 on 2026-08-30), and
one of them (Volf, C04) is a 2026-08-26 recruit, so this is a live case
rather than a hypothetical one. Skipping them would be the divergence
above with extra steps, so the renderer always emits something: username,
else first name, else ``?``, matching ``commands/roster.py``.

⚠️ "41" counts SEAT RECORDS, not people and not active players. 41
records are held by 25 people, of whom 19 have posted inside the 30-day
window. Every one of those three numbers is the honest answer to a
different question, which is why this note names which one.
"""

_LABEL = "\U0001f465 Current players: "


def mention(player: dict) -> str:
    """``@username`` when there is one, else a bare name. Never empty.

    Strips a leading ``@`` from the stored username: a hand-added record
    can carry either form, and ``@@name`` is not a mention.
    """
    username = str(player.get("username") or "").strip().lstrip("@")
    if username:
        return f"@{username}"
    return str(player.get("first_name") or "").strip() or "?"


def _sort_key(name: str) -> str:
    return name.lstrip("@").lower()


def current_players_line(players: list[dict]) -> str:
    """The line, or ``""`` when the campaign has nobody in it yet.

    ⚠️ The empty case is real: C10 The Junction is configured, tiered and
    currently seats zero players. A bare "Current players:" with nothing
    after it reads as a bug in the bot rather than as an empty table.

    Sorted by the displayed name so the advert is stable day to day.
    ``state["players"]`` is a dict keyed by an arbitrary id, and letting
    its order through would reshuffle the line whenever a record was
    rewritten, which reads as a change when nothing changed.
    """
    if not players:
        return ""
    names = sorted((mention(p) for p in players), key=_sort_key)
    return _LABEL + ", ".join(names)
