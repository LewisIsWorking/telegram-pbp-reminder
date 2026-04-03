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

    # Fetch last 25 runs
    data = _gh_request(
        f"/repos/{_REPO}/actions/workflows/{_WORKFLOW}/runs?per_page=25"
    )
    if not data:
        return

    cutoff = now - timedelta(hours=25)
    recent_runs = [
        r for r in data.get("workflow_runs", [])
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > cutoff
    ]

    if not recent_runs:
        return

    # Download and analyse logs
    logs = []
    for run in recent_runs[:24]:  # cap to avoid timeout
        log = _fetch_run_log(run["id"])
        if log:
            logs.append(log)

    analysis = _analyse_logs(logs)
    report = _build_report(analysis, len(recent_runs), now)

    if tg.send_message(group_id, bot_topic, report):
        state["last_diagnostic"] = today
        print(f"Daily diagnostic posted ({len(recent_runs)} runs analysed)")
