"""Telegram Bot API helpers."""

import json
import requests

TELEGRAM_API = ""


def init(token: str) -> None:
    """Set the API base URL from bot token."""
    global TELEGRAM_API
    TELEGRAM_API = f"https://api.telegram.org/bot{token}"


def _post(method: str, payload: dict, label: str = "request") -> dict | None:
    """POST to Telegram API, return parsed result on success or None on failure."""
    try:
        resp = requests.post(f"{TELEGRAM_API}/{method}", json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data.get("result")
        print(f"Telegram {label} failed: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"Telegram {label} network error: {e}")
    return None


def get_updates(offset: int) -> list:
    """Fetch new messages and callbacks from Telegram Bot API."""
    try:
        resp = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={
                "offset": offset,
                "limit": 100,
                "timeout": 5,
                "allowed_updates": json.dumps(["message", "callback_query", "message_reaction", "poll_answer"]),
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"Error fetching updates: {e}")
        return []

    if resp.status_code != 200:
        print(f"Error fetching updates: HTTP {resp.status_code}")
        return []

    try:
        data = resp.json()
    except ValueError:
        print(f"Error parsing updates response: {resp.text[:200]}")
        return []

    if not data.get("ok"):
        print(f"Telegram API error: {data}")
        return []

    return data.get("result", [])


def send_message(chat_id: int, thread_id: int | None, text: str,
                 parse_mode: str | None = None) -> bool:
    """Send a text message. If thread_id is None, sends to main chat."""
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "disable_notification": False,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if parse_mode:
        payload["parse_mode"] = parse_mode
    result = _post("sendMessage", payload, "send_message")
    return result is not None


def send_message_with_buttons(
    chat_id: int, thread_id: int, text: str, buttons: list
) -> int | None:
    """Send a message with inline keyboard buttons. Returns message_id or None."""
    result = _post("sendMessage", {
        "chat_id": chat_id,
        "message_thread_id": thread_id,
        "text": text,
        "disable_notification": False,
        "reply_markup": {"inline_keyboard": [buttons]},
    }, "send_button_message")
    return result["message_id"] if result else None


def edit_message(chat_id: int, message_id: int, text: str,
                 parse_mode: str = None, remove_keyboard: bool = False) -> bool:
    """Edit an existing message. Optionally remove inline keyboard."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if remove_keyboard:
        payload["reply_markup"] = {"inline_keyboard": []}
    return _post("editMessageText", payload, "edit_message") is not None


def answer_callback(callback_id: str, text: str = "") -> bool:
    """Answer a callback query to dismiss the loading spinner."""
    return _post("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
    }, "answer_callback") is not None


def send_poll(chat_id: int, thread_id: int | None, question: str,
              options: list[str], is_anonymous: bool = False,
              allows_multiple_answers: bool = False) -> tuple[int, str] | None:
    """Send a native Telegram poll. Returns (message_id, poll_id) or None."""
    poll_options = [{"text": opt} for opt in options]
    payload: dict = {
        "chat_id": chat_id,
        "question": question,
        "options": poll_options,
        "is_anonymous": is_anonymous,
        "allows_multiple_answers": allows_multiple_answers,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    result = _post("sendPoll", payload, "send_poll")
    if result:
        msg_id = result.get("message_id")
        poll_id = result.get("poll", {}).get("id", "")
        return (msg_id, poll_id)
    return None


def pin_message(chat_id: int, message_id: int,
                disable_notification: bool = True) -> bool:
    """Pin a message in a chat. Returns True on success."""
    return _post("pinChatMessage", {
        "chat_id": chat_id,
        "message_id": message_id,
        "disable_notification": disable_notification,
    }, "pin_message") is not None


def message_link(group_id: int, topic_id: int, message_id: int,
                 group_username: str | None = None) -> str:
    """Build a t.me deep link to a specific message.

    Uses username form (t.me/GroupName/topic/msg) for public groups,
    or private form (t.me/c/groupdigits/msg) for private groups.
    """
    if group_username:
        return f"https://t.me/{group_username}/{topic_id}/{message_id}"
    # Private group: strip leading -100 from group_id
    digits = str(abs(group_id))
    if digits.startswith("100"):
        digits = digits[3:]
    return f"https://t.me/c/{digits}/{message_id}"
