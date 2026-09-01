"""Run the bot from OUTSIDE GitHub, because GitHub's scheduler is the fault.

    python3 tools/external_heartbeat.py

⛔⛔ **THE WATCHDOG CANNOT SAVE US FROM THIS ONE, AND THAT IS THE POINT.**
`.github/workflows/watchdog.yml` is itself schedule-driven, so it shares
the exact failure mode it exists to detect. It recovers a *broken
workflow*. It cannot recover a *scheduler that has stopped delivering*,
because then the watchdog does not run either.

Measured 2026-09-01, after moving the crons off the contended `:00`/`:30`
minutes, which was supposed to fix delivery:

```
2026-08-30   18 / 48   38%
2026-08-31    3 / 48    6%
2026-09-01    8 / 48   17%
worst gap 27.8h
```

The bot asks GitHub for 48 runs a day and gets between 3 and 18. On
2026-08-31 it got none at all for 15 hours, which stranded three
messages permanently past Telegram's 48h delete wall. **Uptime is a
correctness requirement for this bot, not a nice-to-have**, and it is
currently outsourced to something that does not provide it.

So: something outside GitHub asks GitHub to run the workflow. A
`workflow_dispatch` satisfies the run job's condition regardless of what
the schedule does or does not deliver.

⚠️ **It only dispatches when the bot has actually gone quiet**, so on a
day when GitHub behaves this costs nothing. Duplicate runs would be
harmless anyway (the `pbp-checker` concurrency group serialises them and
the checker is offset-driven), but a quiet script is easier to trust.

⛔ A `skipped` run DOES NOT COUNT as the bot running. That distinction is
the whole of the 2026-08-31 outage: every run was skipped, nothing was
red, and no counter that looked at "did a run happen" noticed.

## Setting it up on the VPS

```bash
# 1. A PAT with `workflow` scope (classic) or actions:write (fine-grained).
#    ⛔ NEVER commit it. 600 perms, outside the repo.
install -m 600 /dev/null ~/.pathwars-dispatch-token
echo 'ghp_xxx' > ~/.pathwars-dispatch-token

# 2. Every 15 minutes, quietly.
crontab -e
*/15 * * * * GITHUB_TOKEN=$(cat ~/.pathwars-dispatch-token) \\
    /usr/bin/python3 /opt/pathwars/external_heartbeat.py >> /var/log/pathwars-heartbeat.log 2>&1
```
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("PATHWARS_REPO", "LewisIsWorking/telegram-pbp-reminder")
WORKFLOW = "pbp-reminder.yml"

# The bot asks for a run every 30 minutes. 45 gives one missed slot of
# grace before an outsider steps in, so normal jitter costs nothing.
QUIET_AFTER = timedelta(minutes=45)

# Conclusions that mean THE BOT ACTUALLY RAN. `skipped` is deliberately
# absent: on 2026-08-31 every run was skipped and the bot was dead.
RAN = {"success", "failure"}


def last_real_run(runs: list) -> datetime | None:
    """When the bot last actually ran, ignoring skipped and cancelled."""
    best = None
    for run in runs:
        if run.get("conclusion") not in RAN:
            continue
        stamp = run.get("created_at") or ""
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if best is None or when > best:
            best = when
    return best


def should_dispatch(runs: list, now: datetime) -> bool:
    """True when nothing has actually run inside the grace window.

    ⚠️ No runs at all returns True. An empty history is not evidence of
    health, and this is the one place where acting on "cannot tell" is
    correct: the cost of a redundant run is one cheap job, and the cost
    of not running is a permanently orphaned message.
    """
    last = last_real_run(runs)
    return last is None or (now - last) > QUIET_AFTER


def _api(path: str, token: str, data: dict | None = None):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        data=json.dumps(data).encode() if data else None,
        method="POST" if data else "GET",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status == 204:
            return {}
        return json.loads(response.read() or b"{}")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    if not token:
        print(f"{stamp} no GITHUB_TOKEN; cannot dispatch")
        return 1
    try:
        runs = _api(f"/actions/workflows/{WORKFLOW}/runs?per_page=20",
                    token).get("workflow_runs", [])
    except (urllib.error.URLError, OSError, ValueError) as error:
        print(f"{stamp} could not read run history: {error}")
        return 1

    last = last_real_run(runs)
    age = "never" if last is None else f"{(now - last).total_seconds() / 60:.0f}m ago"
    if not should_dispatch(runs, now):
        print(f"{stamp} bot ran {age}; nothing to do")
        return 0
    try:
        _api(f"/actions/workflows/{WORKFLOW}/dispatches", token, {"ref": "main"})
    except urllib.error.HTTPError as error:
        hint = (" (the token needs the 'workflow' scope, or actions:write)"
                if error.code in (401, 403) else "")
        print(f"{stamp} DISPATCH FAILED HTTP {error.code}{hint}")
        return 1
    except (urllib.error.URLError, OSError) as error:
        print(f"{stamp} DISPATCH FAILED: {error}")
        return 1
    print(f"{stamp} bot last ran {age}; dispatched a run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
