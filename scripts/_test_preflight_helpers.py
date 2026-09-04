"""Shared fixtures for the preflight diagnostic tests (2026-09-04).

Split out when ``test_the_debug_topic_gets_the_whole_story.py`` reached
322 lines. Three files now share these builders:

  test_the_debug_topic_gets_the_whole_story.py  what the report SAYS
  test_bot_alerts_reach_the_right_topic.py      where it GOES
  test_orphan_risk_warns_before_the_wall.py     the 48h delete wall

⭐ ``NOW`` is fixed rather than ``utcnow()``. Every assertion here is
about an age or a gap, and a moving clock turns those into flakes that
only appear when a run straddles the boundary.
"""

from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 9, 4, 15, 5, tzinfo=timezone.utc)

# The real run id from the 2026-09-04 incident these tests are drawn from.
THIS_RUN = "33906473914"
REPO = "LewisIsWorking/telegram-pbp-reminder"


def at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def run(run_id, hours_ago, conclusion="success", event="schedule") -> dict:
    """One Actions run in the shape the REST API really returns.

    ⚠️ ``id`` and ``created_at``, not the gh CLI's ``databaseId`` and
    ``createdAt``. The production path goes through the REST API, and a
    fixture in the other shape would pass while production read None.
    """
    return {"id": run_id, "conclusion": conclusion,
            "created_at": at(hours_ago), "event": event}


def heartbeat(hours_ago: float) -> dict:
    return {"written_at": at(hours_ago), "last_run_id": "33900000000",
            "last_run_attempt": "1"}
