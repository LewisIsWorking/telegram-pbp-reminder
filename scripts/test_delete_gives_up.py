"""The bot must stop asking Telegram to delete what it cannot delete.

COVERS  ``posting.stuck_deletes`` — the bounded give-up, the one-time
        alert, the manual clear, and the ``pending_delete`` sweep in
        ``scheduled.topic_queue_state.retry_pending_deletes``.
MISSES  Whether the give-up threshold is the right number. Four attempts
        is a judgement call about Telegram outage length, not a fact any
        test can settle.
PROVEN  by ``test_the_sweep_can_fail``, which removes the drop and
        asserts the sweep test goes red.

Split from ``test_delete_can_actually_fail.py`` on 2026-08-16 at 224
lines. That file owns "a refused delete is reported as a failure"; this
one owns "and then the bot gives up gracefully". They are two behaviours
that happen to share a bug, and the 200-line cap is what forced the
distinction to be made explicit.

Why a give-up exists at all: ``"message can't be deleted"`` used to be
suppressed as a soft success, on the reasoning that the message will
never delete so retrying is pointless. The reasoning was right and the
remedy was wrong — it lied about the outcome instead of bounding the
retry. This is the bound, with the outcome left honest.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from posting import safe_delete
from posting.safe_delete import perform_guarded_delete

CHAT = -1001661053273
MID = 170029  # the real C06 message that survived its own deletion

REFUSED_BODY = '{"ok":false,"description":"Bad Request: message can\'t be deleted"}'


@pytest.fixture
def clean_stuck(tmp_path, monkeypatch):
    """Isolate the stuck-delete log so tests never touch real state."""
    from posting import stuck_deletes
    from state_store import StateStore
    monkeypatch.setattr(stuck_deletes, "_store", StateStore(state_dir=tmp_path))
    stuck_deletes.reset_for_test()
    return stuck_deletes


def _post_returning(body: str):
    """A stand-in for ``telegram._post`` that mimics the real suppression."""
    def fake(method, payload, label="request", suppress_errors=()):
        if any(s in body for s in suppress_errors):
            return True
        return None
    return fake


def _refuse_n_times(n: int, stuck, monkeypatch):
    """Drive n refused deletes for MID through the production path."""
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    with patch.object(safe_delete, "record_action"), \
            patch.object(safe_delete, "record_refusal"):
        for _ in range(n):
            perform_guarded_delete(CHAT, MID, _post_returning(REFUSED_BODY))


# ── The bound ────────────────────────────────────────────────────────────────

def test_bot_gives_up_after_max_attempts(clean_stuck, monkeypatch):
    """Retrying forever was the real problem with reporting failure."""
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS, clean_stuck, monkeypatch)
    assert clean_stuck.is_hopeless(MID) is True
    assert clean_stuck.hopeless_ids() == [MID]


def test_bot_keeps_trying_below_the_threshold(clean_stuck, monkeypatch):
    """A transient failure must NOT be mistaken for a permanent one.

    The positive counterpart to the test above: without it, a give-up on
    the first failure would pass every other test in this file while
    abandoning messages a single retry would have removed.
    """
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS - 1, clean_stuck, monkeypatch)
    assert clean_stuck.is_hopeless(MID) is False
    assert clean_stuck.hopeless_ids() == []


def test_hopeless_id_makes_no_http_call(clean_stuck, monkeypatch):
    """Once given up on, the ID must cost nothing on every later run."""
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS, clean_stuck, monkeypatch)
    called = []

    def spy(*a, **k):
        called.append(a)
        return None

    assert perform_guarded_delete(CHAT, MID, spy) is False
    assert called == [], "a hopeless ID must not reach Telegram again"


def test_attempts_are_tracked_per_message(clean_stuck, monkeypatch):
    """One stuck message must not condemn an unrelated one."""
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS, clean_stuck, monkeypatch)
    assert clean_stuck.is_hopeless(999999) is False


# ── The alert ────────────────────────────────────────────────────────────────

def test_giving_up_alerts_exactly_once(clean_stuck, monkeypatch):
    """The operator must hear about it, and must hear about it once."""
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: True)
    with patch.object(safe_delete, "record_action"), \
            patch("posting.stuck_deletes.record_refusal") as alert:
        for _ in range(clean_stuck.MAX_ATTEMPTS + 3):
            perform_guarded_delete(CHAT, MID, _post_returning(REFUSED_BODY))
    assert alert.call_count == 1


def test_give_up_names_the_message_in_the_log(clean_stuck, monkeypatch, capsys):
    """A silent give-up is the bug wearing a different hat.

    The whole defect was a failure nobody could see. If the bot abandons
    a message it must say which message, or the operator is back to
    discovering it by scrolling the topic thirteen days later.
    """
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS, clean_stuck, monkeypatch)
    out = capsys.readouterr().out
    assert "GIVING UP" in out
    assert str(MID) in out


# ── Recovery ─────────────────────────────────────────────────────────────────

def test_clearing_a_stuck_id_lets_the_bot_try_again(clean_stuck, monkeypatch):
    """A human deleting the message by hand must not leave state wrong."""
    _refuse_n_times(clean_stuck.MAX_ATTEMPTS, clean_stuck, monkeypatch)
    clean_stuck.clear_stuck(MID)
    assert clean_stuck.is_hopeless(MID) is False
    assert clean_stuck.hopeless_ids() == []


def test_first_and_last_seen_are_both_recorded(clean_stuck, monkeypatch):
    """"Failing since 2026-08-03" and "failing since an hour ago" want
    different responses, and the attempt count alone cannot tell them
    apart."""
    _refuse_n_times(2, clean_stuck, monkeypatch)
    entry = clean_stuck._load()[str(MID)]
    assert entry["first_seen"] <= entry["last_seen"]
    assert entry["attempts"] == 2


# ── The sweep ────────────────────────────────────────────────────────────────

def test_retry_sweep_drops_hopeless_ids(monkeypatch):
    """pending_delete is append-only for anything permanently stuck."""
    from scheduled import topic_queue_state as tqs
    monkeypatch.setattr(tqs, "is_hopeless", lambda mid: mid == MID)
    slot = {"pending_delete": [MID, 999]}
    with patch("posting.message_batch.tg.delete_message", return_value=False):
        tqs.retry_pending_deletes(slot, CHAT)
    assert slot["pending_delete"] == [999], (
        "the hopeless ID is recorded in stuck_deletes; keeping it here too "
        "means an API call every run forever")


def test_retry_sweep_keeps_ids_still_worth_retrying(monkeypatch):
    """The positive counterpart — the sweep must not drop everything."""
    from scheduled import topic_queue_state as tqs
    monkeypatch.setattr(tqs, "is_hopeless", lambda mid: False)
    slot = {"pending_delete": [MID, 999]}
    with patch("posting.message_batch.tg.delete_message", return_value=False):
        tqs.retry_pending_deletes(slot, CHAT)
    assert slot["pending_delete"] == [MID, 999]


def test_retry_sweep_clears_ids_that_succeed(monkeypatch):
    """And a delete that works must leave nothing behind."""
    from scheduled import topic_queue_state as tqs
    monkeypatch.setattr(tqs, "is_hopeless", lambda mid: False)
    slot = {"pending_delete": [MID, 999]}
    with patch("posting.message_batch.tg.delete_message", return_value=True):
        tqs.retry_pending_deletes(slot, CHAT)
    assert slot["pending_delete"] == []


def test_the_sweep_can_fail(monkeypatch):
    """Feed the sweep the pre-fix behaviour and confirm it goes red.

    Per ``guards-that-mean-something``: prove the guard by feeding it the
    bug. With is_hopeless always False — which is what the code did
    before this change, because nothing ever recorded a failure — the
    hopeless ID survives the sweep and grows the list forever.
    """
    from scheduled import topic_queue_state as tqs
    monkeypatch.setattr(tqs, "is_hopeless", lambda mid: False)
    slot = {"pending_delete": [MID, 999]}
    with patch("posting.message_batch.tg.delete_message", return_value=False):
        tqs.retry_pending_deletes(slot, CHAT)
    assert slot["pending_delete"] == [MID, 999], (
        "If this fails, retry_pending_deletes no longer consults "
        "is_hopeless and test_retry_sweep_drops_hopeless_ids is vacuous.")
