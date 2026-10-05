"""Judge each prior run by the job that pushes state, not the whole workflow.

Added 2026-10-05. Between 19:43 and 20:58 UTC GitHub's hosted runners
stopped picking up jobs ("The job was not acquired by Runner of type hosted
even after multiple attempts"). Three runs went red and the gate paused
posting. But in two of them the ``run`` job had run, pushed state and gone
green; only the separate ``test`` job was never picked up. The third had no
job picked up at all, so it posted nothing and lost nothing.

The gate's question is "did this run's state reach the remote?"
(``prior_runs.consecutive_failures``). The workflow's conclusion answered a
different one, "did every job pass?", and a test job GitHub never started
is no evidence about state at all.

So each red run is re-judged by its state jobs (``run`` and ``run-queue``,
the two that commit and push):

  a state job succeeded            "success": its push landed.
  no state job was ever picked up  None: GitHub never ran it, so it is not
                                   evidence either way, the same treatment
                                   ``consecutive_failures`` gives a run
                                   still in progress.
  a state job ran and did not pass "failure", as before.

⚠️ Only ever MORE lenient on positive evidence, never on a missing answer.
If the jobs cannot be read, the run keeps its red conclusion. The committed
heartbeat still catches any run that went green without pushing.
"""

import requests

SUCCESS = "success"
# The two jobs in pbp-reminder.yml with a "Commit data" step.
STATE_JOBS = ("run", "run-queue")


def state_verdict(jobs: list) -> str | None:
    """The run's conclusion as far as state is concerned. See module doc."""
    started = [j for j in jobs
               if j.get("name") in STATE_JOBS
               and (j.get("steps") or j.get("runner_name"))]
    if any(j.get("conclusion") == SUCCESS for j in started):
        return SUCCESS
    if not started:
        return None
    return "failure"


def judged_conclusions(runs: list, fetch_jobs) -> list:
    """Conclusions newest first, with each red run re-judged by its state jobs.

    Stops looking up jobs at the first success, since the streak ends there
    and older runs cannot change it. ``fetch_jobs(run_id)`` returns the jobs
    list, or None when it could not be read.
    """
    out, settled = [], False
    for run in runs:
        conclusion = run.get("conclusion")
        if not settled and conclusion not in (None, SUCCESS):
            jobs = fetch_jobs(run.get("id"))
            if jobs is not None:
                conclusion = state_verdict(jobs)
        settled = settled or conclusion == SUCCESS
        out.append(conclusion)
    return out


def make_fetch_jobs(repo: str, token: str, session=requests):
    """A ``fetch_jobs`` for ``judged_conclusions`` against the real API."""
    def fetch_jobs(run_id) -> list | None:
        if not run_id:
            return None
        try:
            response = session.get(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs",
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json"},
                timeout=20)
            if response.status_code != 200:
                return None
            return response.json().get("jobs")
        except (requests.RequestException, ValueError):
            return None
    return fetch_jobs
