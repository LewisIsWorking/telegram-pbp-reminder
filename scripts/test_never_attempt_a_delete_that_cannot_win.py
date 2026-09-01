"""Past the 48h wall, edit the message instead of orphaning it.

Lewis, 2026-09-01, on the third batch of stranded queue posts:
*"this needs fixing, this is a big issue."* It is, and hand-deleting
them was never the fix.

## What was actually wrong

Telegram will not let a bot delete its own message after 48 hours.
Admin rights do not lift it. The queue updates itself by **delete the
old, post the new**, so every queue post carried a 48h fuse, and the 36h
republish in ``topic_queue_age`` existed only to keep relighting it.

That mitigation cannot survive a missed run. When the bot was down 15
hours the messages crossed the wall, and then the code **attempted the
delete anyway**:

```
175996, 175998, 176000 — 57.5h old, deleted 0 of 3, orphaned 3 of 3
```

⭐⭐ **The question never asked was: can this delete possibly succeed?**
When the answer is no, attempting it is not a risk, it is a loss that has
already happened.

## The fix

**Editing has no time limit. Deleting does.** Past the wall the message
is REUSED rather than abandoned: the queue is edited in place, and the
caught-up notice is the same message edited again. One message per
thread, kept current forever, nothing stranded.

⚠️ Nothing here changes behaviour for a message inside the window. The
normal path still deletes and reposts, which is what keeps the
notification on a real content change.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from posting.message_batch import MessageBatch
from scheduled.topic_queue_age import (SAFE_TO_DELETE, can_still_delete,
                                       batch_is_stale)

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _slot(hours_old=None, **extra):
    slot = {"msg_ids": [900], "fingerprint": "old", "last_posted_at": None}
    if hours_old is not None:
        slot["last_posted_at"] = (_NOW - timedelta(hours=hours_old)).isoformat()
    slot.update(extra)
    return slot


class TestTheQuestionThatWasNeverAsked:
    def test_a_fresh_batch_can_still_be_deleted(self):
        assert can_still_delete(_slot(2), _NOW)

    def test_a_batch_past_the_wall_cannot(self):
        # ⭐⭐ The real 2026-08-31 reading: 57.5 hours old.
        assert not can_still_delete(_slot(57.5), _NOW)

    def test_the_boundary_is_where_it_is_documented(self):
        assert can_still_delete(_slot(SAFE_TO_DELETE.total_seconds() / 3600 - 0.1), _NOW)
        assert not can_still_delete(_slot(SAFE_TO_DELETE.total_seconds() / 3600 + 0.1), _NOW)

    def test_the_margin_sits_under_telegrams_wall(self):
        # ⚠️ The check runs at the start of a run and the delete lands
        # seconds later, so the threshold must not be the wall itself.
        assert SAFE_TO_DELETE < timedelta(hours=48)

    def test_an_unknown_age_reads_as_deletable(self):
        # ⛔ Deliberate. A slot predating the field is almost certainly
        # fresh, and failing closed would put every legacy slot into
        # edit-only mode permanently, which is the opposite of the point.
        assert can_still_delete({"msg_ids": [1]}, _NOW)

    def test_it_is_a_different_question_from_staleness(self):
        # ⭐ 40h is stale (past the 36h republish) but still deletable.
        # Conflating the two is what made the old code republish right up
        # to the wall and then attempt the doomed delete.
        slot = _slot(40)
        assert batch_is_stale(slot, _NOW) and can_still_delete(slot, _NOW)


class TestEditingReplacesTheDoomedDelete:
    def _tg(self, monkeypatch, edit_ok=True):
        import telegram as tg
        calls = {"edit": [], "delete": []}
        monkeypatch.setattr(tg, "edit_message",
                            lambda c, m, t, **k: calls["edit"].append((m, t)) or edit_ok)
        monkeypatch.setattr(tg, "delete_message",
                            lambda c, m: calls["delete"].append(m) or True)
        return calls

    def test_every_chunk_is_edited(self, monkeypatch):
        calls = self._tg(monkeypatch)
        batch = MessageBatch(msg_ids=[10, 11], pin_id=10)
        assert batch.edit_all(-100, ["a", "b"])
        assert calls["edit"] == [(10, "a"), (11, "b")]
        assert calls["delete"] == [], "editing must not delete anything"

    def test_a_changed_chunk_count_refuses_rather_than_half_doing_it(self, monkeypatch):
        # ⚠️ Rewriting only the first two of three would silently drop
        # content. The caller is told instead.
        calls = self._tg(monkeypatch)
        assert not MessageBatch(msg_ids=[10, 11]).edit_all(-100, ["a", "b", "c"])
        assert not MessageBatch(msg_ids=[10, 11]).edit_all(-100, ["a"])

    def test_an_empty_batch_cannot_be_edited(self, monkeypatch):
        self._tg(monkeypatch)
        assert not MessageBatch(msg_ids=[]).edit_all(-100, ["a"])

    def test_a_failed_edit_is_reported(self, monkeypatch):
        self._tg(monkeypatch, edit_ok=False)
        assert not MessageBatch(msg_ids=[10]).edit_all(-100, ["a"])
