"""Per-thread and global message count milestones."""

import json
import os
from datetime import datetime, timezone
from helpers import build_topic_maps
import telegram as tg

_STEP = 500
_GLOBAL_STEP = 5000

_MILESTONE_ICONS = {
    500: "🎯", 1000: "🏅", 1500: "⚡", 2000: "🔥", 2500: "⭐",
    3000: "💎", 3500: "🌟", 4000: "👑", 4500: "🏆", 5000: "🎆",
}

_DATA_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'milestone_messages.json'
)

_GENERIC_BODY = (
    "That's {n:,} posts of collaborative storytelling. "
    "Every single one moved the story forward."
)


class _MilestoneMessages:
    """Lazy-loaded campaign-specific milestone message bodies."""

    _data: dict | None = None

    @classmethod
    def _load(cls) -> dict:
        if cls._data is None:
            try:
                with open(_DATA_JSON, encoding='utf-8') as f:
                    cls._data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                cls._data = {}
        return cls._data

    @classmethod
    def get(cls, thread_id: str, milestone: int) -> str | None:
        """Return campaign-specific body text or None if not found."""
        return cls._load().get(str(thread_id), {}).get(str(milestone))

    @classmethod
    def reset(cls) -> None:
        """Clear cached data (for testing)."""
        cls._data = None


def _icon(milestone: int) -> str:
    return _MILESTONE_ICONS.get(milestone, "🎯")


def _thread_label(thread_id: str, config: dict, maps) -> tuple[str, str]:
    """Return (campaign_name, thread_type) for a physical thread_id.

    thread_type is 'PBP', 'COMBAT', or '' for unknown/single-thread campaigns.
    """
    for pair in config.get("topic_pairs", []):
        ids = [str(i) for i in pair.get("pbp_topic_ids", [])]
        if thread_id in ids:
            name = pair.get("name", "Unknown")
            if len(ids) == 1:
                return name, ""
            thread_type = "PBP" if ids[0] == thread_id else "COMBAT"
            return name, thread_type
    return "Unknown", ""


def _group_and_chat(thread_id: str, config: dict, maps) -> tuple[int, int | None]:
    """Return (group_id, chat_topic_id) for a thread."""
    for pair in config.get("topic_pairs", []):
        ids = [str(i) for i in pair.get("pbp_topic_ids", [])]
        if thread_id in ids:
            gid = pair.get("group_id", config["group_id"])
            chat_tid = pair.get("chat_topic_id")
            return gid, chat_tid
    return config["group_id"], None  # pragma: no cover


def _build_msg(thread_id: str, label: str, icon: str, milestone: int) -> str:
    """Assemble milestone message, using campaign-specific body if available."""
    body = _MilestoneMessages.get(thread_id, milestone)
    if body is None:
        body = _GENERIC_BODY.format(n=milestone)
    return f"{icon} {label} has hit {milestone:,} messages!\n\n{body}"


def check_message_milestones(config: dict, state: dict,
                              *, now: datetime | None = None,
                              maps=None, **_kw) -> None:
    """Celebrate when a thread or the global total crosses a 500-post milestone.

    Posts in both the thread where it happened AND the bot topic.
    """
    bot_topic = config.get("bot_topic_id")
    maps = maps or build_topic_maps(config)
    celebrated = state.setdefault("celebrated_milestones", {})

    thread_counts = state.get("thread_message_counts", {})
    global_total = sum(sum(u.values()) for u in thread_counts.values())

    for thread_id, user_counts in thread_counts.items():
        total = sum(user_counts.values())
        if total < _STEP:
            continue

        milestone = (total // _STEP) * _STEP
        key = f"thread:{thread_id}"
        if milestone <= celebrated.get(key, 0):
            continue

        name, thread_type = _thread_label(thread_id, config, maps)
        gid, chat_tid = _group_and_chat(thread_id, config, maps)
        icon = _icon(milestone)
        label = f"{name} {thread_type}" if thread_type else name

        msg = _build_msg(thread_id, label, icon, milestone)

        sent = False
        if tg.send_message(gid, int(thread_id), msg):
            sent = True
        main_gid = config["group_id"]
        if bot_topic and (gid != main_gid or int(thread_id) != bot_topic):
            tg.send_message(main_gid, bot_topic, msg)

        if sent:
            celebrated[key] = milestone
            print(f"Thread milestone: {label} hit {milestone:,} messages")

    if global_total >= _GLOBAL_STEP:
        global_milestone = (global_total // _GLOBAL_STEP) * _GLOBAL_STEP
        if global_milestone > celebrated.get("global", 0):
            leaderboard_topic = config.get("leaderboard_topic_id")
            main_gid = config["group_id"]
            target = leaderboard_topic or bot_topic
            if target:
                msg = (
                    f"🎆 Path Wars has hit {global_milestone:,} total messages "
                    f"across all campaigns!\n\n"
                    f"That's {global_milestone:,} posts of adventure, intrigue, "
                    f"and terrible puns spread across {len(maps.to_name)} campaigns."
                )
                if tg.send_message(main_gid, target, msg):
                    celebrated["global"] = global_milestone
                    print(f"Global milestone: {global_milestone:,} total messages")
