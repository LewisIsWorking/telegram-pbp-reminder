"""A failed delete of the old GM queue is retried on the next refresh.

2026-11-10: posting queue #2136, the delete of #2135 hit "Connection reset
by peer". The batch was kept for retry, as designed, but the retry only ran
on the next NEW post. The queue did not change, so every run edited it in
place, and the old queue stayed visible beside the new one for hours. The
real-state orphan guard then failed every scheduled run.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from test_queue_refreshes_in_place import TestThroughTheRealQueuePost
from posting import MessageBatch, QueueHistory
from scheduled.gm_queue_history import retry_evictions

OLD = 999


def _with_stranded_old_batch(harness):
    state = harness._fresh()
    t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    harness._run(state, t1)
    state["gm_queue_history"].insert(0, {"msg_ids": [OLD], "pin_id": OLD})
    return state, t1


class TestTheRefreshRetries:
    def test_the_old_queue_is_deleted_on_an_unchanged_run(self):
        harness = TestThroughTheRealQueuePost()
        state, t1 = _with_stranded_old_batch(harness)
        with patch("telegram.delete_message", return_value=True) as delete:
            posted, _edits = harness._run(state, t1.replace(minute=30))
        assert posted.call_count == 0, "expected a refresh, not a repost"
        assert [c.args[1] for c in delete.call_args_list] == [OLD]
        assert len(state["gm_queue_history"]) == 1
        assert OLD not in state["gm_queue_history"][0]["msg_ids"]

    def test_a_second_failure_keeps_it_for_the_next_run(self):
        harness = TestThroughTheRealQueuePost()
        state, t1 = _with_stranded_old_batch(harness)
        with patch("telegram.delete_message", return_value=False):
            harness._run(state, t1.replace(minute=30))
        assert state["gm_queue_history"][0]["msg_ids"] == [OLD]
        assert len(state["gm_queue_history"]) == 2


class TestRetryEvictions:
    def test_nothing_to_retry_deletes_nothing(self):
        state = {"gm_queue_history": [{"msg_ids": [5], "pin_id": 5}]}
        with patch("telegram.delete_message") as delete:
            retry_evictions(state, -100)
        delete.assert_not_called()
        assert state["gm_queue_history"] == [{"msg_ids": [5], "pin_id": 5}]

    def test_no_history_is_fine(self):
        state = {}
        retry_evictions(state, -100)
        assert state == {}

    def test_only_the_failed_ids_of_a_batch_are_kept(self):
        batches = [MessageBatch(msg_ids=[1, 2, 3], pin_id=1),
                   MessageBatch(msg_ids=[9], pin_id=9)]
        with patch("telegram.delete_message", side_effect=lambda _c, m: m != 2):
            kept = QueueHistory(max_kept=1).evict_overflow(batches, -100)
        assert [b.msg_ids for b in kept] == [[2], [9]]
