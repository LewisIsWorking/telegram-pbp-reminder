"""Every cron must be claimed by a job, and every job must name a real cron.

⛔⛔ **I BROKE THE BOT WITH THIS AND NOTHING WENT RED.** 2026-08-31, PR
#75 moved the crons off GitHub's contended `:00`/`:30` minutes to `:13`
and `:43`. Both side-effecting jobs gate on the literal cron string:

```yaml
if: ... github.event.schedule == '0 * * * *'      # run
if: github.event_name == 'schedule' && ... == '30 * * * *'   # run-queue
```

Those were not updated. Every scheduled run then had **no job whose
condition was true**, so GitHub marked the run **`skipped`** and the bot
stopped for 15 hours. `skipped` is neither success nor failure:

* the workflow list shows no red,
* `consecutive_failures` counts only finished non-success runs and never
  saw one, and
* the preflight heartbeat did age out, which is the only reason it was
  noticeable at all, and it blamed the state-commit step.

⭐ **The guard I wrote in that same PR checked the cron MINUTES and not
the wiring the minutes feed.** It asserted `:13` and `:43` were not
contended and were 30 apart. Both true. Both useless. A guard that
validates one end of a reference and not the other end is half a guard.

⚠️ This file asserts the **relationship**, in both directions, so a cron
cannot be moved without its job, and a job cannot name a cron that does
not exist.
"""

import os
import re

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml
    yaml = None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WF = os.path.join(_ROOT, ".github", "workflows", "pbp-reminder.yml")

# Jobs that may only run for a specific schedule. Each must reference
# exactly one cron from the schedule block.
_SCHEDULE_GATED = ("run", "run-queue")


def _doc() -> dict:
    if yaml is None:  # pragma: no cover
        pytest.skip("pyyaml not installed")
    with open(_WF, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def declared_crons(doc: dict) -> set:
    triggers = doc.get("on") or doc.get(True) or {}
    return {str(e["cron"]) for e in triggers.get("schedule", [])}


def crons_named_in(condition: str) -> set:
    """Every cron literal a job's `if:` compares against."""
    return set(re.findall(r"'(\d+ [^']*)'", condition))


def _condition(doc: dict, job: str) -> str:
    return str(doc["jobs"][job].get("if", ""))


class TestTheExtractionWorks:
    """Prove the input can vary before trusting the verdict."""

    def test_it_reads_a_cron_out_of_a_condition(self):
        assert crons_named_in(
            "github.event.schedule == '13 * * * *'") == {"13 * * * *"}

    def test_it_reads_several(self):
        cond = "a == '13 * * * *' || b == '43 * * * *'"
        assert crons_named_in(cond) == {"13 * * * *", "43 * * * *"}

    def test_the_2026_08_31_breakage_is_detected(self):
        # ⭐⭐ The exact mismatch that stopped the bot, as a unit test.
        declared = {"13 * * * *", "43 * * * *"}
        named = crons_named_in("github.event.schedule == '0 * * * *'")
        assert not (named & declared), "guard would not have caught PR #75"

    def test_a_condition_with_no_cron_reads_as_empty(self):
        assert crons_named_in("github.event_name == 'push'") == set()


class TestEveryJobNamesARealCron:
    @pytest.mark.parametrize("job", _SCHEDULE_GATED)
    def test_the_job_references_a_declared_cron(self, job):
        doc = _doc()
        named = crons_named_in(_condition(doc, job))
        declared = declared_crons(doc)
        assert named, f"the {job} job's condition names no cron at all"
        orphans = named - declared
        assert not orphans, (
            f"the {job} job gates on {sorted(orphans)}, which is not in the "
            f"schedule block {sorted(declared)}. Every scheduled run will "
            f"have no matching job, GitHub will mark it SKIPPED rather than "
            f"failed, and the bot will stop without anything going red.")

    @pytest.mark.parametrize("job", _SCHEDULE_GATED)
    def test_the_job_claims_exactly_one_cron(self, job):
        # Two crons on one job would run the full pass twice an hour.
        named = crons_named_in(_condition(_doc(), job))
        assert len(named) == 1, f"the {job} job claims {sorted(named)}"


class TestEveryCronIsClaimed:
    def test_no_cron_is_left_without_a_job(self):
        # ⛔ The other direction. A cron nobody gates on fires a run in
        # which nothing happens: billed, green-ish, and pointless.
        doc = _doc()
        claimed = set()
        for job in _SCHEDULE_GATED:
            claimed |= crons_named_in(_condition(doc, job))
        unclaimed = declared_crons(doc) - claimed
        assert not unclaimed, (
            f"cron(s) {sorted(unclaimed)} are declared but no job runs for "
            f"them. Those runs will do nothing at all.")

    def test_the_two_jobs_do_not_share_a_cron(self):
        doc = _doc()
        full = crons_named_in(_condition(doc, "run"))
        queue = crons_named_in(_condition(doc, "run-queue"))
        assert not (full & queue), (
            "the full pass and the queue-only pass fire on the same cron; "
            "one of them is redundant and they will race the concurrency "
            "group every time")
