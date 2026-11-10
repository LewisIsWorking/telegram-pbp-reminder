"""Daily GM digest of players who have waited a long time on their combat turn.

Added 2026-11-10. The bot already pings players still to act in the combat
topic every ``combat_ping_hours``. Some players need a personal message from
the GM as well, so once a day this lists, in the GM queue topic, everyone who
has been waiting at least ``TURN_DIGEST_HOURS`` on a players' phase.

Names are plain text, not mentions: the line is for the GM, so it must not
ping the player again. Anyone ``/away`` is left out, and nothing is posted
when nobody is overdue.
"""

import html
from datetime import datetime, timezone

import helpers
import telegram as tg
from combat.display import format_elapsed
from combat.foundry_sync import SOURCE as FOUNDRY

TURN_DIGEST_HOURS = 24
REPOST_HOURS = 22
STATE_KEY = "last_turn_digest"


def _pair_for_pid(config: dict, pid: str) -> dict | None:
    return next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)


def _topic_link(config: dict, pair: dict) -> str | None:
    topic = pair.get("combat_topic_id")
    if not topic:
        return None
    group_id, username = helpers.campaign_link_target(config, pair)
    if username:
        return f"https://t.me/{username}/{topic}"
    return f"https://t.me/c/{str(group_id).removeprefix('-100')}/{topic}"


def _waiting_ids(state: dict, pid: str, combat: dict) -> list[str]:
    """Who is still to act: Foundry knows exactly; a /combat fight is everyone not marked acted."""
    if combat.get("source") == FOUNDRY:
        return list(combat.get("waiting_user_ids", []))
    acted_raw = combat.get("players_acted", {})
    acted = set(acted_raw.keys()) if isinstance(acted_raw, dict) else set(acted_raw)
    return [p["user_id"] for p in helpers.players_by_campaign(state).get(pid, [])
            if p["user_id"] not in acted]


def overdue_turns(config: dict, state: dict, now: datetime) -> list[dict]:
    """One entry per player waiting TURN_DIGEST_HOURS or more, longest wait first."""
    names = {(p.get("pbp_topic_id"), p["user_id"]): p.get("first_name") or "player"
             for p in state.get("players", {}).values() if "user_id" in p}
    found = []
    for pid, combat in state.get("combat", {}).items():
        if not combat.get("active") or combat.get("current_phase") != "players":
            continue
        if not helpers.feature_enabled(config, pid, "combat"):
            continue
        hours = helpers.hours_since(now, datetime.fromisoformat(combat["phase_started_at"]))
        if hours < TURN_DIGEST_HOURS:
            continue
        pair = _pair_for_pid(config, pid) or {}
        for uid in _waiting_ids(state, pid, combat):
            if helpers.is_away(state, pid, uid, now):
                continue
            found.append({
                "name": names.get((pid, uid), "player"),
                "campaign": pair.get("name") or combat.get("campaign_name", pid),
                "hours": hours,
                "link": _topic_link(config, pair),
            })
    return sorted(found, key=lambda e: -e["hours"])


def build_digest(entries: list[dict]) -> str:
    lines = ["📨 <b>Combat turns waiting 24h+</b>, a DM might help:"]
    for e in entries:
        line = (f"• {html.escape(e['name'])}, {html.escape(e['campaign'])}, "
                f"waiting {format_elapsed(e['hours'])}")
        if e["link"]:
            line += f"\n  {e['link']}"
        lines.append(line)
    return "\n".join(lines)


def post_turn_digest(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post the digest to the GM queue topic, at most once every REPOST_HOURS."""
    topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    if not topic:
        return
    now = now or datetime.now(timezone.utc)
    last = state.get(STATE_KEY)
    if last and helpers.hours_since(now, datetime.fromisoformat(last)) < REPOST_HOURS:
        return
    entries = overdue_turns(config, state, now)
    if not entries:
        return
    print(f"Turn digest: {len(entries)} overdue")
    if tg.send_message(config["group_id"], topic, build_digest(entries), parse_mode="HTML"):
        state[STATE_KEY] = now.isoformat()
