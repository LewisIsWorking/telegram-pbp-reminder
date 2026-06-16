"""Leaderboard formatting and posting."""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import build_topic_maps, fmt_date, posts_str
from scheduled.leaderboard_data import _gather_leaderboard_stats
import telegram as tg


def _format_leaderboard(campaign_stats: list, global_player_posts: dict,
                        now: datetime, streaks: list | None = None,
                        state: dict | None = None) -> str:
    """Format the leaderboard message from collected stats."""
    seven_days_ago = now - timedelta(days=7)

    campaign_stats.sort(key=lambda c: c["player_7d"], reverse=True)
    active = [c for c in campaign_stats if c["total_7d"] > 0]
    dead = [c for c in campaign_stats if c["total_7d"] == 0]

    date_from = fmt_date(seven_days_ago)
    date_to = fmt_date(now)

    lines = [f"📊 Weekly Campaign Leaderboard ({date_from} to {date_to})"]

    # Compute week totals across all campaigns
    week_total_player = sum(c["player_7d"] for c in campaign_stats)
    week_total_gm = sum(c["gm_7d"] for c in campaign_stats)
    week_total_all = sum(c["total_7d"] for c in campaign_stats)
    lines.append(
        f"\n📬 This week: {week_total_all} posts "
        f"({week_total_player} player, {week_total_gm} GM) "
        f"across {len(active)} active campaigns."
    )

    for i, c in enumerate(active):
        rank = helpers.rank_icon(i)
        code = c.get("code", "")
        label = f"{code}: {c['name']}" if code else c["name"]
        campaign_block = (
            f"[{rank} {label} {c['trend_icon']}]\n"
            f"- {c['player_7d']} player posts.\n"
            f"- {posts_str(c['total_7d'])} total.\n"
            f"- {c['gm_7d']} GM posts.\n"
            f"- Avg gap: {c['avg_gap_str']}.\n"
            f"- Last post: {c['last_post_str']}."
        )

        player_blocks = []
        for j, p in enumerate(c["top_players"]):
            medal = helpers.rank_icon(j)
            block = f"{medal} {p['full_name']}\n"
            uname = p.get("username", "")
            if uname:
                block += f"- @{uname}\n"
            block += f"- {posts_str(p['count'])}"
            player_blocks.append(block)

        lines.append("\n━━━━━━━━━━━━━━━━\n\n" + campaign_block + "\n\n" + "\n".join(player_blocks))

    if dead:
        lines.append("\n⚠️ Dead campaigns (0 posts in 7 days):")
        for c in dead:
            lines.append(f"💀 [{c['name']}] (last post: {c['last_post_str']})")

    gap_ranked = [c for c in campaign_stats if c["player_avg_gap"] is not None]
    if gap_ranked:
        gap_ranked.sort(key=lambda c: c["player_avg_gap"])
        lines.append("\n━━━━━━━━━━━━━━━━\n\n⏱ Fastest player response gaps:")
        for i, c in enumerate(gap_ranked):
            code = c.get("code", "")
            gl = f"{code}: {c['name']}" if code else c["name"]
            lines.append(f"{helpers.rank_icon(i)} {gl}: {c['player_avg_gap_str']}")

    if global_player_posts:
        lines.append("\n━━━━━━━━━━━━━━━━")
        top_global = sorted(
            global_player_posts.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )
        player_blocks = []
        for i, (uid, pdata) in enumerate(top_global):
            icon = helpers.rank_icon(i)
            campaign_word = "campaign" if pdata["campaigns"] == 1 else "campaigns"
            block = f"{icon} {pdata['full_name']}\n"
            if pdata["username"]:
                block += f"- @{pdata['username']}\n"
            block += f"- {posts_str(pdata['count'])} across {pdata['campaigns']} {campaign_word}"
            player_blocks.append(block)
        lines.append("\n⭐ Top Players of the Week:\n\n" + "\n\n".join(player_blocks))

        # MVP of the Week prize (most active by volume)
        if top_global:
            winner_uid, winner_data = top_global[0]
            winner_name = winner_data["full_name"]
            campaign_word = "campaign" if winner_data["campaigns"] == 1 else "campaigns"
            lines.append(
                f"\n━━━━━━━━━━━━━━━━\n\n"
                f"🏆 MVP of the Week: {winner_name}!\n"
                f"- {posts_str(winner_data['count'])} across "
                f"{winner_data['campaigns']} {campaign_word}.\n"
                f"- Prize: 1 Hero Point in a campaign of your choice! 🎲\n"
                f"- Claim it with the buttons below — or type "
                f"/heropoint <campaign> if they don't respond."
            )

    # Streak leaderboard
    if streaks:
        top_streaks = sorted(streaks, key=lambda s: s["streak"], reverse=True)[:5]
        streak_lines = []
        for i, s in enumerate(top_streaks):
            icon = helpers.rank_icon(i)
            streak_lines.append(f"{icon} {s['name']} — {s['streak']}d streak ({s['campaign']})")
        lines.append("\n━━━━━━━━━━━━━━━━\n\n🔥 Longest Active Streaks:\n\n" + "\n".join(streak_lines))

    # Weekly queue clearance report
    if state:
        from commands.queue_stats import get_week_clears  # pragma: no cover
        week_clears = get_week_clears(state)  # pragma: no cover
        if week_clears:  # pragma: no cover
            lines.append(f"\n━━━━━━━━━━━━━━━━\n\n📬 GM Queue: {week_clears} replies cleared this week.")  # pragma: no cover

    return "\n".join(lines)


def post_campaign_leaderboard(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post a cross-campaign activity leaderboard to the ISSUES topic."""
    group_id = config["group_id"]
    leaderboard_topic = config.get("leaderboard_topic_id")
    if not leaderboard_topic:
        return

    now = now or datetime.now(timezone.utc)

    if not helpers.interval_elapsed(state.get("last_leaderboard"), helpers.LEADERBOARD_INTERVAL_DAYS, now):
        return

    campaign_stats, global_player_posts, all_streaks = _gather_leaderboard_stats(config, state, now)

    if not campaign_stats:
        print("No campaign data for leaderboard")
        return

    message = _format_leaderboard(campaign_stats, global_player_posts, now, all_streaks, state)

    # Track MVP win
    if global_player_posts:
        top = max(global_player_posts.items(), key=lambda x: x[1]["count"])
        winner_uid, winner_data = top
        mvp_wins = state.setdefault("mvp_wins", {})
        entry = mvp_wins.setdefault(winner_uid, {"name": "", "count": 0})
        entry["name"] = winner_data["full_name"]
        entry["count"] += 1
        total = entry["count"]
        # Append MVP total to message
        suffix = f" (MVP x{total})" if total > 1 else ""
        message = message.replace(
            f"🏆 MVP of the Week: {winner_data['full_name']}!",
            f"🏆 MVP of the Week: {winner_data['full_name']}!{suffix}",
        )

    print(f"Posting campaign leaderboard ({len(campaign_stats)} campaigns)")
    if tg.send_message(group_id, leaderboard_topic, message):
        state["last_leaderboard"] = now.isoformat()
        # MVP hero point reminder
        if global_player_posts:
            top = max(global_player_posts.items(), key=lambda x: x[1]["count"])
            winner_uid, winner_data = top
            uname = winner_data.get("username", "")
            mention = f"@{uname}" if uname else winner_data["full_name"]
            from boons.hero_point import post_hero_point_picker
            post_hero_point_picker(winner_uid, winner_data["full_name"],
                                   config, state)
