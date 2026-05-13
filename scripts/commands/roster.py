"""/roster — campaign player overview and per-campaign history.

/roster          — all campaigns ordered fewest to most active players
/roster C04      — drill-down: current players + join/leave history for C04
/roster 04       — same, with or without the C prefix
"""

from datetime import datetime, timezone, timedelta

_TARGET = 6
_ACTIVE_DAYS = 30


def _active_players(pid: str, state: dict) -> list[dict]:
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
        if p.get("permanent"):
            # Intentional: permanent flag = roster member, full stop.
            # See docstring above. Do not add a recency check here.
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


def _split_active(players: list[dict]) -> tuple[list[dict], list[dict]]:
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
    """
    non_perm = [p for p in players if not p.get("permanent")]
    perm = [p for p in players if p.get("permanent")]
    return non_perm, perm


def _find_pair(arg: str, config: dict) -> dict | None:
    """Find campaign pair by code (e.g. 'C04', '04', '4')."""
    norm = arg.upper().lstrip("C").lstrip("0") or "0"
    for pair in config.get("topic_pairs", []):
        code = pair.get("code", "").upper().lstrip("C").lstrip("0") or "0"
        if code == norm:
            return pair
    return None


def build_roster_overview(config: dict, state: dict) -> str:
    rows = []
    for pair in config.get("topic_pairs", []):
        code = pair.get("code", "")
        name = pair.get("name", "")
        pid = str(pair["pbp_topic_ids"][0])
        non_perm, perm = _split_active(_active_players(pid, state))
        target = pair.get("roster_target", _TARGET)
        rows.append((len(non_perm), len(perm), code, name, target))
    # Warnings first (non-perm vs target — perm players don't count
    # toward the target per Lewis's 2026-05-12 clarification), then by
    # non-perm count ascending so the most under-staffed campaigns
    # appear first within the warning group.
    rows.sort(key=lambda r: (r[4] <= r[0], r[0]))
    lines = [f"📋 Campaign Roster (target: {_TARGET}, active last {_ACTIVE_DAYS}d)\n"]
    for non_perm_n, perm_n, code, name, target in rows:
        # Icon gates on NON-PERM count only. Permanent players are full
        # members (counted in the roster, never auto-kicked, shown with
        # [perm] tags) but they don't fill "out of 6" slots — the X/Y
        # target measures non-perm activity. A campaign at "4/6 +2 perm"
        # is still under-staffed: it needs 6 non-perm active players,
        # not 6 total. See L20 + L23 in REFACTOR_PROGRESS.md.
        icon = "✅" if non_perm_n >= target else "⚠️"
        label = f"{code}: {name}" if code else name
        # Format: "4/6 +2 perm" — X non-perm, Y target, Z perm padding.
        # The "+Z perm" suffix is omitted when there are no perm players
        # so campaigns without a perm slot read cleanly as "X/Y".
        perm_suffix = f" +{perm_n} perm" if perm_n else ""
        lines.append(f"{icon} {label} — {non_perm_n}/{target}{perm_suffix}")
    return "\n".join(lines)


def build_roster_campaign(pair: dict, config: dict, state: dict) -> str:
    code = pair.get("code", "")
    name = pair.get("name", "")
    pid = str(pair["pbp_topic_ids"][0])
    label = f"{code}: {name}" if code else name

    players = _active_players(pid, state)
    non_perm, perm = _split_active(players)
    target = pair.get("roster_target", _TARGET)
    combined = len(non_perm) + len(perm)
    # Icon gates on NON-PERM count only (perm players don't count toward
    # the target). Same rationale as build_roster_overview — see comment
    # there and L23 in REFACTOR_PROGRESS.md.
    icon = "✅" if len(non_perm) >= target else "⚠️"
    perm_suffix = f" +{len(perm)} perm" if perm else ""
    names = "\n".join(
        f"  • {p.get('first_name', '?')}"
        + (f" (@{p['username']})" if p.get("username") else "")
        + (" [perm]" if p.get("permanent") else "")
        for p in sorted(players, key=lambda p: p.get("first_name", ""))
    ) or "  (none)"

    history = [e for e in state.get("player_history", []) if e.get("pid") == pid]
    if history:
        hist_lines = []
        for e in sorted(history, key=lambda e: e.get("at", "")):
            ev = "➕ joined" if e["event"] == "join" else "➖ left"
            date = e.get("at", "")[:10]
            uname = f" (@{e['username']})" if e.get("username") else ""
            hist_lines.append(f"  {date} {ev} {e.get('name', '?')}{uname}")
        hist_text = "\n".join(hist_lines)
    else:
        hist_text = "  (no history recorded yet)"

    return (
        f"📋 {label}\n"
        f"{icon} {len(non_perm)}/{target}{perm_suffix} active player"
        f"{'s' if combined != 1 else ''} (last {_ACTIVE_DAYS}d)\n\n"
        f"Current:\n{names}\n\n"
        f"History:\n{hist_text}"
    )


def build_roster(arg: str, config: dict, state: dict) -> str:
    if not arg:
        return build_roster_overview(config, state)
    pair = _find_pair(arg, config)
    if not pair:
        return f"Campaign '{arg}' not found. Try /roster C04 or just /roster."
    return build_roster_campaign(pair, config, state)
