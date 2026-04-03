"""Combat turn pinging and timer expiry."""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg


def check_combat_turns(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """During players' phase, ping players who haven't acted yet."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, combat in list(state["combat"].items()):
        if not combat.get("active"):
            continue

        if not helpers.feature_enabled(config, pid, "combat"):
            continue

        if combat["current_phase"] != "players":
            continue

        # Check if enough time has passed since phase started
        phase_start = datetime.fromisoformat(combat["phase_started_at"])
        hours_elapsed = helpers.hours_since(now, phase_start)

        if hours_elapsed < helpers.COMBAT_PING_HOURS:
            continue

        # Don't re-ping within helpers.COMBAT_PING_HOURS
        last_ping_str = combat.get("last_ping_at")
        if last_ping_str:
            since_ping = helpers.hours_since(now, datetime.fromisoformat(last_ping_str))
            if since_ping < helpers.COMBAT_PING_HOURS:
                continue

        # Find all known players in this campaign who haven't acted
        acted_raw = combat.get("players_acted", {})
        acted = set(acted_raw.keys()) if isinstance(acted_raw, dict) else set(acted_raw)
        missing = [
            helpers.player_mention(p)
            for p in all_campaigns.get(pid, [])
            if p["user_id"] not in acted
            and not helpers.is_away(state, pid, p["user_id"], now)
        ]

        if not missing:
            continue

        campaign_name = combat.get("campaign_name", "Unknown")
        round_num = combat.get("round", 1)
        hours_int = int(hours_elapsed)

        chat_topic_id = maps.to_chat.get(pid)
        if not chat_topic_id:
            continue

        missing_str = ", ".join(missing)
        phase_date = fmt_date(phase_start)
        message = (
            f"Round {round_num} - waiting on: {missing_str}\n"
            f"({hours_int}h since players' phase started on {phase_date})"
        )

        print(f"Combat ping in {campaign_name}: waiting on {missing_str}")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            combat["last_ping_at"] = now.isoformat()


def check_expired_timers(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Check for expired timers and post notifications."""
    if not maps:
        maps = build_topic_maps(config)
    if not now:
        now = datetime.now(timezone.utc)

    group_id = config.get("group_id")
    bot_topic = config.get("bot_topic_id")
    for pid, timer in list(state.get("timers", {}).items()):
        deadline = datetime.fromisoformat(timer["deadline"])
        if now >= deadline:
            # Check if we already notified
            if timer.get("notified"):
                continue  # pragma: no cover

            chat_topic_id = maps.to_chat.get(pid)
            if not chat_topic_id:
                continue  # pragma: no cover
            campaign_name = maps.to_name.get(pid, pid)
            reason = timer.get("reason", "")
            reason_str = f"\n📝 {reason}" if reason else ""

            tg.send_message(group_id, bot_topic or chat_topic_id,
                            f"⏰ Timer expired for {campaign_name}!{reason_str}\n"
                            f"GMs: /canceltimer to clear.")
            timer["notified"] = True
            print(f"Timer expired in {campaign_name}")
