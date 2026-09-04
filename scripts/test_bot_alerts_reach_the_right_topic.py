"""Where the alerts go, and whether a failed send admits it.

Split from ``test_the_debug_topic_gets_the_whole_story`` on 2026-09-04.

⛔ Two destinations with opposite economics, and mixing them up is the
failure this guards. The bot topic orphans every message it receives
after 48h, so it gets the short rationed alert. "The Bot is Dead" (Nudge
Bot Notifications topic 767) is a log meant to accumulate, so it gets
everything, ungated on fault.
"""

import pytest

from _test_preflight_helpers import NOW, REPO, THIS_RUN, at, heartbeat, run
from preflight import alerting, gate


class TestTheDestinationsStayApart:
    """⛔ The verbose report must never reach the bot topic. Messages
    there are unrecorded and become undeletable orphans after 48h."""

    @pytest.fixture(autouse=True)
    def _capture(self, monkeypatch):
        # ⭐ The REAL config.json is loaded on purpose. These assertions
        # therefore pin the live destinations: changing either id in
        # config breaks this test rather than silently redirecting the
        # bot's alerts somewhere nobody is reading.
        self.sent = []
        monkeypatch.setattr(alerting, "_send",
                            lambda chat, thread, text, label:
                            self.sent.append((chat, thread, label)))

    def test_debug_goes_to_the_configured_debug_topic(self):
        alerting.notify_debug("x")
        chat, thread, label = self.sent[0]
        assert label == "debug"
        assert (chat, thread) == (-1004303231713, 767)

    def test_alerts_still_go_to_the_bot_topic(self):
        """⭐ Can-fail counterpart: proves the two are actually different
        destinations and not both reading one config key."""
        alerting.notify("x")
        chat, thread, label = self.sent[0]
        assert label == "alert"
        assert (chat, thread) == (-1001661053273, 137393)


class TestSendReportsFailureHonestly:
    """⚠️ Until 2026-09-04 this printed "alert sent" without reading the
    response, so a wrong topic id looked like success."""

    def _send(self, monkeypatch, capsys, response):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setattr(alerting.requests, "post",
                            lambda *a, **k: response)
        alerting._send(-100, 767, "x", "debug")
        return capsys.readouterr().out

    def test_a_rejected_send_says_so(self, monkeypatch, capsys):
        class _R:
            status_code, text = 400, "Bad Request: message thread not found"
        out = self._send(monkeypatch, capsys, _R())
        assert "REJECTED" in out and "thread not found" in out

    def test_an_accepted_send_says_where_it_went(self, monkeypatch, capsys):
        class _R:
            status_code, text = 200, "{}"
        assert "sent to -100/767" in self._send(monkeypatch, capsys, _R())

    def test_a_missing_destination_is_named_not_silent(self, monkeypatch, capsys):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        alerting._send(None, 767, "x", "debug")
        assert "no token or no debug destination" in capsys.readouterr().out


class TestTheGateReportsWhenItMatters:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "o.txt"))
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_RUN_ID", THIS_RUN)
        self.debugs = []
        monkeypatch.setattr(gate, "notify_debug", self.debugs.append)
        monkeypatch.setattr(gate, "send_alert", lambda *a, **k: None)
        monkeypatch.setattr(gate, "write_heartbeat", lambda *a, **k: {})

    def _main(self, runs, age, monkeypatch):
        monkeypatch.setattr(gate, "fetch_runs", lambda *a, **k: runs)
        monkeypatch.setattr(gate, "read_heartbeat", lambda *a, **k: heartbeat(age))
        monkeypatch.setattr(gate, "heartbeat_age_hours", lambda r, n: age)
        return gate.main()

    def test_a_halt_sends_the_report(self, monkeypatch):
        runs = [run(THIS_RUN, 0.0), run(91, 1.0, "failure"), run(90, 3.3)]
        self._main(runs, 3.3, monkeypatch)
        assert len(self.debugs) == 1
        assert "A PUSH LIKELY FAILED" in self.debugs[0]

    def test_a_suppressed_gap_also_sends_it(self, monkeypatch):
        """⭐ The interesting case: nothing halted, but the report is how
        we see the 2026-09-04 fix working in production."""
        self._main([run(THIS_RUN, 0.0), run(90, 3.3)], 3.3, monkeypatch)
        assert len(self.debugs) == 1
        assert "NOT HALTING" in self.debugs[0]

    def test_a_healthy_run_sends_nothing(self, monkeypatch):
        """⛔ Can-fail counterpart. Reporting every run would be 48 a day
        and the signal would drown."""
        self._main([run(THIS_RUN, 0.0), run(90, 0.5)], 0.5, monkeypatch)
        assert self.debugs == []


class TestTheWatchdogReportsToo:
    """⭐⭐ The watchdog runs when the main workflow is NOT, so during a
    delivery outage it is the only thing still speaking. If it stayed
    quiet the debug topic would go silent exactly when it is needed.

    ⛔ This class exists because a mutation deleting the watchdog's
    ``notify_debug`` call survived the whole suite: every earlier test
    captured its debug output and none asserted on it.
    """

    def _watch(self, monkeypatch, age_hours):
        from preflight import watchdog
        debugs, alerts = [], []
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setattr(watchdog, "read_heartbeat", lambda: heartbeat(age_hours))
        monkeypatch.setattr(watchdog, "heartbeat_age_hours",
                            lambda record, now: age_hours)
        monkeypatch.setattr(watchdog, "dispatch", lambda r, t: (True, "ok"))
        watchdog.watch(fetch_runs=lambda r, t: [run(90, 3.3)],
                       send_alert=lambda *a, **k: alerts.append(a),
                       notify=None, notify_debug=debugs.append)
        return debugs

    def test_an_outage_reaches_the_debug_topic(self, monkeypatch):
        debugs = self._watch(monkeypatch, 9.0)
        assert len(debugs) == 1
        assert "Bot diagnostic" in debugs[0]

    def test_it_reports_every_tick_not_on_the_alert_ration(self, monkeypatch):
        """⭐ 9.0h is deliberately NOT an alert hour (onset, 3h, then
        daily), so this proves the debug report is ungated rather than
        riding on the rationed alert."""
        from preflight.prior_runs import broken_hours, should_alert
        assert not should_alert(broken_hours(0, 9.0)), "pick a non-alert hour"
        assert len(self._watch(monkeypatch, 9.0)) == 1

    def test_a_healthy_bot_reports_nothing(self, monkeypatch):
        """⛔ Can-fail counterpart: ungated on FAULT, not unconditional."""
        assert self._watch(monkeypatch, 0.5) == []
