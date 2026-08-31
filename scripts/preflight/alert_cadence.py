"""When to interrupt a human about a state-persistence outage.

Extracted from ``preflight/prior_runs.py`` on 2026-08-31, which had
reached 197 lines and needed room for ``explain`` to stop naming a single
cause. Deciding *whether to halt* and deciding *whether to shout* are
different questions with different inputs; only the second one is here.

⭐ Deliberately computed from the observations themselves rather than
from a "have I already alerted" marker. The marker would live in the very
state that is not persisting, so it would reset on every run and alert
every hour, or freeze and never alert again. A stateless rule is the only
kind that works while state is frozen.
"""

# Alert at onset, again at 3h (nobody has looked), then once a day.
FIRST_ALERT_HOURS = (0, 3)
REPEAT_ALERT_EVERY_HOURS = 24

# Roughly two runs an hour: the hourly full pass plus the queue pass.
# ⚠️ Only used to turn a streak into hours when the heartbeat cannot be
# read, and only ever an upper bound now: as of 2026-08-27 GitHub has been
# delivering as few as 4 scheduled runs a day, so a streak of N failures
# can span far more than N/2 hours. It converts a proxy into a rougher
# proxy, which is why the heartbeat is preferred whenever it can be read.
RUNS_PER_HOUR = 2


def broken_hours(streak: int, age_hours: float | None,
                 max_age_hours: float) -> int:
    """Whole hours this has been broken, from whichever signal can say.

    Prefers the heartbeat, which measures the outage directly. Falls back
    to converting the run streak, which is a proxy and is only needed
    before the first heartbeat exists.
    """
    if age_hours is not None:
        return max(0, int(age_hours - max_age_hours))
    return streak // RUNS_PER_HOUR


def should_alert(hours: int) -> bool:
    """True on the elapsed times worth interrupting a human for.

    Alerting every run would replace one kind of spam with another, and
    the operator would learn to ignore exactly the channel that is trying
    to tell them the bot is down.
    """
    if hours in FIRST_ALERT_HOURS:
        return True
    return (hours > max(FIRST_ALERT_HOURS)
            and hours % REPEAT_ALERT_EVERY_HOURS == 0)
