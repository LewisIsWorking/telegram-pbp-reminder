"""DM the GM the "Reply to this next" message, but only when it changes.

Lewis, 2026-09-13: the "SORT IT OUT, GM!" escalation already reaches him as
a DM, and he asked for the focus message to arrive the same way.

⛔⛔ **It is sent on CHANGE, not on every queue post.** The queue posts about
once an hour, measured 2026-09-13 as 1706 -> 1735 in 24h. The focus message
rides along with each of those. DMing every copy would be ~25 DMs a day, most
of them identical, and would bury the escalation messages he actually reads.

What is worth a notification is "your next reply has moved". So the DM goes
out when the target changes, and stays quiet while it does not. The newest DM
is therefore always current, and the older ones read as a timeline, which is
how he already reads the escalation DMs.

⚠️ Deliberately NOT deleted when superseded, unlike the copy in the group
topic, which is evicted with its batch. That one must go because it would keep
pointing at a message the GM has already answered. A DM here cannot mislead in
the same way: answering the target moves the focus, which sends a new DM that
supersedes it. Tracking DM deletions would also pull in the whole orphan and
48-hour-wall machinery for no gain.

⚠️ Only the focus message is sent, never the quiet-campaign fallback that
``queue_followup`` substitutes when nothing is owed a reply. That fallback is a
different message, it is not urgent, and it is not what was asked for.
"""

from scheduled.queue_focus import build_focus_message, focus_key

STATE_KEY = "last_focus_dm_key"


def send_focus_dm(config: dict, state: dict, scanned: dict,
                  priority_map: dict, now, *, send) -> bool:
    """DM the focus message if its target changed. Returns True if sent.

    ``send`` is ``telegram.send_message``, passed in so the caller keeps its
    own patch point rather than this module importing a second copy of it.
    """
    gm_uid = config.get("gm_user_id")
    if not gm_uid:
        return False

    key = focus_key(scanned, priority_map)
    if key is None:
        # Nothing owed. Forget the last target, so that if the same message
        # is somehow the focus again later it is announced rather than
        # silently skipped as a duplicate.
        state.pop(STATE_KEY, None)
        return False

    if state.get(STATE_KEY) == key:
        return False

    text = build_focus_message(config, scanned, priority_map, now)
    if not text:
        return False

    # ⚠️ Record the target only once Telegram has accepted it. Recording
    # before the send would mark a failed DM as delivered, and it would then
    # never be retried because the target has not changed.
    if not send(gm_uid, None, text):
        return False
    state[STATE_KEY] = key
    return True
