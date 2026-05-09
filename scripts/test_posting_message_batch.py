"""Unit tests for ``posting.message_batch.MessageBatch``."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


class TestConstruction:
    def test_default_pin_id_is_none(self):
        from posting import MessageBatch
        b = MessageBatch(msg_ids=[1, 2, 3])
        assert b.pin_id is None

    def test_explicit_pin_id(self):
        from posting import MessageBatch
        b = MessageBatch(msg_ids=[10, 11], pin_id=10)
        assert b.pin_id == 10

    def test_empty_msg_ids_allowed(self):
        from posting import MessageBatch
        b = MessageBatch(msg_ids=[])
        assert b.is_empty


class TestIsEmpty:
    def test_true_when_no_ids(self):
        from posting import MessageBatch
        assert MessageBatch(msg_ids=[]).is_empty

    def test_false_when_one_id(self):
        from posting import MessageBatch
        assert not MessageBatch(msg_ids=[42]).is_empty

    def test_false_when_pin_id_only_present(self):
        """is_empty is about msg_ids, not pin_id."""
        from posting import MessageBatch
        # pin_id without msg_ids is technically inconsistent but should
        # still report is_empty since there's nothing to delete.
        b = MessageBatch(msg_ids=[], pin_id=42)
        assert b.is_empty


class TestDeleteAll:
    """delete_all goes through posting.message_batch.tg."""

    def test_returns_empty_list_when_all_succeed(self, tg_mock):
        from posting import MessageBatch
        tg_mock.delete_message.return_value = True
        failed = MessageBatch(msg_ids=[1, 2, 3]).delete_all(-100)
        assert failed == []
        assert tg_mock.delete_message.call_count == 3

    def test_returns_failed_ids(self, tg_mock):
        from posting import MessageBatch
        # 2 fails, others succeed
        tg_mock.delete_message.side_effect = lambda gid, mid: mid != 2
        failed = MessageBatch(msg_ids=[1, 2, 3]).delete_all(-100)
        assert failed == [2]

    def test_no_calls_for_empty_batch(self, tg_mock):
        from posting import MessageBatch
        failed = MessageBatch(msg_ids=[]).delete_all(-100)
        assert failed == []
        tg_mock.delete_message.assert_not_called()

    def test_passes_group_id(self, tg_mock):
        from posting import MessageBatch
        tg_mock.delete_message.return_value = True
        MessageBatch(msg_ids=[7]).delete_all(-9999)
        tg_mock.delete_message.assert_called_once_with(-9999, 7)


class TestToFromDict:
    def test_round_trip_preserves_data(self):
        from posting import MessageBatch
        original = MessageBatch(msg_ids=[100, 101, 102], pin_id=100)
        restored = MessageBatch.from_dict(original.to_dict())
        assert restored.msg_ids == [100, 101, 102]
        assert restored.pin_id == 100

    def test_to_dict_shape(self):
        from posting import MessageBatch
        b = MessageBatch(msg_ids=[1], pin_id=1)
        assert b.to_dict() == {"msg_ids": [1], "pin_id": 1}

    def test_from_dict_tolerates_missing_pin_id(self):
        from posting import MessageBatch
        b = MessageBatch.from_dict({"msg_ids": [5]})
        assert b.msg_ids == [5]
        assert b.pin_id is None

    def test_from_dict_tolerates_missing_msg_ids(self):
        from posting import MessageBatch
        b = MessageBatch.from_dict({})
        assert b.msg_ids == []
        assert b.pin_id is None

    def test_to_dict_returns_independent_msg_ids_list(self):
        """Mutating the returned dict's msg_ids must not affect the batch."""
        from posting import MessageBatch
        b = MessageBatch(msg_ids=[1, 2])
        d = b.to_dict()
        d["msg_ids"].append(99)
        assert b.msg_ids == [1, 2]
