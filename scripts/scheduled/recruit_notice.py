"""The per-campaign short-of-players notice (moved out of maintenance.py 2026-10-03).

Lewis, 2026-10-03: "We have 2 different posts doing the same chat, the top
post is better." The notice now uses the recruit-focus advert's layout, and
``check_recruitment_needs`` skips the campaign that advert already covers.
"""


def pair_for(config: dict, pid: str) -> dict | None:
    """The topic pair whose first pbp topic is ``pid``."""
    for pair in config.get("topic_pairs", []):
        ids = pair.get("pbp_topic_ids") or []
        if ids and str(ids[0]) == str(pid):
            return pair
    return None


def recruit_notice_text(pair: dict, config: dict, players: list[dict], needed: int,
                        non_perm_count: int, perm_count: int, target: int) -> str:
    """The short-of-players notice, in the recruit-focus advert's layout.

    Lewis preferred that layout to the old "📢 X needs N more players!"
    notice (2026-10-03), so both posts now read the same. Perm players are
    named with everyone else but counted only in the suffix, as before.
    """
    from scheduled.recruit_link import recruit_link
    from scheduled.recruit_roster_line import current_players_line

    code, name = pair.get("code", ""), pair.get("name", "")
    label = f"{code}: {name}" if code else name
    emoji = pair.get("emoji", "")
    emoji_prefix = f"{emoji} " if emoji else ""
    seats = "seat" if needed == 1 else "seats"
    perm_suffix = f" +{perm_count} perm" if perm_count else ""
    lines = ["━━━━━━━━━━━━━━━━",
             f"🧭 This table has room: {emoji_prefix}{label}",
             f"⏳ {needed} {seats} open ({non_perm_count}/{target} players{perm_suffix})."]
    roster_line = current_players_line(players)
    if roster_line:
        lines.append(roster_line)
    lines.append("↗ Know someone? Send them our way!")
    link = recruit_link(pair, config) if pair.get("pbp_topic_ids") else ""
    if link:
        lines.append(link)
    return "\n".join(lines)
