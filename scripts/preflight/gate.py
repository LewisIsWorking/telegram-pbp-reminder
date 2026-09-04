"""Run before anything posts: pause the bot when its state is not persisting.

Added 2026-08-19. See ``prior_runs`` for why a frozen state must silence
the bot rather than merely be logged.

Order of business, and it matters:

  1. Write the heartbeat, so this run has something to push and its own
     conclusion becomes honest evidence for the next run's decision.
  2. Ask the Actions API how the previous runs of this workflow ended.
  3. If the streak says state is frozen, set ``halt=true`` and let the
     workflow skip its posting steps.
  4. Alert a human on the streak lengths worth interrupting for.

⚠️ **Exits 0 in every path, including its own errors.** This gate decides
whether *other* steps run; it must not decide whether the *run* passes.
If it failed the job it would keep the very streak alive that closes it,
and the bot could never recover - the commit-and-push step still needs to
run so that a repaired push turns the run green and reopens the gate.

⚠️ **Fails open when it cannot tell.** An unreachable API is not evidence
that state is broken, and halting on "don't know" would be unrecoverable
for the same reason. It says so loudly in the log instead.

Counts failures from every event, not just ``schedule``. A push that
breaks the tests turns runs red too, and pausing the bot then is also the
answer - a bot whose suite is failing should not be posting either.
"""

import os
import sys
from datetime import datetime, timezone

import requests

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from preflight.delivery_gap import drop_stale_heartbeat_reason  # noqa: E402
from preflight.heartbeat import (heartbeat_age_hours,  # noqa: E402
                                 read_heartbeat, write_heartbeat)
from preflight.run_history import (RUNS_TO_INSPECT,  # noqa: F401,E402
                                   WORKFLOW_FILE, fetch_conclusions,
                                   fetch_runs)
from preflight.prior_runs import (broken_hours,  # noqa: E402
                                  consecutive_failures, explain, halt_reasons,
                                  should_alert)


def send_alert(reasons: list, age_hours: float | None, repo: str,
               extra: str = "") -> None:
    """Tell a human, on the streak lengths that warrant it.

    ⚠️ This post is itself an unrecorded bot message, and so becomes an
    orphan - the exact harm the gate exists to prevent. It is worth it at
    most once a day, because it is the only thing that brings a human to
    fix the cause. Nothing else the bot sends earns that trade.

    ⭐ ``extra`` carries the self-repair outcome so it rides on THIS
    message instead of being a second one. Added 2026-09-02: the
    watchdog was notifying on every repair attempt, ungated, which is
    48 messages a day during an outage. Each one is an unrecorded bot
    message that becomes permanently undeletable after 48h, so the
    watchdog was manufacturing the exact harm it exists to prevent,
    during the very window in which posting is forbidden for that reason.
    """
    body = f"\U0001f6d1 Bot posting PAUSED\n\n{explain(reasons, age_hours)}"
    if extra:
        body += f"\n\n{extra}"
    notify(f"{body}\n\nhttps://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}")


def notify(text: str) -> None:
    """Send one message to the bot topic. Never raises.

    Extracted from ``send_alert`` on 2026-09-01 so the self-repair path
    can report what it did through the same channel. ⚠️ Every caller is
    posting an unrecorded message and creating an orphan; that price is
    only worth paying for things that bring a human to the keyboard.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("[preflight] no bot token; skipping alert")
        return
    from helpers_pkg.config import load_config
    config = load_config()
    thread_id = config.get("bot_topic_id")
    if not thread_id:
        print("[preflight] no bot_topic_id; skipping alert")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": config["group_id"], "message_thread_id": thread_id,
                  "text": text},
            timeout=20,
        )
        print("[preflight] alert sent")
    except Exception as error:  # noqa: BLE001 - alerting must not break the gate
        print(f"[preflight] alert failed: {error}")


def publish_halt(halt: bool) -> None:
    """Hand the decision to the workflow via ``$GITHUB_OUTPUT``."""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(f"halt={'true' if halt else 'false'}\n")


def watch() -> int:
    """Report-only entry point. Implementation in preflight/watchdog.py,
    which was extracted 2026-09-01 when this file reached 211 lines."""
    from preflight.watchdog import watch as _watch
    return _watch(fetch_conclusions, send_alert, notify)


def main() -> int:
    if "--watch" in sys.argv:
        return watch()
    # ⚠️ ORDER IS LOAD-BEARING. The committed heartbeat must be read before
    # this run writes its own, or the gate would measure itself and every
    # run would look perfectly healthy.
    heartbeat = read_heartbeat()
    age_hours = heartbeat_age_hours(heartbeat, datetime.now(timezone.utc))
    if age_hours is None:
        print("[preflight] no readable heartbeat yet; relying on run history "
              "alone for this run.")

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    runs = fetch_runs(repo, token) if repo and token else None
    conclusions = None if runs is None else [r.get("conclusion") for r in runs]
    if conclusions is None:
        # Not evidence of health, so it cannot clear the heartbeat's verdict.
        # It simply contributes nothing.
        print("[preflight] run history unavailable; heartbeat decides.")
        streak = 0
    else:
        streak = consecutive_failures(conclusions)

    reasons = halt_reasons(streak, age_hours)
    # ⭐ A stale heartbeat with no run behind it is GitHub's silence, not a
    # lost push, and pausing for it is a false positive that cost three
    # alerts on 2026-09-04 alone. Applied AFTER halt_reasons so the union
    # shape is untouched: this can only ever remove the one reason it can
    # positively explain, and only on evidence the history is fresh.
    reasons, note = drop_stale_heartbeat_reason(
        reasons, runs, heartbeat, os.environ.get("GITHUB_RUN_ID"))
    if note:
        print(f"[preflight] not halting for the stale heartbeat: {note}.")
    print(f"[preflight] {explain(reasons, age_hours)}")
    publish_halt(bool(reasons))
    if reasons and should_alert(broken_hours(streak, age_hours)):
        send_alert(reasons, age_hours, repo)

    # Written last, so this run's own heartbeat can never influence the
    # decision above, and so a run that halts still refreshes it.
    write_heartbeat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
