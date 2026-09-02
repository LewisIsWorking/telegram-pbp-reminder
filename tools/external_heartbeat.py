"""Run the bot from OUTSIDE GitHub, because GitHub's scheduler is the fault.

    python3 tools/external_heartbeat.py

⛔⛔ **The watchdog cannot save the bot from this one, and that is the
point.** `.github/workflows/watchdog.yml` is itself schedule-driven, so
it shares the exact failure mode it exists to detect. It recovers a
*broken workflow*. It cannot recover a *scheduler that has stopped
delivering*, because then the watchdog does not run either.

⚠️ **2026-09-02: this is now a SECOND line of defence, not the only
one.** The in-repo watchdog can restart the bot on its own since its job
was given `actions: write` (it was failing with HTTP 403 on `read`, and
no PAT was ever needed: GitHub exempts `workflow_dispatch` from the
GITHUB_TOKEN recursion guard). This script still matters, because it is
the only thing that survives GitHub delivering **no schedules at all**,
which is precisely what the watchdog cannot survive.

Measured 2026-09-01, **after** moving the crons off the contended
`:00`/`:30` minutes, which was supposed to fix delivery:

```
2026-08-30   18 / 48   38%
2026-08-31    3 / 48    6%     <-- the 15h outage
2026-09-01    8 / 48   17%
worst gap 27.8h
```

A tracked message ID is a **perishable asset with a hard 48h expiry**, so
an outage over 12h strands messages permanently. Uptime is a correctness
requirement here, and it is currently outsourced to something that does
not provide it.

## It reads 200 bytes, not 300 KiB

⭐⭐ The first version asked the Actions API for the run list: **306,759
bytes** per check. It now fetches the committed heartbeat instead:

```
GitHub Actions run list   306,759 bytes   1415 ms
raw ci_heartbeat.json         200 bytes    452 ms
```

**1,500x less, and a better signal.** The heartbeat is only written by a
run that actually did the work *and* pushed, so a `skipped` run cannot
produce one. The old version needed an explicit "skipped does not count"
rule; this one gets that property for free, because a skipped run leaves
no trace to misread.

⚠️ The fetch is **unauthenticated** (the repo is public), so the token is
needed only for the dispatch itself. `raw.githubusercontent.com` is
CDN-cached for a few minutes, which is irrelevant against a 45 minute
threshold.

## Cost on the VPS, measured not estimated

```
python start + imports   ~294 ms
heartbeat fetch          ~452 ms, 200 bytes
peak heap                ~1.5 MiB
```

At one check every 15 minutes: **~0.8s CPU per hour** (0.02% of one
core), **~19 KB/day** of traffic, and nothing resident between runs.

## Setting it up

```bash
# A PAT with `workflow` scope (classic) or actions:write (fine-grained).
# ⛔ NEVER commit it. 600 perms, outside the repo.
install -m 600 /dev/null ~/.pathwars-dispatch-token
echo 'ghp_xxx' > ~/.pathwars-dispatch-token

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
from pathlib import Path

REPO = os.environ.get("PATHWARS_REPO", "LewisIsWorking/telegram-pbp-reminder")
WORKFLOW = "pbp-reminder.yml"
HEARTBEAT_URL = (f"https://raw.githubusercontent.com/{REPO}/main/"
                 f"data/ci_heartbeat.json")

# The bot asks for a run every 30 minutes. 45 gives one missed slot of
# grace before an outsider steps in, so normal jitter costs nothing.
QUIET_AFTER = timedelta(minutes=45)

# ⛔ Never dispatch more often than this, whatever the heartbeat says.
# If the bot is running but its PUSH is broken, the heartbeat never
# refreshes and nothing this script does will fix it. Without a floor it
# would fire every single tick, multiplying a broken run forever.
DISPATCH_COOLDOWN = timedelta(minutes=30)

MARKER = Path(os.environ.get("PATHWARS_MARKER",
                             Path.home() / ".pathwars-last-dispatch"))


def parse_written_at(payload: bytes) -> datetime | None:
    """The heartbeat's timestamp, or None if it cannot be read."""
    try:
        written = json.loads(payload)["written_at"]
        stamp = datetime.fromisoformat(written)
    except (ValueError, KeyError, TypeError):
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def should_dispatch(heartbeat_age, since_last_dispatch) -> bool:
    """Decide, from two ages. Both may be None meaning "unknown".

    ⚠️ An unreadable heartbeat dispatches. That is the opposite of the
    posting gate's rule, deliberately and for a stated reason: there, a
    wrong guess sends a message that can never be deleted; here, a wrong
    guess costs one cheap run. The cooldown below stops it looping.
    """
    if since_last_dispatch is not None and since_last_dispatch < DISPATCH_COOLDOWN:
        return False
    return heartbeat_age is None or heartbeat_age > QUIET_AFTER


def _fetch(url: str, token: str = "", data: dict | None = None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=json.dumps(data).encode() if data else None,
        method="POST" if data else "GET", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _marker_age(now: datetime):
    try:
        stamp = datetime.fromtimestamp(MARKER.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return now - stamp


def main() -> int:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        written = parse_written_at(_fetch(HEARTBEAT_URL))
    except (urllib.error.URLError, OSError):
        written = None
    age = None if written is None else now - written
    shown = "unreadable" if age is None else f"{age.total_seconds() / 60:.0f}m ago"

    if not should_dispatch(age, _marker_age(now)):
        print(f"{stamp} bot state last pushed {shown}; nothing to do")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print(f"{stamp} state {shown} and no GITHUB_TOKEN; cannot dispatch")
        return 1
    try:
        _fetch(f"https://api.github.com/repos/{REPO}/actions/workflows/"
               f"{WORKFLOW}/dispatches", token, {"ref": "main"})
    except urllib.error.HTTPError as error:
        hint = (" (the token needs the 'workflow' scope, or actions:write)"
                if error.code in (401, 403) else "")
        print(f"{stamp} DISPATCH FAILED HTTP {error.code}{hint}")
        return 1
    except (urllib.error.URLError, OSError) as error:
        print(f"{stamp} DISPATCH FAILED: {error}")
        return 1

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.touch()
    print(f"{stamp} state {shown}; dispatched a run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
