"""The watchdog must not manufacture the harm it exists to prevent.

Lewis, 2026-09-02, after the self-repair shipped: *"verify, make sure
it's safe."* It was not.

⛔⛔ **`watch()` called `notify()` on EVERY repair attempt, ungated.** The
watchdog runs twice an hour, so a day of downtime was **48 Telegram
messages**. Each one is an unrecorded bot message, which becomes
**permanently undeletable after 48 hours**.

That is the exact harm the whole preflight system exists to prevent, and
it was being produced **during the one window in which posting is
forbidden for that very reason**. The gate says "any message sent now
would have its id lost"; the watchdog was sending 48 of them.

Lewis's own paste showed the shape already: PAUSED, self-repair, PAUSED.
Three messages where one would do.

⭐ The fix is not to stop repairing. **The dispatch still runs on every
tick**, because it is free, the concurrency group serialises it, and it
is the actual recovery. Only the MESSAGE is rationed, onto the existing
alert cadence, and the repair outcome now rides on the same message
rather than being a second one.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from preflight.prior_runs import broken_hours, should_alert
from preflight.self_repair import REPAIR_AFTER_HOURS


class _Watch:
    """Drive watch() and record every outbound message and dispatch."""

    def __init__(self, monkeypatch, age_hours, dispatch_ok=True):
        from preflight import watchdog
        self.alerts, self.notifies, self.dispatches = [], [], []
        monkeypatch.setattr(watchdog, "read_heartbeat", lambda: {"x": 1})
        monkeypatch.setattr(watchdog, "heartbeat_age_hours",
                            lambda record, now: age_hours)
        monkeypatch.setattr(watchdog, "dispatch",
                            lambda repo, token: self.dispatches.append(token)
                            or (dispatch_ok, "detail"))
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_TOKEN", "auto")
        monkeypatch.delenv("GIST_TOKEN", raising=False)
        watchdog.watch(fetch_conclusions=lambda r, t: None,
                       send_alert=lambda reasons, age, repo, extra="":
                           self.alerts.append(extra),
                       notify=lambda text: self.notifies.append(text))

    @property
    def messages(self):
        return len(self.alerts) + len(self.notifies)


class TestOneMessagePerAlertNotOnePerTick:
    def test_a_quiet_hour_of_the_outage_sends_nothing(self, monkeypatch):
        # ⭐⭐ The bug. At 5h broken_hours is 2, which the alert cadence
        # deliberately skips. Before the fix this still posted, because
        # notify() was outside the cadence check entirely.
        w = _Watch(monkeypatch, 5.0)
        assert w.messages == 0, (
            f"sent {w.messages} message(s) during a lull in the alert "
            f"cadence; at 2 runs/hour that is how 48 orphans a day happen")

    def test_but_it_still_repairs_during_that_lull(self, monkeypatch):
        # ⭐ The dispatch is free and is the actual recovery. Rationing
        # the message must not ration the fix.
        assert _Watch(monkeypatch, 5.0).dispatches == ["auto"]

    def test_the_repair_outcome_rides_on_the_alert(self, monkeypatch):
        # One message, not two. Lewis received PAUSED + self-repair +
        # PAUSED for a single outage.
        w = _Watch(monkeypatch, 3.5)
        assert len(w.alerts) == 1 and w.notifies == []
        assert w.alerts[0], "the repair outcome was dropped, not merged"

    def test_a_healthy_bot_sends_nothing_and_repairs_nothing(self, monkeypatch):
        w = _Watch(monkeypatch, 0.5)
        assert w.messages == 0 and w.dispatches == []


class TestTheRealSendAlertCarriesIt:
    """⛔ Proven is not reachable, again. Every test above stubs
    ``send_alert``, so the repair outcome could be dropped by the real
    one and nothing would notice. A mutation deleting the ``extra``
    branch survived until this existed."""

    def _sent(self, monkeypatch, **kwargs):
        from preflight import gate
        out = []
        monkeypatch.setattr(gate, "notify", lambda text: out.append(text))
        gate.send_alert(["a reason"], 5.0, "owner/repo", **kwargs)
        return out[0]

    def test_the_extra_reaches_the_message(self, monkeypatch):
        text = self._sent(monkeypatch, extra="REPAIR-OUTCOME-HERE")
        assert "REPAIR-OUTCOME-HERE" in text

    def test_the_pause_reason_is_still_there_too(self, monkeypatch):
        # can-fail counterpart: the extra must be ADDED, not substituted.
        text = self._sent(monkeypatch, extra="REPAIR-OUTCOME-HERE")
        assert "Bot posting PAUSED" in text and "a reason" in text

    def test_no_extra_leaves_the_message_unchanged(self, monkeypatch):
        text = self._sent(monkeypatch)
        assert "Bot posting PAUSED" in text and text.count("\n\n") == 2


class TestTheMessageBudgetOverARealOutage:
    """⛔ The number that matters: how many undeletable messages does a
    day of downtime cost?"""

    def _ticks(self):
        # Watchdog fires twice an hour; walk 24h of heartbeat ages.
        return [REPAIR_AFTER_HOURS + i * 0.5 for i in range(48)]

    def test_a_full_day_down_costs_a_handful_not_dozens(self, monkeypatch):
        sent = sum(1 for age in self._ticks()
                   if should_alert(broken_hours(0, age)))
        assert sent <= 8, (
            f"{sent} messages in 24h of downtime. Each is permanently "
            f"undeletable after 48h.")
        assert sent >= 1, "an outage must still reach a human"

    def test_the_old_behaviour_would_have_been_every_tick(self):
        # can-fail counterpart, and the measurement that justifies the
        # change: ungated, every tick past the repair threshold posts.
        ungated = sum(1 for age in self._ticks() if age > REPAIR_AFTER_HOURS)
        assert ungated >= 40, "fixture no longer models a real outage"
