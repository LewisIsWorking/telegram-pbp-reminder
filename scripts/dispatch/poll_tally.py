"""
Poll vote tally formatting helpers.

Extracted from poll_notify.py to keep that module under 200 lines.
Builds rich multi-line tally blocks showing per-option voter names,
voting progress, and the waiting list for each campaign.
"""


def _uid_mention(uid: str, config: dict, state: dict) -> str:
    """Return @username or first name for a voter UID."""
    for p in state.get("players", {}).values():
        if str(p.get("user_id", "")) == uid:  # pragma: no cover
            u = p.get("username", "")  # pragma: no cover
            if u:  # pragma: no cover
                return f"@{u}"  # pragma: no cover
            return p.get("first_name", uid)  # pragma: no cover
    for pair in config.get("topic_pairs", []):
        names = pair.get("poll_user_names", {})
        if uid in names:
            return f"@{names[uid]}"
    return uid


def _lead_summary(votes: dict, options: list[str]) -> str:
    """Return '→ X leads', '→ X & Y tied', or '→ N-way tie'."""
    counts: dict[str, int] = {}
    for i, label in enumerate(options):
        count = len(votes.get(str(i), []))
        if count > 0:
            counts[label.split()[0]] = count
    if not counts:
        return ""
    max_votes = max(counts.values())
    leaders = [label for label, c in counts.items() if c == max_votes]
    if len(leaders) == 1:
        return f"→ {leaders[0]} leads"
    if len(leaders) == 2:
        return f"→ {leaders[0]} & {leaders[1]} tied"
    return f"→ {len(leaders)}-way tie"


def _waiting_for_code(code: str, config: dict, state: dict) -> list[str]:
    """Return @mention list of roster members who haven't voted yet."""
    pair = next((p for p in config.get("topic_pairs", [])
                 if p.get("code") == code), None)
    if not pair:
        return []
    voted = {str(u) for u in
             state.get("session_poll", {}).get(code, {}).get("voted_uids", [])}
    return [_uid_mention(str(u), config, state)
            for u in pair.get("poll_user_ids", [])
            if str(u) not in voted]


def build_tally_block(code: str, slot: dict, options: list[str],
                      config: dict, state: dict) -> str:
    """Build a multi-line campaign tally block.

    Example output:
      C01 — 2/3 voted  |  waiting: @MrNegetZ @DragonFox2000
        Friday:         1  @PathWars
        Either:         2  @Elinoa @Selenor
        → Either leads
    """
    votes = slot.get("votes", {})
    voted_uids = slot.get("voted_uids", [])

    pair = next((p for p in config.get("topic_pairs", [])
                 if p.get("code") == code), None)
    roster_uids = {str(u) for u in (pair.get("poll_user_ids", []) if pair else [])}
    roster_size = len(roster_uids) if roster_uids else "?"
    roster_voted = sum(1 for u in voted_uids if str(u) in roster_uids)

    waiting = _waiting_for_code(code, config, state)
    wait_str = f"  |  waiting: {' '.join(waiting)}" if waiting else ""
    header = f"{code} — {roster_voted}/{roster_size} voted{wait_str}"

    lines = [header]
    for i, label in enumerate(options):
        uids = votes.get(str(i), [])
        if not uids:
            continue
        names = "  ".join(_uid_mention(u, config, state) for u in uids)
        short = label[:25]
        lines.append(f"  {short}: {len(uids)}  {names}")

    lead = _lead_summary(votes, options)
    if lead:
        lines.append(f"  {lead}")

    return "\n".join(lines)
