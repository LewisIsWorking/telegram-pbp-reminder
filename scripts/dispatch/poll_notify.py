"""
Cross-campaign poll vote notifications.

When a player votes in any linked poll (e.g. C01 ↔ C11), posts a live
tally update to every linked campaign's chat topic, including the voter's
own campaign.
"""

import telegram as tg
from helpers_pkg.groups import group_id_for_campaign, linked_poll_codes, pid_for_code
from scheduled.session_poll_build import poll_options_for, option_tally
from datetime import datetime, timezone


def _tally_line(code: str, poll_slot: dict, options: list[str]) -> str:
    """Build 'C01: Friday: 3, Saturday: 1' from a poll slot."""
    votes = poll_slot.get("votes", {})
    parts = option_tally(votes, options)
    return f"{code}: {', '.join(parts)}" if parts else f"{code}: no votes yet"


def _options_for_code(config: dict, code: str) -> list[str]:
    now = datetime.now(timezone.utc)
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return poll_options_for(pair, now)
    return ["Friday", "Saturday", "Can't make it"]


def notify_vote(config: dict, state: dict,
                voter_name: str, option_label: str, voting_pid: str) -> None:
    """Post a tally notification to own + all linked campaigns' chat topics."""
    voting_code = None
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == voting_pid:
            voting_code = pair.get("code", voting_pid)
            break
    if not voting_code:
        return

    polls = state.get("session_poll", {})
    linked_codes = linked_poll_codes(config, voting_pid)
    all_codes = [voting_code] + linked_codes

    # Build combined tally across all linked polls
    tally_lines = []
    for code in all_codes:
        slot = polls.get(code, {})
        options = _options_for_code(config, code)
        tally_lines.append(_tally_line(code, slot, options))

    msg = (f"━━━━━━━━━━━━━━━━\n"
           f"🗳️ {voter_name} voted {option_label}\n"
           + "\n".join(tally_lines))

    # Send to every campaign's chat topic (own + linked)
    for code in all_codes:
        target_pid = pid_for_code(config, code)
        if not target_pid:
            continue
        gid = group_id_for_campaign(config, target_pid)
        chat_tid = None
        for pair in config.get("topic_pairs", []):
            if str(pair["pbp_topic_ids"][0]) == target_pid:
                chat_tid = pair.get("chat_topic_id")
                break
        if chat_tid:
            tg.send_message(gid, chat_tid, msg)
