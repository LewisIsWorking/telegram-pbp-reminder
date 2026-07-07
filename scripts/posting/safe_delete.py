"""Safety-guarded message mutation that refuses non-bot messages.

This module is the *enforcement point* for the bot-sent registry. It
hosts the guards that wrap Telegram's ``deleteMessage`` and
``unpinChatMessage`` calls, checking the registry before letting the
request through. Both operations can affect any message in a group
when the bot is admin, so both are gated the same way.

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
    """
    if not is_bot_sent(message_id):
        print(f"[delete_message] REFUSED chat={chat_id} mid={message_id}: "
              f"not in bot_sent_ids registry. The bot only deletes messages "
              f"it sent. To force-add a known bot-sent ID, call "
              f"posting.bot_sent_registry.record_sent({message_id}).")
        record_refusal(chat_id, message_id)
        return False
    return post_fn("deleteMessage", {
        "chat_id": chat_id, "message_id": message_id,
    }, "delete_message",
    suppress_errors=("message to delete not found", "MESSAGE_ID_INVALID",
                     "message not found", "message can't be deleted")) is not None


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
        return False
    return post_fn("unpinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
    }, "unpin_message",
    suppress_errors=("message to unpin not found", "MESSAGE_ID_INVALID",
                     "message not found")) is not None
