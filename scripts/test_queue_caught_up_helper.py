"""Tests for scheduled/queue_caught_up.py and the pin=False parameter
on gm_queue_history.post_and_persist.

Added 2026-05-12 alongside the fix for the orphan-GM-queue bug Lewis
flagged at queue #382. The bug was that "All caught up!" went out via
tg.send_message which bypassed the rolling-history machinery, leaving
the previous GM Queue batch visible in chat with no entry tracking
its eviction.
"""

import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def test_post_caught_up_routes_through_post_and_persist():
    """post_caught_up forwards to post_and_persist with pin=False
    so the previous batch is evicted and the caught-up message is
    NOT pinned (it's informational, not a sticky reference)."""
    from scheduled.queue_caught_up import post_caught_up, CAUGHT_UP_TEXT
    state = {"gm_queue_history": [], "last_queue_pin_id": None}
    with patch("scheduled.queue_caught_up.post_and_persist") as mock_pp:
        mock_pp.return_value = (True, 999)
        post_caught_up(state, -1001, 42)
    assert mock_pp.call_count == 1
    args, kwargs = mock_pp.call_args
    # Positional args: (state, group_id, bot_topic, msgs)
    assert args[0] is state
    assert args[1] == -1001
    assert args[2] == 42
    assert args[3] == [CAUGHT_UP_TEXT]
    # pin=False keyword
    assert kwargs == {"pin": False}, (
        f"Expected pin=False, got kwargs={kwargs}"
    )


def test_post_and_persist_pin_false_does_not_pin():
    """post_and_persist with pin=False calls post_batch with pin=False,
    and the returned batch has pin_id=None. State's last_queue_pin_id
    is cleared (no pin to track)."""
    from scheduled.gm_queue_history import post_and_persist
    from posting import MessageBatch
    state = {"gm_queue_history": [], "last_queue_pin_id": None}
    fake_batch = MessageBatch(msg_ids=[5001], pin_id=None)
    with patch("scheduled.gm_queue_history.post_batch",
               return_value=fake_batch) as mock_post, \
         patch("scheduled.gm_queue_history.tg.unpin_message"), \
         patch("scheduled.gm_queue_history.append_and_evict"):
        sent, pin_id = post_and_persist(
            state, -1001, 42, ["caught up text"], pin=False)
    assert sent is True
    assert pin_id is None
    # post_batch must have been called with pin=False
    _, kwargs = mock_post.call_args
    assert kwargs.get("pin") is False, (
        f"Expected post_batch(pin=False), got {kwargs}"
    )
    # last_queue_pin_id cleared (since batch.pin_id is None)
    assert state["last_queue_pin_id"] is None


def test_post_and_persist_pin_false_unpins_previous():
    """When pin=False, post_and_persist still unpins the PREVIOUS pin
    so the bot topic doesn't accumulate stale pinned-notifications
    when transitioning from a real queue to the caught-up message."""
    from scheduled.gm_queue_history import post_and_persist
    from posting import MessageBatch
    state = {"gm_queue_history": [], "last_queue_pin_id": 12345}
    fake_batch = MessageBatch(msg_ids=[5001], pin_id=None)
    with patch("scheduled.gm_queue_history.post_batch",
               return_value=fake_batch), \
         patch("scheduled.gm_queue_history.tg.unpin_message") as mock_unpin, \
         patch("scheduled.gm_queue_history.append_and_evict"):
        post_and_persist(
            state, -1001, 42, ["caught up text"], pin=False)
    assert mock_unpin.call_count == 1
    args = mock_unpin.call_args[0]
    assert args == (-1001, 12345), (
        f"Expected unpin(-1001, 12345), got unpin{args}"
    )


def test_post_and_persist_pin_true_default_unchanged():
    """pin=True is the default and preserves the pre-2026-05-12
    behaviour (calls post_batch with pin=True, sets last_queue_pin_id
    to the batch's pin_id)."""
    from scheduled.gm_queue_history import post_and_persist
    from posting import MessageBatch
    state = {"gm_queue_history": [], "last_queue_pin_id": None}
    fake_batch = MessageBatch(msg_ids=[5001], pin_id=5001)
    with patch("scheduled.gm_queue_history.post_batch",
               return_value=fake_batch) as mock_post, \
         patch("scheduled.gm_queue_history.tg.unpin_message"), \
         patch("scheduled.gm_queue_history.append_and_evict"):
        sent, pin_id = post_and_persist(
            state, -1001, 42, ["queue text"])  # no pin kwarg = default
    assert sent is True
    assert pin_id == 5001
    _, kwargs = mock_post.call_args
    assert kwargs.get("pin") is True
    assert state["last_queue_pin_id"] == 5001
