"""Auto-post roster overview every 3 days, or immediately when roster changes."""

from datetime import datetime, timezone

import telegram as tg
from commands.roster import build_roster_overview, _active_players, _TARGET

_INTERVAL_DAYS = 3
_NUDGE_KEY = "last_roster_nudge"
_SNAP_KEY = "last_roster_snapshot"


def _roster_snapshot(config: dict, state: dict) -> str:
    """Build a compact string summarising current roster counts per campaign."""
    parts = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        count = len(_active_players(pid, state))
        target = pair.get("roster_target", _TARGET)
        parts.append(f"{pair.get('code',pid)}:{count}/{target}")
    return "|".join(parts)


def _needs_nudge(config: dict, state: dict) -> bool:
    """Return True if any campaign is below its target."""
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        target = pair.get("roster_target", _TARGET)
        if len(_active_players(pid, state)) < target:
            return True
    return False


def post_roster_nudge(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post roster overview if below target AND (3 days elapsed OR roster changed)."""
    now = now or datetime.now(timezone.utc)

    if not _needs_nudge(config, state):
        return

    snapshot = _roster_snapshot(config, state)
    last_snap = state.get(_SNAP_KEY)
    roster_changed = snapshot != last_snap

    last_str = state.get(_NUDGE_KEY)
    interval_elapsed = True
    if last_str and not roster_changed:
        try:
            last = datetime.fromisoformat(last_str)
            interval_elapsed = (now - last).total_seconds() >= _INTERVAL_DAYS * 86400
        except (ValueError, TypeError):
            pass

    if not roster_changed and not interval_elapsed:
        return

    group_id = config.get("group_id")
    bot_topic = config.get("bot_topic_id")
    if not group_id or not bot_topic:
        return  # pragma: no cover

    tg.send_message(group_id, bot_topic, build_roster_overview(config, state))
    state[_NUDGE_KEY] = now.isoformat()
    state[_SNAP_KEY] = snapshot
    print("Roster nudge posted")
