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

COVERS:   state frozen for any reason the run notices: branch protection,
          a rebase conflict, an expired token, the runner dying mid-push.
MISSES:   a run that goes green while state silently did not move. The
          heartbeat written by ``scripts/preflight/heartbeat.py`` closes
          that hole by guaranteeing every run has something to push, so a
          green run is real evidence the push landed.
ANCHORED: to the workflow's own conclusions via the Actions API, not to a
          hand-kept list of "things that can break".
PROVEN:   ``test_prior_runs.py`` feeds it the real 2026-08-18 streak and
          requires a halt, and feeds it a recovery and requires reopening.
"""

# Two consecutive is the trigger, not one. Single failures happen for
# reasons that do not touch state at all - a runner blip, a rebase race
# that the next run wins. Two in a row is systemic, and by then the bot
# has posted at most one unrecorded message rather than none.
HALT_AFTER_CONSECUTIVE_FAILURES = 2

# The streak lengths that get a Telegram alert. Deliberately computed from
# the streak itself rather than from a "have I already alerted" marker,
# because the marker would live in the very state that is not persisting.
# A stateless rule is the only kind that works while state is frozen.
FIRST_ALERT_STREAKS = (2, 6)
REPEAT_ALERT_EVERY = 24

SUCCESS = "success"


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


def should_alert(streak: int) -> bool:
    """True on the streak lengths worth interrupting a human for.

    Alerts at 2 (this is systemic), at 6 (nobody has looked), then once a
    day. Alerting every hour would replace one kind of spam with another,
    and the operator would learn to ignore exactly the channel that is
    trying to tell them the bot is down.
    """
    if streak in FIRST_ALERT_STREAKS:
        return True
    return streak > max(FIRST_ALERT_STREAKS) and streak % REPEAT_ALERT_EVERY == 0


def explain(streak: int) -> str:
    """One line naming the fault and what it stops, for logs and alerts."""
    if not should_halt_posting(streak):
        return f"State persistence looks healthy ({streak} failed run(s) since the last success)."
    return (
        f"{streak} consecutive workflow runs failed, so bot state has not been "
        f"committed since the last success. Posting is paused: any message sent "
        f"now would have its id lost, and would become permanently undeletable "
        f"after 48h. Check the state-commit step of the latest run."
    )
