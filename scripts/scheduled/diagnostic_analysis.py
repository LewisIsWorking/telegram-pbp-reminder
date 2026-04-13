"""
Log analysis helpers for the daily diagnostic check.
Extracted from diagnostic.py to keep both files under 200 lines.
"""

import re
from datetime import datetime

# Error patterns — lines matching these are bucketed as issues
_ERROR_PATTERNS = [
    (re.compile(r"rate limit|429",      re.I), "Warning: Rate limited"),
    (re.compile(r"FATAL|SystemExit",    re.I), "Fatal error"),
    (re.compile(r"Error processing update"),   "Update error"),
    (re.compile(r"Telegram.*failed",    re.I), "Send failed"),
    (re.compile(r"network error",       re.I), "Network error"),
    (re.compile(r"State backup failed", re.I), "Backup failed"),
    (re.compile(r"REFUSING to save",    re.I), "Save refused"),
    (re.compile(r"Warning:.*state",     re.I), "State warning"),
    (re.compile(r"could not load gist", re.I), "Gist load failed"),
]

# Info patterns — lines matching these are surfaced as activity events
_INFO_PATTERNS = [
    re.compile(r"Poll vote"),
    re.compile(r"Session poll (posted|ping)"),
    re.compile(r"POTW for"),
    re.compile(r"Queue reminder: \d+ unreplied"),
    re.compile(r"Unknown voter captured"),
]

def _analyse_logs(logs: list[str]) -> dict:
    """Scan all log lines and bucket them into issues and events."""
    issues: dict[str, list[str]] = {}
    events: list[str] = []
    runs_with_errors = 0

    for log in logs:
        run_had_error = False
        for line in log.splitlines():
            clean = re.sub(r"^\d{4}-\d{2}-\d{2}T[\d:.Z]+ ", "", line).strip()
            if not clean:
                continue  # pragma: no cover
            # Skip GitHub Actions infrastructure lines (on cleaned text)
            _GH_PREFIXES = ("[command]", "##[", "Run ", "  with:",
                            "Worker ID:", "Current runner version",
                            "FORCE_JAVASCRIPT", "pythonLocation",
                            "shell:", "env:", "Temporarily overriding",
                            "PKG_CONFIG", "Python_ROOT", "LD_LIBRARY")
            if clean.startswith(_GH_PREFIXES):
                continue  # pragma: no cover
            # Skip filesystem path lines (git credential files, runner paths)
            if clean.startswith(("/home/runner", "/github/", "/opt/hosted")):
                continue  # pragma: no cover
            if "git-credentials-" in clean:
                continue  # pragma: no cover

            for pattern, label in _ERROR_PATTERNS:
                if pattern.search(clean):
                    issues.setdefault(label, []).append(clean[:200])
                    run_had_error = True
                    break

            for pattern in _INFO_PATTERNS:
                m = pattern.search(clean)
                if m:
                    events.append(clean[:100])
                    break

        if run_had_error:
            runs_with_errors += 1

    return {
        "issues": issues,
        "events": events,
        "runs_with_errors": runs_with_errors,
    }


def _build_report(analysis: dict, run_count: int, now: datetime) -> str:
    issues   = analysis["issues"]
    events   = analysis["events"]
    n_errors = analysis["runs_with_errors"]

    status = "✅ All clear" if not issues else f"⚠️ {len(issues)} issue type(s) found"
    lines = [
        f"━━━━━━━━━━━━━━━━",
        f"🔍 Daily Diagnostic — {now.strftime('%Y-%m-%d')}",
        f"{status} across {run_count} hourly runs",
        "",
    ]

    if issues:
        lines.append("Issues:")
        for label, occurrences in sorted(issues.items()):
            lines.append(f"  {label} ×{len(occurrences)}")
            # Show first unique example
            seen = set()
            for occ in occurrences:
                if occ not in seen:
                    lines.append(f"    └ {occ[:200]}")
                    seen.add(occ)
                    if len(seen) >= 10:
                        break  # pragma: no cover

    if events:
        # Summarise notable events
        vote_lines = [e for e in events if "Poll vote" in e]
        potw_lines = [e for e in events if "POTW" in e]
        unknown_lines = [e for e in events if "Unknown voter" in e]
        queue_lines = [e for e in events if "Queue reminder" in e]

        lines.append("")
        lines.append("Activity:")
        if vote_lines:
            lines.append(f"  🗳️ {len(vote_lines)} poll vote(s) recorded")
        if potw_lines:
            lines.append(f"  🏆 {len(potw_lines)} POTW award(s)")
        if unknown_lines:
            lines.append(f"  👤 {len(unknown_lines)} unknown voter ID(s) captured")
        if queue_lines:
            # Extract max unreplied count
            counts = [int(m.group(1)) for q in queue_lines
                      if (m := re.search(r"(\d+) unreplied", q))]
            if counts:
                lines.append(f"  📋 Queue: {max(counts)} unreplied at peak")

    return "\n".join(lines)

