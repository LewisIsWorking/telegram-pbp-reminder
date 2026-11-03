"""'Reply to this next' focus message for the GM queue.

Posted as a follow-up message in the GM queue topic, immediately after the
queue itself, naming the single campaign most in need of a reply.

Selection rule:
  1. Normally the winner is the campaign whose *oldest* unreplied message has
     been waiting longest.
  2. Campaigns flagged ``queue_priority`` in their topic_pair override that:
     if any prioritised campaign has unreplied entries, the choice is made
     among those only. A prioritised campaign is therefore never passed over
     because some other campaign has an older message.
  3. Otherwise a silent or caught-up campaign (nothing unreplied) goes first
     when it has gone longer without a post than the oldest message has been
     waiting (2026-09-25). See ``pick_idle_focus``.
  0. Before all of these, a campaign flagged ``queue_always_first`` that has
     gone quiet is the focus whatever else is waiting (2026-10-07). See
     ``scheduled/queue_always_first.py``.

Below the pick, an "Oldest waiting" line names the single oldest unreplied
post across every campaign (Lewis, 2026-11-03): the pick is the PRIORITY
next, that line is the CHRONOLOGICAL next. When both are the same post, one
line says so instead. See ``oldest_waiting_lines``.

The message is appended to the queue's own message batch, so it is deleted
along with that batch on the next post (``MAX_KEPT_BATCHES = 1``). That
matters - a focus message that outlived its queue would keep pointing at a
message the GM has already answered.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import age_str, short_preview
from scheduled.queue_always_first import always_first_message, pick_always_first


def _oldest_entry(entries: list) -> dict:
    """Return the entry with the earliest timestamp."""
    return min(entries, key=lambda e: e.get("time", "9999"))


def _wait_hours(entry: dict, now: datetime) -> float:
    """Hours since the entry was posted; 0 when the timestamp is unparseable."""
    try:
        posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
        return helpers.hours_since(now, posted.replace(tzinfo=timezone.utc))
    except (ValueError, KeyError):
        return 0.0


OLDEST_LABEL = "⏳ Oldest waiting:"
SAME_POST_LINE = "⏳ That is also the oldest post waiting anywhere."


def _campaign_label(config: dict, data: dict) -> str:
    """'<emoji> C04: Magni Guard', as the focus line names a campaign."""
    code = data.get("code", "")
    name = data.get("campaign", "")
    label = f"{code}: {name}" if code else name
    emoji = next((p.get("emoji", "") for p in config.get("topic_pairs", [])
                  if p.get("code") == code), "") if code else ""
    return f"{emoji} {label}" if emoji else label


def pick_oldest_waiting(scanned: dict):
    """(pid, entry) for the oldest unreplied post in any campaign, or None."""
    best = None
    for pid, data in scanned.items():
        entries = data.get("entries") or []
        if not entries:
            continue
        entry = _oldest_entry(entries)
        if best is None or entry.get("time", "9999") < best[1].get("time", "9999"):
            best = (pid, entry)
    return best


def oldest_waiting_lines(config: dict, scanned: dict, now: datetime,
                         focus_entry: dict | None = None) -> list:
    """The chronological next, as lines to add under the priority pick.

    ``focus_entry`` is the post the pick already points at, if it points at a
    post at all (an idle campaign is a campaign, not a post). When it is the
    oldest post too, a single line says so rather than naming it twice.
    """
    oldest = pick_oldest_waiting(scanned)
    if oldest is None:
        return []
    pid, entry = oldest
    if focus_entry is not None and entry is focus_entry:
        return [SAME_POST_LINE]
    lines = [f"{OLDEST_LABEL} {_campaign_label(config, scanned[pid])}, "
             f"{entry.get('name', '?')}, {age_str(_wait_hours(entry, now))}"]
    link = entry.get("link", "")
    if link:
        lines.append(f"🔗 {link}")
    return lines


def pick_focus_pid(scanned: dict, priority_map: dict) -> str | None:
    """Return the pid of the campaign most in need of a reply, or None.

    ``priority_map`` is the same pid -> rank map the queue reminder builds
    from ``queue_priority``. When several prioritised campaigns are waiting,
    the lower rank wins first, then the older message.
    """
    pids = [p for p, d in scanned.items() if d.get("entries")]
    if not pids:
        return None
    prioritised = [p for p in pids if p in priority_map]
    pool = prioritised or pids

    def sort_key(pid):
        oldest = _oldest_entry(scanned[pid]["entries"]).get("time", "9999")
        return (priority_map.get(pid, 0) if prioritised else 0, oldest)

    return min(pool, key=sort_key)


def pick_idle_focus(config: dict, state: dict | None, scanned: dict,
                    priority_map: dict, now: datetime):
    """The silent or caught-up campaign that should go first, or None.

    Lewis, 2026-09-25: a campaign nobody is waiting on can still need the GM
    more than the oldest unreplied message does. So it competes on the same
    clock: hours since its last post against hours the oldest message has
    waited, and the longer wait wins. A tie goes to the waiting message.

    Only when the queue has entries: an empty queue already ends with the
    "Oldest campaign" callout, and two "go here next" lines would disagree.
    A prioritised campaign with entries still wins outright. A campaign with
    no recorded post (``days=inf``) never competes, or it would win forever.
    """
    pid = pick_focus_pid(scanned, priority_map)
    if state is None or not pid or pid in priority_map:
        return None
    from scheduled.queue_silence_rows import idle_campaigns
    rows = [r for r in idle_campaigns(config, state, scanned, now)
            if r.ever_posted and r.days != float("inf")]
    if not rows:
        return None
    row = max(rows, key=lambda r: r.days)
    waited = _wait_hours(_oldest_entry(scanned[pid]["entries"]), now)
    return row if row.days * 24 > waited else None


def focus_key(scanned: dict, priority_map: dict, *, config: dict | None = None,
              state: dict | None = None, now: datetime | None = None) -> str | None:
    """A stable identity for the current focus target, or None if there is none.

    Used by ``queue_focus_dm`` to tell "the target moved" from "the same target
    was posted again". Built from ``pick_focus_pid`` and ``_oldest_entry``, the
    same two calls ``build_focus_message`` makes, so the key and the message
    cannot disagree about which message is being pointed at.

    ⚠️ Identifies the MESSAGE, not the campaign. Answering the oldest message in
    a campaign keeps the same campaign in focus but moves the target to its next
    oldest, and that is exactly a change worth announcing. An idle campaign in
    focus is keyed by campaign, which stays put until someone posts there.
    """
    if config is not None and now is not None:
        first = pick_always_first(config, state, scanned, now)
        if first:
            return f"idle:{first.pid}"
    pid = pick_focus_pid(scanned, priority_map)
    if not pid:
        return None
    if config is not None and now is not None:
        row = pick_idle_focus(config, state, scanned, priority_map, now)
        if row:
            return f"idle:{row.pid}"
    entry = _oldest_entry(scanned[pid]["entries"])
    return entry.get("link") or f"{pid}@{entry.get('time', '')}"


def _idle_focus_message(row, scanned: dict, pid: str, now: datetime) -> str:
    """The focus message when a silent or caught-up campaign goes first."""
    from scheduled.queue_silence_rows import callout_phrase
    waiting = age_str(_wait_hours(_oldest_entry(scanned[pid]["entries"]), now))
    quiet = callout_phrase(row)
    lines = ["━━━━━━━━━━━━━━━━",
             f"🎯 Post here next: {row.icon} {row.prefix}{row.label}",
             f"⏳ {quiet[0].upper()}{quiet[1:]}, longer than the oldest reply "
             f"owed anywhere ({waiting}).",
             "Nobody is waiting on you there, so it needs you to get it moving."]
    if row.link.strip():
        lines.append(row.link.strip())
    return "\n".join(lines)


def build_focus_message(config: dict, scanned: dict, priority_map: dict,
                        now: datetime, state: dict | None = None) -> str:
    """Build the focus message, or '' when there is nothing to point at.

    Pass ``state`` so silent and caught-up campaigns can go first; without it
    only unreplied messages compete, as before 2026-09-25.
    """
    first = pick_always_first(config, state, scanned, now)
    if first:
        return "\n".join([always_first_message(first),
                          *oldest_waiting_lines(config, scanned, now)])
    pid = pick_focus_pid(scanned, priority_map)
    if not pid:
        return ""
    row = pick_idle_focus(config, state, scanned, priority_map, now)
    if row:
        return "\n".join([_idle_focus_message(row, scanned, pid, now),
                          *oldest_waiting_lines(config, scanned, now)])

    data = scanned[pid]
    entry = _oldest_entry(data["entries"])

    waiting = age_str(_wait_hours(entry, now))
    count = len(data["entries"])
    who = entry.get("name", "?")
    preview = short_preview(entry.get("preview", ""), words=18)

    lines = ["━━━━━━━━━━━━━━━━",
             f"🎯 Reply to this next: {_campaign_label(config, data)}"]
    if pid in priority_map:
        lines.append("📌 Prioritised campaign, so it jumps the age queue.")
    lines.append(f"⏳ Oldest message waiting {waiting} "
                 f"({count} unreplied in this campaign).")
    lines.append(f"↗ {who}: {preview}")
    link = entry.get("link", "")
    if link:
        lines.append(f"🔗 {link}")
    lines.extend(oldest_waiting_lines(config, scanned, now, focus_entry=entry))
    return "\n".join(lines)
