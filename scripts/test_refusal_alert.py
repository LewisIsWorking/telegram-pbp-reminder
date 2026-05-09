"""Tests for refusal_alert.py — Telegram alert poster for delete refusals.

Covers:
  * No refusals -> no Telegram call, return 0
  * Refusals + valid config -> POST to Telegram, mark alerted, return 0
  * Refusals + missing config -> warn, return 1, do NOT mark alerted
  * Telegram failure -> return 1, do NOT mark alerted
  * Long refusal lists are truncated in the message body
"""

from unittest.mock import MagicMock, patch

import pytest

from posting import refusal_log as rl
import refusal_alert


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    monkeypatch.setattr(rl, "_LOG_PATH", tmp_path / "refusal_log.json")
    monkeypatch.setattr(rl, "_ALERTED_PATH",
                        tmp_path / "refusal_log_alerted.json")
    rl.reset_for_test()
    yield
    rl.reset_for_test()


def _config_ok():
    return {"group_id": -1001, "bot_topic_id": 99}


def test_no_refusals_returns_zero_no_post(capsys):
    with patch("refusal_alert.requests.post") as post:
        rc = refusal_alert.main()
    post.assert_not_called()
    assert rc == 0
    assert "No new refusals" in capsys.readouterr().out


def test_refusals_with_config_posts_and_marks(monkeypatch):
    rl.record_refusal(-1001, 12345, timestamp="2026-05-09T10:00:00+00:00")
    rl.record_refusal(-1001, 12346, timestamp="2026-05-09T10:00:01+00:00")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_SHA", "abc123def")

    with patch("refusal_alert.load_config", return_value=_config_ok()), \
         patch("refusal_alert.requests.post") as post:
        post.return_value = MagicMock(ok=True)
        rc = refusal_alert.main()

    assert rc == 0
    post.assert_called_once()
    call_kwargs = post.call_args.kwargs
    body = call_kwargs["json"]["text"]
    assert "12345" in body
    assert "12346" in body
    assert "abc123de" in body  # truncated SHA

    # After alert: no more unalerted entries
    assert rl.get_unalerted_refusals() == []


def test_missing_config_returns_one_does_not_mark(monkeypatch):
    rl.record_refusal(-1001, 12345, timestamp="2026-05-09T10:00:00+00:00")

    # No env, no config — clear environment
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)

    with patch("refusal_alert.load_config", return_value={}), \
         patch("refusal_alert.requests.post") as post:
        rc = refusal_alert.main()

    assert rc == 1
    post.assert_not_called()
    # Refusal not marked — should still be visible next run.
    assert len(rl.get_unalerted_refusals()) == 1


def test_telegram_failure_returns_one_does_not_mark(monkeypatch):
    rl.record_refusal(-1001, 12345, timestamp="2026-05-09T10:00:00+00:00")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("GITHUB_SHA", "abc")

    with patch("refusal_alert.load_config", return_value=_config_ok()), \
         patch("refusal_alert.requests.post") as post:
        post.return_value = MagicMock(ok=False, status_code=500, text="boom")
        rc = refusal_alert.main()

    assert rc == 1
    # Marker not advanced — refusal still visible
    assert len(rl.get_unalerted_refusals()) == 1


def test_long_refusal_list_truncated_in_body(monkeypatch):
    for i in range(40):
        rl.record_refusal(-1001, 1000 + i,
                          timestamp=f"2026-05-09T10:{i:02d}:00+00:00")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("GITHUB_SHA", "abc")

    with patch("refusal_alert.load_config", return_value=_config_ok()), \
         patch("refusal_alert.requests.post") as post:
        post.return_value = MagicMock(ok=True)
        rc = refusal_alert.main()

    body = post.call_args.kwargs["json"]["text"]
    # First 25 IDs included, plus a "and 15 more" line
    assert "1000" in body and "1024" in body
    assert "and 15 more" in body
    assert rc == 0


def test_format_alert_includes_doc_pointer():
    """The alert message points the operator at the right doc."""
    refusals = [
        {"timestamp": "2026-05-09T10:00:00+00:00",
         "chat_id": -1001, "message_id": 99},
    ]
    text = refusal_alert._format_alert(refusals, "abc123de")
    assert "delete-safety.md" in text
