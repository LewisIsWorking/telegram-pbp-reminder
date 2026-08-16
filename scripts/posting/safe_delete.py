"""Safety-guarded message mutation that refuses non-bot messages.

This module is the *enforcement point* for the bot-sent registry. It
hosts the guards that wrap Telegram's ``deleteMessage`` and
``unpinChatMessage`` calls, checking the registry before letting the
request through. Both operations can affect any message in a group
when the bot is admin, so both are gated the same way.

It also hosts ``perform_pin`` — pinning needs no guard (it removes no
one's content). Every pin, unpin, AND delete the bot performs is
recorded to ``posting.pin_audit`` so a vanished pin can be traced to
(or cleared of) a specific bot action and call site. Deletes are
included because Telegram auto-unpins a deleted message — a pin can
disappear via a delete with no unpin call at all.

The guards are intentionally placed on the path that ``telegram.py``
delegates to, rather than living inline in ``telegram.delete_message`` /
``telegram.unpin_message``. That delegation keeps ``telegram.py`` under
the 200-line cap while also colocating the safety logic with its
supporting registry module (both live in ``posting/``).

Why a registry guard at all
---------------------------
Telegram bots with admin+delete permissions in a group can delete
*any* message in that group — including player messages, GM messages,
or anything else. There is no Telegram-side flag that says "only
delete my own messages". So the only safe rule is: track every ID the
bot has sent, and refuse to call ``deleteMessage`` for anything else.

The single guard here, combined with the recording calls inside
``telegram.py`` after every successful send, gives that property to
every caller in the codebase — scheduled posters, future maintenance
scripts, and any new code — automatically and unconditionally.

There is intentionally no ``force`` flag. The right way to "force" a
delete of a known bot ID that wasn't recorded (e.g. seeded from old
state) is to call ``posting.bot_sent_registry.record_sent`` explicitly
to add the ID to the registry, and then call ``delete_message``. That
keeps the guard's invariant — "every ID we delete is one we recorded
sending or knowingly added" — intact.
"""

from posting.bot_sent_registry import is_bot_sent
from posting.refusal_log import record_refusal
from posting.pin_audit import record_action
from posting.stuck_deletes import is_hopeless, note_failed_delete

# Error bodies that mean the message is ALREADY GONE, so the delete has
# achieved what it wanted and counts as success. Named and exported
# (2026-08-16) because the test that guards this list used to hand-write
# its own copy and feed that to ``_post`` — so it verified the mechanism
# and never the configuration, and stayed green no matter what
# ``perform_guarded_delete`` actually passed. Derive the scope, do not
# retype it.
#
# ⚠️ Nothing that means "the message is still there" belongs in here. See
# the note in perform_guarded_delete about "message can't be deleted".
ALREADY_GONE_ERRORS = (
    "message to delete not found",
    "MESSAGE_ID_INVALID",
    "message not found",
)


def perform_guarded_delete(chat_id: int, message_id: int, post_fn) -> bool:
    """Delete a message after verifying the bot sent it.

    Args:
        chat_id: Telegram chat/group ID.
        message_id: ID of the message to delete.
        post_fn: The ``telegram._post`` function. Passed in rather
            than imported so the production caller (``telegram.py``)
            avoids a circular import — and so tests can substitute a
            mock without monkeypatching ``telegram``.

    Returns:
        True if the message was successfully deleted on Telegram's
        side. False if either:

        * The message_id is not in the bot-sent registry — the call
          is refused before any HTTP request is made. A diagnostic
          line is printed identifying the offending caller and the
          escape hatch (manual ``record_sent``) for the rare case
          where a legitimate delete needs to proceed.
        * The Telegram API call itself failed (network error, message
          already deleted, permissions, etc).

    The "message not found" / "MESSAGE_ID_INVALID" error families are
    suppressed in the API call — those just mean Telegram already
    cleaned up the message (e.g. expired poll) and the bot's view of
    state is stale, not that anything went wrong.

    ⚠️ ``"message can't be deleted"`` is deliberately NOT suppressed
    (changed 2026-08-16). It used to be, on the reasoning that the
    message "is going to stay there regardless of how many times it
    asks" — true, and precisely why it is a failure. Suppressing it
    made ``ok=True``, which cleared the tracked slot and dropped the ID
    before ``pending_delete`` ever saw it. The message survived and the
    audit trail said it had not: 715 deletes logged, 715 successes,
    zero failures, while a 2026-08-03 ``Unreplied: 2`` post sat in C06.
    The infinite-retry problem that suppression was solving is now
    solved by ``posting.stuck_deletes`` instead — bounded attempts, then
    a reported give-up — which fixes it without falsifying the outcome.
    """
    if is_hopeless(message_id):
        # Already given up on. Skip the HTTP call, and keep returning
        # False so callers still treat the message as present — it is.
        return False
    if not is_bot_sent(message_id):
        print(f"[delete_message] REFUSED chat={chat_id} mid={message_id}: "
              f"not in bot_sent_ids registry. The bot only deletes messages "
              f"it sent. To force-add a known bot-sent ID, call "
              f"posting.bot_sent_registry.record_sent({message_id}).")
        record_refusal(chat_id, message_id)
        record_action("delete", chat_id, message_id, ok=False,
                      refused=True, bot_owned=False)
        return False
    ok = post_fn("deleteMessage", {
        "chat_id": chat_id, "message_id": message_id,
    }, "delete_message",
    suppress_errors=ALREADY_GONE_ERRORS) is not None
    # Deletes are logged because Telegram auto-unpins a deleted message:
    # if a human had pinned this (bot-sent) message, the pin vanishes here
    # with no unpin call. See posting.pin_audit for the full rationale.
    record_action("delete", chat_id, message_id, ok=ok, bot_owned=True)
    if not ok:
        note_failed_delete(chat_id, message_id)
    return ok


