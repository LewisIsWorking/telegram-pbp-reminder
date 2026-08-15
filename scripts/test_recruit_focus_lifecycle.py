"""Recruit focus post — lifecycle (2026-08-15).

Split from ``test_recruit_focus.py``, which reached 239 lines. That file
asks *which campaign gets named*; this one asks *how the message lives
and dies* — the 24h gate, the self-delete, and refusing to delete when
the replacement never sent.

The two state keys behind that lifecycle are guarded mechanically
elsewhere and deliberately not re-asserted here:
``test_state_keys_are_declared`` proves both survive a save/load cycle,
and ``test_bot_sent_scan_covers_state`` proves the message id reaches the
bot-sent registry so ``perform_guarded_delete`` will permit the delete.
Those are the exact two omissions that duplicated the schedule post.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from test_recruit_focus import _NOW, _cfg, _pair, _state  # noqa: E402


class TestPosting:
    def _fire(self, monkeypatch, state, now=_NOW, cfg=None):
        import telegram as tg
        from scheduled.recruit_focus import post_recruit_focus
        sent, deleted = [], []
        monkeypatch.setattr(tg, "send_message_id",
                            lambda g, t, b, **k: sent.append((t, b, k)) or 4242)
        monkeypatch.setattr(tg, "delete_message",
                            lambda g, m: deleted.append(m) or True)
        cfg = cfg or _cfg(_pair("C01", "100", target=6))
        state.update(_state(**{"100": 5}))
        post_recruit_focus(cfg, state, now=now)
        return sent, deleted

    def test_posts_to_the_gm_queue_topic(self, monkeypatch):
        sent, _ = self._fire(monkeypatch, {})
        assert sent and sent[0][0] == 146780

    def test_is_silent(self, monkeypatch):
        """One a day, but still no reason to ping."""
        sent, _ = self._fire(monkeypatch, {})
        assert sent[0][2].get("silent") is True

    def test_deletes_its_predecessor(self, monkeypatch):
        sent, deleted = self._fire(monkeypatch, {"recruit_focus_msg_id": 999})
        assert deleted == [999]

    def test_records_the_new_id_and_timestamp(self, monkeypatch):
        state = {}
        self._fire(monkeypatch, state)
        assert state["recruit_focus_msg_id"] == 4242
        assert state["last_recruit_focus"] == _NOW.isoformat()

    def test_does_not_repost_within_24h(self, monkeypatch):
        state = {"last_recruit_focus": (_NOW - timedelta(hours=23)).isoformat()}
        sent, _ = self._fire(monkeypatch, state)
        assert sent == []

    def test_reposts_after_24h(self, monkeypatch):
        state = {"last_recruit_focus": (_NOW - timedelta(hours=25)).isoformat()}
        sent, _ = self._fire(monkeypatch, state)
        assert sent

    def test_unparseable_timestamp_does_not_wedge_it_shut(self, monkeypatch):
        """A corrupt gate must fail open, or the post never returns."""
        sent, _ = self._fire(monkeypatch, {"last_recruit_focus": "not a date"})
        assert sent

    def test_send_failure_keeps_the_old_post(self, monkeypatch):
        import telegram as tg
        from scheduled.recruit_focus import post_recruit_focus
        deleted = []
        monkeypatch.setattr(tg, "send_message_id", lambda *a, **k: None)
        monkeypatch.setattr(tg, "delete_message",
                            lambda g, m: deleted.append(m) or True)
        state = {"recruit_focus_msg_id": 999}
        state.update(_state(**{"100": 5}))
        post_recruit_focus(_cfg(_pair("C01", "100", target=6)), state,
                           now=_NOW)
        assert deleted == [], "never delete when the replacement failed"
        assert state["recruit_focus_msg_id"] == 999

    def test_nothing_short_posts_nothing(self, monkeypatch):
        import telegram as tg
        from scheduled.recruit_focus import post_recruit_focus
        sent = []
        monkeypatch.setattr(tg, "send_message_id",
                            lambda g, t, b, **k: sent.append(b) or 1)
        state = dict(_state(**{"100": 6}))
        post_recruit_focus(_cfg(_pair("C01", "100", target=6)), state,
                           now=_NOW)
        assert sent == []

    def test_can_be_disabled(self, monkeypatch):
        cfg = _cfg(_pair("C01", "100", target=6))
        cfg["recruit_focus_enabled"] = False
        sent, _ = self._fire(monkeypatch, {}, cfg=cfg)
        assert sent == []
