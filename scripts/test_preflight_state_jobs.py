"""Re-judging red runs by their state-pushing jobs (preflight/state_jobs)."""

from datetime import datetime, timezone

from preflight import gate
from preflight.state_jobs import judged_conclusions, state_verdict


def _job(name, conclusion, steps=3, runner="GitHub Actions 1"):
    return {"name": name, "conclusion": conclusion,
            "steps": [{}] * steps, "runner_name": runner if steps else ""}


def _never(name):
    """The shape GitHub gives a job no runner ever picked up."""
    return _job(name, "cancelled", steps=0)


class TestStateVerdict:
    def test_state_job_pushed_but_test_never_started(self):
        assert state_verdict([_job("run", "success"), _never("test")]) == "success"

    def test_queue_only_run_counts_too(self):
        assert state_verdict([_job("run-queue", "success"),
                              _job("run", "skipped", steps=0)]) == "success"

    def test_no_state_job_started_is_no_evidence(self):
        assert state_verdict([_never("run"), _never("test")]) is None

    def test_state_job_ran_and_failed(self):
        assert state_verdict([_job("run", "failure")]) == "failure"

    def test_state_job_cancelled_mid_run_still_fails(self):
        assert state_verdict([_job("run", "cancelled")]) == "failure"

    def test_a_green_test_job_proves_nothing_about_state(self):
        assert state_verdict([_job("test", "success"),
                              _job("run", "failure")]) == "failure"


class TestJudgedConclusions:
    def test_unreadable_jobs_keep_the_red_conclusion(self):
        runs = [{"id": 1, "conclusion": "failure"}]
        assert judged_conclusions(runs, lambda rid: None) == ["failure"]

    def test_stops_looking_up_after_the_first_success(self):
        asked = []

        def fetch(rid):
            asked.append(rid)
            return [_job("run", "success")]
        runs = [{"id": 1, "conclusion": None}, {"id": 2, "conclusion": "failure"},
                {"id": 3, "conclusion": "failure"}]
        assert judged_conclusions(runs, fetch) == [None, "success", "failure"]
        assert asked == [2]

    def test_green_runs_are_not_looked_up(self):
        def fetch(rid):
            raise AssertionError("looked up a green run")
        assert judged_conclusions([{"id": 1, "conclusion": "success"}],
                                  fetch) == ["success"]


def _gate_with(monkeypatch, tmp_path, conclusions, jobs):
    """Drive gate.main() offline; returns what it wrote to $GITHUB_OUTPUT."""
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    now = datetime.now(timezone.utc).isoformat()
    runs = [{"id": 1000 + i, "conclusion": c, "created_at": now}
            for i, c in enumerate(conclusions)]
    monkeypatch.setattr(gate, "fetch_runs", lambda *a, **k: runs)
    monkeypatch.setattr(gate, "make_fetch_jobs", lambda repo, token: jobs.get)
    monkeypatch.setattr(gate, "write_heartbeat", lambda: {"written_at": "x"})
    monkeypatch.setattr(gate, "read_heartbeat", lambda: {"written_at": "fresh"})
    monkeypatch.setattr(gate, "heartbeat_age_hours", lambda record, now: 0.2)
    # ⛔ Unstubbed, these are REAL Telegram sends (see test_preflight_gate).
    monkeypatch.setattr(gate, "send_alert", lambda *a: None)
    monkeypatch.setattr(gate, "notify_debug", lambda *a: None)
    gate.main()
    return out.read_text(encoding="utf-8")


def test_runner_outage_of_2026_10_05_does_not_pause(monkeypatch, tmp_path):
    """Three red runs, but the state job pushed in two and never started in
    the third. Posting was paused for it; it must not be."""
    pushed = [_job("run", "success", steps=13), _never("test")]
    never = [_never("run"), _never("test")]
    jobs = {1000: pushed, 1001: pushed, 1002: never}
    assert _gate_with(monkeypatch, tmp_path,
                      ["cancelled", "failure", "failure", "success"],
                      jobs) == "halt=false\n"


def test_a_state_job_that_ran_and_failed_still_pauses(monkeypatch, tmp_path):
    # ⭐ can-fail counterpart: real push failures keep their streak.
    failed = [_job("run", "failure", steps=9)]
    assert _gate_with(monkeypatch, tmp_path, ["failure", "failure", "success"],
                      {1000: failed, 1001: failed}) == "halt=true\n"
