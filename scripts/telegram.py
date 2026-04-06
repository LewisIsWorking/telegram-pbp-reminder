"""Telegram Bot API helpers."""

import time
import requests
from telegram_utils import fetch_updates, message_link  # noqa: F401 — re-exported

TELEGRAM_API = ""


def init(token: str) -> None:
    """Set the API base URL from bot token."""
    global TELEGRAM_API
    TELEGRAM_API = f"https://api.telegram.org/bot{token}"


def _post(method: str, payload: dict, label: str = "request") -> dict | None:
    """POST to Telegram API. Retries once on HTTP 429."""
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
            print(f"Telegram {label} failed: {resp.text[:500]}")
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
    """Send a text message and return the message_id, or None on failure."""
    payload: dict = {"chat_id": chat_id, "text": text, "disable_notification": False}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    result = _post("sendMessage", payload, "send_message")
    return result.get("message_id") if result else None


def send_message_with_buttons(
    chat_id: int, thread_id: int, text: str, buttons: list
) -> int | None:
    """Send a message with inline keyboard buttons. Returns message_id or None."""
    result = _post("sendMessage", {
        "chat_id": chat_id, "message_thread_id": thread_id, "text": text,
        "disable_notification": False, "reply_markup": {"inline_keyboard": [buttons]},
    }, "send_button_message")
    return result["message_id"] if result else None


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
    if result:
        return (result.get("message_id"), result.get("poll", {}).get("id", ""))
    return None


def pin_message(chat_id: int, message_id: int,
                disable_notification: bool = True) -> bool:
    """Pin a message in a chat. Returns True on success."""
    return _post("pinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
        "disable_notification": disable_notification,
    }, "pin_message") is not None


def unpin_message(chat_id: int, message_id: int) -> bool:
    """Unpin a specific message in a chat. Returns True on success."""
    return _post("unpinChatMessage", {
        "chat_id": chat_id, "message_id": message_id,
    }, "unpin_message") is not None
