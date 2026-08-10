"""
Poll update handlers, extracted from router.py.

Handles poll_answer (vote cast/changed) and poll (poll closed) updates.
"""
from datetime import datetime, timezone

import telegram as tg
from dispatch.poll_notify import notify_vote, capture_unknown_voter
from scheduled.session_poll_build import votes_to_option_label


def build_poll_id_map(state: dict) -> dict[str, str]:
    """Return {poll_id: campaign_code} from current session_poll state."""
    result = {}
    for code, slot in state.get("session_poll", {}).items():
        pid = slot.get("poll_id", "")
        if pid:
            result[pid] = code
    return result


def find_pair(config: dict, code: str) -> dict | None:
    """Find a topic_pair by campaign code."""
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return pair
    return None


def handle_poll_closed(poll: dict, config: dict, state: dict) -> None:
    """Handle a poll closing (is_closed=True). Auto-marks session as happened."""
    poll_id = poll.get("id", "")
    if not poll_id:
        return

    # Check session polls
    for code, slot in state.get("session_poll", {}).items():
        if slot.get("poll_id") == poll_id:
            slot["session_happened"] = True
            total = poll.get("total_voter_count", 0)
            bot_topic = config.get("bot_topic_id")
            group_id = config["group_id"]
            if bot_topic:
                tg.send_message(group_id, bot_topic,
                                f"📊 {code} poll closed — {total} voted. "
                                f"No more pings this week.")
            print(f"Poll closed: {code} (poll_id={poll_id}, voters={total})")
            return

    # Check swimming poll
    swim = state.get("swimming_poll", {})
    if swim.get("poll_id") == poll_id:
        swim["session_happened"] = True
        total = poll.get("total_voter_count", 0)
        bot_topic = config.get("bot_topic_id")
        group_id = config["group_id"]
        if bot_topic:
            tg.send_message(group_id, bot_topic,
                            f"📊 Swimming poll closed — {total} voted.")
        print(f"Poll closed: swimming (poll_id={poll_id}, voters={total})")


def handle_poll_answer(poll_answer: dict, config: dict, state: dict) -> None:
    """Record a poll vote and fire cross-campaign notifications."""
    uid = str(poll_answer.get("user", {}).get("id", ""))
    name = poll_answer.get("user", {}).get("first_name", "?")
    option_ids = poll_answer.get("option_ids", [])
    incoming_poll_id = poll_answer.get("poll_id", "")

    poll_id_map = build_poll_id_map(state)
    code = poll_id_map.get(incoming_poll_id)
    if not code:
        return  # vote for an unrecognised poll

    polls = state.setdefault("session_poll", {})
    poll = polls.setdefault(code, {})
    voted = poll.setdefault("voted_uids", [])

    # Empty option_ids = user retracted their vote (revoting feature)
    if not option_ids:
        if uid in voted:
            voted.remove(uid)
    elif uid and uid not in voted:
        voted.append(uid)
        capture_unknown_voter(uid, code, config, state, option_ids)

    votes = poll.setdefault("votes", {})
    # Remove previous votes from this user across all options (handles revoting)
    for key in votes:
        votes[key] = [v for v in votes[key] if v != uid]
    # Record new vote(s) by option index string
    for idx in option_ids:
        votes.setdefault(str(idx), []).append(uid)

    # Cross-campaign notification
    pair = find_pair(config, code)
    pid = str(pair["pbp_topic_ids"][0]) if pair else None
    # Use stored options to avoid date drift (votes arrive days after poll was posted)
    stored_options = poll.get("options", [])
    if stored_options:
        raw_labels = [stored_options[i].split()[0]
                      for i in option_ids if i < len(stored_options)]
        option_label = " & ".join(raw_labels) if raw_labels else "?"
    else:
        option_label = votes_to_option_label(option_ids, pair or {}, datetime.now(timezone.utc))
    if pid:
        notify_vote(config, state, name, uid, code, option_label, pid)
    print(f"Poll vote: {name} ({code}) → option {option_ids}")
