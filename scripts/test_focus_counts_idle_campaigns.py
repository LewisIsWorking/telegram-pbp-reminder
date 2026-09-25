"""Silent and caught-up campaigns can go first (Lewis, 2026-09-25).

"Reply to this next" used to consider only unreplied messages, so a
campaign nobody had posted in for a week never came up while any message
anywhere was waiting a day. Now the longer wait wins, on one clock.
"""

from datetime import timedelta

from _test_focus_dm_helpers import MAGNI_OLDEST, NOW, entry, scanned
from scheduled.queue_focus import (build_focus_message, focus_key,
                                   pick_idle_focus)

MAGNI, KIBWE = "144765", "40585"


def _config():
    return {"group_id": -1001661053273, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [144765], "code": "C04", "name": "Magni Guard"},
        {"pbp_topic_ids": [40585], "code": "C06", "name": "Kibwe"}]}


def _state(kibwe_hours_ago):
    last = (NOW - timedelta(hours=kibwe_hours_ago)).isoformat()
    return {"topics": {KIBWE: {"last_message_time": last}}}


def _queue(magni_hours):
    return scanned((MAGNI, "Magni Guard", "C04", [entry(MAGNI_OLDEST, magni_hours)]))


def test_a_silent_campaign_goes_first_when_it_has_waited_longer():
    msg = build_focus_message(_config(), _queue(28), {}, NOW, state=_state(6 * 24))
    assert "Post here next" in msg and "Kibwe" in msg
    assert "Reply to this next" not in msg
    assert "No posts for 6d" in msg and "(1d 4h)" in msg


def test_a_caught_up_campaign_can_go_first_too():
    msg = build_focus_message(_config(), _queue(10), {}, NOW, state=_state(30))
    assert "Kibwe" in msg and "Quiet for 1d 6h" in msg


def test_the_waiting_message_still_wins_when_it_is_older():
    msg = build_focus_message(_config(), _queue(79), {}, NOW, state=_state(30))
    assert msg.startswith("━") and "Reply to this next" in msg and "Magni Guard" in msg


def test_a_prioritised_campaign_with_a_reply_owed_still_wins_outright():
    msg = build_focus_message(_config(), _queue(2), {MAGNI: 1}, NOW, state=_state(9 * 24))
    assert "Reply to this next" in msg and "Magni Guard" in msg


def test_a_campaign_with_no_recorded_post_never_competes():
    """days=inf would otherwise win forever and bury every real reply."""
    assert pick_idle_focus(_config(), {"topics": {}}, _queue(5), {}, NOW) is None


def test_an_empty_queue_is_left_to_the_oldest_campaign_callout():
    assert build_focus_message(_config(), {}, {}, NOW, state=_state(9 * 24)) == ""


def test_without_state_the_old_behaviour_is_unchanged():
    msg = build_focus_message(_config(), _queue(28), {}, NOW)
    assert "Reply to this next" in msg and "Magni Guard" in msg


def test_the_dm_key_follows_the_idle_target():
    cfg, q = _config(), _queue(28)
    assert focus_key(q, {}, config=cfg, state=_state(6 * 24), now=NOW) == f"idle:{KIBWE}"
    assert focus_key(q, {}, config=cfg, state=_state(10), now=NOW) == MAGNI_OLDEST
