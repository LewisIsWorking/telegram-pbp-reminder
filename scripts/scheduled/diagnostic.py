"""
Daily bot health diagnostic.

Fetches the last 25 GitHub Actions run logs, analyses them for errors,
warnings, anomalies and patterns, then posts a summary to the bot topic.
Runs once per day at a configurable hour.
"""

import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg

_GITHUB_API = "https://api.github.com"
_REPO       = "LewisIsWorking/telegram-pbp-reminder"
_WORKFLOW   = "233336939"  # PBP Inactivity Reminder

# Patterns that indicate problems

def _gh_request(path: str) -> dict | None:
    token = os.environ.get("GIST_TOKEN", "")
    req = urllib.request.Request(
        f"{_GITHUB_API}{path}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        print(f"GitHub API error: {e}")
        return None


def _fetch_run_log(run_id: int) -> str:
    """Download and return checker stdout from a workflow run."""
    import zipfile, io
    token = os.environ.get("GIST_TOKEN", "")
    url = f"{_GITHUB_API}/repos/{_REPO}/actions/runs/{run_id}/logs"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        # Follow redirect — GitHub returns a zip download URL
        z = zipfile.ZipFile(io.BytesIO(resp.read()))
        for name in z.namelist():
            if "check-inactivity" in name:
                return z.read(name).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Log fetch error for run {run_id}: {e}")
    return ""


from scheduled.diagnostic_analysis import _analyse_logs, _build_report, _ERROR_PATTERNS, _INFO_PATTERNS
from scheduled.schedule_delivery import report_line

# Run-list page size. Must stay above SCHEDULED_RUNS_PER_DAY or the
# delivery count silently truncates; test_schedule_delivery.py fails if it
# stops being. Separate from the log cap below: listing runs is one cheap
# request, downloading each run's log zip is not.
_RUNS_PAGE = 100
_LOG_CAP = 24

def run_daily_diagnostic(config: dict, state: dict, *,
                         now: datetime | None = None, **_kw) -> None:
    """Fetch recent run logs, analyse, post health report to bot topic."""
    now = now or datetime.now(timezone.utc)
    if now.hour != config.get("diagnostic_hour", 8):
        return

    today = now.date().isoformat()
    if state.get("last_diagnostic") == today:
        return

    bot_topic = config.get("bot_topic_id")
    group_id  = config["group_id"]
    if not bot_topic:
        return

    # ⛔ per_page was 25 until 2026-08-31, while a healthy day is 48
    # scheduled runs. The instrument's maximum reading was half the
    # healthy value, so it could only ever report a degraded number, and
    # the report printed that number with no denominator. Four days of
    # GitHub delivering 4 to 12 runs a day looked exactly like four days
    # of it delivering 48. See scheduled/schedule_delivery.py.
    data = _gh_request(
        f"/repos/{_REPO}/actions/workflows/{_WORKFLOW}/runs?per_page={_RUNS_PAGE}"
    )
    if not data:
        return

    all_runs = data.get("workflow_runs", [])
    cutoff = now - timedelta(hours=25)
    recent_runs = [
        r for r in all_runs
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > cutoff
    ]

    # Built before the early return below. A window with no runs is when
    # this line most needs to go out, and returning silently would let the
    # scheduler's own outage suppress the report about the scheduler.
    scheduler = report_line(all_runs, now, page_size=_RUNS_PAGE)

    if not recent_runs:
        if tg.send_message(group_id, bot_topic, scheduler):
            state["last_diagnostic"] = today
        return

    # Download and analyse logs. Capped well below the run count to stay
    # inside the job timeout; _build_report states the cap rather than
    # presenting a sample as the whole picture.
    logs = []
    for run in recent_runs[:_LOG_CAP]:
        log = _fetch_run_log(run["id"])
        if log:
            logs.append(log)

    analysis = _analyse_logs(logs)
    report = _build_report(analysis, len(recent_runs), now,
                           scheduler_line=scheduler, logs_read=len(logs))

    if tg.send_message(group_id, bot_topic, report):
        state["last_diagnostic"] = today
        print(f"Daily diagnostic posted ({len(recent_runs)} runs analysed)")
