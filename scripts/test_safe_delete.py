"""Tests for posting.safe_delete — the guarded deletion/unpin paths.

Verifies that both safety guards (delete and unpin):
  * Refuse (return False, call no API) when the ID is unknown
  * Let through (call the post function) when the ID is registered
  * Print a diagnostic refusal line
"""

from unittest.mock import MagicMock

import pytest

from posting import bot_sent_registry as reg
from posting import refusal_log as rl
from posting import pin_audit as pa
from posting.safe_delete import perform_guarded_delete, perform_guarded_unpin
from state_store import StateStore


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    test_store = StateStore(state_dir=tmp_path)
    monkeypatch.setattr(reg, "_store", test_store)
    monkeypatch.setattr(rl, "_store", test_store)
    monkeypatch.setattr(pa, "_store", test_store)
    reg.reset_for_test()
    rl.reset_for_test()
    pa.reset_for_test()
    yield
    reg.reset_for_test()
    rl.reset_for_test()
    pa.reset_for_test()


def test_refuses_unknown_id_no_api_call():
    """An ID not in the registry → False return, post_fn not called."""
    post_fn = MagicMock(return_value={"ok": True})
    result = perform_guarded_delete(-1001, 99999, post_fn)
    assert result is False
    post_fn.assert_not_called()


def test_refused_call_prints_diagnostic(capsys):
    """The refusal path emits a print line so logs show it happened."""
    post_fn = MagicMock(return_value={"ok": True})
    perform_guarded_delete(-1001, 99999, post_fn)
    captured = capsys.readouterr()
    assert "REFUSED" in captured.out
    assert "99999" in captured.out
    assert "registry" in captured.out


def test_known_id_passes_through_to_post():
    """An ID in the registry → post_fn is called and its result returned."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value={"ok": True})
    result = perform_guarded_delete(-1001, 12345, post_fn)
    assert result is True
    post_fn.assert_called_once()
    args, kwargs = post_fn.call_args
    assert args[0] == "deleteMessage"
    assert args[1] == {"chat_id": -1001, "message_id": 12345}


def test_post_failure_returns_false():
    """When post_fn returns None (API failure) the result is False."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value=None)
    result = perform_guarded_delete(-1001, 12345, post_fn)
    assert result is False


def test_suppress_errors_passed_through():
    """The full suppress_errors tuple should reach post_fn unchanged."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value={"ok": True})
    perform_guarded_delete(-1001, 12345, post_fn)
    args, kwargs = post_fn.call_args
    suppress = kwargs.get("suppress_errors", ())
    assert "message to delete not found" in suppress
    assert "MESSAGE_ID_INVALID" in suppress


def test_no_force_flag_in_signature():
    """The guard takes (chat_id, message_id, post_fn) — no bypass arg.

    Locks in the design promise that there is no force/bypass parameter;
    a future change that adds one to make 'just this once' deletes
    easier should fail this test and force a deliberate decision.
    """
    import inspect
    sig = inspect.signature(perform_guarded_delete)
    assert list(sig.parameters) == ["chat_id", "message_id", "post_fn"]


# ── unpin guard ────────────────────────────────────────────────────────────
# The bug this fixes: unpin_message used to POST unpinChatMessage for any ID
# a caller passed, so a stale/crossed pin id cleared a GM's or player's manual
# pin. The guard now refuses IDs the bot never sent — same rule as delete.


def test_unpin_refuses_unknown_id_no_api_call():
    """An unknown ID → False return, no unpinChatMessage request made."""
    post_fn = MagicMock(return_value={"ok": True})
    result = perform_guarded_unpin(-1001, 99999, post_fn)
    assert result is False
    post_fn.assert_not_called()


def test_unpin_refused_call_prints_diagnostic(capsys):
    """The unpin refusal path emits a print line naming the ID."""
    post_fn = MagicMock(return_value={"ok": True})
    perform_guarded_unpin(-1001, 99999, post_fn)
    captured = capsys.readouterr()
    assert "REFUSED" in captured.out
    assert "unpin_message" in captured.out
    assert "99999" in captured.out


def test_unpin_known_id_passes_through_to_post():
    """A registered ID → unpinChatMessage is called with the right args."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value={"ok": True})
    result = perform_guarded_unpin(-1001, 12345, post_fn)
    assert result is True
    post_fn.assert_called_once()
    args, _ = post_fn.call_args
    assert args[0] == "unpinChatMessage"
    assert args[1] == {"chat_id": -1001, "message_id": 12345}


def test_unpin_post_failure_returns_false():
    """When post_fn returns None (API failure) the result is False."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value=None)
    assert perform_guarded_unpin(-1001, 12345, post_fn) is False


def test_unpin_suppress_errors_passed_through():
    """The unpin suppress_errors tuple should reach post_fn unchanged."""
    reg.record_sent(12345)
    post_fn = MagicMock(return_value={"ok": True})
    perform_guarded_unpin(-1001, 12345, post_fn)
    _, kwargs = post_fn.call_args
    suppress = kwargs.get("suppress_errors", ())
    assert "message to unpin not found" in suppress
    assert "MESSAGE_ID_INVALID" in suppress


def test_unpin_no_force_flag_in_signature():
    """The unpin guard also exposes no force/bypass parameter."""
    import inspect
    sig = inspect.signature(perform_guarded_unpin)
    assert list(sig.parameters) == ["chat_id", "message_id", "post_fn"]
