"""Silent and caught-up campaign sections for the GM queue.

A campaign with zero unreplied entries is one of:
  - **never posted**: the bot has seen no message in it at all, or
  - **silent**:       its RP topics have had no messages for >= 5 days, or
  - **caught up**:    it posted within the last 5 days (the GM is on top of it).

Campaigns with unreplied entries appear in the main queue body instead; the
sections here account for everything else so no campaign silently vanishes
from the queue (players were confused when caught-up campaigns disappeared).

⭐ Never-posted campaigns were dropped entirely until 2026-08-30. See
``queue_silence_rows`` for that bug and why they now rank first. Row
building, wording and the threshold live there; this module is only the
four section builders.
"""

from datetime import datetime

from scheduled.queue_silence_rows import (SILENCE_THRESHOLD_DAYS, callout_phrase,
                                          idle_campaigns, phrase)

_SILENCE_THRESHOLD_DAYS = SILENCE_THRESHOLD_DAYS


def _line(row) -> str:
    """Render one row as a queue line."""
    return f"  {row.icon} {row.prefix}{row.label} — {phrase(row)}{row.link}"


def _sorted_lines(rows) -> list[str]:
    """Longest-idle first, then rendered.

    Sorted rather than emitted in config ``topic_pairs`` order, which is why
    a section could once read 21h, 0h, 2h, 5h, 4d 2h, 1h (reported
    2026-08-10). ``days`` is a float, so sub-day ages order correctly against
    each other, and ``inf`` puts a never-posted campaign at the top with no
    special case.
    """
    return [_line(row) for row in sorted(rows, key=lambda r: r.days, reverse=True)]


def silent_campaigns(config: dict, state: dict,
                     scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns idle >= the silence threshold.

    A campaign with no posts at all belongs here rather than under "Caught
    up": nothing about it is caught up. ``days=inf`` satisfies the same
    comparison the threshold already used, so it needs no extra clause.

    Longest-silent first. Each line is ready to append directly to the GM
    queue message.
    """
    return _sorted_lines([r for r in idle_campaigns(config, state, scanned, now)
                          if r.days >= _SILENCE_THRESHOLD_DAYS])


def caught_up_campaigns(config: dict, state: dict,
                        scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns with no unreplied entries that
    posted within the silence threshold (GM is on top of them).

    Ensures every configured campaign is represented somewhere in the queue
    rather than vanishing when it is both caught up and recently active.
    """
    return _sorted_lines([r for r in idle_campaigns(config, state, scanned, now)
                          if r.days < _SILENCE_THRESHOLD_DAYS])


def oldest_campaign_line(config: dict, state: dict,
                         scanned: dict, now: datetime) -> str | None:
    """Return a 'go here next' callout naming the longest-idle campaign.

    The GM queue ends with a "Reply to this next" focus message, but that
    is built from unreplied entries, so when the queue is empty there is
    nothing pointing anywhere. This is the empty-queue equivalent: with no
    one waiting on a reply, the most useful next action is the campaign
    that has gone longest without any post at all.

    Ranking is simply "longest since last post", so a silent campaign
    naturally outranks a caught-up one without needing a separate rule.
    9d beats 21h because it is a bigger number, not because of its
    section. A campaign with no posts at all outranks both, for the same
    reason and by the same comparison. Returns None when the config has
    no eligible campaigns.
    """
    rows = idle_campaigns(config, state, scanned, now)
    if not rows:
        return None
    row = max(rows, key=lambda r: r.days)
    return (f"🕰️ Oldest campaign: {row.icon} {row.prefix}{row.label} — "
            f"{callout_phrase(row)}."
            f"\nNothing is waiting on a reply, so this is the one that "
            f"most needs you.{row.link}")


def campaign_age_lines(config: dict, state: dict,
                       scanned: dict, now: datetime) -> list[str]:
    """Return one line per campaign with no unreplied entries, longest idle first.

    Used by the "All caught up!" notification so a cleared queue still shows
    how long each campaign has been quiet. Wording matches the in-queue
    sections, via the same ``phrase``.
    """
    return _sorted_lines(idle_campaigns(config, state, scanned, now))
