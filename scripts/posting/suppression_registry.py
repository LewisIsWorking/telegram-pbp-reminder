"""Which Telegram error bodies may be treated as success, and why.

``telegram._post`` returns ``True`` — soft success — for any response
matching a ``suppress_errors`` entry. That is correct **only** when the
error means the caller's goal is already achieved. It is catastrophic
when the error means the operation did not happen, because every
downstream retry, alert and audit then records a success that never was.

On 2026-05-10 ``"message can't be deleted"`` was added to the delete
list. It means the message is **still there**. For three months the bot
recorded 715 deletes, 715 successes and zero failures while 28 messages
it believed it had removed sat in the group. Lewis found it by scrolling
Telegram — no test, guard or report ever mentioned it.

⭐ The registry lives here, in production code, rather than in the test
that checks it. ``ALREADY_GONE_ERRORS`` is *derived* from the dict below,
so a string cannot reach ``suppress_errors`` without someone writing down
why it means "already true". The justification is not documentation about
the guard, it is the mechanism of the guard.

⛔ THE RULE. The error must mean **the thing you wanted is already true**.
If it means "I refused", "I could not", or "not permitted", it is a
FAILURE. Bound the retry instead — see ``posting.stuck_deletes`` — and
leave the outcome honest.
"""

# Every string that may be treated as soft success, mapped to the reason
# the desired end state already holds. Adding an entry is a deliberate act.
SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED = {
    "message to delete not found":
        "A delete on an ID Telegram no longer has. The message is gone, "
        "which is what the caller wanted. Removed in a prior run, by an "
        "admin, by the author, or an expired service message.",
    "message not found":
        "An unpin where the pinned message is already gone. Nothing is "
        "pinned, which is what the caller wanted.",
    "message to unpin not found":
        "The same condition, in the other wording Telegram uses.",
    "MESSAGE_ID_INVALID":
        "Telegram's older error code for the same already-gone "
        "condition. Still emitted in some edge cases.",
}

# Strings that LOOK suppressible and are not. Listed so the mistake is
# refused by name with its history attached, rather than rediscovered.
NEVER_SUPPRESS = {
    "message can't be deleted":
        "Means the message is STILL IN THE CHAT. Suppressed 2026-05-10, "
        "removed 2026-08-16 after it orphaned 28 messages and reported "
        "every one as deleted. Telegram returns this for any bot message "
        "older than 48h, and administrator rights do not lift that.",
    "message can't be edited":
        "The edit did not happen. Same shape as the delete case.",
    "not enough rights":
        "A permissions failure. The operation did not happen.",
    "CHAT_ADMIN_REQUIRED":
        "A permissions failure. The operation did not happen.",
}

# The tuple the guarded call sites actually pass. Derived, never retyped:
# the 2026-08-16 audit found the test guarding this list had declared its
# own copy, so it verified the mechanism and never the configuration.
ALREADY_GONE_ERRORS = tuple(SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED)

# Delete and unpin share one list. A delete-specific string simply never
# matches an unpin response, so splitting them would buy nothing and
# reintroduce exactly the hand-maintained subset that caused the bug.
assert not (set(SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED)
            & set(NEVER_SUPPRESS)), \
    "a string cannot be both safe to suppress and banned"
