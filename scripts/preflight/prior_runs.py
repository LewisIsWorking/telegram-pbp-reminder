"""Decide, from the workflow's own run history, whether posting is safe.

Added 2026-08-19 after the bot posted the same "Unreplied: 1" notice four
times in under two hours.

The mechanism was not in the posting code at all. ``main`` gained branch
protection on 2026-08-18, the state-commit step started failing with
``GH006``, and every run afterwards reloaded the same frozen state, saw an
empty ``msg_ids``, and posted again. 25 consecutive runs failed and nothing
said so; the state files had not moved since 2026-08-18T15:01.

⭐ Why halting is the right response, and not merely the cautious one:
**the two failure directions do not cost the same.**

  not posting   The next hourly run posts it. Recoverable, and cheaply.

  posting       The message id is only recorded in state. If state cannot
                be committed the id is lost, so nothing will ever delete
                the message. Past 48h Telegram will not let the bot delete
                it even by hand. Every duplicate is a permanent orphan.
                There are already 41 of those.

So when the bot cannot show that it remembers what it sends, it must not
send. This module is the "can it remember" question, kept free of I/O so
the answer can be tested against every streak length rather than mocked.

⚠️ **The gate must never fail the job it guards.** A gate that fails its
own run keeps the failure streak alive, which keeps the gate closed, which
fails the run. The bot could never recover once tripped, not even after
the underlying fault was fixed. ``gate.py`` therefore skips only the
posting steps and lets the commit-and-push step run, so a run that pushes
successfully turns green on its own and reopens the gate an hour later.

⭐ **Two signals, combined as a union** (see ``halt_reasons``). Either may
add a reason to stay quiet; neither can clear the other's. That shape was
forced by a real miss hours after the first version shipped: the Actions
API served a cached page of runs from three days earlier, the gate read it
as "0 failed runs", and posting proceeded on a run whose real streak was
27. A source that can only ever make the gate MORE cautious does not need
to be reliable.

COVERS:   state frozen for any reason: branch protection, a rebase
          conflict, an expired token, the runner dying mid-push, and now
          also a stale or unavailable Actions API.
MISSES:   a run that goes green while state silently did not move. The
          heartbeat written by ``scripts/preflight/heartbeat.py`` closes
          that hole by guaranteeing every run has something to push, so a
          green run is real evidence the push landed.
ANCHORED: to the committed heartbeat, which is repository content and
          cannot be served from a cache, corroborated by the workflow's
          own conclusions. Not to a hand-kept list of "things that break".
PROVEN:   ``test_preflight_prior_runs.py`` feeds it the real 2026-08-18
          streak and requires a halt, feeds it a recovery and requires
          reopening, and feeds it the cached-API reading that fooled it on
          2026-08-19 and requires it to halt anyway.
"""

# Two consecutive is the trigger, not one. Single failures happen for
# reasons that do not touch state at all - a runner blip, a rebase race
# that the next run wins. Two in a row is systemic, and by then the bot
# has posted at most one unrecorded message rather than none.
HALT_AFTER_CONSECUTIVE_FAILURES = 2

# When to alert, measured in whole hours broken. Deliberately computed
# from the observations themselves rather than from a "have I already
# alerted" marker, because the marker would live in the very state that is
# not persisting. A stateless rule is the only kind that works while state
# is frozen.
FIRST_ALERT_HOURS = (0, 3)
REPEAT_ALERT_EVERY_HOURS = 24

# Roughly two runs an hour: the hourly full pass plus the :30 queue pass.
# Only used to turn a streak into hours when the heartbeat cannot be read.
RUNS_PER_HOUR = 2

# The bot runs hourly, plus a queue-only pass on the half hour, so a
# healthy heartbeat is under an hour old. 3h leaves room for a delayed
# GitHub scheduler without letting a real outage sit unnoticed for long.
MAX_HEARTBEAT_AGE_HOURS = 3.0

SUCCESS = "success"


