"""The quick queue re-check: when it is asked for, and that it is wired up.

Lewis, 2026-09-13: "if the queue changes, refire in 10 minutes or less... if
unchanged go back to 30". The logic is small. The wiring is where it would
break silently: a mistyped step id or output name would make every re-check
condition false, and nothing would ever go red.
"""

import os

import yaml

from scheduled import queue_refire
from scheduled.queue_refire import MAX_CHAIN, decide

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wf(name):
    with open(os.path.join(_ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── the decision ─────────────────────────────────────────────────────────

def test_a_changed_queue_asks_for_a_recheck():
    state = {}
    assert decide(state, "a", "b", is_refire=False)
    assert state["queue_refire_chain"] == 1


def test_an_unchanged_queue_goes_back_to_the_schedule():
    state = {"queue_refire_chain": 3}
    assert not decide(state, "a", "a", is_refire=True)
    assert state["queue_refire_chain"] == 0


def test_the_chain_stops_at_the_cap():
    """A busy evening must not dispatch a run every 10 minutes forever."""
    state = {}
    asked = [decide(state, str(i), str(i + 1), is_refire=i > 0) for i in range(MAX_CHAIN + 2)]
    assert asked[:MAX_CHAIN] == [True] * MAX_CHAIN
    assert asked[MAX_CHAIN] is False


def test_a_scheduled_run_starts_a_fresh_chain():
    state = {"queue_refire_chain": MAX_CHAIN}
    assert decide(state, "a", "b", is_refire=False)
    assert state["queue_refire_chain"] == 1


def test_the_signal_reaches_the_workflow(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    queue_refire.announce(True)
    assert out.read_text(encoding="utf-8") == "refire=true\n"


def test_no_workflow_no_signal(monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    queue_refire.announce(True)  # must not raise outside Actions


def test_the_refire_flag_is_read_from_the_workflow(monkeypatch):
    monkeypatch.setenv("QUEUE_REFIRE_RUN", "true")
    assert queue_refire.is_refire_run()
    monkeypatch.setenv("QUEUE_REFIRE_RUN", "")
    assert not queue_refire.is_refire_run()


# ── the wiring ───────────────────────────────────────────────────────────

def test_both_bot_jobs_signal_and_request_a_recheck_after_the_state_push():
    jobs = _wf("pbp-reminder.yml")["jobs"]
    for name in ("run", "run-queue"):
        steps = jobs[name]["steps"]
        ids = [s.get("id") for s in steps]
        assert "checker" in ids, f"{name}: the checker step has no id"
        checker = steps[ids.index("checker")]
        assert checker["env"]["QUEUE_REFIRE_RUN"] == "${{ inputs.refire }}"
        names = [s.get("name") for s in steps]
        ask = names.index("Ask for a quick queue re-check")
        assert ask > names.index("Commit data (archive + transcripts + state)"), \
            f"{name}: the re-check must start after the state push"
        assert steps[ask]["if"] == "steps.checker.outputs.refire == 'true'"
        assert "queue-refire.yml" in steps[ask]["run"]
        assert jobs[name]["permissions"]["actions"] == "write", \
            f"{name}: starting a workflow needs actions: write"


def test_the_bot_accepts_the_refire_input():
    on = _wf("pbp-reminder.yml").get("on") or _wf("pbp-reminder.yml")[True]
    assert on["workflow_dispatch"]["inputs"]["refire"]["type"] == "boolean"


def test_the_wait_happens_outside_the_bot_lock():
    """Waiting inside pbp-checker would stall every scheduled run behind it."""
    wf = _wf("queue-refire.yml")
    assert wf["concurrency"]["group"] != _wf("pbp-reminder.yml")["concurrency"]["group"]
    steps = wf["jobs"]["wait-then-dispatch"]["steps"]
    run = " ".join(s.get("run", "") for s in steps)
    assert "sleep" in run
    assert "gh workflow run pbp-reminder.yml" in run and "-f refire=true" in run


# ── through checker.main, where the before/after comparison lives ────────

def _run_main(tmp_path, change: bool, refire_env: str = ""):
    from unittest.mock import patch
    import checker

    out = tmp_path / "gh_out"
    state = {"offset": 5, "last_queue_fingerprint": "before"}

    def _fake_checks(config, bot_state, only=()):
        if change:
            bot_state["last_queue_fingerprint"] = "after"

    cfg = {"group_id": -1001, "bot_topic_id": 999, "topic_pairs": []}
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "GIST_TOKEN": "g",
                                 "GIST_ID": "i", "GITHUB_OUTPUT": str(out),
                                 "QUEUE_REFIRE_RUN": refire_env}), \
         patch.object(checker.tg, "init"), \
         patch.object(checker.state_store, "init"), \
         patch.object(checker.state_store, "load", return_value=state), \
         patch.object(checker.state_store, "save"), \
         patch.object(checker.helpers, "load_config", return_value=cfg), \
         patch.object(checker.helpers, "load_settings"), \
         patch.object(checker.helpers, "validate_config", return_value=[]), \
         patch.object(checker.tg, "get_updates", return_value=[]), \
         patch.object(checker, "_run_checks", _fake_checks), \
         patch.object(checker, "cleanup_timestamps"), \
         patch.object(checker, "update_transcript_index"):
        checker.main(queue_only=True)
    return out.read_text(encoding="utf-8"), state


def test_a_run_that_changes_the_queue_signals_the_workflow(tmp_path):
    signal, state = _run_main(tmp_path, change=True)
    assert signal == "refire=true\n"
    assert state["queue_refire_chain"] == 1


def test_a_run_that_leaves_the_queue_alone_does_not(tmp_path):
    signal, state = _run_main(tmp_path, change=False)
    assert signal == "refire=false\n"
    assert state["queue_refire_chain"] == 0
