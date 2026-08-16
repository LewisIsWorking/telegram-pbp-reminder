"""Tests for ``_post`` suppressed-error semantics (P3/9 follow-up).

Background: pre-2026-05-10, ``_post`` returned ``None`` for both real
failures and "soft" failures whose body matched ``suppress_errors``.
Callers using ``_post(...) is not None`` therefore treated
"already gone" responses (e.g. a deleteMessage 400 with
``"message to delete not found"``) as failure. That left old GM
queue batches stuck in ``gm_queue_history`` past ``MAX_KEPT_BATCHES``
and made ``Topic queue prev-delete failed`` log spurious entries.

Fix: ``_post`` now returns ``True`` when the body matches a
suppress pattern, signalling "the desired end state is achieved".
Real failures (no match) still return ``None`` so callers can
retry or surface the error.

Coverage:
  * suppressed body \u2192 returns True
  * unsuppressed body \u2192 still returns None
  * empty suppress_errors tuple \u2192 every non-200 returns None (legacy)
  * status 200 with ok=true still returns the result payload (no
    regression on the success path)
  * each documented suppress pattern from safe_delete is recognised
"""

from unittest.mock import MagicMock, patch
import os
import importlib.util

# conftest installs a mock ``telegram`` in sys.modules before collection.
# Load the real implementation directly by file path so the patches in
# this file actually exercise the real ``_post``.
_spec = importlib.util.spec_from_file_location(
    "_real_telegram_for_suppress",
    os.path.join(os.path.dirname(__file__), "telegram.py"),
)
_tg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tg)


def _resp(status: int, body: str) -> MagicMock:
    """Build a mock response with status and body."""
    m = MagicMock()
    m.status_code = status
    m.text = body
    m.json.return_value = {"ok": False}
    return m


def test_post_suppressed_error_returns_true():
    """A 400 with a body matching ``suppress_errors`` is now treated
    as soft success: the desired end state (message gone) is achieved.
    """
    _tg.init("t")
    body = '{"ok":false,"description":"Bad Request: message to delete not found"}'
    with patch.object(_tg.requests, "post", return_value=_resp(400, body)):
        result = _tg._post(
            "deleteMessage", {}, "delete_message",
            suppress_errors=("message to delete not found",),
        )
        assert result is True


def test_post_unsuppressed_error_still_returns_none():
    """Real errors (no suppress match) still return None so callers
    correctly treat them as failure."""
    _tg.init("t")
    body = '{"ok":false,"description":"Forbidden: bot was kicked"}'
    with patch.object(_tg.requests, "post", return_value=_resp(403, body)):
        result = _tg._post(
            "deleteMessage", {}, "delete_message",
            suppress_errors=("message to delete not found",),
        )
        assert result is None


def test_post_no_suppress_errors_keeps_legacy_none_behaviour():
    """When the caller passes no suppress patterns, every non-200
    response still returns None \u2014 same as before this fix."""
    _tg.init("t")
    body = '{"ok":false,"description":"Bad Request: anything"}'
    with patch.object(_tg.requests, "post", return_value=_resp(400, body)):
        assert _tg._post("sendMessage", {}) is None


def test_post_unsuppressed_error_prints_diagnostic(capsys):
    \
        """Real errors must surface the body so operators can diagnose."""
    _tg.init("t")
    body = '{"ok":false,"description":"Forbidden: chat not found"}'
    with patch.object(_tg.requests, "post", return_value=_resp(403, body)):
        _tg._post("deleteMessage", {}, "delete_message",
                  suppress_errors=("message to delete not found",))
    captured = capsys.readouterr()
    assert "Telegram delete_message failed" in captured.out
    assert "chat not found" in captured.out


def test_post_suppressed_error_no_print(capsys):
    """Suppressed errors must NOT print \u2014 they're soft success, not
    something an operator needs to see."""
    _tg.init("t")
    body = '{"ok":false,"description":"Bad Request: message to delete not found"}'
    with patch.object(_tg.requests, "post", return_value=_resp(400, body)):
        _tg._post("deleteMessage", {}, "delete_message",
                  suppress_errors=("message to delete not found",))
    captured = capsys.readouterr()
    assert "failed" not in captured.out


def test_post_each_safe_delete_suppress_pattern_recognised():
    """Every pattern ``posting.safe_delete`` actually passes must be
    treated as soft success. If any of these regress to returning
    None, the bug Lewis reported on 2026-05-10 returns: GM queue
    batches stuck past max_kept, topic queue prev-deletes spurious.

    ANCHORED 2026-08-16 to ``safe_delete.ALREADY_GONE_ERRORS``. This
    test used to declare its own copy of the tuple, so it proved that
    ``_post`` can suppress *some* list and never that the list matched
    the one production sends. It passed for months while the real tuple
    carried ``"message can't be deleted"`` — an error meaning the
    message is still there.
    """
    from posting.safe_delete import ALREADY_GONE_ERRORS

    _tg.init("t")
    # Passed by name, not via a local alias: test_suppressed_errors_are
    # _declared parses suppress_errors= arguments statically and cannot
    # follow an assignment, so aliasing it here would hide the list from
    # the guard. It caught exactly that on 2026-08-16.
    for pattern in ALREADY_GONE_ERRORS:
        body = f'{{"ok":false,"description":"Bad Request: {pattern}"}}'
        with patch.object(_tg.requests, "post", return_value=_resp(400, body)):
            result = _tg._post(
                "deleteMessage", {}, "delete_message",
                suppress_errors=ALREADY_GONE_ERRORS,
            )
            assert result is True, f"pattern {pattern!r} regressed to None"


def test_post_success_path_still_returns_result_payload():
    """Regression check: 200 + ok=true still returns the result, not
    True. Without this guard, send_message_id (which extracts the
    message_id from the result dict) would silently break.
    """
    _tg.init("t")
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"ok": True, "result": {"message_id": 99}}
    with patch.object(_tg.requests, "post", return_value=m):
        assert _tg._post("sendMessage", {}) == {"message_id": 99}


def test_post_delete_success_returns_true_unchanged():
    """For a successful deleteMessage, Telegram returns
    ``{ok: true, result: true}`` \u2014 verify this still flows through
    as True (the result payload), not the new soft-success True.
    The end value is the same but the code path is different and
    callers must not be surprised by either."""
    _tg.init("t")
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"ok": True, "result": True}
    with patch.object(_tg.requests, "post", return_value=m):
        result = _tg._post(
            "deleteMessage", {}, "delete_message",
            suppress_errors=("message to delete not found",),
        )
        assert result is True
