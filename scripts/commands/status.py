"""Campaign health snapshot: /status and /overview."""

from datetime import datetime, timezone, timedelta

import helpers
from helpers import (
    build_topic_maps, timestamps_in_window, posts_str,
)

def build_status(pid: str, campaign_name: str, state: dict, gm_ids: set,
                 config: dict | None = None) -> str:
    """Build a quick campaign health snapshot for /status command."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # Player count (excluding GMs)
    players = [
        p for p in state.get("players", {}).values()
        if p.get("pbp_topic_id") == pid and p.get("user_id", "") not in gm_ids
    ]
    player_count = len(players)

    # Last post
    topic_state = state.get("topics", {}).get(pid)
    if topic_state:
        last_time = datetime.fromisoformat(topic_state["last_message_time"])
        elapsed = helpers.hours_since(now, last_time)
        if elapsed < 1:
            last_str = "just now"
        elif elapsed < 24:
            last_str = f"{int(elapsed)}h ago"
        else:
            last_str = f"{int(elapsed / 24)}d {int(elapsed % 24)}h ago"
    else:
        last_str = "no posts tracked yet"

    # Posts this week
    topic_ts = helpers.get_topic_timestamps(state, pid)
    gm_week = player_week = 0
    for uid, timestamps in topic_ts.items():
        count = len(timestamps_in_window(timestamps, week_ago))
        if uid in gm_ids:
            gm_week += count  # pragma: no cover
        else:
            player_week += count

    # At-risk players (1+ weeks inactive)
    at_risk = []
    for p in players:
        last_post = datetime.fromisoformat(p["last_post_time"])
        days_inactive = helpers.days_since(now, last_post)
        if days_inactive >= 7:
            at_risk.append(f"{p['first_name']} ({int(days_inactive)}d)")

    # Active combat
    combat = state.get("combat", {}).get(pid)
    combat_str = ""
    if combat and combat.get("active"):
        combat_str = f"\nCombat: Round {combat['round']}, {combat['current_phase']}' turn"

    lines = [
        f"Status for {campaign_name}:",
        f"Party: {player_count}/{helpers.REQUIRED_PLAYERS}",
        f"Last post: {last_str}",
        f"This week: {player_week} player + {gm_week} GM posts",
    ]
    if at_risk:
        lines.append(f"At risk: {', '.join(at_risk)}")

    # Away players
    away_names = []
    for p in players:
        uid = p.get("user_id", "")
        record = helpers.is_away(state, pid, uid, now)
        if record:
            away_names.append(p["first_name"])
    if away_names:
        lines.append(f"✈️ Away: {', '.join(away_names)}")

    if combat_str:
        lines.append(combat_str)

    paused = state.get("paused_campaigns", {}).get(pid)
    if paused:
        lines.append(f"⏸️ PAUSED: {paused.get('reason', 'No reason')}")

    scene = state.get("current_scenes", {}).get(pid)
    if scene:
        lines.append(f"🎭 Scene: {scene}")

    active_quests = [q for q in state.get("quests", {}).get(pid, [])
                     if q.get("status") == "active"]
    if active_quests:
        lines.append(f"📋 {len(active_quests)} active quest{'s' if len(active_quests) != 1 else ''}")

    # HP tracker count
    hp_entries = state.get("hp_tracker", {}).get(pid, {})
    if hp_entries:
        alive = sum(1 for h in hp_entries.values() if h["current"] > 0)
        lines.append(f"❤️ {alive}/{len(hp_entries)} enemies standing (/hp)")

    # Conditions count
    conds = state.get("conditions", {}).get(pid, [])
    if conds:
        lines.append(f"⚡ {len(conds)} active condition{'s' if len(conds) != 1 else ''}")

    # Active clocks
    clocks = state.get("clocks", {}).get(pid, {})
    if clocks:
        incomplete = sum(1 for c in clocks.values() if c["filled"] < c["segments"])
        lines.append(f"⏱️ {incomplete}/{len(clocks)} clock{'s' if len(clocks) != 1 else ''} ticking")

    # Queue count
    if config:
        from commands.queue_scan import scan_transcripts
        scanned = scan_transcripts(config, state)
        q = len(scanned.get(pid, {}).get("entries", []))
        if q:
            lines.append(f"📬 {q} unreplied player message{'s' if q != 1 else ''}")  # pragma: no cover

    return "\n".join(lines)

def build_overview(config: dict, state: dict) -> str:
    """Build a compact cross-campaign overview for /overview command."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    maps = build_topic_maps(config)

    lines = ["Path Wars — Campaign Overview:", ""]

    total_posts_all = 0
    total_players_all = 0
    campaigns_data = []

    for pid, name in maps.to_name.items():
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        topic_ts = helpers.get_topic_timestamps(state, pid)
        topic_state = state.get("topics", {}).get(pid)

        # Weekly posts
        gm_week = player_week = 0
        for uid, timestamps in topic_ts.items():
            count = len(timestamps_in_window(timestamps, week_ago))  # pragma: no cover
            if uid in gm_ids:  # pragma: no cover
                gm_week += count  # pragma: no cover
            else:  # pragma: no cover
                player_week += count  # pragma: no cover
        total_week = gm_week + player_week
        total_posts_all += total_week

        # Last post age
        if topic_state:
            last_time = datetime.fromisoformat(topic_state["last_message_time"])
            hours = helpers.hours_since(now, last_time)
            if hours < 1:
                age = "<1h"  # pragma: no cover
            elif hours < 24:
                age = f"{int(hours)}h"
            else:
                age = f"{int(hours / 24)}d"
        else:
            age = "—"  # pragma: no cover

        # Player count (excluding GMs)
        players = [p for p in state.get("players", {}).values()
                    if p.get("pbp_topic_id") == pid and p.get("user_id", "") not in gm_ids]
        player_count = len(players)
        total_players_all += player_count

        # Combat
        combat = state.get("combat", {}).get(pid, {})
        combat_flag = " ⚔️" if combat.get("active") else ""

        # Paused
        paused = state.get("paused_campaigns", {}).get(pid)
        pause_flag = " ⏸️" if paused else ""

        # Health icon
        health = helpers.health_icon(total_week)

        campaigns_data.append({
            "name": name, "total": total_week, "players": player_count,
            "age": age, "combat": combat_flag, "pause": pause_flag,
            "health": health,
        })

    for c in campaigns_data:
        line = f"{c['health']} {c['name']}: {posts_str(c['total'])} this week"
        line += f" | {c['players']} players | Last: {c['age']}"
        line += c["combat"] + c["pause"]
        lines.append(line)

    lines.append("")
    lines.append(f"Total: {posts_str(total_posts_all)} across {len(campaigns_data)} campaigns, {total_players_all} active players")

    return "\n".join(lines)
