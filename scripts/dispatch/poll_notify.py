"""
Cross-campaign poll vote notifications.

When a player votes in any linked poll (e.g. C01 ↔ C11), posts a live
tally update to every linked campaign's chat topic, including the voter's
own campaign.

Format:
  🗳️ @username (C01) voted Friday
  C01: Friday: 3, Either: 1
  C11: Weekday: 2
"""

import telegram as tg
from datetime import datetime, timezone
from helpers_pkg.groups import group_id_for_campaign, linked_poll_codes, pid_for_code
from scheduled.session_poll_build import poll_options_for, option_tally


def _voter_mention(uid: str, name: str, config: dict, state: dict) -> str:
    """Return '@username' if known, else fallback to first name."""
    # Check player registry first
    for p in state.get("players", {}).values():
        if str(p.get("user_id", "")) == uid:
            u = p.get("username", "")
            if u:
                return f"@{u}"
            return p.get("first_name", name)
    # Check poll_user_names in each pair
    for pair in config.get("topic_pairs", []):
        names = pair.get("poll_user_names", {})
        if uid in names:
            return f"@{names[uid]}"
    return name


def _tally_line(code: str, poll_slot: dict, options: list[str]) -> str:
    votes = poll_slot.get("votes", {})
    parts = option_tally(votes, options)
    return f"{code}: {', '.join(parts)}" if parts else f"{code}: no votes yet"


def _options_for_code(config: dict, code: str) -> list[str]:
    now = datetime.now(timezone.utc)
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return poll_options_for(pair, now)
    return ["Friday", "Saturday", "Can't make it"]


def notify_vote(config: dict, state: dict, voter_name: str, voter_uid: str,
                voting_code: str, option_label: str, voting_pid: str) -> None:
    """Post tally notification to own + all linked campaigns' chat topics."""
    polls = state.get("session_poll", {})
    linked_codes = linked_poll_codes(config, voting_pid)
    all_codes = [voting_code] + linked_codes

    mention = _voter_mention(voter_uid, voter_name, config, state)

    tally_lines = []
    for code in all_codes:
        slot = polls.get(code, {})
        options = _options_for_code(config, code)
        tally_lines.append(_tally_line(code, slot, options))

    msg = (f"━━━━━━━━━━━━━━━━\n"
           f"🗳️ {mention} ({voting_code}) voted {option_label}\n"
           + "\n".join(tally_lines))

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


def capture_unknown_voter(uid: str, code: str,
                          config: dict, state: dict) -> None:
    """Store unrecognised voter IDs for later promotion via promote_poll_voters.py.

    Called when a poll_answer arrives from a UID not in poll_user_ids.
    Recorded in state['poll_unknown_voters'][code] so it can be matched
    to a placeholder on the next Sunday after enough players have voted.
    """
    pair = next((p for p in config.get("topic_pairs", [])
                 if p.get("code") == code), None)
    if not pair:
        return
    known = {str(u) for u in pair.get("poll_user_ids", [])}
    if uid in known:
        return
    bucket = state.setdefault("poll_unknown_voters", {}).setdefault(code, [])
    if uid not in bucket:
        bucket.append(uid)
        print(f"Unknown voter captured: {uid} in {code}")
