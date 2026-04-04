"""
Combat message tracker.

Routes GM combat commands and tracks player actions during combat.
Notifies GM when all players have acted.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg

from combat.commands import (
    handle_combat_start,
    handle_next_command,
    handle_endcombat,
    handle_enemies_command,
)


def handle_round_command(text: str, pid: str, campaign_name: str,
                         now_iso: str, group_id: int, thread_id: int, state: dict) -> None:
    """Parse and execute /round <N> <players|enemies> command."""
    parts = text.split()
    if len(parts) < 3:
        return

    try:
        round_num = int(parts[1])
    except ValueError:  # pragma: no cover
        return  # pragma: no cover

    phase = parts[2].lower()
    if not round_num or phase not in ("players", "enemies"):
        return  # pragma: no cover

    if pid not in state["combat"]:
        state["combat"][pid] = {
            "active": True,
            "campaign_name": campaign_name,
            "round": round_num,
            "current_phase": phase,
            "phase_started_at": now_iso,
            "players_acted": [],
            "last_ping_at": None,
        }
    else:
        combat = state["combat"][pid]
        if phase == "players" and (
            combat["current_phase"] != "players"
            or combat["round"] != round_num
        ):
            combat["players_acted"] = []
        combat["round"] = round_num
        combat["current_phase"] = phase
        combat["phase_started_at"] = now_iso
        combat["last_ping_at"] = None

    phase_label = "Players" if phase == "players" else "Enemies"
    print(f"Combat in {campaign_name}: Round {round_num}, {phase_label}")
    tg.send_message(group_id, thread_id, f"Round {round_num}. {phase_label}' turn.")


def _check_all_acted(pid: str, campaign_name: str, group_id: int, thread_id: int,
                     state: dict, gm_ids: set) -> None:
    """If all non-away players have acted, notify the GM."""
    combat = state["combat"].get(pid)
    if not combat or not combat.get("active"):
        return  # pragma: no cover
    acted = set(combat.get("players_acted", {}).keys())
    now = datetime.now(timezone.utc)
    players = [
        p for p in state.get("players", {}).values()
        if p.get("pbp_topic_id") == pid
    ]
    waiting = [
        p for p in players
        if p["user_id"] not in acted
        and not helpers.is_away(state, pid, p["user_id"], now)
    ]
    if not waiting and len(acted) > 0:
        combat["all_players_notified"] = True
        # Mention all GMs
        gm_mentions = []
        for p in state.get("players", {}).values():
            if p.get("user_id") in gm_ids and p.get("pbp_topic_id") == pid:
                gm_mentions.append(helpers.player_mention(p))  # pragma: no cover
        gm_str = " ".join(gm_mentions) if gm_mentions else "GM"
        tg.send_message(group_id, thread_id,
                        f"✅ All players have posted their actions for Round {combat['round']}!\n"
                        f"{gm_str} — ready to resolve.")


def handle_combat_message(
    text: str, raw_text: str, user_id: str, user_name: str, gm_ids: set, pid: str, campaign_name: str,
    now_iso: str, group_id: int, thread_id: int, state: dict,
) -> None:
    """Process GM combat commands and track player actions.

    Combat state structure:
        active: bool
        campaign_name: str
        round: int
        current_phase: "players" | "enemies"
        phase_started_at: ISO timestamp
        players_acted: {user_id: timestamp}  (dict now, not list)
        last_ping_at: ISO timestamp or None
        enemies: [str]              — named enemy roster
        combat_log: [{round, text, at}]  — key moment log
        started_at: ISO timestamp
        all_players_notified: bool  — have we pinged GM that everyone's done?
    """
    if user_id in gm_ids:
        if text.startswith("/round"):
            handle_round_command(text, pid, campaign_name, now_iso, group_id, thread_id, state)  # pragma: no cover

        elif text.startswith("/next"):
            handle_next_command(pid, campaign_name, now_iso, group_id, thread_id, state)

        elif text.startswith("/endcombat") or text == "/combat end":
            handle_endcombat(pid, campaign_name, group_id, thread_id, state)

        elif text.startswith("/combat") and not text.startswith("/combatlog"):
            combat_args = raw_text[7:].strip()
            handle_combat_start(combat_args, pid, campaign_name, now_iso, group_id, thread_id, state)

        elif text.startswith("/enemies"):
            enemy_args = raw_text[8:].strip()
            handle_enemies_command(enemy_args, pid, campaign_name, now_iso, group_id, thread_id, state)

        elif text.startswith("/clog"):
            clog_args = raw_text[5:].strip()
            if clog_args:
                combat = state["combat"].get(pid)
                if combat and combat.get("active"):
                    log = combat.setdefault("combat_log", [])
                    log.append({"round": combat["round"], "text": clog_args, "at": now_iso})
                    tg.send_message(group_id, thread_id, f"📝 R{combat['round']}: {clog_args}")
                else:
                    tg.send_message(group_id, thread_id, "No active combat. Start with /combat")
            else:
                tg.send_message(group_id, thread_id,
                                "Usage: /clog <event>\ne.g. /clog The ogre crits Cardigan for 28 damage!")

    # Track player action during combat (with timestamp)
    combat = state["combat"].get(pid)
    if (combat and combat.get("active")
            and combat["current_phase"] == "players"
            and user_id not in gm_ids):
        acted = combat.get("players_acted", {})
        # Migrate old list format to dict
        if isinstance(acted, list):
            acted = {uid: now_iso for uid in acted}
            combat["players_acted"] = acted
        if user_id not in acted:
            acted[user_id] = now_iso
            # Check if all players have now acted
            if not combat.get("all_players_notified"):
                _check_all_acted(pid, campaign_name, group_id, thread_id, state, gm_ids)
