"""Telegram Bot API helpers."""

import time
import requests
from telegram_utils import fetch_updates, message_link  # noqa: F401 — re-exported

TELEGRAM_API = ""


def init(token: str) -> None:
    """Set the API base URL from bot token."""
    global TELEGRAM_API
    TELEGRAM_API = f"https://api.telegram.org/bot{token}"


def _post(method: str, payload: dict, label: str = "request",
          suppress_errors: tuple = ()) -> dict | None:
    """POST to Telegram API. Retries once on HTTP 429.

    Returns the parsed ``result`` payload on 200+ok=true. Returns
    ``True`` when a non-2xx response body matches a ``suppress_errors``
    substring (soft success — the desired end state is already
    achieved). Returns ``None`` for hard failures (network errors,
    rate-limit-after-retry, unrecognised error bodies).

    See ``scripts/telegram_post_notes.py`` for the full rationale,
    the catalogue of recognised soft-success patterns, and the
    safety argument (this is downstream of
    ``posting.bot_sent_registry`` — it does NOT change *which* IDs
    get attempted, only how the result is interpreted).
    """
    for attempt in range(2):
        try:
            resp = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result")
            elif resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                print(f"Telegram rate limit on {label}, waiting {retry_after}s")
                time.sleep(retry_after + 1)
                continue
            _body = resp.text[:500]
            if any(s in _body for s in suppress_errors):
                return True
            print(f"Telegram {label} failed: {_body}")
        except requests.RequestException as e:
            print(f"Telegram {label} network error: {e}")
        break
    return None


def get_updates(offset: int) -> list:
    """Fetch new updates from Telegram. Delegates to telegram_utils."""
    return fetch_updates(TELEGRAM_API, offset)


def send_message(chat_id: int, thread_id: int | None, text: str,
                 parse_mode: str | None = None) -> bool:
    """Send a text message. If thread_id is None, sends to main chat."""
    payload: dict = {"chat_id": chat_id, "text": text, "disable_notification": False}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return _post("sendMessage", payload, "send_message") is not None


def send_message_id(chat_id: int, thread_id: int | None, text: str,
                    parse_mode: str | None = None) -> int | None:
    """Send a text message and return the message_id, or None on failure.

    On success, the returned message_id is recorded in the bot-sent
    registry so a later call to :func:`delete_message` will accept it.
    """
    payload: dict = {"chat_id": chat_id, "text": text, "disable_notification": False}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    result = _post("sendMessage", payload, "send_message")
    if not result:
        return None
    mid = result.get("message_id")
    from posting.bot_sent_registry import record_sent
    record_sent(mid)
    return mid


def send_message_with_buttons(
    chat_id: int, thread_id: int, text: str, buttons: list
) -> int | None:
    """Send a message with inline keyboard buttons. Returns message_id or None.

    On success, the returned message_id is recorded in the bot-sent
    registry so a later call to :func:`delete_message` will accept it.
    """
    result = _post("sendMessage", {
        "chat_id": chat_id, "message_thread_id": thread_id, "text": text,
        "disable_notification": False, "reply_markup": {"inline_keyboard": [buttons]},
    }, "send_button_message")
    if not result:
        return None
    mid = result["message_id"]
    from posting.bot_sent_registry import record_sent
    record_sent(mid)
    return mid


def edit_message(chat_id: int, message_id: int, text: str,
                 parse_mode: str = None, remove_keyboard: bool = False) -> bool:
    """Edit an existing message. Optionally remove inline keyboard."""
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if remove_keyboard:
        payload["reply_markup"] = {"inline_keyboard": []}
    return _post("editMessageText", payload, "edit_message") is not None


def answer_callback(callback_id: str, text: str = "") -> bool:
    """Answer a callback query to dismiss the loading spinner."""
    return _post("answerCallbackQuery", {
        "callback_query_id": callback_id, "text": text,
    }, "answer_callback") is not None


def send_poll(chat_id: int, thread_id: int | None, question: str,
              options: list[str], is_anonymous: bool = False,
              allows_multiple_answers: bool = False,
              allows_adding_options: bool = False,
              allows_revoting: bool = False,
              open_period: int | None = None,
              explanation: str | None = None) -> tuple[int, str] | None:
    """Send a native Telegram poll. Returns (message_id, poll_id) or None."""
    payload: dict = {
        "chat_id": chat_id, "question": question,
        "options": [{"text": opt} for opt in options],
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
    }
    if allows_adding_options:
        payload["allows_adding_options"] = True  # pragma: no cover
    if allows_revoting:
        payload["allows_revoting"] = True  # pragma: no cover
    if open_period is not None:
        payload["open_period"] = open_period  # pragma: no cover
    if explanation:
        payload["explanation"] = explanation  # pragma: no cover
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    result = _post("sendPoll", payload, "send_poll")
    if not result:
        return None
    mid = result.get("message_id")
    from posting.bot_sent_registry import record_sent
    record_sent(mid)
    return (mid, result.get("poll", {}).get("id", ""))


def pin_message(chat_id: int, message_id: int,
                disable_notification: bool = True) -> bool:
    """Pin a message in a chat. Returns True on success."""
    return _post("pinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
        "disable_notification": disable_notification,
    }, "pin_message") is not None


def unpin_message(chat_id: int, message_id: int) -> bool:
    """Unpin a specific message the bot itself pinned. True on success.

    Thin delegate to ``posting.safe_delete.perform_guarded_unpin`` —
    that module owns the bot-sent-registry safety check (the bot only
    unpins IDs it sent, so a stale/crossed ID can never clear a GM's or
    player's manual pin) and the actual Telegram API call. See its
    docstring for the full contract.
    """
    from posting.safe_delete import perform_guarded_unpin
    return perform_guarded_unpin(chat_id, message_id, _post)


# NOTE: there is deliberately no `unpin_all_messages` helper. Telegram's
# `unpinAllChatMessages` is group-wide (it ignores `message_thread_id`),
# so calling it per-thread wiped GM pins the bot never created (4.51.3).
# Always unpin a specific id with `unpin_message` instead. If a genuine
# per-topic clear is ever needed, use `unpinAllForumTopicMessages` — but
# note even that removes GM pins within the topic.


def delete_message(chat_id: int, message_id: int) -> bool:
    """Delete a message that the bot itself sent.

    Thin delegate to ``posting.safe_delete.perform_guarded_delete`` —
    that module owns the bot-sent-registry safety check and the actual
    Telegram API call. See its docstring for the full contract.
    """
    from posting.safe_delete import perform_guarded_delete
    return perform_guarded_delete(chat_id, message_id, _post)
