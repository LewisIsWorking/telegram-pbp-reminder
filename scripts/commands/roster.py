"""/roster — campaign player overview and per-campaign history.

/roster          — all campaigns ordered fewest to most active players
/roster C04      — drill-down: current players + join/leave history for C04
/roster 04       — same, with or without the C prefix
"""

from datetime import datetime, timezone, timedelta

_TARGET = 6
_ACTIVE_DAYS = 30


def _active_players(pid: str, state: dict) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_ACTIVE_DAYS)
    result = []
    for p in state.get("players", {}).values():
        if str(p.get("pbp_topic_id", "")) != pid:
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
        count = len(_active_players(pid, state))
        rows.append((count, code, name))
    rows.sort(key=lambda r: r[0])
    lines = [f"📋 Campaign Roster (target: {_TARGET}, active last {_ACTIVE_DAYS}d)\n"]
    for count, code, name in rows:
        icon = "✅" if count >= _TARGET else "⚠️"
        label = f"{code}: {name}" if code else name
        lines.append(f"{icon} {label} — {count}/{_TARGET}")
    return "\n".join(lines)


def build_roster_campaign(pair: dict, config: dict, state: dict) -> str:
    code = pair.get("code", "")
    name = pair.get("name", "")
    pid = str(pair["pbp_topic_ids"][0])
    label = f"{code}: {name}" if code else name

    players = _active_players(pid, state)
    count = len(players)
    icon = "✅" if count >= _TARGET else "⚠️"
    names = "\n".join(
        f"  • {p.get('first_name', '?')}"
        + (f" (@{p['username']})" if p.get("username") else "")
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
        f"{icon} {count} active player{'s' if count != 1 else ''} (last {_ACTIVE_DAYS}d)\n\n"
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
