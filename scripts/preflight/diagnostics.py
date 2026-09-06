"""Everything a human needs to diagnose a stopped bot, in one message.

Added 2026-09-04 at Lewis's request: *"You should add more debugging to
the bot stopped posting messages to aid you in debugging."*

The alert that went to the bot topic said one thing - how old the last
state push was - and that single number was ambiguous enough to send him
to the wrong place three times in a day. Every one of those pauses was
GitHub not delivering the cron, and the alert's advice named a
state-commit step that had never failed.

⭐ **The report answers the questions in the order they get asked**, and
each section exists because a real session needed it and had to go and
fetch it by hand:

  1. what did the gate decide, and on which reasons
  2. **which of the two causes is it** - the answer, plus the evidence
  3. the heartbeat: when, and which run wrote it
  4. this run, with a link
  5. the recent runs and the GAPS between them, which is the shape that
     makes non-delivery obvious at a glance
  6. delivery rate over 24h, because "27% of 48" is the real problem
  7. what the staleness is about to COST: queue posts nearing the 48h
     delete wall

⚠️ Verbosity is only safe because it goes to a debug topic. The bot-topic
alert stays short and rationed: every message there is unrecorded and
becomes an undeletable orphan after 48h. The debug topic is a log, meant
to accumulate, and Lewis said to put as much in it as we want.

⚠️ Telegram caps a message at 4096 characters and REJECTS anything longer
rather than truncating, so a report that grew past the cap would send
nothing at all. It is trimmed here, with the cut made visible.
"""

from datetime import datetime, timedelta, timezone

from preflight.delivery_gap import (finished_since, history_is_fresh,
                                    is_delivery_gap, _moment)
from preflight.orphan_risk import scan, summarise
from preflight.stale_features import summarise_from_disk

# Telegram's limit is 4096. The margin absorbs the header the caller adds.
MAX_MESSAGE = 3800
EXPECTED_RUNS_PER_DAY = 48


def _runs_in(runs: list, now: datetime, window: timedelta,
             event: str | None = None) -> list:
    cutoff = now - window
    out = []
    for run in runs or []:
        started = _moment(run.get("created_at") or run.get("createdAt"))
        if started is None or started < cutoff:
            continue
        if event and run.get("event") != event:
            continue
        out.append(run)
    return out


def delivery_line(runs: list, now: datetime) -> str:
    """Scheduled runs actually delivered in 24h against what was asked.

    ⭐ The number that matters and that nothing was reporting. The bot
    asks for 48 a day; through 2026-09 it has been getting roughly a
    quarter of them, and every pause traces back to that.
    """
    if runs is None:
        return "Delivery (24h): UNKNOWN - run history unavailable"
    got = len(_runs_in(runs, now, timedelta(hours=24), event="schedule"))
    # ⚠️ The history is capped at RUNS_TO_INSPECT, so a healthy day can
    # fill the page and undercount. Say so rather than report a low
    # number as if it were measured.
    capped = " (history page full; may undercount)" if len(runs) >= 40 else ""
    pct = 100.0 * got / EXPECTED_RUNS_PER_DAY
    return (f"Delivery (24h): {got}/{EXPECTED_RUNS_PER_DAY} scheduled runs "
            f"= {pct:.0f}%{capped}")