def perform_guarded_unpin(chat_id: int, message_id: int, post_fn) -> bool:
    """Unpin a message after verifying the bot sent it.

    The same reality that makes ``perform_guarded_delete`` necessary
    applies to *unpinning*: a bot with admin rights can unpin **any**
    message in the group — not just its own — because Telegram has no
    "only touch my own messages" flag. A stale or crossed message_id
    reaching ``unpinChatMessage`` therefore silently clears a GM's or
    player's manual pin. Every unpin call routes through this guard so
    that can never happen, whatever the ID's origin.

    Args mirror ``perform_guarded_delete``. ``post_fn`` is ``telegram._post``,
    passed in to avoid a circular import and to keep tests mock-friendly.

    Returns True only if the message was in the bot-sent registry AND
    Telegram accepted the unpin. Returns False (no HTTP request made) if
    the ID isn't ours — a diagnostic line names the offending caller and
    the ``record_sent`` escape hatch for the rare legitimate-but-unrecorded
    pin (e.g. one seeded from old state). The "message not found" family
    is suppressed: Telegram auto-unpins expired polls, so the pin may
    already be gone and that is success, not failure.
    """
    if not is_bot_sent(message_id):
        print(f"[unpin_message] REFUSED chat={chat_id} mid={message_id}: "
              f"not in bot_sent_ids registry. The bot only unpins messages "
              f"it sent. To force-add a known bot-sent ID, call "
              f"posting.bot_sent_registry.record_sent({message_id}).")
        record_refusal(chat_id, message_id)
        record_action("unpin", chat_id, message_id, ok=False,
                      refused=True, bot_owned=False)
        return False
    ok = post_fn("unpinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
    }, "unpin_message",
    suppress_errors=("message to unpin not found", "MESSAGE_ID_INVALID",
                     "message not found")) is not None
    record_action("unpin", chat_id, message_id, ok=ok, bot_owned=True)
    return ok


def perform_pin(chat_id: int, message_id: int, post_fn,
                *, disable_notification: bool = True) -> bool:
    """Pin a message and record the action in the pin-audit trail.

    Pinning needs no registry guard — pinning a message the bot didn't
    send is harmless (it doesn't remove anyone's content). But we still
    log *what* the bot pins, because a pin recorded here that later
    turns out to be a human's message is the smoking gun for how a
    non-bot ID could ever enter a ``pin_id`` state field (and thus the
    registry via backfill). ``post_fn`` is ``telegram._post``, passed in
    to avoid a circular import. Returns True on Telegram acceptance.
    """
    ok = post_fn("pinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
        "disable_notification": disable_notification,
    }, "pin_message") is not None
    # Pin is unguarded, so record whether the pinned id is the bot's own.
    # bot_owned=False here would mean the bot pinned a message it never
    # sent — the exact anomaly the non-bot alert exists to catch.
    record_action("pin", chat_id, message_id, ok=ok,
                  bot_owned=is_bot_sent(message_id))
    return ok
