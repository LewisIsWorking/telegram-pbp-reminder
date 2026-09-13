"""Refresh the pinned GM queue in place, instead of reposting it.

Lewis, 2026-09-13: "The bot doesn't seem to be firing per half hour now, the
queue isn't updating."

It was firing. The queue was updating, on every real change. What had gone was
**the only visible sign it was alive.** Until earlier that day the queue
reposted every hour whether or not anything changed, because ticking ages sat
in its change fingerprint. That was a bug, and fixing it made the queue post
only on real change. But the hourly repost had doubled as a heartbeat, so a
healthy quiet queue became indistinguishable from a dead bot.

This restores the heartbeat without the noise. On a run where the queue has
NOT changed, every message in the current batch is **edited** with a fresh
render: a "Checked" time, and up-to-date ages. Telegram edits notify nobody,
so it is visible without being loud, and the frozen silent-campaign ages that
the fingerprint fix had introduced are current again too.

⛔ It falls back to a normal repost whenever it cannot edit cleanly, and the
exact reason never has to be known:

- **Telegram's edit time limit is not reliably documented.** Third-party
  sources say bots may edit for 48 hours; one says admins with pin rights may
  edit indefinitely. So nothing here assumes either. If Telegram refuses an
  edit, for any reason, the caller reposts. A repost creates a fresh message,
  which restarts whatever the limit is.
- **The message count must match exactly.** ``post_batch`` records the id of
  each chunk only if that chunk SENT, so one earlier failure leaves the stored
  ids a position short. Pairing by index would then write chunk 3's text into
  chunk 2's message. A count mismatch reposts instead.
"""

from scheduled import local_time


def checked_line(now) -> str:
    """The visible heartbeat, in the time zone Lewis reads."""
    return f"🕒 Checked {local_time.fmt(now)}"


def refresh_in_place(state: dict, group_id: int, msgs: list[str], *,
                     edit) -> bool:
    """Edit the current queue batch to match ``msgs``. True if it now does.

    False means "repost instead": there is no batch to edit, its message count
    no longer matches, or Telegram refused an edit. A partial success also
    returns False, because the repost that follows evicts the whole old batch,
    including any message that was already edited.

    ``edit`` is ``telegram.edit_message``, passed in so the caller keeps its
    own patch point.

    ⛔⛔ **Messages whose text has not changed are skipped, not re-sent.** Only
    the first message carries the "Checked" time. The others, including the
    focus follow-up, are often byte-identical between runs half an hour apart,
    because an age like "3d 7h" does not always tick over. Telegram answers an
    identical edit with "message is not modified", ``edit_message`` reports
    that as a failure, and the refresh would repost almost every run.

    Suppressing "message is not modified" instead would have needed a new
    public function in telegram.py, which is on the length backlog and may not
    grow, and it would add an entry to the suppression registry. Not sending
    identical text needs neither: the error simply cannot occur.

    The texts are remembered in ``state["gm_queue_texts"]``. With none
    remembered, as on the first run after this ships, every message is edited
    and any unchanged one triggers a single repost, which records them.
    """
    history = state.get("gm_queue_history") or []
    if not history:
        return False
    ids = history[-1].get("msg_ids") or []
    if not ids or len(ids) != len(msgs):
        return False
    previous = state.get("gm_queue_texts") or []
    for index, (message_id, text) in enumerate(zip(ids, msgs)):
        if index < len(previous) and previous[index] == text:
            continue
        if not edit(group_id, message_id, text):
            return False
    state["gm_queue_texts"] = list(msgs)
    return True
