"""Unit tests for ``posting.single_pin.SinglePin``."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


class TestEmptySlot:
    def test_current_schema_shape(self):
        from posting import SinglePin
        slot = SinglePin.empty_slot()
        assert slot == {"msg_ids": [], "fingerprint": "", "last_posted_at": None}

    def test_each_call_returns_new_dict(self):
        """Mutating one slot must not affect another."""
        from posting import SinglePin
        a = SinglePin.empty_slot()
        b = SinglePin.empty_slot()
        a["msg_ids"].append(99)
        assert b["msg_ids"] == []


class TestReadBatch:
    def test_current_schema_with_msg_ids(self):
        from posting import SinglePin
        batch = SinglePin.read_batch({"msg_ids": [10, 20, 30],
                                      "fingerprint": "fp"})
        assert batch.msg_ids == [10, 20, 30]
        assert batch.pin_id == 10

    def test_legacy_msg_id_shape(self):
        from posting import SinglePin
        batch = SinglePin.read_batch({"msg_id": 42, "fingerprint": "x"})
        assert batch.msg_ids == [42]
        assert batch.pin_id == 42

    def test_empty_when_neither_present(self):
        from posting import SinglePin
        batch = SinglePin.read_batch({"fingerprint": ""})
        assert batch.msg_ids == []
        assert batch.pin_id is None

    def test_empty_when_legacy_msg_id_is_none(self):
        from posting import SinglePin
        batch = SinglePin.read_batch({"msg_id": None, "fingerprint": ""})
        assert batch.msg_ids == []

    def test_empty_when_msg_ids_empty_list(self):
        from posting import SinglePin
        batch = SinglePin.read_batch({"msg_ids": [], "fingerprint": ""})
        assert batch.is_empty

    def test_returns_independent_copy(self):
        """Mutating returned batch's msg_ids must not affect the slot."""
        from posting import SinglePin
        slot = {"msg_ids": [1, 2], "fingerprint": ""}
        batch = SinglePin.read_batch(slot)
        batch.msg_ids.append(99)
        assert slot["msg_ids"] == [1, 2]


class TestWriteBatch:
    def test_writes_current_schema(self):
        from posting import MessageBatch, SinglePin
        slot = {"msg_ids": [], "fingerprint": ""}
        batch = MessageBatch(msg_ids=[100, 101], pin_id=100)
        SinglePin.write_batch(slot, batch, "fp1")
        assert slot["msg_ids"] == [100, 101]
        assert slot["fingerprint"] == "fp1"
        assert "last_posted_at" in slot
        assert slot["last_posted_at"] is not None

    def test_drops_legacy_msg_id_key(self):
        from posting import MessageBatch, SinglePin
        slot = {"msg_id": 7, "fingerprint": "stale"}
        SinglePin.write_batch(slot,
                              MessageBatch(msg_ids=[9999]), "fresh")
        assert "msg_id" not in slot
        assert slot["msg_ids"] == [9999]
        assert slot["fingerprint"] == "fresh"

    def test_stores_independent_copy_of_msg_ids(self):
        from posting import MessageBatch, SinglePin
        slot = {"msg_ids": [], "fingerprint": ""}
        batch = MessageBatch(msg_ids=[1, 2, 3])
        SinglePin.write_batch(slot, batch, "fp")
        # Mutating the original batch's msg_ids should not affect slot
        batch.msg_ids.append(99)
        assert slot["msg_ids"] == [1, 2, 3]


class TestClear:
    def test_resets_current_schema(self):
        from posting import SinglePin
        slot = {"msg_ids": [1, 2, 3], "fingerprint": "fp",
                "last_posted_at": "2026-05-08T14:00:00+00:00"}
        SinglePin.clear(slot)
        assert slot["msg_ids"] == []
        assert slot["fingerprint"] == ""
        assert slot["last_posted_at"] is None

    def test_drops_legacy_msg_id_key(self):
        from posting import SinglePin
        slot = {"msg_id": 7, "fingerprint": "fp"}
        SinglePin.clear(slot)
        assert "msg_id" not in slot
        assert slot["msg_ids"] == []

    def test_preserves_caught_up_msg_id(self):
        """SinglePin owns msg_ids/fingerprint/last_posted_at only.
        Other slot fields (e.g. caught_up_msg_id used by topic_queue_poster
        for cleaning up '✅ All caught up!' notices) must survive a clear
        so the next cycle can find and delete them.
        """
        from posting import SinglePin
        slot = {"msg_ids": [1, 2], "fingerprint": "fp",
                "last_posted_at": "2026-05-08T14:00:00+00:00",
                "caught_up_msg_id": 9999}
        SinglePin.clear(slot)
        assert slot["msg_ids"] == []
        assert slot["caught_up_msg_id"] == 9999  # untouched


class TestRoundTrip:
    """Slot survives a write-then-read round trip preserving content."""

    def test_round_trip_preserves_msg_ids(self):
        from posting import MessageBatch, SinglePin
        slot = SinglePin.empty_slot()
        original = MessageBatch(msg_ids=[10, 20], pin_id=10)
        SinglePin.write_batch(slot, original, "fp")
        recovered = SinglePin.read_batch(slot)
        assert recovered.msg_ids == [10, 20]
        assert recovered.pin_id == 10
