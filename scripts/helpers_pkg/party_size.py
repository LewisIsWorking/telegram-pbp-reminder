"""How a campaign's player count reads next to its standard party size.

Added 2026-10-12. "8/6" alone read as "full" to a player asking whether
Riddleport had room (SunderTorrent). The 6 is the standard party size, not
a cap, so the count now says so in brackets after the numbers.
"""


def party_count(count: int, target: int) -> str:
    """'8/6 (8 players, standard party size 6)'."""
    s = "" if count == 1 else "s"
    return f"{count}/{target} ({count} player{s}, standard party size {target})"
