"""Read this workflow's own run history from the Actions API.

Extracted from ``preflight/gate.py`` on 2026-09-04, which reached 212
lines once the gate had to know *when* runs happened and not merely how
they ended. Asking GitHub what it has run is I/O against a service that
lies by omission and occasionally by cache; deciding what to do about the
answer is arithmetic. Those are different jobs with different failure
modes, and only this one touches the network.

⚠️ The API is treated as convenient corroboration, never as authority.
``prior_runs`` explains why: on 2026-08-19 it served a cached page of
runs from three days earlier and the gate believed it. Anything built on
top of what this module returns has to survive being handed stale data -
see ``delivery_gap.history_is_fresh`` for the one proof that it is not.
"""

import requests

WORKFLOW_FILE = "pbp-reminder.yml"
RUNS_TO_INSPECT = 40


def fetch_runs(repo: str, token: str, *, branch: str = "main",
               session=requests) -> list | None:
    """Recent runs of this workflow, newest first, as GitHub returns them.

    Returns ``None`` - distinct from ``[]`` - when the history could not
    be read at all. An empty list is a real answer meaning "no prior
    runs"; ``None`` means "no answer", and only the second one may skip
    the check. Collapsing the two would let an auth failure read as a
    clean history and quietly disarm the gate.

    ⭐ Widened from ``fetch_conclusions`` on 2026-09-04. The conclusions
    alone cannot say WHEN a run happened, and without that a stale
    heartbeat caused by GitHub skipping the cron is indistinguishable
    from one caused by a failed push. See ``preflight/delivery_gap``.
    """
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
    try:
        response = session.get(
            url,
            params={"branch": branch, "per_page": RUNS_TO_INSPECT,
                    "exclude_pull_requests": "true"},
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"},
            timeout=20,
        )
        if response.status_code != 200:
            print(f"[preflight] could not read run history: HTTP "
                  f"{response.status_code}. Proceeding without the check.")
            return None
        return response.json().get("workflow_runs", [])
    except Exception as error:  # noqa: BLE001 - any failure means "no answer"
        print(f"[preflight] could not read run history: {error}. "
              f"Proceeding without the check.")
        return None


def fetch_conclusions(repo: str, token: str, **kwargs) -> list | None:
    """Just the conclusions, for callers that need nothing else.

    ⚠️ Preserves the None-vs-[] distinction ``fetch_runs`` establishes; a
    comprehension over None would raise instead of meaning "no answer".
    """
    runs = fetch_runs(repo, token, **kwargs)
    return None if runs is None else [run.get("conclusion") for run in runs]
