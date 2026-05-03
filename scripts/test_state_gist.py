"""Tests for state_gist.py — pure gist load/save functions."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json
from unittest.mock import MagicMock, patch

import pytest


_FILENAME = "pbp_state.json"


class TestGistLoad:
    def test_no_credentials_returns_none(self):
        """Empty api or empty token both treat the gist as not configured."""
        from state_gist import gist_load
        assert gist_load("", "tok", _FILENAME) is None
        assert gist_load("http://fake", "", _FILENAME) is None

    def test_success_returns_parsed_state(self):
        from state_gist import gist_load
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "files": {_FILENAME: {"content": json.dumps({"offset": 42})}}
        }
        with patch("state_gist.requests.get", return_value=mock_resp):
            result = gist_load("http://fake", "tok", _FILENAME)
        assert result == {"offset": 42}

    def test_missing_file_returns_none(self):
        """Gist exists but doesn't contain our state file — treat as None."""
        from state_gist import gist_load
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"files": {}}
        with patch("state_gist.requests.get", return_value=mock_resp):
            result = gist_load("http://fake", "tok", _FILENAME)
        assert result is None

    def test_http_error_aborts(self):
        """Non-200 must raise SystemExit so we never silently fall back to
        defaults and clobber gist history with an empty save next tick."""
        from state_gist import gist_load
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("state_gist.requests.get", return_value=mock_resp):
            with pytest.raises(SystemExit):
                gist_load("http://fake", "tok", _FILENAME)

    def test_network_error_aborts(self):
        """Network failure must abort, not return None — same protection."""
        from state_gist import gist_load
        import requests as _req
        with patch("state_gist.requests.get",
                   side_effect=_req.RequestException("conn refused")):
            with pytest.raises(SystemExit):
                gist_load("http://fake", "tok", _FILENAME)


class TestGistSave:
    def test_no_credentials_silent_noop(self):
        """No api or no token: silently no-op (gist not configured)."""
        from state_gist import gist_save
        # Should not raise and should not call requests
        with patch("state_gist.requests.patch") as mock_patch:
            gist_save("", "tok", _FILENAME, {"offset": 1})
            gist_save("http://fake", "", _FILENAME, {"offset": 1})
            mock_patch.assert_not_called()

    def test_success_logs_ok(self, capsys):
        from state_gist import gist_save
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("state_gist.requests.patch", return_value=mock_resp):
            gist_save("http://fake", "tok", _FILENAME, {"offset": 1})
        captured = capsys.readouterr()
        assert "saved to gist" in captured.out

    def test_http_failure_does_not_raise(self):
        """A failed save must never crash the bot — gist is best-effort backup."""
        from state_gist import gist_save
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("state_gist.requests.patch", return_value=mock_resp):
            gist_save("http://fake", "tok", _FILENAME, {"offset": 1})  # no raise

    def test_network_error_does_not_raise(self):
        """Network exception during save must be caught — same reason."""
        from state_gist import gist_save
        import requests as _req
        with patch("state_gist.requests.patch",
                   side_effect=_req.RequestException("conn refused")):
            gist_save("http://fake", "tok", _FILENAME, {"offset": 1})  # no raise

    def test_serialises_state_with_default_str(self):
        """Non-JSON-native types in state (e.g. datetimes) must serialise via
        the default=str fallback rather than raising TypeError."""
        from state_gist import gist_save
        from datetime import datetime
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("state_gist.requests.patch", return_value=mock_resp) as mp:
            gist_save("http://fake", "tok", _FILENAME,
                      {"last_run": datetime(2026, 5, 3, 14, 0, 0)})
        # Inspect the body that was sent
        call_kwargs = mp.call_args.kwargs
        body_content = call_kwargs["json"]["files"][_FILENAME]["content"]
        # datetime should appear stringified, not raise
        assert "2026-05-03" in body_content


class TestGistHeaders:
    def test_token_in_authorization(self):
        """The internal _headers helper builds a token-auth header.

        Not strictly part of the public API but worth pinning so a typo
        in the auth scheme is caught by tests rather than at runtime."""
        from state_gist import _headers
        h = _headers("abc123")
        assert h["Authorization"] == "token abc123"
        assert h["Accept"] == "application/vnd.github.v3+json"
