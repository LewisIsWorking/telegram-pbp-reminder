"""/roster — campaign player overview and per-campaign history.

/roster          — all campaigns ordered fewest to most active players
/roster C04      — drill-down: current players + join/leave history for C04
/roster 04       — same, with or without the C prefix
"""

from datetime import datetime, timezone, timedelta
from players.permanence import is_permanent

from commands.roster_members import (  # noqa: F401
    _TARGET, _ACTIVE_DAYS, _active_players, active_poll_uids,
    _split_active)


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
        non_perm, perm = _split_active(_active_players(pid, state, config), config)
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

    players = _active_players(pid, state, config)
    non_perm, perm = _split_active(players, config)
    target = pair.get("roster_target", _TARGET)
    combined = len(non_perm) + len(perm)
    # Icon gates on NON-PERM count only (perm players don't count toward
    # the target). Same rationale as build_roster_overview — see comment
    # there and L23 in REFACTOR_PROGRESS.md.
    icon = "✅" if len(non_perm) >= target else "⚠️"
    perm_suffix = f" +{len(perm)} perm" if perm else ""
    # Split the names list into Current (non-perm) and Perm sections.
    # Lewis requested this on 2026-05-17 after spotting the C00 drill-
    # down listing 4 players as "Current:" when 3 were perm — the [perm]
    # inline tag was easy to miss when scanning. Two sections (omitted
    # when empty) make the split visually unambiguous. See L26.
    def _name_line(p: dict) -> str:
        return (f"  • {p.get('first_name', '?')}"
                + (f" (@{p['username']})" if p.get("username") else ""))

    def _section(label: str, group: list[dict]) -> str:
        if not group:
            return ""
        body = "\n".join(_name_line(p) for p in
                         sorted(group, key=lambda p: p.get("first_name", "")))
        return f"{label}:\n{body}"

    roster_blocks = [s for s in (_section("Current", non_perm),
                                 _section("Perm", perm)) if s]
    roster_text = "\n".join(roster_blocks) or "Current:\n  (none)"

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
        f"{roster_text}\n\n"
        f"History:\n{hist_text}"
    )


def build_roster(arg: str, config: dict, state: dict) -> str:
    if not arg:
        return build_roster_overview(config, state)
    pair = _find_pair(arg, config)
    if not pair:
        return f"Campaign '{arg}' not found. Try /roster C04 or just /roster."
    return build_roster_campaign(pair, config, state)
