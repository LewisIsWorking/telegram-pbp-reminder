"""
Player of the Week streak tracking.

A campaign streak: same player wins POTW in consecutive weeks for a campaign.
A community streak: same player wins POTW across ANY campaign in consecutive weeks.

Streaks are computed from potw_history on each POTW run and announced
when they reach 2, 3, 5, 10 weeks (campaign) or 2, 3, 5 (community).
"""

from datetime import datetime


# Announce at these streak lengths
CAMPAIGN_MILESTONES  = {2, 3, 5, 10}
COMMUNITY_MILESTONES = {2, 3, 5}


def compute_campaign_streak(history: list[dict], pid: str, user_id: str) -> int:
    """Return current consecutive-week win count for a player in one campaign."""
    pid_wins = [r for r in history
                if r.get("campaign_pid") == pid
                and r.get("user_id") == user_id]
    if not pid_wins:
        return 0
    pid_wins.sort(key=lambda r: (r.get("year", 0), r.get("week", "")))
    streak = 1
    for i in range(len(pid_wins) - 1, 0, -1):
        curr = pid_wins[i]
        prev = pid_wins[i - 1]
        if _consecutive_weeks(prev, curr):
            streak += 1
        else:
            break
    return streak


def compute_community_streak(history: list[dict], user_id: str) -> int:
    """Return consecutive weeks a player won POTW in any campaign."""
    user_wins = [r for r in history if r.get("user_id") == user_id]
    if not user_wins:
        return 0
    user_wins.sort(key=lambda r: (r.get("year", 0), r.get("week", "")))
    # Deduplicate: one win per ISO week (take the latest if multiple)
    by_week: dict[str, dict] = {}
    for r in user_wins:
        key = f"{r.get('year')}-{r.get('week')}"
        by_week[key] = r
    wins = sorted(by_week.values(), key=lambda r: (r.get("year", 0), r.get("week", "")))
    streak = 1
    for i in range(len(wins) - 1, 0, -1):
        if _consecutive_weeks(wins[i - 1], wins[i]):
            streak += 1
        else:
            break
    return streak


def streak_announcement(streak: int, player_name: str, campaign: str,
                        kind: str) -> str | None:
    """Return a celebration message if the streak hits a milestone, else None."""
    milestones = CAMPAIGN_MILESTONES if kind == "campaign" else COMMUNITY_MILESTONES
    if streak not in milestones:
        return None
    if kind == "campaign":
        return (f"🔥 {player_name} is on a {streak}-week streak in {campaign}! "
                f"Unstoppable poster!")
    return (f"🌟 {player_name} has won Player of the Week across "
            f"{streak} consecutive weeks community-wide! Legendary!")


def _consecutive_weeks(earlier: dict, later: dict) -> bool:
    """Return True if two records are exactly one ISO week apart."""
    try:
        year_e, week_e = earlier.get("year"), int(earlier.get("week", "W0")[1:])
        year_l, week_l = later.get("year"), int(later.get("week", "W0")[1:])
        if year_e == year_l:
            return week_l == week_e + 1
        if year_l == year_e + 1:
            # Last week of year_e to first week of year_l
            last_week = _last_iso_week(year_e)
            return week_e == last_week and week_l == 1
    except (TypeError, ValueError):
        pass
    return False


def _last_iso_week(year: int) -> int:
    """Return the last ISO week number of a given year."""
    dec28 = datetime(year, 12, 28)
    return dec28.isocalendar()[1]


def announce_streaks(config: dict, state: dict, winner: dict,
                     campaign_name: str, pid: str,
                     group_id: int, topic_id: int) -> None:
    """Post streak celebration messages to campaign topic + bot topic."""
    import helpers
    import telegram as tg
    history = state.get("potw_history", [])
    uid  = winner["user_id"]
    name = helpers.player_mention(winner)

    camp_streak = compute_campaign_streak(history, pid, uid)
    msg = streak_announcement(camp_streak, name, campaign_name, "campaign")
    if msg:
        tg.send_message(group_id, topic_id, f"━━━━━━━━━━━━━━━━\n{msg}")

    comm_streak = compute_community_streak(history, uid)
    msg = streak_announcement(comm_streak, name, campaign_name, "community")
    if msg:
        bot_topic = config.get("bot_topic_id")
        if bot_topic:
            tg.send_message(group_id, bot_topic, f"━━━━━━━━━━━━━━━━\n{msg}")
