"""Guarantee every run has something to commit, so green means "state landed".

Added 2026-08-19 alongside ``prior_runs``.

``prior_runs`` reads the workflow's conclusions and treats a green run as
evidence that state reached the remote. That inference is only sound if
every run actually attempts a push. The commit step short-circuits with::

    if git diff --cached --quiet; then
      echo "No state changes to commit"
      exit 0
    fi

so a quiet hour goes green **without ever contacting the remote**. Left
alone, that would let a single quiet run reset the failure streak and
reopen the gate while the push was still broken - the bot would resume
posting, fail to record, and the orphans would start again.

Writing one small file per run removes the ambiguity: there is always a
staged change, so the push is always exercised, so green always means the
push succeeded. The file is the price of making the signal honest.

⚠️ Written directly rather than through ``state.save``. ``state.PARTITIONS``
is a silent allowlist - keys it does not name are dropped on every save,
without error - so routing the heartbeat through the state machinery would
risk it vanishing exactly as quietly as the bug it exists to detect.
"""

import json
import os
from datetime import datetime, timezone

# ⚠️ Anchored to __file__, never to the working directory. The workflow
# invokes this as `cd scripts && python -m preflight.gate`, so a relative
# "data/state/..." would resolve to scripts/data/state/ - written happily,
# never matched by the commit step's `git add data/`, and therefore never
# pushed. The heartbeat would look fine and prove nothing, which is the
# precise failure mode it exists to rule out.
# Matches state_store.store's `parent.parent.parent` idiom.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
# ⚠️ Deliberately NOT under data/state/. That directory is bot state, and
# state_store.schema requires every file in it to declare an owning module
# and a runtime reader. The heartbeat has neither: nothing in the bot ever
# reads it, and its only consumer is the run conclusion it helps produce.
# Filing it as state would have made the registry describe it as something
# it is not. `git add data/` picks it up either way.
HEARTBEAT_PATH = os.path.join(_REPO_ROOT, "data", "ci_heartbeat.json")


def build_heartbeat(run_id: str, attempt: str, now: datetime) -> dict:
    """The record written each run.

    ``run_id`` alone would repeat across re-runs of the same run, which is
    precisely the case where a human is retrying a broken push and most
    needs the file to change. ``attempt`` disambiguates those, and the
    timestamp covers everything else.
    """
    return {
        "last_run_id": run_id or "local",
        "last_run_attempt": attempt or "1",
        "written_at": now.isoformat(),
        "why": "Proves the state push is exercised every run; see preflight/prior_runs.py",
    }


def read_heartbeat(path: str = HEARTBEAT_PATH) -> dict | None:
    """The heartbeat as checked out, or None if there isn't a usable one.

    ⭐ This is the authoritative "is state persisting" signal, and it must
    be read BEFORE this run writes its own, or it would only ever measure
    itself.

    Its authority comes from how it gets here: the heartbeat only reaches
    the remote inside a successful state commit. So a fresh one in the
    checkout is proof that a recent push landed, and a stale one is proof
    that none did. Unlike the Actions API it cannot be served from a cache,
    because it is not a query - it is the repository's own content.

    None means "cannot tell" (absent, unreadable, malformed) and is kept
    distinct from a stale reading, which is a real answer.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get("written_at") else None


def heartbeat_age_hours(record: dict | None, now: datetime) -> float | None:
    """Hours since the last state push landed, or None if unknowable.

    A timestamp in the future is treated as unknowable rather than as age
    zero. Clock skew that large means something is wrong with the reading,
    and the one thing this must never do is silently report health.
    """
    if not record:
        return None
    try:
        written = datetime.fromisoformat(record["written_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if written.tzinfo is None:
        written = written.replace(tzinfo=timezone.utc)
    age = (now - written).total_seconds() / 3600.0
    return None if age < -0.5 else max(age, 0.0)


def write_heartbeat(now: datetime | None = None, path: str = HEARTBEAT_PATH) -> dict:
    """Write the heartbeat and return it."""
    record = build_heartbeat(
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        now or datetime.now(timezone.utc),
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    return record
