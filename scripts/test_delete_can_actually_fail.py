"""A refused delete must be recorded as a failure, and must be retried.

COVERS  ``posting.safe_delete.perform_guarded_delete`` outcome reporting,
        and the bounded give-up in ``posting.stuck_deletes``.
MISSES  Whether Telegram actually refuses a given message. That depends
        on the bot's admin rights and the 48h window, and cannot be
        determined without a live API call — see the note at the bottom.
ANCHORED to ``safe_delete.ALREADY_GONE_ERRORS`` rather than a retyped
        copy of it, so the two cannot drift apart again.
PROVEN  by ``test_the_guard_can_fail`` below, which restores the old
        suppression string and asserts these tests go red.

The bug, 2026-08-16. ``"message can't be deleted"`` sat in the
``suppress_errors`` tuple, so Telegram declining a delete came back from
``_post`` as ``True``. Every caller reads that as success: the tracked
slot is cleared, the ID is never parked in ``pending_delete``, and the
message stays in the chat forever. The pin audit held 715 deletes and
715 successes — no delete had ever failed in the bot's recorded history —
while a C06 ``Unreplied: 2`` post from 2026-08-03 was still sitting in
the topic thirteen days later.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from posting import safe_delete
from posting.safe_delete import ALREADY_GONE_ERRORS, perform_guarded_delete

CHAT = -1001661053273
MID = 170029  # the real C06 message that survived its own deletion


def _resp(status: int, body: str) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json.loads(body)
    m.text = body
    return m


@pytest.fixture
def clean_stuck(tmp_path, monkeypatch):
    """Isolate the stuck-delete log so tests never touch real state."""
    from posting import stuck_deletes
    from state_store import StateStore
    monkeypatch.setattr(stuck_deletes, "_store", StateStore(state_dir=tmp_path))
    stuck_deletes.reset_for_test()
    return stuck_deletes


def _post_returning(body: str, status: int = 400):
    """A stand-in for ``telegram._post`` that mimics the real suppression."""
    def fake(method, payload, label="request", suppress_errors=()):
        if status == 200:
            return json.loads(body).get("result")
        if any(s in body for s in suppress_errors):
            return True
        return None
    return fake


# ── The bug itself ───────────────────────────────────────────────────────────

def test_refused_delete_reports_failure(clean_stuck, monkeypatch):
    """Telegram saying it will not delete must NOT read as success."""
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    body = '{"ok":false,"description":"Bad Request: message can\'t be deleted"}'
    with patch.object(safe_delete, "record_action"):
        result = perform_guarded_delete(CHAT, MID, _post_returning(body))
    assert result is False, (
        "'message can't be deleted' means the message is still in the chat. "
        "Returning True here is what orphaned the 2026-08-03 C06 post.")


def test_refused_delete_is_counted_for_retry(clean_stuck, monkeypatch):
    """A failure must leave a trace, or nothing can ever retry it."""
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    body = '{"ok":false,"description":"Bad Request: message can\'t be deleted"}'
    with patch.object(safe_delete, "record_action"):
        perform_guarded_delete(CHAT, MID, _post_returning(body))
    log = clean_stuck._load()
    assert str(MID) in log
    assert log[str(MID)]["attempts"] == 1
    assert log[str(MID)]["hopeless"] is False


def test_audit_records_ok_false_on_refusal(clean_stuck, monkeypatch):
    """The pin audit must be able to show a failed delete.

    Before the fix its outcome column had exactly one value across 1393
    rows. A trail that cannot record a negative is not evidence.
    """
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    body = '{"ok":false,"description":"Bad Request: message can\'t be deleted"}'
    with patch.object(safe_delete, "record_action") as audit:
        perform_guarded_delete(CHAT, MID, _post_returning(body))
    assert audit.call_args.kwargs["ok"] is False


# ── The already-gone cases must still be soft success ────────────────────────

@pytest.mark.parametrize("pattern", ALREADY_GONE_ERRORS)
def test_already_gone_still_counts_as_success(pattern, clean_stuck, monkeypatch):
    """Removing one suppression must not remove the legitimate ones.

    These three genuinely mean the message is no longer there, which is
    the outcome the caller wanted. Regressing them brings back the
    2026-05-10 bug: GM queue batches stuck past max_kept.
    """
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    body = f'{{"ok":false,"description":"Bad Request: {pattern}"}}'
    with patch.object(safe_delete, "record_action"):
        assert perform_guarded_delete(CHAT, MID, _post_returning(body)) is True
    assert clean_stuck._load() == {}, "an already-gone message is not stuck"


def test_undeletable_string_is_not_treated_as_gone():
    """The exact string that caused the bug must stay off the list."""
    assert "message can't be deleted" not in ALREADY_GONE_ERRORS


# The bounded give-up that replaces the old infinite-retry worry, and the
# pending_delete sweep, live in ``test_delete_gives_up.py`` — split out
# 2026-08-16 when this file hit 224 lines.


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_guard_can_fail(clean_stuck, monkeypatch):
    """Feed the guard the actual bug and confirm it goes red.

    Per ``guards-that-mean-something``: a test suite that passes is only
    evidence if it would have failed. This restores the pre-fix
    suppression tuple and asserts the outcome flips to the wrong answer,
    which is what the whole file exists to prevent.
    """
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    monkeypatch.setattr(
        safe_delete, "ALREADY_GONE_ERRORS",
        ALREADY_GONE_ERRORS + ("message can't be deleted",))
    body = '{"ok":false,"description":"Bad Request: message can\'t be deleted"}'
    with patch.object(safe_delete, "record_action"):
        result = perform_guarded_delete(CHAT, MID, _post_returning(body))
    assert result is True, (
        "With the old tuple restored the refusal reads as success — that is "
        "the bug. If this assertion fails, perform_guarded_delete no longer "
        "reads ALREADY_GONE_ERRORS and these tests are checking nothing.")


# ⚠️ WHAT THIS FILE CANNOT TELL YOU
# --------------------------------
# Whether Telegram refuses a given delete depends on the bot's rights in
# the group and on the 48h window for non-admins. Every one of the 15
# over-48h deletes in the pin audit reported success, which is consistent
# both with "the bot is an admin and they all worked" and with "the bot
# is not an admin and none of them did". The audit could not tell those
# apart, which is exactly the defect. From the next run onward it can:
# a real refusal now lands in stuck_deletes with a timestamp.
