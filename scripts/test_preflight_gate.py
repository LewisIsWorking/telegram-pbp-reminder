"""The gate's I/O edges: fail-open, always-exit-0, and the halt output.

The arithmetic lives in ``test_preflight_prior_runs.py``. What matters
here is that the gate never takes the bot down with it, and never disarms
itself by mistaking "could not tell" for "all clear".
"""

import json

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
    """Keep the heartbeat out of the working tree during tests."""
    monkeypatch.setattr(gate, "write_heartbeat", lambda: {"written_at": "x"})


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
                            lambda streak, repo: self.alerts.append(streak))

    def _run_with(self, conclusions, monkeypatch):
        monkeypatch.setattr(gate, "fetch_conclusions",
                            lambda *a, **k: conclusions)
        return gate.main()

    def test_halts_on_a_failing_streak(self, monkeypatch):
        assert self._run_with(["failure"] * 25, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=true\n"

    def test_does_not_halt_when_healthy(self, monkeypatch):
        # ⭐ can-fail counterpart to the test above.
        assert self._run_with(["success", "success"], monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_fails_open_when_history_is_unreadable(self, monkeypatch):
        # ⚠️ "Could not tell" must never halt: the gate would be unable to
        # reopen, because reopening requires reading the history it cannot
        # reach. Loud in the log, permissive in effect.
        assert self._run_with(None, monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_fails_open_outside_actions(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert gate.main() == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"

    def test_alerts_when_it_trips(self, monkeypatch):
        self._run_with(["failure", "failure", "success"], monkeypatch)
        assert self.alerts == [2]

    def test_no_alert_on_the_quiet_streak_lengths(self, monkeypatch):
        self._run_with(["failure"] * 3 + ["success"], monkeypatch)
        assert self.alerts == []

    def test_no_alert_while_healthy(self, monkeypatch):
        self._run_with(["success"], monkeypatch)
        assert self.alerts == []

    def test_writes_the_heartbeat_before_deciding(self, monkeypatch):
        # The heartbeat is what makes the NEXT run's evidence honest, so
        # it must be written even on the run that halts.
        written = []
        monkeypatch.setattr(gate, "write_heartbeat",
                            lambda: written.append(True) or {})
        self._run_with(["failure"] * 5, monkeypatch)
        assert written == [True]


class TestHeartbeat:
    def test_writes_a_record_that_changes_every_run(self, tmp_path, monkeypatch):
        from datetime import datetime, timezone

        from preflight.heartbeat import write_heartbeat
        path = tmp_path / "state" / "ci_heartbeat.json"
        monkeypatch.setenv("GITHUB_RUN_ID", "123")
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
        record = write_heartbeat(datetime(2026, 8, 19, tzinfo=timezone.utc),
                                 path=str(path))
        assert record["last_run_id"] == "123"
        assert record["last_run_attempt"] == "2"
        assert json.loads(path.read_text(encoding="utf-8"))["written_at"].startswith("2026-08-19")

    def test_default_path_is_anchored_to_the_repo_not_the_cwd(self):
        # ⭐ The workflow runs this as `cd scripts && python -m preflight.gate`.
        # A cwd-relative default would write scripts/data/ci_heartbeat.json,
        # which the commit step's `git add data/` never sees - so the file
        # would exist, look correct, and never be pushed. The heartbeat's
        # whole job is to make the push happen, so that miss would be silent
        # and total.
        import os

        from preflight import heartbeat
        assert os.path.isabs(heartbeat.HEARTBEAT_PATH)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(heartbeat.__file__))))
        assert heartbeat.HEARTBEAT_PATH == os.path.join(
            repo_root, "data", "ci_heartbeat.json")
        # And it must sit OUTSIDE data/state/, whose schema registry demands
        # an owning module and a runtime reader the heartbeat does not have.
        assert os.path.join("data", "state") not in heartbeat.HEARTBEAT_PATH

    def test_a_rerun_of_the_same_run_still_differs(self, monkeypatch):
        # ⚠️ Re-running a failed run reuses GITHUB_RUN_ID. That is exactly
        # when a human is retrying a broken push, so the file must still
        # change or there would be nothing to commit and nothing to prove.
        from datetime import datetime, timezone

        from preflight.heartbeat import build_heartbeat
        now = datetime(2026, 8, 19, tzinfo=timezone.utc)
        assert build_heartbeat("123", "1", now) != build_heartbeat("123", "2", now)
