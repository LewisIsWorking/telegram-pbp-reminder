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
    return f"  {row.icon} {row.prefix}{row.label} - {phrase(row)}{row.link}"


def _sorted_lines(rows) -> list[str]:
    """Longest-idle first, then rendered.

    Sorted rather than emitted in config ``topic_pairs`` order, which is why
    a section could once read 21h, 0h, 2h, 5h, 4d 2h, 1h (reported
    2026-08-10). ``days`` is a float, so sub-day ages order correctly against
    each other, and ``inf`` puts a never-posted campaign at the top with no
    special case.
    """
    return [_line(row) for row in sorted(rows, key=lambda r: r.days, reverse=True)]


def silent_rows(config: dict, state: dict,
                scanned: dict, now: datetime) -> list:
    """The campaigns idle >= the silence threshold, as rows.

    ⭐ The ONE filter. The queue needs two views of silence, the lines it
    shows and the ids it fingerprints, and both are derived from this single
    list so they cannot disagree. They were briefly two independent calls on
    2026-09-13, and a test that stubbed only the lines exposed it at once: the
    lines said "no silent campaigns" while the ids still found one.

    A campaign with no posts at all belongs here rather than under "Caught
    up": nothing about it is caught up. ``days=inf`` satisfies the same
    comparison the threshold already used, so it needs no extra clause.
    """
    return [r for r in idle_campaigns(config, state, scanned, now)
            if r.days >= _SILENCE_THRESHOLD_DAYS]


def silent_lines_for(rows: list) -> list[str]:
    """Render silent rows as queue lines, longest-silent first."""
    return _sorted_lines(rows)


def silent_ids(rows: list) -> list[str]:
    """WHICH campaigns are silent, for the queue's change fingerprint.

    ⛔⛔ Not the rendered lines. Until 2026-09-13 the fingerprint appended the
    rendered lines, and every line carries its age ("no posts for 13d 20h").
    The age ticks every hour, so the fingerprint changed every hour, so the
    queue reposted every hour whether or not anything in it had changed.
    Measured from state history: **12 of 13 consecutive reposts were nothing
    but an age ticking**, one was a real change.

    The caught-up section had already been kept out of the fingerprint for
    exactly this reason. The silent section got the same ticking text and
    was not.

    A campaign entering or leaving the silent list IS a queue change, so the
    set of ids is kept. Its age and its icon band are presentation, refreshed
    by the next real change or the next daily slot, so never more than about
    twelve hours stale.

    ⚠️ Sorted because ``idle_campaigns`` walks ``topic_pairs`` in config
    order. That is stable run to run, but reordering campaigns in config.json
    would otherwise read as a change and repost for nothing.
    """
    return sorted(r.pid for r in rows)


def silent_campaigns(config: dict, state: dict,
                     scanned: dict, now: datetime) -> list[str]:
    """Return formatted lines for campaigns idle >= the silence threshold.

    Longest-silent first. Each line is ready to append directly to the GM
    queue message. Kept for callers that want only the lines; the queue
    itself uses ``silent_rows`` so its lines and fingerprint share one list.
    """
    return silent_lines_for(silent_rows(config, state, scanned, now))


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
    return (f"🕰️ Oldest campaign: {row.icon} {row.prefix}{row.label} - "
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
