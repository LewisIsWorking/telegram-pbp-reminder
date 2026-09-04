"""The suite must be unable to make a real HTTP call. Proven here.

⛔⛔ 2026-09-04: the test suite sent fourteen real Telegram messages to
the live "The Bot is Dead" topic, from CI, across two runs. They were
plainly fixtures once seen - ``github.com/o/r/actions``, ``written by
run: 33900000000``, "25 consecutive workflow runs failed" - but nothing
in the suite was in a position to notice, because:

  * ``_test_telegram_mock`` only covers code going through
    ``telegram.py``. Eleven modules use ``requests`` directly.
  * ``alerting._send`` returns early with no ``TELEGRAM_BOT_TOKEN``, so
    on a developer machine the send path is never entered at all. The
    local suite could not reproduce the bug even in principle.
  * CI sets that token, because the pytest step alerts on failure.

Three things had to be true together, and each looked harmless alone.
The tests below pin all three.
"""

import os

import pytest
import requests

from _test_no_real_network import _BLOCKED, RealNetworkCallInTests
from preflight import alerting

# Hardcoded on purpose. See test_each_helper_is_replaced_in_its_own_right.
_MUST_BE_BLOCKED = ("request", "get", "post", "put", "patch", "delete",
                    "head", "options")


class TestEveryEntryPointIsBlocked:
    @pytest.mark.parametrize("method", _MUST_BE_BLOCKED)
    def test_module_level_helpers_refuse(self, method):
        with pytest.raises(RealNetworkCallInTests):
            getattr(requests, method)("https://api.telegram.org/botX/send")

    def test_a_session_of_its_own_refuses_too(self):
        """⚠️ Code holding its own Session would slip past a guard that
        only replaced the module-level helpers."""
        with pytest.raises(RealNetworkCallInTests):
            requests.Session().get("https://api.github.com/x")

    def test_every_host_is_blocked_not_just_telegram(self):
        """A test reaching ANY host is slow, flaky and token-dependent."""
        with pytest.raises(RealNetworkCallInTests):
            requests.get("https://example.com/")

    def test_the_error_names_the_url_it_stopped(self):
        with pytest.raises(RealNetworkCallInTests) as caught:
            requests.post("https://api.telegram.org/botSECRET/sendMessage")
        assert "api.telegram.org" in str(caught.value)

    @pytest.mark.parametrize("name", _MUST_BE_BLOCKED)
    def test_each_helper_is_replaced_in_its_own_right(self, name):
        """⚠️ The two layers are REDUNDANT ON PURPOSE, and that hid a
        gap: cutting every module-level helper but ``get`` still left the
        suite green, because ``requests.post`` routes through
        ``Session.request``, which is patched too. Nothing was leaking,
        but nothing proved the first layer existed either, so it read as
        dead code a future cleanup would remove.

        ⛔⛔ The expected names are HARDCODED above, not imported from
        ``_BLOCKED``. The first version parametrised over ``_BLOCKED``
        itself, so shrinking that tuple shrank the test with it and the
        mutation stayed green: a guard whose expectation comes from the
        thing it guards cannot fail.
        """
        assert getattr(requests, name).__name__ == "blocked", (
            f"requests.{name} is the real one; the module-level layer of "
            f"the guard is gone even if Session.request still covers it")

    def test_the_guards_own_list_covers_them_all(self):
        assert set(_MUST_BE_BLOCKED) <= set(_BLOCKED)


class TestItCannotBeSwallowed:
    """⛔⛔ The property that makes this a guard rather than a decoration."""

    def test_it_is_not_an_Exception(self):
        """Every sender here wraps its call in `except Exception`, on
        purpose. A guard deriving from Exception is caught by the exact
        code it watches: the call is blocked, the test still passes, and
        the leak stays invisible.

        This is measured history, not theory. As a RuntimeError the full
        suite was 2895 green with 7 tests still leaking; promoting it to
        BaseException made those 7 fail at once."""
        assert issubclass(RealNetworkCallInTests, BaseException)
        assert not issubclass(RealNetworkCallInTests, Exception)

    def test_the_real_sender_does_not_absorb_it(self, monkeypatch):
        """⭐ End-to-end through the code that actually swallowed it.
        `_send` has a bare `except Exception`; this proves the guard
        still escapes it."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        with pytest.raises(RealNetworkCallInTests):
            alerting._send(-100, 767, "would have been a real message", "debug")

    def test_an_ordinary_failure_IS_still_absorbed(self, monkeypatch):
        """⭐ Can-fail counterpart. `_send` must go on swallowing normal
        errors, or alerting could break the run it reports on. The guard
        is the single exception to that, not a change of policy."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")

        def boom(*a, **k):
            raise ConnectionError("network flake")

        monkeypatch.setattr(alerting.requests, "post", boom)
        alerting._send(-100, 767, "x", "debug")  # must not raise


class TestTheSuiteLooksLikeCI:
    def test_a_token_is_always_present(self):
        """⛔ Without this the send path is never entered locally and the
        guard above protects nothing on a developer machine. The bug
        shipped precisely through that gap."""
        assert os.environ.get("TELEGRAM_BOT_TOKEN")

    def test_the_token_could_never_be_a_real_one(self):
        """⚠️ It must be obviously fake: a plausible-looking value would
        make a leak here indistinguishable from a leak in production."""
        assert "never-valid" in os.environ["TELEGRAM_BOT_TOKEN"]

    def test_the_no_token_path_is_still_reachable(self, monkeypatch, capsys):
        """A test that wants the early return can still delenv for it."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        alerting._send(-100, 767, "x", "debug")
        assert "no token" in capsys.readouterr().out
