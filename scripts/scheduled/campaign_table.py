"""
Weekly campaign overview table.

Posts a monospaced summary of all campaigns showing
player counts, activity, and health status.
"""

from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg

# Last post age → health icon
# 🟢 < 1 day   — healthy, active today
# 🟡 1-3 days  — slowing down
# 🟠 3-5 days  — concerning, needs attention
# 🔴 5+ days   — stalled, no recent activity

REQUIRED_PLAYERS = 6


def build_campaign_table(config: dict, state: dict,
                         now: datetime | None = None) -> str:
    """Build the campaign overview table."""
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_num = now.isocalendar()[1]

    lines = [f"📊 Campaign Overview (W{week_num})\n"]

    from commands.queue_scan import scan_transcripts
    scanned = scan_transcripts(config, state)

    rows = []
    for pid, code, name, pair in helpers.iter_campaigns(config):
        is_hybrid_camp = helpers.is_hybrid(config, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        topic_ts = helpers.get_topic_timestamps(state, pid)
        active = sum(
            1 for uid, ts in topic_ts.items()
            if uid not in gm_ids and ts
        )

        registry = state.get("player_registry", {}).get(pid, {})
        total_registered = sum(
            1 for uid, entry in registry.items()
            if entry.get("id", 0) != 0
        )

        week_posts = 0
        for uid, timestamps in topic_ts.items():
            for ts in timestamps:
                try:
                    if datetime.fromisoformat(ts) > week_ago:
                        week_posts += 1
                except (ValueError, TypeError):
                    pass

        topic = state.get("topics", {}).get(pid, {})
        last_time = topic.get("last_message_time")
        age, days_val = _calc_age(last_time, now)
        icon = _health_icon(days_val)

        queue = len(scanned.get(pid, {}).get("entries", []))
        q_str = f"📋{queue}" if queue else ""

        short_name = _truncate(name, 18)
        rows.append({
            "code": code, "name": short_name,
            "active": active, "total": total_registered,
            "week": week_posts, "age": age,
            "icon": icon, "queue": q_str,
            "hybrid": is_hybrid_camp,
        })

    rows.sort(key=lambda r: r["active"])

    lines.append("Campaign           Code Players Total Week Last")
    for r in rows:
        line = (f"{r['icon']} {r['name']:<18s} {r['code']:<5s}"
                f"{r['active']:>3d}   {r['total']:>3d}  "
                f"{r['week']:>3d}  {r['age']:>3s}")
        if r["queue"]:
            line += f"  {r['queue']}"
        lines.append(line)

    total_active = sum(r["active"] for r in rows)
    total_week = sum(r["week"] for r in rows)
    lines.append(f"\nTotal: {total_active} active players, {total_week} posts this week")
    lines.append("\n🟢 <1d  🟡 1-3d  🟠 3-5d  🔴 5d+")

    eligible = [r for r in rows
                if not r["hybrid"] and r["active"] < REQUIRED_PLAYERS]
    if eligible:
        neediest = eligible[0]
        needed = REQUIRED_PLAYERS - neediest["active"]
        lines.append(
            f"\n⚠️ {neediest['code']}: {neediest['name']} needs players "
            f"the most ({neediest['active']}/{REQUIRED_PLAYERS}, "
            f"needs {needed} more)")

    return "\n".join(lines)


def post_campaign_table(config: dict, state: dict, *,
                        now: datetime | None = None, **_kw) -> None:
    """Post the weekly campaign table to the bot topic."""
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    now = now or datetime.now(timezone.utc)
    last = state.get("last_campaign_table")
    if last and not helpers.interval_elapsed(last, 6.5, now):
        return
    table = build_campaign_table(config, state, now)
    if tg.send_message(config["group_id"], bot_topic,
                       f"━━━━━━━━━━━━━━━━\n{table}"):
        state["last_campaign_table"] = now.isoformat()
        print("Posted weekly campaign table")


def _calc_age(last_time: str | None, now: datetime) -> tuple[str, float]:
    if not last_time:
        return "—", 99.0
    hours = helpers.hours_since(now, datetime.fromisoformat(last_time))
    if hours < 24:
        return f"{int(hours)}h", hours / 24
    return f"{int(hours / 24)}d", hours / 24


def _health_icon(days_val: float) -> str:
    if days_val < 1:
        return "🟢"
    elif days_val < 3:
        return "🟡"
    elif days_val < 5:
        return "🟠"
    return "🔴"


def _truncate(s: str, length: int) -> str:
    return s[:length - 1] + "…" if len(s) > length else s
