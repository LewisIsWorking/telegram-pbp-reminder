"""Post the community roster once a week, and leave it up.

Lewis, 2026-08-30: *"maybe once a week the bot could post the full
community roster in https://t.me/Path_Wars/146780"*.

Kept, not replaced
------------------
Unlike the recruit advert, this post **deletes nothing**. A weekly run of
these in one topic is a record of the community growing or shrinking, and
that history is the reason to have it at all: it is the artefact that
makes "are we actually growing" answerable next month without anybody
re-deriving it. Nothing here holds a message id, because nothing here
ever needs to find a previous post again.

Registration, which is where jobs silently die
----------------------------------------------
A scheduled job has to appear in three places or it fails quietly:

* ``checker._run_checks`` - or it never runs;
* ``schedule_intervals.INTERVAL_JOBS`` - or it runs but is missing from
  the schedule post, which is what happened to seven jobs until
  2026-08-13, and ``test_schedule_is_complete`` now fails for it;
* ``state_schema.PARTITIONS`` - or ``last_community_roster`` is discarded
  on every save, the gate never sees a previous run, and the post fires
  every single hour.

That third one is not hypothetical: it is the exact bug that duplicated
the schedule post for two days.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from scheduled.community_roster_build import build_community_roster

INTERVAL_DAYS = 7
_LAST_KEY = "last_community_roster"


def roster_destination(config: dict) -> int | None:
    """The topic this goes in: t.me/Path_Wars/146780 in the live config.

    Configurable ahead of the GM queue so the post can be moved without a
    code change, but it falls back rather than requiring new config: the
    three ids Lewis pointed at are all 146780 today.
    """
    return (config.get("community_roster_topic_id")
            or config.get("gm_queue_topic_id")
            or config.get("bot_topic_id"))


def post_community_roster(config: dict, state: dict, *,
                          now: datetime | None = None, **_kw) -> None:
    """Once every ``INTERVAL_DAYS``, name everybody in the community."""
    now = now or datetime.now(timezone.utc)
    if not config.get("community_roster_enabled", True):
        return
    if not helpers.interval_elapsed(state.get(_LAST_KEY), INTERVAL_DAYS, now):
        return

    thread_id = roster_destination(config)
    if not thread_id:
        print("[community_roster] no topic configured; nothing posted.")
        return

    text = build_community_roster(config, state, now)
    print(f"Community roster: {len(text)} chars to topic {thread_id}")
    # ⚠️ Stamp the run ONLY on a confirmed send. Stamping first would
    # swallow a failed post for a week, and a weekly job that silently
    # skips a week looks identical to a quiet week in the group.
    #
    # ⚠️ silent=True because this post @-mentions roughly 25 people by
    # design. A weekly mention each is useful; a weekly notification each
    # is what makes people mute the topic, and a muted topic is the one
    # place this record must not be.
    if tg.send_message_id(config["group_id"], thread_id, text, silent=True):
        state[_LAST_KEY] = now.isoformat()
