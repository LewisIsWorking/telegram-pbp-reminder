"""The test suite may not reach the network. Enforced, not intended.

⛔⛔ Added 2026-09-04 after the suite sent **fourteen real Telegram
messages** to the live "The Bot is Dead" topic, from CI, twice.

What happened, and why nothing caught it:

  1. ``notify_debug`` was added to ``gate.main`` so faults report to the
     debug topic.
  2. Two test classes that already called ``gate.main`` stubbed
     ``send_alert`` but of course not the parameter that did not exist
     when they were written.
  3. ``preflight/alerting`` posts with ``requests.post``. It never goes
     near ``telegram.py``, so ``_test_telegram_mock`` - the thing whose
     docstring promised "No real Telegram API calls are ever made during
     tests" - was no protection whatever.
  4. CI puts ``TELEGRAM_BOT_TOKEN`` in the pytest step's env, because
     that step alerts on test failure. So the token was right there.

The messages were unmistakable once seen: ``github.com/o/r/actions``,
``written by run: 33900000000``, "25 consecutive workflow runs failed".
Fixture values, posted to a live channel.

⭐ **Stubbing the two fixtures would not have been a fix.** ELEVEN
production modules call ``requests`` directly - ``ci_alert``,
``refusal_alert``, ``set_commands``, ``audit_orphans``,
``post_changelog`` among them, five of which post to Telegram. Any test
that reaches any of them, now or later, has the same hole. The mock
covered one door in a building with twelve.

So the rule is enforced at the only place that covers all of them: the
HTTP client itself. A test that tries to reach the network fails, loudly,
naming the URL, instead of quietly doing it.

⚠️ Deliberately blocks EVERY host, not just api.telegram.org. A test
reaching GitHub's API is also a test that is slow, flaky, and dependent
on a token; there is no host this suite has any business contacting.

⚠️ Deliberately raises rather than returning a benign fake. A fake
response would let the calling code carry on and the test would assert
against imaginary data - green, and meaningless.

⭐ Tests that want to exercise send/fetch code still can: pass a fake
session (``fetch_runs(session=...)``) or monkeypatch the specific
function. Both replace the blocker for that test only, and monkeypatch
restores it afterwards.
"""

import os

import requests

_BLOCKED = ("request", "get", "post", "put", "patch", "delete", "head",
            "options")


class RealNetworkCallInTests(BaseException):
    """Raised instead of making the call.

    ⛔⛔ Inherits ``BaseException``, NOT ``Exception``, and that is the
    whole difference between a guard and a decoration. Every sender in
    this codebase wraps its call in ``except Exception`` on purpose -
    alerting must never break the run it is reporting on. So a guard
    raising ``RuntimeError`` gets swallowed by the exact code it is
    watching: the network call is blocked, the test still passes, and
    nobody learns the test was trying to send.

    Measured, not assumed. With ``RuntimeError`` the full suite was 2895
    green while two test classes were still calling the real
    ``notify_debug``. As a ``BaseException`` those two failed
    immediately, which is how the leak became visible at all.

    Named so the traceback explains itself without opening this file."""


def _refuse(method: str):
    def blocked(*args, **kwargs):
        url = kwargs.get("url") or (args[1] if len(args) > 1 else
                                    (args[0] if args else "<no url>"))
        raise RealNetworkCallInTests(
            f"requests.{method}() to {url!r} during a test.\n"
            f"The suite must not reach the network. Something under test "
            f"is making a REAL HTTP call - on 2026-09-04 that put 14 "
            f"fixture-filled messages into the live debug topic.\n"
            f"Fix the test to stub the call (a fake session, or "
            f"monkeypatch the function), not this guard.")
    return blocked


# ⛔⛔ THE SUITE MUST LOOK LIKE CI. `alerting._send` returns early when
# TELEGRAM_BOT_TOKEN is unset, so on a developer machine the send path is
# never entered and every leaking test passes. In CI the token IS set -
# the pytest step needs it to alert on failure - so the same tests took
# the branch and posted for real.
#
# That gap is why this shipped: the local suite CANNOT reproduce the bug
# it needs to catch. Setting a dummy here makes both environments take
# the same branch, where the blocker above is waiting. Proven: with the
# token unset, 2895 green while 7 tests were leaking; with it set, those
# 7 fail immediately.
#
# A test that wants the no-token path does `monkeypatch.delenv`.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-never-valid")


def install() -> None:
    """Replace requests' entry points. Import-time, like the tg mock.

    ⚠️ ``Session.request`` is covered too. The module-level helpers all
    route through it, but code holding its own ``Session`` would slip
    past if only the helpers were replaced.
    """
    for name in _BLOCKED:
        if hasattr(requests, name):
            setattr(requests, name, _refuse(name))
    requests.Session.request = _refuse("Session.request")


install()
