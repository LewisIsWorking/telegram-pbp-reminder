"""Issue #36: a failed delete of the old schedule post must not leave a post nothing remembers.

Before 2026-11-25, post_schedule sent the new post, called delete_message on the old one and threw the result away,
then overwrote the old id. One failed delete meant two schedule posts in the topic for good.
"""
from datetime import datetime, timezone

from posting.bot_sent_state_scan import extract_ids_from_live
from scheduled.schedule_post import post_schedule

_NOW = datetime(2026, 11, 25, 4, 0, tzinfo=timezone.utc)
_CFG = {"group_id": -100, "bot_topic_id": 137393, "schedule_chat_id": -200, "schedule_topic_id": 1,
        "queue_daily_hours": [9, 21], "poll_post_hour": 7, "diagnostic_hour": 8, "topic_pairs": []}


def test_a_failed_delete_keeps_the_old_id_and_retries_it_next_run(tg_mock):
    tg_mock.send_message_id.return_value = 2
    tg_mock.delete_message.return_value = False
    state = {"schedule_post_msg_id": 1, "schedule_post_chat_id": -200}
    post_schedule(_CFG, state, now=_NOW)
    assert state["schedule_post_msg_id"] == 2 and state["schedule_post_stale"] == [[-200, 1]]
    assert 1 in extract_ids_from_live(state)   # the registry still knows it, so the retry is not refused

    tg_mock.send_message_id.return_value = 3
    tg_mock.delete_message.return_value = True
    tg_mock.delete_message.reset_mock()
    post_schedule(_CFG, state, now=_NOW)
    assert {c.args for c in tg_mock.delete_message.call_args_list} == {(-200, 1), (-200, 2)}
    assert state["schedule_post_msg_id"] == 3 and state["schedule_post_stale"] == []


def test_a_delete_that_raises_still_records_the_new_post(tg_mock):
    tg_mock.send_message_id.return_value = 2
    tg_mock.delete_message.side_effect = RuntimeError("boom")
    state = {"schedule_post_msg_id": 1, "schedule_post_chat_id": -200}
    post_schedule(_CFG, state, now=_NOW)
    assert state["schedule_post_msg_id"] == 2 and state["schedule_post_stale"] == [[-200, 1]]


def test_a_post_telegram_will_never_delete_is_dropped(tg_mock, monkeypatch):
    import posting.stuck_deletes as stuck
    monkeypatch.setattr(stuck, "is_hopeless", lambda mid: mid == 1)
    tg_mock.send_message_id.return_value = 3
    tg_mock.delete_message.return_value = True
    state = {"schedule_post_msg_id": 2, "schedule_post_chat_id": -200, "schedule_post_stale": [[-200, 1]]}
    post_schedule(_CFG, state, now=_NOW)
    tg_mock.delete_message.assert_called_once_with(-200, 2)
    assert state["schedule_post_stale"] == []


def test_switched_off_still_retries_the_stale_ones(tg_mock):
    tg_mock.delete_message.return_value = True
    state = {"schedule_post_stale": [[-200, 1]]}
    post_schedule(dict(_CFG, schedule_post_enabled=False), state, now=_NOW)
    tg_mock.delete_message.assert_called_once_with(-200, 1)
    assert state["schedule_post_stale"] == [] and not tg_mock.send_message_id.called
