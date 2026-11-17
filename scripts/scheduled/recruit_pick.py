"""Which campaign the recruit focus post names (split out 2026-11-17).

The rule itself is documented once, in ``scheduled/recruit_focus``'s
"Selection rule" section: largest shortfall, then longest at the current
player count, then lowest fill ratio, then config order, within the lowest
tier that is still short.
"""

from datetime import datetime, timezone

import helpers
from commands.roster import _active_players
from commands.roster_members import effective_target

# {pid: {"count": n, "since": iso}}: when each campaign was first seen at
# its current player count. The "for longest" half of the selection rule
# (2026-11-17). Not a message id, so it needs ``state.PARTITIONS`` only.
_SINCE_KEY = "recruit_count_since"


def _shortfall(pair: dict, state: dict,
               config: dict) -> tuple[int, list[dict], int]:
    """Return (missing, seated_players, target) for one campaign.

    ⭐ Returns the PLAYERS, not a count of them (changed 2026-08-29, when
    the advert began naming them). Counting here and resolving the names
    somewhere else means two ``_active_players`` calls deciding the same
    question, and a post that says "4/6" above five names is wrong in a
    way that reads as correct. The signature was widened rather than
    added to so every caller had to look at what it now receives.
    """
    pid = str(pair["pbp_topic_ids"][0])
    # Ladder default; an explicit per-pair roster_target still wins.
    target = pair.get("roster_target") or effective_target(config, state)
    players = _active_players(pid, state, config)
    return target - len(players), players, target


def recruit_tier(pair: dict, config: dict) -> int | None:
    """Which queue this campaign recruits from, or None for never.

    Tiers let a campaign wait its turn instead of being excluded outright
    (Lewis, 2026-08-15): **a tier only becomes eligible once every campaign
    in every lower tier is full.**

      * explicit ``recruit_tier`` on the pair wins
      * else ``recruitment`` in ``disabled_features`` means **never**
      * else tier 0, the normal queue

    The precedence matters. Reading the disabled flag first would make an
    explicit tier unreachable, which is exactly the config C10 and C08 are
    in - both were hard-excluded on 2026-08-15 and are now tiered instead.
    """
    if "recruit_tier" in pair:
        return pair["recruit_tier"]
    pid = str(pair["pbp_topic_ids"][0])
    if not helpers.feature_enabled(config, pid, "recruitment"):
        return None
    return 0


def _eligible_pairs(config: dict, state: dict) -> list[dict]:
    """Pairs in the lowest tier that still has a shortfall.

    Every campaign below that tier is full by construction, which is what
    makes the tier eligible at all.
    """
    short: dict[int, list] = {}
    for pair in config.get("topic_pairs", []):
        tier = recruit_tier(pair, config)
        if tier is None:
            continue
        if _shortfall(pair, state, config)[0] > 0:
            short.setdefault(tier, []).append(pair)
    if not short:
        return []
    return short[min(short)]


def _track_counts(config: dict, state: dict, now: datetime) -> dict:
    """Record each recruiting campaign's player count and since when.

    Uses the same count as the pick (``_shortfall``). A changed count, or
    a campaign seen for the first time, starts its clock at ``now``. Every
    campaign with a tier is tracked, not just the eligible ones, so a
    campaign waiting in a later tier has its time banked when its turn
    comes. Returns the record.
    """
    record = state.setdefault(_SINCE_KEY, {})
    for pair in config.get("topic_pairs", []):
        if recruit_tier(pair, config) is None:
            continue
        pid = str(pair["pbp_topic_ids"][0])
        count = len(_shortfall(pair, state, config)[1])
        entry = record.get(pid)
        if not isinstance(entry, dict) or entry.get("count") != count:
            record[pid] = {"count": count, "since": now.isoformat()}
    return record


def _since(record: dict, pid: str, now: datetime) -> datetime:
    """When ``pid`` reached its current count, or ``now`` if unknown."""
    try:
        since = datetime.fromisoformat(record[pid]["since"])
    except (KeyError, TypeError, ValueError):
        return now
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return since


def pick_recruit_pair(config: dict, state: dict, *,
                      now: datetime | None = None) -> dict | None:
    """The campaign most in need of players, or None if all are full.

    Mirrors ``queue_focus.pick_focus_pid``: one winner, chosen by a stated
    rule, so the GM is given a single action rather than a league table.
    Within the eligible tier: largest shortfall, then longest at the
    current count, then lowest fill ratio, then config order (see the
    module docstring). Updates ``recruit_count_since`` as it goes.
    """
    now = now or datetime.now(timezone.utc)
    record = _track_counts(config, state, now)
    candidates = []
    for pair in _eligible_pairs(config, state):
        missing, players, target = _shortfall(pair, state, config)
        ratio = len(players) / target if target else 1.0
        since = _since(record, str(pair["pbp_topic_ids"][0]), now)
        candidates.append((-missing, since, ratio, pair))
    if not candidates:
        return None
    # min() keeps the first of equal keys, which is config order.
    return min(candidates, key=lambda c: (c[0], c[1], c[2]))[3]
