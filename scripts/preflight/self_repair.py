"""When the bot has stopped running, start it again.

Added 2026-09-01. Lewis, after I mis-wired the crons and every scheduled
run came back ``skipped`` for 15 hours: *"you should really be able for
the bot to fix itself or something, killing itself like that is not
good."*

He is right, and the fix I shipped first only made the outage **visible**.
This makes it **recoverable**.

⭐⭐ **THE TRICK IS ALREADY IN THE MAIN WORKFLOW'S OWN CONDITION.** The
full-pass job runs on::

    github.event_name == 'push'
    || github.event_name == 'workflow_dispatch'
    || (github.event_name == 'schedule' && github.event.schedule == '...')

A **``workflow_dispatch`` satisfies that regardless of what the cron
literals say.** So a watchdog that dispatches the main workflow when the
heartbeat goes stale would have carried the bot straight through the
2026-08-31 outage: the schedule branch was dead, the dispatch branch was
not, and nobody would have noticed until the next commit.

⛔⛔ **CORRECTED 2026-09-02. I HAD THE TOKEN RULE BACKWARDS.** This module
was written asserting that ``GITHUB_TOKEN`` cannot start a run and that a
PAT was therefore required. The self-repair then fired for real, on the
outage it was built for, and returned::

    Could not force a run: HTTP 403: the token cannot dispatch workflows.

GitHub's docs say the opposite of what I assumed:

> *"events triggered by the ``GITHUB_TOKEN`` will not create a new
> workflow run, **with the following exceptions: workflow_dispatch and
> repository_dispatch events always create workflow runs**."*

The recursion guard I was thinking of is real, and `workflow_dispatch` is
explicitly exempt from it. So the automatic token works, needs no setup
from anyone, and only needs ``actions: write`` on the job.

⭐ The PAT is kept as a **fallback**, not the primary. A repository whose
default token permissions are locked down would still have a route.

⚠️ Either way, a failure says so out loud and names the fix, because a
self-repair that silently does nothing is worse than none: it looks like
cover that is not there. That property is what turned a wrong assumption
into a precise error message instead of a mystery.

⚠️ **Only ever dispatches on a POSITIVE reading of staleness.** An
unreadable heartbeat means "cannot tell", and cannot-tell must not
trigger anything. That is the same rule ``prior_runs`` uses for halting,
pointed the other way.
"""

import json
import os
import urllib.error
import urllib.request

# The main workflow runs twice an hour. Two hours with no state push is
# not scheduler jitter, it is broken. Deliberately looser than the 3h
# posting gate: this decides whether to spend a run, not whether it is
# safe to speak.
REPAIR_AFTER_HOURS = 2.0

WORKFLOW_FILE = "pbp-reminder.yml"


def dispatch_token(env: dict) -> str:
    """The token to dispatch with: the automatic one first.

    ⭐ ``GITHUB_TOKEN`` needs no setup by anyone and is exempt from the
    recursion guard for ``workflow_dispatch``. The PAT is a fallback for
    a repository whose default token permissions are locked down, so
    self-repair still has a route there.

    ⚠️ Order matters and is asserted by a test. Preferring the PAT would
    make the feature depend on a secret that may not exist, which is how
    the 2026-09-02 self-repair failed with a 403 on the one outage it was
    built for.
    """
    return (env.get("GITHUB_TOKEN") or env.get("GIST_TOKEN") or "").strip()


def should_repair(age_hours: float | None) -> bool:
    """True when the heartbeat is stale enough to force a run.

    ``None`` means the heartbeat could not be read at all. That is not
    evidence of an outage and must not dispatch anything.
    """
    return age_hours is not None and age_hours > REPAIR_AFTER_HOURS


def dispatch(repo: str, token: str, ref: str = "main",
             workflow: str = WORKFLOW_FILE) -> tuple[bool, str]:
    """Ask GitHub to start the main workflow. Returns (ok, explanation).

    Never raises. A watchdog that dies while reporting a death helps
    nobody.
    """
    if not token:
        return False, "no token available (neither GITHUB_TOKEN nor GIST_TOKEN)"
    if not repo:
        return False, "GITHUB_REPOSITORY unset"

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    body = json.dumps({"ref": ref}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status == 204:
                return True, f"dispatched {workflow} on {ref}"
            return False, f"unexpected status {response.status}"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, (f"HTTP {error.code}: the token cannot dispatch "
                           f"workflows. The watchdog job needs "
                           f"`permissions: actions: write`, or GIST_TOKEN "
                           f"needs the 'workflow' scope.")
        return False, f"HTTP {error.code}"
    except (urllib.error.URLError, OSError) as error:
        return False, f"network error: {error}"


def repair_message(ok: bool, detail: str, age_hours: float) -> str:
    """What the operator is told. Says what it did, not just what it saw."""
    head = (f"\U0001f527 Bot self-repair: no state push for "
            f"{age_hours:.1f}h (limit {REPAIR_AFTER_HOURS:g}h).")
    if ok:
        return (f"{head}\nForced a run via workflow_dispatch. If this keeps "
                f"happening the schedule is not firing; check the cron and "
                f"the job conditions against each other.")
    return (f"{head}\n⛔ Could not force a run: {detail}\n"
            f"The bot is down and cannot restart itself.")
