"""The "Reply to this next" message reaches the GM as a DM, on change only.

Lewis, 2026-09-13: the escalation already arrives as a DM and he wanted the
focus message the same way.

⛔ The property that matters most is the one that makes it NOT fire. Lewis
only needs the DM when the message to reply to next changes, and most queue
posts do not change it. So most of these tests are about silence.

(An earlier version of this docstring cited the queue reposting hourly. That
was a fingerprint bug, fixed alongside: see
test_queue_does_not_repost_for_a_ticking_age.py.)

The key itself and the wiring into the real queue post are in
test_focus_dm_key_and_wiring.py.
"""

from _test_focus_dm_helpers import (GM, MAGNI_NEXT, MAGNI_OLDEST, NOW, RIDDLE,
                                    Send, config, entry, scanned,
                                    two_campaigns)
from scheduled.queue_focus_dm import STATE_KEY, send_focus_dm


class TestItFires:
    def test_the_first_focus_is_sent(self):
        send = Send()
        assert send_focus_dm(config(), {}, two_campaigns(), {}, NOW, send=send)
        assert len(send.calls) == 1

    def test_it_is_a_dm_to_the_gm_not_a_post_to_the_group(self):
        """⭐ Asserts the DESTINATION. A test that only checked a message was
        sent would pass on a version posting this into the players' group."""
        send = Send()
        send_focus_dm(config(), {}, two_campaigns(), {}, NOW, send=send)
        chat_id, thread_id, _ = send.calls[0]
        assert chat_id == GM
        assert thread_id is None

    def test_it_sends_the_focus_message_itself(self):
        send = Send()
        send_focus_dm(config(), {}, two_campaigns(), {}, NOW, send=send)
        text = send.calls[0][2]
        assert "🎯 Reply to this next:" in text
        assert "C04: Magni Guard" in text
        assert MAGNI_OLDEST in text


class TestItStaysQuiet:
    def test_the_same_target_again_is_not_resent(self):
        """⭐⭐ The core property: a repost with the same target is not a DM."""
        send, state, queue = Send(), {}, two_campaigns()
        for _ in range(25):
            send_focus_dm(config(), state, queue, {}, NOW, send=send)
        assert len(send.calls) == 1

    def test_a_new_message_elsewhere_does_not_move_the_target(self):
        """New activity in another campaign re-posts the queue but does not
        change which message is owed a reply first."""
        send, state = Send(), {}
        send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=send)
        busier = two_campaigns()
        busier["66154"]["entries"].append(entry("https://t.me/x/66154/9", 1))
        send_focus_dm(config(), state, busier, {}, NOW, send=send)
        assert len(send.calls) == 1

    def test_nothing_owed_sends_nothing(self):
        send = Send()
        assert not send_focus_dm(config(), {}, {}, {}, NOW, send=send)
        assert send.calls == []

    def test_no_gm_configured_sends_nothing(self):
        send, cfg = Send(), config()
        del cfg["gm_user_id"]
        assert not send_focus_dm(cfg, {}, two_campaigns(), {}, NOW, send=send)
        assert send.calls == []


class TestItFiresAgainWhenTheTargetMoves:
    def test_answering_the_oldest_message_announces_the_next(self):
        """⚠️ Same campaign stays in focus, but the TARGET moves to its next
        oldest message. A key built from the campaign alone would miss this.

        Magni's next message is 60h old, still older than Riddleport's 40h,
        so answering the 79h one genuinely leaves Magni Guard in focus. With a
        younger next message the focus would correctly jump to Riddleport."""
        send, state = Send(), {}
        before = scanned(("144765", "Magni Guard", "C04",
                          [entry(MAGNI_OLDEST, 79), entry(MAGNI_NEXT, 60)]),
                         ("66154", "Riddleport", "C00", [entry(RIDDLE, 40)]))
        after = scanned(("144765", "Magni Guard", "C04", [entry(MAGNI_NEXT, 60)]),
                        ("66154", "Riddleport", "C00", [entry(RIDDLE, 40)]))
        send_focus_dm(config(), state, before, {}, NOW, send=send)
        send_focus_dm(config(), state, after, {}, NOW, send=send)

        assert len(send.calls) == 2
        assert "C04: Magni Guard" in send.calls[1][2], "campaign must be unchanged"
        assert MAGNI_NEXT in send.calls[1][2]

    def test_focus_moving_to_another_campaign_is_announced(self):
        send, state = Send(), {}
        send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=send)
        cleared = two_campaigns()
        del cleared["144765"]
        send_focus_dm(config(), state, cleared, {}, NOW, send=send)
        assert len(send.calls) == 2
        assert "C00: Riddleport" in send.calls[1][2]

    def test_a_target_that_returns_after_the_queue_emptied_is_announced(self):
        """Emptying the queue forgets the last target, so a message that is the
        focus again later is not swallowed as a duplicate."""
        send, state, queue = Send(), {}, two_campaigns()
        send_focus_dm(config(), state, queue, {}, NOW, send=send)
        send_focus_dm(config(), state, {}, {}, NOW, send=send)
        assert STATE_KEY not in state
        send_focus_dm(config(), state, queue, {}, NOW, send=send)
        assert len(send.calls) == 2


class TestAFailedSendIsRetried:
    def test_the_target_is_not_recorded_when_telegram_refuses(self):
        """⛔ Recording before the send would mark a failed DM as delivered,
        and it would then never be retried because the target is unchanged."""
        state = {}
        assert not send_focus_dm(config(), state, two_campaigns(), {}, NOW,
                                 send=Send(ok=False))
        assert STATE_KEY not in state

        retry = Send()
        assert send_focus_dm(config(), state, two_campaigns(), {}, NOW, send=retry)
        assert len(retry.calls) == 1
