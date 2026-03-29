"""
Weekly session poll for hybrid live campaigns.

Supports multiple campaigns (C01, C11, etc.), each with their own poll
slot in state["session_poll"][code]. C11-style campaigns can run any day;
C01-style are Mon–Fri only.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from helpers_pkg.groups import group_id_for_campaign, pid_for_code
from scheduled.session_poll_build import (
    poll_options_for, build_history_str,
    build_ping_message, build_all_voted_message,
)


def _migrate_flat_poll(state: dict) -> None:
    """Migrate old flat session_poll dict to per-code structure (C01)."""
    poll = state.get("session_poll", {})
    if poll and "week_iso" in poll:
        state["session_poll"] = {"C01": poll}


def _poll_roster(config: dict, state: dict, pid: str, pair: dict) -> dict:
    """Return {uid: {name, username}} for all players to be polled."""
    roster = {}
    poll_uids = pair.get("poll_user_ids")
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if poll_uids:
        for uid in poll_uids:
            uid_str = str(uid)
            p = next((p for p in state.get("players", {}).values()
                      if p.get("user_id") == uid_str), None)
            roster[uid_str] = {
                "name": p.get("first_name", uid_str) if p else uid_str,
                "username": p.get("username", "") if p else "",
            }
    else:
        for key, p in state.get("players", {}).items():
            if p.get("pbp_topic_id") == pid:
                uid = p.get("user_id", "")
                roster[uid] = {"name": p.get("first_name", "?"),
                               "username": p.get("username", "")}
    return roster


def _unvoted_mentions(roster: dict, voted_uids: list) -> list[str]:
    voted = set(str(u) for u in voted_uids)
    mentions = []
    for uid, info in roster.items():
        if uid not in voted:
            u = info.get("username", "")
            mentions.append(f"@{u}" if u else info["name"])
    return mentions


def _post_one(config: dict, state: dict, pair: dict,
              now: datetime) -> None:
    """Post or ping the poll for a single hybrid campaign."""
    pid = str(pair["pbp_topic_ids"][0])
    code = pair.get("code", pid)
    gid = group_id_for_campaign(config, pid)
    poll_tid = pair.get("chat_topic_id")
    any_day = pair.get("poll_any_day", False)
    weekday = now.weekday()  # 0=Mon, 6=Sun

    if not any_day and weekday > 4:
        return

    _migrate_flat_poll(state)
    polls = state.setdefault("session_poll", {})
    poll = polls.get(code, {})
    current_week = now.strftime("%Y-W%W")
    week_num = now.isocalendar()[1]

    # New week — post fresh poll
    if poll.get("week_iso") != current_week:
        options = poll_options_for(pair, now)
        hist_str = build_history_str(
            state.get("poll_history", {}).get(code, {})
        )
        question = f"🗳️ {code} Week {week_num}/52 — When are we playing?"
        multi = pair.get("allows_multiple_answers", False)
        result = tg.send_poll(gid, poll_tid, question, options,
                              is_anonymous=False,
                              allows_multiple_answers=multi)
        msg_id, poll_id = result if result else (None, None)
        if hist_str:
            tg.send_message(gid, poll_tid,
                            f"━━━━━━━━━━━━━━━━{hist_str}")
        polls[code] = {
            "week_iso": current_week,
            "poll_id": poll_id or "",
            "poll_message_id": msg_id,
            "voted_uids": [],
            "last_ping_day": -1,
            "votes": {"friday": [], "saturday": [], "cant": []},
        }
        poll = polls[code]
        print(f"Session poll created: {code} week {current_week}")

    # Daily ping (once per weekday index, or once per day for any_day)
    last_ping = poll.get("last_ping_day", -1)
    ping_key = weekday if not any_day else now.toordinal()
    if ping_key <= last_ping:
        return

    roster = _poll_roster(config, state, pid, pair)
    voted_uids = poll.get("voted_uids", [])
    unvoted = _unvoted_mentions(roster, voted_uids)

    if not unvoted:
        if not poll.get("all_voted_posted"):
            tg.send_message(gid, poll_tid,
                            build_all_voted_message(code, len(roster), week_num))
            poll["all_voted_posted"] = True
        return

    msg = build_ping_message(pair, poll, unvoted, len(voted_uids),
                             len(roster), weekday, week_num, any_day)
    if tg.send_message(gid, poll_tid, msg):
        poll["last_ping_day"] = ping_key
        print(f"Session poll ping: {code} day {weekday}")


def post_session_poll(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post or update session polls for all hybrid campaigns."""
    now = now or datetime.now(timezone.utc)
    for pair in config.get("topic_pairs", []):
        if pair.get("hybrid_live"):
            try:
                _post_one(config, state, pair, now)
            except Exception as e:
                print(f"Session poll error ({pair.get('code','?')}): {e}")
