"""The watchdog lives outside the bot, and it can start it again.

Lewis, 2026-09-01, after I mis-wired the crons and every scheduled run
came back ``skipped`` for 15 hours: *"you should really be able for the
bot to fix itself or something, killing itself like that is not good."*

The first fix only made the outage **visible**. This makes it
**recoverable**, and the mechanism was already sitting in the main
workflow's own condition:

```yaml
github.event_name == 'push'
|| github.event_name == 'workflow_dispatch'      # <-- this branch
|| (github.event_name == 'schedule' && github.event.schedule == '...')
```

⭐⭐ A ``workflow_dispatch`` satisfies that **regardless of what the cron
literals say**. A watchdog that dispatches on a stale heartbeat would
have carried the bot straight through the 2026-08-31 outage.

⛔ Where the watchdog LIVES is a separate claim and is tested in
``test_the_watchdog_is_outside_the_bot``. This file tests what it DOES.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from preflight.self_repair import (REPAIR_AFTER_HOURS, dispatch,
                                   dispatch_token, repair_message,
                                   should_repair)


class TestWhenItDecidesToRestartTheBot:
    def test_a_stale_heartbeat_triggers_a_restart(self):
        assert should_repair(REPAIR_AFTER_HOURS + 0.1)

    def test_a_fresh_one_does_not(self):
        assert not should_repair(0.7)

    def test_the_boundary_is_where_it_is_documented(self):
        assert not should_repair(REPAIR_AFTER_HOURS)

    def test_an_unreadable_heartbeat_never_dispatches(self):
        # ⛔ None means "cannot tell". Cannot-tell must not trigger
        # anything, the same rule prior_runs uses for halting, pointed
        # the other way. Dispatching blind could loop forever.
        assert not should_repair(None)


class TestItCannotFailSilently:
    """A self-repair that quietly does nothing is worse than none."""

    def test_no_token_at_all_is_reported_not_swallowed(self):
        ok, detail = dispatch("owner/repo", "")
        assert not ok and "no token available" in detail

    def test_no_repo_is_reported(self):
        ok, detail = dispatch("", "tok")
        assert not ok and "GITHUB_REPOSITORY" in detail

    def test_a_failed_repair_says_the_bot_is_down(self):
        text = repair_message(False, "HTTP 403: the token cannot dispatch", 9.0)
        assert "cannot restart itself" in text and "403" in text
        assert "9.0h" in text

    def test_a_successful_repair_says_what_it_did(self):
        text = repair_message(True, "dispatched", 5.0)
        assert "Forced a run via workflow_dispatch" in text

    def test_a_403_names_the_fix(self):
        # ⭐ This message is why a wrong design was caught in one reading
        # rather than becoming a mystery. It fired for real on
        # 2026-09-02 and named exactly what was missing.
        import urllib.error
        from unittest.mock import patch
        err = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        with patch("urllib.request.urlopen", side_effect=err):
            ok, detail = dispatch("owner/repo", "tok")
        assert not ok and "actions: write" in detail


class TestTheAutomaticTokenIsPreferred:
    """⛔⛔ I had the token rule backwards, and it cost a real outage.

    ``self_repair`` was written asserting that ``GITHUB_TOKEN`` cannot
    start a run, so it reached for a PAT. It then fired for real on the
    outage it was built for and returned **HTTP 403**.

    GitHub's docs say the opposite: *"events triggered by the
    GITHUB_TOKEN will not create a new workflow run, **with the
    following exceptions: workflow_dispatch and repository_dispatch
    events always create workflow runs**."*

    The automatic token works and needs no setup by anyone. Preferring
    the PAT makes self-repair depend on a secret that may not exist.
    """

    def test_the_automatic_token_wins(self):
        assert dispatch_token({"GITHUB_TOKEN": "auto",
                               "GIST_TOKEN": "pat"}) == "auto"

    def test_the_pat_is_the_fallback(self):
        assert dispatch_token({"GIST_TOKEN": "pat"}) == "pat"

    def test_neither_present_is_empty_not_an_error(self):
        assert dispatch_token({}) == ""

    def test_an_empty_automatic_token_falls_through(self):
        # can-fail counterpart: an unset secret arrives as "", which must
        # not shadow a working PAT.
        assert dispatch_token({"GITHUB_TOKEN": "", "GIST_TOKEN": "pat"}) == "pat"

    def test_a_network_error_does_not_raise(self):
        import urllib.error
        from unittest.mock import patch
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("down")):
            ok, detail = dispatch("owner/repo", "tok")
        assert not ok and "network error" in detail


class TestTheWatchdogActuallyCallsIt:
    """⛔ Proven is not reachable, and this is the third time this
    session the harness has caught me testing pieces and not wiring.

    Every test above exercises ``should_repair``, ``dispatch`` and
    ``repair_message`` directly. **None of them shows the watchdog calls
    any of it.** Deleting the whole repair block from ``watch()`` left
    the suite green until this class existed.
    """

    def _watch(self, monkeypatch, age_hours, dispatch_result=(True, "ok")):
        from preflight import watchdog
        calls = {"dispatch": [], "notify": []}
        monkeypatch.setattr(watchdog, "read_heartbeat", lambda: {"x": 1})
        monkeypatch.setattr(watchdog, "heartbeat_age_hours",
                            lambda record, now: age_hours)
        monkeypatch.setattr(watchdog, "dispatch",
                            lambda repo, token: calls["dispatch"].append(
                                (repo, token)) or dispatch_result)
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        # ⛔ BOTH tokens are set on purpose. The first version set only
        # the PAT, so reverting the watchdog to read GIST_TOKEN directly
        # passed and the mutation survived: a fixture that supplies one
        # candidate cannot test which candidate is chosen.
        monkeypatch.setenv("GIST_TOKEN", "pat-123")
        monkeypatch.setenv("GITHUB_TOKEN", "auto-456")
        watchdog.watch(fetch_conclusions=lambda r, t: None,
                       send_alert=lambda *a: None,
                       notify=lambda text: calls["notify"].append(text))
        return calls

    def test_a_stale_heartbeat_makes_it_dispatch(self, monkeypatch):
        # ⭐⭐ The end-to-end behaviour Lewis asked for: the bot restarts
        # itself instead of staying dead.
        calls = self._watch(monkeypatch, REPAIR_AFTER_HOURS + 5)
        assert calls["dispatch"] == [("owner/repo", "auto-456")], (
            "the watchdog must dispatch with the AUTOMATIC token; reaching "
            "for the PAT is what returned HTTP 403 on 2026-09-02")
        assert calls["notify"] and "workflow_dispatch" in calls["notify"][0]

    def test_a_healthy_heartbeat_dispatches_nothing(self, monkeypatch):
        # can-fail counterpart: proves the dispatch is driven by the
        # reading and not fired on every run.
        calls = self._watch(monkeypatch, 0.5)
        assert calls["dispatch"] == [] and calls["notify"] == []

    def test_a_failed_dispatch_is_still_reported(self, monkeypatch):
        calls = self._watch(monkeypatch, REPAIR_AFTER_HOURS + 5,
                            dispatch_result=(False, "HTTP 403"))
        assert calls["notify"] and "cannot restart itself" in calls["notify"][0]
