"""
Cross-campaign poll vote notifications.

When a player votes in any linked poll (e.g. C01 ↔ C11), posts a live
tally update to every linked campaign's chat topic, including the voter's
own campaign.
"""

import telegram as tg
from helpers_pkg.campaigns import get_code, get_name
from helpers_pkg.groups import group_id_for_campaign, linked_poll_codes, pid_for_code


def _option_label(option_idx: int, pair: dict) -> str:
    """Return the human-readable label for a poll option index."""
    options = pair.get("poll_options")
    if options and option_idx < len(options):
        # Strip dynamic date suffix for display (e.g. "Friday 04 April" → "Friday")
        return options[option_idx].split()[0]
    return ["Friday", "Saturday", "Can't make it"][option_idx] if option_idx < 3 else "?"


def _tally_line(code: str, poll_slot: dict) -> str:
    """Build 'C01: 3 Friday / 2 Saturday / 1 Can't' from a poll slot."""
    votes = poll_slot.get("votes", {})
    fri = len(votes.get("friday", []))
    sat = len(votes.get("saturday", []))
    cant = len(votes.get("cant", []))
    parts = []
    if fri:
        parts.append(f"{fri} Fri")
    if sat:
        parts.append(f"{sat} Sat")
    if cant:
        parts.append(f"{cant} Can't")
    return f"{code}: {' / '.join(parts) if parts else 'no votes yet'}"


def notify_vote(config: dict, state: dict,
                voter_name: str, option_label: str, voting_pid: str) -> None:
    """Post a tally notification to own + all linked campaigns' chat topics.

    Called immediately after a vote is recorded in state.
    """
    voting_code = get_code(config, voting_pid) or voting_pid
    polls = state.get("session_poll", {})

    # Collect self + all linked PIDs
    linked_codes = linked_poll_codes(config, voting_pid)
    all_codes = [voting_code] + linked_codes

    # Build combined tally header
    tally_lines = []
    for code in all_codes:
        slot = polls.get(code, {})
        tally_lines.append(_tally_line(code, slot))

    voter_line = f"🗳️ {voter_name} voted {option_label}"
    tally = "\n".join(tally_lines)
    msg = f"━━━━━━━━━━━━━━━━\n{voter_line}\n{tally}"

    # Send to every campaign's chat topic (own + linked)
    for code in all_codes:
        target_pid = pid_for_code(config, code)
        if not target_pid:
            continue
        gid = group_id_for_campaign(config, target_pid)
        # Find chat_topic_id for this campaign
        chat_tid = None
        for pair in config.get("topic_pairs", []):
            if str(pair["pbp_topic_ids"][0]) == target_pid:
                chat_tid = pair.get("chat_topic_id")
                break
        if chat_tid:
            tg.send_message(gid, chat_tid, msg)
