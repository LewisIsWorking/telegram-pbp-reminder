"""An unchanged GM queue is edited in place, so it visibly stays alive.

Lewis, 2026-09-13: "The bot doesn't seem to be firing per half hour now, the
queue isn't updating." It was running and updating on every real change, but
the fix that stopped the queue reposting hourly had also removed the only
visible sign the bot was alive. A healthy quiet queue looked like a dead one.

Three things here would break silently, and each has a test that can fail:

1. **A shifted batch.** ``post_batch`` records a chunk's id only if the chunk
   SENT, so one earlier failure leaves the ids a position short. Pairing by
   index would write one message's text into another's.
2. **"Message is not modified".** Only the first message carries the Checked
   time. Re-sending an unchanged message gets that error, which counts as a
   failure, and the queue would repost almost every run.
3. **Renumbering.** A refresh must keep the current "GM Queue #N". Rendering
   count+1, as a repost does, renumbers a queue that has not changed.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from _test_queue_post_fakes import edit_ok, faithful_post_and_persist
from scheduled.queue_refresh import checked_line, refresh_in_place
from test_core_scheduled import _qr_config

G = -1001


def _batch(ids):
    return {"gm_queue_history": [{"msg_ids": ids, "pin_id": ids[0]}]}


class _Edit:
    def __init__(self, refuse=()):
        self.refuse, self.calls = set(refuse), []

    def __call__(self, chat_id, message_id, text, **_kw):
        self.calls.append((message_id, text))
        return message_id not in self.refuse


class TestItRefreshes:
    def test_a_changed_message_is_edited(self):
        state = _batch([1, 2]) | {"gm_queue_texts": ["old head", "body"]}
        edit = _Edit()
        assert refresh_in_place(state, G, ["new head", "body"], edit=edit)
        assert edit.calls == [(1, "new head")]

    def test_the_new_texts_are_remembered(self):
        state = _batch([1, 2]) | {"gm_queue_texts": ["a", "b"]}
        refresh_in_place(state, G, ["a2", "b"], edit=_Edit())
        assert state["gm_queue_texts"] == ["a2", "b"]


class TestItSkipsUnchangedMessages:
    def test_identical_text_is_never_resent(self):
        """⛔⛔ #2. Re-sending an unchanged message returns "message is not
        modified", edit_message reports that as failure, and the refresh
        falls back to a repost. Most runs would repost."""
        state = _batch([1, 2, 3]) | {"gm_queue_texts": ["head", "body", "focus"]}
        edit = _Edit()
        assert refresh_in_place(state, G, ["head 2", "body", "focus"], edit=edit)
        assert [mid for mid, _ in edit.calls] == [1], "resent unchanged messages"

    def test_with_nothing_remembered_every_message_is_edited(self):
        """The first run after this ships has no stored texts."""
        edit = _Edit()
        assert refresh_in_place(_batch([1, 2]), G, ["x", "y"], edit=edit)
        assert [mid for mid, _ in edit.calls] == [1, 2]


class TestItFallsBackToARepost:
    def test_a_shifted_batch_is_not_edited(self):
        """⛔⛔ #1. Three chunks rendered, but only two ids recorded because
        one earlier chunk failed to send. Pairing by index would put the
        wrong text in the wrong message."""
        edit = _Edit()
        assert not refresh_in_place(_batch([1, 3]), G, ["a", "b", "c"], edit=edit)
        assert edit.calls == [], "edited a batch whose ids no longer line up"

    def test_no_batch_means_repost(self):
        assert not refresh_in_place({}, G, ["a"], edit=_Edit())

    def test_a_refused_edit_means_repost(self):
        """Telegram's edit limit is not reliably documented. Whatever the
        reason for a refusal, the answer is a fresh message."""
        state = _batch([1]) | {"gm_queue_texts": ["old"]}
        assert not refresh_in_place(state, G, ["new"], edit=_Edit(refuse={1}))

    def test_a_partial_success_still_reposts_and_forgets_nothing(self):
        state = _batch([1, 2]) | {"gm_queue_texts": ["a", "b"]}
        assert not refresh_in_place(state, G, ["a2", "b2"],
                                    edit=_Edit(refuse={2}))
        assert state["gm_queue_texts"] == ["a", "b"], \
            "a failed refresh must not record texts Telegram never accepted"


def test_the_checked_line_reads_in_local_time():
    assert checked_line(datetime(2026, 9, 13, 19, 32, tzinfo=timezone.utc)) \
        == "🕒 Checked 20:32 BST"


class TestThroughTheRealQueuePost:
    """Every test above calls the module directly. These go through
    post_queue_reminder, which is where the renumbering trap lives."""

    def _run(self, state, now, edit=edit_ok, post=faithful_post_and_persist):
        # ⚠️ The post and edit fakes are PARAMETERS, not patched by callers.
        # A caller wrapping this in its own patch of post_and_persist is
        # shadowed by the patch below, so its fake never runs. That made the
        # "repost stops recording texts" test vacuous until a mutation run
        # showed it could not fail.
        entries = [{"name": "Alice", "time": "2026-04-03 08:00:00",
                    "preview": "hi", "link": "", "message_id": "1"}]
        scanned = {"100": {"campaign": "Kibwe", "code": "C00",
                           "entries": entries}}
        with patch("scheduled.queue_reminder.scan_transcripts",
                   return_value=scanned), \
             patch("scheduled.queue_reminder.post_topic_queues"), \
             patch("scheduled.queue_reminder.send_focus_dm", return_value=False), \
             patch("scheduled.queue_reminder.post_and_persist",
                   side_effect=post) as posted, \
             patch("scheduled.queue_reminder.tg.edit_message",
                   side_effect=edit) as edits:
            from scheduled.queue_reminder import post_queue_reminder
            post_queue_reminder(_qr_config(), state, now=now)
        return posted, edits

    def _fresh(self):
        return {"last_queue_fingerprint": "OLD", "queue_post_count": 41,
                "last_queue_pin_id": None,
                "last_queue_daily_slots": ["2026-04-03:09"]}

    def test_a_refresh_keeps_the_queue_number(self):
        """⛔⛔ #3."""
        state = self._fresh()
        t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        self._run(state, t1)
        assert state["queue_post_count"] == 42
        _posted, edits = self._run(state, t1.replace(minute=30))
        heads = [c.args[2] for c in edits.call_args_list if "GM Queue" in c.args[2]]
        assert heads and all("#42" in h for h in heads), heads
        assert not any("#43" in h for h in heads), "a refresh renumbered the queue"
        assert state["queue_post_count"] == 42

    def test_the_refreshed_head_carries_the_checked_time(self):
        """The heartbeat itself: visible on the pinned message."""
        state = self._fresh()
        t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        self._run(state, t1)
        _posted, edits = self._run(state, t1.replace(minute=30))
        assert any("Checked 11:30 BST" in c.args[2]
                   for c in edits.call_args_list)

    def test_after_a_repost_unchanged_messages_are_not_resent(self):
        """⛔ The edit fake above accepts everything, so it could not see this.
        This one refuses identical text, as Telegram does. If a repost stopped
        recording what it sent, the next refresh would re-send unchanged
        messages, be refused, and repost on every single run."""
        held = {}

        def post(state, group_id, bot_topic, msgs, pin=True):
            batch = faithful_post_and_persist(state, group_id, bot_topic, msgs)
            ids = state["gm_queue_history"][-1]["msg_ids"]
            held.update(zip(ids, msgs))
            return batch

        def telegram_edit(chat_id, message_id, text, **_kw):
            if held.get(message_id) == text:
                return False  # "message is not modified"
            held[message_id] = text
            return True

        state = self._fresh()
        t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        self._run(state, t1, post=post, edit=telegram_edit)
        assert held, "the Telegram-like fake never recorded the first post"
        posted, _ = self._run(state, t1.replace(minute=30),
                              post=post, edit=telegram_edit)
        assert posted.call_count == 0, "an unchanged run reposted"
        assert state["queue_post_count"] == 42

    def test_a_refused_refresh_reposts_with_the_next_number(self):
        state = self._fresh()
        t1 = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
        self._run(state, t1)
        posted, _ = self._run(state, t1.replace(minute=30),
                              edit=lambda *a, **k: False)
        assert posted.call_count == 1
        assert state["queue_post_count"] == 43
