"""
Weekly campaign overview table.

Posts a per-line summary of all campaigns showing
player counts, activity, and health status. Uses plain
text lines rather than column alignment so emoji widths
don't cause mobile rendering issues.
"""

import html
from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg
from commands.queue_format import entry_age_icon

# Last post age -> health icon uses the same 22-tier GM queue scale
# (entry_age_icon from commands/queue_format.py, input in hours)

REQUIRED_PLAYERS = 6


def build_campaign_table(config: dict, state: dict,
                         now: datetime | None = None) -> str:
    """Build the campaign overview as HTML, one line per campaign."""
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    week_num = now.isocalendar()[1]

    from commands.queue_scan import scan_transcripts
    scanned = scan_transcripts(config, state)

    rows = _collect_rows(config, state, scanned, week_ago)
    rows.sort(key=lambda r: r["active"])

    lines = []
    for r in rows:
        name_safe = html.escape(r["name"])
        q_str = f"  📋{r['qcount']}" if r["qcount"] else ""
        lines.append(
            f"{r['icon']} {name_safe} ({r['code']})"
            f"  {r['active']}p · {r['week']}/wk · {r['age']}{q_str}"
        )

    total_active = sum(r["active"] for r in rows)
    total_week   = sum(r["week"]   for r in rows)

    title   = f"📊 Campaign Overview (W{week_num})"
    pre     = "<pre>" + "\n".join(lines) + "</pre>"
    totals  = (f"Total: {total_active} active players, "
               f"{total_week} posts this week")
    legend  = ("🆕&lt;1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d "
               "🟠6d 🟧7d 🔴8d 🟥9d 🟣10d 🟪11d 🔵12d 🟦13d "
               "🟤14d 🟫15d ⚫16d ⬛17d 💀21d ☠️25d")

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
        age, hours_val = _calc_age(last_time, now)

        queue = len(scanned.get(pid, {}).get("entries", []))
        rows.append({
            "code": code, "name": _truncate(name, 20),
            "active": active, "week": week_posts,
            "age": age, "icon": entry_age_icon(hours_val),
            "qcount": queue,
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
    """Return (age_str, hours_elapsed) for a last-post timestamp."""
    if not last_time:
        return "—", 99.0 * 24
    hours = helpers.hours_since(now, datetime.fromisoformat(last_time))
    if hours < 24:
        return f"{int(hours)}h", hours
    return f"{int(hours / 24)}d", hours




def _truncate(s: str, length: int) -> str:
    return s[:length - 1] + "…" if len(s) > length else s
