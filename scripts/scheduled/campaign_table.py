"""
Weekly campaign overview table.

Posts a monospaced summary of all campaigns showing
player counts, activity, and health status. Rendered
using HTML <pre> blocks so Telegram uses a fixed-width
font and columns stay aligned.
"""

import html
from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg

# Last post age → health icon
# 🟢 < 1 day   — healthy, active today
# 🟡 1-3 days  — slowing down
# 🟠 3-5 days  — concerning, needs attention
# 🔴 5+ days   — stalled, no recent activity

REQUIRED_PLAYERS = 6

# In Telegram <pre> blocks, emoji glyphs are 2 display-cells wide.
# Each data row starts with: emoji (2 cells) + space (1 cell) = 3 cells.
# The header uses 3 leading spaces so "Campaign" aligns under data names.
_HEADER = "   {:<18s} {:>4s} {:>4s} {:>5s} {:>4s}"
_ROW    = "{} {:<18s} {:>4s} {:>4d} {:>5d} {:>4s}{}"


def build_campaign_table(config: dict, state: dict,
                         now: datetime | None = None) -> str:
    """Build the campaign overview table as HTML with monospaced alignment."""
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_num = now.isocalendar()[1]

    from commands.queue_scan import scan_transcripts
    scanned = scan_transcripts(config, state)

    rows = _collect_rows(config, state, scanned, week_ago)
    rows.sort(key=lambda r: r["active"])

    header = _HEADER.format("Campaign", "Code", "Act", "Week", "Last")
    table_lines = [header]
    for r in rows:
        name_safe = html.escape(r["name"])
        line = _ROW.format(
            r["icon"], name_safe, r["code"],
            r["active"], r["week"], r["age"], r["queue"],
        )
        table_lines.append(line)

    total_active = sum(r["active"] for r in rows)
    total_week   = sum(r["week"]   for r in rows)

    title    = f"📊 Campaign Overview (W{week_num})"
    pre      = "<pre>" + "\n".join(table_lines) + "</pre>"
    totals   = (f"Total: {total_active} active players, "
                f"{total_week} posts this week")
    legend   = "🟢 &lt;1d  🟡 1-3d  🟠 3-5d  🔴 5d+"

    parts = [title, "", pre, "", totals, legend]
    parts.extend(_build_warning(rows))
    return "\n".join(parts)


def _collect_rows(config: dict, state: dict,
                  scanned: dict, week_ago: datetime) -> list[dict]:
    """Gather per-campaign data rows."""
    rows = []
    now = datetime.now(timezone.utc)
    for pid, code, name, _pair in helpers.iter_campaigns(config):
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        topic_ts = helpers.get_topic_timestamps(state, pid)

        active = sum(
            1 for uid, ts in topic_ts.items()
            if uid not in gm_ids and ts
        )
        week_posts = _count_week_posts(topic_ts, week_ago)

        topic     = state.get("topics", {}).get(pid, {})
        last_time = topic.get("last_message_time")
        age, days_val = _calc_age(last_time, now)

        queue = len(scanned.get(pid, {}).get("entries", []))
        rows.append({
            "code": code, "name": _truncate(name, 18),
            "active": active, "week": week_posts,
            "age": age, "icon": _health_icon(days_val),
            "queue": f"  📋{queue}" if queue else "",
            "hybrid": helpers.is_hybrid(config, pid),
        })
    return rows


def _count_week_posts(topic_ts: dict, week_ago: datetime) -> int:
    """Count posts in the last 7 days across all users."""
    count = 0
    for timestamps in topic_ts.values():
        for ts in timestamps:
            try:
                if datetime.fromisoformat(ts) > week_ago:
                    count += 1
            except (ValueError, TypeError):
                pass
    return count


def _build_warning(rows: list[dict]) -> list[str]:
    """Return a warning line if any non-hybrid campaign is under-staffed."""
    eligible = [r for r in rows
                if not r["hybrid"] and r["active"] < REQUIRED_PLAYERS]
    if not eligible:
        return []
    n = eligible[0]
    needed = REQUIRED_PLAYERS - n["active"]
    return [
        f"\n⚠️ {html.escape(n['code'])}: {html.escape(n['name'])} "
        f"needs players the most "
        f"({n['active']}/{REQUIRED_PLAYERS}, needs {needed} more)"
    ]


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
                       f"━━━━━━━━━━━━━━━━\n{table}",
                       parse_mode="HTML"):
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
