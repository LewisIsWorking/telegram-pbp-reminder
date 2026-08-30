"""The weekly community roster post: who is in this community, by name.

Lewis, 2026-08-30, after "44 active players" turned out to be 19: *"You
should be able to give me the accurate figure more often, maybe once a
week the bot could post the full community roster."*

The point is not the headline number
------------------------------------
A single figure is what went wrong. This post shows the working: the
three bases side by side, then every campaign with its players named,
then the seats that are silent, then the rows that belong to no campaign
at all. Anyone reading can see which number they are quoting and why the
two disagree.

Silence is shown, not hidden
----------------------------
C08 Theria seats seven people and one of them has posted this month; the
other six have been silent 110 to 180 days. Rendering it as "1/6" alone
loses the fact that six real people are enrolled, and rendering it as
"7/6" is the error that started all this. Both lines are printed.

⚠️ Read-only. It computes and returns a string, and nothing here writes
state or sends a message, so it is safe to call from a test or a REPL
against production data.
"""

import datetime

from commands.roster_members import _active_players, effective_target
from recruiting.roster_basis import (configured_pids, counts, posted_days_ago)
from scheduled.recruit_roster_line import mention

# A seat quiet this long is called out by name in its campaign block.
# Matches roster_members._ACTIVE_DAYS, so "not listed as active" and
# "listed as quiet" are the same set rather than two nearly equal ones
# with a silent gap between them.
QUIET_DAYS = 30


def _named(players: list) -> str:
    return ", ".join(sorted((mention(p) for p in players),
                            key=lambda n: n.lstrip("@").lower()))


def _quiet_seats(pid: str, state: dict, active: list) -> list:
    """Seats in this campaign that ``_active_players`` left out.

    ⭐ Derived by SUBTRACTING the active list rather than by re-testing
    the window. Re-testing would be a second opinion about the same
    borderline seat, and the two could disagree; subtraction cannot, and
    it follows the definition of "active" wherever that goes next,
    including the permanent-player rule this deliberately does not
    duplicate.

    Identity comparison is exact here because ``_active_players`` yields
    the very dicts held in ``state["players"]`` rather than copies.
    """
    seated = {id(p) for p in active}
    return [p for p in state.get("players", {}).values()
            if str(p.get("pbp_topic_id", "")) == pid and id(p) not in seated]


def _campaign_block(pair: dict, config: dict, state: dict,
                    asof: datetime.datetime) -> list[str]:
    pid = str(pair["pbp_topic_ids"][0])
    active = _active_players(pid, state, config)
    target = pair.get("roster_target") or effective_target(config, state)
    code = pair.get("code", "")
    label = f"{code}: {pair.get('name', '')}" if code else pair.get("name", "")
    emoji = pair.get("emoji", "")
    head = f"{emoji + ' ' if emoji else ''}{label} - {len(active)}/{target}"

    lines = [head]
    lines.append(f"   {_named(active)}" if active else "   (nobody seated)")

    quiet = _quiet_seats(pid, state, active)
    if quiet:
        parts = []
        for player in sorted(quiet, key=lambda p: -(posted_days_ago(p, asof)
                                                    or 0)):
            ago = posted_days_ago(player, asof)
            when = f"{int(ago)}d" if ago is not None else "never posted"
            parts.append(f"{mention(player)} {when}")
        lines.append(f"   💤 {', '.join(parts)}")
    return lines


def orphan_seats(config: dict, state: dict) -> list:
    """Records whose campaign the config no longer knows about.

    Two of these exist today: C11 Dark Pockets retired and its roster rows
    were never swept. They inflate every enrolment count and belong to
    nothing, so the post names them rather than letting them sit inside a
    total.
    """
    live = configured_pids(config)
    return [p for p in state.get("players", {}).values()
            if str(p.get("pbp_topic_id", "")) not in live]


def build_community_roster(config: dict, state: dict,
                           now: datetime.datetime) -> str:
    figures = counts(state.get("players", {}), config, now,
                     window=QUIET_DAYS)
    pairs = list(config.get("topic_pairs", []))

    lines = [
        f"👥 Community roster - {now.date().isoformat()}",
        "━━━━━━━━━━━━━━━━",
        f"📊 {figures['seat_humans']} people hold {figures['seats']} seats "
        f"across {len(pairs)} campaigns.",
        f"✅ {figures['active_humans']} people ({figures['active_seats']} "
        f"seats) have posted in the last {QUIET_DAYS} days.",
        f"🔝 The top five hold {figures['top_five_seats']} of "
        f"{figures['active_seats']} active seats "
        f"({figures['top_five_pct']}%).",
        "",
    ]
    for pair in pairs:
        lines.extend(_campaign_block(pair, config, state, now))

    orphans = orphan_seats(config, state)
    if orphans:
        lines.append("")
        lines.append(f"🕯 In no current campaign: {_named(orphans)}")

    lines.append("")
    lines.append(f"ℹ️ \"Active\" means posted within {QUIET_DAYS} days. One "
                 f"person can hold several seats, which is why people and "
                 f"seats differ.")
    return "\n".join(lines)
