"""Message count milestones."""

from datetime import datetime, timezone
from helpers import build_topic_maps
import telegram as tg


_CAMPAIGN_MILESTONE_STEP = 500
_GLOBAL_MILESTONE_STEP = 5000

_MILESTONE_ICONS = {
    500: "🎯", 1000: "🏅", 1500: "⚡", 2000: "🔥", 2500: "⭐",
    3000: "💎", 3500: "🌟", 4000: "👑", 4500: "🏆", 5000: "🎆",
}


def check_message_milestones(config: dict, state: dict, *, now: datetime | None = None, maps=None, **_kw) -> None:
    """Celebrate when a campaign or the global total crosses a message milestone."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    maps = maps or build_topic_maps(config)
    celebrated = state.setdefault("celebrated_milestones", {})

    global_total = 0

    for pid, name in maps.to_name.items():
        # Count total messages for this campaign
        counts = state.get("message_counts", {}).get(pid, {})
        campaign_total = sum(counts.values())
        global_total += campaign_total

        if campaign_total < _CAMPAIGN_MILESTONE_STEP:
            continue

        # Find highest milestone crossed
        milestone = (campaign_total // _CAMPAIGN_MILESTONE_STEP) * _CAMPAIGN_MILESTONE_STEP

        campaign_key = f"campaign:{pid}"
        last_celebrated = celebrated.get(campaign_key, 0)

        if milestone > last_celebrated:
            icon = _MILESTONE_ICONS.get(milestone, "🎯")
            chat_topic_id = maps.to_chat.get(pid)
            if chat_topic_id:
                message = (
                    f"{icon} {name} has hit {milestone:,} PBP messages!\n\n"
                    f"That's {milestone:,} posts of collaborative storytelling. "
                    f"Every single one moved the story forward."
                )
                if tg.send_message(group_id, bot_topic or chat_topic_id, message):
                    celebrated[campaign_key] = milestone
                    print(f"Milestone: {name} hit {milestone:,} messages")

    # Global milestone
    if global_total >= _GLOBAL_MILESTONE_STEP:
        global_milestone = (global_total // _GLOBAL_MILESTONE_STEP) * _GLOBAL_MILESTONE_STEP
        last_global = celebrated.get("global", 0)

        if global_milestone > last_global:
            leaderboard_topic = config.get("leaderboard_topic_id")
            if leaderboard_topic:
                message = (
                    f"🎆 Path Wars has hit {global_milestone:,} total PBP messages "
                    f"across all campaigns!\n\n"
                    f"That's {global_milestone:,} posts of adventure, intrigue, "
                    f"and terrible puns spread across {len(maps.to_name)} campaigns."
                )
                if tg.send_message(group_id, leaderboard_topic, message):
                    celebrated["global"] = global_milestone
                    print(f"Global milestone: {global_milestone:,} total messages")
