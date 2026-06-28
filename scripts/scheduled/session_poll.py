"""
Weekly session poll for hybrid live campaigns.

Both polls (C01, C11) start early Sunday and run all week.
Poll message is pinned. Daily pings include a link to the poll.
State stored per-code: state["session_poll"][code].
"""

from datetime import datetime, timezone, timedelta

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
        state["session_poll"] = {"C01": poll}  # pragma: no cover


def _poll_roster(config: dict, state: dict, pid: str, pair: dict) -> dict:
    """Return {uid: {name, username}} for all players to be polled."""
    from commands.roster import active_poll_uids
    roster = {}
    # Optional {uid_str: username} map for players not in PBP registry
    name_map = {str(k): v for k, v in (pair.get("poll_user_names") or {}).items()}
    # Gate on whether poll_user_ids is *configured*; iterate the filtered set.
    # active_poll_uids honours the optional per-campaign poll_roster_filter:
    # when set, the list is trimmed to the campaign's active roster so players
    # who have left/gone inactive are no longer polled or pinged. (A filtered
    # result of [] yields an empty roster — it must NOT fall through to the
    # pbp-topic player scan, which would re-add the dropped players.)
    if pair.get("poll_user_ids"):
        for uid in active_poll_uids(pair, config, state):
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
            if p.get("pbp_topic_id") == pid:  # pragma: no cover
                uid = p.get("user_id", "")  # pragma: no cover
                roster[uid] = {"name": p.get("first_name", "?"),  # pragma: no cover
                               "username": p.get("username", "")}
    return roster


def _unvoted_mentions(roster: dict, voted_uids: list) -> list[str]:
    voted = set(str(u) for u in voted_uids)
    mentions = []
    for uid, info in roster.items():
        if uid not in voted:
            u = info.get("username", "")
            name = info["name"]
            # If name is just the raw UID (player not in registry), show friendly fallback
            if name == uid:
                name = f"Unknown ({uid})"  # pragma: no cover
            mentions.append(f"@{u}" if u else name)
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
    # Reminder/ping messages can be routed to a separate topic (e.g. a dedicated
    # "Nudge Bot" topic) while the poll widget + pin stay in the campaign topic.
    nudge_tid = pair.get("nudge_topic_id") or poll_tid
    post_hour = config.get("poll_post_hour", 7)
    weekday = now.weekday()  # 6 = Sunday

    _migrate_flat_poll(state)
    polls = state.setdefault("session_poll", {})
    poll = polls.get(code, {})
    week_key = sunday_week_key(now)
    # Poll posted Sunday covers the upcoming week; use Monday's ISO week number
    week_num = (now + timedelta(days=1)).isocalendar()[1] if now.weekday() == 6 else now.isocalendar()[1]

    # New week starts Sunday at or after poll_post_hour
    is_sunday = (weekday == 6)
    if poll.get("week_iso") != week_key and is_sunday and now.hour >= post_hour:
        options = poll_options_for(pair, now)
        hist_str = build_history_str(
            state.get("poll_history", {}).get(code, {}), options
        )
        emoji = pair.get("emoji", "🗳️")
        question = f"{emoji} {code} Week {week_num}/52 — When are we playing?"
        multi = pair.get("allows_multiple_answers", False)
        # open_period: 6 days (518400s) — poll auto-closes Saturday night
        result = tg.send_poll(gid, poll_tid, question, options,
                              is_anonymous=False,
                              allows_multiple_answers=multi,
                              allows_adding_options=True,
                              allows_revoting=True,
                              open_period=518400,
                              explanation=hist_str or None)
        msg_id, poll_id = result if result else (None, None)

        # Unpin previous week's poll before pinning the new one
        old_msg_id = poll.get("poll_message_id")
        if old_msg_id:
            tg.unpin_message(gid, old_msg_id)  # pragma: no cover

        # Pin the poll
        if msg_id:
            tg.pin_message(gid, msg_id)

        if hist_str:
            # History recap is a reminder-style post, not the poll itself —
            # route it to the nudge topic alongside the daily ping. The poll
            # widget already carries the same history in its explanation popup.
            tg.send_message(gid, nudge_tid,
                            f"━━━━━━━━━━━━━━━━{hist_str}")

        if msg_id:
            polls[code] = {
                "week_iso": week_key,
                "poll_id": poll_id or "",
                "poll_message_id": msg_id,
                "options": options,  # stored to avoid date drift in notifications
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

    # Session already happened — no more pings this week
    if poll.get("session_happened"):
        return  # pragma: no cover

    # Daily ping — once per calendar day (ordinal)
    today_ord = now.toordinal()
    if today_ord <= poll.get("last_ping_day", -1):
        return  # pragma: no cover

    roster = _poll_roster(config, state, pid, pair)
    voted_uids = poll.get("voted_uids", [])
    unvoted = _unvoted_mentions(roster, voted_uids)

    # Re-pin the poll on every daily ping — guards against other messages
    # (e.g. Matrix bridge) overriding the pin
    poll_msg_id = poll.get("poll_message_id")
    if poll_msg_id:
        tg.pin_message(gid, poll_msg_id)

    if not unvoted:
        if not poll.get("all_voted_posted"):
            tg.send_message(gid, nudge_tid,
                            build_all_voted_message(code, len(roster), week_num))
            poll["all_voted_posted"] = True
        return

    # Count only roster members who voted (non-roster voters inflate voted_uids)
    roster_voted = sum(1 for uid in roster if uid in set(str(v) for v in voted_uids))
    link = _poll_link(config, pair, poll_msg_id)
    msg = build_ping_message(pair, unvoted, roster_voted,
                             len(roster), week_num, link)
    if tg.send_message(gid, nudge_tid, msg):
        poll["last_ping_day"] = today_ord
        print(f"Session poll ping: {code} day {weekday}")


def post_session_poll(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post or update session polls for all hybrid campaigns."""
    now = now or datetime.now(timezone.utc)
    for pair in config.get("topic_pairs", []):
        # session_poll_disabled lets a hybrid campaign opt out of the weekly
        # poll + daily nudges without flipping hybrid_live (which also drives
        # campaign-table labelling and under-staffed warnings).
        if pair.get("hybrid_live") and not pair.get("session_poll_disabled"):
            try:
                _post_one(config, state, pair, now)
            except Exception as e:
                print(f"Session poll error ({pair.get('code', '?')}): {e}")
