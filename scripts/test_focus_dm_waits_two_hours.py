"""The GM focus DM goes out at most once every 2 hours.

Lewis, 2026-11-11: the bot DMed him the queue 4 times in 3 hours, because
the target flipped between two campaigns. He asked for "a max of 1 message
per hour or 2 hours". These tests pin the 2-hour gap, and that a change made
inside the gap is still sent once the gap is over.
"""

from datetime import timedelta

from _test_focus_dm_helpers import NOW, Send, config, two_campaigns
from scheduled.queue_focus_dm import (SENT_AT_KEY, STATE_KEY, MIN_GAP,
                                      send_focus_dm)


def _moved():
    """The same queue with Magni Guard answered, so Riddleport is the focus."""
    queue = two_campaigns()
    del queue["144765"]
    return queue


def test_the_gap_is_two_hours():
    assert MIN_GAP == timedelta(hours=2)


def test_a_new_target_inside_the_gap_is_held_back():
    send, state = Send(), {}
    assert send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=send)
    assert not send_focus_dm(config(), state, _moved(), {},
                             NOW + timedelta(minutes=119), send=send)
    assert len(send.calls) == 1


def test_the_held_back_target_is_sent_once_the_gap_is_over():
    """⚠️ Holding a DM back must not record its target, or it would never be
    sent: the next run would see the same key and skip it as a duplicate."""
    send, state = Send(), {}
    send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=send)
    send_focus_dm(config(), state, _moved(), {}, NOW + timedelta(hours=1),
                  send=send)
    assert send_focus_dm(config(), state, _moved(), {},
                         NOW + timedelta(hours=2), send=send)
    assert len(send.calls) == 2
    assert "C00: Riddleport" in send.calls[1][2]


def test_the_send_time_is_recorded_only_on_success():
    state = {}
    send_focus_dm(config(), state, two_campaigns(), {}, NOW,
                  send=Send(ok=False))
    assert SENT_AT_KEY not in state
    assert send_focus_dm(config(), state, two_campaigns(), {},
                         NOW + timedelta(minutes=1), send=Send())
    assert state[SENT_AT_KEY] == (NOW + timedelta(minutes=1)).isoformat()


def test_a_corrupt_stamp_does_not_silence_the_dm():
    state = {SENT_AT_KEY: "not a time"}
    assert send_focus_dm(config(), state, two_campaigns(), {}, NOW,
                         send=Send())


def test_an_emptied_queue_does_not_reset_the_gap():
    """Emptying the queue forgets the target but not when the last DM went,
    so a queue that empties and refills cannot DM twice in a row."""
    send, state = Send(), {}
    send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=send)
    send_focus_dm(config(), state, {}, {}, NOW + timedelta(minutes=10),
                  send=send)
    assert STATE_KEY not in state
    assert not send_focus_dm(config(), state, two_campaigns(), {},
                             NOW + timedelta(minutes=20), send=send)
    assert len(send.calls) == 1
