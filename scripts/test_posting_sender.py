"""Unit tests for ``posting.sender.post_batch``."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


class TestSendChunks:
    def test_sends_each_chunk_in_order(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.side_effect = [101, 102, 103]
        post_batch(-100, 999, ["a", "b", "c"], pin=False)
        assert tg_mock.send_message_id.call_count == 3
        sent = [c[0][2] for c in tg_mock.send_message_id.call_args_list]
        assert sent == ["a", "b", "c"]

    def test_passes_thread_id(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = 42
        post_batch(-100, 999, ["x"], pin=False)
        # send_message_id is called with (group_id, thread_id, chunk)
        assert tg_mock.send_message_id.call_args[0][:2] == (-100, 999)

    def test_thread_id_none_for_non_forum_chats(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = 1
        post_batch(-100, None, ["x"], pin=False)
        assert tg_mock.send_message_id.call_args[0][:2] == (-100, None)


class TestReturnValue:
    def test_returns_message_batch_with_msg_ids(self, tg_mock):
        from posting import MessageBatch, post_batch
        tg_mock.send_message_id.side_effect = [10, 11]
        result = post_batch(-100, 999, ["a", "b"], pin=False)
        assert isinstance(result, MessageBatch)
        assert result.msg_ids == [10, 11]

    def test_returns_none_when_every_send_fails(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = None
        assert post_batch(-100, 999, ["a", "b"], pin=False) is None

    def test_partial_send_returns_only_delivered_ids(self, tg_mock):
        from posting import post_batch
        # 1st succeeds, 2nd fails, 3rd succeeds
        tg_mock.send_message_id.side_effect = [10, None, 12]
        result = post_batch(-100, 999, ["a", "b", "c"], pin=False)
        assert result.msg_ids == [10, 12]


class TestPinning:
    def test_pin_true_pins_first_delivered_chunk(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.side_effect = [501, 502]
        result = post_batch(-100, 999, ["a", "b"], pin=True)
        tg_mock.pin_message.assert_called_once_with(
            -100, 501, disable_notification=False)
        assert result.pin_id == 501

    def test_pin_false_skips_pin_call(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = 42
        result = post_batch(-100, 999, ["a"], pin=False)
        tg_mock.pin_message.assert_not_called()
        assert result.pin_id is None

    def test_disable_notification_forwarded(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = 7
        post_batch(-100, 999, ["x"], pin=True, disable_notification=True)
        tg_mock.pin_message.assert_called_once_with(
            -100, 7, disable_notification=True)

    def test_no_pin_when_first_send_fails_but_later_succeeds(self, tg_mock):
        """When 1st chunk fails, 2nd's id is the pin (it was delivered first)."""
        from posting import post_batch
        tg_mock.send_message_id.side_effect = [None, 502]
        result = post_batch(-100, 999, ["a", "b"], pin=True)
        # Pin is the first *delivered* chunk, not the first attempted.
        tg_mock.pin_message.assert_called_once_with(
            -100, 502, disable_notification=False)
        assert result.pin_id == 502

    def test_no_pin_call_when_every_send_fails(self, tg_mock):
        from posting import post_batch
        tg_mock.send_message_id.return_value = None
        result = post_batch(-100, 999, ["a"], pin=True)
        assert result is None
        tg_mock.pin_message.assert_not_called()
