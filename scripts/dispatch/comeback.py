"""Comeback alert: notify when a player breaks a long silence."""

from datetime import datetime, timezone

import helpers
import telegram as tg


SILENCE_THRESHOLD_DAYS = 5


def check_comeback(parsed: dict, old_player: dict, state: dict,
                   config: dict, gm_ids: set) -> None:
    """Check if a returning player broke a long silence and send alert."""
    if not old_player.get("last_post_time"):
        return  # pragma: no cover

    text = parsed.get("text", "")
    if text.startswith("/"):
        return  # pragma: no cover

    pid = parsed["pid"]
    user_id = parsed["user_id"]
    user_name = parsed["user_name"]
    campaign_name = parsed["campaign_name"]
    msg_time_iso = parsed["msg_time_iso"]
    group_id = config["group_id"]

    try:
        last = datetime.fromisoformat(old_player["last_post_time"])
        gap = helpers.days_since(datetime.fromisoformat(msg_time_iso), last)

        if gap < SILENCE_THRESHOLD_DAYS:
            return

        bot_topic = config.get("bot_topic_id")
        if not bot_topic:
            return

        char = helpers.character_name(config, pid, user_id)
        tag = f" ({char})" if char else ""

        gm_at = _find_gm_mention(state, gm_ids)
        player_at = _find_player_mention(parsed)

        tg.send_message(
            group_id, bot_topic,
            f"━━━━━━━━━━━━━━━━\n"
            f"👀 {user_name}{tag} posted in {campaign_name} "
            f"after {int(gap)}d of silence!\n{gm_at}{player_at}")

        print(f"Comeback: {user_name} in {campaign_name} ({int(gap)}d)")

    except (ValueError, TypeError):
        pass


def _find_gm_mention(state: dict, gm_ids: set) -> str:
    """Find the GM's @username for mentioning."""
    return next(
        (f"@{p.get('username')}"
         for p in state.get("players", {}).values()
         if p.get("user_id") in {str(u) for u in gm_ids}
         and p.get("username")),
        "@PathWars"
    )


def _find_player_mention(parsed: dict) -> str:
    """Build the player's @mention string."""
    username = parsed.get("username", "")
    return f" @{username}" if username else ""
