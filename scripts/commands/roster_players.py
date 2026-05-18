"""Cross-campaign player view for /rosterplayers.

Renders a player-centric roster: one row per unique user_id showing
which campaigns they're in, when they last posted, and an at-risk
marker if they've received a week-2 or week-3 inactivity warning.
A footer pulls out the at-risk players and any recent join/leave
events from state['player_history'].

Separated from roster_views.py so the file stays under the 200-line
cap and so /rosterall can re-use just the footer logic without
pulling in the whole player table.

Note on player_history (2026-05-11): scripts/players/history.py
exposes on_join/on_leave/on_rejoin which append events to
state['player_history'], but no production code path currently
calls them. The footer's 'recently joined / left' sections render
correctly once those wire-ups exist; for now they'll typically be
empty in production state.
"""

from datetime import datetime, timezone, timedelta
from players.permanence import is_permanent

from commands.roster import _ACTIVE_DAYS

_HISTORY_DAYS = 30  # window for the 'recently joined / left' sections


def _at_risk_status(player: dict, config: dict) -> str | None:
    """Return an at-risk marker string for a player, or None.

    Uses last_warned_week (set by scheduled.alerts.check_player_activity):
      * 3 \u2014 received the week-3 'auto-removal in 1 week' warning.
      * 2 \u2014 received the week-2 silent-for-too-long warning.
      * 1 \u2014 received the gentle week-1 ping. Not 'at risk' yet.
      * 0 / missing \u2014 nothing issued.

    Permanent players are never warned for removal (the alerts logic
    skips removal for them), so they never qualify as at-risk here.
    """
    if is_permanent(player, config):
        return None
    warned = player.get("last_warned_week", 0)
    if warned >= 3:
        return "\U0001f525"   # week-3 fired: removal imminent
    if warned == 2:
        return "\u26a0\ufe0f"  # week-2 fired: silent stretch
    return None


def _days_ago(player: dict, now: datetime) -> int | None:
    try:
        last = datetime.fromisoformat(player["last_post_time"])
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).days
    except (KeyError, ValueError):
        return None


def _pid_to_code(config: dict) -> dict[str, str]:
    out = {}
    for pair in config.get("topic_pairs", []):
        code = pair.get("code", "")
        for pid in pair.get("pbp_topic_ids", []):
            out[str(pid)] = code
    return out


def _recent_history(state: dict, now: datetime,
                    event: str) -> list[dict]:
    """Return player_history events of a given type within the last
    _HISTORY_DAYS, sorted oldest-first."""
    cutoff = now - timedelta(days=_HISTORY_DAYS)
    out = []
    for e in state.get("player_history", []):
        if e.get("event") != event:
            continue
        try:
            at = datetime.fromisoformat(e["at"])
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if at >= cutoff:
            out.append(e)
    out.sort(key=lambda e: e.get("at", ""))
    return out


def _aggregate_by_user(state: dict, pid_to_code: dict[str, str],
                      now: datetime, config: dict) -> tuple[dict, list]:
    """Group player records by user_id across campaigns; also collect
    at-risk records keyed by campaign for the footer section."""
    by_user: dict[str, dict] = {}
    at_risk: list[tuple[str, dict, int | None]] = []
    for player in state.get("players", {}).values():
        uid = str(player.get("user_id", ""))
        pid = str(player.get("pbp_topic_id", ""))
        code = pid_to_code.get(pid, "?")
        if not uid:
            continue
        days = _days_ago(player, now)
        slot = by_user.setdefault(uid, {
            "name": player.get("first_name")
                    or player.get("username") or "?",
            "permanent": is_permanent(player, config),
            "campaigns": [],
            "most_recent_days": days,
        })
        slot["campaigns"].append(code)
        if days is not None and (
                slot["most_recent_days"] is None
                or days < slot["most_recent_days"]):
            slot["most_recent_days"] = days
        if _at_risk_status(player, config) is not None:
            at_risk.append((code, player, days))
    return by_user, at_risk


def build_footer(state: dict, pid_to_code: dict[str, str],
                 now: datetime,
                 at_risk: list[tuple[str, dict, int | None]],
                 config: dict,
                 ) -> list[str]:
    """Build the at-risk / recently-joined / recently-left lines.

    Returned as a list of strings so the caller can either append
    them to the player table (build_roster_players) or attach them
    to a different parent block (build_roster_all in roster_views).
    Empty list when nothing to report.
    """
    lines: list[str] = []
    if at_risk:
        lines.append("\n\U0001f525 At risk (recent inactivity warning):")
        at_risk.sort(key=lambda t: (t[2] if t[2] is not None else 0),
                     reverse=True)
        for code, player, days in at_risk:
            name = player.get("first_name") or "?"
            risk = _at_risk_status(player, config) or ""
            age = f"{days}d ago" if days is not None else "?"
            warned = player.get("last_warned_week", 0)
            lines.append(f"  {risk} {code} {name} \u2014 last post {age} "
                         f"(week-{warned} warning issued)")
    joined = _recent_history(state, now, "join")
    left = _recent_history(state, now, "leave")
    if joined:
        lines.append(f"\n\U0001f195 Recently joined (last {_HISTORY_DAYS}d):")
        for e in joined:
            date = e.get("at", "")[:10]
            code = pid_to_code.get(str(e.get("pid", "")), "?")
            lines.append(f"  \u2022 {date}  {code}  {e.get('name', '?')}")
    if left:
        lines.append(f"\n\u2796 Recently left (last {_HISTORY_DAYS}d):")
        for e in left:
            date = e.get("at", "")[:10]
            code = pid_to_code.get(str(e.get("pid", "")), "?")
            lines.append(f"  \u2022 {date}  {code}  {e.get('name', '?')}")
    return lines


def build_roster_players(config: dict, state: dict) -> str:
    """Cross-campaign player table + at-risk + history footer."""
    now = datetime.now(timezone.utc)
    pid_to_code = _pid_to_code(config)
    by_user, at_risk = _aggregate_by_user(state, pid_to_code, now, config)

    rows = sorted(by_user.values(),
                  key=lambda r: (r["most_recent_days"]
                                 if r["most_recent_days"] is not None
                                 else 9999))

    n_pairs = len(list(config.get("topic_pairs", [])))
    lines = [f"\U0001f4cb Player Roster \u2014 {len(rows)} unique players "
             f"across {n_pairs} campaigns\n"]
    for r in rows:
        camps = " ".join(sorted(set(r["campaigns"])))
        days = r["most_recent_days"]
        age = f"{days}d ago" if days is not None else "never"
        tag = " [perm]" if r["permanent"] else ""
        lines.append(f"  \u2022 {r['name']:18s}{tag:7s}  "
                     f"{camps:18s}  last: {age}")

    lines.extend(build_footer(state, pid_to_code, now, at_risk, config))
    return "\n".join(lines)
