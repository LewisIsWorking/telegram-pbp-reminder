"""/heropoint command — typed fallback for the MVP Hero Point claim.

The weekly leaderboard MVP earns one Hero Point to spend in a campaign of
their choice. Normally they tap a campaign button under the leaderboard
(boons/hero_point.py), but that button is a Telegram callback that only
resolves on the next hourly cron run — players read it as "the button does
nothing". This command is the typed equivalent: ``/heropoint <campaign>``.

Both routes share the ``pending_hero_points`` state entry, so claiming by
button or by command clears the same key and a player cannot double-claim.
The picker created that entry keyed by the winner's user_id; only that user
has a pending entry, which is what gates the claim here.
"""

import telegram as tg


def winner_campaigns(user_id: str, config: dict, state: dict) -> list[tuple[str, str, str]]:
    """Campaigns the winner is active in, as (pid, name, code), sorted by name.

    Mirrors the campaign selection in boons/hero_point.post_hero_point_picker
    so the typed command offers exactly the same choices as the buttons.
    """
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for p in state.get("players", {}).values():
        if p.get("user_id") == user_id and not p.get("removed"):
            pid = str(p.get("pbp_topic_id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                pair = next((pr for pr in config.get("topic_pairs", [])
                             if str(pr["pbp_topic_ids"][0]) == pid), None)
                if pair:
                    out.append((pid, pair.get("name", pid), pair.get("code", "")))
    return sorted(out, key=lambda c: c[1])


def _match(arg: str, campaigns: list[tuple[str, str, str]]) -> tuple[str, str, str] | None:
    """Resolve a typed campaign arg (code or name) to one of the winner's campaigns."""
    key = arg.strip().lower()
    if not key:
        return None
    # Exact code or name match first, then prefix/substring on the name.
    for pid, name, code in campaigns:
        if key == code.lower() or key == name.lower():
            return (pid, name, code)
    for pid, name, code in campaigns:
        if name.lower().startswith(key) or key in name.lower():
            return (pid, name, code)
    return None


def _prompt_options(name: str, campaigns: list[tuple[str, str, str]],
                    group_id: int, reply_topic: int) -> None:
    opts = ", ".join(f"{code} {nm}".strip() if code else nm
                     for _, nm, code in campaigns)
    tg.send_message(group_id, reply_topic,
                    f"🎲 {name}, which campaign gets your Hero Point?\n"
                    f"Reply: /heropoint <campaign>\n\nYour campaigns: {opts}")


def claim_or_prompt(user_id: str, user_name: str | None, arg: str,
                    target_pid, config: dict, state: dict,
                    group_id: int, reply_topic: int) -> None:
    """Shared core for both the in-topic handler and the bot-topic branch.

    Claims the Hero Point if a campaign is resolvable (from ``arg`` or, in a
    campaign topic, the ``target_pid`` they posted in); otherwise prompts with
    the list of eligible campaigns. No-ops with a friendly note if the caller
    has no pending Hero Point.
    """
    pending = state.get("pending_hero_points", {}).get(user_id)
    if not pending:
        tg.send_message(group_id, reply_topic,
                        "You don't have a Hero Point to claim right now — "
                        "the weekly leaderboard MVP earns one. 🏆")
        return

    name = pending.get("name") or user_name or "Winner"
    campaigns = winner_campaigns(user_id, config, state)
    if not campaigns:  # pragma: no cover
        tg.send_message(group_id, reply_topic,
                        f"{name}, you have a Hero Point but no active "
                        f"campaign to spend it in.")
        return

    target = None
    if arg:
        target = _match(arg, campaigns)
    elif target_pid:
        target = next((c for c in campaigns if c[0] == str(target_pid)), None)

    if not target:
        _prompt_options(name, campaigns, group_id, reply_topic)
        return

    pid, campaign, _code = target
    tg.send_message(group_id, reply_topic,
                    f"🎲 {name} claimed their Hero Point for {campaign}!")
    bot_topic = config.get("bot_topic_id")
    if bot_topic and bot_topic != reply_topic:
        tg.send_message(config["group_id"], bot_topic,
                        f"✅ +1 Hero Point for {campaign} — {name}")
    state.get("pending_hero_points", {}).pop(user_id, None)
    print(f"Hero Point claimed by {name} for {campaign} (via /heropoint)")


def handle(ctx: dict) -> bool:
    """Handle /heropoint typed in a campaign topic (registered in _HANDLERS)."""
    text = ctx["text"]
    if text != "/heropoint" and not text.startswith("/heropoint "):
        return False
    arg = text[len("/heropoint"):].strip()
    reply_topic = ctx.get("reply_topic") or ctx.get("thread_id")
    claim_or_prompt(ctx["user_id"], ctx.get("user_name"), arg,
                    ctx.get("pid"), ctx["config"], ctx["state"],
                    ctx["group_id"], reply_topic)
    return True


def handle_bot_topic(args: str, user_id: str, user_name: str,
                     config: dict, state: dict,
                     group_id: int, bot_topic: int) -> None:
    """Handle /heropoint from the bot topic (campaign resolved from the arg)."""
    claim_or_prompt(user_id, user_name, args.strip(), None,
                    config, state, group_id, bot_topic)
