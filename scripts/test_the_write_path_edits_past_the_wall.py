"""The queue writer actually takes the edit path. End to end.

⛔ Proven is not reachable, and this is the fourth time in one session
the harness has caught me testing pieces and not wiring.
``test_never_attempt_a_delete_that_cannot_win`` proves
``can_still_delete`` and ``MessageBatch.edit_all`` in isolation. Neither
shows that ``_post_thread_queue`` or ``_clear_thread_queue`` calls them,
and a fix nothing calls is exactly how three messages got orphaned while
a guard sat green.

Every test here drives the real write path and asserts on what reached
Telegram: **no delete for a message past the wall, ever.**
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
_THREAD = "40585"
_GROUP = -1001661053273


@pytest.fixture
def tg_calls(monkeypatch):
    """Record every outbound call the write path makes."""
    import telegram as tg
    calls = {"edit": [], "delete": [], "send": [], "unpin": [], "pin": []}
    monkeypatch.setattr(tg, "edit_message",
                        lambda c, m, t, **k: calls["edit"].append((m, t)) or True)
    monkeypatch.setattr(tg, "delete_message",
                        lambda c, m: calls["delete"].append(m) or True)
    monkeypatch.setattr(tg, "send_message_id",
                        lambda c, t, b, **k: calls["send"].append(b) or 5555)
    monkeypatch.setattr(tg, "unpin_message",
                        lambda c, m: calls["unpin"].append(m) or True)
    return calls


def _slot(hours_old):
    return {"msg_ids": [900], "pin_id": 900, "fingerprint": "stale",
            "last_posted_at": (_NOW - timedelta(hours=hours_old)).isoformat(),
            "caught_up_msg_id": None, "caught_up_at": None,
            "pending_delete": []}


def _entries():
    return [{"name": "Cannon", "time": "2026-08-30 09:00:00",
             "preview": "a thing", "message_id": "1", "link": "",
             "thread_id": _THREAD}]


class TestPostingPastTheWall:
    def test_it_edits_and_never_deletes(self, tg_calls):
        # ⭐⭐ The real 2026-08-31 shape: 57.5h old, content changed.
        from scheduled.topic_queue_write import _post_thread_queue
        slot = _slot(57.5)
        _post_thread_queue(_GROUP, _THREAD, slot, _entries(), _NOW)
        assert tg_calls["edit"], "the message past the wall was not edited"
        assert tg_calls["delete"] == [], (
            f"attempted {tg_calls['delete']}: a delete past the wall is a "
            f"loss that has already happened")
        assert slot["msg_ids"] == [900], "the message must be REUSED"

    def test_it_does_not_move_the_send_clock(self, tg_calls):
        # ⚠️ last_posted_at records when the IDs were SENT, which is what
        # governs deletability. Refreshing it on an edit would make the
        # slot look freshly deletable and put us back into doomed deletes.
        from scheduled.topic_queue_write import _post_thread_queue
        slot = _slot(57.5)
        before = slot["last_posted_at"]
        _post_thread_queue(_GROUP, _THREAD, slot, _entries(), _NOW)
        assert slot["last_posted_at"] == before
        assert slot.get("last_edited_at"), "the edit should be observable"

    def test_a_fresh_message_still_deletes_and_reposts(self, tg_calls,
                                                      monkeypatch):
        # ⭐ can-fail counterpart, and it protects the notification. A
        # real content change on a young message must behave exactly as
        # before: delete, repost, ping.
        import scheduled.topic_queue_write as w
        monkeypatch.setattr(w, "post_batch",
                            lambda *a, **k: __import__("posting").MessageBatch(
                                msg_ids=[901], pin_id=901))
        slot = _slot(2)
        w._post_thread_queue(_GROUP, _THREAD, slot, _entries(), _NOW)
        assert tg_calls["delete"] == [900]
        assert tg_calls["edit"] == []


class TestClearingPastTheWall:
    def test_the_queue_becomes_the_caught_up_notice(self, tg_calls):
        # ⭐ 15 of the 28 historical orphans were caught-up notices. Past
        # the wall the queue message is edited into one instead.
        from scheduled.topic_queue_clear import _clear_thread_queue
        slot = _slot(57.5)
        _clear_thread_queue(_GROUP, _THREAD, slot, pid=_THREAD, state=None,
                            config={"topic_pairs": []}, now=_NOW)
        assert tg_calls["edit"], "the queue was not edited into a notice"
        assert tg_calls["delete"] == []
        assert tg_calls["send"] == [], "a new notice must not be sent"
        assert slot["caught_up_msg_id"] == 900, "the same message is reused"

    def test_the_reused_notice_is_not_given_a_fresh_timestamp(self, tg_calls):
        # ⛔ It is as old as the message it came from. Stamping it `now`
        # would tell sweep_aged_caught_up it has 36 hours to delete
        # something it can never delete.
        from scheduled.topic_queue_clear import _clear_thread_queue
        slot = _slot(57.5)
        _clear_thread_queue(_GROUP, _THREAD, slot, pid=_THREAD, state=None,
                            config={"topic_pairs": []}, now=_NOW)
        assert slot["caught_up_at"] is None

    def test_a_fresh_queue_still_deletes_and_sends_a_notice(self, tg_calls):
        # can-fail counterpart for the clear path.
        from scheduled.topic_queue_clear import _clear_thread_queue
        slot = _slot(2)
        _clear_thread_queue(_GROUP, _THREAD, slot, pid=_THREAD, state=None,
                            config={"topic_pairs": []}, now=_NOW)
        assert tg_calls["delete"] == [900]
        assert tg_calls["send"] and tg_calls["edit"] == []
        assert slot["caught_up_at"] == _NOW.isoformat()
