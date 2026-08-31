"""How often did GitHub actually run us? Answered from git, not the API.

    py -3 tools/schedule_delivery_report.py [--days 14]

Every successful run commits ``data/ci_heartbeat.json``, so the git log of
that one file IS the record of runs that happened. That makes this a
second, independent measurement of the same thing the daily diagnostic
reports from the Actions API.

⭐ Independence is the point, not redundancy. The Actions API has already
been caught serving a **cached page of runs from three days earlier**
(2026-08-19, see ``scripts/preflight/prior_runs.py``), and that stale
reading nearly unlocked the posting gate. Git history cannot be served
stale: it is the repository's own content. When the two agree, as they
did on 2026-08-31 (173 API vs 385 heartbeat commits over their respective
windows, matching day for day), the reading can be trusted.

⚠️ Counts runs that COMMITTED, which includes push and pull_request runs,
so it reads slightly above the scheduled-only figure. It answers "is the
bot running", not "is the cron firing". For the cron specifically, use the
scheduler line in the daily diagnostic.
"""

import argparse
import collections
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HEARTBEAT = "data/ci_heartbeat.json"
# Two hourly crons. Kept in step with scripts/scheduled/schedule_delivery.py
# by test_schedule_delivery.py, which reads the workflow itself.
EXPECTED_PER_DAY = 48
HEALTHY = 0.90


def resolve_ref(preferred: str = "origin/main") -> str:
    """The ref to measure, preferring the remote.

    ⛔ Defaults to origin/main, not HEAD. The state commits land on the
    remote and a local checkout is behind it the moment anything runs.
    The first version of this tool read HEAD and reported the window
    ending 2026-08-30 13:07 while the remote had commits up to 08-31
    05:54, which reads as "the bot stopped yesterday". A stale branch
    looks exactly like a broken pipeline.
    """
    ok = subprocess.run(["git", "rev-parse", "--verify", "--quiet", preferred],
                        capture_output=True, text=True).returncode == 0
    return preferred if ok else "HEAD"


def run_times(days: int, ref: str) -> list:
    """Commit timestamps for the heartbeat on ``ref``, newest last."""
    out = subprocess.run(
        ["git", "log", ref, f"--since={days} days ago", "--format=%aI",
         "--", HEARTBEAT],
        capture_output=True, text=True, check=True).stdout
    stamps = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            stamps.append(datetime.fromisoformat(line))
    return sorted(stamps)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--ref", default=None,
                        help="git ref to measure (default: origin/main)")
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip the git fetch; the reading may be stale")
    args = parser.parse_args()

    ref = args.ref or resolve_ref()
    if not args.no_fetch and ref.startswith("origin/"):
        subprocess.run(["git", "fetch", "--quiet", "origin"], check=False)

    times = run_times(args.days, ref)
    if not times:
        print(f"No heartbeat commits on {ref} in the last {args.days} days. "
              f"That means the bot has not run at all.")
        return 1

    # ⚠️ The ref is printed because it changes the answer. See resolve_ref.
    print(f"ref: {ref}   window: {times[0]:%Y-%m-%d %H:%M} .. "
          f"{times[-1]:%Y-%m-%d %H:%M} UTC   expected {EXPECTED_PER_DAY}/day")
    print()
    per_day = collections.Counter(t.astimezone(timezone.utc).date()
                                  for t in times)
    # The first and last days are partial, so their ratio is not comparable.
    # Marked rather than dropped: a silently trimmed window is how a report
    # ends up disagreeing with the raw data for no stated reason.
    edges = {times[0].date(), times[-1].date()}
    for day in sorted(per_day):
        n = per_day[day]
        ratio = n / EXPECTED_PER_DAY
        mark = "  (partial day)" if day in edges else (
            "" if ratio >= HEALTHY else "   <-- degraded")
        print(f"  {day}  {n:3d} / {EXPECTED_PER_DAY}  {ratio:4.0%}{mark}")

    gaps = [(times[i + 1] - times[i]).total_seconds() / 3600
            for i in range(len(times) - 1)]
    over = [g for g in gaps if g > 3.0]
    print()
    print(f"gaps over the preflight 3h heartbeat limit: {len(over)} of "
          f"{len(gaps)}   worst {max(gaps, default=0):.1f}h")
    if over:
        print("  Each one pauses posting on the next run that does fire. "
              "The state-commit step is not the fault; see "
              "scripts/scheduled/schedule_delivery.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
