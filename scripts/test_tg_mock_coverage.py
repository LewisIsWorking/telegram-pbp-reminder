"""The ``tg_mock`` fixture must patch every module that sends (2026-08-10).

Why this guard exists
---------------------
``conftest.tg_mock`` used to hand-list its patch targets. It named 8
modules; 56 import ``telegram as tg``. Any test that used the fixture
while exercising one of the other 48 was asserting against a mock the
code never touched — so::

    assert not tg_mock.send_message.called

passed regardless of what the code did. Two of my own POTW tests were
exactly that. Proven by deleting the POTW Monday gate outright and
watching the suite stay green.

The fixture now discovers its targets by scanning source, so it cannot
drift as modules are added. This file is the guard on the guard: it
checks the discovery still finds the real modules, that the fixture
actually patched them, and — most importantly — that a call made through
any of them is visible on the mock. A fixture that patches nothing would
still "pass" a `not called` assertion, so coverage alone is not enough;
the positive direction has to be checked too.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import conftest  # noqa: E402


class TestDiscovery:
    def test_finds_a_realistic_number_of_modules(self):
        names = conftest.tg_importing_modules()
        assert len(names) > 40, (
            f"only {len(names)} modules discovered — the source scan has "
            f"probably broken, which would silently hollow out every "
            f"'not called' assertion in the suite")

    def test_includes_the_known_senders(self):
        names = set(conftest.tg_importing_modules())
        for expected in ("scheduled.potw", "scheduled.schedule_post",
                         "scheduled.topic_queue_poster", "posting.sender",
                         "scheduled.queue_reminder", "dispatch.tracking"):
            assert expected in names, f"{expected} must be patchable"

    def test_excludes_tests_and_conftest(self):
        names = conftest.tg_importing_modules()
        assert not [n for n in names
                    if n.startswith("test_") or n == "conftest"]


class TestNoDirectFromImports:
    """The O(1) swap only works while nothing binds a function directly.

    The fixture swaps callables on the shared ``telegram`` module object,
    which every module reaches via ``import telegram as tg``. A module
    doing ``from telegram import send_message`` would bind the real
    function at import time and slip straight past the mock — silently
    restoring the exact vacuum this whole guard exists to prevent.
    """

    def test_nothing_binds_telegram_functions_directly(self):
        import re
        from pathlib import Path
        root = Path(os.path.dirname(__file__))
        offenders = []
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "conftest.py":
                continue
            try:
                src = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"^\s*from telegram import ", src, re.M):
                offenders.append(str(path.relative_to(root)))
        assert not offenders, (
            f"these bind telegram functions directly and would bypass "
            f"tg_mock: {offenders}. Use `import telegram as tg`.")


class TestFixtureActuallyPatches:
    def test_swaps_the_real_senders(self, tg_mock):
        for fn in ("send_message", "send_message_id", "delete_message",
                   "pin_message", "unpin_message"):
            assert fn in tg_mock.patched_attrs, f"{fn} left unmocked"


class TestCallsAreVisible:
    """Coverage is not enough — calls must actually land on the mock.

    A fixture that patched nothing would still satisfy every ``not
    called`` assertion in the suite. These check the positive direction,
    so the guard cannot itself be vacuous.
    """

    def test_send_through_potw_is_seen(self, tg_mock):
        import scheduled.potw as potw
        potw.tg.send_message_id(-100, 1, "hi")
        assert tg_mock.send_message_id.called

    def test_send_through_schedule_post_is_seen(self, tg_mock):
        import scheduled.schedule_post as sp
        sp.tg.send_message_id(-100, 1, "hi")
        assert tg_mock.send_message_id.called

    def test_send_through_queue_reminder_is_seen(self, tg_mock):
        import scheduled.queue_reminder as qr
        qr.tg.send_message(-100, 1, "hi")
        assert tg_mock.send_message.called

    def test_isolated_between_tests(self, tg_mock):
        """A fresh mock per test, or call counts leak across the suite."""
        assert not tg_mock.send_message_id.called
