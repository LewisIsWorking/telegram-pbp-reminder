"""Row building for the GM queue's silent / caught-up sections.

Extracted from ``scheduled/queue_silence.py`` on 2026-08-30, which had
reached 186 lines and could not absorb the never-posted case below. That
module keeps the four public section builders; everything here turns a
config pair plus state into one comparable row.

⭐ The never-posted case, 2026-08-30. Lewis, on C10 The Junction:
*"But it doesn't do the 'all caught up' and such messages, etc"*.

``_idle_campaigns`` used to read:

```python
if last_dt is None:
    continue  # never posted / untracked — neither silent nor caught up
```

so a campaign the bot had never seen a message in was dropped from the
Silent section, the Caught up section, ``campaign_age_lines`` and the
"oldest campaign" callout. C10 was configured on 2026-08-13 and appeared
in none of them until an empty GM post landed on 2026-08-30 12:07.

"Never posted" is not a third category beside silent and caught up. It is
the **most** silent a campaign can be, and the one a GM most needs
naming. It is now ranked first everywhere by giving it ``days = inf``,
which needs no special case in any caller's sort.

⛔ ``days`` is ``inf`` for these rows, so ``age`` is left empty: ``_age_str``
does ``int(hours)`` and would raise ``OverflowError``. Read the wording
through ``phrase()``, never by formatting ``age`` directly.
"""

from datetime import datetime
from typing import NamedTuple

import helpers
from commands.queue_format import entry_age_icon

# A campaign idle this long reads as "silent" rather than "caught up".
SILENCE_THRESHOLD_DAYS = 5


class IdleRow(NamedTuple):
    """One campaign with no unreplied entries.

    ``ever_posted`` is False when the bot holds no ``last_message_time``
    for any of the campaign's RP topics. Those rows carry ``days=inf``
    and an empty ``age``; ``phrase()`` is the only safe way to word them.

    A NamedTuple rather than the previous bare 8-tuple so that adding
    ``ever_posted`` broke every call site at the attribute level instead
    of silently shifting positional unpacking by one.
    """

    pair: dict
    pid: str
    days: float
    icon: str
    prefix: str
    label: str
    age: str
    link: str
    ever_posted: bool


def age_str(hours: float) -> str:
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


def phrase(row: IdleRow) -> str:
    """Return the wording for one row, e.g. 'no posts for 12d'.

    The single place that decides between the three forms, so a caller
    can never pair "no posts for" with a never-posted row's empty age and
    render 'no posts for '.
    """
    if not row.ever_posted:
        return "no posts yet"
    if row.days >= SILENCE_THRESHOLD_DAYS:
        return f"no posts for {row.age}"
    return f"last post {row.age} ago"


def callout_phrase(row: IdleRow) -> str:
    """Return the wording for the 'oldest campaign' callout.

    Differs from ``phrase`` in one form only: a recently-active campaign
    reads "quiet for 1d 3h" there rather than "last post 1d 3h ago",
    because the callout is a prompt to act rather than a status line.
    Kept byte-identical to the pre-2026-08-30 wording.
    """
    if not row.ever_posted:
        return "no posts yet"
    if row.days >= SILENCE_THRESHOLD_DAYS:
        return f"no posts for {row.age}"
    return f"quiet for {row.age}"


def latest_last_post(state: dict, pair: dict) -> datetime | None:
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


def topic_link(config: dict, pair: dict, pid: str) -> str:
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


def idle_campaigns(config: dict, state: dict,
                   scanned: dict, now: datetime) -> list[IdleRow]:
    """Return an ``IdleRow`` per campaign with no unreplied entries.

    Excludes only campaigns shown in the queue body (they have unreplied
    entries) and those carrying ``queue_exclude``. A campaign that has
    never been posted in is included with ``ever_posted=False``; see the
    module docstring for why that is not a skip.
    """
    rows = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        # Skip if the campaign has unreplied entries: it is in the body
        if pid in scanned and scanned[pid].get("entries"):
            continue
        if helpers.is_excluded(config, pid):
            continue
        last_dt = latest_last_post(state, pair)
        if last_dt is None:
            days, hours, age = float("inf"), float("inf"), ""
        else:
            days = (now - last_dt).total_seconds() / 86400
            hours = days * 24
            age = age_str(hours)
        code = pair.get("code", "")
        name = pair.get("name", pid)
        emoji = pair.get("emoji", "")
        rows.append(IdleRow(
            pair=pair,
            pid=pid,
            days=days,
            # entry_age_icon compares against inf without converting it,
            # so a never-posted campaign lands on the oldest icon (☠️).
            icon=entry_age_icon(hours),
            prefix=f"{emoji} " if emoji else "",
            label=f"{code}: {name}" if code else name,
            age=age,
            link=topic_link(config, pair, pid),
            ever_posted=last_dt is not None,
        ))
    return rows
