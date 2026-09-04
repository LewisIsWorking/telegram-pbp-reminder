"""The gate's I/O edges: fail-open, always-exit-0, and the halt output.

The arithmetic lives in ``test_preflight_prior_runs.py``. What matters
here is that the gate never takes the bot down with it, and never disarms
itself by mistaking "could not tell" for "all clear".
"""

from datetime import datetime, timezone

import pytest

from preflight import gate


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Session:
    """Stands in for ``requests``; records the call and returns canned data."""

    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


def _runs(*conclusions):
    return {"workflow_runs": [{"conclusion": c} for c in conclusions]}


@pytest.fixture(autouse=True)
def _no_real_heartbeat(monkeypatch, tmp_path):
    """Keep the heartbeat out of the working tree, and default it to fresh.

    Fresh by default so each test isolates the one signal it is about. The
    tests that care about the heartbeat override it explicitly.
    """
    monkeypatch.setattr(gate, "write_heartbeat", lambda: {"written_at": "x"})
    monkeypatch.setattr(gate, "read_heartbeat", lambda: {"written_at": "fresh"})
    monkeypatch.setattr(gate, "heartbeat_age_hours", lambda record, now: 0.2)


class TestFetchConclusions:
    def test_reads_conclusions_newest_first(self):
        session = _Session(_Response(200, _runs("failure", "success")))
        assert gate.fetch_conclusions("o/r", "tok", session=session) == \
            ["failure", "success"]

    def test_asks_for_the_right_branch_and_workflow(self):
        session = _Session(_Response(200, _runs()))
        gate.fetch_conclusions("o/r", "tok", session=session)
        url, kwargs = session.calls[0]
        assert gate.WORKFLOW_FILE in url
        assert kwargs["params"]["branch"] == "main"
        assert kwargs["headers"]["Authorization"] == "Bearer tok"

    def test_no_prior_runs_is_an_empty_list_not_none(self):
        # ⭐ The distinction the gate depends on: [] is a real answer that
        # must still be evaluated; None means the check could not run.
        session = _Session(_Response(200, _runs()))
        assert gate.fetch_conclusions("o/r", "tok", session=session) == []

    def test_http_error_is_none(self):
        session = _Session(_Response(403))
        assert gate.fetch_conclusions("o/r", "tok", session=session) is None

    def test_network_error_is_none(self):
        session = _Session(error=OSError("no route to host"))
        assert gate.fetch_conclusions("o/r", "tok", session=session) is None


class TestPublishHalt:
    def test_writes_the_output_github_actions_reads(self, tmp_path, monkeypatch):
        out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        gate.publish_halt(True)
        assert out.read_text(encoding="utf-8") == "halt=true\n"

    def test_writes_false_when_clear(self, tmp_path, monkeypatch):
        out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        gate.publish_halt(False)
        assert out.read_text(encoding="utf-8") == "halt=false\n"

    def test_silent_outside_actions(self, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        gate.publish_halt(True)  # must not raise


class TestMain:
    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, monkeypatch):
        self.out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(self.out))
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        self.alerts = []
        monkeypatch.setattr(gate, "send_alert",
                            lambda reasons, age, repo: self.alerts.append(reasons))
        # ⛔⛔ Not optional. `main` reports to the debug topic on any fault
        # since 2026-09-04, and unstubbed that is a REAL Telegram send:
        # five tests in this class posted fixture values ("25 consecutive
        # workflow runs failed", github.com/o/r/...) into the live "The
        # Bot is Dead" topic from CI, twice, before anyone noticed.
        self.debugs = []
        monkeypatch.setattr(gate, "notify_debug", self.debugs.append)

    def _run_with(self, conclusions, monkeypatch):
        """Drive main() from a list of conclusions, newest first.

        ⚠️ Each synthetic run is stamped ``created_at`` = now, i.e. AFTER
        any committed heartbeat. That is what these tests mean by "a
        history": runs ARE happening, and only their outcomes are in
        question. Unstamped, they would read as a delivery gap (see
        ``preflight/delivery_gap``) and the stale-heartbeat cases below
        would start passing for the wrong reason.
        """
        runs = None if conclusions is None else [
            {"id": 1000 + i, "conclusion": c,
             "created_at": datetime.now(timezone.utc).isoformat()}
            for i, c in enumerate(conclusions)]
        monkeypatch.setattr(gate, "fetch_runs", lambda *a, **k: runs)
        return gate.main()

    def test_halts_on_a_failing_streak(self, monkeypatch):
        assert self._run_with(["failure"] * 25, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=true\n"

    def test_does_not_halt_when_healthy(self, monkeypatch):
        # ⭐ can-fail counterpart to the test above.
        assert self._run_with(["success", "success"], monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_unreadable_history_alone_does_not_halt(self, monkeypatch):
        # ⚠️ "Could not tell" must never halt on its own: the gate would be
        # unable to reopen. Loud in the log, permissive in effect. The
        # heartbeat is still consulted, and here it is fresh.
        assert self._run_with(None, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_unreadable_history_cannot_clear_a_stale_heartbeat(self, monkeypatch):
        # ⭐ The 2026-08-19 miss, at the gate level: whatever the API does
        # or fails to do, a stale heartbeat still stops posting.
        monkeypatch.setattr(gate, "heartbeat_age_hours", lambda r, n: 15.0)
        assert self._run_with(None, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=true\n"

    def test_a_healthy_looking_history_cannot_clear_a_stale_heartbeat(self, monkeypatch):
        # ⭐⭐ The exact cached-API reading that fooled it: the API reports
        # nothing but successes while state has not moved for 15 hours.
        monkeypatch.setattr(gate, "heartbeat_age_hours", lambda r, n: 15.0)
        assert self._run_with(["success"] * 8, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=true\n"

    def test_fails_open_outside_actions(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert gate.main() == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_alerts_when_it_trips(self, monkeypatch):
        self._run_with(["failure", "failure", "success"], monkeypatch)
        assert len(self.alerts) == 1

    def test_no_alert_while_healthy(self, monkeypatch):
        self._run_with(["success"], monkeypatch)
        assert self.alerts == []

    def test_reads_the_committed_heartbeat_before_writing_its_own(self, monkeypatch):
        # ⚠️⚠️ Order is the whole mechanism. If this run's heartbeat were
        # written first, the gate would measure itself and every run would
        # look perfectly healthy, silently and permanently.
        order = []
        monkeypatch.setattr(gate, "read_heartbeat",
                            lambda: order.append("read") or {"written_at": "x"})
        monkeypatch.setattr(gate, "write_heartbeat",
                            lambda: order.append("write") or {})
        self._run_with(["success"], monkeypatch)
        assert order == ["read", "write"]

    def test_writes_the_heartbeat_even_on_a_run_that_halts(self, monkeypatch):
        written = []
        monkeypatch.setattr(gate, "write_heartbeat",
                            lambda: written.append(True) or {})
        self._run_with(["failure"] * 5, monkeypatch)
        assert written == [True]
