"""The cron minutes must not be :00 or :30, and must stay 30 apart.

2026-08-31. Lewis pasted the bot's own alert: *"Bot posting PAUSED ...
the last state push landed 3.2h ago"*, pointing at the state-commit step.

The state-commit step was fine. It has never failed:

```
[preflight] State persistence looks healthy (last push 0.7h ago).
State push succeeded on attempt 1
```

⛔ **The runs were not happening at all.** GitHub's docs say the schedule
event is delayed under load and that "high load times include the start
of every hour". We asked for `0 * * * *` and `30 * * * *`, the two most
contended minutes on the platform.

Measured two independent ways that agree, the Actions API and the git
history of `data/ci_heartbeat.json` (which no API cache can touch):

```
2026-08-23 .. 08-31: 173 of 372 scheduled runs delivered = 46%
13 gaps over the preflight 3h limit, worst 11.0h
per day   08-23  45   08-27   5   08-30  12
          08-24  41   08-28   4   08-31   2
          08-25  45   08-29  10
```

⚠️ This guard pins the *placement*, which is the part a later edit would
casually undo ("tidy the cron back to the hour"). It cannot prove GitHub
delivers better at :13, only that we are no longer asking for the slot
GitHub documents as worst. Re-measure with `tools/schedule_delivery.py`
rather than assuming this fixed it.
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

# The minutes GitHub names as high load. Not a style preference.
CONTENDED = {0, 30}
# The queue pass promises "clears show up within ~30 min instead of ~60".
REQUIRED_SPACING_MINUTES = 30


def _workflow() -> dict:
    if yaml is None:  # pragma: no cover
        pytest.skip("pyyaml not installed")
    with open(_WF, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def cron_minutes(doc: dict) -> list[int]:
    """Every schedule entry's minute field, in file order.

    Takes the parsed doc rather than reading the file, so the tests below
    can feed it a known-bad schedule and prove the extraction works. A
    guard whose input cannot be varied has never been shown to fire.
    """
    # PyYAML parses the bare key `on:` as the boolean True.
    triggers = doc.get("on") or doc.get(True) or {}
    minutes = []
    for entry in triggers.get("schedule", []):
        field = str(entry["cron"]).split()[0]
        if not re.fullmatch(r"\d+", field):
            raise AssertionError(
                f"cron minute {field!r} is not a plain number, so this "
                f"guard cannot reason about when it fires")
        minutes.append(int(field))
    return minutes


class TestTheExtractionWorks:
    """Prove the input can vary before trusting the verdict."""

    def test_it_reads_the_minute_from_a_synthetic_schedule(self):
        doc = {"on": {"schedule": [{"cron": "13 * * * *"},
                                   {"cron": "43 * * * *"}]}}
        assert cron_minutes(doc) == [13, 43]

    def test_the_old_schedule_would_be_caught(self):
        # ⭐⭐ The mutation, run as a test: this is exactly what the file
        # said until 2026-08-31, and the guard must reject it.
        doc = {"on": {"schedule": [{"cron": "0 * * * *"},
                                   {"cron": "30 * * * *"}]}}
        assert set(cron_minutes(doc)) & CONTENDED

    def test_a_cron_expression_it_cannot_read_is_an_error(self):
        # Not a silent pass. `*/30 * * * *` fires ON the contended
        # minutes while looking like a different answer.
        with pytest.raises(AssertionError):
            cron_minutes({"on": {"schedule": [{"cron": "*/30 * * * *"}]}})


class TestTheRealWorkflow:
    def test_there_are_still_two_scheduled_passes(self):
        assert len(cron_minutes(_workflow())) == 2, (
            "the hourly full pass and the queue-only pass are both needed")

    def test_neither_lands_on_a_contended_minute(self):
        minutes = cron_minutes(_workflow())
        clash = sorted(set(minutes) & CONTENDED)
        assert not clash, (
            f"cron minute(s) {clash} are the ones GitHub documents as "
            f"high load. Delivery was 46% while we asked for them. Pick "
            f"any other minute; the absolute value does not matter.")

    def test_they_stay_thirty_minutes_apart(self):
        first, second = sorted(cron_minutes(_workflow()))
        assert second - first == REQUIRED_SPACING_MINUTES, (
            f"the two passes are {second - first} minutes apart. The "
            f"queue pass exists so GM reply-to clears appear within ~30 "
            f"min rather than ~60, and that promise is the spacing.")

    def test_both_run_every_hour_of_every_day(self):
        # Moving the minute must not have narrowed the hours by accident.
        triggers = _workflow().get("on") or _workflow().get(True)
        for entry in triggers["schedule"]:
            assert str(entry["cron"]).split()[1:] == ["*", "*", "*", "*"], (
                f"{entry['cron']!r} no longer runs every hour, every day")
