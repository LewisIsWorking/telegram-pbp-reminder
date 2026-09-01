"""Structural properties of the watchdog workflow file.

Split from ``test_the_bot_restarts_itself`` on 2026-09-01 at the 200-line
limit. That file tests what the watchdog *does*; this one tests where it
*lives*, which is a separate claim and the one that took 15 hours to
learn.

⛔⛔ **A WATCHDOG INSIDE THE THING IT WATCHES IS NOT A WATCHDOG.** The
2026-08-31 outage skipped every job in ``pbp-reminder.yml``, including
any watchdog job placed there. The first fix put one in that file
anyway; it would have survived *that* bug but not a broken ``on:`` block
in the same file, which stops everything in it from running at all.

Four properties are load-bearing and each has its own test:
1. it is a **separate file** with its own schedule;
2. it is **not in the main concurrency group**, so a stuck main run
   cannot block the thing that notices stuck main runs;
3. it holds **``contents: read``**, so it can never write a heartbeat and
   erase the evidence of the outage; and
4. it is handed the **PAT**, because ``GITHUB_TOKEN`` cannot start a run.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml
    yaml = None

from preflight.self_repair import WORKFLOW_FILE

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WATCHDOG = os.path.join(_ROOT, ".github", "workflows", "watchdog.yml")
_MAIN = os.path.join(_ROOT, ".github", "workflows", "pbp-reminder.yml")


def _load(path: str) -> dict:
    if yaml is None:  # pragma: no cover
        pytest.skip("pyyaml not installed")
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class TestTheWatchdogIsOutsideWhatItWatches:
    def test_it_is_a_separate_workflow_file(self):
        # ⛔⛔ The whole point. A watchdog job inside pbp-reminder.yml
        # dies with a broken `on:` block in that file.
        assert os.path.exists(_WATCHDOG)
        assert "watchdog" not in _load(_MAIN)["jobs"], (
            "the watchdog is back inside the workflow it watches; a YAML "
            "error in that file would take both down together")

    def test_it_has_its_own_schedule(self):
        triggers = _load(_WATCHDOG).get("on") or _load(_WATCHDOG).get(True)
        assert triggers.get("schedule"), "the watchdog does not run on a timer"

    def test_it_does_not_share_the_main_concurrency_group(self):
        # ⚠️ Sharing it would let a stuck main run block the watchdog,
        # which is exactly when it is needed.
        main_group = _load(_MAIN).get("concurrency", {}).get("group")
        watch_group = _load(_WATCHDOG).get("concurrency", {}).get("group")
        assert watch_group != main_group

    def test_it_cannot_write_and_so_cannot_forge_a_heartbeat(self):
        perms = _load(_WATCHDOG)["jobs"]["watch"].get("permissions", {})
        assert perms.get("contents") == "read", (
            f"watchdog has contents: {perms.get('contents')!r}. Write access "
            f"would let it push a heartbeat and report health forever while "
            f"nothing else ran.")

    def test_it_runs_in_report_only_mode(self):
        steps = _load(_WATCHDOG)["jobs"]["watch"]["steps"]
        runs = " ".join(str(s.get("run", "")) for s in steps)
        assert "preflight.gate --watch" in runs, (
            "plain `preflight.gate` writes a heartbeat and would mask the "
            "outage it is watching for")

    def test_it_is_given_the_pat_not_just_the_automatic_token(self):
        steps = _load(_WATCHDOG)["jobs"]["watch"]["steps"]
        env = {}
        for step in steps:
            env.update(step.get("env") or {})
        assert "GIST_TOKEN" in env, (
            "without a PAT the dispatch is refused by GitHub and the bot "
            "cannot restart itself")

    def test_it_dispatches_the_main_workflow_by_name(self):
        assert WORKFLOW_FILE == os.path.basename(_MAIN)
