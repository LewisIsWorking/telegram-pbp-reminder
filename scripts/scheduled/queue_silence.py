"""Silent and caught-up campaign sections for the GM queue.

A campaign with zero unreplied entries is either:
  - **silent**    — its RP topics have had no messages for >= 5 days, or
  - **caught up** — it posted within the last 5 days (the GM is on top of it).

Campaigns with unreplied entries appear in the main queue body instead; the
two sections here account for everything else so no campaign silently vanishes
from the queue (players were confused when caught-up campaigns disappeared).
"""

from datetime import datetime

import helpers
from commands.queue_format import entry_age_icon

_SILENCE_THRESHOLD_DAYS = 5


def _age_str(hours: float) -> str:
    """Format an age as '12d', '9d 20h', or '5h'.

    Drops the hours part only when it is zero AND there is a days part, so
    silent lines stay byte-compatible with the previous formatter ('12d'),
    while sub-day caught-up lines read cleanly ('5h' rather than '0d 5h').
    """
    d, h = divmod(int(hours), 24)
    if d and h:
        return f"{d}d {h}h"
    if d:
        return f"{d}d"
    return f"{h}h"


def _latest_last_post(state: dict, pair: dict) -> datetime | None:
    """Most recent last_message_time across all of a campaign's RP topics.

    Multi-topic campaigns (e.g. C00 Riddleport) may be active in a secondary
    topic while the canonical one is quiet, so consider them all.
    """
    topics = state.get("topics", {})
    latest = None
    for tid in pair.get("pbp_topic_ids", []):
        ts = topics.get(str(tid), {}).get("last_message_time")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def _topic_link(config: dict, pair: dict, pid: str) -> str:
    """Build a ' 🔗 <url>' suffix to a campaign's canonical topic, group-aware.

    Uses ``campaign_link_target`` so cross-group campaigns (e.g. C11 Dark
    Pockets) resolve to their own group rather than inheriting the global
    ``group_username`` and pointing at the wrong group.
    """
    gid, guser = helpers.campaign_link_target(config, pair)
    if guser:
        return f" 🔗 https://t.me/{guser}/{pid}"
    if gid:
        digits = str(abs(gid))
        if digits.startswith("100"):
            digits = digits[3:]
        return f" 🔗 https://t.me/c/{digits}/{pid}"
    return ""


def _idle_campaigns(config: dict, state: dict, scanned: dict, now: datetime):
    """Yield ``(pair, pid, days, icon, prefix, label, age, link)`` for each
    campaign that has no unreplied entries and a known last-post time."""
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        # Skip if the campaign has unreplied entries — it is shown in the body
        if pid in scanned and scanned[pid].get("entries"):
            continue
        if helpers.is_excluded(config, pid):
            continue
        last_dt = _latest_last_post(state, pair)
        if last_dt is None:
            continue  # never posted / untracked — neither silent nor caught up
        days = (now - last_dt).total_seconds() / 86400
        hours = days * 24
        code = pair.get("code", "")
        name = pair.get("name", pid)
        emoji = pair.get("emoji", "")
        label = f"{code}: {name}" if code else name
        prefix = f"{emoji} " if emoji else ""
        icon = entry_age_icon(hours)
        age = _age_str(hours)
        link = _topic_link(config, pair, pid)
        yield pair, pid, days, icon, prefix, label, age, link


def silent_campaigns(config: dict, state: dict,
                     scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns idle >= the silence threshold.

    Each line is ready to append directly to the GM queue message.
    """
    lines = []
    for _pair, _pid, days, icon, prefix, label, age, link in \
            _idle_campaigns(config, state, scanned, now):
        if days < _SILENCE_THRESHOLD_DAYS:
            continue
        lines.append(f"  {icon} {prefix}{label} — no posts for {age}{link}")
    return lines


def caught_up_campaigns(config: dict, state: dict,
                        scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns with no unreplied entries that
    posted within the silence threshold (GM is on top of them).

    Ensures every configured campaign is represented somewhere in the queue
    rather than vanishing when it is both caught up and recently active.
    """
    lines = []
    for _pair, _pid, days, icon, prefix, label, age, link in \
            _idle_campaigns(config, state, scanned, now):
        if days >= _SILENCE_THRESHOLD_DAYS:
            continue
        lines.append(f"  {icon} {prefix}{label} — last post {age} ago{link}")
    return lines
