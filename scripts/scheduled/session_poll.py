"""
Weekly session poll for hybrid live campaigns.

Both polls (C01, C11) start early Sunday and run all week.
Poll message is pinned. Daily pings include a link to the poll.
State stored per-code: state["session_poll"][code].
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from helpers_pkg.groups import group_id_for_campaign
from scheduled.session_poll_build import (
    sunday_week_key, poll_options_for, build_history_str,
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
    # Optional {uid_str: username} map for players not in PBP registry
    name_map = {str(k): v for k, v in pair.get("poll_user_names", {}).items()}
    if poll_uids:
        for uid in poll_uids:
            uid_str = str(uid)
            p = next((p for p in state.get("players", {}).values()
                      if p.get("user_id") == uid_str), None)
            fallback_username = name_map.get(uid_str, "")
            roster[uid_str] = {
                "name": p.get("first_name", fallback_username or uid_str) if p else (fallback_username or uid_str),
                "username": p.get("username", fallback_username) if p else fallback_username,
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


def _poll_link(config: dict, pair: dict, msg_id: int | None) -> str:
    """Build a t.me link to the poll message."""
    if not msg_id:
        return ""
    pid = str(pair["pbp_topic_ids"][0])
    gid = group_id_for_campaign(config, pid)
    tid = pair.get("chat_topic_id")
    username = pair.get("group_username", config.get("group_username"))
    return tg.message_link(gid, tid, msg_id, username)


def _post_one(config: dict, state: dict, pair: dict, now: datetime) -> None:
    """Post or ping the poll for a single hybrid campaign."""
    pid = str(pair["pbp_topic_ids"][0])
    code = pair.get("code", pid)
    gid = group_id_for_campaign(config, pid)
    poll_tid = pair.get("chat_topic_id")
    post_hour = config.get("poll_post_hour", 7)
    weekday = now.weekday()  # 6 = Sunday

    _migrate_flat_poll(state)
    polls = state.setdefault("session_poll", {})
    poll = polls.get(code, {})
    week_key = sunday_week_key(now)
    week_num = now.isocalendar()[1]

    # New week starts Sunday at or after poll_post_hour
    is_sunday = (weekday == 6)
    if poll.get("week_iso") != week_key and is_sunday and now.hour >= post_hour:
        options = poll_options_for(pair, now)
        hist_str = build_history_str(
            state.get("poll_history", {}).get(code, {}), options
        )
        question = f"🗳️ {code} Week {week_num}/52 — When are we playing?"
        multi = pair.get("allows_multiple_answers", False)
        result = tg.send_poll(gid, poll_tid, question, options,
                              is_anonymous=False,
                              allows_multiple_answers=multi)
        msg_id, poll_id = result if result else (None, None)

        # Pin the poll
        if msg_id:
            tg.pin_message(gid, msg_id)

        if hist_str:
            tg.send_message(gid, poll_tid,
                            f"━━━━━━━━━━━━━━━━{hist_str}")

        if msg_id:
            polls[code] = {
                "week_iso": week_key,
                "poll_id": poll_id or "",
                "poll_message_id": msg_id,
                "voted_uids": [],
                "last_ping_day": -1,
                "votes": {},
            }
            poll = polls[code]
            print(f"Session poll posted + pinned: {code} week {week_key}")
        else:
            print(f"Session poll FAILED for {code} week {week_key} — will retry next run")

    # Don't ping before poll is up
    if poll.get("week_iso") != week_key:
        return

    # Daily ping — once per calendar day (ordinal)
    today_ord = now.toordinal()
    if today_ord <= poll.get("last_ping_day", -1):
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

    link = _poll_link(config, pair, poll.get("poll_message_id"))
    msg = build_ping_message(pair, unvoted, len(voted_uids),
                             len(roster), week_num, link)
    if tg.send_message(gid, poll_tid, msg):
        poll["last_ping_day"] = today_ord
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
                print(f"Session poll error ({pair.get('code', '?')}): {e}")
