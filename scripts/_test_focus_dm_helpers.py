"""Shared fixtures for the focus-message DM tests.

Split out 2026-09-13 when the single test file reached 235 lines. Used by
test_focus_message_is_dmed_on_change.py and test_focus_dm_key_and_wiring.py.
"""

from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
GM = 1698524397

MAGNI_OLDEST = "https://t.me/Path_Wars/144765/178096"
MAGNI_NEXT = "https://t.me/Path_Wars/144765/178200"
RIDDLE = "https://t.me/Path_Wars/66154/177600"


def t(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def entry(link, hours_ago, name="Alastair Tan"):
    return {"name": name, "time": t(hours_ago), "preview": "Action plan",
            "link": link, "message_id": link.rsplit("/", 1)[-1]}


def config():
    return {"group_id": -1001, "bot_topic_id": 999, "gm_user_id": GM,
            "topic_pairs": [
                {"pbp_topic_ids": [144765], "code": "C04", "name": "Magni Guard"},
                {"pbp_topic_ids": [66154], "code": "C00", "name": "Riddleport"}]}


def scanned(*campaigns):
    return {pid: {"campaign": name, "code": code, "entries": list(entries)}
            for pid, name, code, entries in campaigns}


def two_campaigns():
    """Magni Guard owes the oldest reply (79h); Riddleport is next (40h)."""
    return scanned(
        ("144765", "Magni Guard", "C04",
         [entry(MAGNI_OLDEST, 79), entry(MAGNI_NEXT, 10)]),
        ("66154", "Riddleport", "C00", [entry(RIDDLE, 40)]))


class Send:
    """A telegram.send_message stand-in that records every call."""

    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def __call__(self, chat_id, thread_id, text, **_kw):
        self.calls.append((chat_id, thread_id, text))
        return self.ok
