"""
Boon display helpers — /boons and /boonsall command formatters.

Extracted from boons/handler.py to keep that file under 200 lines.
"""


def build_boons(pid: str, user_id: str, campaign_name: str, state: dict) -> str:
    """Build /boons output: current player's boons in this campaign."""
    boons = state.get("player_boons", {}).get(pid, {}).get(user_id, [])
    if not boons:
        return f"No boons held in {campaign_name}."
    lines = [f"🎁 Your boons in {campaign_name}:\n"]
    for i, b in enumerate(boons, 1):
        lines.append(f"{i}. {b['text']}")
        lines.append(f"   Earned: {b['date']} ({b.get('week', '?')})")
    return "\n".join(lines)


def build_boons_all(user_id: str, state: dict) -> str:
    """Build /boonsall output: all boons for this player across all campaigns."""
    all_boons = state.get("player_boons", {})
    found = [b for users in all_boons.values() for b in users.get(user_id, [])]
    if not found:
        return "No boons held in any campaign."
    lines = ["🎁 All your boons:\n"]
    by_campaign: dict = {}
    for b in found:
        by_campaign.setdefault(b["campaign"], []).append(b)
    for camp, boons in sorted(by_campaign.items()):
        lines.append(f"📜 {camp}:")
        for i, b in enumerate(boons, 1):
            lines.append(f"  {i}. {b['text']}  ({b['date']})")
        lines.append("")
    return "\n".join(lines).rstrip()