def should_halt_for_stale_heartbeat(age_hours: float | None) -> bool:
    """True when no state push has landed recently enough.

    Added 2026-08-19, hours after the streak check shipped, because the
    Actions API served a **cached page of runs from three days earlier**.
    The gate read it as "0 failed runs", opened, and let posting proceed on
    a run where the streak was really 27. Re-querying minutes later
    returned the correct data, so it was transient rather than a bad query.
    An unreliable source is fine; an unreliable source that can UNLOCK the
    gate is not.

    ``None`` means the heartbeat could not be read at all, which is not
    evidence of staleness. It does not halt on its own.
    """
    return age_hours is not None and age_hours > MAX_HEARTBEAT_AGE_HOURS


def consecutive_failures(conclusions: list) -> int:
    """How many of the most recent finished runs failed, newest first.

    ``conclusions`` is the workflow's own run conclusions in GitHub's
    order (newest first). Entries of ``None`` are runs still in progress -
    typically the run asking the question - and are skipped rather than
    counted, since a run that has not finished is not evidence either way.

    ⚠️ Only ``success`` breaks the streak. ``cancelled``, ``timed_out``
    and ``startup_failure`` all count as failures here, because the
    question is not "did something go wrong" but "did this run's state
    reach the remote" - and for every one of those, it did not.
    """
    streak = 0
    for conclusion in conclusions:
        if conclusion is None:
            continue
        if conclusion == SUCCESS:
            break
        streak += 1
    return streak


def should_halt_posting(streak: int) -> bool:
    """True when state is not persisting and the bot must stay quiet."""
    return streak >= HALT_AFTER_CONSECUTIVE_FAILURES


def broken_hours(streak: int, age_hours: float | None) -> int:
    """Whole hours this has been broken, from whichever signal can say.

    Prefers the heartbeat, which measures the outage directly. Falls back
    to converting the run streak, which is a proxy and is only needed
    before the first heartbeat exists.
    """
    if age_hours is not None:
        return max(0, int(age_hours - MAX_HEARTBEAT_AGE_HOURS))
    return streak // RUNS_PER_HOUR


def should_alert(hours: int) -> bool:
    """True on the elapsed times worth interrupting a human for.

    Alerts at onset, again at 3h (nobody has looked), then once a day.
    Alerting every run would replace one kind of spam with another, and
    the operator would learn to ignore exactly the channel that is trying
    to tell them the bot is down.
    """
    if hours in FIRST_ALERT_HOURS:
        return True
    return (hours > max(FIRST_ALERT_HOURS)
            and hours % REPEAT_ALERT_EVERY_HOURS == 0)


def halt_reasons(streak: int, age_hours: float | None) -> list:
    """Every reason to stay quiet. Empty means it is safe to post.

    ⭐ **A union, never an intersection.** Each signal may only ADD a
    reason; neither can clear the other's. That is the whole correction of
    2026-08-19: previously the run history could report "healthy" and
    thereby open the gate, so one cached API response disarmed it. Now a
    bad reading from either source can make the gate more cautious and can
    never make it less.

    Which means the signals do not need to be equally trustworthy, and
    that is the point. The heartbeat is local, committed evidence and
    cannot be served stale. The API is convenient corroboration that
    catches failures the heartbeat cannot yet see, such as the very first
    broken run. Combining them this way takes the strength of each without
    inheriting the weakness of either.
    """
    reasons = []
    if should_halt_for_stale_heartbeat(age_hours):
        reasons.append(
            f"the last state push landed {age_hours:.1f}h ago, over the "
            f"{MAX_HEARTBEAT_AGE_HOURS:g}h limit")
    if should_halt_posting(streak):
        reasons.append(f"{streak} consecutive workflow runs failed")
    return reasons


def explain(reasons: list, age_hours: float | None = None) -> str:
    """One line naming the fault and what it stops, for logs and alerts.

    Takes the reasons rather than the streak, so the message can never
    disagree with the decision: they are computed from the same list.
    Reporting a cause the gate did not act on, or acting on one it did not
    report, is how an operator ends up debugging the wrong thing.
    """
    if not reasons:
        seen = "unknown age" if age_hours is None else f"{age_hours:.1f}h ago"
        return f"State persistence looks healthy (last push {seen})."
    return (
        f"Posting is paused because {', and '.join(reasons)}. Any message "
        f"sent now would have its id lost, and would become permanently "
        f"undeletable after 48h. Check the state-commit step of the latest run."
    )
