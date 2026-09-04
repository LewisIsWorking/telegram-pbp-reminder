"""Tell "GitHub never ran us" apart from "our state push failed".

Added 2026-09-04. ``prior_runs`` closes with a comment admitting the hole
this fills::

    ⛔ A stale heartbeat has TWO causes and this module cannot tell them
    apart. Our push failed, or GitHub never ran us.

It could not tell them apart because it only ever asked the Actions API
for *conclusions* and threw the timestamps away. With the timestamps the
question is answerable, and the answer matters: on 2026-09-04 the bot
paused and alerted Lewis three times - at 3.2h, 3.1h and 3.3h - while
**every one of the last 40 runs had concluded ``success``**. Not one push
had failed. All three pauses were GitHub skipping two hours of a cron it
delivers about 27% of. The alert sent him to a state-commit step that has
never once gone red.

⭐ **The discriminator.** The heartbeat only advances inside a successful
push, so its timestamp H is the moment of the last one. Then:

  a run finished after H, and H did not move   -> the push is broken
  no run finished after H at all               -> nothing has yet tried

In the second case there is no failure to be cautious about. The gap is
the scheduler's, the state machinery is untouched, and the next run may
post safely.

⛔⛔ **Why this cannot re-open the 2026-08-19 hole.** That day the Actions
API served a **cached page of runs from three days earlier**; the gate
read "0 failed runs" and posted on a run whose real streak was 27. A
cached page looks *exactly* like a delivery gap to the rule above - old
runs, none after H - so the rule on its own would have made that incident
worse rather than better.

So the suppression is refused unless the history proves itself fresh, and
it proves it the only way that cannot be faked: **the currently executing
run must appear in it.** No cached response can contain a run that had
not started when it was cached. Absent that proof this module declines to
say anything and the gate halts exactly as it did before.

⚠️ Everything here fails CLOSED. Every unknown - no history, no run id,
no heartbeat, an unparseable timestamp - returns "not a delivery gap" and
leaves the halt standing. Suppression happens only on positive evidence.

⚠️ It suppresses the *stale heartbeat* reason ONLY. A failed-run streak
is untouched, because that is direct evidence a push lost.
"""

from datetime import datetime, timezone

# ⚠️ Pinned to the wording built by ``prior_runs.halt_reasons``.
# ``test_preflight_delivery_gap`` feeds a real ``halt_reasons`` output
# through this marker, so a reword breaks a test loudly rather than
# silently disarming the suppression on a string that no longer matches.
STALE_HEARTBEAT_MARKER = "state push landed"


def _moment(value) -> datetime | None:
    """Parse a GitHub timestamp. Unparseable is None, never "now"."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _run_id(run: dict) -> str:
    """The run's id under either the REST (``id``) or gh CLI name."""
    return str(run.get("id") or run.get("databaseId") or "")


def history_is_fresh(runs: list | None, current_run_id: str | None) -> bool:
    """True only when the fetched history provably includes THIS run.

    The one freshness proof a cache cannot forge, and the whole reason
    the 2026-08-19 cached-page incident cannot recur through this path.
    """
    if not runs or not current_run_id:
        return False
    return any(_run_id(run) == str(current_run_id) for run in runs)


def finished_since(runs: list, moment: datetime,
                   exclude_run_id: str | None = None) -> list:
    """Finished runs that STARTED after ``moment``.

    "Started after" rather than "finished after" deliberately: the run
    that wrote heartbeat H started before H and finished after it, so
    finish time would always match it and the count could never be zero.

    In-progress runs (``conclusion`` still None) are excluded. A run that
    has not finished has not attempted its push, so it is not yet
    evidence of anything - the same reasoning ``consecutive_failures``
    applies when it skips them.
    """
    out = []
    for run in runs:
        if run.get("conclusion") is None:
            continue
        if exclude_run_id and _run_id(run) == str(exclude_run_id):
            continue
        started = _moment(run.get("created_at") or run.get("createdAt"))
        if started is not None and started > moment:
            out.append(run)
    return out


def is_delivery_gap(runs: list | None, heartbeat: dict | None,
                    current_run_id: str | None) -> bool:
    """True when a stale heartbeat is GitHub's silence, not a lost push.

    Requires, in order and all of them: a fresh history, a readable
    heartbeat timestamp, and no finished run since it.
    """
    if not history_is_fresh(runs, current_run_id):
        return False
    written = _moment((heartbeat or {}).get("written_at"))
    if written is None:
        return False
    return not finished_since(runs, written, exclude_run_id=current_run_id)


def drop_stale_heartbeat_reason(reasons: list, runs: list | None,
                                heartbeat: dict | None,
                                current_run_id: str | None) -> tuple:
    """``(reasons, note)`` with the stale-heartbeat reason removed if earned.

    Returns the list unchanged and an empty note whenever the evidence is
    not there, so the caller needs no special case for "could not tell".
    """
    if not reasons or not is_delivery_gap(runs, heartbeat, current_run_id):
        return reasons, ""
    kept = [r for r in reasons if STALE_HEARTBEAT_MARKER not in r]
    if len(kept) == len(reasons):
        return reasons, ""
    return kept, ("the stale heartbeat is GitHub not delivering the "
                  "schedule, not a failed push: no run has finished since "
                  "the last one landed, so nothing has tried and lost")
