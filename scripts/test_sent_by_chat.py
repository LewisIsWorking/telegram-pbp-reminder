"""Bot-sent IDs are kept per chat for separate destinations (2026-09-22).

Regression for the delete guard: message IDs are unique only within a
chat, so an ID the bot sent in Nudge Bot Notifications must never let the
guard delete the message with the same ID in Path Wars.
"""

import pytest

from posting import bot_sent_registry as bsr
from posting import sent_by_chat as sbc

MAIN, NOTIF, OTHER = -1001661053273, -1004303231713, -123


@pytest.fixture(autouse=True)
def _fresh(monkeypatch, tmp_path):
    from state_store import StateStore
    store = StateStore(state_dir=tmp_path)
    monkeypatch.setattr(sbc, "_store", store)
    monkeypatch.setattr(bsr, "_store", store)
    monkeypatch.setattr(bsr, "_backfill_locked", lambda: 0)
    sbc.reset_for_test()
    bsr.reset_for_test()
    sbc._SEPARATE.append(frozenset({NOTIF}))
    yield
    sbc.reset_for_test()
    bsr.reset_for_test()


def test_an_id_sent_elsewhere_does_not_authorise_a_main_group_delete():
    sbc.record_sent_in(NOTIF, 512, "Pin digest")
    assert sbc.is_bot_sent_in(NOTIF, 512)
    assert not sbc.is_bot_sent_in(MAIN, 512)
    assert not bsr.is_bot_sent(512)


def test_main_group_sends_still_use_the_flat_registry():
    sbc.record_sent_in(MAIN, 176700, "Queue")
    assert bsr.is_bot_sent(176700)
    assert sbc.is_bot_sent_in(MAIN, 176700)


def test_an_unlisted_chat_behaves_exactly_as_before():
    sbc.record_sent_in(OTHER, 9, "fixture")
    assert bsr.is_bot_sent(9)


def test_ids_recorded_before_the_split_can_still_be_cleaned_up():
    bsr.record_sent(300)  # an old schedule post, recorded flat
    assert sbc.is_bot_sent_in(NOTIF, 300)


def test_per_chat_ids_survive_a_reload():
    sbc.record_sent_in(NOTIF, 77)
    sbc._BY_CHAT = None
    assert sbc.is_bot_sent_in(NOTIF, 77)


def test_the_real_config_marks_the_notifications_group_separate():
    sbc.reset_for_test()
    assert not sbc.is_main(NOTIF)
    assert sbc.is_main(MAIN) and sbc.is_main(None)
