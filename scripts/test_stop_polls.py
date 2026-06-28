"""Tests for the two opt-out flags that stop polls in the Dark Pockets group.

* ``swimming_poll_enabled: false`` (top-level) stops the weekly 🏊 swimming
  poll + its daily pings.
* ``session_poll_disabled: true`` on a hybrid campaign (C11) stops its session
  poll, daily nudges, and Friday result announcement — without flipping
  ``hybrid_live`` (which also drives campaign-table labelling / warnings).

Both default to current behaviour, so existing tests are unaffected.
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

_SUNDAY_8AM = datetime(2026, 3, 29, 8, tzinfo=timezone.utc)
_FRIDAY_3PM = datetime(2026, 4, 3, 15, tzinfo=timezone.utc)


# ── swimming poll opt-out ────────────────────────────────────────────────────

def test_swimming_poll_disabled_does_not_post():
    from scheduled.swimming_poll import post_swimming_poll
    cfg = {"swimming_poll_enabled": False, "poll_post_hour": 7}
    with patch("scheduled.swimming_poll.tg.send_poll") as m_poll:
        post_swimming_poll(cfg, {}, now=_SUNDAY_8AM)
    m_poll.assert_not_called()


def test_swimming_poll_enabled_by_default_still_posts():
    from scheduled.swimming_poll import post_swimming_poll
    cfg = {"poll_post_hour": 7}  # flag absent -> default enabled
    with patch("scheduled.swimming_poll.tg.send_poll",
               return_value=(1, "pid")) as m_poll, \
         patch("scheduled.swimming_poll.tg.pin_message"):
        post_swimming_poll(cfg, {}, now=_SUNDAY_8AM)
    m_poll.assert_called_once()


def test_swimming_ping_disabled_does_not_send():
    from scheduled.swimming_poll import post_swimming_ping
    cfg = {"swimming_poll_enabled": False}
    state = {"swimming_poll": {"week_iso": "x", "voted_uids": [],
                               "last_ping_day": -1}}
    with patch("scheduled.swimming_poll.tg.send_message") as m_send:
        post_swimming_ping(cfg, state, now=_SUNDAY_8AM)
    m_send.assert_not_called()


# ── C11 session-poll opt-out ─────────────────────────────────────────────────

def _c11_config():
    return {"group_id": -1, "poll_post_hour": 7, "topic_pairs": [{
        "code": "C11", "name": "Dark Pockets", "pbp_topic_ids": [1242],
        "chat_topic_id": 2321, "hybrid_live": True,
        "session_poll_disabled": True,
        "poll_options": ["Friday"], "poll_user_ids": [111]}]}


def test_session_poll_disabled_skips_campaign():
    from scheduled.session_poll import post_session_poll
    state = {}
    with patch("scheduled.session_poll._post_one") as m_post:
        post_session_poll(_c11_config(), state, now=_SUNDAY_8AM)
    m_post.assert_not_called()


def test_poll_result_skips_disabled_campaign():
    from scheduled.poll_result import announce_poll_result
    state = {"session_poll": {"C11": {"poll_id": "p", "options": ["Friday"],
                                      "votes": {}}}}
    with patch("scheduled.poll_result.tg.send_message") as m_send:
        announce_poll_result(_c11_config(), state, now=_FRIDAY_3PM)
    m_send.assert_not_called()
