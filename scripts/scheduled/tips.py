"""Daily tip posting."""

import random
from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps
import telegram as tg
from scheduled.tips_data import _TIPS


def post_daily_tip(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a random tip to the dedicated bot topic once per day."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return

    now = now or datetime.now(timezone.utc)

    # Check daily interval
    last_tip_str = state.get("last_daily_tip")
    if last_tip_str:
        last_tip = datetime.fromisoformat(last_tip_str)
        if helpers.hours_since(now, last_tip) < 22:
            return

    # Pick a tip we haven't used recently
    used_tips = state.get("used_tip_indices", [])
    available = [i for i in range(len(_TIPS)) if i not in used_tips]
    if not available:
        available = list(range(len(_TIPS)))
        used_tips = []

    tip_idx = random.choice(available)

    print(f"Daily tip #{tip_idx} to bot topic {bot_topic}")
    if tg.send_message(group_id, bot_topic, "━━━━━━━━━━━━━━━━\n" + _TIPS[tip_idx], parse_mode="HTML"):
        state["last_daily_tip"] = now.isoformat()
        used_tips.append(tip_idx)
        state["used_tip_indices"] = used_tips
