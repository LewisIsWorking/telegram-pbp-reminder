"""Tests for scheduled/topic_queue_state.py — slot schema helpers."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


class TestEmptySlot:
    def test_returns_current_schema(self):
        from scheduled.topic_queue_state import empty_slot
        assert empty_slot() == {"msg_ids": [], "fingerprint": ""}

    def test_returns_independent_instances(self):
        from scheduled.topic_queue_state import empty_slot
        a = empty_slot()
        b = empty_slot()
        a["msg_ids"].append(1)
        assert b["msg_ids"] == []


class TestSlotMsgIds:
    def test_reads_current_schema(self):
        from scheduled.topic_queue_state import slot_msg_ids
        assert slot_msg_ids({"msg_ids": [10, 20], "fingerprint": "x"}) == [10, 20]

    def test_falls_back_to_legacy_msg_id(self):
        from scheduled.topic_queue_state import slot_msg_ids
        assert slot_msg_ids({"msg_id": 42, "fingerprint": "x"}) == [42]

    def test_empty_list_when_neither_present(self):
        from scheduled.topic_queue_state import slot_msg_ids
        assert slot_msg_ids({"fingerprint": ""}) == []

    def test_empty_list_when_legacy_is_none(self):
        from scheduled.topic_queue_state import slot_msg_ids
        assert slot_msg_ids({"msg_id": None, "fingerprint": ""}) == []

    def test_empty_list_when_msg_ids_is_empty_list(self):
        from scheduled.topic_queue_state import slot_msg_ids
        assert slot_msg_ids({"msg_ids": [], "fingerprint": ""}) == []

    def test_returns_independent_copy(self):
        """Mutating the returned list must not affect the slot."""
        from scheduled.topic_queue_state import slot_msg_ids
        slot = {"msg_ids": [1, 2], "fingerprint": ""}
        ids = slot_msg_ids(slot)
        ids.append(99)
        assert slot["msg_ids"] == [1, 2]


class TestSetSlotMsgIds:
    def test_writes_current_schema(self):
        from scheduled.topic_queue_state import set_slot_msg_ids
        slot = {"msg_ids": [], "fingerprint": ""}
        set_slot_msg_ids(slot, [100, 101], "fp1")
        assert slot == {"msg_ids": [100, 101], "fingerprint": "fp1"}

    def test_drops_legacy_msg_id(self):
        from scheduled.topic_queue_state import set_slot_msg_ids
        slot = {"msg_id": 7, "fingerprint": "stale"}
        set_slot_msg_ids(slot, [9999], "fresh")
        assert "msg_id" not in slot
        assert slot["msg_ids"] == [9999]
        assert slot["fingerprint"] == "fresh"

    def test_stores_independent_copy(self):
        from scheduled.topic_queue_state import set_slot_msg_ids
        slot = {"msg_ids": [], "fingerprint": ""}
        ids = [1, 2, 3]
        set_slot_msg_ids(slot, ids, "fp")
        ids.append(99)
        assert slot["msg_ids"] == [1, 2, 3]


class TestClearSlot:
    def test_resets_current_schema_slot(self):
        from scheduled.topic_queue_state import clear_slot
        slot = {"msg_ids": [1, 2, 3], "fingerprint": "fp"}
        clear_slot(slot)
        assert slot == {"msg_ids": [], "fingerprint": ""}

    def test_drops_legacy_key(self):
        from scheduled.topic_queue_state import clear_slot
        slot = {"msg_id": 7, "fingerprint": "fp"}
        clear_slot(slot)
        assert "msg_id" not in slot
        assert slot["msg_ids"] == []
        assert slot["fingerprint"] == ""
