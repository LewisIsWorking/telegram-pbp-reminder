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
    """Persist a chosen boon in state for later retrieval."""
    boons = state.setdefault("player_boons", {}).setdefault(pid, {}).setdefault(user_id, [])
    _, week, _ = now.isocalendar()
    boons.append({
        "text": boon_text,
        "date": now.strftime("%Y-%m-%d"),
        "campaign": campaign_name,
        "week": f"W{week}",
    })
    print(f"Stored boon for user {user_id} in {campaign_name}: {boon_text[:50]}")


def _resolve_boon(state: dict, topic_id: str, choice_idx: int, label: str,
                  now: datetime | None = None) -> tuple[str | None, dict | None]:
    """Resolve a boon choice. Returns (new_text, pending_entry) or (None, None)."""
    now = now or datetime.now(timezone.utc)
    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        return None, None

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
        return

    parts = cb_data.split(":")
    if len(parts) != 3:
        return

    topic_id = parts[1]
    try:
        choice_idx = int(parts[2])
    except ValueError:
        return

    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        return

    if user_id != pending["winner_user_id"]:
        return

    new_text, _ = _resolve_boon(state, topic_id, choice_idx, "Chosen boon")
    if not new_text:
        return

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
    """Handle /chooseboon N command. Returns response message."""
    pending = state.get("pending_potw_boons", {}).get(pid)
    if not pending:
        return "No pending boon choice for this campaign."

    if user_id != pending["winner_user_id"]:
        return "Only the Player of the Week can choose!"

    choice_idx = choice_num - 1  # User gives 1-based
    if choice_idx < 0 or choice_idx >= len(pending["boons"]):
        return f"Pick a number between 1 and {len(pending['boons'])}."

    group_id = config["group_id"]
    new_text, _ = _resolve_boon(state, pid, choice_idx, "Chosen boon")
    if not new_text:
        return "Something went wrong."

    # Update the original button message
    tg.edit_message(group_id, pending["message_id"], new_text,
                    parse_mode="HTML", remove_keyboard=True)

    chosen = pending["boons"][choice_idx]
    campaign = pending.get("campaign_name", "Unknown")
    del state["pending_potw_boons"][pid]

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


def build_boons(pid: str, user_id: str, campaign_name: str, state: dict) -> str:
    """Build /boons output: current player's boons in this campaign."""
    boons = state.get("player_boons", {}).get(pid, {}).get(user_id, [])
    if not boons:
        return f"No boons held in {campaign_name}."

    lines = [f"🎁 Your boons in {campaign_name}:\n"]
    for i, b in enumerate(boons, 1):
        lines.append(f"{i}. {b['text']}")
        lines.append(f"   Earned: {b['date']} ({b.get('week', '?')})")
    return "\n".join(lines)


def build_boons_all(user_id: str, state: dict) -> str:
    """Build /boonsall output: all boons for this player across all campaigns."""
    all_boons = state.get("player_boons", {})
    found = []
    for pid, users in all_boons.items():
        for b in users.get(user_id, []):
            found.append(b)

    if not found:
        return "No boons held in any campaign."

    lines = ["🎁 All your boons:\n"]
    by_campaign = {}
    for b in found:
        by_campaign.setdefault(b["campaign"], []).append(b)

    for camp, boons in sorted(by_campaign.items()):
        lines.append(f"📜 {camp}:")
        for i, b in enumerate(boons, 1):
            lines.append(f"  {i}. {b['text']}  ({b['date']})")
        lines.append("")
    return "\n".join(lines).rstrip()
