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
from commands.roster import _active_players, _TARGET

_GATE_HOURS = 24
_LAST_KEY = "last_recruit_focus"
_MSG_KEY = "recruit_focus_msg_id"


def _shortfall(pair: dict, state: dict, config: dict) -> tuple[int, int, int]:
    """Return (missing, active, target) for one campaign."""
    pid = str(pair["pbp_topic_ids"][0])
    target = pair.get("roster_target", _TARGET)
    active = len(_active_players(pid, state, config))
    return target - active, active, target


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
        missing, active, target = _shortfall(pair, state, config)
        ratio = active / target if target else 1.0
        candidates.append((-missing, ratio, pair))
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c[0], c[1]))[2]


def build_recruit_message(config: dict, state: dict) -> str:
    """Build the message, or '' when no campaign is short."""
    pair = pick_recruit_pair(config, state)
    if not pair:
        return ""

    missing, active, target = _shortfall(pair, state, config)
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

    lines = ["━━━━━━━━━━━━━━━━",
             f"🧭 Recruit for this next: {emoji_prefix}{label}",
             f"⏳ {missing} {seats} open ({active}/{target} players)."]
    if tier:
        lines.append(f"📌 Reserve campaign — every campaign in tier "
                     f"{tier - 1} and below is full.")
    if len(eligible) > 1:
        lines.append(f"↗ Biggest gap of {len(eligible)} campaigns "
                     f"currently recruiting.")
    else:
        lines.append("↗ The only campaign currently below target.")

    topic = pair["pbp_topic_ids"][0]
    username = config.get("group_username", "")
    if username:
        lines.append(f"🔗 https://t.me/{username}/{topic}")
    return "\n".join(lines)


def post_recruit_focus(config: dict, state: dict, *,
                       now: datetime | None = None, **_kw) -> None:
    """Post once per 24h to the GM queue, replacing the previous one.

    Send first, then delete, so a failed send never leaves the topic with
    no recruit post at all — same ordering as ``schedule_post``.
    """
    now = now or datetime.now(timezone.utc)
    topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    if not topic:
        return
    if not config.get("recruit_focus_enabled", True):
        return

    last = state.get(_LAST_KEY)
    if last:
        try:
            since = helpers.hours_since(now, datetime.fromisoformat(last))
        except (ValueError, TypeError):
            since = _GATE_HOURS
        if since < _GATE_HOURS:
            return

    text = build_recruit_message(config, state)
    if not text:
        # Every campaign is full. Clear the gate so the next shortfall
        # posts immediately rather than waiting out a stale 24h window,
        # and leave any existing post up — it is still true until it is
        # replaced, and deleting it here would need a second delete path.
        return

    msg_id = tg.send_message_id(config["group_id"], topic, text, silent=True)
    if not msg_id:
        return
    prev = state.get(_MSG_KEY)
    if prev:
        tg.delete_message(config["group_id"], prev)
    state[_MSG_KEY] = msg_id
    state[_LAST_KEY] = now.isoformat()
