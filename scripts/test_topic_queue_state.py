"""Tests for scheduled/topic_queue_state.py — slot schema helpers."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone


def _dt(*args):
    """Build a UTC datetime from positional args (y, m, d, h, m, s)."""
    return datetime(*args, tzinfo=timezone.utc)


class TestEmptySlot:
    def test_returns_current_schema(self):
        from scheduled.topic_queue_state import empty_slot
        assert empty_slot() == {"msg_ids": [], "fingerprint": "", "last_posted_at": None}

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
        assert slot["msg_ids"] == [100, 101]
        assert slot["fingerprint"] == "fp1"
        assert "last_posted_at" in slot

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
        assert slot["msg_ids"] == []
        assert slot["fingerprint"] == ""
        assert slot.get("last_posted_at") is None

    def test_drops_legacy_key(self):
        from scheduled.topic_queue_state import clear_slot
        slot = {"msg_id": 7, "fingerprint": "fp"}
        clear_slot(slot)
        assert "msg_id" not in slot
        assert slot["msg_ids"] == []
        assert slot["fingerprint"] == ""


# ── can_skip_repost / staleness gate (L28, 2026-05-28) ──────────────────────

class TestCanSkipRepost:
    """The 48h-delete-window guard: an unchanged queue must re-post
    before its tracked message ages past Telegram's 48h delete limit,
    or the next change orphans it."""

    _NOW = _dt(2026, 5, 28, 12, 0, 0)

    def _slot(self, msg_ids=(8888,), fingerprint="fp",
              posted="2026-05-28T11:00:00+00:00"):
        s = {"msg_ids": list(msg_ids), "fingerprint": fingerprint}
        if posted is not None:
            s["last_posted_at"] = posted
        return s

    def test_skip_when_unchanged_and_fresh(self):
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot()
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is True

    def test_no_skip_when_fingerprint_changed(self):
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot()
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "different", existing, self._NOW) is False

    def test_no_skip_when_empty_batch(self):
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot(msg_ids=())
        existing = MessageBatch(msg_ids=[], pin_id=None)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is False

    def test_no_skip_when_stale_past_threshold(self):
        """Posted 40h ago (> 36h threshold) → must re-post to stay
        within the 48h delete window."""
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot(posted="2026-05-26T20:00:00+00:00")  # 40h before _NOW
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is False

    def test_skip_at_exactly_under_threshold(self):
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        # 35h before _NOW (just under 36h) → still skippable.
        slot = self._slot(posted="2026-05-27T01:00:00+00:00")
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is True

    def test_no_skip_when_no_timestamp(self):
        """Legacy slot / unknown age → force a refresh (can't confirm
        the message is still deletable)."""
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot(posted=None)
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is False

    def test_no_skip_when_timestamp_unparseable(self):
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot(posted="not-a-timestamp")
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is False

    def test_naive_timestamp_treated_as_utc(self):
        """A stored timestamp without tzinfo is assumed UTC, not crashed on."""
        from scheduled.topic_queue_state import can_skip_repost
        from posting import MessageBatch
        slot = self._slot(posted="2026-05-28 11:00:00")  # naive, 1h ago
        existing = MessageBatch(msg_ids=[8888], pin_id=8888)
        assert can_skip_repost(slot, "fp", existing, self._NOW) is True
