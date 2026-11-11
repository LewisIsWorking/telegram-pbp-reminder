"""Switching the schedule post off also takes down its last copy.

Lewis, 2026-11-11: "I don't really need the Bot's schedule". Before this,
schedule_post_enabled=False only stopped new posts, so the last one stayed
up with a "Next run" that never came.
"""

from datetime import datetime, timezone

from scheduled.schedule_post import post_schedule

_NOW = datetime(2026, 11, 11, 4, 0, tzinfo=timezone.utc)
_CFG = {"group_id": -100, "bot_topic_id": 137393,
        "schedule_chat_id": -200, "schedule_topic_id": 1,
        "queue_daily_hours": [9, 21], "poll_post_hour": 7,
        "diagnostic_hour": 8, "topic_pairs": [],
        "schedule_post_enabled": False}


def test_the_last_post_is_deleted_and_forgotten(tg_mock):
    tg_mock.delete_message.return_value = True
    state = {"schedule_post_msg_id": 55, "schedule_post_chat_id": -200}
    post_schedule(_CFG, state, now=_NOW)
    tg_mock.delete_message.assert_called_once_with(-200, 55)
    assert not tg_mock.send_message_id.called
    assert "schedule_post_msg_id" not in state
    assert "schedule_post_chat_id" not in state


def test_a_failed_delete_is_kept_for_the_next_run(tg_mock):
    tg_mock.delete_message.return_value = False
    state = {"schedule_post_msg_id": 55, "schedule_post_chat_id": -200}
    post_schedule(_CFG, state, now=_NOW)
    assert state["schedule_post_msg_id"] == 55


def test_older_state_without_a_chat_falls_back_to_the_group(tg_mock):
    tg_mock.delete_message.return_value = True
    post_schedule(_CFG, {"schedule_post_msg_id": 9}, now=_NOW)
    tg_mock.delete_message.assert_called_once_with(-100, 9)


def test_nothing_to_take_down_does_nothing(tg_mock):
    post_schedule(_CFG, {}, now=_NOW)
    assert not tg_mock.delete_message.called
    assert not tg_mock.send_message_id.called
