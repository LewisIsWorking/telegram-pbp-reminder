"""Old schedule posts whose delete failed, kept in ``state["schedule_post_stale"]`` and retried every run (issue #36).

The schedule post replaces itself: post the new copy, delete the old one. Until 2026-11-25 the delete's result was
thrown away and the old id overwritten, so a single failed delete left a schedule post that nothing remembered, and the
topic held two of them for good. The ids here are also registered by posting/bot_sent_state_scan.py, or the retried
delete would be refused by the bot-sent guard just like the first one.
"""
import telegram as tg


def delete_or_keep(state: dict, chat_id: int, msg_id: int) -> None:
    """Delete an old schedule post; if that fails, remember it for the next run."""
    try:
        ok = tg.delete_message(chat_id, msg_id)
    except Exception as e:  # never lose the id to an exception either
        print(f"schedule post: delete {msg_id} raised {type(e).__name__}")
        ok = False
    if not ok:
        state.setdefault("schedule_post_stale", []).append([chat_id, msg_id])


def retry_stale(state: dict) -> None:
    """Retry old schedule posts a delete missed. One that posting.stuck_deletes
    has given up on (Telegram will not delete it any more) is dropped: it is
    already reported there for a human to remove."""
    from posting.stuck_deletes import is_hopeless
    stale, state["schedule_post_stale"] = state.get("schedule_post_stale") or [], []
    for chat_id, msg_id in stale:
        if not is_hopeless(msg_id):
            delete_or_keep(state, chat_id, msg_id)


def take_down(config: dict, state: dict) -> None:
    """Delete the last schedule post, if there is one, and forget it."""
    prev = state.get("schedule_post_msg_id")
    if not prev:
        return
    prev_chat = state.get("schedule_post_chat_id") or config["group_id"]
    if tg.delete_message(prev_chat, prev):
        state.pop("schedule_post_msg_id", None)
        state.pop("schedule_post_chat_id", None)

