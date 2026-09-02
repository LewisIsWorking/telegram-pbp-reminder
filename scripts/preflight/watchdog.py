"""Is the bot still running, and if not, start it again.

Extracted from ``preflight/gate.py`` on 2026-09-01, which reached 211
lines once self-repair landed. The gate decides whether **this run** may
post; this decides whether **any run is happening at all**. Different
questions, different failure modes, and only one of them is allowed to
write anything.

⛔⛔ **THE WATCHDOG MUST NOT LIVE INSIDE THE THING IT WATCHES.**
2026-08-31 21:28 to 09-01 12:43: a cron/condition mismatch meant no job's
``if:`` was ever true, so GitHub marked every scheduled run **skipped**.
A skipped run runs no jobs, therefore runs no gate, therefore sends no
alert. The bot stopped for 15 hours and nothing went red, because the
only thing that could have complained was the code that was not
executing. A human noticed a stale queue post.

Invoked from ``.github/workflows/watchdog.yml``, a **separate workflow
file** with its own schedule, because a watchdog job inside the main file
still dies with a broken ``on:`` block there.
"""

import os
from datetime import datetime, timezone

from preflight.heartbeat import heartbeat_age_hours, read_heartbeat
from preflight.prior_runs import (broken_hours, consecutive_failures,
                                  explain, halt_reasons, should_alert)
from preflight.self_repair import (dispatch, dispatch_token, repair_message,
                                   should_repair)


def watch(fetch_conclusions, send_alert, notify=None) -> int:
    """Report, then repair. Writes nothing.

    Collaborators are passed in rather than imported so this can be
    tested without patching module globals, and so it cannot reach
    ``write_heartbeat`` even by accident.

    ⚠️ ``notify`` is accepted and unused since 2026-09-02. The repair
    outcome now rides on ``send_alert``, so there is exactly one message
    per alert. The parameter stays because gate.py passes it and a
    future caller may want an ungated channel; it is deliberately NOT
    wired to anything that fires per-tick.

    ⚠️ It deliberately never writes a heartbeat. Doing so would refresh
    the very signal that proves the outage, and the watchdog would then
    report health forever while nothing else ran.
    """
    age_hours = heartbeat_age_hours(read_heartbeat(),
                                    datetime.now(timezone.utc))
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    conclusions = fetch_conclusions(repo, token) if repo and token else None
    streak = consecutive_failures(conclusions) if conclusions else 0

    reasons = halt_reasons(streak, age_hours)
    print(f"[watchdog] {explain(reasons, age_hours)}")

    # ⭐ Repair FIRST, so its outcome can ride on the one alert below.
    # A workflow_dispatch satisfies the main workflow's own condition
    # regardless of what its cron literals say, so this recovers the
    # 2026-08-31 failure with no human involved.
    #
    # ⚠️ The DISPATCH runs on every tick while the bot is down. It is
    # free, the concurrency group serialises it, and it is the actual
    # recovery. Only the MESSAGE is rationed.
    repair = ""
    if should_repair(age_hours):
        ok, detail = dispatch(repo, dispatch_token(os.environ))
        print(f"[watchdog] self-repair: {detail}")
        repair = repair_message(ok, detail, age_hours)

    # ⛔⛔ ONE MESSAGE, ON THE ALERT CADENCE. Corrected 2026-09-02.
    # This used to notify on every repair attempt, ungated: 48 Telegram
    # messages a day during an outage, each an unrecorded bot message
    # that becomes permanently undeletable after 48h. The watchdog was
    # manufacturing the exact harm it exists to prevent, during the one
    # window in which posting is forbidden for that reason.
    if reasons and should_alert(broken_hours(streak, age_hours)):
        send_alert(reasons, age_hours, repo, extra=repair)
    return 0
