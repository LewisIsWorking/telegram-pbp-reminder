"""
Boon choice callback handler.

Handles Player of the Week boon selection via inline keyboard callbacks
and auto-expires unclaimed boons after 48 hours.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from helpers import html_escape


def _format_boon_result(boons: list[str], chosen_idx: int, base_message: str, label: str) -> str:
    """Format POTW boon result message with chosen boon highlighted in HTML."""
    boon_lines = ""
    for i, b in enumerate(boons):
        escaped = html_escape(b)
        if i == chosen_idx:
            boon_lines += f"\n{i + 1}. {escaped} ✓\n"
        else:
            boon_lines += f"\n<s>{i + 1}. {escaped}</s>\n"
    return f"{html_escape(base_message)}\n\n{label}:{boon_lines}"


def process_boon_callback(cb: dict, config: dict, state: dict) -> None:
    """Handle a player clicking a boon choice button."""
    cb_id = cb.get("id", "")
    cb_data = cb.get("data", "")
    from_user = cb.get("from", {})
    user_id = str(from_user.get("id", ""))
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if not cb_data.startswith("boon:"):
        return

    # Parse: boon:<topic_id>:<choice_index>
    parts = cb_data.split(":")
    if len(parts) != 3:
        tg.answer_callback(cb_id, "Invalid choice.")
        return

    topic_id = parts[1]
    try:
        choice_idx = int(parts[2])
    except ValueError:
        tg.answer_callback(cb_id, "Invalid choice.")
        return

    # Check pending choices
    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        tg.answer_callback(cb_id, "This choice has expired.")
        return

    # Only the winner can choose
    if user_id != pending["winner_user_id"]:
        tg.answer_callback(cb_id, "Only the Player of the Week can choose!")
        return

    if choice_idx < 0 or choice_idx >= len(pending["boons"]):
        tg.answer_callback(cb_id, "Invalid choice.")
        return

    new_text = _format_boon_result(pending["boons"], choice_idx, pending["base_message"], "Chosen boon")

    tg.edit_message(chat_id, message_id, new_text, parse_mode="HTML")
    tg.answer_callback(cb_id, f"You chose boon #{choice_idx + 1}!")

    # Clean up pending state
    del state["pending_potw_boons"][topic_id]
    print(f"POTW boon chosen for topic {topic_id}: #{choice_idx + 1}")


def expire_pending_boons(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Auto-pick boon #1 if winner hasn't chosen within 48 hours."""
    now = now or datetime.now(timezone.utc)
    group_id = config["group_id"]
    pending = state.get("pending_potw_boons", {})

    for topic_id in list(pending.keys()):
        entry = pending[topic_id]
        posted_at = datetime.fromisoformat(entry["posted_at"])
        elapsed = helpers.hours_since(now, posted_at)

        if elapsed >= 48:
            new_text = _format_boon_result(entry["boons"], 0, entry["base_message"], "Boon (auto-selected)")

            tg.edit_message(group_id, entry["message_id"], new_text, parse_mode="HTML")
            del pending[topic_id]
            print(f"POTW boon auto-expired for topic {topic_id}, picked #1")
