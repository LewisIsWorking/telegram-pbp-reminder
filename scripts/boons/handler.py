"""
Boon choice callback handler.

Handles Player of the Week boon selection via inline keyboard callbacks,
text command fallback (/chooseboon), auto-expiry, and boon storage.
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


def _store_boon(state: dict, pid: str, user_id: str, boon_text: str,
                campaign_name: str, now: datetime) -> None:
    """Persist a chosen boon in state and update potw_history."""
    boons = state.setdefault("player_boons", {}).setdefault(pid, {}).setdefault(user_id, [])
    _, week, _ = now.isocalendar()
    boons.append({
        "text": boon_text,
        "date": now.strftime("%Y-%m-%d"),
        "campaign": campaign_name,
        "week": f"W{week}",
    })
    # Backfill boon_chosen in most recent matching potw_history record
    for record in reversed(state.get("potw_history", [])):
        if record.get("user_id") == user_id and record.get("campaign_pid") == pid:  # pragma: no cover
            if record.get("boon_chosen") is None:  # pragma: no cover
                record["boon_chosen"] = boon_text  # pragma: no cover
            break  # pragma: no cover
    print(f"Stored boon for user {user_id} in {campaign_name}: {boon_text[:50]}")


def _resolve_boon(state: dict, topic_id: str, choice_idx: int, label: str,
                  now: datetime | None = None) -> tuple[str | None, dict | None]:
    """Resolve a boon choice. Returns (new_text, pending_entry) or (None, None)."""
    now = now or datetime.now(timezone.utc)
    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        return None, None  # pragma: no cover

    if choice_idx < 0 or choice_idx >= len(pending["boons"]):
        return None, None

    new_text = _format_boon_result(pending["boons"], choice_idx, pending["base_message"], label)

    # Store the chosen boon
    campaign_name = pending.get("campaign_name", "Unknown")
    _store_boon(state, topic_id, pending["winner_user_id"],
                pending["boons"][choice_idx], campaign_name, now)

    return new_text, pending


def process_boon_callback(cb: dict, config: dict, state: dict) -> None:
    """Handle a player clicking a boon choice button.

    Note: answer_callback will always fail with hourly cron (Telegram
    requires a response within ~10s). We skip it and send a confirmation
    message instead, which the user sees on the next cron run.
    """
    cb_data = cb.get("data", "")
    from_user = cb.get("from", {})
    user_id = str(from_user.get("id", ""))
    msg = cb.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")
    thread_id = msg.get("message_thread_id")

    if not cb_data.startswith("boon:"):
        return  # pragma: no cover

    parts = cb_data.split(":")
    if len(parts) != 3:
        return  # pragma: no cover

    topic_id = parts[1]
    try:
        choice_idx = int(parts[2])
    except ValueError:  # pragma: no cover
        return  # pragma: no cover

    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        return  # pragma: no cover

    if user_id != pending["winner_user_id"]:
        return

    new_text, _ = _resolve_boon(state, topic_id, choice_idx, "Chosen boon")
    if not new_text:
        return  # pragma: no cover

    # Edit original message: update text and remove inline buttons
    tg.edit_message(chat_id, message_id, new_text,
                    parse_mode="HTML", remove_keyboard=True)

    # Send confirmation to bot topic
    chosen = pending["boons"][choice_idx]
    user_name = from_user.get("first_name", "Winner")
    campaign = pending.get("campaign_name", "Unknown")
    bot_topic = config.get("bot_topic_id")
    confirm_tid = bot_topic or thread_id or int(topic_id)
    tg.send_message(config["group_id"], confirm_tid,
                    f"\u2705 {user_name} chose boon #{choice_idx + 1} for {campaign}: {chosen}")

    del state["pending_potw_boons"][topic_id]
    print(f"POTW boon chosen via button for topic {topic_id}: #{choice_idx + 1}")


def choose_boon_by_text(pid: str, user_id: str, choice_num: int,
                        config: dict, state: dict) -> str:
    """Handle /chooseboon N command. Returns response message.

    Looks up pending boon by pid first, then falls back to searching by
    winner_user_id — handles the case where the command is typed in a
    chat topic rather than the PBP topic the boon was issued from.
    """
    all_pending = state.get("pending_potw_boons", {})
    pending = all_pending.get(pid)
    actual_pid = pid
    if not pending:
        # Fallback: find by winner_user_id (command typed in chat topic)
        for p_pid, p_data in all_pending.items():
            if p_data.get("winner_user_id") == user_id:
                pending = p_data
                actual_pid = p_pid
                break
    if not pending:
        return "No pending boon choice for this campaign."

    if user_id != pending["winner_user_id"]:
        return "Only the Player of the Week can choose!"

    choice_idx = choice_num - 1  # User gives 1-based
    if choice_idx < 0 or choice_idx >= len(pending["boons"]):
        return f"Pick a number between 1 and {len(pending['boons'])}."

    group_id = config["group_id"]
    new_text, _ = _resolve_boon(state, actual_pid, choice_idx, "Chosen boon")
    if not new_text:
        return "Something went wrong."

    # Update the original button message
    tg.edit_message(group_id, pending["message_id"], new_text,
                    parse_mode="HTML", remove_keyboard=True)

    chosen = pending["boons"][choice_idx]
    campaign = pending.get("campaign_name", "Unknown")
    del state["pending_potw_boons"][actual_pid]

    # Notify bot topic
    bot_topic = config.get("bot_topic_id")
    if bot_topic:
        winner_name = ""
        for key, p in state.get("players", {}).items():
            if p.get("user_id") == user_id:
                winner_name = p["first_name"]
                break
        tg.send_message(group_id, bot_topic,
                        f"\u2705 {winner_name or 'Winner'} chose boon #{choice_num} for {campaign}: {chosen}")

    print(f"POTW boon chosen via text for topic {pid}: #{choice_num}")
    return f"✅ Boon chosen: {chosen}"


def expire_pending_boons(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Delegate to boons.reminders for reminders + expiry."""
    from boons.reminders import check_boon_reminders
    check_boon_reminders(config, state, now=now)

