"""
Combat lifecycle commands.

GM commands: /combat (start), /next (advance phase), /endcombat, /enemies.
"""

import telegram as tg


def handle_combat_start(args: str, pid: str, campaign_name: str,
                        now_iso: str, group_id: int, thread_id: int, state: dict) -> None:
    """Start combat with optional enemy list: /combat Ogre, 2 Skeletons"""
    enemies = [e.strip() for e in args.split(",") if e.strip()] if args else []

    state["combat"][pid] = {
        "active": True,
        "campaign_name": campaign_name,
        "round": 1,
        "current_phase": "players",
        "phase_started_at": now_iso,
        "players_acted": {},
        "last_ping_at": None,
        "enemies": enemies,
        "combat_log": [],
        "started_at": now_iso,
        "all_players_notified": False,
    }

    lines = [f"⚔️ Combat started in {campaign_name}!",
             f"Round 1 — Players' turn."]
    if enemies:
        lines.append("")
        lines.append("Enemies:")
        for e in enemies:
            lines.append(f"  • {e}")
    lines.append("")
    lines.append("Post your actions. Use /whosturn to see who's still needed.")

    print(f"Combat started in {campaign_name}: {enemies}")
    tg.send_message(group_id, thread_id, "\n".join(lines))


def handle_next_command(pid: str, campaign_name: str, now_iso: str,
                        group_id: int, thread_id: int, state: dict) -> None:
    """Advance to next phase: players→enemies→next round players."""
    combat = state["combat"].get(pid)
    if not combat or not combat.get("active"):
        tg.send_message(group_id, thread_id, "No active combat. Start with /combat")  # pragma: no cover
        return  # pragma: no cover

    old_round = combat["round"]
    old_phase = combat["current_phase"]

    if old_phase == "players":
        # Advance to enemies
        combat["current_phase"] = "enemies"
        combat["phase_started_at"] = now_iso
        combat["last_ping_at"] = None
        tg.send_message(group_id, thread_id,
                        f"Round {old_round} — Enemies' turn.")
    else:
        # Advance to next round, players
        new_round = old_round + 1
        combat["round"] = new_round
        combat["current_phase"] = "players"
        combat["phase_started_at"] = now_iso
        combat["players_acted"] = {}
        combat["last_ping_at"] = None
        combat["all_players_notified"] = False
        tg.send_message(group_id, thread_id,
                        f"Round {new_round} — Players' turn.\n"
                        f"Post your actions!")

    print(f"Combat in {campaign_name}: Round {combat['round']}, {combat['current_phase']}")


def handle_endcombat(pid: str, campaign_name: str,
                     group_id: int, thread_id: int, state: dict) -> None:
    """End combat with a summary."""
    combat = state["combat"].get(pid)
    if not combat:
        tg.send_message(group_id, thread_id, f"No active combat in {campaign_name}.")  # pragma: no cover
        return  # pragma: no cover

    # Build summary
    rounds = combat.get("round", 1)
    log = combat.get("combat_log", [])

    lines = [f"⚔️ Combat ended in {campaign_name}.",
             f"Lasted {rounds} round{'s' if rounds != 1 else ''}."]

    if log:
        lines.append("")
        lines.append("Combat log:")
        for entry in log[-8:]:  # Last 8 entries
            lines.append(f"  R{entry['round']}: {entry['text']}")
        if len(log) > 8:
            lines.append(f"  ... and {len(log) - 8} earlier entries")  # pragma: no cover

    del state["combat"][pid]
    print(f"Combat ended in {campaign_name}")
    tg.send_message(group_id, thread_id, "\n".join(lines))


def handle_enemies_command(args: str, pid: str, campaign_name: str,
                           now_iso: str, group_id: int, thread_id: int, state: dict) -> None:
    """/enemies — view or set enemy roster."""
    combat = state["combat"].get(pid)
    if not combat or not combat.get("active"):
        tg.send_message(group_id, thread_id, "No active combat. Start with /combat")
        return

    if not args:
        # View enemies
        enemies = combat.get("enemies", [])
        if enemies:
            lines = [f"⚔️ Enemies in {campaign_name}:"]
            for e in enemies:
                lines.append(f"  • {e}")
            tg.send_message(group_id, thread_id, "\n".join(lines))
        else:
            tg.send_message(group_id, thread_id,
                            "No enemies listed. Use /enemies Ogre, Skeleton, etc.")
    else:
        # Set enemies
        enemies = [e.strip() for e in args.split(",") if e.strip()]
        combat["enemies"] = enemies
        lines = [f"⚔️ Updated enemies:"]
        for e in enemies:
            lines.append(f"  • {e}")
        tg.send_message(group_id, thread_id, "\n".join(lines))
