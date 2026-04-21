"""Auto-post roster overview every 3 days while any campaign is below target."""

from datetime import datetime, timezone

import telegram as tg
from commands.roster import build_roster_overview

_INTERVAL_DAYS = 3
_STATE_KEY = "last_roster_nudge"


def post_roster_nudge(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post /roster overview to bot topic if any campaign is below target
    and at least 3 days have passed since the last post."""
    now = now or datetime.now(timezone.utc)

    last_str = state.get(_STATE_KEY)
    if last_str:
        try:
            last = datetime.fromisoformat(last_str)
            if (now - last).total_seconds() < _INTERVAL_DAYS * 86400:
                return
        except (ValueError, TypeError):
            pass

    from helpers_pkg.constants import _TARGET as DEFAULT_TARGET
    pairs = config.get("topic_pairs", [])
    from commands.roster import _active_players
    needs_players = any(
        len(_active_players(str(p["pbp_topic_ids"][0]), state))
        < p.get("roster_target", DEFAULT_TARGET)
        for p in pairs
    )
    if not needs_players:
        return

    group_id = config.get("group_id")
    bot_topic = config.get("bot_topic_id")
    if not group_id or not bot_topic:
        return  # pragma: no cover

    msg = build_roster_overview(config, state)
    tg.send_message(group_id, bot_topic, msg)
    state[_STATE_KEY] = now.isoformat()
    print("Roster nudge posted")
