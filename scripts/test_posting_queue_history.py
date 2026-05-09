"""Unit tests for ``posting.queue_history.QueueHistory``."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


def _b(msg_ids: list[int], pin_id: int | None = None):
    """Construct a MessageBatch tersely; pin_id defaults to first msg_id."""
    from posting import MessageBatch
    if pin_id is None and msg_ids:
        pin_id = msg_ids[0]
    return MessageBatch(msg_ids=list(msg_ids), pin_id=pin_id)


class TestSerialisation:
    def test_from_dicts_round_trip(self):
        from posting import QueueHistory
        dicts = [{"msg_ids": [1, 2], "pin_id": 1},
                 {"msg_ids": [3], "pin_id": 3}]
        batches = QueueHistory.from_dicts(dicts)
        assert len(batches) == 2
        assert batches[0].msg_ids == [1, 2]
        assert batches[1].pin_id == 3

    def test_to_dicts_round_trip(self):
        from posting import QueueHistory
        batches = [_b([1, 2]), _b([3])]
        dicts = QueueHistory.to_dicts(batches)
        assert dicts == [
            {"msg_ids": [1, 2], "pin_id": 1},
            {"msg_ids": [3], "pin_id": 3},
        ]

    def test_empty_lists(self):
        from posting import QueueHistory
        assert QueueHistory.from_dicts([]) == []
        assert QueueHistory.to_dicts([]) == []


class TestAppendNoEviction:
    def test_first_append(self, tg_mock):
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        result = history.append_with_retry([], _b([100]), -100)
        assert len(result) == 1
        tg_mock.delete_message.assert_not_called()

    def test_under_cap(self, tg_mock):
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        result = history.append_with_retry([_b([10]), _b([20])], _b([30]), -100)
        assert [b.pin_id for b in result] == [10, 20, 30]
        tg_mock.delete_message.assert_not_called()


class TestAppendEvicts:
    def test_overflow_evicts_oldest(self, tg_mock):
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        tg_mock.delete_message.return_value = True
        existing = [_b([10]), _b([20]), _b([30])]
        result = history.append_with_retry(existing, _b([40]), -100)
        # Oldest (10) evicted, length back to 3.
        assert len(result) == 3
        assert [b.pin_id for b in result] == [20, 30, 40]
        tg_mock.delete_message.assert_called_once_with(-100, 10)

    def test_evicts_every_id_in_multi_message_batch(self, tg_mock):
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        tg_mock.delete_message.return_value = True
        existing = [_b([100, 101, 102]), _b([200]), _b([300])]
        history.append_with_retry(existing, _b([400]), -100)
        assert tg_mock.delete_message.call_count == 3
        deleted = [c[0][1] for c in tg_mock.delete_message.call_args_list]
        assert deleted == [100, 101, 102]


class TestRetryOnFailure:
    def test_failed_delete_keeps_batch_with_failed_ids(self, tg_mock):
        """If a delete fails, the batch is retained at the front with only
        the failed IDs so the next call can retry."""
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        # 100 fails, 101 succeeds
        tg_mock.delete_message.side_effect = lambda gid, mid: mid != 100
        existing = [_b([100, 101]), _b([200]), _b([300])]
        result = history.append_with_retry(existing, _b([400]), -100)
        # The retained batch sits at front, with only the failed ID
        assert result[0].msg_ids == [100]
        # And rest are unchanged + new at tail
        assert [b.pin_id for b in result] == [100, 200, 300, 400]

    def test_all_deletes_failed_keeps_full_batch(self, tg_mock):
        from posting import QueueHistory
        history = QueueHistory(max_kept=3)
        tg_mock.delete_message.return_value = False
        existing = [_b([100, 101]), _b([200]), _b([300])]
        result = history.append_with_retry(existing, _b([400]), -100)
        assert result[0].msg_ids == [100, 101]

    def test_retained_then_evictable_chain(self, tg_mock):
        """Multiple eviction attempts in one call: front blocks, second
        evicts cleanly."""
        from posting import QueueHistory
        history = QueueHistory(max_kept=2)  # cap=2
        # First eviction (the 10s) fails its 10; second (the 20s) succeeds
        tg_mock.delete_message.side_effect = lambda gid, mid: mid != 10
        existing = [_b([10]), _b([20]), _b([30])]
        result = history.append_with_retry(existing, _b([40]), -100)
        # Cap=2 means we want 2 batches. Started with 3, added 1 = 4.
        # Need to evict 2. Front [10] fails (retained). Next [20] succeeds.
        # Final: [10_retained, 30, 40] = 3 (cap+1 due to stuck batch).
        assert [b.pin_id for b in result] == [10, 30, 40]
