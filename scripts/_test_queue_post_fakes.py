"""A post_and_persist stand-in that records its batch like the real one.

Added 2026-09-13 with the queue's edit-in-place refresh. An unchanged queue is
now edited rather than reposted, which needs a batch of message ids to edit.

⚠️ The older tests patched post_and_persist with a bare ``return_value``. That
recorded nothing, so every later run found no batch, fell back to reposting,
and the tests read that as "the fingerprint gate is broken". A fake that
behaves like the function it replaces keeps those tests about what they test.
"""


def faithful_post_and_persist(state, group_id, bot_topic, msgs, pin=True):
    """Record one batch covering every message, as gm_queue_history does."""
    ids = list(range(1000, 1000 + len(msgs)))
    state["gm_queue_history"] = [{"msg_ids": ids, "pin_id": ids[0]}]
    state["last_queue_pin_id"] = ids[0]
    return True, ids[0]


def edit_ok(chat_id, message_id, text, parse_mode=None, remove_keyboard=False):
    """A telegram.edit_message stand-in where every edit succeeds."""
    return True
