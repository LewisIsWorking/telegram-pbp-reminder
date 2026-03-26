"""
Campaign report builders.

/campaign — comprehensive campaign scoreboard
Roster helpers shared with post_roster_summary.
"""

from datetime import datetime, timezone, timedelta

import helpers
from helpers import (
    timestamps_in_window, deduplicate_posts,
    calc_avg_gap_str, fmt_relative_date, posts_str,
)


def roster_user_stats(raw_timestamps: list[str], total_count: int, now: datetime) -> dict:
    """Compute roster stats from raw ISO timestamp strings.

    Returns dict with: total, sessions, week_count, avg_gap_str, last_post_str, streak.
    """
    week_ago = now - timedelta(days=7)
    all_posts = sorted(datetime.fromisoformat(ts) for ts in raw_timestamps)
    sessions = deduplicate_posts(all_posts)
    week_count = len(deduplicate_posts(timestamps_in_window(raw_timestamps, week_ago)))
    avg_gap_str = calc_avg_gap_str(raw_timestamps)
    last_post_str = fmt_relative_date(now, all_posts[-1]) if all_posts else "N/A"
    streak = helpers.calc_streak(raw_timestamps, now)
    return {
        "total": total_count,
        "sessions": len(sessions),
        "week_count": week_count,
        "avg_gap_str": avg_gap_str,
        "last_post_str": last_post_str,
        "streak": streak,
    }


def roster_block(label: str, username: str, stats: dict,
                 extra_line: str = "") -> str:
    """Format a single roster entry (player or GM)."""
    s_suffix = "s" if stats["sessions"] != 1 else ""
    block = f"{label}\n"
    if username:
        block += f"- @{username}.\n"
    if extra_line:
        block += f"- {extra_line}\n"
    block += (
        f"- {posts_str(stats['total'])} total.\n"
        f"- {stats['sessions']} posting session{s_suffix}.\n"
        f"- {posts_str(stats['week_count'])} in the last week.\n"
        f"- Average gap between posting: {stats['avg_gap_str']}.\n"
        f"- Last post: {stats['last_post_str']}."
    )
    streak = stats.get("streak", 0)
    if streak >= 2:
        block += f"\n- 🔥 {streak}-day streak!"
    return block


def build_campaign_report(pid: str, config: dict, state: dict, gm_ids: set) -> str:
    """Build a comprehensive campaign scoreboard for /campaign command."""
    now = datetime.now(timezone.utc)

    # Campaign metadata
    pair = None
    for p in config.get("topic_pairs", []):
        if str(p["pbp_topic_ids"][0]) == pid:
            pair = p
            break
    name = pair["name"] if pair else "Unknown"
    created_str = pair.get("created", "") if pair else ""

    # Header
    lines = [f"━━ {name} ━━"]

    paused = state.get("paused_campaigns", {}).get(pid)
    if paused:
        lines.append(f"⏸️ PAUSED: {paused.get('reason', 'No reason')}")

    if created_str:
        created = datetime.strptime(created_str, "%Y-%m-%d").date()
        age_days = (now.date() - created).days
        if age_days >= 365:
            years = age_days // 365
            lines.append(f"Running since {created.strftime('%B %d, %Y')} W{created.isocalendar()[1]} ({years}y {age_days % 365}d)")
        else:
            lines.append(f"Running since {created.strftime('%B %d, %Y')} W{created.isocalendar()[1]} ({age_days}d)")

    # Players and counts (excluding GMs)
    players = [
        p_val for p_val in state.get("players", {}).values()
        if p_val.get("pbp_topic_id") == pid and p_val.get("user_id", "") not in gm_ids
    ]
    counts = state.get("message_counts", {}).get(pid, {})
    topic_ts = helpers.get_topic_timestamps(state, pid)
    player_count = len(players)

    lines.append(f"\nParty: {player_count}/{helpers.REQUIRED_PLAYERS}")
    if player_count < helpers.REQUIRED_PLAYERS:
        needed = helpers.REQUIRED_PLAYERS - player_count
        lines[-1] += f" (needs {needed} more)"

    # Weekly pace
    pace = helpers.pace_split(topic_ts, gm_ids, now)
    total_this = pace["gm_this"] + pace["player_this"]
    total_last = pace["gm_last"] + pace["player_last"]
    trend = helpers.trend_icon(total_this, total_last)

    lines.append(f"\n{trend} This week: {posts_str(total_this)} ({pace['player_this']} player, {pace['gm_this']} GM)")
    if total_last > 0:
        lines.append(f"Last week: {posts_str(total_last)} ({pace['player_last']} player, {pace['gm_last']} GM)")

    # Roster
    lines.append("\n━━ Roster ━━")
    sorted_players = sorted(players, key=lambda p: counts.get(p["user_id"], 0), reverse=True)

    # GM first
    for gm_id in gm_ids:
        gm_count = counts.get(gm_id, 0)
        raw_ts = topic_ts.get(gm_id, [])
        if gm_count > 0 and raw_ts:
            stats = roster_user_stats(raw_ts, gm_count, now)
            lines.append("\n" + roster_block("GM", "", stats))

    for player in sorted_players:
        uid = player["user_id"]
        raw_ts = topic_ts.get(uid, [])
        if not raw_ts:
            continue
        full = helpers.player_full_name(player)
        stats = roster_user_stats(raw_ts, counts.get(uid, 0), now)
        lines.append("\n" + roster_block(full, player.get("username", ""), stats))

    # At-risk players
    at_risk = []
    for p in players:
        last_post = datetime.fromisoformat(p["last_post_time"])
        inactive_days = helpers.days_since(now, last_post)
        if inactive_days >= 7:
            week_num = int(inactive_days / 7)
            at_risk.append(f"- {p['first_name']}: {int(inactive_days)}d inactive (warning {week_num}/3)")

    if at_risk:
        lines.append("\n⚠️ At Risk:")
        lines.extend(at_risk)

    # Active combat
    combat = state.get("combat", {}).get(pid)
    if combat and combat.get("active"):
        acted = set(combat.get("players_acted", []))
        missing = [p["first_name"] for p in players if p["user_id"] not in acted]
        lines.append(f"\n⚔️ Combat: Round {combat['round']}, {combat['current_phase']}' turn")
        if missing and combat["current_phase"] == "players":
            lines.append(f"Waiting on: {', '.join(missing)}")

    # Current scene
    scene = state.get("current_scenes", {}).get(pid)
    if scene:
        lines.append(f"\n🎭 Scene: {scene}")

    # GM notes
    notes = state.get("campaign_notes", {}).get(pid, [])
    if notes:
        lines.append(f"\n📝 Notes ({len(notes)}):")
        for i, note in enumerate(notes[-3:], start=max(1, len(notes) - 2)):
            lines.append(f"  {i}. {note['text']}")
        if len(notes) > 3:
            lines.append(f"  … and {len(notes) - 3} more (/notes to see all)")

    return "\n".join(lines)
