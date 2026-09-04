"""The CI workflow must gate merges, and must never post from a PR.

Two holes found on 2026-08-27, both of which let test fixtures reach the
group as 43 imaginary messages from a player who does not exist.

## 1. Nothing ran the tests before a merge

The ``test`` job was gated on ``push || workflow_dispatch``. There was no
``pull_request`` trigger at all, so every guard in this suite gated
nothing at review time. PR #64 committed a queue file built entirely
from test fixtures and merged green.

## 2. The test step swallowed pytest's exit code

    set +e
    python -m pytest ... | tee /tmp/pytest_output.txt
    EXIT_CODE=${PIPESTATUS[0]}
    set -e
    if [ $EXIT_CODE -ne 0 ]; then
      python3 scripts/ci_alert.py
    fi

The last command is the ``if``. When tests failed it ran the alert and
the step exited **0**, so the job was green. The suite could not fail the
build even on push: it could only send a message about it.

## ⛔ And the trap while fixing it

The ``run`` job was gated on ``github.event_name != 'schedule' || ...``.
A denylist. Adding the ``pull_request`` trigger would have satisfied it
on every PR, and that job posts to Telegram, writes state and pushes
commits. **A condition phrased as "not X" opts in every trigger anyone
adds later.** Both job conditions are now allowlists, and this file
fails if either reverts.
"""

import os

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml
    yaml = None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WF = os.path.join(_ROOT, ".github", "workflows", "pbp-reminder.yml")

# Jobs that reach the outside world: they send Telegram messages, write
# state and push commits. None of them may run for a pull_request.
SIDE_EFFECTING = ("run", "run-queue")


def _workflow() -> dict:
    if yaml is None:  # pragma: no cover
        pytest.skip("pyyaml not installed")
    with open(_WF, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _triggers(doc: dict) -> dict:
    # PyYAML parses the bare key `on:` as the boolean True.
    return doc.get("on") or doc.get(True) or {}


def _condition(doc: dict, job: str) -> str:
    return str(doc["jobs"][job].get("if", ""))


class TestPullRequestsAreGated:
    def test_the_workflow_parses(self):
        # ⭐ Without this, a syntax error would make every assertion
        # below error rather than fail, and the reason would be buried.
        assert _workflow()["jobs"], "no jobs parsed from the workflow"

    def test_pull_request_is_a_trigger(self):
        assert "pull_request" in _triggers(_workflow())

    def test_the_test_job_runs_for_it(self):
        assert "pull_request" in _condition(_workflow(), "test")


class TestNothingPostsFromAPullRequest:
    @pytest.mark.parametrize("job", SIDE_EFFECTING)
    def test_the_job_never_fires_on_a_pull_request(self, job):
        # ⭐⭐ The one that matters. These jobs message real players.
        doc = _workflow()
        condition = _condition(doc, job)
        assert "pull_request" not in condition, (
            f"the {job} job's condition mentions pull_request: {condition}")

    @pytest.mark.parametrize("job", SIDE_EFFECTING)
    def test_the_condition_is_an_allowlist_not_a_denylist(self, job):
        # ⛔ `event_name != 'schedule'` is TRUE for pull_request, and for
        # every trigger type added in future. The bug is not that it was
        # wrong, it is that it was wrong by default.
        condition = _condition(doc=_workflow(), job=job)
        assert "!=" not in condition, (
            f"the {job} job is gated by a denylist ({condition}). Any new "
            f"trigger opts in automatically, including pull_request, and "
            f"this job posts to Telegram.")
        assert "==" in condition, f"the {job} job has no positive condition"


class TestAFailingSuiteFailsTheBuild:
    def _test_step(self) -> str:
        # ⚠️ Match the INVOCATION, not the word. The first version looked
        # for "pytest" and matched `pip install ... pytest ...`, so it
        # asserted against the dependency step and failed for a reason
        # that had nothing to do with the property being tested.
        for step in _workflow()["jobs"]["test"]["steps"]:
            if "python -m pytest" in str(step.get("run", "")):
                return step["run"]
        raise AssertionError("no step in the test job invokes pytest")

    def test_the_exit_code_is_propagated(self):
        # ⭐⭐ Before this, a red suite sent an alert and exited 0. The
        # tests could not fail the build, only complain about it.
        assert "exit $EXIT_CODE" in self._test_step(), (
            "the pytest step does not propagate its exit code, so a "
            "failing suite leaves the job green")

    def _alert_step(self) -> dict:
        for step in _workflow()["jobs"]["test"]["steps"]:
            if "ci_alert.py" in str(step.get("run", "")):
                return step
        raise AssertionError("nothing in the test job runs ci_alert.py")

    def test_the_alert_still_fires(self):
        # can-fail counterpart: propagating the code must not have
        # removed the notification. Moved to its own step on 2026-09-04
        # (see below), so this looks for the step rather than the string.
        assert "failure()" in str(self._alert_step().get("if", "")), (
            "the alert step is not conditioned on failure, so it either "
            "never runs or runs on every green build")

    def test_the_pytest_step_holds_no_real_credential(self):
        # ⛔⛔ 2026-09-04: the suite posted 14 fixture-filled diagnostics
        # into the live debug topic from CI, because the pytest step
        # carried the real bot token for the alert that shared it.
        # _test_no_real_network blocks the calls; this keeps the
        # credential itself out of reach of anything the suite runs.
        token = self._test_step_env().get("TELEGRAM_BOT_TOKEN", "")
        assert "secrets." not in str(token), (
            f"the pytest step has the real bot token ({token!r}); a "
            f"leaking test can then send for real")
        assert "never-valid" in str(token), (
            "keep an obviously fake token here so the sending code path "
            "is still exercised rather than skipped")

    def test_the_alert_step_does_have_it(self):
        # ⭐ Can-fail counterpart: the credential must have MOVED, not
        # been deleted, or a red suite would notify nobody.
        env = self._alert_step().get("env", {})
        assert "secrets.TELEGRAM_BOT_TOKEN" in str(
            env.get("TELEGRAM_BOT_TOKEN", ""))

    def _test_step_env(self) -> dict:
        for step in _workflow()["jobs"]["test"]["steps"]:
            if "python -m pytest" in str(step.get("run", "")):
                return step.get("env", {})
        raise AssertionError("no step in the test job invokes pytest")


class TestTheDataGateExists:
    def test_a_step_fails_on_a_dirty_data_directory(self):
        # The generic backstop for write paths nobody has enumerated.
        # test_tests_never_touch_real_data.py checks the writers we know
        # about; this checks the invariant for the ones we do not.
        steps = _workflow()["jobs"]["test"]["steps"]
        gate = [s for s in steps
                if "git status --porcelain data/" in str(s.get("run", ""))]
        assert gate, "no step fails the build when the suite dirties data/"
        assert "exit 1" in gate[0]["run"], (
            "the data gate prints but does not fail; a printed fault is "
            "not a gate")
