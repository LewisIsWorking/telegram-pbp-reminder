"""Ask for a quick queue re-check after the queue changes.

Lewis, 2026-09-13: "if the queue changes, refire in 10 minutes or less...
if unchanged go back to 30". A change means players are active or the GM is
replying right now, which is exactly when a 30-minute wait is longest.

How it works:

* ``checker.main`` notes the queue fingerprint before the checks run and
  passes the one after to ``decide``. The fingerprint changes on a real
  queue change (a new post, a cleared reply, a silent campaign coming or
  going, the queue emptying). It does not change on an in-place refresh or
  a daily repost, so neither of those asks for a re-check.
* ``announce`` writes ``refire=true`` to ``$GITHUB_OUTPUT``. The workflow
  then starts ``queue-refire.yml``, which waits outside the ``pbp-checker``
  lock and dispatches a normal run with ``refire=true``.
* A re-check that finds nothing changed asks for nothing, so the cadence
  falls back to the scheduled 30 minutes on its own.

⛔ ``MAX_CHAIN`` caps consecutive re-checks. Without it a busy evening, with
someone posting every few minutes, would dispatch a run every ~10 minutes
indefinitely. The chain count lives in state (``queue_refire_chain``) and
resets on any run that is not itself a re-check.
"""

import os

# Six quick re-checks in a row, about an hour of 10-minute cadence, then the
# normal schedule takes over until the next scheduled run sees a change.
MAX_CHAIN = 6


def decide(state: dict, before: str | None, after: str | None,
           is_refire: bool) -> bool:
    """Whether this run should ask for a quick re-check. Updates the chain."""
    chain = state.get("queue_refire_chain", 0) if is_refire else 0
    if before == after or chain >= MAX_CHAIN:
        state["queue_refire_chain"] = 0
        return False
    state["queue_refire_chain"] = chain + 1
    return True


def announce(want: bool) -> None:
    """Tell the workflow, through ``$GITHUB_OUTPUT``. A no-op outside Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        out.write(f"refire={'true' if want else 'false'}\n")


def is_refire_run() -> bool:
    """True when the workflow dispatched this run as a quick re-check."""
    return os.environ.get("QUEUE_REFIRE_RUN", "").lower() == "true"
