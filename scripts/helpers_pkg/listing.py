"""Which campaigns the bot's campaign-wide posts list.

Added 2026-09-21 for a test campaign (C99, Tongs Browser's encounter
tests). A campaign with ``"listing"`` in ``disabled_features`` is left out
of every post that lists all campaigns: the weekly digest, the leaderboard,
the roster overview and nudge, and the community roster. Players would
otherwise read "Tongs Testing - 0 posts" beside their real tables.

⚠️ Why a switch and not ``roster_target: 0``: ``/roster`` reads a target
of 0 as unset and falls back to the default, so a zero target would still
list the test campaign as under-staffed.
"""

LISTING = "listing"


def listed(pair: dict) -> bool:
    """True unless the campaign asked to be left out of campaign-wide posts."""
    return LISTING not in pair.get("disabled_features", [])


def listed_pairs(config: dict) -> list[dict]:
    """The campaigns a campaign-wide post should show, in config order."""
    return [pair for pair in config.get("topic_pairs", []) if listed(pair)]


def listed_pids(config: dict) -> set[str]:
    """The canonical topic ids of those campaigns."""
    return {str(pair["pbp_topic_ids"][0]) for pair in listed_pairs(config)}
