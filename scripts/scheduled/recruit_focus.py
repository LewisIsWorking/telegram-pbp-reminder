"""'Recruit for this next' focus message for the GM queue (2026-08-15).

Requested as a sibling to the queue focus message: where that one names the
single campaign most in need of a *reply*, this names the single campaign
most in need of *new players*.

Differences from ``queue_focus``, and why
-----------------------------------------
The queue focus is appended to the queue's own message batch, so it dies
with that batch. This one has no batch to ride on, so it manages its own
lifecycle: **once per 24 hours, deleting its predecessor**, the same shape
as ``scheduled/schedule_post``.

That means it owns a bot-sent message id, and there are exactly two places
a new id has to be registered or it silently breaks:

* ``state.PARTITIONS`` — a key absent there is discarded on every save, so
  the id never survives to the next run and the post can never delete its
  predecessor. This is what duplicated the schedule post for two days.
* ``posting/bot_sent_state_scan`` — the registry rebuilds from state each
  run (fresh checkout every time), and ``perform_guarded_delete`` refuses
  any id it does not know.

Both are covered by ``test_state_keys_are_declared`` and
``test_bot_sent_scan_covers_state``, which fail if either is missed.

Selection rule
--------------
Largest shortfall against the campaign's own target wins. Ties break on the
lower fill ratio, so a 1-of-2 campaign outranks a 5-of-6 with the same gap
of one. Campaigns with ``recruitment`` in ``disabled_features`` are never
picked — C08 Theria is currently in that state and would otherwise win on
shortfall every single day.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.roster import _active_players
from commands.roster_members import effective_target
from scheduled.recruit_roster_line import current_players_line

_GATE_HOURS = 24
_LAST_KEY = "last_recruit_focus"
_MSG_KEY = "recruit_focus_msg_id"
# When the current post went up. Separate from _LAST_KEY, which is the
# once-per-24h gate: the gate answers "may I post again", this answers
# "how old is the thing already up", and the retirement sweep needs the
# second question. Added 2026-08-17.
_AT_KEY = "recruit_focus_at"
# Every copy of the current advert, as {chat_id, message_id}. A bare
# id cannot hold two posts in two different chats, and the chat is
# load-bearing because message ids are unique per chat, not globally.
# Added 2026-08-18 with the Nudge Bot Notifications mirror.
_POSTS_KEY = "recruit_focus_posts"


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
    in — both were hard-excluded on 2026-08-15 and are now tiered instead.
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


def pick_recruit_pair(config: dict, state: dict) -> dict | None:
    """The campaign most in need of players, or None if all are full.

    Mirrors ``queue_focus.pick_focus_pid``: one winner, chosen by a stated
    rule, so the GM is given a single action rather than a league table.
    Within the eligible tier, largest shortfall wins, then lowest fill
    ratio.
    """
    candidates = []
    for pair in _eligible_pairs(config, state):
        missing, players, target = _shortfall(pair, state, config)
        ratio = len(players) / target if target else 1.0
        candidates.append((-missing, ratio, pair))
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c[0], c[1]))[2]


def build_recruit_message(config: dict, state: dict) -> tuple[str, dict | None]:
    """Return ``(text, pair)``, or ``("", None)`` when no campaign is short.

    ⭐ Returns the CAMPAIGN as well as the words (changed 2026-08-17, when
    the post moved from the GM queue into the campaign's own chat topic).
    A bare string names its campaign only in prose, so the caller had to
    find the destination some other way — and the only way available is to
    run ``pick_recruit_pair`` a second time, deriving the same answer twice
    and trusting the two to agree. The message and its destination are one
    decision, so they are one return value.
    """
    pair = pick_recruit_pair(config, state)
    if not pair:
        return "", None

    missing, players, target = _shortfall(pair, state, config)
    active = len(players)
    code = pair.get("code", "")
    name = pair.get("name", "")
    label = f"{code}: {name}" if code else name
    emoji = pair.get("emoji", "")
    emoji_prefix = f"{emoji} " if emoji else ""

    seats = "seat" if missing == 1 else "seats"
    # Counted within the eligible tier only. Counting every short campaign
    # would advertise a number the GM cannot act on — the lower tiers are
    # full, and anything in a higher tier is not open for recruiting yet.
    eligible = _eligible_pairs(config, state)
    tier = recruit_tier(pair, config)

    # ⭐ Written for PLAYERS, not the GM (reworded 2026-08-17, when the post
    # moved into each campaign's own chat topic). The old copy opened
    # "Recruit for this next" — an instruction addressed to Lewis, perfectly
    # clear in the GM queue and addressed to nobody in a room full of
    # players. Same facts, turned to face the people who can actually act
    # on them by inviting someone.
    lines = ["━━━━━━━━━━━━━━━━",
             f"🧭 This table has room: {emoji_prefix}{label}",
             f"⏳ {missing} {seats} open ({active}/{target} players)."]
    # Named from the SAME list the ratio above was counted from. Omitted
    # entirely when the campaign seats nobody. Lewis, 2026-08-29.
    roster_line = current_players_line(players)
    if roster_line:
        lines.append(roster_line)
    if tier:
        # Tiers are internal scheduling. A player needs neither the word
        # "tier" nor the number — only that it is open now.
        lines.append("📌 Now open for new players — the campaigns ahead of "
                     "it are full.")
    if len(eligible) > 1:
        lines.append(f"↗ Know someone? This is the biggest gap of "
                     f"{len(eligible)} campaigns currently recruiting.")
    else:
        lines.append("↗ Know someone? This is the only campaign currently "
                     "below target.")

    topic = pair["pbp_topic_ids"][0]
    username = config.get("group_username", "")
    if username:
        lines.append(f"🔗 https://t.me/{username}/{topic}")
    return "\n".join(lines), pair
