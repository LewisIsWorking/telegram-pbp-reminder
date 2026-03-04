"""
Mechanics display builders.

Read-only commands: /showvote, /showtimer, /hp (view), /clocks.
"""

from datetime import datetime, timezone

import helpers

_MAX_HP_ENTRIES = 20
_MAX_CLOCKS = 15


def build_vote(pid: str, campaign_name: str, state: dict) -> str:
    """Build the current vote display for /vote (no args) or /showvote."""
    vote = state.get("votes", {}).get(pid)
    if not vote or vote.get("closed"):
        return "No active vote. GMs can start one with /vote <question> | <option1> | <option2> [| ...]"

    lines = [f"🗳️ Vote — {campaign_name}:", ""]
    lines.append(f"❓ {vote['question']}")
    lines.append("")

    results = vote.get("results", {})
    total = sum(len(v) for v in results.values())

    for i, option in enumerate(vote["options"], 1):
        voters = results.get(str(i), [])
        count = len(voters)
        bar = "█" * count + "░" * max(0, 5 - count) if total > 0 else "░" * 5
        voter_names = ", ".join(voters) if voters else ""
        voter_str = f"  ({voter_names})" if voter_names else ""
        lines.append(f"  {i}. {option}  [{bar}] {count}{voter_str}")

    lines.append("")
    lines.append(f"{total} vote{'s' if total != 1 else ''} cast. Use /pick <N> to vote.")
    return "\n".join(lines)


def build_timer(pid: str, campaign_name: str, state: dict) -> str:
    """Build the timer display for /showtimer."""
    timer = state.get("timers", {}).get(pid)
    if not timer:
        return "No active timer. GMs: /timer <duration> [reason]"

    now = datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(timer["deadline"])
    remaining = deadline - now

    if remaining.total_seconds() <= 0:
        return f"⏰ Timer EXPIRED for {campaign_name}!\n{timer.get('reason', '')}\nGMs: /canceltimer to clear"

    # Format remaining time
    hours = int(remaining.total_seconds() // 3600)
    mins = int((remaining.total_seconds() % 3600) // 60)
    if hours >= 24:
        days = hours // 24
        time_str = f"{days}d {hours % 24}h"
    elif hours > 0:
        time_str = f"{hours}h {mins}m"
    else:
        time_str = f"{mins}m"

    reason = timer.get("reason", "")
    reason_str = f"\n📝 {reason}" if reason else ""

    return (
        f"⏳ Timer — {campaign_name}\n"
        f"⏰ {time_str} remaining (deadline: {deadline.strftime('%b %d %H:%M UTC')})"
        f"{reason_str}\n"
        f"GMs: /canceltimer to clear"
    )


def build_hp_tracker(pid: str, campaign_name: str, state: dict) -> str:
    """Build HP tracker display for /hp (no args)."""
    hp_entries = state.get("hp_tracker", {}).get(pid, {})
    if not hp_entries:
        return (f"No HP tracked in {campaign_name}.\n"
                "GMs: /hp set <n> <current>/<max>\n"
                "      /hp d <n> <amount>   (damage)\n"
                "      /hp h <n> <amount>   (heal)")

    lines = [f"❤️ HP Tracker — {campaign_name}:", ""]
    for name, hp in sorted(hp_entries.items()):
        icon = helpers.hp_status_icon(hp["current"], hp["max"])
        bar = helpers.hp_bar(hp["current"], hp["max"])
        lines.append(f"  {icon} {name}: {bar}")
    lines.append("")
    lines.append(f"{len(hp_entries)}/{_MAX_HP_ENTRIES} entries.")
    lines.append("GMs: /hp set, /hp d(amage), /hp h(eal), /hp remove, /hp clear")
    return "\n".join(lines)


def build_clocks(pid: str, campaign_name: str, state: dict) -> str:
    """Build progress clocks display for /clocks."""
    clocks = state.get("clocks", {}).get(pid, {})
    if not clocks:
        return (f"No clocks in {campaign_name}.\n"
                "GMs: /clock <n> <segments>  (create)\n"
                "      /tick <n> [N]          (advance)\n"
                "      /untick <n> [N]        (reverse)")

    lines = [f"⏱️ Progress Clocks — {campaign_name}:", ""]
    for name, clock in sorted(clocks.items()):
        display = helpers.clock_display(clock["filled"], clock["segments"])
        complete = " ✅" if clock["filled"] >= clock["segments"] else ""
        lines.append(f"  {name}: {display}{complete}")
    lines.append("")
    lines.append(f"{len(clocks)}/{_MAX_CLOCKS} clocks.")
    lines.append("GMs: /clock, /tick, /untick, /delclock")
    return "\n".join(lines)
