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

⛔ **``GITHUB_TOKEN`` CANNOT DO THIS.** GitHub deliberately refuses to
start new workflow runs from events created with the automatic token, to
stop a workflow triggering itself forever. Self-repair therefore needs a
PAT (``GIST_TOKEN`` here, which already exists for the diagnostic). If
the token is missing or lacks ``actions: write`` this module says so out
loud rather than failing quietly, because a self-repair that silently
does nothing is worse than none: it looks like cover that is not there.

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
        return False, ("no PAT available (GIST_TOKEN unset), and the "
                       "automatic GITHUB_TOKEN cannot start a run")
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
                           f"workflows. GIST_TOKEN needs the 'workflow' "
                           f"scope (classic) or actions:write (fine-grained).")
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
