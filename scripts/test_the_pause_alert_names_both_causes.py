"""A stale heartbeat has two causes, and the alert named one.

2026-08-31. The bot paused itself and said:

```
🛑 Bot posting PAUSED
Posting is paused because the last state push landed 3.2h ago, over the
3h limit. ... Check the state-commit step of the latest run.
```

The state-commit step had never failed. Every run that fired logged
`State push succeeded on attempt 1`. GitHub was delivering as few as 4
scheduled runs a day against 48 requested, so the heartbeat aged out
between runs.

⛔ **preflight cannot distinguish the two causes and never could.** Our
push failed, or GitHub never ran us. A run that never happened writes
nothing; a run whose push failed also leaves nothing behind. They are
identical from inside the repository. Naming only the first sent a human
to a healthy step.

⭐ The advice is now chosen from the same `reasons` list as the decision,
the same discipline `explain` already applied to the *cause*. A failed run
IS evidence the commit step ran and lost, so that case keeps the direct
instruction. A stale heartbeat alone is not, so it names both.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from preflight.prior_runs import (MAX_HEARTBEAT_AGE_HOURS, explain,
                                  halt_reasons)

_STALE_ONLY = 5.5      # the real 2026-08-31 05:10 reading
_FRESH = 0.7           # the real 05:54 reading


class TestAStaleHeartbeatAlone:
    """GitHub dropped the runs. The commit step is not the fault."""

    def _reasons(self):
        reasons = halt_reasons(0, _STALE_ONLY)
        assert reasons, "a 5.5h heartbeat must halt; fixture is wrong"
        return reasons

    def test_it_says_to_check_whether_runs_are_happening(self):
        # ⭐⭐ The bug. Before this, the only advice was the commit step.
        assert "whether runs are happening" in explain(self._reasons())

    def test_it_still_mentions_the_commit_step_first(self):
        # Not a swap. The commit step is still the more likely cause and
        # is still worth checking first; it is no longer the only one.
        text = explain(self._reasons())
        assert text.index("state-commit step") < text.index("runs are happening")

    def test_the_age_and_the_limit_are_both_in_the_message(self):
        text = explain(self._reasons())
        assert "5.5h" in text and f"{MAX_HEARTBEAT_AGE_HOURS:g}h limit" in text


class TestFailedRunsKeepTheDirectInstruction:
    """A run that failed IS evidence the commit step ran and lost."""

    def test_it_does_not_hedge(self):
        reasons = halt_reasons(4, None)
        assert reasons, "4 consecutive failures must halt; fixture is wrong"
        text = explain(reasons)
        assert "Check the state-commit step of the latest run." in text
        assert "whether runs are happening" not in text, (
            "a failed run already tells you runs are happening")

    def test_both_reasons_together_still_point_at_the_commit_step(self):
        # The 2026-08-18 branch-protection outage looked like this: runs
        # failing AND the heartbeat frozen. The commit step really was
        # the fault, so the hedge must not dilute the instruction.
        text = explain(halt_reasons(25, 48.0))
        assert "whether runs are happening" not in text
        assert "25 consecutive workflow runs failed" in text


class TestHealthyIsUnchanged:
    def test_a_fresh_heartbeat_reports_healthy(self):
        # can-fail counterpart: proves the tests above are reading a
        # message that is not always produced.
        assert halt_reasons(0, _FRESH) == []
        text = explain([], _FRESH)
        assert text.startswith("State persistence looks healthy")
        assert "0.7h ago" in text

    def test_healthy_carries_no_advice_at_all(self):
        text = explain([], _FRESH)
        assert "state-commit step" not in text
