"""The focus-DM target key, and that the DM is wired into the real queue post.

Split from test_focus_message_is_dmed_on_change.py on 2026-09-13 at 235 lines.
"""

from unittest.mock import patch

from _test_focus_dm_helpers import (GM, MAGNI_OLDEST, NOW, RIDDLE, config,
                                    entry, scanned, two_campaigns)
from scheduled.queue_focus import focus_key

_FRESH = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
          "last_queue_daily_slots": []}


class TestTheKey:
    def test_it_identifies_the_message_not_the_campaign(self):
        assert focus_key(two_campaigns(), {}) == MAGNI_OLDEST

    def test_priority_is_honoured_exactly_as_the_message_honours_it(self):
        """The key and the message must pick the same target, or the DM would
        announce one message and link another."""
        assert focus_key(two_campaigns(), {"66154": 1}) == RIDDLE

    def test_an_entry_without_a_link_still_gets_a_stable_key(self):
        queue = scanned(("144765", "Magni Guard", "C04", [entry("", 5)]))
        key = focus_key(queue, {})
        assert key and key == focus_key(queue, {})

    def test_nothing_owed_has_no_key(self):
        assert focus_key({}, {}) is None


class TestItIsWiredIntoTheRealQueuePost:
    """⛔ Every test in the sibling file calls the module directly. A module
    nobody calls passes all of them. These go through post_queue_reminder."""

    def _run(self, posted_ok):
        with patch("scheduled.queue_reminder.scan_transcripts",
                   return_value=two_campaigns()), \
             patch("scheduled.queue_reminder.post_topic_queues"), \
             patch("scheduled.queue_reminder.post_and_persist",
                   return_value=(posted_ok, 1 if posted_ok else None)), \
             patch("scheduled.queue_reminder.tg.send_message",
                   return_value=True) as sent:
            from scheduled.queue_reminder import post_queue_reminder
            post_queue_reminder(config() | {"queue_daily_hours": [9, 21]},
                                dict(_FRESH), now=NOW)
        return [c for c in sent.call_args_list if c.args[0] == GM]

    def test_a_queue_post_dms_the_gm(self):
        dms = self._run(posted_ok=True)
        assert len(dms) == 1
        assert "🎯 Reply to this next:" in dms[0].args[2]

    def test_a_failed_group_post_does_not_dm(self):
        """Kept consistent with the queue: no group post, no DM."""
        assert self._run(posted_ok=False) == []