def cause_block(runs: list, heartbeat: dict | None, run_id: str | None,
                age_hours: float | None) -> str:
    """Which of the two causes, and the evidence for saying so.

    Never asserts a cause it cannot support. When the freshness proof
    fails it says the question is unanswerable and why, because "cannot
    tell" sent to a human is worth more than a confident guess.
    """
    fresh = history_is_fresh(runs, run_id)
    written = _moment((heartbeat or {}).get("written_at"))
    lines = ["CAUSE"]
    if not fresh:
        lines.append("  UNDETERMINED: the run history does not contain this "
                     "run, so it cannot be trusted as fresh.")
        lines.append(f"  (history={'none' if runs is None else len(runs)} runs, "
                     f"this run id={run_id or 'unset'})")
        return "\n".join(lines)
    if written is None:
        lines.append("  UNDETERMINED: no readable heartbeat timestamp.")
        return "\n".join(lines)
    since = finished_since(runs, written, exclude_run_id=run_id)
    if is_delivery_gap(runs, heartbeat, run_id):
        lines.append("  GITHUB DID NOT RUN US. Zero runs have finished since "
                     "the last state push, so nothing has tried and failed.")
        lines.append("  The state machinery is untouched. Posting is safe.")
    else:
        lines.append(f"  A PUSH LIKELY FAILED. {len(since)} run(s) finished "
                     f"since the last state push and it did not move.")
        outcomes = ", ".join(str(r.get("conclusion")) for r in since[:6])
        lines.append(f"  Those runs concluded: {outcomes}")
        lines.append("  Check the state-commit step of the latest run.")
    return "\n".join(lines)


def runs_block(runs: list, now: datetime, limit: int = 8) -> str:
    """Recent runs with the gap before each. The gaps are the signal."""
    if not runs:
        return "RECENT RUNS\n  none available"
    lines = ["RECENT RUNS (newest first; gap = time since the run below it)"]
    stamped = [(r, _moment(r.get("created_at") or r.get("createdAt")))
               for r in runs]
    stamped = [(r, t) for r, t in stamped if t is not None][:limit + 1]
    for index, (run, when) in enumerate(stamped[:limit]):
        nxt = stamped[index + 1][1] if index + 1 < len(stamped) else None
        gap = "" if nxt is None else f"  +{(when - nxt).total_seconds() / 3600:.2f}h"
        lines.append(f"  {when:%m-%d %H:%M} {str(run.get('event'))[:16]:16} "
                     f"{str(run.get('conclusion'))}{gap}")
    return "\n".join(lines)


def build(reasons: list, age_hours: float | None, heartbeat: dict | None,
          runs: list | None, run_id: str | None, repo: str,
          now: datetime | None = None, note: str = "",
          extra: str = "") -> str:
    """The whole report. Never raises; a broken section must not cost the
    other six, because this is what gets read when nothing else works."""
    now = now or datetime.now(timezone.utc)
    verdict = ("PAUSED - " + "; ".join(reasons)) if reasons else \
        "POSTING ALLOWED"
    parts = [
        f"\U0001f9ea Bot diagnostic - {now:%Y-%m-%d %H:%M:%S} UTC",
        f"VERDICT: {verdict}",
    ]
    if note:
        parts.append(f"NOT HALTING because {note}.")
    if extra:
        parts.append(extra)
    written = (heartbeat or {}).get("written_at", "none")
    parts.append(
        "HEARTBEAT\n"
        f"  written_at: {written}\n"
        f"  age: {'unknown' if age_hours is None else f'{age_hours:.2f}h'}"
        f"  (limit 3.0h)\n"
        f"  written by run: {(heartbeat or {}).get('last_run_id', 'unknown')}"
        f" attempt {(heartbeat or {}).get('last_run_attempt', '?')}")
    parts.append(f"THIS RUN\n  id {run_id or 'unset'}\n"
                 f"  https://github.com/{repo}/actions/runs/{run_id or ''}")
    for section in (lambda: cause_block(runs, heartbeat, run_id, age_hours),
                    lambda: runs_block(runs, now),
                    lambda: delivery_line(runs, now),
                    lambda: summarise(scan(now)),
                    # ⛔ The section that would have caught two
                    # features being dead for ten days while every
                    # other line of this report said healthy.
                    lambda: summarise_from_disk(now)):
        try:
            parts.append(section())
        except Exception as error:  # noqa: BLE001 - one bad section, not six
            parts.append(f"(section failed: {error})")
    report = "\n\n".join(parts)
    if len(report) > MAX_MESSAGE:
        report = report[:MAX_MESSAGE] + "\n\n[...trimmed to fit Telegram]"
    return report
