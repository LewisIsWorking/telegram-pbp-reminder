"""Silent campaigns in the GM queue body, ranked by age with the rest.

Lewis, 2026-11-19: "silent campaigns should be in the chronological queue but
they aren't currently, please add them in as equal priority to wait for reply
campaigns."

Until then a silent campaign (no message in any of its RP topics for
``SILENCE_THRESHOLD_DAYS`` or more, see ``queue_silence_rows``) was listed in
its own "💤 Silent campaigns" section under the body, so it never took a place
in the age order the GM works through. It now has one, in the body itself.

**Its age.** A campaign owed a reply sorts by the timestamp of its oldest
unreplied post. A silent campaign sorts by the timestamp of its last post, the
same clock ``silent_rows`` and the focus pick already read: the moment the
campaign stopped moving. So a campaign silent for 6 days sits above a post
that has waited 4 days and below one that has waited 8.

**Priority.** Same rule as a waiting campaign: ``queue_priority`` rank first,
then age. A prioritised silent campaign therefore jumps the queue exactly as a
prioritised campaign with an owed reply does.

**Never posted.** A campaign with no recorded post has no age to compare, so
it goes last in its rank tier rather than first: at ``days=inf`` it would sit
on top of the queue forever. The focus pick excludes it for the same reason.

**Ties.** An owed reply goes before a silent campaign with the same rank and
the same timestamp, as in the focus pick.

The silent section is gone rather than duplicated. ``silent_rows`` and the
fingerprint ids are unchanged, so a campaign going silent still reposts the
queue exactly as before. Silent sections carry no numbered entries, so
``/markdone N`` numbering is untouched.
"""

from datetime import datetime, timedelta

from commands.queue_format import NO_PRIORITY
from scheduled.queue_silence_rows import phrase

# Sorts after every real "%Y-%m-%d %H:%M:%S" timestamp and after the "9999"
# a timeless entry gets, so a never-posted campaign is last in its tier.
_NO_AGE = "~"


def silent_since(row, now: datetime) -> str:
    """The silent campaign's last post, in the scanner's timestamp format."""
    if not row.ever_posted:
        return _NO_AGE
    return (now - timedelta(days=row.days)).strftime("%Y-%m-%d %H:%M:%S")


def queue_order(scanned: dict, rows: list, priority_map: dict,
                now: datetime) -> list[str]:
    """Pids of every body section, waiting and silent, in queue order."""
    keyed = []
    for pid, data in scanned.items():
        entries = data.get("entries") or []
        if not entries:
            continue
        oldest = min(e.get("time", "9999") for e in entries)
        keyed.append(((priority_map.get(pid, NO_PRIORITY), oldest, 0), pid))
    for row in rows:
        keyed.append(((priority_map.get(row.pid, NO_PRIORITY),
                       silent_since(row, now), 1), row.pid))
    return [pid for _key, pid in sorted(keyed, key=lambda k: k[0])]


def silent_section_lines(row, pin: str, gm: str) -> list[str]:
    """One silent campaign as a body section: a header and one status line.

    Shaped like a waiting campaign's section so it reads as part of the same
    list. No entry number, because there is no post to ``/markdone``.
    """
    return [f"━━ {pin}💤 {row.prefix}{row.label} (silent){row.players} ━━ {gm}",
            f"  {row.icon} {phrase(row)}{row.link}"]
