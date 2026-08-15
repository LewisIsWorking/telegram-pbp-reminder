"""Who counts as part of a campaign's roster.

Extracted from ``commands/roster.py`` on 2026-08-15, which had reached 216
lines. Membership rules live here; the ``build_roster_*`` renderers stay in
``roster.py`` and import from this module.

The permanent-player rule below is a deliberate design decision Lewis
flagged on 2026-05-10, not an over-counting bug. Read the docstring before
touching it.
"""

from datetime import datetime, timezone, timedelta
from players.permanence import is_permanent

_TARGET = 6
_ACTIVE_DAYS = 30


def _active_players(pid: str, state: dict, config: dict) -> list[dict]:
    """Return players considered part of the campaign's active roster.

    Inclusion rules (in priority order):

    1. **Permanent players are always counted** — regardless of when
       they last posted. This is INTENTIONAL, not a bug. The
       ``permanent`` flag (set via ``/setpermanent``) marks players
       who are members of the campaign even during dormant stretches:
       trusted long-term players, GMs-as-players who post sporadically,
       and people who explicitly want to stay enrolled across quiet
       weeks. The same flag suppresses the week-3 auto-removal ping
       in the inactivity reminder — the two behaviours together
       implement the contract "this person is a member full stop;
       don't measure them, don't kick them." Do NOT add a recency
       check here — it would silently demote permanent players from
       the roster count and break the user-facing meaning of
       ``/setpermanent``.

    2. **Non-permanent players** must have posted within the last
       ``_ACTIVE_DAYS`` days to count.

    Lewis explicitly flagged this design on 2026-05-10 after a
    session where Claude (incorrectly) treated the permanent
    bypass as an over-counting bug. Recorded in REFACTOR_PROGRESS.md
    as L20 to prevent a repeat.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=_ACTIVE_DAYS)
    result = []
    for p in state.get("players", {}).values():
        if str(p.get("pbp_topic_id", "")) != pid:
            continue
        if is_permanent(p, config):
            # Intentional: permanent (per-record OR config-listed) =
            # roster member, full stop. See docstring above. Do not
            # add a recency check here — perm = always counted.
            result.append(p)
            continue
        try:
            last = datetime.fromisoformat(p["last_post_time"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last >= cutoff:
                result.append(p)
        except (KeyError, ValueError):
            pass
    return result


def active_poll_uids(pair: dict, config: dict, state: dict) -> list[str]:
    """Return a campaign's poll_user_ids, optionally filtered to the active roster.

    Opt-in per campaign via ``pair['poll_roster_filter']``:

    * **Unset (default)** — the full ``poll_user_ids`` list is returned
      unchanged. This is required for campaigns whose players are not tracked
      in the shared registry (e.g. C11 runs in a *separate* Telegram group),
      where an active-roster intersection would wrongly empty the list.
    * **Set** — only poll users who are on the campaign's active roster
      (``_active_players`` for the campaign's first pbp topic) are returned,
      so players who have left or gone inactive stop being pinged and stop
      counting toward the vote total.

    Returns user ids as strings to match the rest of the poll code.
    """
    uids = [str(u) for u in pair.get("poll_user_ids", [])]
    if not pair.get("poll_roster_filter"):
        return uids
    pid = str(pair["pbp_topic_ids"][0])
    active = {str(p.get("user_id")) for p in _active_players(pid, state, config)}
    return [u for u in uids if u in active]


def _split_active(players: list[dict], config: dict) -> tuple[list[dict], list[dict]]:
    """Partition an _active_players result into (non_permanent, permanent).

    Used by the overview and per-campaign builders to display permanent
    players separately. The ``X/Y +Z perm`` format that surfaces this
    distinction (e.g. ``4/6 +1 perm``) lets the GM see at a glance how
    much of a campaign's roster is held by perm slots vs by players
    actually posting within the recency window. Lewis requested this
    on 2026-05-11 after spotting the gap between /roster (counts perms)
    and /overview (does not). The icon (✅/⚠️) still gates on the
    combined count so the set of warned campaigns stays the same —
    only the display becomes more informative.

    As of 2026-05-17 (L26), "permanent" is decided by
    ``players.permanence.is_permanent(p, config)`` rather than just
    ``p.get("permanent")``, so users listed in
    ``config["permanent_user_ids"]`` partition into the perm bucket
    even when their per-record flag isn't set.
    """
    non_perm = [p for p in players if not is_permanent(p, config)]
    perm = [p for p in players if is_permanent(p, config)]
    return non_perm, perm
