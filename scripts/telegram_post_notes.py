"""Diagnostic notes on Telegram API edge cases.

Extracted from ``scripts/telegram.py`` to keep that file under the 200-
line cap. Importing this module is not required at runtime; it exists
to document non-obvious API behaviour that the production code relies
on. The ``_post`` docstring in ``telegram.py`` references this file.

\u2500\u2500 Soft-success responses (deleteMessage / unpinChatMessage) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

For "is the message there?" operations, certain Telegram error bodies
indicate the *desired end state is already achieved*. The bot should
treat these as success, not failure. Patterns currently recognised:

* ``"message to delete not found"`` \u2014 deleteMessage on an already-gone
  message ID. Could be: message deleted in a prior bot run, message
  deleted by an admin, message deleted by the author, expired
  service message, etc.
* ``"MESSAGE_ID_INVALID"`` \u2014 Telegram's old-style error code for the
  same condition. Still emitted in some edge cases.
* ``"message not found"`` \u2014 emitted by unpinChatMessage when the
  pinned message is already gone (deleted, or pin was already cleared).
The live list is ``posting.safe_delete.ALREADY_GONE_ERRORS`` \u2014 read it
there rather than trusting this prose, which cannot fail a build.

\u26d4 ``"message can't be deleted"`` **was** on this list and was removed on
2026-08-16. The old rationale ran: it is emitted for service messages
and a few other edge cases; from the bot's perspective the message is
going to stay there regardless of how many times it asks; and treating
it as failure causes infinite retry loops in queue history eviction.

Every clause of that is true and the conclusion still does not follow.
"The message is going to stay there" is the *definition* of a failed
delete, not a soft success. Suppressing it made
``perform_guarded_delete`` return True, so the caller cleared the
tracked slot and dropped the ID before ``pending_delete`` could ever
retry it \u2014 the one mechanism built to catch orphans never saw an orphan.
The pin audit recorded **715 deletes, 715 successes, zero failures,
ever**, while an ``Unreplied: 2`` post from 2026-08-03 sat in the C06
topic for thirteen days until Lewis spotted it. An outcome column with
one possible value measures nothing.

The retry-loop problem was real, and is now solved where it belongs, in
``posting.stuck_deletes``: bounded attempts, then the bot stops asking
and files the ID for a human to remove. That ends the loop without
falsifying the outcome.

Pre-2026-05-10 ``_post`` returned ``None`` for all these cases. Both
callers (``posting.safe_delete.perform_guarded_delete`` and
``telegram.unpin_message``) check ``_post(...) is not None``, so they
read these as failure. That left old GM queue batches stuck past
``MAX_KEPT_BATCHES = 3`` and produced spurious
``Topic queue prev-delete failed`` log entries even when the message
was actually gone.

\u2500\u2500 Safety \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

The fix is downstream of ``posting.bot_sent_registry.is_bot_sent``.
The registry remains the gatekeeper: any message ID not recorded as
sent by the bot is refused at the safe_delete layer before any HTTP
call is made. Treating Telegram's "not found" responses as soft
success does NOT change *which* IDs are attempted \u2014 it only changes
how the result is interpreted for IDs the safeguard has already
approved.

\u2500\u2500 What still returns None \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

* Network exceptions
* HTTP 429 after both retry attempts exhausted
* Status 200 with ``ok: false`` and a body that doesn't match suppress
* Any other non-200 status with a body that doesn't match suppress

These remain hard failures. The caller can retry, log, or surface the
error as appropriate. Real failures still print to stdout for
operator visibility.
"""
