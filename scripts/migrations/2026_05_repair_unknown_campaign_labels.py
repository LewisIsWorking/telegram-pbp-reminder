"""
One-off migration: repair `campaign: "Unknown"` entries in players.json.

Background
----------
Prior to fix/no-unknown-campaign-persistence (PR #1, 2026-05-21), the POTW
cron at scripts/scheduled/potw.py:107 used `maps.to_name.get(pid, "Unknown")`.
When `pid` wasn't yet in `maps` (config staleness, race during a config
update, etc.), the literal string "Unknown" flowed into the pending entry's
`campaign_name`, and then handler._store_boon persisted it as the boon's
`campaign` field in players.json. That value is never overwritten -- the
boon stays labelled "Unknown" forever, displaying as "boon for some game"
in the COO PathWars UI.

The handler/potw fix prevents NEW "Unknown" entries from being written. This
migration repairs the EXISTING ones already in players.json.

What it does
------------
1. Loads config.json and players.json
2. Walks player_boons[topic_id][user_id] -> list of boons
3. For each boon whose `campaign` field is exactly "Unknown":
     - Resolves the real name via helpers_pkg.campaigns.try_get_name(config, topic_id)
     - If resolved: replaces "Unknown" with the real name. Logs the change.
     - If unresolvable: logs a warning and leaves the entry alone (the topic
       may have been retired; a human should review).
4. Writes players.json back out (only if any changes were made).

Idempotent: re-running on already-repaired data is a no-op.

Usage
-----
    python scripts/migrations/2026_05_repair_unknown_campaign_labels.py

    # Dry run (report changes but don't write):
    python scripts/migrations/2026_05_repair_unknown_campaign_labels.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure `scripts/` is on sys.path so we can import helpers_pkg.campaigns
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from helpers_pkg import campaigns  # noqa: E402

CONFIG_PATH = REPO_ROOT / "config.json"
PLAYERS_PATH = REPO_ROOT / "data" / "state" / "players.json"


def repair(dry_run: bool = False) -> int:
    """Returns count of entries repaired (0 = nothing to do)."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    players = json.loads(PLAYERS_PATH.read_text(encoding="utf-8"))

    repaired = 0
    unresolvable = 0
    player_boons = players.get("player_boons", {})

    for topic_id, by_user in player_boons.items():
        for user_id, boons in by_user.items():
            for i, boon in enumerate(boons):
                if boon.get("campaign") != "Unknown":
                    continue
                resolved = campaigns.try_get_name(config, topic_id)
                if resolved:
                    action = "would set" if dry_run else "set"
                    print(
                        f"  [topic {topic_id}] user {user_id} boon[{i}] "
                        f"week={boon.get('week')} date={boon.get('date')}: "
                        f"{action} campaign='{resolved}'"
                    )
                    if not dry_run:
                        boon["campaign"] = resolved
                    repaired += 1
                else:
                    print(
                        f"  WARNING: topic {topic_id} (user {user_id}, "
                        f"week={boon.get('week')}) is unresolvable in current "
                        f"config -- leaving as 'Unknown'. May be a retired "
                        f"campaign; review manually."
                    )
                    unresolvable += 1

    print()
    print(f"Repaired:     {repaired}")
    print(f"Unresolvable: {unresolvable}")

    if repaired > 0 and not dry_run:
        # Match the bot's state-write convention exactly so the diff is minimal:
        # json.dumps(..., indent=2) with default ensure_ascii=True (non-ASCII as
        # \uXXXX escapes) and no trailing newline. Same as queue_io, state_store,
        # state_backup etc. in this repo.
        PLAYERS_PATH.write_text(
            json.dumps(players, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote {PLAYERS_PATH}")
    elif repaired > 0 and dry_run:
        print("\n(dry run -- no changes written)")
    else:
        print("\nNothing to repair.")

    return repaired


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report changes but don't write players.json")
    args = parser.parse_args()
    repair(dry_run=args.dry_run)