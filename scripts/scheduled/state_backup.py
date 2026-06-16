"""
State backup to repository.

Commits a snapshot of the gist state to data/state_backup.json
in the repo weekly, creating a git history of state changes.
This protects against gist corruption or deletion.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import helpers

_BACKUP_PATH = Path(__file__).parent.parent.parent / "data" / "state_backup.json"
_BACKUP_INTERVAL_DAYS = 1  # Daily backup


def backup_state(config: dict, state: dict, *,
                 now: datetime | None = None, **_kw) -> None:
    """Write a state snapshot to the repo for git-tracked backup."""
    now = now or datetime.now(timezone.utc)

    last = state.get("last_state_backup")
    if last and not helpers.interval_elapsed(last, _BACKUP_INTERVAL_DAYS, now):
        return

    # Remove transient keys that don't need backing up
    backup = {k: v for k, v in state.items()
              if not k.startswith("_") and k != "offset"}

    backup["_backup_timestamp"] = now.isoformat()
    backup["_backup_version"] = _read_version()

    try:
        _BACKUP_PATH.write_text(
            json.dumps(backup, indent=2, default=str),
            encoding="utf-8"
        )
        state["last_state_backup"] = now.isoformat()
        print(f"State backup written ({len(json.dumps(backup))} chars)")
    except OSError as e:
        print(f"State backup failed: {e}")


def _read_version() -> str:
    """Read the current bot version."""
    version_path = Path(__file__).parent.parent.parent / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip()
    except OSError:  # pragma: no cover
        return "unknown"  # pragma: no cover
