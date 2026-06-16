"""
Boon resolution helpers.

Pure logic for turning a Player-of-the-Week boon *choice* into a
formatted result message and a persisted state record: result
formatting, campaign-name resolution, storage, and the combined
``_resolve_boon`` entry point. The callback/text handlers in
``boons.handler`` orchestrate Telegram I/O around these.

Extracted from ``boons/handler.py`` in v4.x to keep both modules under
the 200-line limit. ``boons.handler`` re-exports these names, so
existing ``boons.handler._resolve_boon`` / ``compat`` imports and test
patch targets continue to resolve unchanged.
"""

from datetime import datetime, timezone

from helpers import html_escape
from helpers_pkg import campaigns


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


def _resolve_campaign_name(pending: dict, config: dict, topic_id: str) -> str:
    """Resolve the campaign display name for a boon write or confirmation.

    Preference order:
      1. pending["campaign_name"] if set and not the legacy "Unknown" sentinel
      2. Live campaigns config (handles maps/config staleness during cron)
      3. topic_id itself — diagnosable in players.json, never the string "Unknown"

    Why this exists: older bot versions (pre-2026-05-21) had
    `name = maps.to_name.get(pid, "Unknown")` in potw.py and matching
    `pending.get("campaign_name", "Unknown")` reads here, which combined to
    persist the literal string "Unknown" as the boon's `campaign` field in
    players.json forever. The downstream COO PathWars UI then displays such
    boons as "some game" with no recoverable label. This helper guarantees
    "Unknown" never reaches state on the write path.
    """
    name = pending.get("campaign_name")
    if name and name != "Unknown":
        return name
    resolved = campaigns.try_get_name(config, topic_id)
    if resolved:
        return resolved
    # 🪪 Last resort — topic_id is at least diagnosable later, unlike "Unknown".
    print(f"[boons] WARNING: campaign for topic {topic_id} could not be resolved; "
          f"persisting topic_id as campaign label")
    return topic_id


def _resolve_boon(state: dict, topic_id: str, choice_idx: int, label: str,
                  config: dict, now: datetime | None = None) -> tuple[str | None, dict | None]:
    """Resolve a boon choice. Returns (new_text, pending_entry) or (None, None)."""
    now = now or datetime.now(timezone.utc)
    pending = state.get("pending_potw_boons", {}).get(topic_id)
    if not pending:
        return None, None  # pragma: no cover

    if choice_idx < 0 or choice_idx >= len(pending["boons"]):
        return None, None

    new_text = _format_boon_result(pending["boons"], choice_idx, pending["base_message"], label)

    # 🛡️ Resolve campaign name from config rather than passing through whatever
    # the pending entry happens to hold — see _resolve_campaign_name docstring.
    campaign_name = _resolve_campaign_name(pending, config, topic_id)
    _store_boon(state, topic_id, pending["winner_user_id"],
                pending["boons"][choice_idx], campaign_name, now)

    return new_text, pending
