"""
Weekly campaign overview table.

Posts a monospaced summary of all campaigns showing
player counts, activity, and health status.
"""

from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg


def build_campaign_table(config: dict, state: dict,
                         now: datetime | None = None) -> str:
    """Build the campaign overview table."""
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_num = now.isocalendar()[1]

    lines = [f"📊 Campaign Overview (W{week_num})\n"]

    rows = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        code = pair.get("code", "")
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        # Active players (who have posted)
        topic_ts = helpers.get_topic_timestamps(state, pid)
        active = sum(
            1 for uid, ts in topic_ts.items()
            if uid not in gm_ids and ts
        )

        # Posts this week
        week_posts = 0
        for uid, timestamps in topic_ts.items():
            for ts in timestamps:
                try:
                    if datetime.fromisoformat(ts) > week_ago:
                        week_posts += 1
                except (ValueError, TypeError):
                    pass

        # Last post age
        topic = state.get("topics", {}).get(pid, {})
        last_time = topic.get("last_message_time")
        if last_time:
            hours = helpers.hours_since(now, datetime.fromisoformat(last_time))
            if hours < 24:
                age = f"{int(hours)}h"
            else:
                age = f"{int(hours / 24)}d"
        else:
            age = "—"

        # Health icon
        days = float(age.rstrip("dh")) if age != "—" else 99
        if "d" in age:
            days_val = days
        else:
            days_val = days / 24
        if days_val < 1:
            icon = "🟢"
        elif days_val < 3:
            icon = "🟡"
        elif days_val < 5:
            icon = "🟠"
        else:
            icon = "🔴"

        # Queue count
        from commands.queue_scan import scan_transcripts
        scanned = scan_transcripts(config, state)
        queue = len(scanned.get(pid, {}).get("entries", []))
        q_str = f"📋{queue}" if queue else ""

        short_name = _truncate(name, 18)
        rows.append({
            "code": code,
            "name": short_name,
            "active": active,
            "week": week_posts,
            "age": age,
            "icon": icon,
            "queue": q_str,
        })

    # Sort by active players, least to most
    rows.sort(key=lambda r: r["active"])

    # Build table
    lines.append("Campaign           Code Active Week  Last")
    for r in rows:
        line = (f"{r['icon']} {r['name']:<18s} {r['code']:<4s} "
                f"{r['active']:>4d}   {r['week']:>3d}  {r['age']:>3s}")
        if r["queue"]:
            line += f"  {r['queue']}"
        lines.append(line)

    # Totals
    total_active = sum(r["active"] for r in rows)
    total_week = sum(r["week"] for r in rows)
    lines.append(f"\nTotal: {total_active} active players, {total_week} posts this week")

    return "\n".join(lines)


def post_campaign_table(config: dict, state: dict, *,
                        now: datetime | None = None, **_kw) -> None:
    """Post the weekly campaign table to the bot topic."""
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    now = now or datetime.now(timezone.utc)

    # Post once per week (alongside leaderboard)
    last = state.get("last_campaign_table")
    if last and not helpers.interval_elapsed(last, 6.5, now):
        return

    table = build_campaign_table(config, state, now)
    if tg.send_message(config["group_id"], bot_topic,
                       f"━━━━━━━━━━━━━━━━\n{table}"):
        state["last_campaign_table"] = now.isoformat()
        print("Posted weekly campaign table")


def _truncate(s: str, length: int) -> str:
    """Truncate a string with ellipsis if needed."""
    return s[:length - 1] + "…" if len(s) > length else s
