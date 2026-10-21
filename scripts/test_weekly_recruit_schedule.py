"""When the weekly recruitment DM fires, where it goes, and its wiring.

Split from ``test_weekly_recruit``, which asks which campaign wins and what
the message says. The clock is injected here too: every call passes
``now=`` built from ``_NOW``, bar the one test that proves the default.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from scheduled import weekly_recruit as wr  # noqa: E402
from test_weekly_recruit import _GM, _NOW, _Sent, _cfg, _pair, _state  # noqa: E402,E501


# ── Delivery and cadence ─────────────────────────────────────────────────────

def test_it_dms_the_gm_never_a_topic(monkeypatch):
    sent = _Sent(monkeypatch)
    state = _state(a=(100, 3))
    wr.post_weekly_recruit(_cfg(_pair("C01", 100)), state, now=_NOW)
    assert len(sent.calls) == 1
    chat, thread, _text = sent.calls[0]
    assert (chat, thread) == (_GM, None)
    assert state[wr.LAST_KEY] == _NOW.isoformat()
    assert state[wr.PICKS_KEY] == {"100": _NOW.isoformat()}


def test_it_holds_a_weekly_cadence(monkeypatch):
    sent = _Sent(monkeypatch)
    cfg, state = _cfg(_pair("C01", 100)), _state(a=(100, 3))
    wr.post_weekly_recruit(cfg, state, now=_NOW)
    wr.post_weekly_recruit(cfg, state, now=_NOW + timedelta(days=6, hours=23))
    assert len(sent.calls) == 1
    wr.post_weekly_recruit(cfg, state, now=_NOW + timedelta(days=7))
    assert len(sent.calls) == 2


def test_a_failed_dm_is_retried_next_run(monkeypatch):
    sent = _Sent(monkeypatch, ok=False)
    state = _state(a=(100, 3))
    wr.post_weekly_recruit(_cfg(_pair("C01", 100)), state, now=_NOW)
    assert sent.calls and wr.LAST_KEY not in state
    assert wr.PICKS_KEY not in state


def test_all_full_spends_the_week_without_a_dm(monkeypatch):
    sent = _Sent(monkeypatch)
    state = _state(a=(100, 6))
    wr.post_weekly_recruit(_cfg(_pair("C01", 100)), state, now=_NOW)
    assert sent.calls == []
    assert state[wr.LAST_KEY] == _NOW.isoformat()


def test_switched_off_or_no_gm_sends_nothing(monkeypatch):
    sent = _Sent(monkeypatch)
    state = _state(a=(100, 3))
    wr.post_weekly_recruit(_cfg(_pair("C01", 100),
                                weekly_recruit_enabled=False), state, now=_NOW)
    wr.post_weekly_recruit(_cfg(_pair("C01", 100), gm_user_id=None),
                           state, now=_NOW)
    assert sent.calls == [] and wr.LAST_KEY not in state


def test_now_defaults_to_the_real_clock(monkeypatch):
    sent = _Sent(monkeypatch)
    state = _state(a=(100, 3))
    wr.post_weekly_recruit(_cfg(_pair("C01", 100)), state)
    assert len(sent.calls) == 1
    stamped = datetime.fromisoformat(state[wr.LAST_KEY])
    assert abs((stamped - datetime.now(timezone.utc)).total_seconds()) < 60


# ── Registration, where scheduled jobs silently die ─────────────────────────

def test_it_is_registered_everywhere_a_job_must_be():
    import inspect

    import checker
    from scheduled.schedule_intervals import INTERVAL_JOBS
    from state_schema import DEFAULT_STATE, PARTITIONS
    assert "post_weekly_recruit" in inspect.getsource(checker._run_checks)
    job = next(j for j in INTERVAL_JOBS if j.key == wr.LAST_KEY)
    assert job.days == wr.INTERVAL_DAYS
    declared = {k for keys in PARTITIONS.values() for k in keys}
    assert {wr.LAST_KEY, wr.PICKS_KEY} <= declared
    assert {wr.LAST_KEY, wr.PICKS_KEY} <= set(DEFAULT_STATE)
