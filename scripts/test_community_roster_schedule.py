"""When the community roster fires, where it lands, and what it keeps.

Split from ``test_community_roster``, which asks what the post SAYS.
This one asks how it lives: the weekly gate, the destination, and the
fact that it deletes nothing.

⚠️ The registration assertions at the bottom look redundant next to
``test_schedule_is_complete`` and are not. That guard proves the job is
listed wherever it is listed; these say which lists a scheduled job has
to be in at all, in the file a person reads when adding the next one.
Seven jobs were missing from the schedule post until 2026-08-13 because
nothing said it out loud.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from test_community_roster import _NOW, _cfg, _pair, _seat, _state  # noqa: E402


class _Fired:
    """What the job did to the outside world on one run."""

    def __init__(self):
        self.sent, self.deleted = [], []


def _fire(monkeypatch, state, cfg=None, now=_NOW, message_id=4242):
    import telegram as tg
    from scheduled.community_roster import post_community_roster
    log = _Fired()
    monkeypatch.setattr(tg, "send_message_id",
                        lambda g, t, b, **k: log.sent.append((g, t, b, k))
                        or message_id)
    monkeypatch.setattr(tg, "delete_message",
                        lambda g, m: log.deleted.append(m) or True)
    cfg = cfg or _cfg(_pair("C01", "100"))
    state.setdefault("players", _state(_seat("Ann", 100,
                                             username="ann"))["players"])
    post_community_roster(cfg, state, now=now)
    return log


class TestTheWeeklyGate:
    def test_it_posts_when_it_has_never_run(self, monkeypatch):
        assert _fire(monkeypatch, {}).sent

    def test_it_does_not_post_again_the_next_day(self, monkeypatch):
        state = {"last_community_roster": (_NOW - timedelta(days=1))
                 .isoformat()}
        assert not _fire(monkeypatch, state).sent

    def test_it_posts_again_after_seven_days(self, monkeypatch):
        state = {"last_community_roster": (_NOW - timedelta(days=7, hours=1))
                 .isoformat()}
        assert _fire(monkeypatch, state).sent

    def test_a_successful_post_records_the_time(self, monkeypatch):
        state = {}
        _fire(monkeypatch, state)
        assert state["last_community_roster"] == _NOW.isoformat()

    def test_a_failed_post_does_not(self, monkeypatch):
        # ⭐⭐ Stamping before the send would swallow the week silently,
        # and a weekly job that skips a week is indistinguishable from a
        # quiet week in the group.
        state = {}
        log = _fire(monkeypatch, state, message_id=None)
        assert log.sent, "it must have tried"
        assert "last_community_roster" not in state

    def test_the_config_switch_turns_it_off(self, monkeypatch):
        cfg = _cfg(_pair("C01", "100"), community_roster_enabled=False)
        assert not _fire(monkeypatch, {}, cfg=cfg).sent


class TestWhereItLands:
    def test_it_goes_to_the_gm_queue_topic_by_default(self, monkeypatch):
        # t.me/Path_Wars/146780, which Lewis named.
        log = _fire(monkeypatch, {})
        assert log.sent[0][1] == 146780

    def test_an_explicit_topic_wins(self, monkeypatch):
        cfg = _cfg(_pair("C01", "100"), community_roster_topic_id=999)
        assert _fire(monkeypatch, {}, cfg=cfg).sent[0][1] == 999

    def test_it_falls_back_to_the_bot_topic(self, monkeypatch):
        cfg = _cfg(_pair("C01", "100"))
        del cfg["gm_queue_topic_id"]
        assert _fire(monkeypatch, {}, cfg=cfg).sent[0][1] == 137393

    def test_no_topic_at_all_posts_nothing(self, monkeypatch):
        cfg = _cfg(_pair("C01", "100"))
        del cfg["gm_queue_topic_id"]
        del cfg["bot_topic_id"]
        assert not _fire(monkeypatch, {}, cfg=cfg).sent

    def test_it_is_silent(self, monkeypatch):
        # ⚠️ It @-mentions the whole community by design. A weekly mention
        # each is useful; a weekly notification each is how a topic gets
        # muted, and this is the one topic that must not be.
        assert _fire(monkeypatch, {}).sent[0][3].get("silent") is True


class TestItKeepsItsHistory:
    def test_it_deletes_nothing(self, monkeypatch):
        # ⭐ The opposite choice to the recruit advert, and deliberate: a
        # run of these posts IS the record of the community over time.
        state = {"recruit_focus_msg_id": 999}
        assert _fire(monkeypatch, state).deleted == []

    def test_it_stores_no_message_id(self, monkeypatch):
        state = {}
        _fire(monkeypatch, state)
        assert list(state) == ["players", "last_community_roster"], (
            "nothing needs to find this post again, so nothing should be "
            "keeping an id for it")


class TestItIsRegisteredEverywhereItHasToBe:
    def test_the_checker_runs_it(self):
        # Or it never runs at all.
        import inspect

        import checker
        assert "Community roster" in inspect.getsource(checker._run_checks)

    def test_the_schedule_post_knows_about_it(self):
        # Or it runs and the schedule silently under-reports itself.
        from scheduled.schedule_intervals import INTERVAL_JOBS
        job = [j for j in INTERVAL_JOBS if j.key == "last_community_roster"]
        assert job, "not in INTERVAL_JOBS"
        assert job[0].days == 7
        assert job[0].checks == ("Community roster",), (
            "the checks tuple must match the label in checker._run_checks")

    def test_the_state_key_survives_a_save(self):
        # ⭐⭐ Or the gate sees "never run" every hour and the roster is
        # posted every hour. This is the schedule-post bug exactly.
        from state_schema import PARTITIONS, DEFAULT_STATE
        declared = {k for keys in PARTITIONS.values() for k in keys}
        assert "last_community_roster" in declared
        assert "last_community_roster" in DEFAULT_STATE
