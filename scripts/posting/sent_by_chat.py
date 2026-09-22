"""Bot-sent message IDs, kept per chat.

``bot_sent_registry`` is a flat set of ints with no chat attached. That
was sound while the bot posted in one group. It stopped being sound on
2026-08-17, when the schedule post moved to the Nudge Bot Notifications
group, and would have got much worse on 2026-09-22, when four families
of GM messages followed it there (``helpers_pkg.routes``).

Message IDs are only unique WITHIN a chat. A small ID the bot sent in the
notifications group, recorded in the flat set, makes the delete guard
say "the bot sent this" about the message with the same ID in Path Wars,
which is years old and almost certainly a player's. The guard exists to
refuse exactly that delete.

So: the main group keeps using the flat registry, unchanged, and each
chat the config names as a separate destination gets its own set here.
New IDs from those chats never enter the flat set, so they can never
authorise a delete in the main group.

⚠️ The other direction still consults the flat set. Schedule posts sent
before this existed were recorded there, and refusing to clean them up
would strand them. That direction is the old behaviour, and the risk it
carries is small: those chats are GM-only logs, not player topics.
"""

import threading

from state_store import StateStore

_LOCK = threading.Lock()
_AUX_NAME = "bot_sent_ids_by_chat"
_store = StateStore()
_BY_CHAT: dict[str, set[int]] | None = None
_SEPARATE: list = []  # [frozenset of chat ids] once looked up; a list so tests can clear it

# Config keys naming a chat other than the main group. Only these chats are
# kept apart. Any other chat, including the made-up ids tests post to, uses
# the flat registry exactly as before, so nothing that worked changes.
_CHAT_KEYS = ("schedule_chat_id", "debug_chat_id", "recruit_mirror_chat_id")


def _separate_chats() -> frozenset:
    if not _SEPARATE:
        try:
            from helpers_pkg.config import load_config
            cfg = load_config()
            ids = {cfg.get(k) for k in _CHAT_KEYS}
            ids |= {r.get("chat_id") for r in (cfg.get("notification_routes") or {}).values()}
            ids.discard(None)
            ids.discard(cfg.get("group_id"))
            _SEPARATE.append(frozenset(int(i) for i in ids))
        except Exception as exc:  # pragma: no cover - no config at all
            print(f"[sent_by_chat] no config ({exc}); every chat uses the flat registry")
            _SEPARATE.append(frozenset())
    return _SEPARATE[0]


def is_main(chat_id: int | None) -> bool:
    """False only for a chat the config names as a separate destination."""
    return chat_id is None or int(chat_id) not in _separate_chats()


def _load_locked() -> dict[str, set[int]]:
    global _BY_CHAT
    if _BY_CHAT is None:
        raw = _store.load_aux(_AUX_NAME, default={})
        raw = raw if isinstance(raw, dict) else {}
        _BY_CHAT = {str(c): {int(m) for m in ids} for c, ids in raw.items()}
    return _BY_CHAT


def record_sent_in(chat_id: int | None, message_id: int | None,
                   text: str | None = None, thread_id: int | None = None,
                   kind: str | None = None) -> None:
    """Record a successful send against the chat it was sent in."""
    if message_id is None:
        return
    if is_main(chat_id):
        from posting.bot_sent_registry import record_sent
        record_sent(message_id, text, thread_id, kind)
        return
    from posting.sent_log import record as _describe
    _describe(message_id, text=text, thread_id=thread_id, kind=kind)
    with _LOCK:
        ids = _load_locked().setdefault(str(int(chat_id)), set())
        if int(message_id) not in ids:
            ids.add(int(message_id))
            _store.save_aux(_AUX_NAME, {c: sorted(s) for c, s in _BY_CHAT.items()})


def is_bot_sent_in(chat_id: int | None, message_id: int | None) -> bool:
    """Did the bot send ``message_id`` in ``chat_id``? Main group -> flat registry."""
    if message_id is None:
        return False
    if is_main(chat_id):
        from posting.bot_sent_registry import is_bot_sent
        return is_bot_sent(message_id)
    with _LOCK:
        if int(message_id) in _load_locked().get(str(int(chat_id)), set()):
            return True
    from posting.bot_sent_registry import is_bot_sent
    return is_bot_sent(message_id)  # recorded before per-chat sets existed


def reset_for_test() -> None:
    """Reset in-memory state. Tests only."""
    global _BY_CHAT
    with _LOCK:
        _BY_CHAT = None
        _SEPARATE.clear()
