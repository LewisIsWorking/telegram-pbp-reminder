"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts
from commands.queue_format import NO_PRIORITY, build_priority_map
from scheduled.due import latest_due_slot
from scheduled.topic_queue_poster import post_topic_queues
from scheduled.queue_silence import (
    silent_rows, silent_lines_for, silent_ids, caught_up_campaigns,
    campaign_age_lines,
)
from scheduled.gm_queue_history import post_and_persist
from scheduled.queue_caught_up import post_caught_up as _post_caught_up
from scheduled.queue_followup import build_followup
from scheduled.queue_focus_dm import send_focus_dm
from scheduled.queue_refresh import (checked_line, next_check_line,
                                     refresh_in_place)
from scheduled.queue_render import (
    build_streak, build_summary, build_momentum_map, build_header,
    chunk_messages, build_body_lines,
)


def post_queue_reminder(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    if not bot_topic:
        return  # pragma: no cover
    now = now or datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)

    # Maintain per-topic pinned queues — always runs, independent of bot-topic posting
    post_topic_queues(config, scanned, now, state=state)

    # Build a fingerprint of the current queue state
    fingerprint_parts = []
    for pid in sorted(scanned.keys()):
        data = scanned[pid]
        for entry in data["entries"]:
            fingerprint_parts.append(f"{pid}:{entry['time']}")
    fingerprint = "|".join(fingerprint_parts) if fingerprint_parts else "empty"

    # Only post if queue changed since last post, OR it's a scheduled reminder hour
    # queue_daily_hours: list of UTC hours to post (e.g. [9, 21])
    # queue_daily_hour: legacy single-hour setting
    raw = config.get("queue_daily_hours") or (
        [config["queue_daily_hour"]] if config.get("queue_daily_hour") is not None else []
    )
    daily_hours = raw if isinstance(raw, list) else [raw]
    # ⛔⛔ Was `if now.hour in daily_hours` until 2026-09-06. With GitHub
    # delivering ~27% of the cron, that missed 10 of 28 daily slots in a
    # fortnight, both slots on three separate days. Now the first run at
    # or after a slot's hour posts it. See scheduled/due.py.
    slot_key = latest_due_slot(now, daily_hours,
                               state.get("last_queue_daily_slots", []))
    is_daily = slot_key is not None

    group_id = config["group_id"]
    # Built before the early returns because all three exits need it to
    # choose a follow-up. Lower number = higher priority; legacy
    # queue_priority: True maps to level 1.
    priority_map = build_priority_map(config)
    # One list of silent rows, two views of it, so the lines shown and the
    # ids fingerprinted can never disagree. See queue_silence.silent_rows.
    rows = silent_rows(config, state, scanned, now)
    silent_lines = silent_lines_for(rows)
    # ⛔ The ids, not silent_lines. The lines carry ages that tick hourly,
    # which reposted the queue every hour for nothing. See silent_ids.
    ids = silent_ids(rows)
    if ids:
        fingerprint += "|silent:" + "|".join(ids)
    # ⚠️ No longer an early return. An unchanged queue is edited in place
    # further down, which needs the render. The caught-up branches below guard
    # themselves against reposting. See scheduled/queue_refresh.py.
    refreshing = (not is_daily
                  and fingerprint == state.get("last_queue_fingerprint", ""))

    if not scanned and not silent_lines:
        # Queue is empty AND no silent campaigns to display. If we're
        # transitioning from a non-empty fingerprint, post a one-time
        # "All caught up!" notification so GMs see the state change;
        # otherwise stay silent so we don't spam the topic with the
        # same message every cron tick.
        #
        # Note: the scanner (queue_scan.py:185-197) omits campaigns
        # with zero entries, so this branch — not the total==0 branch
        # below — is the one that actually fires when every queue is
        # clean.
        if state.get("last_queue_fingerprint", "empty") != "empty":
            # See _post_caught_up docstring — routes via batch
            # machinery so the previous GM queue gets evicted.
            _post_caught_up(state, group_id, bot_topic,
                             campaign_age_lines(config, state, scanned, now),
                             build_followup(config, state, scanned,
                                            priority_map, now))
        state["last_queue_fingerprint"] = "empty"
        return

    total = sum(len(d["entries"]) for d in scanned.values())
    if total == 0 and not silent_lines:
        if state.get("last_queue_fingerprint", "empty") != "empty":
            # Defensive path (current scanner doesn't produce this
            # shape but might in the future). Same fix as line-68.
            _post_caught_up(state, group_id, bot_topic,
                             campaign_age_lines(config, state, scanned, now),
                             build_followup(config, state, scanned,
                                            priority_map, now))
        state["last_queue_fingerprint"] = fingerprint
        return

    # C11 uses level 0 (highest), C06 uses level 1, rest use level 2.
    priority_pids = set(priority_map.keys())  # kept for pin-icon display

    def sort_key(pid):
        entries = scanned[pid]["entries"]
        oldest = min(e.get("time", "9999") for e in entries)
        # NO_PRIORITY sorts after every explicit rank. Was 2 until
        # 2026-07-30, which collided with real rank 2.
        return (priority_map.get(pid, NO_PRIORITY), oldest)

    sorted_pids = sorted(scanned.keys(), key=sort_key)
    streak = build_streak(state, now)
    summary = build_summary(scanned, sorted_pids)
    momentum_map = build_momentum_map(state, config)

    def _render(queue_num):
        """The queue batch for a given post number.

        ⚠️ Takes the number rather than computing count+1, because a refresh
        must show the CURRENT number and a repost the next. Computing it here
        would renumber a queue that has not changed, on every run.
        """
        lines = [build_header(queue_num, total, streak, summary),
                 checked_line(now), next_check_line(now)]
        lines.extend(build_body_lines(config, state, scanned, sorted_pids,
                                      priority_pids, momentum_map, now))
        if silent_lines:
            lines.append("━━ 💤 Silent campaigns ━━")
            lines.extend(silent_lines)
        # Caught-up campaigns (no unreplied entries, posted recently). Kept OUT
        # of the fingerprint: their ages tick every hour, so including them
        # would re-post the queue continuously. Moving in/out of caught-up
        # always coincides with an unreplied or silent change anyway.
        caught_up_lines = caught_up_campaigns(config, state, scanned, now)
        if caught_up_lines:
            lines.append("━━ ✅ Caught up ━━")
            lines.extend(caught_up_lines)
        msgs = chunk_messages(lines, "\n".join(lines))
        # The "go here next" follow-up, in the same batch so it is evicted
        # with the queue it describes. build_followup picks between the reply
        # focus and the oldest-campaign callout; see its docstring.
        focus = build_followup(config, state, scanned, priority_map, now)
        if focus:
            msgs.append(focus)
        return msgs

    count = state.get("queue_post_count", 0)
    if refreshing:
        # Unchanged queue: edit it in place so it visibly stays alive without
        # notifying anyone. Any failure to edit cleanly reposts below.
        if refresh_in_place(state, group_id, _render(count),
                            edit=tg.edit_message):
            print(f"Queue reminder: refreshed in place ({total} unreplied)")
            return
        print("Queue reminder: could not refresh in place, reposting")

    queue_num = count + 1
    msgs = _render(queue_num)

    sent, _first_msg_id = post_and_persist(state, group_id, bot_topic, msgs)
    if sent:
        state["last_queue_fingerprint"] = fingerprint
        state["queue_post_count"] = queue_num
        # What each message now says, so the next unchanged run can skip
        # re-sending identical text. See queue_refresh.refresh_in_place.
        state["gm_queue_texts"] = list(msgs)
        if is_daily:
            # ⚠️ The slot computed ABOVE, not now.hour. A catch-up post
            # at 14:00 fills the 09:00 slot; keying the record on the
            # wall clock would file it as a 14:00 slot that nothing ever
            # asked for, and 09:00 would stay due forever.
            slots = state.setdefault("last_queue_daily_slots", [])
            if slot_key not in slots:
                slots.append(slot_key)
            # Keep only last 14 slots (7 days × 2 posts/day)
            state["last_queue_daily_slots"] = slots[-14:]
            state["last_queue_daily"] = now.date().isoformat()  # backwards compat
        print(f"Queue reminder: {total} unreplied ({len(msgs)} msg)")
        # Also DM the GM the focus message, but only when its target has
        # moved. See queue_focus_dm for why it is not sent on every post.
        # ⚠️ tg.send_message is looked up HERE, at call time, so a test
        # patching telegram.send_message still reaches it.
        if send_focus_dm(config, state, scanned, priority_map, now,
                         send=tg.send_message):
            print("Queue focus DM sent: target changed")

