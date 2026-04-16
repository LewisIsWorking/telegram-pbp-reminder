"""
Cross-campaign poll vote notifications.

When a player votes in any linked poll (e.g. C01 ↔ C11), posts a live
tally update to every linked campaign's chat topic, including the voter's
own campaign.

Format:
  🗳️ @username voted Friday in C01

  C01 — 2/3 voted  |  waiting: @Alice @Bob
    Friday:         1  @PathWars
    Either:         2  @Elinoa @Selenor
    → Either leads

  C11 — 7/8 voted  |  waiting: @molluggg
    2026-04-13 Mon: 4  @NJ @Craig @Jack @Sparkleslayer
    → 2026-04-13 leads
"""

import telegram as tg
from datetime import datetime, timezone
from helpers_pkg.groups import group_id_for_campaign, linked_poll_codes, pid_for_code
from scheduled.session_poll_build import poll_options_for
from dispatch.poll_tally import build_tally_block


def _voter_mention(uid: str, name: str, config: dict, state: dict) -> str:
    """Return '@username' if known, else fallback to first name."""
    for p in state.get("players", {}).values():
        if str(p.get("user_id", "")) == uid:
            u = p.get("username", "")
            if u:
                return f"@{u}"
            return p.get("first_name", name)
    for pair in config.get("topic_pairs", []):
        names = pair.get("poll_user_names", {})
        if uid in names:
            return f"@{names[uid]}"
    return name


def _options_for_code(config: dict, code: str,
                       state: dict | None = None) -> list[str]:
    """Return poll options for a campaign code.

    Prefers options stored in poll state at creation time (avoids date
    drift when votes arrive mid-week and now != poll-creation Sunday).
    Falls back to recalculating from current time.
    """
    if state:
        stored = state.get("session_poll", {}).get(code, {}).get("options")
        if stored:
            return stored  # pragma: no cover
    now = datetime.now(timezone.utc)
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return poll_options_for(pair, now)
    return ["Friday", "Saturday", "Can't make it"]


def _poll_link_for(code: str, config: dict, state: dict) -> str:
    """Return a t.me link to the current week's poll message, or ''."""
    from helpers_pkg.groups import group_id_for_campaign, pid_for_code
    slot = state.get("session_poll", {}).get(code, {})
    msg_id = slot.get("poll_message_id")
    if not msg_id:
        return ""
    pid = pid_for_code(config, code)
    if not pid:
        return ""  # pragma: no cover
    pair = next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)
    if not pair:
        return ""  # pragma: no cover
    gid = group_id_for_campaign(config, pid)
    chat_tid = pair.get("chat_topic_id")
    username = pair.get("group_username", config.get("group_username"))
    return tg.message_link(gid, chat_tid, msg_id, username)


def _action_label(option_label: str) -> str:
    """Convert raw option label to readable voted action string."""
    if option_label == "?":
        return "retracted their vote"  # pragma: no cover
    return f"voted {option_label}"


def notify_vote(config: dict, state: dict, voter_name: str, voter_uid: str,
                voting_code: str, option_label: str, voting_pid: str) -> None:
    """Post tally notification to own + all linked campaigns' chat topics."""
    polls = state.get("session_poll", {})
    linked_codes = linked_poll_codes(config, voting_pid)
    all_codes = [voting_code] + linked_codes

    mention = _voter_mention(voter_uid, voter_name, config, state)
    action = _action_label(option_label)

    tally_blocks = []
    for code in all_codes:
        slot = polls.get(code, {})
        options = _options_for_code(config, code, state)
        tally_blocks.append(build_tally_block(code, slot, options, config, state))

    poll_link = _poll_link_for(voting_code, config, state)
    link_line = f"\n🔗 {poll_link}" if poll_link else ""
    msg = (f"━━━━━━━━━━━━━━━━\n"
           f"🗳️ {mention} {action} in {voting_code}{link_line}\n\n"
           + "\n\n".join(tally_blocks))

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
                          config: dict, state: dict,
                          option_ids: list | None = None) -> None:
    """Store unrecognised voter IDs for later promotion via promote_poll_voters.py.

    Called when a poll_answer arrives from a UID not in poll_user_ids.
    Recorded in state['poll_unknown_voters'][code] so it can be matched
    to a placeholder on the next Sunday after enough players have voted.
    Also posts an alert to the bot topic so the GM knows immediately.
    """
    pair = next((p for p in config.get("topic_pairs", [])
                 if p.get("code") == code), None)
    if not pair:
        return
    known = {str(u) for u in pair.get("poll_user_ids", [])}
    # Also treat poll_user_names keys as known
    known |= set(pair.get("poll_user_names", {}).keys())
    if uid in known:
        return
    bucket = state.setdefault("poll_unknown_voters", {}).setdefault(code, [])
    if uid not in bucket:
        bucket.append(uid)
        print(f"Unknown voter captured: {uid} in {code}")
        bot_topic = config.get("bot_topic_id")
        group_id = config.get("group_id")
        if bot_topic and group_id:
            sp_opts = state.get("session_poll", {}).get(code, {}).get("options", [])
            voted = [sp_opts[i] for i in (option_ids or []) if i < len(sp_opts)]
            voted_str = ", ".join(voted) if voted else "?"
            placeholders = [
                f"@{pair['poll_user_names'].get(str(u), str(u))}"
                for u in pair.get("poll_user_ids", [])
                if 9000000000 <= u < 9200000000
            ]
            ph_str = ", ".join(placeholders) if placeholders else "none"
            tg.send_message(group_id, bot_topic,
                            f"⚠️ Unknown voter in {code} poll: uid {uid}\n"
                            f"Voted: {voted_str}\n"
                            f"Unresolved roster slots: {ph_str}\n"
                            f"They will be identified when they next post.")

def identify_unknown_voter(uid: str, username: str, first_name: str,
                           code: str, config: dict, state: dict) -> None:
    """Called when a message arrives from a UID that was previously unknown.

    Stores the UID→username mapping in poll_identified_voters so that
    promote_poll_voters.py can auto-match against placeholder config entries.
    Removes the UID from poll_unknown_voters and posts a bot-topic alert.
    """
    bucket = state.get("poll_unknown_voters", {}).get(code, [])
    if uid not in bucket:
        return
    state["poll_unknown_voters"][code] = [u for u in bucket if u != uid]
    identified = state.setdefault("poll_identified_voters", {})
    if uid in identified:
        return
    identified[uid] = {"username": username, "first_name": first_name, "code": code}
    print(f"Identified unknown voter {uid} as @{username} in {code}")
    bot_topic = config.get("bot_topic_id")
    group_id = config.get("group_id")
    if bot_topic and group_id:
        tg.send_message(group_id, bot_topic,
                        f"✅ Identified {code} unknown voter: "
                        f"@{username} ({first_name}) — uid {uid}\n"
                        f"Will be auto-promoted on next workflow run.")
