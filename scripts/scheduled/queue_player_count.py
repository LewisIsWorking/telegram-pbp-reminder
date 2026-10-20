"""Player count tag for the GM queue's campaign lines (2026-10-20).

Lewis: *"Can we add campaign player counts to the GM queue?"* - so he can
see at a glance which campaigns are short of players when recruiting.

Every campaign line in the queue (body headers, Silent and Caught up rows)
gets one compact tag:

* ``👥 4/6 ⚠️`` - below the target
* ``👥 6/6``    - at the target
* ``👥 7/6``    - above it. More players is good, so no warning.
* ``👥 5``      - a campaign that never recruits (``recruit_tier`` None),
  which is not asking for anybody, so it gets no target to fall short of.

⭐ The target is always 6 (Lewis, 2026-10-20), the roster's ``_TARGET``.
Not ``effective_target``: that ladder moves the bar to 8 once every campaign
reaches 6, and Lewis wants the queue measured against 6 regardless.

The count is the one ``/roster`` uses: ``_active_players`` split by
``_split_active``, and only the NON-permanent players are measured against
the target (Lewis, 2026-05-12: perm players do not fill "out of 6" slots).
Permanent players appear as ``+2p`` so the number never hides a seat.

⚠️ Not part of the queue fingerprint. A count change is not a reason to
repost and notify; the next in-place refresh or repost shows it.
"""

from datetime import datetime

from commands.roster_members import _TARGET, _active_players, _split_active
from scheduled.recruit_focus import recruit_tier

QUEUE_TARGET = _TARGET


def player_count_tag(config: dict, state: dict, pair: dict | None,
                     now: datetime) -> str:
    """Return ``" 👥 4/6 ⚠️"`` (leading space) for a campaign, or ``""``."""
    if not pair or not pair.get("pbp_topic_ids"):
        return ""
    pid = str(pair["pbp_topic_ids"][0])
    non_perm, perm = _split_active(
        _active_players(pid, state, config, now=now), config)
    count = len(non_perm)
    perm_str = f" +{len(perm)}p" if perm else ""
    if recruit_tier(pair, config) is None:
        return f" 👥 {count}{perm_str}"
    warn = " ⚠️" if count < QUEUE_TARGET else ""
    return f" 👥 {count}/{QUEUE_TARGET}{perm_str}{warn}"


def pair_for_pid(config: dict, pid: str) -> dict | None:
    """The topic pair whose canonical topic is ``pid``."""
    return next((p for p in config.get("topic_pairs", [])
                 if p.get("pbp_topic_ids")
                 and str(p["pbp_topic_ids"][0]) == str(pid)), None)
