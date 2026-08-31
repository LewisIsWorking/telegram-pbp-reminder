"""The scheduler line must actually reach the daily diagnostic.

⛔ Proven is not the same as reachable. test_schedule_delivery tests
the functions that build the line; none of that shows the diagnostic
calls them. A guard nothing invokes is exactly how a measured, tested,
green line never appears in the message anybody reads.

Split from that file on 2026-08-31 at the 200-line limit.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _run(hours_ago: float, event: str = "schedule") -> dict:
    return {"id": 1000 + int(hours_ago * 10), "event": event,
            "created_at": (_NOW - timedelta(hours=hours_ago)).isoformat()
                          .replace("+00:00", "Z")}


class TestItActuallyReachesTheReport:
    def _analysis(self):
        return {"issues": {}, "events": [], "runs_with_errors": 0}

    def test_the_report_carries_the_scheduler_line(self):
        from scheduled.diagnostic_analysis import _build_report
        report = _build_report(self._analysis(), 4, _NOW,
                               scheduler_line="⚠️ Scheduler: 4 of 48",
                               logs_read=4)
        assert "⚠️ Scheduler: 4 of 48" in report

    def test_the_report_says_how_many_logs_it_actually_read(self):
        # The run count and the number of logs opened are two different
        # figures; _LOG_CAP truncates the second. Saying only the first
        # presents a sample as the whole.
        from scheduled.diagnostic_analysis import _build_report
        report = _build_report(self._analysis(), 48, _NOW, logs_read=24)
        assert "48 runs" in report and "logs read for 24" in report

    def test_the_diagnostic_builds_the_line_from_the_full_run_list(self, monkeypatch):
        # ⭐⭐ End to end through run_daily_diagnostic: 4 scheduled runs
        # where 48 were asked for must reach the posted message.
        import telegram as tg
        from scheduled import diagnostic
        sent = []
        runs = [_run(i * 5) for i in range(4)] + [_run(2, "push")]
        monkeypatch.setattr(diagnostic, "_gh_request",
                            lambda path: {"workflow_runs": runs})
        monkeypatch.setattr(diagnostic, "_fetch_run_log", lambda run_id: "")
        monkeypatch.setattr(tg, "send_message",
                            lambda g, t, b, **k: sent.append(b) or True)
        diagnostic.run_daily_diagnostic(
            {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 12},
            {}, now=_NOW)
        assert sent, "the diagnostic posted nothing"
        assert "4 of 48" in sent[0], sent[0]

    def test_a_window_with_no_runs_still_reports(self, monkeypatch):
        # ⛔ The early return used to be a bare `return`, so a total
        # scheduler outage suppressed the one message about it.
        import telegram as tg
        from scheduled import diagnostic
        sent = []
        monkeypatch.setattr(diagnostic, "_gh_request",
                            lambda path: {"workflow_runs": [_run(100)]})
        monkeypatch.setattr(tg, "send_message",
                            lambda g, t, b, **k: sent.append(b) or True)
        state = {}
        diagnostic.run_daily_diagnostic(
            {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 12},
            state, now=_NOW)
        assert sent and "0 of 48" in sent[0], sent
        assert state.get("last_diagnostic"), "not marked posted, so it repeats"

    def test_the_page_size_is_the_one_passed_to_the_api(self):
        # A page size the request does not use would make the "at least"
        # marker fire on the wrong boundary.
        import inspect
        from scheduled import diagnostic
        source = inspect.getsource(diagnostic.run_daily_diagnostic)
        assert "per_page={_RUNS_PAGE}" in source
