"""
Cross-campaign player profile builder.

Command: /profile.
"""

from datetime import datetime, timezone

import helpers


def build_profile(target_name: str, config: dict, state: dict) -> str:
    """Build cross-campaign profile for /profile command."""
    # Find the target player across all campaigns
    target_name_lower = target_name.lower().lstrip("@")
    found_entries = []

    for key, player in state.get("players", {}).items():
        full_name = helpers.player_full_name(player).lower()
        username = (player.get("username") or "").lower()
        first_name = player.get("first_name", "").lower()

        if (target_name_lower == username or
                target_name_lower == first_name or
                target_name_lower in full_name):
            found_entries.append((key, player))

    if not found_entries:
        return f"No player matching '{target_name}' found across any campaign."

    # Determine display name from first match
    display_name = helpers.player_full_name(found_entries[0][1])
    user_id = found_entries[0][1]["user_id"]

    # Gather stats across all campaigns they're in
    lines = [f"👤 {display_name}", ""]
    total_posts = 0
    total_campaigns = 0
    total_words = 0

    for key, player in found_entries:
        pid = player["pbp_topic_id"]
        campaign_name = player["campaign_name"]
        counts = state.get("message_counts", {}).get(pid, {})
        post_count = counts.get(user_id, 0)
        total_posts += post_count
        total_campaigns += 1

        # Last post
        last_post = player.get("last_post_time", "")
        if last_post:
            last_dt = datetime.fromisoformat(last_post)
            elapsed_h = helpers.hours_since(datetime.now(timezone.utc), last_dt)
            if elapsed_h < 24:
                last_str = f"{int(elapsed_h)}h ago"
            else:
                last_str = f"{int(elapsed_h / 24)}d ago"
        else:
            last_str = "unknown"

        # Character name
        char_name = helpers.character_name(config, pid, user_id)
        char_tag = f" ({char_name})" if char_name else ""

        # Streak
        topic_ts = helpers.get_topic_timestamps(state, pid)
        raw_ts = topic_ts.get(user_id, [])
        streak = helpers.calc_streak(raw_ts, datetime.now(timezone.utc))
        streak_str = f" | 🔥 {streak}d streak" if streak >= 3 else ""

        # Word count
        words = state.get("word_counts", {}).get(pid, {}).get(user_id, 0)
        words_str = f" | {words:,} words" if words > 0 else ""
        total_words += words

        lines.append(f"📖 {campaign_name}{char_tag}")
        lines.append(f"   {post_count} posts{words_str} | Last: {last_str}{streak_str}")

    lines.append("")
    words_summary = f" ({total_words:,} words)" if total_words > 0 else ""
    lines.append(f"Total: {total_posts} posts{words_summary} across {total_campaigns} campaign{'s' if total_campaigns != 1 else ''}")

    return "\n".join(lines)
